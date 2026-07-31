"""应用配置"""
import os
import secrets
import warnings

# 基础路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "data", "learning_platform.db")
KNOWLEDGE_TAGS_PATH = os.path.join(BASE_DIR, "data", "knowledge_tags.json")
RESOURCES_PATH = os.path.join(BASE_DIR, "data", "resources.json")


def _load_or_create_jwt_secret(secret_file: str) -> str:
    """创建并持久复用本机 JWT 密钥，避免服务重启导致所有登录令牌失效。"""
    secret_path = os.path.abspath(secret_file)
    os.makedirs(os.path.dirname(secret_path), exist_ok=True)

    try:
        with open(secret_path, "r", encoding="utf-8") as file:
            persisted = file.read().strip()
        if len(persisted) >= 32:
            return persisted
    except FileNotFoundError:
        pass

    generated = secrets.token_urlsafe(48)
    try:
        # O_EXCL 让多个服务进程首次启动时只有一个进程负责创建。
        descriptor = os.open(
            secret_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(generated)
        return generated
    except FileExistsError:
        # 另一个进程已创建完成，统一读取同一份密钥。
        with open(secret_path, "r", encoding="utf-8") as file:
            persisted = file.read().strip()
        if len(persisted) >= 32:
            return persisted
        raise RuntimeError("JWT 密钥文件内容无效，请删除后重启服务以重新生成")


# JWT配置
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()
if not SECRET_KEY:
    _jwt_secret_file = os.getenv(
        "JWT_SECRET_FILE",
        os.path.join(BASE_DIR, "data", ".jwt-secret"),
    ).strip()
    SECRET_KEY = _load_or_create_jwt_secret(_jwt_secret_file)
    warnings.warn(
        "JWT_SECRET_KEY 未配置，正在使用数据目录中的持久化本机密钥；"
        "生产环境仍建议通过环境变量配置独立的随机密钥。",
        RuntimeWarning,
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天

# 数据库配置
# 题库目录（backend/data/dataset/ 下）
DATASET_DIR = os.path.join(BASE_DIR, "data", "dataset")

# RAG 知识库配置
CHROMA_DB_PATH = os.path.join(BASE_DIR, "data", "chroma_db")
RAG_TOP_K = 6
RAG_DEFAULT_EMBEDDING_PROVIDER = "siliconflow"  # Docker/云端查询；本地建库显式使用 bge
# ⚠️ 此处不写入任何 API Key。用户必须在个人中心配置自己的嵌入 API Key 后才能使用 RAG。
# 规则：未配置 → 不可用；绝不使用硬编码的默认 Key（会扣别人的钱）。

# 出题配置
MAX_QUESTIONS_PER_QUIZ = 20
QUESTION_TYPES = ["单选", "多选", "判断", "简答", "填空", "代码实操"]
DIFFICULTY_LEVELS = ["Lv1入门", "Lv2中等", "Lv3高阶"]
LEARNING_STAGES = ["入门", "进阶", "高阶"]

# 知识点权重配置
WEAK_POINT_WEIGHT = 0.6   # 薄弱知识点出题权重
MASTERED_WEIGHT = 0.2     # 已掌握知识点出题权重
NORMAL_WEIGHT = 0.2       # 一般知识点出题权重
