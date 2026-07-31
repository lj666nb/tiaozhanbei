"""学情复盘路由"""
from fastapi import APIRouter, Depends
from auth import get_current_user
from schemas import APIResponse
from services import analytics_service

router = APIRouter()

@router.get("/stats", response_model=APIResponse)
async def get_stats(current_user: dict = Depends(get_current_user)):
    """获取学习统计概览"""
    stats = analytics_service.get_user_stats(current_user["id"])
    return APIResponse(data=stats)

@router.get("/report/weekly", response_model=APIResponse)
async def get_weekly_report(current_user: dict = Depends(get_current_user)):
    """获取周报告"""
    report = analytics_service.get_weekly_report(current_user["id"])
    return APIResponse(data=report)

@router.get("/report/monthly", response_model=APIResponse)
async def get_monthly_report(current_user: dict = Depends(get_current_user)):
    """获取月报告"""
    report = analytics_service.get_monthly_report(current_user["id"])
    return APIResponse(data=report)

@router.get("/growth", response_model=APIResponse)
async def get_growth(current_user: dict = Depends(get_current_user)):
    """获取能力成长轨迹"""
    data = analytics_service.get_growth_data(current_user["id"])
    return APIResponse(data=data)

@router.get("/activity", response_model=APIResponse)
async def get_recent_activity(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """获取用户最近学习动态（跨设备一致）

    合并测评、答疑、错题复习三类活动，按时间倒序返回。
    """
    activities = analytics_service.get_recent_activity(current_user["id"], limit)
    return APIResponse(data=activities)


@router.post("/submit-result", response_model=APIResponse)
async def submit_quiz_result(
    knowledge_tag: str = "",
    result: str = "",
    current_user: dict = Depends(get_current_user)
):
    """提交测评结果并记录活动（跨设备同步）"""
    import json as _json
    result_data = {}
    if result:
        try:
            result_data = _json.loads(result)
        except Exception:
            result_data = {"raw": result}
    analytics_service.record_learning_activity(
        current_user["id"], knowledge_tag or "综合练习", "quiz", 0, result_data
    )
    return APIResponse(message="记录成功")


@router.post("/record", response_model=APIResponse)
async def record_activity(
    knowledge_tag: str = "",
    action_type: str = "",
    duration: int = 0,
    current_user: dict = Depends(get_current_user)
):
    """记录学习活动"""
    analytics_service.record_learning_activity(current_user["id"], knowledge_tag, action_type, duration)
    return APIResponse(message="记录成功")
