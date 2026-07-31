"""编程能力验证闭环 API。"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from schemas import APIResponse
from services import capability_service


router = APIRouter()


class SessionStartRequest(BaseModel):
    exercise_id: str = Field(min_length=1, max_length=40)
    force_new: bool = False


class EventBatchRequest(BaseModel):
    events: list[dict] = []


class CodePassedRequest(BaseModel):
    code: str = Field(min_length=1, max_length=200_000)


class DefenseRequest(BaseModel):
    answers: list[dict]
    ai_usage: str = "未使用"


class RepairRequest(BaseModel):
    code: str = Field(min_length=1, max_length=200_000)
    explanation: str = Field(min_length=1, max_length=3000)


class ProjectStateRequest(BaseModel):
    state: str = Field(min_length=1, max_length=20)


def _bad_request(exc: Exception):
    raise HTTPException(status_code=400, detail=str(exc))


@router.post("/sessions", response_model=APIResponse)
async def start_session(req: SessionStartRequest, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=capability_service.start_session(
            current_user["id"], req.exercise_id, req.force_new
        ))
    except Exception as exc:
        _bad_request(exc)


@router.get("/sessions/{session_id}", response_model=APIResponse)
async def get_session(
    session_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = capability_service.get_session(current_user["id"], session_id)
        if capability_service.defense_grading_pending(data):
            background_tasks.add_task(
                capability_service.grade_defense_answers,
                current_user["id"],
                session_id,
            )
        return APIResponse(data=data)
    except Exception as exc:
        _bad_request(exc)


@router.post("/sessions/{session_id}/events", response_model=APIResponse)
async def record_events(session_id: int, req: EventBatchRequest, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=capability_service.record_events(current_user["id"], session_id, req.events))
    except Exception as exc:
        _bad_request(exc)


@router.post("/sessions/{session_id}/code-passed", response_model=APIResponse)
async def mark_code_passed(session_id: int, req: CodePassedRequest, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=capability_service.mark_code_passed(current_user["id"], session_id, req.code))
    except Exception as exc:
        _bad_request(exc)


@router.post("/sessions/{session_id}/defense", response_model=APIResponse)
async def submit_defense(
    session_id: int,
    req: DefenseRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    try:
        data = await capability_service.submit_defense(
            current_user["id"], session_id, req.answers, req.ai_usage
        )
        background_tasks.add_task(
            capability_service.grade_defense_answers,
            current_user["id"],
            session_id,
        )
        return APIResponse(data=data)
    except Exception as exc:
        _bad_request(exc)


@router.post("/sessions/{session_id}/repair", response_model=APIResponse)
async def submit_repair(session_id: int, req: RepairRequest, current_user: dict = Depends(get_current_user)):
    try:
        return APIResponse(data=capability_service.submit_repair(
            current_user["id"], session_id, req.code, req.explanation
        ))
    except Exception as exc:
        _bad_request(exc)


@router.post("/sessions/{session_id}/repair/retry", response_model=APIResponse)
async def retry_repair(session_id: int, current_user: dict = Depends(get_current_user)):
    """保留上次评分，并重新注入故障开始下一次修复。"""
    try:
        return APIResponse(data=capability_service.retry_repair(
            current_user["id"], session_id
        ))
    except Exception as exc:
        _bad_request(exc)


@router.post("/sessions/{session_id}/project-state", response_model=APIResponse)
async def switch_project_state(
    session_id: int,
    req: ProjectStateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Refresh the visible workspace to a selected learning-stage snapshot."""
    try:
        return APIResponse(data=capability_service.switch_project_state(
            current_user["id"], session_id, req.state
        ))
    except Exception as exc:
        _bad_request(exc)


@router.post("/sessions/{session_id}/skip", response_model=APIResponse)
async def skip_capability(session_id: int, current_user: dict = Depends(get_current_user)):
    """跳过能力验证，仅以测试分数完成关卡。"""
    try:
        return APIResponse(data=capability_service.skip_capability(
            current_user["id"], session_id
        ))
    except Exception as exc:
        _bad_request(exc)


@router.get("/sessions/{session_id}/review", response_model=APIResponse)
async def review_session(
    session_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """获取能力验证回顾数据，包含用户回答与标准答案对比。"""
    try:
        data = await capability_service.get_session_review(
            current_user["id"], session_id
        )
        session = capability_service.get_session(current_user["id"], session_id)
        if capability_service.defense_grading_pending(session):
            background_tasks.add_task(
                capability_service.grade_defense_answers,
                current_user["id"],
                session_id,
            )
        return APIResponse(data=data)
    except Exception as exc:
        _bad_request(exc)


@router.get("/history", response_model=APIResponse)
async def get_history(current_user: dict = Depends(get_current_user)):
    """获取用户所有已完成实验的详细历史记录。"""
    try:
        return APIResponse(data=capability_service.get_completed_sessions(current_user["id"]))
    except Exception as exc:
        _bad_request(exc)


class VariantCodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=200_000)


@router.post("/sessions/{session_id}/variant/generate", response_model=APIResponse)
async def generate_variant(session_id: int, current_user: dict = Depends(get_current_user)):
    """为已完成修复的实验生成变式迁移场景。"""
    try:
        return APIResponse(data=capability_service.generate_variant(current_user["id"], session_id))
    except Exception as exc:
        _bad_request(exc)


@router.post("/sessions/{session_id}/variant/submit", response_model=APIResponse)
async def submit_variant(session_id: int, req: VariantCodeRequest, current_user: dict = Depends(get_current_user)):
    """提交变式迁移代码并判题。"""
    try:
        return APIResponse(data=capability_service.submit_variant(current_user["id"], session_id, req.code))
    except Exception as exc:
        _bad_request(exc)


@router.get("/scores", response_model=APIResponse)
async def get_scores(current_user: dict = Depends(get_current_user)):
    """获取所有已完成的实验关卡分数。"""
    try:
        return APIResponse(data=capability_service.get_exercise_scores(current_user["id"]))
    except Exception as exc:
        _bad_request(exc)

