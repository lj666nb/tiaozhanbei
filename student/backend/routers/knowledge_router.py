"""知识点管理路由"""
import json
from fastapi import APIRouter
from schemas import APIResponse
from config import KNOWLEDGE_TAGS_PATH

router = APIRouter()

@router.get("/tags", response_model=APIResponse)
async def get_knowledge_tags():
    """获取所有知识点标签"""
    try:
        with open(KNOWLEDGE_TAGS_PATH, 'r', encoding='utf-8') as f:
            tags = json.load(f)
        return APIResponse(data=tags)
    except Exception as e:
        return APIResponse(code=500, message=f"读取失败: {str(e)}")

@router.get("/categories", response_model=APIResponse)
async def get_categories():
    """获取测评维度列表（对应6个分模块题库）"""
    categories = [
        {"name": "智能体基础通识", "tag_count": 80, "module_id": "01"},
        {"name": "大模型与提示词工程", "tag_count": 80, "module_id": "02"},
        {"name": "智能体四大核心能力模块", "tag_count": 80, "module_id": "03"},
        {"name": "开发框架与工程实践", "tag_count": 80, "module_id": "04"},
        {"name": "多智能体系统", "tag_count": 80, "module_id": "05"},
        {"name": "评估安全与前沿拓展", "tag_count": 80, "module_id": "06"},
    ]
    return APIResponse(data=categories)
