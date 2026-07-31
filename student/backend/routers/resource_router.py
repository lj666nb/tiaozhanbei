"""资源推送路由"""
import os, json
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from auth import get_current_user
from schemas import APIResponse
from services import resource_service
from database import get_db
from pydantic import BaseModel
import httpx
import uuid

router = APIRouter()

PDF_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "pdfs")
COVER_DIR = os.path.join(PDF_DIR, "covers")
os.makedirs(PDF_DIR, exist_ok=True)
os.makedirs(COVER_DIR, exist_ok=True)

@router.get("/recommend", response_model=APIResponse)
async def get_recommendations(current_user: dict = Depends(get_current_user)):
    """获取个性化推荐资源"""
    resources = resource_service.recommend_resources(current_user["id"])
    return APIResponse(data=resources)

@router.get("/list", response_model=APIResponse)
async def list_resources(category: str = None, difficulty: str = None, page: int = 1, page_size: int = 12):
    """获取资源列表"""
    result = resource_service.get_resources_by_category(category, difficulty, page, page_size)
    return APIResponse(data=result)

@router.post("/collect/{resource_id}", response_model=APIResponse)
async def collect_resource(resource_id: str, current_user: dict = Depends(get_current_user)):
    """收藏/取消收藏资源"""
    result = resource_service.toggle_collect_resource(current_user["id"], resource_id)
    return APIResponse(data=result)

@router.get("/collected", response_model=APIResponse)
async def get_collected(current_user: dict = Depends(get_current_user)):
    """获取收藏资源"""
    resources = resource_service.get_collected_resources(current_user["id"])
    return APIResponse(data=resources)


@router.get("/material", response_model=APIResponse)
async def get_knowledge_material(knowledge: str = "", current_user: dict = Depends(get_current_user)):
    """根据知识点联网搜索+AI整理学习资料（Markdown格式）

    工作流程：
    1. 用Bing搜索知识点相关内容
    2. 抓取搜索结果网页的正文
    3. 由AI整合、组织、去重，生成结构化Markdown学习资料
    """
    try:
        result = await resource_service.search_and_curate_material(
            user_id=current_user["id"],
            knowledge=knowledge
        )
        return APIResponse(data=result)
    except Exception as e:
        return APIResponse(code=500, message=f"获取学习资料失败: {str(e)}", data=None)


@router.get("/learn/{resource_id}", response_model=APIResponse)
async def learn_resource(resource_id: str, current_user: dict = Depends(get_current_user)):
    """点击资源卡片获取学习资料（优先本地，兜底AI联网整理）

    策略：
    1. 用资源ID查找资源，获取其tags
    2. 用tags匹配本地 learning_materials
    3. 本地无匹配时，联网搜索+AI整理
    """
    try:
        result = await resource_service.get_resource_material_async(
            resource_id=resource_id,
            user_id=current_user["id"]
        )
        return APIResponse(data=result)
    except Exception as e:
        return APIResponse(code=500, message=f"获取学习资料失败: {str(e)}", data=None)


@router.get("/proxy-image")
async def proxy_image(url: str = ""):
    """代理获取外部图片，解决浏览器跨域/混合内容拦截问题"""
    if not url:
        raise HTTPException(status_code=400, detail="url parameter required")
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "image/png")
                return StreamingResponse(
                    content=iter([resp.content]),
                    media_type=content_type,
                    headers={"Cache-Control": "public, max-age=86400"}
                )
            raise HTTPException(status_code=resp.status_code, detail="Image fetch failed")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ===== PDF 电子书管理 =====

@router.post("/pdf/upload", response_model=APIResponse)
async def upload_pdf(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """上传PDF电子书"""
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="仅支持PDF文件")
    content = await file.read()
    if len(content) > 200 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件大小不能超过200MB")
    filename = f"{uuid.uuid4().hex}.pdf"
    filepath = os.path.join(PDF_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(content)

    # 生成封面（PDF第一页 → PNG）
    cover_filename = None
    try:
        import fitz
        doc = fitz.open(filepath)
        if doc.page_count > 0:
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            cover_filename = filename.replace('.pdf', '.png')
            pix.save(os.path.join(COVER_DIR, cover_filename))
        doc.close()
    except Exception:
        pass  # 封面生成失败不影响上传

    conn = get_db()
    cur = conn.execute(
        "INSERT INTO pdf_books (user_id, filename, original_name, file_size, cover) VALUES (?, ?, ?, ?, ?)",
        (current_user["id"], filename, file.filename, len(content), cover_filename)
    )
    book_id = cur.lastrowid
    conn.commit()
    conn.close()
    return APIResponse(data={"id": book_id, "original_name": file.filename, "file_size": len(content), "cover": cover_filename})


@router.get("/pdf/list", response_model=APIResponse)
async def list_pdfs(current_user: dict = Depends(get_current_user)):
    """获取已上传的PDF列表"""
    conn = get_db()
    rows = conn.execute(
        "SELECT id, original_name, file_size, cover, created_at FROM pdf_books WHERE user_id = ? ORDER BY created_at DESC",
        (current_user["id"],)
    ).fetchall()
    conn.close()
    items = [{"id": r["id"], "name": r["original_name"], "size": r["file_size"], "cover": r["cover"], "created_at": r["created_at"]} for r in rows]
    return APIResponse(data=items)


@router.get("/pdf/cover/{book_id}")
async def get_pdf_cover(book_id: int):
    """获取PDF封面图片"""
    conn = get_db()
    row = conn.execute("SELECT cover FROM pdf_books WHERE id = ?", (book_id,)).fetchone()
    conn.close()
    if not row or not row["cover"]:
        raise HTTPException(status_code=404, detail="无封面")
    filepath = os.path.join(COVER_DIR, row["cover"])
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="封面文件丢失")
    return FileResponse(filepath, media_type="image/png")


@router.get("/pdf/{book_id}")
async def get_pdf(book_id: int, token: str = None, download: int = 0):
    """在线阅读PDF / 下载PDF（支持 ?token=xxx 用于浏览器新标签页）"""
    from jose import jwt as jose_jwt
    from config import SECRET_KEY, ALGORITHM
    user_id = None
    if token:
        try:
            payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = payload.get("user_id")
        except Exception:
            pass
    if user_id is None:
        raise HTTPException(status_code=401, detail="无法验证凭据")
    conn = get_db()
    row = conn.execute("SELECT filename, original_name FROM pdf_books WHERE id = ? AND user_id = ?", (book_id, user_id)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="PDF不存在")
    filepath = os.path.join(PDF_DIR, row["filename"])
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="PDF文件丢失")
    from urllib.parse import quote
    safe_name = quote(row["original_name"], safe='')
    disposition = "attachment" if download else "inline"
    return FileResponse(filepath, media_type="application/pdf",
                        headers={"Content-Disposition": f"{disposition}; filename*=UTF-8''{safe_name}"})


@router.delete("/pdf/{book_id}", response_model=APIResponse)
async def delete_pdf(book_id: int, current_user: dict = Depends(get_current_user)):
    """删除PDF电子书"""
    conn = get_db()
    row = conn.execute("SELECT filename, cover FROM pdf_books WHERE id = ? AND user_id = ?", (book_id, current_user["id"])).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="PDF不存在")
    filepath = os.path.join(PDF_DIR, row["filename"])
    if os.path.exists(filepath):
        os.remove(filepath)
    if row["cover"]:
        cover_path = os.path.join(COVER_DIR, row["cover"])
        if os.path.exists(cover_path):
            os.remove(cover_path)
    conn.execute("DELETE FROM pdf_books WHERE id = ?", (book_id,))
    conn.commit()
    conn.close()
    return APIResponse(data={"message": "已删除"})


class BatchDeletePdfRequest(BaseModel):
    ids: list[int]


@router.post("/pdf/batch-delete", response_model=APIResponse)
async def batch_delete_pdfs(req: BatchDeletePdfRequest, current_user: dict = Depends(get_current_user)):
    """批量删除PDF电子书"""
    conn = get_db()
    deleted = 0
    for bid in req.ids:
        row = conn.execute("SELECT filename, cover FROM pdf_books WHERE id = ? AND user_id = ?", (bid, current_user["id"])).fetchone()
        if row:
            filepath = os.path.join(PDF_DIR, row["filename"])
            if os.path.exists(filepath):
                os.remove(filepath)
            if row["cover"]:
                cover_path = os.path.join(COVER_DIR, row["cover"])
                if os.path.exists(cover_path):
                    os.remove(cover_path)
            conn.execute("DELETE FROM pdf_books WHERE id = ?", (bid,))
            deleted += 1
    conn.commit()
    conn.close()
    return APIResponse(data={"deleted": deleted})


# ===== 编程习题 =====

import re as _re
import glob as _glob

EXERCISES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "exercises")
EXERCISES_PROCESSED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "exercises_processed.json")
FLAGSHIP_EXERCISES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "flagship_exercises.json")


def _load_flagship_exercises():
    try:
        with open(FLAGSHIP_EXERCISES, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _parse_exercise(text):
    lines = text.strip().split("\n")
    info = {"id": "", "module": "", "title": "", "description": "", "input_output": "", "starter_code": "", "eval_code": ""}
    section = None
    buf = []
    for line in lines:
        if line.startswith("关卡 ") and "：" in line:
            info["id"] = line.split("：")[0].replace("关卡 ", "").strip()
            info["title"] = line.split("：", 1)[1].strip() if "：" in line else ""
        elif line.startswith("所属模块："):
            info["module"] = line.replace("所属模块：", "").strip()
        elif line.startswith("【任务描述】"):
            if section == "desc": info["description"] = "\n".join(buf).strip()
            buf = []; section = "desc"
        elif line.startswith("【输入输出说明】"):
            if section == "desc": info["description"] = "\n".join(buf).strip()
            buf = []; section = "io"
        elif line.startswith("【初始代码】"):
            if section == "io": info["input_output"] = "\n".join(buf).strip()
            buf = []; section = "starter"
        elif line.startswith("【评测代码】"):
            if section == "starter":
                raw = "\n".join(buf)
                m = _re.search(r'```python\s*\n(.*?)```', raw, _re.DOTALL)
                info["starter_code"] = m.group(1).strip() if m else raw.strip()
            buf = []; section = "eval"
        elif line.startswith("---") or line.startswith("==="):
            continue
        else:
            buf.append(line)
    if section == "eval":
        raw = "\n".join(buf)
        m = _re.search(r'```python\s*\n(.*?)```', raw, _re.DOTALL)
        info["eval_code"] = m.group(1).strip() if m else raw.strip()
    return info if info["id"] else None


def _load_all_exercises():
    # 优先使用预处理后的习题（含骨架代码 + 测试代码 + 标记）
    if os.path.exists(EXERCISES_PROCESSED):
        try:
            with open(EXERCISES_PROCESSED, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    # 降级: 从原始 .txt 文件加载
    exercises = []
    files = sorted(_glob.glob(os.path.join(EXERCISES_DIR, "module_*.txt")))
    for fpath in files:
        content = open(fpath, "r", encoding="utf-8").read()
        parts = _re.split(r'\n(?=关卡 \d+-\d+：)', content)
        for part in parts:
            ex = _parse_exercise(part.strip())
            if ex and ex["id"]:
                exercises.append(ex)
    return exercises


@router.get("/exercises", response_model=APIResponse)
async def list_exercises(module: str = None):
    # 主入口只发布经过私有业务场景验证的旗舰题。旧题仍可按 ID 访问，
    # 但不再用数量制造“课程很深”的错觉。
    all_ex = _load_flagship_exercises()
    if module:
        all_ex = [e for e in all_ex if module in e.get("module", "")]
    items = [{"id": e["id"], "module": e["module"], "title": e["title"],
              "description": e["description"][:150], "input_output": e["input_output"]} for e in all_ex]
    return APIResponse(data=items)


@router.get("/exercises/{exercise_id}", response_model=APIResponse)
async def get_exercise(exercise_id: str):
    all_ex = _load_flagship_exercises() + _load_all_exercises()
    for e in all_ex:
        if e["id"] == exercise_id:
            return APIResponse(data=e)
    raise HTTPException(status_code=404, detail="习题不存在")
