"""AI 图片生成路由"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from auth import get_current_user
from schemas import APIResponse
from services import image_service
import os

router = APIRouter()
IMAGES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "generated_images")


@router.post("/generate", response_model=APIResponse)
async def generate_image(prompt: str = "", current_user: dict = Depends(get_current_user)):
    """使用 LLM 生成 AI 配图 SVG"""
    if not prompt or len(prompt.strip()) < 10:
        return APIResponse(code=400, message="提示词不能为空或过短", data=None)
    result = await image_service.generate_image(current_user["id"], prompt)
    if result.get("success"):
        return APIResponse(data={
            "svg": result["svg"],
            "cached": result.get("cached", False)
        })
    return APIResponse(code=500, message=result.get("error", "生成失败"), data=None)


@router.get("/list", response_model=APIResponse)
async def list_images(current_user: dict = Depends(get_current_user)):
    images = image_service.get_cached_images(current_user["id"])
    return APIResponse(data=images)


@router.get("/{filename}")
async def serve_image(filename: str):
    file_path = os.path.join(IMAGES_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image not found")
    media = "image/svg+xml" if filename.endswith(".svg") else "image/png"
    return FileResponse(file_path, media_type=media)
