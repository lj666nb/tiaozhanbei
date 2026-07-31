# Agent工程化 - API服务化与部署

## 1. 概述

将LangChain Agent封装为REST API是从"实验原型"走向"生产服务"的关键一步。本章从零构建一个可直接部署的Agent API服务，覆盖请求模型设计、异步并发、日志监控、权限控制、流式输出和容器化部署等完整工程链路。

**学完本章你将掌握**：
- 使用FastAPI + Pydantic设计健壮的Agent API
- 异步任务队列与并发控制策略
- 结构化日志 + Prometheus + Grafana 可观测性体系
- 多级API Key管理与速率限制
- SSE流式输出实现Agent"边思考边展示"
- Docker多阶段构建与docker-compose生产级编排

**Image-Prompt(agent API service overview):** A flat-design minimalist 2D vector illustration introducing Agent API service deployment. A central "Agent API Service" hub with five surrounding capability nodes connected by tech light blue #409EFF lines: "FastAPI + Pydantic" (web framework gear icon), "异步并发" (parallel arrows icon), "结构化日志" (JSON log document icon), "Prometheus监控" (graph/chart icon), "Docker部署" (container whale icon). White background with dark blue #1a1a2e labels. Academic API engineering overview visualization with radial layout.

---

## 2. 技术选型对比

在实际项目中，技术栈的选择直接影响系统的性能、可维护性和扩展性。以下是对比分析：

### 2.1 Web框架：FastAPI vs Flask

| 维度 | FastAPI | Flask |
|------|---------|-------|
| 异步支持 | 原生 async/await，基于Starlette | 需额外扩展（Flask 2.0+ 有限支持） |
| 数据校验 | 内置Pydantic，自动生成JSON Schema | 需手动或借助Marshmallow |
| API文档 | 自动生成 Swagger UI + ReDoc | 需Flask-RESTX等扩展 |
| 性能 | 接近Node.js/Go，异步非阻塞 | 同步模型，高并发需Gunicorn+worker |
| 类型安全 | 完整类型注解，IDE智能提示 | 弱 |
| 生态成熟度 | 快速增长，社区活跃 | 非常成熟，插件丰富 |
| WebSocket | 原生支持 | 需Flask-SocketIO |
| 适合场景 | API服务、微服务、高并发IO密集 | 传统Web应用、小型API |

**结论**：对于Agent API服务，FastAPI是更优选择——Agent调用LLM是典型的IO密集型场景，异步非阻塞能极大提升吞吐量。

### 2.2 消息队列/任务调度：Redis vs RabbitMQ vs Celery

| 维度 | Redis (as broker) | RabbitMQ | Celery (框架层) |
|------|-------------------|----------|-----------------|
| 定位 | 内存数据结构存储，可作轻量MQ | 专业消息队列 | 分布式任务队列框架 |
| 协议 | Redis协议 / Redis Streams | AMQP 0-9-1 | 依赖Broker（Redis/RabbitMQ） |
| 消息可靠性 | 持久化可选，断电可能丢消息 | 高可靠，支持ACK/持久化 | 依赖Broker特性 |
| 延迟 | 极低（微秒级） | 低（毫秒级） | 依赖Broker + 轮询间隔 |
| 复杂路由 | 基本（Pub/Sub, Streams） | 丰富（Exchange/Queue/Binding） | 基于Broker |
| 运维复杂度 | 低，通常已部署 | 中等 | 需额外启动Worker进程 |
| 典型搭配 | 轻量任务、缓存 | 关键业务消息 | CPU/IO密集型异步任务 |

**推荐方案**：小型项目 Redis + Celery（复用已有Redis）；中大型项目 RabbitMQ + Celery（消息零丢失需求）。

**Image-Prompt(technology stack comparison):** A flat-design minimalist 2D vector illustration comparing technology choices for Agent API service. Two comparison panels side by side: Left "Web框架 FastAPI vs Flask" showing FastAPI with native async/sync arrows, auto-generated Swagger docs icon, Pydantic validation shield; Flask with simpler but sync-only architecture. Right "消息队列 Redis vs RabbitMQ vs Celery" showing three tiers: Redis (lightweight cache cylinder), RabbitMQ (message queue with ACK arrows), Celery (task queue layer on top). Tech light blue #409EFF for recommended choices. White background with dark blue #1a1a2e labels. Academic technology selection visualization.

---

## 3. 核心代码实现：Agent API服务

### 3.1 项目结构

```
agent-api-service/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI应用入口
│   ├── config.py             # 配置管理
│   ├── models/
│   │   ├── __init__.py
│   │   ├── request.py        # Pydantic请求模型
│   │   └── response.py       # Pydantic响应模型
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py          # Agent封装层
│   │   ├── auth.py           # API Key认证
│   │   └── rate_limit.py     # 速率限制
│   ├── tasks/
│   │   ├── __init__.py
│   │   ├── celery_app.py     # Celery配置
│   │   └── agent_tasks.py    # 异步Agent任务
│   ├── monitoring/
│   │   ├── __init__.py
│   │   ├── logger.py         # 结构化日志
│   │   └── metrics.py        # Prometheus指标
│   └── api/
│       ├── __init__.py
│       ├── v1/
│       │   ├── __init__.py
│       │   ├── agent.py      # Agent API端点
│       │   └── health.py     # 健康检查
├── docker/
│   ├── Dockerfile
│   └── Dockerfile.worker
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── alembic/                  # 数据库迁移（可选）
```

### 3.2 配置管理（config.py）

```python
"""
app/config.py
集中管理所有配置项，支持环境变量覆盖。
使用pydantic-settings实现类型安全的配置加载。
"""
import os
from typing import Optional, List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置，所有字段可从环境变量或.env文件加载"""

    # ── 应用基础配置 ──
    APP_NAME: str = "Agent API Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ── LLM配置 ──
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o"
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    # ── 向量数据库配置 ──
    REDIS_URL: str = "redis://localhost:6379/0"
    # 可选：ChromaDB / Milvus / Pinecone
    VECTOR_STORE_TYPE: str = "chromadb"  # chromadb | redis | pinecone
    CHROMA_PERSIST_DIR: str = "./chroma_data"

    # ── Celery配置 ──
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # ── API Key管理 ──
    # 生产环境应从数据库或Vault加载
    API_KEYS: List[str] = ["sk-test-key-001", "sk-test-key-002"]
    ADMIN_API_KEYS: List[str] = ["sk-admin-key-001"]

    # ── 速率限制 ──
    RATE_LIMIT_DEFAULT: str = "100/minute"   # 默认：每分钟100次
    RATE_LIMIT_PREMIUM: str = "1000/minute"  # 高级：每分钟1000次

    # ── 监控配置 ──
    PROMETHEUS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"
    STRUCTURED_LOG: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
```

### 3.3 请求/响应模型设计（Pydantic）

```python
"""
app/models/request.py
Pydantic请求模型 —— 利用类型系统实现自动校验与文档生成。
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class Message(BaseModel):
    """单条对话消息"""
    role: str = Field(..., description="角色: user / assistant / system")
    content: str = Field(..., min_length=1, max_length=100000, description="消息内容")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = {"user", "assistant", "system"}
        if v not in allowed:
            raise ValueError(f"role 必须是 {allowed} 之一, 收到: {v}")
        return v


class AgentChatRequest(BaseModel):
    """
    Agent对话请求体。
    自动校验：
    - messages 非空
    - temperature 在 [0, 2] 范围内
    - stream 决定是否启用SSE
    """
    messages: List[Message] = Field(
        ..., min_length=1, max_length=100,
        description="对话历史消息列表"
    )
    temperature: float = Field(
        default=0.7, ge=0.0, le=2.0,
        description="LLM温度参数，越高越随机"
    )
    max_tokens: int = Field(
        default=4096, ge=1, le=128000,
        description="最大生成Token数"
    )
    stream: bool = Field(
        default=False,
        description="是否启用流式输出(SSE)"
    )
    tools: Optional[List[str]] = Field(
        default=None,
        description="本次对话启用的工具名称列表，None表示全部可用"
    )
    session_id: Optional[str] = Field(
        default=None, max_length=64,
        description="会话ID，用于多轮对话上下文关联"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="附加元数据，透传到日志/监控"
    )

    class Config:
        # 在Swagger UI中展示示例
        json_schema_extra = {
            "example": {
                "messages": [
                    {"role": "system", "content": "你是一个智能助手，可以搜索网络和运行代码。"},
                    {"role": "user", "content": "帮我查一下今天北京的天气，并告诉我适合穿什么。"}
                ],
                "temperature": 0.7,
                "max_tokens": 4096,
                "stream": True,
                "session_id": "abc-123-def"
            }
        }


class AgentChatResponse(BaseModel):
    """Agent对话响应体"""
    id: str = Field(..., description="响应唯一ID")
    object: str = Field(default="agent.response", description="对象类型")
    created: int = Field(..., description="Unix时间戳")
    model: str = Field(..., description="使用的模型名称")
    choices: List[Dict[str, Any]] = Field(..., description="响应选项")
    usage: Dict[str, int] = Field(
        default_factory=dict,
        description="Token使用统计: {prompt_tokens, completion_tokens, total_tokens}"
    )
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Agent工具调用记录"
    )
    session_id: Optional[str] = Field(default=None, description="会话ID")


class ErrorResponse(BaseModel):
    """统一错误响应格式"""
    error: dict = Field(..., description="错误详情")
```

### 3.4 Agent封装层（core/agent.py）

```python
"""
app/core/agent.py
LangChain Agent封装 —— 将Agent逻辑与HTTP层解耦。
支持同步/异步调用、工具注册、流式输出。
"""
import time
from typing import AsyncIterator, Dict, Any, Optional, List
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import tool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.config import settings
from app.monitoring.logger import get_logger

logger = get_logger(__name__)


# ── 工具定义示例 ──

@tool
def search_web(query: str) -> str:
    """搜索互联网获取最新信息。参数query为搜索关键词。"""
    # 生产环境替换为真实的搜索API（如SerpAPI、Bing API）
    return f"[模拟搜索] 关于'{query}'的结果：今日北京天气晴，15°C~25°C，微风。"


@tool
def run_python_code(code: str) -> str:
    """在沙箱中运行Python代码并返回结果。"""
    import io, sys
    old_stdout = sys.stdout
    sys.stdout = buffer = io.StringIO()
    try:
        # ⚠️ 生产环境务必使用Docker沙箱或RestrictedPython！
        exec(code, {"__builtins__": __builtins__}, {})
        result = buffer.getvalue() or "代码执行完成（无输出）"
    except Exception as e:
        result = f"代码执行错误: {e}"
    finally:
        sys.stdout = old_stdout
    return result


class AgentService:
    """
    Agent服务层。
    负责：初始化LLM → 注册工具 → 创建Agent → 管理执行生命周期。
    """

    def __init__(self):
        self.llm = self._init_llm()
        self.tools = self._register_tools()
        self.agent = self._create_agent()
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            verbose=settings.DEBUG,
            max_iterations=15,           # 防止无限循环
            max_execution_time=300,      # 最大执行秒数
            handle_parsing_errors=True,  # 优雅处理格式错误
            return_intermediate_steps=True,  # 返回工具调用轨迹
        )

    def _init_llm(self) -> ChatOpenAI:
        """初始化LLM，支持多模型切换"""
        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            temperature=0.7,
            max_tokens=4096,
        )

    def _register_tools(self) -> list:
        """注册Agent可用工具"""
        return [search_web, run_python_code]

    def _create_agent(self):
        """创建OpenAI Tools Agent"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", "你是一个智能助手，可以使用工具来完成任务。"
                       "如果需要进行搜索或执行代码，请调用对应的工具。"
                       "回答使用中文。"),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        return create_openai_tools_agent(self.llm, self.tools, prompt)

    async def chat(
        self,
        messages: List[Dict[str, str]],
        session_id: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        异步执行Agent对话（非流式）。

        Args:
            messages: 对话消息列表
            session_id: 会话ID
            **kwargs: 透传参数（temperature, max_tokens等）

        Returns:
            包含response/content/usage/tool_calls的标准字典
        """
        start_time = time.time()
        logger.info("agent_chat_start", session_id=session_id, msg_count=len(messages))

        # 将消息列表转换为LangChain格式
        human_msg = _extract_last_human(messages)
        chat_history = _convert_to_langchain_format(messages[:-1])

        try:
            result = await self.executor.ainvoke({
                "input": human_msg,
                "chat_history": chat_history,
                **kwargs,
            })

            elapsed = time.time() - start_time
            # 从中间步骤中提取工具调用信息
            tool_calls = [
                {"tool": step[0].tool, "input": step[0].tool_input, "output": step[1]}
                for step in result.get("intermediate_steps", [])
            ]

            response_data = {
                "id": f"agent-{int(start_time)}",
                "object": "agent.response",
                "created": int(start_time),
                "model": settings.OPENAI_MODEL,
                "choices": [{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result["output"],
                    },
                    "finish_reason": "stop",
                }],
                "usage": self._estimate_usage(messages, result["output"]),
                "tool_calls": tool_calls,
                "session_id": session_id,
            }

            logger.info(
                "agent_chat_complete",
                session_id=session_id,
                elapsed_ms=int(elapsed * 1000),
                tool_call_count=len(tool_calls),
            )
            return response_data

        except Exception as e:
            logger.error("agent_chat_error", session_id=session_id, error=str(e))
            raise

    async def chat_stream(
        self,
        messages: List[Dict[str, str]],
        session_id: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """
        SSE流式输出 —— 逐步yield Agent思考过程。

        使用async generator实现：
        - 先yield工具调用事件
        - 再yield LLM生成的token
        - 最后yield完成事件
        """
        start_time = time.time()
        logger.info("agent_chat_stream_start", session_id=session_id)
        human_msg = _extract_last_human(messages)
        chat_history = _convert_to_langchain_format(messages[:-1])

        try:
            async for event in self.executor.astream_events(
                {"input": human_msg, "chat_history": chat_history},
                version="v2",
            ):
                kind = event["event"]

                # 工具调用开始
                if kind == "on_tool_start":
                    yield _sse_event("tool_start", {
                        "tool": event["name"],
                        "input": str(event["data"].get("input", "")),
                    })
                # 工具调用结束
                elif kind == "on_tool_end":
                    yield _sse_event("tool_end", {
                        "tool": event["name"],
                        "output": str(event["data"].get("output", "")),
                    })
                # LLM生成的token
                elif kind == "on_chat_model_stream":
                    chunk = event["data"].get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        yield _sse_event("token", {
                            "content": chunk.content,
                        })

            # 完成事件
            elapsed_ms = int((time.time() - start_time) * 1000)
            yield _sse_event("done", {
                "session_id": session_id,
                "elapsed_ms": elapsed_ms,
            })

        except Exception as e:
            logger.error("agent_chat_stream_error", session_id=session_id, error=str(e))
            yield _sse_event("error", {"message": str(e)})

    def _estimate_usage(self, messages: list, output: str) -> dict:
        """粗略估算Token使用量（生产环境应使用LLM返回的精确usage）"""
        # 简单估算：中文约1.5字符/token，英文约4字符/token
        prompt_chars = sum(len(m.get("content", "")) for m in messages)
        return {
            "prompt_tokens": prompt_chars // 3,
            "completion_tokens": len(output) // 3,
            "total_tokens": (prompt_chars + len(output)) // 3,
        }


# ── 辅助函数 ──

def _extract_last_human(messages: list) -> str:
    """从消息列表中提取最后一条人类消息"""
    for msg in reversed(messages):
        role = msg.get("role") if isinstance(msg, dict) else getattr(msg, "role", None)
        content = msg.get("content") if isinstance(msg, dict) else getattr(msg, "content", "")
        if role == "user":
            return content
    return ""


def _convert_to_langchain_format(messages: list) -> list:
    """将字典格式消息转为LangChain Message对象"""
    role_map = {
        "user": HumanMessage,
        "assistant": AIMessage,
        "system": SystemMessage,
    }
    result = []
    for msg in messages:
        role = msg["role"] if isinstance(msg, dict) else msg.role
        content = msg["content"] if isinstance(msg, dict) else msg.content
        msg_cls = role_map.get(role)
        if msg_cls:
            result.append(msg_cls(content=content))
    return result


def _sse_event(event_type: str, data: dict) -> str:
    """构造SSE事件字符串"""
    import json
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
```

### 3.5 API Key认证与速率限制

```python
"""
app/core/auth.py
多级API Key管理 —— 区分普通用户与管理员权限。
"""
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)


class APIKeyTier:
    """API Key等级定义"""
    BASIC = "basic"       # 基础用户
    PREMIUM = "premium"   # 高级用户
    ADMIN = "admin"       # 管理员


async def verify_api_key(api_key: str = Security(api_key_header)) -> dict:
    """
    验证API Key并返回权限信息。

    Returns:
        {"key": "...", "tier": "basic"|"premium"|"admin"}
    """
    if api_key in settings.ADMIN_API_KEYS:
        return {"key": api_key, "tier": APIKeyTier.ADMIN}
    if api_key in settings.API_KEYS:
        return {"key": api_key, "tier": APIKeyTier.BASIC}
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "invalid_api_key", "message": "无效的API Key"}},
    )


async def verify_admin(api_key: str = Security(api_key_header)) -> dict:
    """仅允许管理员API Key"""
    if api_key not in settings.ADMIN_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": {"code": "forbidden", "message": "需要管理员权限"}},
        )
    return {"key": api_key, "tier": APIKeyTier.ADMIN}
```

```python
"""
app/core/rate_limit.py
基于slowapi的速率限制 —— 按API Key级别差异化限制。
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

# 创建全局Limiter实例
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200/minute"],  # 全局默认
)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """超出速率限制时的自定义响应"""
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "rate_limit_exceeded",
                "message": f"请求频率超过限制: {exc.limit}",
                "retry_after": exc.retry_after,
            }
        },
    )
```

### 3.6 结构化日志系统

```python
"""
app/monitoring/logger.py
基于structlog的结构化日志 —— 每行日志均为JSON，便于ELK/Loki采集。
"""
import structlog
import logging
import json
from datetime import datetime, timezone


def setup_logging(log_level: str = "INFO"):
    """初始化结构化日志系统"""

    # 自定义JSON渲染器
    def json_renderer(_, __, event_dict):
        event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
        return json.dumps(event_dict, ensure_ascii=False)

    # 配置structlog处理器链
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.JSONRenderer(ensure_ascii=False),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 设置标准库日志级别
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, log_level.upper(), logging.INFO),
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """获取结构化日志实例"""
    return structlog.get_logger(name)


# 启动时调用
setup_logging()
```

**结构化日志输出示例**：

```json
{"timestamp": "2025-07-09T10:30:45.123Z", "level": "info", "logger": "app.api.v1.agent", "event": "agent_chat_start", "session_id": "abc-123", "msg_count": 3}
{"timestamp": "2025-07-09T10:30:48.456Z", "level": "info", "logger": "app.api.v1.agent", "event": "agent_chat_complete", "session_id": "abc-123", "elapsed_ms": 3333, "tool_call_count": 2}
```

### 3.7 Prometheus指标暴露

```python
"""
app/monitoring/metrics.py
Prometheus指标定义 —— 用量、延迟、错误率、Token消耗。
通过 /metrics 端点暴露，供Prometheus采集。
"""
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from typing import Optional


# ── 请求量指标 ──
REQUEST_COUNT = Counter(
    "agent_api_requests_total",
    "Agent API请求总数",
    ["method", "endpoint", "status_code", "api_key_tier"],
)

# ── 请求延迟指标 ──
REQUEST_LATENCY = Histogram(
    "agent_api_request_duration_seconds",
    "Agent API请求延迟（秒）",
    ["method", "endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 300.0],
)

# ── Token消耗指标 ──
TOKEN_USAGE = Counter(
    "agent_token_usage_total",
    "Token消耗总数",
    ["model", "type"],  # type: prompt | completion | total
)

# ── 活跃会话数 ──
ACTIVE_SESSIONS = Gauge(
    "agent_active_sessions",
    "当前活跃会话数",
)

# ── 错误率指标 ──
ERROR_COUNT = Counter(
    "agent_api_errors_total",
    "Agent API错误总数",
    ["method", "endpoint", "error_type"],
)

# ── Agent执行步骤数 ──
AGENT_STEPS = Histogram(
    "agent_execution_steps",
    "Agent执行步骤数分布",
    buckets=[1, 2, 3, 5, 7, 10, 15, 20],
)


class MetricsMiddleware:
    """
    ASGI中间件：自动记录每个请求的延迟与状态码。
    无需在每个端点手动调用。
    """

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return

        import time
        start = time.time()

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_code = message["status"]
                method = scope.get("method", "UNKNOWN")
                path = scope.get("path", "/")
                # 排除 /metrics 自身
                if path != "/metrics":
                    REQUEST_COUNT.labels(
                        method=method, endpoint=path,
                        status_code=str(status_code), api_key_tier="unknown"
                    ).inc()
                    REQUEST_LATENCY.labels(
                        method=method, endpoint=path
                    ).observe(time.time() - start)
            await send(message)

        await self.app(scope, receive, send_wrapper)


def get_metrics_response() -> bytes:
    """返回Prometheus格式的指标数据"""
    return generate_latest()
```

### 3.8 Celery异步任务队列

```python
"""
app/tasks/celery_app.py
Celery应用配置 —— 处理耗时Agent任务，避免阻塞API响应。
"""
from celery import Celery
from app.config import settings

# 创建Celery应用实例
celery_app = Celery(
    "agent_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.agent_tasks"],  # 自动发现任务模块
)

# Celery配置优化
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_acks_late=True,               # 任务执行完成后才ACK，防止丢失
    worker_prefetch_multiplier=1,      # 公平调度，每个worker一次只取一个任务
    task_soft_time_limit=300,          # 软超时（秒），抛异常
    task_time_limit=600,               # 硬超时（秒），强制终止
    result_expires=3600,               # 结果过期时间（秒）
)
```

```python
"""
app/tasks/agent_tasks.py
Celery异步Agent任务 —— 处理耗时的Agent执行。
"""
from app.tasks.celery_app import celery_app
from app.core.agent import AgentService
from app.monitoring.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def run_agent_task(self, messages: list, session_id: str = None, **kwargs):
    """
    异步执行Agent对话任务。

    使用场景：
    - 复杂多步推理任务（预计超过30秒）
    - 批量处理任务
    - 定时触发任务

    Returns:
        任务结果字典
    """
    logger.info("celery_agent_task_start", task_id=self.request.id, session_id=session_id)
    try:
        agent_service = AgentService()
        # 注意：Celery task中需用同步方式或asyncio.run()
        import asyncio
        result = asyncio.run(agent_service.chat(messages, session_id, **kwargs))
        logger.info(
            "celery_agent_task_success",
            task_id=self.request.id,
            session_id=session_id,
        )
        return result
    except Exception as exc:
        logger.error(
            "celery_agent_task_failed",
            task_id=self.request.id,
            error=str(exc),
        )
        # 自动重试
        raise self.retry(exc=exc)


@celery_app.task(bind=True)
def batch_agent_task(self, request_list: list):
    """批量Agent任务处理"""
    results = []
    for req in request_list:
        result = run_agent_task.delay(
            messages=req["messages"],
            session_id=req.get("session_id"),
            **req.get("kwargs", {}),
        )
        results.append({"task_id": result.id, "session_id": req.get("session_id")})
    return {"total": len(results), "tasks": results}
```

### 3.9 FastAPI主应用与API端点

```python
"""
app/main.py
FastAPI应用入口 —— 组装所有中间件、路由、事件处理器。
"""
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.core.agent import AgentService
from app.core.auth import verify_api_key
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
from app.models.request import AgentChatRequest
from app.models.response import ErrorResponse
from app.monitoring.metrics import (
    get_metrics_response, MetricsMiddleware,
    REQUEST_COUNT, TOKEN_USAGE, ERROR_COUNT, ACTIVE_SESSIONS,
)
from app.monitoring.logger import get_logger

logger = get_logger(__name__)

# 全局Agent服务实例（单例）
agent_service = AgentService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("app_startup", version=settings.APP_VERSION)
    # 启动时：预热模型、检查依赖服务连接
    yield
    # 关闭时：清理资源
    logger.info("app_shutdown")


# ── 创建FastAPI应用 ──
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="LangChain Agent REST API - 生产级Agent服务化解决方案",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── 注册中间件（顺序敏感！） ──

# 1. CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应限定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Prometheus指标中间件
app.add_middleware(MetricsMiddleware)

# 3. 速率限制
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


# ── 健康检查 ──
@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查端点（无需认证）"""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "timestamp": int(time.time()),
    }


# ── Prometheus指标 ──
@app.get("/metrics", tags=["系统"])
async def metrics():
    """Prometheus指标采集端点"""
    return StreamingResponse(
        content=iter([get_metrics_response()]),
        media_type="text/plain; charset=utf-8",
    )


# ── Agent对话（非流式） ──
@app.post(
    "/api/v1/agent/chat",
    tags=["Agent"],
    response_model=None,  # 动态模型
    responses={
        200: {"description": "成功响应"},
        401: {"model": ErrorResponse, "description": "认证失败"},
        429: {"model": ErrorResponse, "description": "速率限制"},
        500: {"model": ErrorResponse, "description": "服务内部错误"},
    },
)
@limiter.limit("100/minute")
async def agent_chat(
    request: Request,
    body: AgentChatRequest,
    api_key_info: dict = Depends(verify_api_key),
):
    """
    Agent对话接口（非流式）。

    适用场景：短对话、批量调用、需要完整响应后处理。
    """
    method = request.method
    endpoint = "/api/v1/agent/chat"

    try:
        ACTIVE_SESSIONS.inc()
        result = await agent_service.chat(
            messages=[m.model_dump() for m in body.messages],
            session_id=body.session_id,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )

        # 记录Token消耗
        usage = result.get("usage", {})
        TOKEN_USAGE.labels(model=settings.OPENAI_MODEL, type="prompt").inc(usage.get("prompt_tokens", 0))
        TOKEN_USAGE.labels(model=settings.OPENAI_MODEL, type="completion").inc(usage.get("completion_tokens", 0))
        TOKEN_USAGE.labels(model=settings.OPENAI_MODEL, type="total").inc(usage.get("total_tokens", 0))

        logger.info(
            "api_agent_chat_success",
            api_key_tier=api_key_info["tier"],
            session_id=body.session_id,
        )
        return JSONResponse(content=result)

    except Exception as e:
        ERROR_COUNT.labels(method=method, endpoint=endpoint, error_type=type(e).__name__).inc()
        logger.error("api_agent_chat_error", error=str(e), session_id=body.session_id)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": str(e)}},
        )
    finally:
        ACTIVE_SESSIONS.dec()


# ── Agent对话（SSE流式） ──
@app.post(
    "/api/v1/agent/chat/stream",
    tags=["Agent"],
    responses={
        200: {
            "description": "SSE流式响应",
            "content": {"text/event-stream": {}},
        },
    },
)
@limiter.limit("50/minute")  # 流式端点限制更严格
async def agent_chat_stream(
    request: Request,
    body: AgentChatRequest,
    api_key_info: dict = Depends(verify_api_key),
):
    """
    Agent流式对话接口（SSE）。

    适用场景：需要实时展示Agent思考过程、工具调用、逐步生成。

    事件类型：
    - tool_start: 工具调用开始
    - tool_end: 工具调用完成
    - token: LLM生成片段
    - done: 对话完成
    - error: 错误事件
    """
    logger.info(
        "api_agent_stream_start",
        session_id=body.session_id,
        api_key_tier=api_key_info["tier"],
    )

    async def event_generator():
        try:
            ACTIVE_SESSIONS.inc()
            async for sse_data in agent_service.chat_stream(
                messages=[m.model_dump() for m in body.messages],
                session_id=body.session_id,
                temperature=body.temperature,
                max_tokens=body.max_tokens,
            ):
                yield sse_data
        except Exception as e:
            ERROR_COUNT.labels(
                method=request.method,
                endpoint="/api/v1/agent/chat/stream",
                error_type=type(e).__name__,
            ).inc()
            yield f"event: error\ndata: {{\"message\": \"{str(e)}\"}}\n\n"
        finally:
            ACTIVE_SESSIONS.dec()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用Nginx缓冲
        },
    )


# ── 使用量查询（管理员） ──
@app.get("/api/v1/admin/usage", tags=["管理"])
async def get_usage_stats():
    """查询API使用统计（需管理员权限）"""
    from prometheus_client import REGISTRY
    metrics_data = {}
    for metric in REGISTRY.collect():
        samples = []
        for s in metric.samples:
            samples.append({"name": s.name, "labels": dict(s.labels), "value": s.value})
        if samples:
            metrics_data[metric.name] = samples
    return {"metrics": metrics_data}


# ── 启动入口 ──
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
```

**Image-Prompt(agent API service architecture):** A flat-design minimalist 2D vector illustration of the complete Agent API service architecture. A layered architecture diagram: Top layer "FastAPI Routes" (/api/v1/agent/chat, /health, /metrics) → Middle layer "Core Services" (AgentService, Auth, Rate Limiter as horizontal blocks) → Bottom layer "Infrastructure" (LLM API, Redis, Celery, ChromaDB). Side panels: "Monitoring" (Prometheus + Grafana dashboards), "Logging" (structured JSON log stream). Flow arrows in tech light blue #409EFF between layers. White background with dark blue #1a1a2e labels. Academic service architecture visualization.

---

## 4. 容器化部署

### 4.1 Dockerfile（多阶段构建）

```dockerfile
# ============================================================
# docker/Dockerfile
# 多阶段构建 — 最小化最终镜像体积
# ============================================================

# ── 阶段1：构建依赖 ──
FROM python:3.12-slim AS builder

WORKDIR /app

# 安装Poetry或直接使用pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 先复制依赖文件（利用Docker层缓存）
COPY requirements.txt .

# 在虚拟环境中安装依赖
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


# ── 阶段2：生产镜像 ──
FROM python:3.12-slim AS production

# 安装运行时依赖（比build-essential体积小）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户（安全最佳实践）
RUN groupadd -r agent && useradd -r -g agent -d /app agent

WORKDIR /app

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 复制应用代码
COPY --chown=agent:agent app/ ./app/

# 复制配置文件
COPY --chown=agent:agent .env.example .env

# 切换到非root用户
USER agent

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 4.2 Dockerfile.worker（Celery Worker）

```dockerfile
# ============================================================
# docker/Dockerfile.worker
# Celery Worker专用镜像
# ============================================================
FROM python:3.12-slim

RUN groupadd -r celery && useradd -r -g celery -d /app celery

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=celery:celery app/ ./app/

USER celery

# Celery Worker启动命令
# --concurrency 控制并发worker数
# --queues 指定监听的队列
CMD ["celery", "-A", "app.tasks.celery_app", "worker", \
     "--loglevel=info", \
     "--concurrency=4", \
     "--queues=agent_tasks"]
```

### 4.3 docker-compose.yml（完整编排）

```yaml
# ============================================================
# docker-compose.yml
# 生产级Agent API服务编排
# 包含：API服务、Celery Worker、Redis、ChromaDB向量数据库
# ============================================================

version: "3.9"

services:
  # ── Agent API服务 ──
  agent-api:
    build:
      context: .
      dockerfile: docker/Dockerfile
      target: production
    container_name: agent-api
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
      - CHROMA_PERSIST_DIR=/data/chroma
      - LOG_LEVEL=INFO
      - STRUCTURED_LOG=true
      - API_KEYS=${API_KEYS:-sk-test-key-001,sk-test-key-002}
      - ADMIN_API_KEYS=${ADMIN_API_KEYS:-sk-admin-key-001}
    volumes:
      - chroma_data:/data/chroma
      - ./logs:/app/logs
    depends_on:
      redis:
        condition: service_healthy
      chromadb:
        condition: service_started
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 15s
    networks:
      - agent-network

  # ── Celery Worker ──
  celery-worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    container_name: agent-celery-worker
    command: >
      celery -A app.tasks.celery_app worker
      --loglevel=info
      --concurrency=4
      --queues=agent_tasks
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - REDIS_URL=redis://redis:6379/0
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
      - LOG_LEVEL=INFO
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      replicas: 2  # 启动2个Worker实例
    networks:
      - agent-network

  # ── Celery Beat（定时任务调度） ──
  celery-beat:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    container_name: agent-celery-beat
    command: >
      celery -A app.tasks.celery_app beat
      --loglevel=info
      --schedule=/data/celerybeat-schedule
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/1
      - CELERY_RESULT_BACKEND=redis://redis:6379/2
    volumes:
      - celery_beat_data:/data
    depends_on:
      redis:
        condition: service_healthy
    networks:
      - agent-network

  # ── Redis ──
  redis:
    image: redis:7-alpine
    container_name: agent-redis
    command: >
      redis-server
      --appendonly yes
      --maxmemory 512mb
      --maxmemory-policy allkeys-lru
      --save 900 1
      --save 300 10
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - agent-network

  # ── ChromaDB 向量数据库 ──
  chromadb:
    image: chromadb/chroma:latest
    container_name: agent-chromadb
    ports:
      - "8001:8000"  # 映射到8001避免和API冲突
    environment:
      - IS_PERSISTENT=TRUE
      - PERSIST_DIRECTORY=/chroma/chroma
      - ANONYMIZED_TELEMETRY=FALSE
    volumes:
      - chroma_data:/chroma/chroma
    restart: unless-stopped
    networks:
      - agent-network

  # ── Prometheus（监控采集） ──
  prometheus:
    image: prom/prometheus:latest
    container_name: agent-prometheus
    volumes:
      - ./deploy/prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
      - '--storage.tsdb.retention.time=30d'
    ports:
      - "9090:9090"
    depends_on:
      - agent-api
    restart: unless-stopped
    networks:
      - agent-network

  # ── Grafana（可视化仪表盘） ──
  grafana:
    image: grafana/grafana:latest
    container_name: agent-grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_USER=${GRAFANA_USER:-admin}
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
      - GF_INSTALL_PLUGINS=grafana-piechart-panel
    volumes:
      - grafana_data:/var/lib/grafana
      - ./deploy/grafana/dashboards:/etc/grafana/provisioning/dashboards
      - ./deploy/grafana/datasources:/etc/grafana/provisioning/datasources
    depends_on:
      - prometheus
    restart: unless-stopped
    networks:
      - agent-network

# ── 持久化存储卷 ──
volumes:
  redis_data:
    driver: local
  chroma_data:
    driver: local
  prometheus_data:
    driver: local
  grafana_data:
    driver: local
  celery_beat_data:
    driver: local

# ── 网络 ──
networks:
  agent-network:
    driver: bridge
```

### 4.4 Prometheus配置与Grafana仪表盘

```yaml
# deploy/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: "agent-api"
    metrics_path: "/metrics"
    static_configs:
      - targets: ["agent-api:8000"]
        labels:
          service: "agent-api"
```

**Grafana仪表盘推荐面板**（文字描述）：

```
┌─────────────────────────────────────────────────────────┐
│  Agent API 运维仪表盘                                    │
├──────────────────────────┬──────────────────────────────┤
│ Stat: 总请求数           │ Stat: 平均延迟 (P50/P95/P99)  │
│ Stat: 错误率             │ Stat: 今日Token消耗           │
├──────────────────────────┼──────────────────────────────┤
│ Timeseries: QPS趋势      │ Timeseries: 延迟分布(分位)    │
│ Timeseries: 错误率趋势    │ Timeseries: Token消耗趋势     │
├──────────────────────────┼──────────────────────────────┤
│ Bar Gauge: 各API Key用量 │ Pie Chart: 错误类型分布       │
│ Heatmap: 延迟热力图      │ Table: 最近错误日志            │
└──────────────────────────┴──────────────────────────────┘
```

**Image-Prompt(docker compose deployment architecture):** A flat-design minimalist 2D vector illustration of the docker-compose deployment architecture. Seven service containers arranged in a structured layout: "agent-api" (FastAPI icon with port 8000), "celery-worker" (worker gear icon with x2 replicas), "celery-beat" (clock scheduler icon), "redis" (Redis cube with health check), "chromadb" (vector database icon with port 8001), "prometheus" (metrics scraper icon with port 9090), "grafana" (dashboard icon with port 3000). All connected via "agent-network" bridge at bottom. Tech light blue #409EFF for container borders. White background with dark blue #1a1a2e labels. Academic container orchestration visualization.

---

## 5. 部署架构图（文字描述）

```
                         ┌──────────────┐
                         │   用户/客户端  │
                         └──────┬───────┘
                                │ HTTPS (TLS终端由Nginx/Cloudflare处理)
                                ▼
                  ┌─────────────────────────┐
                  │    Nginx 反向代理        │
                  │  (可选: 负载均衡/缓存)    │
                  └────────────┬────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
    ┌─────────────┐  ┌──────────────┐  ┌──────────────┐
    │ Agent API   │  │ Agent API    │  │ Agent API    │
    │ Instance 1  │  │ Instance 2   │  │ Instance N   │
    │ (FastAPI)   │  │ (FastAPI)    │  │ (FastAPI)    │
    └──────┬──────┘  └──────┬───────┘  └──────┬───────┘
           │                │                 │
           └────────────────┼─────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
    ┌─────────────┐ ┌──────────────┐ ┌──────────────┐
    │    Redis    │ │  Celery      │ │  ChromaDB /  │
    │ (缓存/队列)  │ │  Workers     │ │ 向量数据库    │
    └─────────────┘ └──────┬───────┘ └──────────────┘
                           │
                           ▼
                   ┌───────────────┐
                   │  外部LLM API  │
                   │ (OpenAI等)    │
                   └───────────────┘

    ┌─────────┐    ┌─────────┐    ┌──────────┐
    │Prometheus│◄───│ Agent   │───►│ Grafana  │
    │ (采集)   │    │ /metrics│    │ (可视化) │
    └─────────┘    └─────────┘    └──────────┘

数据流说明：
1. 用户请求 → Nginx → FastAPI → 认证/限流检查
2. 短任务 → 直接在API进程中异步执行 → 返回结果
3. 长任务 → 投递到Celery队列 → Worker消费 → 结果写入Redis → API轮询返回
4. 所有请求指标 → /metrics端点 → Prometheus采集 → Grafana展示
5. 结构化日志 → stdout → ELK/Loki等日志平台采集
```

**Image-Prompt(production deployment architecture):** A flat-design minimalist 2D vector illustration of the production deployment architecture. Top: "用户/客户端" → "Nginx 反向代理" (HTTPS/TLS shield) → three "Agent API Instance" (FastAPI servers with load balancing arrows). Middle layer: "Redis" (cache/queue), "Celery Workers" (task processors), "ChromaDB" (vector database). Bottom: "External LLM APIs" (OpenAI cloud icon). Side monitoring column: "Prometheus" scraping /metrics → "Grafana" dashboards. Log stream flowing to "ELK/Loki". Tech light blue #409EFF for data flow lines. White background with dark blue #1a1a2e labels. Academic production infrastructure visualization.

---

## 6. 完整启动与测试流程

### 6.1 requirements.txt

```txt
# ── Web框架 ──
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.10.0
pydantic-settings==2.6.0

# ── LangChain生态 ──
langchain==0.3.0
langchain-openai==0.2.0
langchain-core==0.3.0

# ── 异步任务 ──
celery==5.4.0
redis==5.1.0

# ── 监控日志 ──
structlog==24.4.0
prometheus-client==0.21.0

# ── 安全 ──
slowapi==0.1.9
python-multipart==0.0.9

# ── 数据库/向量存储 ──
chromadb==0.5.0
sqlalchemy==2.0.35

# ── 工具 ──
httpx==0.27.0
python-dotenv==1.0.1
```

### 6.2 本地开发启动

```bash
# 1. 克隆并进入项目
cd agent-api-service

# 2. 创建虚拟环境
python -m venv .venv && source .venv/bin/activate  # Linux/Mac
# 或 .venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑.env填入OPENAI_API_KEY等

# 5. 启动Redis（Docker）
docker run -d --name agent-redis -p 6379:6379 redis:7-alpine

# 6. 启动API服务（开发模式，热重载）
python -m app.main
# 或 uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 7. （另一个终端）启动Celery Worker
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=4

# 8. 访问API文档
# 浏览器打开: http://localhost:8000/docs
```

### 6.3 Docker Compose生产部署

```bash
# 完整启动所有服务
docker compose up -d

# 查看日志
docker compose logs -f agent-api

# 查看服务状态
docker compose ps

# 扩容Worker（处理高峰负载）
docker compose up -d --scale celery-worker=4

# 停止所有服务
docker compose down

# 彻底清理（含数据卷）
docker compose down -v
```

### 6.4 API测试示例

```bash
# 健康检查（无需认证）
curl http://localhost:8000/health

# 非流式对话
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-test-key-001" \
  -d '{
    "messages": [
      {"role": "system", "content": "你是智能助手"},
      {"role": "user", "content": "什么是Docker多阶段构建？请简要说明。"}
    ],
    "temperature": 0.7,
    "stream": false
  }'

# 流式对话（SSE）
curl -N -X POST http://localhost:8000/api/v1/agent/chat/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk-test-key-001" \
  -d '{
    "messages": [
      {"role": "user", "content": "今天的天气如何？"}
    ],
    "stream": true
  }'

# Prometheus指标
curl http://localhost:8000/metrics
```

**SSE流式响应示例**：

```
event: tool_start
data: {"tool": "search_web", "input": "{'query': '今天天气'}"}

event: tool_end
data: {"tool": "search_web", "output": "[模拟搜索] 关于'今天天气'的结果：今日北京天气晴，15°C~25°C，微风。"}

event: token
data: {"content": "根据"}

event: token
data: {"content": "搜索结果"}

event: token
data: {"content": "，今天北京天气晴朗"}

event: token
data: {"content": "，气温在15到25度之间"}

event: done
data: {"session_id": "abc-123", "elapsed_ms": 3250}
```

### 6.5 Python SDK调用示例

```python
"""
客户端示例 —— 用httpx调用Agent API进行流式消费
"""
import json
import httpx


class AgentClient:
    """Agent API客户端封装"""

    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key or "sk-test-key-001",
        }

    def chat(self, user_message: str, system_prompt: str = None) -> dict:
        """非流式对话"""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        with httpx.Client(timeout=120) as client:
            resp = client.post(
                f"{self.base_url}/api/v1/agent/chat",
                headers=self.headers,
                json={"messages": messages, "stream": False},
            )
            resp.raise_for_status()
            return resp.json()

    def chat_stream(self, user_message: str, system_prompt: str = None):
        """
        流式对话 —— generator方式逐事件yield。

        使用方式:
            for event in client.chat_stream("你好"):
                print(event)
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_message})

        with httpx.Client(timeout=300) as client:
            with client.stream(
                "POST",
                f"{self.base_url}/api/v1/agent/chat/stream",
                headers=self.headers,
                json={"messages": messages, "stream": True},
            ) as resp:
                resp.raise_for_status()
                current_event = None
                current_data = ""
                for line in resp.iter_lines():
                    if line.startswith("event: "):
                        current_event = line[7:]
                    elif line.startswith("data: "):
                        current_data = line[6:]
                    elif line == "" and current_event:  # 空行表示事件结束
                        yield {
                            "event": current_event,
                            "data": json.loads(current_data),
                        }
                        current_event = None
                        current_data = ""


# ── 使用示例 ──
if __name__ == "__main__":
    client = AgentClient(api_key="sk-test-key-001")

    # 非流式调用
    result = client.chat("帮我查一下今天的天气")
    content = result["choices"][0]["message"]["content"]
    print(f"Agent回复: {content}")
    print(f"Token消耗: {result['usage']}")

    # 流式调用
    print("\n=== 流式输出 ===")
    for event in client.chat_stream("今天天气如何？"):
        if event["event"] == "token":
            print(event["data"]["content"], end="", flush=True)
        elif event["event"] == "tool_start":
            print(f"\n[🔧 调用工具: {event['data']['tool']}]")
        elif event["event"] == "tool_end":
            print(f"[📋 工具返回: {event['data']['output'][:100]}...]")
        elif event["event"] == "done":
            print(f"\n\n--- 完成，耗时 {event['data']['elapsed_ms']}ms ---")
```

**Image-Prompt(API testing and SSE streaming):** A flat-design minimalist 2D vector illustration showing API testing workflow. Left side: curl terminal commands for health check, non-streaming chat, and SSE streaming. Right side: SSE event timeline showing event types flowing: "tool_start" (gear icon) → "tool_end" (checkmark) → "token" (text fragments appearing one by one) → "done" (completion flag). A StreamingResponse arrow with "text/event-stream" content type. Tech light blue #409EFF for event stream arrows. White background with dark blue #1a1a2e labels. Academic API testing visualization.

---

## 7. 生产环境 Checklist

在将Agent API服务推向生产环境之前，请逐项确认以下事项：

| 类别 | 检查项 | 状态 |
|------|--------|------|
| **安全** | API Key存储使用Vault或加密数据库（非明文环境变量） |  |
| **安全** | Nginx配置TLS/SSL证书（Let's Encrypt自动续期） |  |
| **安全** | Celery代码执行使用Docker沙箱或RestrictedPython |  |
| **安全** | 定期轮换API Key |  |
| **可靠性** | 配置健康检查（Kubernetes liveness/readiness probe） |  |
| **可靠性** | 数据库/Redis配置主从或集群 |  |
| **可靠性** | 设置资源限制（CPU/Memory limit） |  |
| **监控** | Prometheus + Grafana + AlertManager告警规则 |  |
| **监控** | 日志采集到ELK/Loki并设置异常告警 |  |
| **监控** | Token消耗费用监控与预算告警 |  |
| **性能** | 使用Nginx进行负载均衡 |  |
| **性能** | Redis缓存常见查询结果 |  |
| **性能** | LLM调用设置合理超时与重试策略 |  |
| **运维** | 自动化CI/CD（GitHub Actions / GitLab CI） |  |
| **运维** | 数据库迁移方案（Alembic） |  |
| **运维** | 蓝绿部署或滚动更新策略 |  |

**Image-Prompt(production readiness checklist):** A flat-design minimalist 2D vector illustration of the production deployment checklist. Six checklist categories in a 2x3 grid: "安全" (shield with lock, TLS, API Key rotation icons), "可靠性" (health check heartbeat, master-slave database, resource limits gauges), "监控" (Prometheus + Grafana + AlertManager triangle), "性能" (Nginx load balancer, Redis cache, timeout settings), "运维" (CI/CD pipeline gear, database migration arrow, blue-green deployment). Each category with checkbox items in tech light blue #409EFF. White background with dark blue #1a1a2e labels. Academic operations checklist visualization.

---

## 8. 小结与实践建议

### 核心要点回顾

1. **FastAPI + Pydantic** 提供了类型安全、自动校验和API文档的坚实基础，是Agent服务化的首选框架。
2. **异步非阻塞** 是关键——Agent调用LLM是IO密集场景，使用 `async/await` + `StreamingResponse` 可大幅提升并发能力。
3. **Celery任务队列** 解决了长时间Agent任务的体验问题：API立即返回task_id，客户端轮询结果，避免HTTP超时。
4. **可观测性三板斧**：结构化日志（排查问题）→ Prometheus指标（发现异常）→ Grafana仪表盘（可视化决策）。
5. **SSE流式输出** 是实现"Agent边思考边展示"的标准方案，比WebSocket更轻量，浏览器原生支持EventSource。
6. **容器化** 保证了环境一致性，docker-compose 一键拉起完整技术栈。

### 进一步学习方向

- **LangServe**：LangChain官方API服务化工具，可简化本章部分工作
- **Kubernetes部署**：使用Helm Chart管理Agent API的K8s部署、HPA自动伸缩
- **LLM缓存**：使用GPTCache或Redis语义缓存减少重复LLM调用成本
- **Agent追踪**：集成LangSmith / LangFuse 实现Agent调用链路的全链路追踪
- **A/B测试**：支持多模型版本的流量分配与效果对比
- **API网关**：使用Kong或APISIX统一管理认证、限流、路由

### 动手实践

将本章代码补齐以下功能（建议作为练习）：
1. 实现基于Redis的会话上下文持久化（多轮对话记忆）
2. 添加请求ID追踪（从API入口到日志到响应Header全链路Trace ID）
3. 实现API Key的数据库存储与Web管理界面
4. 添加单元测试（pytest + httpx AsyncClient）和集成测试

**Image-Prompt(agent engineering learning roadmap):** A flat-design minimalist 2D vector illustration of the Agent engineering and deployment learning roadmap. Six key learning areas arranged as connected hexagons: "FastAPI + Pydantic" (type-safe API), "异步非阻塞" (async/await concurrency), "Celery任务队列" (distributed task processing), "可观测性三板斧" (Logs + Metrics + Traces triangle), "SSE流式输出" (streaming events), "容器化部署" (Docker + K8s). Further learning directions shown as upward arrows: "LangServe", "K8s HPA", "LLM缓存", "LangSmith追踪". Tech light blue #409EFF hexagon borders. White background with dark blue #1a1a2e labels. Academic learning roadmap visualization.
