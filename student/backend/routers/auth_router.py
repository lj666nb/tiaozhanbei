"""认证路由"""
from fastapi import APIRouter, Depends, HTTPException
from database import get_db
from auth import hash_password, verify_password, create_access_token, get_current_user
from schemas import UserRegister, UserLogin, UserUpdate, UserResponse, TokenResponse, APIResponse

router = APIRouter()

def _user_payload(user) -> dict:
    return {
        "id": user["id"], "username": user["username"], "nickname": user["nickname"],
        "grade": user["grade"], "learning_stage": user["learning_stage"],
        "learning_goal": user["learning_goal"], "avatar": user["avatar"],
        "programming_background": user["programming_background"] or "",
        "years_experience": int(user["years_experience"] or 0),
        "answer_preference": user["answer_preference"] or "分步清晰",
    }

@router.post("/register", response_model=APIResponse)
def register(req: UserRegister):
    conn = get_db()
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (req.username,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=400, detail="用户名已存在")

    password_hash = hash_password(req.password)
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash, nickname, grade, learning_stage, learning_goal, programming_background, years_experience, answer_preference) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (req.username, password_hash, req.nickname or req.username, req.grade, req.learning_stage, req.learning_goal,
         req.programming_background, req.years_experience, req.answer_preference)
    )
    user_id = cursor.lastrowid
    conn.commit()

    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    token = create_access_token({"user_id": user_id})
    return APIResponse(data={
        "access_token": token,
        "token_type": "bearer",
        "user": _user_payload(user)
    })

@router.post("/login", response_model=APIResponse)
def login(req: UserLogin):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (req.username,)).fetchone()
    conn.close()

    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token({"user_id": user["id"]})
    return APIResponse(data={
        "access_token": token,
        "token_type": "bearer",
        "user": _user_payload(user)
    })

@router.get("/me", response_model=APIResponse)
def get_profile(current_user: dict = Depends(get_current_user)):
    return APIResponse(data=_user_payload(current_user))

@router.get("/verify", response_model=APIResponse)
def verify_token(current_user: dict = Depends(get_current_user)):
    """校验 token 是否有效（前端路由守卫使用）"""
    return APIResponse(data={"valid": True, "user_id": current_user["id"], "username": current_user["username"]})


@router.put("/me", response_model=APIResponse)
def update_profile(req: UserUpdate, current_user: dict = Depends(get_current_user)):
    conn = get_db()
    updates = {}
    if req.nickname is not None:
        updates["nickname"] = req.nickname
    if req.grade is not None:
        updates["grade"] = req.grade
    if req.learning_stage is not None:
        updates["learning_stage"] = req.learning_stage
    if req.learning_goal is not None:
        updates["learning_goal"] = req.learning_goal
    if req.programming_background is not None:
        updates["programming_background"] = req.programming_background
    if req.years_experience is not None:
        updates["years_experience"] = req.years_experience
    if req.answer_preference is not None:
        updates["answer_preference"] = req.answer_preference

    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [current_user["id"]]
        conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
        conn.commit()

    conn.close()
    return APIResponse(message="更新成功")
