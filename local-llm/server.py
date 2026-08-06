"""Local-only, CUDA-only OpenAI-compatible server for the fine-tuned Qwen model."""
from __future__ import annotations

import json
import os
import socket
import time
import uuid
from pathlib import Path
from threading import Event, Lock
from typing import Literal

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Qwen2TokenizerFast,
    StoppingCriteria,
    StoppingCriteriaList,
    TextIteratorStreamer,
)


MODEL_PATH = Path(os.environ.get(
    "LOCAL_LLM_MODEL_PATH",
    r"D:\QLDownload\Qwen3-1.7B-lora\Qwen3-1.7B-lora\merged",
)).resolve()
MODEL_NAME = os.environ.get("LOCAL_LLM_MODEL_NAME", "tiaozhanbei-qwen3-1.7b-local")
PORT = int(os.environ.get("LOCAL_LLM_PORT", "8010"))
# The merged Qwen3-1.7B BF16 checkpoint fits the 8GB laptop GPU at a 4K context.
# A larger eager-attention context can exhaust VRAM, so trimming always keeps
# the newest question while leaving headroom for generation.
MAX_INPUT_TOKENS = int(os.environ.get("LOCAL_LLM_MAX_INPUT_TOKENS", "4096"))
MAX_OUTPUT_TOKENS = int(os.environ.get("LOCAL_LLM_MAX_OUTPUT_TOKENS", "768"))


def _assert_local_gpu_only() -> None:
    if not MODEL_PATH.is_dir() or not (MODEL_PATH / "config.json").is_file():
        raise RuntimeError(f"本地模型目录无效: {MODEL_PATH}")
    if not torch.cuda.is_available():
        raise RuntimeError("未检测到 CUDA GPU；本服务禁止回退到 CPU。")
    if os.environ.get("CUDA_VISIBLE_DEVICES", "0").strip() in {"", "-1"}:
        raise RuntimeError("CUDA_VISIBLE_DEVICES 禁用了 GPU；本服务不会使用 CPU。")
    # 防止误部署到普通云端主机。云端若没有用户明确设置的本地模型目录，也无法启动。
    if os.environ.get("LOCAL_LLM_ALLOW_NONPRIVATE_HOST", "0") != "1":
        host = socket.gethostname().lower()
        cloud_markers = ("cloud", "ecs", "ec2", "azure", "gcp", "k8s", "kube")
        if any(marker in host for marker in cloud_markers):
            raise RuntimeError("检测到疑似云端主机；本地权重服务已拒绝启动。")


_assert_local_gpu_only()


def _load_tokenizer():
    """Load Unsloth/Transformers-5 exports on the Transformers-4 runtime.

    Transformers 5 writes ``extra_special_tokens`` as a list, while late 4.x
    expects a mapping and fails before it can read tokenizer.json. Constructing
    the fast tokenizer directly preserves the vocabulary and the exported chat
    template without changing the user's model directory.
    """
    config = json.loads((MODEL_PATH / "tokenizer_config.json").read_text(encoding="utf-8"))
    if isinstance(config.get("extra_special_tokens"), list):
        chat_template = (MODEL_PATH / "chat_template.jinja").read_text(encoding="utf-8")
        return Qwen2TokenizerFast(
            tokenizer_file=str(MODEL_PATH / "tokenizer.json"),
            eos_token=config.get("eos_token") or "<|im_end|>",
            pad_token=config.get("pad_token") or "<|endoftext|>",
            model_max_length=int(config.get("model_max_length") or 40960),
            padding_side=config.get("padding_side") or "left",
            additional_special_tokens=list(config.get("extra_special_tokens") or []),
            chat_template=chat_template,
        )
    return AutoTokenizer.from_pretrained(
        str(MODEL_PATH), local_files_only=True, trust_remote_code=False
    )


tokenizer = _load_tokenizer()
tokenizer.truncation_side = "left"
model = AutoModelForCausalLM.from_pretrained(
    str(MODEL_PATH),
    local_files_only=True,
    trust_remote_code=False,
    torch_dtype=torch.bfloat16,
    device_map={"": "cuda:0"},
    low_cpu_mem_usage=True,
).eval()
non_cuda_parameters = [
    name for name, parameter in model.named_parameters()
    if parameter.device.type != "cuda"
]
non_cuda_buffers = [
    name for name, buffer in model.named_buffers()
    if buffer.device.type != "cuda"
]
if non_cuda_parameters or non_cuda_buffers:
    raise RuntimeError(
        "模型存在 CPU 卸载，拒绝启动。"
        f"非 CUDA 参数: {non_cuda_parameters[:5]}；"
        f"非 CUDA 缓冲区: {non_cuda_buffers[:5]}"
    )

app = FastAPI(title="挑战杯本地微调模型", docs_url=None, redoc_url=None)
generation_lock = Lock()


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    model: str = MODEL_NAME
    messages: list[Message]
    temperature: float = Field(default=0.6, ge=0.0, le=2.0)
    top_p: float = Field(default=0.95, gt=0.0, le=1.0)
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    stream: bool = False


@app.get("/")
def root():
    return {
        "status": "running",
        "message": "本机微调模型 GPU 服务运行正常",
        "model": MODEL_NAME,
        "device": torch.cuda.get_device_name(0),
        "cuda": True,
        "project_base_url": "http://host.docker.internal:8010/v1",
        "health": "/health",
    }


def _render_chat(payload: list[dict]) -> str:
    return tokenizer.apply_chat_template(
        payload,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )


def _token_count(payload: list[dict]) -> int:
    return len(tokenizer(_render_chat(payload), add_special_tokens=False)["input_ids"])


def _trim_messages(payload: list[dict]) -> list[dict]:
    """Keep the system contract and newest question within the input budget.

    A raw right-side truncation can delete the latest user message and the
    assistant generation marker. That makes the model continue a stale or
    partial prompt and is the main cause of punctuation-only responses.
    """
    if not payload:
        return payload

    system = payload[0] if payload[0].get("role") == "system" else None
    conversation = payload[1:] if system else payload[:]
    if not conversation:
        return [system] if system else payload

    selected = [conversation[-1]]
    for item in reversed(conversation[:-1]):
        candidate = ([system] if system else []) + [item] + selected
        if _token_count(candidate) > MAX_INPUT_TOKENS:
            break
        selected.insert(0, item)

    candidate = ([system] if system else []) + selected
    if _token_count(candidate) <= MAX_INPUT_TOKENS:
        return candidate

    # If the personalized system context alone is oversized, retain both its
    # stable rules (head) and the newest learning context (tail).
    if system:
        latest_only_cost = _token_count(selected)
        system_budget = max(256, MAX_INPUT_TOKENS - latest_only_cost - 64)
        system_ids = tokenizer(
            str(system.get("content", "")), add_special_tokens=False
        )["input_ids"]
        if len(system_ids) > system_budget:
            head_size = system_budget // 2
            tail_size = system_budget - head_size
            compact_ids = system_ids[:head_size] + system_ids[-tail_size:]
            system = {**system, "content": tokenizer.decode(compact_ids, skip_special_tokens=True)}
        candidate = [system] + selected

    return candidate


def _inputs(messages: list[Message]):
    payload = _trim_messages([item.model_dump() for item in messages])
    text = _render_chat(payload)
    encoded = tokenizer(text, return_tensors="pt", truncation=True, max_length=MAX_INPUT_TOKENS)
    return {key: value.to("cuda:0") for key, value in encoded.items()}


class _CancelledGeneration(StoppingCriteria):
    def __init__(self, cancelled: Event):
        self.cancelled = cancelled

    def __call__(self, input_ids, scores, **kwargs) -> bool:
        return self.cancelled.is_set()


def _event(chunk_id: str, text: str = "", finish_reason=None) -> str:
    body = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": MODEL_NAME,
        "choices": [{"index": 0, "delta": {"content": text} if text else {}, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"


@app.get("/health")
def health():
    return {
        "ok": True,
        "model": MODEL_NAME,
        "device": torch.cuda.get_device_name(0),
        "cuda": True,
        "gpu_only": True,
        "cpu_offload": False,
        "model_path": str(MODEL_PATH),
        "max_input_tokens": MAX_INPUT_TOKENS,
        "max_output_tokens": MAX_OUTPUT_TOKENS,
    }


@app.get("/v1/models")
def models():
    return {"object": "list", "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "local"}]}


@app.post("/v1/chat/completions")
def chat(req: ChatRequest):
    if not req.messages:
        raise HTTPException(400, "messages 不能为空")
    encoded = _inputs(req.messages)
    output_tokens = min(req.max_tokens, MAX_OUTPUT_TOKENS)
    generate_kwargs = dict(
        **encoded,
        max_new_tokens=output_tokens,
        do_sample=req.temperature > 0,
        temperature=max(req.temperature, 0.01),
        top_p=req.top_p,
        top_k=20,
        repetition_penalty=1.12,
        no_repeat_ngram_size=4,
        pad_token_id=tokenizer.pad_token_id,
        eos_token_id=tokenizer.eos_token_id,
    )
    chunk_id = f"chatcmpl-{uuid.uuid4().hex}"

    if req.stream:
        def stream_output():
            cancelled = Event()
            streamer = TextIteratorStreamer(
                tokenizer,
                skip_prompt=True,
                skip_special_tokens=True,
                timeout=10.0,
            )
            generate_kwargs["streamer"] = streamer
            generate_kwargs["stopping_criteria"] = StoppingCriteriaList([
                _CancelledGeneration(cancelled)
            ])
            import threading

            def _generate():
                with torch.inference_mode():
                    model.generate(**generate_kwargs)

            with generation_lock:
                worker = threading.Thread(target=_generate, daemon=True)
                worker.start()
                try:
                    yield _event(chunk_id)
                    for piece in streamer:
                        yield _event(chunk_id, piece)
                    worker.join()
                    yield _event(chunk_id, finish_reason="stop")
                    yield "data: [DONE]\n\n"
                finally:
                    cancelled.set()
                    worker.join(timeout=5.0)
        return StreamingResponse(stream_output(), media_type="text/event-stream")

    with generation_lock, torch.inference_mode():
        output = model.generate(**generate_kwargs)
    prompt_len = encoded["input_ids"].shape[1]
    content = tokenizer.decode(output[0, prompt_len:], skip_special_tokens=True)
    return {
        "id": chunk_id,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": MODEL_NAME,
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": prompt_len, "completion_tokens": output.shape[1] - prompt_len, "total_tokens": output.shape[1]},
    }


if __name__ == "__main__":
    import uvicorn
    # 只监听本机；Docker Desktop 通过 host.docker.internal 转发访问。
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="info")
