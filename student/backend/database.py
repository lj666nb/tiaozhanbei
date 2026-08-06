"""数据库初始化与连接管理"""
import os
from config import DATABASE_PATH

# 统一数据库连接（支持 SQLite / PostgreSQL 切换）
from db import get_db, is_postgresql, json_load

# 保留本地 get_db 引用，所有现有 import 不受影响
# from database import get_db → 实际调用 db.get_db()
__all__ = ["get_db", "init_db", "is_postgresql", "json_load"]

def _run_migration(conn, table, column_sql, label):
    """安全执行数据库迁移（列已存在则跳过）"""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_sql}")
        conn.commit()
        print(f"[OK] {label}")
    except Exception:
        pass  # 列已存在，忽略

def init_db():
    """初始化数据库，创建所有表

    - SQLite 模式: 创建表 + 迁移 + 种子数据
    - PostgreSQL 模式: 表已通过 merged_schema.sql 创建，仅做连接验证 + 种子数据
    """
    # 测试和本地工具会临时替换 database.DATABASE_PATH；同步到底层连接模块，
    # 避免仍然打开生产 SQLite 文件。
    if not is_postgresql():
        import db as _db_module
        _db_module.DATABASE_PATH = DATABASE_PATH
    os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
    conn = get_db()

    if is_postgresql():
        print("[DB] 使用 PostgreSQL: " + os.getenv("DATABASE_URL", "")[:50] + "...")
        _seed_pg_data(conn)
        conn.commit()
        conn.close()
        print("[OK] PostgreSQL database connection verified")
        return

    # 使用 connection.executescript 而非 cursor.executescript，
    # 避免 cursor 状态异常导致后续 migration 静默失败
    conn.executescript("""
        -- 用户表
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nickname TEXT DEFAULT '',
            grade TEXT DEFAULT '',
            learning_stage TEXT DEFAULT '入门',
            learning_goal TEXT DEFAULT '',
            avatar TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 知识点标签表
        CREATE TABLE IF NOT EXISTS knowledge_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT DEFAULT '',
            parent_id INTEGER DEFAULT 0
        );

        -- 测评会话表
        CREATE TABLE IF NOT EXISTS quiz_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            stage TEXT DEFAULT '入门',
            questions_json TEXT DEFAULT '[]',
            answers_json TEXT DEFAULT '[]',
            score REAL DEFAULT 0,
            total INTEGER DEFAULT 0,
            report_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- 错题本
        CREATE TABLE IF NOT EXISTS error_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            session_id INTEGER,
            question_data TEXT NOT NULL,
            user_answer TEXT DEFAULT '',
            correct_answer TEXT DEFAULT '',
            error_type TEXT DEFAULT '',
            knowledge_tag TEXT DEFAULT '',
            reviewed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- 问答历史
        CREATE TABLE IF NOT EXISTS qa_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            question_type TEXT DEFAULT 'text',
            knowledge_tags TEXT DEFAULT '',
            explanation_level TEXT DEFAULT 'standard',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- 学习路径
        CREATE TABLE IF NOT EXISTS learning_paths (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            path_data_json TEXT DEFAULT '{}',
            progress_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- 每日任务
        CREATE TABLE IF NOT EXISTS daily_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_data_json TEXT DEFAULT '{}',
            completed INTEGER DEFAULT 0,
            date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- 学习记录
        CREATE TABLE IF NOT EXISTS learning_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            knowledge_tag TEXT DEFAULT '',
            action_type TEXT DEFAULT '',
            duration_seconds INTEGER DEFAULT 0,
            result_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- 资源收藏
        CREATE TABLE IF NOT EXISTS user_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            resource_id TEXT NOT NULL,
            collected INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- 用户LLM配置表
        CREATE TABLE IF NOT EXISTS user_llm_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            provider TEXT DEFAULT 'openai',
            api_key TEXT DEFAULT '',
            base_url TEXT DEFAULT 'https://api.openai.com',
            model_name TEXT DEFAULT 'gpt-4o',
            temperature REAL DEFAULT 0.7,
            max_tokens INTEGER DEFAULT 4096,
            image_api_key TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- 学习统计
        CREATE TABLE IF NOT EXISTS learning_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            study_duration INTEGER DEFAULT 0,
            questions_done INTEGER DEFAULT 0,
            correct_rate REAL DEFAULT 0,
            knowledge_mastery_json TEXT DEFAULT '{}',
            mastery_detail_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, date)
        );

        -- 问答反馈（自进化：👍👎）
        CREATE TABLE IF NOT EXISTS qa_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            qa_history_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            feedback_text TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (qa_history_id) REFERENCES qa_history(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- 成功模式记忆库（自进化：高质量问答模板）
        CREATE TABLE IF NOT EXISTS qa_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            answer_text TEXT NOT NULL,
            knowledge_tags TEXT DEFAULT '',
            success_count INTEGER DEFAULT 0,
            usage_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- 对话会话：短期消息由请求承载，中期记忆持久化在会话与消息表中
        CREATE TABLE IF NOT EXISTS conversation_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT DEFAULT '新对话',
            summary TEXT DEFAULT '',
            turn_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS conversation_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            knowledge_tags TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES conversation_sessions(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- 长期记忆权威存储；embedding_id 对应 Chroma 中的向量记录
        CREATE TABLE IF NOT EXISTS user_memory_facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            memory_type TEXT DEFAULT 'long_term',
            category TEXT NOT NULL,
            fact_key TEXT NOT NULL,
            fact_value TEXT NOT NULL,
            confidence REAL DEFAULT 0.8,
            mention_count INTEGER DEFAULT 1,
            access_count INTEGER DEFAULT 0,
            source_session_id INTEGER,
            embedding_id TEXT DEFAULT '',
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, category, fact_key),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        -- 编程实验三维掌握度：基本测试、用户解释、变式迁移
        CREATE TABLE IF NOT EXISTS knowledge_mastery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            knowledge_tag TEXT NOT NULL,
            source_exercise_id TEXT DEFAULT '',
            mastery_score REAL DEFAULT 0.5,
            basic_score REAL DEFAULT 0,
            explanation_score REAL DEFAULT 0,
            transfer_score REAL DEFAULT 0,
            attempt_count INTEGER DEFAULT 0,
            incorrect_count INTEGER DEFAULT 0,
            last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_review_at TIMESTAMP,
            next_review_at TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, knowledge_tag),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_conversation_user_active
            ON conversation_sessions(user_id, last_active_at);
        CREATE INDEX IF NOT EXISTS idx_conversation_messages_session
            ON conversation_messages(session_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_memory_user_category
            ON user_memory_facts(user_id, category, mention_count);
        CREATE INDEX IF NOT EXISTS idx_mastery_user_due
            ON knowledge_mastery(user_id, next_review_at, mastery_score);
    """)

    # RAG 知识库文档追踪表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rag_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_title TEXT DEFAULT '',
            source_module TEXT DEFAULT '',
            doc_hash TEXT NOT NULL,
            chunk_count INTEGER DEFAULT 0,
            char_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            error_msg TEXT DEFAULT '',
            ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_source ON rag_documents(source_path)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rag_status ON rag_documents(status)")

    # 数据库迁移
    _run_migration(conn, "error_questions", "session_id INTEGER", "错题表迁移: 添加 session_id 列")
    _run_migration(conn, "user_llm_config", "image_api_key TEXT DEFAULT ''", "LLM配置表迁移: 添加 image_api_key 列")
    _run_migration(conn, "user_llm_config", "embedding_provider TEXT DEFAULT 'siliconflow'", "LLM配置表迁移: 添加 embedding_provider 列")
    _run_migration(conn, "user_llm_config", "embedding_api_key TEXT DEFAULT ''", "LLM配置表迁移: 添加 embedding_api_key 列")
    _run_migration(conn, "user_llm_config", "embedding_model TEXT DEFAULT 'BAAI/bge-large-zh-v1.5'", "LLM配置表迁移: 添加 embedding_model 列")
    _run_migration(conn, "user_llm_config", "search_api_key TEXT DEFAULT ''", "LLM配置表迁移: 添加 search_api_key 列")
    _run_migration(conn, "conversation_messages", "metadata TEXT DEFAULT '{}'", "对话消息表迁移: 添加 metadata 列")
    _run_migration(conn, "learning_stats", "mastery_detail_json TEXT DEFAULT '{}'", "学习统计表迁移: 添加 mastery_detail_json 列")
    _run_migration(conn, "qa_history", "rag_sources_json TEXT DEFAULT ''", "QA历史表迁移: 添加 rag_sources_json 列")
    _run_migration(conn, "users", "programming_background TEXT DEFAULT ''", "用户表迁移: 添加技术背景")
    _run_migration(conn, "users", "years_experience INTEGER DEFAULT 0", "用户表迁移: 添加从业年限")
    _run_migration(conn, "users", "answer_preference TEXT DEFAULT '分步清晰'", "用户表迁移: 添加回答偏好")

    # 教程文档表 — 种子数据 + 用户私有修改 + AI 生成
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tutorial_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            knowledge_tag TEXT NOT NULL,
            title TEXT DEFAULT '',
            content TEXT NOT NULL,
            source_type TEXT DEFAULT 'seed',
            user_id INTEGER,
            parent_id INTEGER,
            curriculum_version TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tutorial_knowledge ON tutorial_documents(knowledge_tag, user_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tutorial_user ON tutorial_documents(user_id, source_type)")
    conn.commit()

    # 习题评测元数据表 — 存储每道题的锁定代码/目标函数/测试用例
    conn.execute("""
        CREATE TABLE IF NOT EXISTS exercise_test_metadata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id TEXT UNIQUE NOT NULL,
            exercise_type TEXT DEFAULT 'function',
            target_function TEXT DEFAULT '',
            locked_code TEXT DEFAULT '',
            guide_comment TEXT DEFAULT '# 请在此处实现代码',
            test_cases_json TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.commit()

    # 代码提交评测记录表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS code_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exercise_id TEXT NOT NULL,
            code TEXT NOT NULL,
            passed INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            score REAL DEFAULT 0,
            verified INTEGER DEFAULT 0,
            results_json TEXT DEFAULT '[]',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    _run_migration(conn, "code_submissions", "verified INTEGER DEFAULT 0", "代码提交表迁移: 添加能力验证状态")
    _run_migration(conn, "capability_sessions", "variant_scenario TEXT DEFAULT ''", "能力验证表迁移: 变式迁移场景")
    _run_migration(conn, "capability_sessions", "variant_code TEXT DEFAULT ''", "能力验证表迁移: 变式代码")
    _run_migration(conn, "capability_sessions", "variant_score REAL DEFAULT 0", "能力验证表迁移: 变式评分")
    _run_migration(conn, "capability_sessions", "variant_passed_at TIMESTAMP", "能力验证表迁移: 变式完成时间")
    _run_migration(conn, "capability_sessions", "variant_hints_json TEXT DEFAULT '[]'", "能力验证表迁移: 变式提示")

    # 编程能力真实性验证会话：代码正确只是起点，答辩与故障修复通过后才算掌握
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS capability_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exercise_id TEXT NOT NULL,
            exercise_title TEXT DEFAULT '',
            knowledge_tag TEXT DEFAULT '',
            status TEXT DEFAULT 'coding',
            original_code TEXT DEFAULT '',
            defense_questions_json TEXT DEFAULT '[]',
            defense_answers_json TEXT DEFAULT '[]',
            mutation_code TEXT DEFAULT '',
            mutation_description TEXT DEFAULT '',
            repair_code TEXT DEFAULT '',
            repair_explanation TEXT DEFAULT '',
            variant_scenario TEXT DEFAULT '',
            variant_code TEXT DEFAULT '',
            variant_hints_json TEXT DEFAULT '[]',
            ai_usage TEXT DEFAULT '未使用',
            code_score REAL DEFAULT 0,
            defense_score REAL DEFAULT 0,
            repair_score REAL DEFAULT 0,
            variant_score REAL DEFAULT 0,
            process_score REAL DEFAULT 0,
            total_score REAL DEFAULT 0,
            verified INTEGER DEFAULT 0,
            report_json TEXT DEFAULT '{}',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            code_passed_at TIMESTAMP,
            variant_passed_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS capability_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES capability_sessions(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_capability_session_user_exercise
            ON capability_sessions(user_id, exercise_id, started_at);
        CREATE INDEX IF NOT EXISTS idx_capability_events_session
            ON capability_events(session_id, created_at);
    """)
    conn.commit()

    # 电子书表
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pdf_books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            original_name TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            cover TEXT DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    _run_migration(conn, "pdf_books", "cover TEXT DEFAULT NULL", "电子书表迁移: 添加封面字段")

    # Seed demo user
    try:
        from auth import hash_password
        existing = conn.execute("SELECT id FROM users WHERE username = 'demo'").fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO users (username, password_hash, nickname, grade, learning_stage, learning_goal) VALUES (?, ?, ?, ?, ?, ?)",
                ("demo", hash_password("demo123"), "Demo学员", "大一/计算机科学", "入门", "系统掌握AI智能体学科知识")
            )
            conn.execute(
                "INSERT INTO learning_stats (user_id, date, study_duration, questions_done, correct_rate) VALUES (1, date('now'), 45, 12, 0.75)"
            )
            print("[OK] Demo account created: demo / demo123")
    except Exception as e:
        print(f"[WARN] Demo seed failed: {e}")

    # Seed bundled PDF metadata without replacing the persistent database.
    # The PDF binaries are version-controlled, while the live SQLite file is
    # intentionally not; merge missing rows by username and filename.
    try:
        import json as _json

        _pdf_seed_path = os.path.join(os.path.dirname(__file__), "data", "pdf_books_seed.json")
        _pdf_dir = os.path.join(os.path.dirname(__file__), "data", "pdfs")
        _pdf_count = 0
        if os.path.exists(_pdf_seed_path):
            with open(_pdf_seed_path, "r", encoding="utf-8") as _f:
                _pdf_seed = _json.load(_f)
            for _book in _pdf_seed:
                _user = conn.execute(
                    "SELECT id FROM users WHERE username = ?", (_book.get("username", ""),)
                ).fetchone()
                _filename = os.path.basename(str(_book.get("filename", "")))
                _pdf_path = os.path.join(_pdf_dir, _filename)
                if not _user or not _filename or not os.path.isfile(_pdf_path):
                    continue
                _existing = conn.execute(
                    "SELECT 1 FROM pdf_books WHERE user_id = ? AND filename = ?",
                    (_user["id"], _filename),
                ).fetchone()
                if _existing:
                    continue
                _cover = _book.get("cover")
                if _cover and not os.path.isfile(os.path.join(_pdf_dir, "covers", os.path.basename(_cover))):
                    _cover = None
                conn.execute(
                    "INSERT INTO pdf_books "
                    "(user_id, filename, original_name, file_size, cover, created_at) "
                    "VALUES (?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))",
                    (
                        _user["id"],
                        _filename,
                        _book.get("original_name") or _filename,
                        os.path.getsize(_pdf_path),
                        _cover,
                        _book.get("created_at"),
                    ),
                )
                _pdf_count += 1
            conn.commit()
        if _pdf_count:
            print(f"[OK] Imported {_pdf_count} bundled PDF book records")
    except Exception as e:
        print(f"[WARN] Bundled PDF metadata import failed: {e}")

    # Seed knowledge_tags from JSON (only if table is empty to avoid duplicates)
    try:
        _tags_path = os.path.join(os.path.dirname(__file__), "data", "knowledge_tags.json")
        _tag_exist = conn.execute("SELECT COUNT(*) FROM knowledge_tags").fetchone()[0]
        if _tag_exist == 0 and os.path.exists(_tags_path):
            import json as _json
            with open(_tags_path, "r", encoding="utf-8") as _f:
                _tag_data = _json.load(_f)
            _tag_count = 0
            for _cat in _tag_data:
                _cat_name = _cat.get("category", "")
                for _tag in _cat.get("tags", []):
                    _tag_name = _tag.get("name", "")
                    if not _tag_name:
                        continue
                    conn.execute(
                        "INSERT INTO knowledge_tags (name, category, description) VALUES (?, ?, ?)",
                        (_tag_name, _cat_name, _tag.get("description", ""))
                    )
                    _tag_count += 1
            conn.commit()
            print(f"[OK] 已导入 {_tag_count} 条知识标签到数据库")
    except Exception as e:
        print(f"[WARN] 知识标签导入失败: {e}")

    # Seed exercise_test_metadata from exercises_processed.json (only if empty)
    try:
        _exist = conn.execute("SELECT COUNT(*) FROM exercise_test_metadata").fetchone()[0]
        if _exist == 0:
            _ex_path = os.path.join(os.path.dirname(__file__), "data", "exercises_processed.json")
            if os.path.exists(_ex_path):
                import json as _json, re as _re
                with open(_ex_path, "r", encoding="utf-8") as _f:
                    _exercises = _json.load(_f)
                _ex_count = 0
                for _ex in _exercises:
                    _raw = _ex.get("skeleton_code", "") or _ex.get("starter_code", "")
                    _funcs = _re.findall(r'def\s+(\w+)\s*\(', _raw)
                    _target = ""
                    for _fn in _funcs:
                        if not _fn.startswith("_") and _fn != "__init__":
                            _target = _fn
                            break
                    if not _target and _funcs:
                        _target = _funcs[0]
                    _cls = _re.search(r'class\s+(\w+)', _raw)
                    _etype = "class_method" if _cls else "function"
                    _guide = f"# 请在此处实现 {_target}() 函数功能" if _target else "# 请在此处编写代码"
                    conn.execute(
                        "INSERT OR IGNORE INTO exercise_test_metadata "
                        "(exercise_id, exercise_type, target_function, locked_code, guide_comment, test_cases_json) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (_ex["id"], _etype, _target, _raw, _guide, "[]")
                    )
                    _ex_count += 1
                conn.commit()
                print(f"[OK] 已导入 {_ex_count} 条习题评测元数据")
    except Exception as e:
        print(f"[WARN] 习题元数据导入失败: {e}")

    # Seed tutorial_documents from tutorial_seed.json (only insert new knowledge_tags)
    try:
        _seed_path = os.path.join(os.path.dirname(__file__), "data", "tutorial_seed.json")
        if os.path.exists(_seed_path):
            import json as _json
            with open(_seed_path, "r", encoding="utf-8") as _f:
                _seed_docs = _json.load(_f)
            _imported = 0
            for _doc in _seed_docs:
                _existing = conn.execute(
                    "SELECT 1 FROM tutorial_documents WHERE knowledge_tag = ? AND source_type = 'seed' AND user_id IS NULL",
                    (_doc["knowledge_tag"],)
                ).fetchone()
                if _existing:
                    # Update existing seed record so edited tutorials take effect on restart
                    conn.execute(
                        "UPDATE tutorial_documents SET title = ?, content = ?, curriculum_version = ?, updated_at = datetime('now') "
                        "WHERE knowledge_tag = ? AND source_type = 'seed' AND user_id IS NULL",
                        (_doc.get("title", ""), _doc["content"], _doc.get("curriculum_version", ""), _doc["knowledge_tag"])
                    )
                    _imported += 1
                    continue
                conn.execute(
                    "INSERT INTO tutorial_documents (knowledge_tag, title, content, source_type, user_id, parent_id, curriculum_version) "
                    "VALUES (?, ?, ?, 'seed', NULL, NULL, ?)",
                    (_doc["knowledge_tag"], _doc.get("title", ""), _doc["content"], _doc.get("curriculum_version", ""))
                )
                _imported += 1
            conn.commit()
            if _imported:
                print(f"[OK] Imported {_imported} tutorial seed documents into tutorial_documents table")
    except Exception as e:
        print(f"[WARN] Tutorial seed import failed: {e}")

    conn.commit()
    conn.close()

    # 自动导入 generated_images 目录中的 SVG 文件到数据库
    _import_svgs_to_db()

    print("[OK] Database initialized successfully")


def _import_svgs_to_db():
    """将 generated_images 目录中的 SVG 文件自动导入 SQLite，确保首次运行即有所需配图"""
    import os as _os
    images_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "data", "generated_images")
    if not _os.path.isdir(images_dir):
        return

    conn = get_db()
    conn.execute(
        "CREATE TABLE IF NOT EXISTS generated_images ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, "
        "prompt_hash TEXT NOT NULL, prompt_text TEXT NOT NULL, "
        "svg_content TEXT, file_path TEXT, provider TEXT DEFAULT 'llm-svg', "
        "created_at TEXT)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_img_h ON generated_images(prompt_hash)")

    imported = 0
    for fn in _os.listdir(images_dir):
        if not fn.endswith('.svg'):
            continue
        h = fn.replace('.svg', '')
        # 跳过已存在的
        existing = conn.execute(
            "SELECT 1 FROM generated_images WHERE prompt_hash = ? AND svg_content IS NOT NULL",
            (h,)
        ).fetchone()
        if existing:
            continue
        fpath = _os.path.join(images_dir, fn)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                svg = f.read()
            conn.execute(
                "INSERT OR REPLACE INTO generated_images "
                "(user_id, prompt_hash, prompt_text, svg_content, file_path, provider, created_at) "
                "VALUES (1, ?, ?, ?, ?, 'bundled', datetime('now'))",
                (h, f"bundled {h[:16]}", svg, fpath)
            )
            imported += 1
        except Exception:
            pass

    if imported > 0:
        print(f"[OK] 已导入 {imported} 张 SVG 配图到数据库")
    conn.commit()
    conn.close()

def _seed_pg_data(conn):
    """PostgreSQL 模式下验证/补充种子数据（服务器可能已有数据，使用 ON CONFLICT 安全插入）"""
    import json as _json

    # ── Demo 用户 ──
    try:
        from auth import hash_password, verify_password
        existing = conn.execute("SELECT * FROM users WHERE username = 'demo'").fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO users (username, password_hash, nickname, grade, learning_stage, learning_goal) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                ("demo", hash_password("demo123"), "Demo学员", "大一/计算机科学", "入门", "系统掌握AI智能体学科知识")
            )
            conn.execute(
                "INSERT INTO learning_stats (user_id, date, study_duration, questions_done, correct_rate) "
                "VALUES (1, CURRENT_DATE, 45, 12, 0.75) "
                "ON CONFLICT (user_id, date) DO NOTHING"
            )
            conn.commit()
            print("[OK] Demo account created: demo / demo123")
        elif not verify_password("demo123", existing["password_hash"]):
            # 已有用户但密码不匹配 → 更新为正确密码
            conn.execute(
                "UPDATE users SET password_hash = %s WHERE username = 'demo'",
                (hash_password("demo123"),)
            )
            conn.commit()
            print("[OK] Demo password reset to demo123")
    except Exception as e:
        print(f"[WARN] PG demo seed failed: {e}")

    # ── Knowledge Tags ──
    try:
        _tag_exist = conn.execute("SELECT COUNT(*) AS cnt FROM knowledge_tags").fetchone()
        if _tag_exist["cnt"] == 0:
            _tags_path = os.path.join(os.path.dirname(__file__), "data", "knowledge_tags.json")
            if os.path.exists(_tags_path):
                with open(_tags_path, "r", encoding="utf-8") as _f:
                    _tag_data = _json.load(_f)
                _tag_count = 0
                for _cat in _tag_data:
                    _cat_name = _cat.get("category", "")
                    for _tag in _cat.get("tags", []):
                        _tag_name = _tag.get("name", "")
                        if not _tag_name:
                            continue
                        conn.execute(
                            "INSERT INTO knowledge_tags (name, category, description) "
                            "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                            (_tag_name, _cat_name, _tag.get("description", ""))
                        )
                        _tag_count += 1
                conn.commit()
                print(f"[OK] PG: 已导入 {_tag_count} 条知识标签")
    except Exception as e:
        print(f"[WARN] PG knowledge_tags seed failed: {e}")

    # ── Exercise Metadata ──
    try:
        _exist = conn.execute("SELECT COUNT(*) AS cnt FROM exercise_test_metadata").fetchone()
        if _exist["cnt"] == 0:
            _ex_path = os.path.join(os.path.dirname(__file__), "data", "exercises_processed.json")
            if os.path.exists(_ex_path):
                import re as _re
                with open(_ex_path, "r", encoding="utf-8") as _f:
                    _exercises = _json.load(_f)
                _ex_count = 0
                for _ex in _exercises:
                    _raw = _ex.get("skeleton_code", "") or _ex.get("starter_code", "")
                    _funcs = _re.findall(r'def\s+(\w+)\s*\(', _raw)
                    _target = ""
                    for _fn in _funcs:
                        if not _fn.startswith("_") and _fn != "__init__":
                            _target = _fn
                            break
                    if not _target and _funcs:
                        _target = _funcs[0]
                    _cls = _re.search(r'class\s+(\w+)', _raw)
                    _etype = "class_method" if _cls else "function"
                    _guide = f"# 请在此处实现 {_target}() 函数功能" if _target else "# 请在此处编写代码"
                    conn.execute(
                        "INSERT INTO exercise_test_metadata "
                        "(exercise_id, exercise_type, target_function, locked_code, guide_comment, test_cases_json) "
                        "VALUES (%s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (exercise_id) DO NOTHING",
                        (_ex["id"], _etype, _target, _raw, _guide, "[]")
                    )
                    _ex_count += 1
                conn.commit()
                print(f"[OK] PG: 已导入 {_ex_count} 条习题元数据")
    except Exception as e:
        print(f"[WARN] PG exercise metadata seed failed: {e}")

    # ── Tutorial Seed Documents ──
    try:
        _seed_path = os.path.join(os.path.dirname(__file__), "data", "tutorial_seed.json")
        if os.path.exists(_seed_path):
            with open(_seed_path, "r", encoding="utf-8") as _f:
                _seed_docs = _json.load(_f)
            _imported = 0
            for _doc in _seed_docs:
                _existing = conn.execute(
                    "SELECT 1 FROM tutorial_documents WHERE knowledge_tag = %s AND source_type = 'seed' AND user_id IS NULL",
                    (_doc["knowledge_tag"],)
                ).fetchone()
                if _existing:
                    continue
                conn.execute(
                    "INSERT INTO tutorial_documents "
                    "(knowledge_tag, title, content, source_type, user_id, parent_id, curriculum_version) "
                    "VALUES (%s, %s, %s, 'seed', NULL, NULL, %s)",
                    (_doc["knowledge_tag"], _doc.get("title", ""), _doc["content"],
                     _doc.get("curriculum_version", ""))
                )
                _imported += 1
            conn.commit()
            if _imported:
                print(f"[OK] PG: Imported {_imported} tutorial seed documents")
    except Exception as e:
        print(f"[WARN] PG tutorial seed failed: {e}")

    # ── SVG Images（PG 模式跳过 — 配图按需生成，无需预导入 189 个大文件） ──
    print("[OK] PG: SVG 配图跳过（按需生成）")


if __name__ == "__main__":
    init_db()
