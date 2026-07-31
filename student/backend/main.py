"""FastAPI应用入口"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database import init_db
import os, json

class SafeJSONResponse(JSONResponse):
    """自定义JSON响应：使用 ensure_ascii=True 避免Windows下的surrogate编码问题"""
    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=True,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")

# 创建应用
app = FastAPI(
    title="AI智能体学科学习平台",
    description="个性化、伴随式、智能化的AI智能体学科学习平台API",
    version="1.0.0",
    default_response_class=SafeJSONResponse
)

# CORS中间件
# 部署时设置环境变量 CORS_ORIGIN=你的域名 可限制跨域来源
# 未设置时只允许本地 Vite 开发地址；同源生产部署不需要额外跨域来源。
# 注意：JWT token 通过 Authorization header 传递（非 cookie），无需 allow_credentials=True
_cors_origin = os.getenv("CORS_ORIGIN", "")
_allow_origins = (
    [o.strip() for o in _cors_origin.split(",") if o.strip()]
    if _cors_origin
    else ["http://localhost:5173", "http://127.0.0.1:5173"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化数据库
init_db()

# 启动时检查数据文件完整性
print("[启动检查] 验证数据文件...")
_data_ok = True
_checks = [
    ("题库: module_01", os.path.join(os.path.dirname(__file__), "data", "dataset", "module_01_智能体基础通识.json")),
    ("题库: module_02", os.path.join(os.path.dirname(__file__), "data", "dataset", "module_02_大模型与提示词工程.json")),
    ("题库: module_03", os.path.join(os.path.dirname(__file__), "data", "dataset", "module_03_智能体四大核心能力模块.json")),
    ("题库: module_04", os.path.join(os.path.dirname(__file__), "data", "dataset", "module_04_开发框架与工程实践.json")),
    ("题库: module_05", os.path.join(os.path.dirname(__file__), "data", "dataset", "module_05_多智能体系统.json")),
    ("题库: module_06", os.path.join(os.path.dirname(__file__), "data", "dataset", "module_06_评估安全与前沿拓展.json")),
    ("习题数据", os.path.join(os.path.dirname(__file__), "data", "exercises_processed.json")),
    ("资源索引", os.path.join(os.path.dirname(__file__), "data", "resources.json")),
    ("知识标签", os.path.join(os.path.dirname(__file__), "data", "knowledge_tags.json")),
    ("数据库", os.path.join(os.path.dirname(__file__), "data", "learning_platform.db")),
]
for name, path in _checks:
    if os.path.exists(path):
        print(f"  [OK] {name}")
    else:
        print(f"  [缺失] {name} — 请确认文件已上传到服务器: {path}")
        _data_ok = False
if _data_ok:
    print("[启动检查] 全部数据文件就绪")
else:
    print("[启动检查] 警告: 部分数据文件缺失，相关功能将无法使用")

# 注册路由
from routers import auth_router, diagnosis_router, qa_router, learning_router, analytics_router, resource_router, knowledge_router, llm_config_router, image_router, rag_router, capability_router, workspace_router

app.include_router(auth_router.router, prefix="/api/auth", tags=["认证"])
app.include_router(diagnosis_router.router, prefix="/api/diagnosis", tags=["学情诊断"])
app.include_router(qa_router.router, prefix="/api/qa", tags=["智能答疑"])
app.include_router(learning_router.router, prefix="/api/learning", tags=["伴随学习"])
app.include_router(analytics_router.router, prefix="/api/analytics", tags=["学情复盘"])
app.include_router(resource_router.router, prefix="/api/resources", tags=["资源推送"])
app.include_router(knowledge_router.router, prefix="/api/knowledge", tags=["知识点"])
app.include_router(llm_config_router.router, prefix="/api/llm-config", tags=["LLM配置"])
app.include_router(image_router.router, prefix="/api/images", tags=["图片生成"])
app.include_router(rag_router.router, prefix="/api/rag", tags=["RAG知识库"])
app.include_router(capability_router.router, prefix="/api/capability", tags=["能力真实性验证"])
app.include_router(workspace_router.router, prefix="/api/workspaces", tags=["项目编程实验室"])


@app.get("/")
def root():
    return {"message": "AI智能体学科学习平台 API", "version": "1.0.0", "status": "running"}

@app.get("/api/health")
def health_check():
    return {"status": "healthy"}

@app.get("/api/debug/routes")
def debug_routes():
    """调试：列出所有已注册路由"""
    routes = []
    for r in app.router.routes:
        if hasattr(r, 'methods') and hasattr(r, 'path'):
            routes.append(f"{list(r.methods)} {r.path}")
        elif hasattr(r, 'path'):
            routes.append(f"[include] {r.path}")
    return {"routes": routes}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
