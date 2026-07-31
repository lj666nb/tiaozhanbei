"""Trae-like guided coding workspace APIs."""

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from auth import get_current_user
from schemas import APIResponse
from services import lab_workspace_service


router = APIRouter()


class FileWriteRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    content: str = Field(default="", max_length=300_000)


class FileDeleteRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)


class DirectoryCreateRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)


class EntryMoveRequest(BaseModel):
    path: str = Field(min_length=1, max_length=500)
    destination: str = Field(min_length=1, max_length=500)


class TerminalRequest(BaseModel):
    command: str = Field(min_length=1, max_length=2_000)


class StageCheckRequest(BaseModel):
    stage_id: str = Field(min_length=1, max_length=40)


class AssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    active_file: str = Field(default="", max_length=500)
    mode: str = Field(default="agent", pattern="^(chat|agent)$")
    stage_id: str = Field(default="", max_length=40)


def _fail(exc: Exception):
    raise HTTPException(status_code=400, detail=str(exc))


@router.get("/progress/all", response_model=APIResponse)
async def get_progress_overview(current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=lab_workspace_service.get_progress_overview(current_user["id"]))
    except Exception as exc:
        _fail(exc)


@router.get("/{exercise_id}", response_model=APIResponse)
async def get_workspace(exercise_id: str, reset: bool = False, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=lab_workspace_service.get_workspace(current_user["id"], exercise_id, reset))
    except Exception as exc:
        _fail(exc)


@router.get("/{exercise_id}/entries", response_model=APIResponse)
async def list_entries(exercise_id: str, path: str = "", current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=lab_workspace_service.list_entries(current_user["id"], exercise_id, path))
    except Exception as exc:
        _fail(exc)


@router.get("/{exercise_id}/file", response_model=APIResponse)
async def read_file(exercise_id: str, path: str, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=lab_workspace_service.read_file(current_user["id"], exercise_id, path))
    except Exception as exc:
        _fail(exc)


@router.put("/{exercise_id}/file", response_model=APIResponse)
async def save_file(exercise_id: str, req: FileWriteRequest, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=lab_workspace_service.save_file(current_user["id"], exercise_id, req.path, req.content))
    except Exception as exc:
        _fail(exc)


@router.delete("/{exercise_id}/file", response_model=APIResponse)
async def delete_file(exercise_id: str, req: FileDeleteRequest, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=lab_workspace_service.delete_file(current_user["id"], exercise_id, req.path))
    except Exception as exc:
        _fail(exc)


@router.post("/{exercise_id}/entry/move", response_model=APIResponse)
async def move_entry(exercise_id: str, req: EntryMoveRequest, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=lab_workspace_service.move_entry(current_user["id"], exercise_id, req.path, req.destination))
    except Exception as exc:
        _fail(exc)


@router.post("/{exercise_id}/entry/duplicate", response_model=APIResponse)
async def duplicate_entry(exercise_id: str, req: EntryMoveRequest, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=lab_workspace_service.duplicate_entry(current_user["id"], exercise_id, req.path, req.destination))
    except Exception as exc:
        _fail(exc)


@router.delete("/{exercise_id}/entry", response_model=APIResponse)
async def delete_entry(exercise_id: str, req: FileDeleteRequest, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=lab_workspace_service.delete_entry(current_user["id"], exercise_id, req.path))
    except Exception as exc:
        _fail(exc)


@router.post("/{exercise_id}/directory", response_model=APIResponse)
async def create_directory(exercise_id: str, req: DirectoryCreateRequest, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=lab_workspace_service.create_directory(current_user["id"], exercise_id, req.path))
    except Exception as exc:
        _fail(exc)


@router.post("/{exercise_id}/terminal", response_model=APIResponse)
async def run_terminal(exercise_id: str, req: TerminalRequest, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=lab_workspace_service.run_terminal(current_user["id"], exercise_id, req.command))
    except Exception as exc:
        _fail(exc)


@router.post("/{exercise_id}/terminal/stream")
async def stream_terminal(exercise_id: str, req: TerminalRequest, current_user: dict = Depends(get_current_user)):
    def events():
        try:
            for event in lab_workspace_service.stream_terminal(current_user["id"], exercise_id, req.command):
                yield json.dumps(event, ensure_ascii=False) + "\n"
        except Exception as exc:
            yield json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False) + "\n"

    return StreamingResponse(
        events(), media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{exercise_id}/check", response_model=APIResponse)
async def check_stage(exercise_id: str, req: StageCheckRequest, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=lab_workspace_service.check_stage(current_user["id"], exercise_id, req.stage_id))
    except Exception as exc:
        _fail(exc)


@router.post("/{exercise_id}/assistant", response_model=APIResponse)
async def ask_assistant(exercise_id: str, req: AssistantRequest, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=await lab_workspace_service.ask_assistant(
            current_user["id"], exercise_id, req.question, req.active_file, req.mode, req.stage_id
        ))
    except Exception as exc:
        _fail(exc)


@router.post("/{exercise_id}/assistant/stream")
async def ask_assistant_stream(exercise_id: str, req: AssistantRequest, current_user: dict = Depends(get_current_user)):
    """Stream the lab assistant response with Function Calling tool support (SSE)."""
    return StreamingResponse(
        lab_workspace_service.ask_assistant_streaming(
            current_user["id"], exercise_id, req.question,
            req.active_file, req.mode, req.stage_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/{exercise_id}/assistant/history", response_model=APIResponse)
async def reset_assistant(exercise_id: str, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=lab_workspace_service.reset_assistant(current_user["id"], exercise_id))
    except Exception as exc:
        _fail(exc)
