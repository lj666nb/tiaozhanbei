-- ============================================================================
-- AI智能体学科学习平台 — 统一 PostgreSQL 数据库建表脚本
-- ============================================================================
-- 合并来源:
--   1. 助学系统 (Student Learning Platform) — 25 张表
--   2. 助教系统 (Edu-TA Teaching Assistant) — 12 张表
-- 总计: 37 张业务表
--
-- 使用方法:
--   psql -h <host> -U <user> -d <dbname> -f merged_schema.sql
--
-- 生成日期: 2026-07-23
-- ============================================================================

-- ============================================================================
-- 扩展
-- ============================================================================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";      -- UUID 生成
CREATE EXTENSION IF NOT EXISTS "pgcrypto";        -- gen_random_uuid() (PG13+ 内置)

-- ============================================================================
-- 域名 / 自定义类型
-- ============================================================================

-- 用户角色
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('student', 'teacher', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 学习阶段
DO $$ BEGIN
    CREATE TYPE learning_stage AS ENUM ('入门', '进阶', '高阶');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 解答详细程度
DO $$ BEGIN
    CREATE TYPE explanation_level AS ENUM ('beginner', 'standard', 'advanced');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 教程来源类型
DO $$ BEGIN
    CREATE TYPE tutorial_source_type AS ENUM ('seed', 'user_modified', 'ai_generated');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 教案操作类型
DO $$ BEGIN
    CREATE TYPE audit_operation AS ENUM ('create', 'view', 'edit', 'export', 'delete', 'restore');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 工作流状态
DO $$ BEGIN
    CREATE TYPE workflow_status AS ENUM ('pending', 'running', 'completed', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- 题目状态
DO $$ BEGIN
    CREATE TYPE question_status AS ENUM ('draft', 'published');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ============================================================================
-- 第一部分: 用户与认证 (1 张表)
-- ============================================================================

-- 1. users — 统一用户表（合并自助学 users + 助教教师信息）
CREATE TABLE users (
    id                      SERIAL PRIMARY KEY,
    username                TEXT NOT NULL UNIQUE,
    password_hash           TEXT NOT NULL,
    nickname                TEXT DEFAULT '',
    role                    user_role DEFAULT 'student',
    -- 教师专属字段
    title                   TEXT DEFAULT '',          -- 职称（讲师/副教授/教授）
    department              TEXT DEFAULT '',          -- 所属院系
    school                  TEXT DEFAULT '',          -- 所属学校
    -- 学生专属字段（来自助学）
    grade                   TEXT DEFAULT '',          -- 年级/身份
    learning_stage          learning_stage DEFAULT '入门',
    learning_goal           TEXT DEFAULT '',
    avatar                  TEXT DEFAULT '',
    programming_background  TEXT DEFAULT '',          -- 编程背景
    years_experience        INTEGER DEFAULT 0,        -- 从业年限
    answer_preference       TEXT DEFAULT '分步清晰',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);

-- 种子数据: demo / demo123 (nickname=Demo学员, role=student)
-- 助教系统也共用此认证表，教师通过 role='teacher' 区分


-- ============================================================================
-- 第二部分: 助学系统核心表 (24 张表)
-- ============================================================================

-- 2. knowledge_tags — 知识点标签库
CREATE TABLE knowledge_tags (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    description TEXT DEFAULT '',
    parent_id   INTEGER DEFAULT 0
);

-- 3. quiz_sessions — 测评会话
CREATE TABLE quiz_sessions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    stage           TEXT DEFAULT '入门',
    questions_json  JSONB DEFAULT '[]',
    answers_json    JSONB DEFAULT '[]',
    score           REAL DEFAULT 0,
    total           INTEGER DEFAULT 0,
    report_json     JSONB DEFAULT '{}',
    status          TEXT DEFAULT 'pending',   -- pending / completed
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);
CREATE INDEX idx_quiz_user ON quiz_sessions(user_id);

-- 4. error_questions — 错题本
CREATE TABLE error_questions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    session_id      INTEGER,                  -- 可空：通过 migration 添加
    question_data   JSONB NOT NULL,
    user_answer     TEXT DEFAULT '',
    correct_answer  TEXT DEFAULT '',
    error_type      TEXT DEFAULT '',
    knowledge_tag   TEXT DEFAULT '',
    reviewed        INTEGER DEFAULT 0,        -- 0=未复习, 1=已复习
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_error_user ON error_questions(user_id);

-- 5. qa_history — 问答历史
CREATE TABLE qa_history (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    question          TEXT NOT NULL,
    answer            TEXT NOT NULL,
    question_type     TEXT DEFAULT 'text',    -- text / code
    knowledge_tags    JSONB DEFAULT '[]',
    explanation_level explanation_level DEFAULT 'standard',
    rag_sources_json  JSONB DEFAULT '[]',
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_qa_user ON qa_history(user_id);

-- 6. learning_paths — 学习路径
CREATE TABLE learning_paths (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    path_data_json  JSONB DEFAULT '{}',
    progress_json   JSONB DEFAULT '{}',
    status          TEXT DEFAULT 'active',    -- active / archived
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_path_user ON learning_paths(user_id);

-- 7. daily_tasks — 每日任务
CREATE TABLE daily_tasks (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    task_data_json  JSONB DEFAULT '{}',
    completed       INTEGER DEFAULT 0,        -- 0=未完成, 1=已完成
    date            DATE NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_daily_user_date ON daily_tasks(user_id, date);

-- 8. learning_records — 学习行为记录
CREATE TABLE learning_records (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    knowledge_tag     TEXT DEFAULT '',
    action_type       TEXT DEFAULT '',        -- qa / quiz / quiz_start / review_error
    duration_seconds  INTEGER DEFAULT 0,
    result_json       JSONB DEFAULT '{}',
    created_at        TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_record_user ON learning_records(user_id);

-- 9. user_resources — 资源收藏
CREATE TABLE user_resources (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    resource_id TEXT NOT NULL,
    collected   INTEGER DEFAULT 0,            -- 0=未收藏, 1=已收藏
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_resource_user ON user_resources(user_id);

-- 10. user_llm_config — 用户 LLM / API 配置
CREATE TABLE user_llm_config (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL UNIQUE REFERENCES users(id),
    provider            TEXT DEFAULT 'openai',
    api_key             TEXT DEFAULT '',
    base_url            TEXT DEFAULT 'https://api.openai.com',
    model_name          TEXT DEFAULT 'gpt-4o',
    temperature         REAL DEFAULT 0.7,
    max_tokens          INTEGER DEFAULT 4096,
    image_api_key       TEXT DEFAULT '',
    embedding_provider  TEXT DEFAULT '',
    embedding_api_key   TEXT DEFAULT '',
    embedding_model     TEXT DEFAULT 'text-embedding-v3',
    search_api_key      TEXT DEFAULT '',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

-- 11. learning_stats — 每日学习统计
CREATE TABLE learning_stats (
    id                      SERIAL PRIMARY KEY,
    user_id                 INTEGER NOT NULL REFERENCES users(id),
    date                    DATE NOT NULL,
    study_duration          INTEGER DEFAULT 0,       -- 学习时长（分钟）
    questions_done          INTEGER DEFAULT 0,
    correct_rate            REAL DEFAULT 0,
    knowledge_mastery_json  JSONB DEFAULT '{}',
    mastery_detail_json     JSONB DEFAULT '{}',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, date)
);

-- 12. qa_feedback — 问答反馈
CREATE TABLE qa_feedback (
    id              SERIAL PRIMARY KEY,
    qa_history_id   INTEGER NOT NULL REFERENCES qa_history(id),
    user_id         INTEGER NOT NULL REFERENCES users(id),
    rating          INTEGER NOT NULL,          -- 1=👍, -1=👎
    feedback_text   TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_feedback_qa ON qa_feedback(qa_history_id);

-- 13. qa_patterns — 成功模式记忆库
CREATE TABLE qa_patterns (
    id              SERIAL PRIMARY KEY,
    question_text   TEXT NOT NULL,
    answer_text     TEXT NOT NULL,
    knowledge_tags  JSONB DEFAULT '[]',
    success_count   INTEGER DEFAULT 0,
    usage_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 14. conversation_sessions — 对话会话
CREATE TABLE conversation_sessions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    title           TEXT DEFAULT '新对话',
    summary         TEXT DEFAULT '',
    turn_count      INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_active_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_conv_user_active ON conversation_sessions(user_id, last_active_at);

-- 15. conversation_messages — 对话消息
CREATE TABLE conversation_messages (
    id              SERIAL PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES conversation_sessions(id),
    user_id         INTEGER NOT NULL REFERENCES users(id),
    role            TEXT NOT NULL,             -- user / assistant
    content         TEXT NOT NULL,
    knowledge_tags  JSONB DEFAULT '[]',
    metadata        JSONB DEFAULT '{}',        -- RAG 来源等
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_conv_msg_session ON conversation_messages(session_id, created_at);

-- 16. user_memory_facts — 长期记忆
CREATE TABLE user_memory_facts (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    memory_type       TEXT DEFAULT 'long_term',
    category          TEXT NOT NULL,           -- preference / profile / interest / goal
    fact_key          TEXT NOT NULL,
    fact_value        TEXT NOT NULL,
    confidence        REAL DEFAULT 0.8,
    mention_count     INTEGER DEFAULT 1,
    access_count      INTEGER DEFAULT 0,
    source_session_id INTEGER,
    embedding_id      TEXT DEFAULT '',         -- Chroma 向量 ID
    first_seen_at     TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, category, fact_key)
);
CREATE INDEX idx_memory_user_category ON user_memory_facts(user_id, category, mention_count);

-- 17. knowledge_mastery — 编程三维掌握度
CREATE TABLE knowledge_mastery (
    id                SERIAL PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id),
    knowledge_tag     TEXT NOT NULL,
    source_exercise_id TEXT DEFAULT '',
    mastery_score     REAL DEFAULT 0.5,        -- 综合掌握度 (0-1)
    basic_score       REAL DEFAULT 0,          -- 基本测试得分
    explanation_score REAL DEFAULT 0,          -- 用户解释得分
    transfer_score    REAL DEFAULT 0,          -- 变式迁移得分
    attempt_count     INTEGER DEFAULT 0,
    incorrect_count   INTEGER DEFAULT 0,
    last_activity_at  TIMESTAMPTZ DEFAULT NOW(),
    last_review_at    TIMESTAMPTZ,
    next_review_at    TIMESTAMPTZ,
    updated_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, knowledge_tag)
);
CREATE INDEX idx_mastery_user_due ON knowledge_mastery(user_id, next_review_at, mastery_score);

-- 18. tutorial_documents — 教程文档
CREATE TABLE tutorial_documents (
    id                  SERIAL PRIMARY KEY,
    knowledge_tag       TEXT NOT NULL,
    title               TEXT DEFAULT '',
    content             TEXT NOT NULL,
    source_type         tutorial_source_type DEFAULT 'seed',
    user_id             INTEGER REFERENCES users(id),  -- NULL=种子数据（共享）
    parent_id           INTEGER,                        -- 用户修改种子文档时指向原始种子
    curriculum_version  TEXT DEFAULT '',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tutorial_knowledge ON tutorial_documents(knowledge_tag, user_id);
CREATE INDEX idx_tutorial_user ON tutorial_documents(user_id, source_type);

-- 19. exercise_test_metadata — 习题评测元数据
CREATE TABLE exercise_test_metadata (
    id                SERIAL PRIMARY KEY,
    exercise_id       TEXT NOT NULL UNIQUE,    -- 习题编号 (如 1-1, 1-2)
    exercise_type     TEXT DEFAULT 'function', -- function / class_method
    target_function   TEXT DEFAULT '',
    locked_code       TEXT DEFAULT '',         -- 锁定代码（不可编辑部分）
    guide_comment     TEXT DEFAULT '# 请在此处实现代码',
    test_cases_json   JSONB DEFAULT '[]',
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    updated_at        TIMESTAMPTZ DEFAULT NOW()
);

-- 20. code_submissions — 代码提交记录
CREATE TABLE code_submissions (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    exercise_id     TEXT NOT NULL,
    code            TEXT NOT NULL,
    passed          INTEGER DEFAULT 0,        -- 通过测试数
    total           INTEGER DEFAULT 0,        -- 总测试数
    score           REAL DEFAULT 0,
    verified        INTEGER DEFAULT 0,        -- 0=未验证, 1=能力已验证
    results_json    JSONB DEFAULT '[]',
    submitted_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_submission_user_ex ON code_submissions(user_id, exercise_id);

-- 21. capability_sessions — 能力验证会话
CREATE TABLE capability_sessions (
    id                      SERIAL PRIMARY KEY,
    user_id                 INTEGER NOT NULL REFERENCES users(id),
    exercise_id             TEXT NOT NULL,
    exercise_title          TEXT DEFAULT '',
    knowledge_tag           TEXT DEFAULT '',
    status                  TEXT DEFAULT 'coding',  -- coding → defense_pending → repair_pending → verified
    original_code           TEXT DEFAULT '',
    defense_questions_json  JSONB DEFAULT '[]',
    defense_answers_json    JSONB DEFAULT '[]',
    mutation_code           TEXT DEFAULT '',
    mutation_description    TEXT DEFAULT '',
    repair_code             TEXT DEFAULT '',
    repair_explanation      TEXT DEFAULT '',
    ai_usage                TEXT DEFAULT '未使用',
    code_score              REAL DEFAULT 0,
    defense_score           REAL DEFAULT 0,
    repair_score            REAL DEFAULT 0,
    process_score           REAL DEFAULT 0,
    total_score             REAL DEFAULT 0,
    verified                INTEGER DEFAULT 0,
    report_json             JSONB DEFAULT '{}',
    started_at              TIMESTAMPTZ DEFAULT NOW(),
    code_passed_at          TIMESTAMPTZ,
    completed_at            TIMESTAMPTZ
);
CREATE INDEX idx_cap_session_user_ex ON capability_sessions(user_id, exercise_id, started_at);

-- 22. capability_events — 能力验证事件
CREATE TABLE capability_events (
    id              SERIAL PRIMARY KEY,
    session_id      INTEGER NOT NULL REFERENCES capability_sessions(id),
    user_id         INTEGER NOT NULL REFERENCES users(id),
    event_type      TEXT NOT NULL,            -- session_start / edit / submit / code_passed / defense_submit / repair_submit / verified
    payload_json    JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_cap_events_session ON capability_events(session_id, created_at);

-- 23. pdf_books — 电子书
CREATE TABLE pdf_books (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),
    filename        TEXT NOT NULL,            -- 存储文件名
    original_name   TEXT NOT NULL,            -- 原始文件名
    file_size       INTEGER DEFAULT 0,
    cover           TEXT DEFAULT NULL,        -- 封面路径
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- 24. rag_documents — RAG 文档追踪
CREATE TABLE rag_documents (
    id              SERIAL PRIMARY KEY,
    source_path     TEXT NOT NULL,
    source_type     TEXT NOT NULL,            -- pdf / markdown / qa
    source_title    TEXT DEFAULT '',
    source_module   TEXT DEFAULT '',
    doc_hash        TEXT NOT NULL,
    chunk_count     INTEGER DEFAULT 0,
    char_count      INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending',   -- pending / ingested / error
    error_msg       TEXT DEFAULT '',
    ingested_at     TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_rag_source ON rag_documents(source_path);
CREATE INDEX idx_rag_status ON rag_documents(status);

-- 25. generated_images — AI 生成配图
CREATE TABLE generated_images (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL,
    prompt_hash     TEXT NOT NULL,
    prompt_text     TEXT NOT NULL,
    svg_content     TEXT,
    file_path       TEXT,
    provider        TEXT DEFAULT 'llm-svg',   -- bundled / llm-svg
    created_at      TEXT
);
CREATE INDEX idx_img_h ON generated_images(prompt_hash);


-- ============================================================================
-- 第三部分: 助教系统核心表 (12 张表)
-- ============================================================================

-- 26. lesson_plans — 教案
CREATE TABLE lesson_plans (
    id                      UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id                 INTEGER NOT NULL REFERENCES users(id),  -- 创建教案的教师
    course_name             TEXT NOT NULL,
    chapter                 TEXT DEFAULT '',
    total_hours             INTEGER DEFAULT 2,
    additional_requirements TEXT DEFAULT '',        -- 附加要求（如"偏重实践"）
    plan_data               JSONB NOT NULL,         -- 完整教案 JSON（目标/活动/作业/板书/评价量规）
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_lesson_course ON lesson_plans(course_name);
CREATE INDEX idx_lesson_user ON lesson_plans(user_id);

-- 27. homework_grades — 作业批改结果
CREATE TABLE homework_grades (
    id                  UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id),  -- 学生
    student_name        TEXT DEFAULT '',            -- 冗余学生姓名
    course_name         TEXT NOT NULL,
    chapter             TEXT DEFAULT '',            -- 所属章节 / 班级名
    question_text       TEXT DEFAULT '',
    student_answer      TEXT DEFAULT '',
    question_type       TEXT DEFAULT '',            -- 选择题/填空题/主观题/计算题/手动录入
    max_score           REAL DEFAULT 100,
    score               REAL DEFAULT 0,
    percentage          REAL DEFAULT 0,            -- 得分百分比 (0-100)
    feedback            TEXT DEFAULT '',            -- 综合评语
    strengths           JSONB DEFAULT '[]',         -- 优点列表
    weaknesses          JSONB DEFAULT '[]',         -- 不足与错误
    suggestions         JSONB DEFAULT '[]',         -- 改进建议
    knowledge_points    JSONB DEFAULT '[]',         -- 涉及知识点
    detailed_analysis   TEXT DEFAULT '',            -- 逐句/逐步详细分析
    source_file         TEXT DEFAULT '',            -- 来源文件名
    batch_id            TEXT DEFAULT '',            -- 同一批次上传的标识
    is_archived         BOOLEAN DEFAULT FALSE,      -- 是否已归档至教学台账
    project_id          TEXT DEFAULT 'ta-project',  -- 数据来源: ta-project / student-project
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_hw_course ON homework_grades(course_name);
CREATE INDEX idx_hw_user ON homework_grades(user_id);
CREATE INDEX idx_hw_project ON homework_grades(project_id);

-- 28. exercise_batches — AI 出题批次
CREATE TABLE exercise_batches (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),  -- 出题教师
    course_name     TEXT NOT NULL,
    chapter         TEXT DEFAULT '',
    difficulty      TEXT DEFAULT '中等',         -- 简单/中等/困难
    total           INTEGER DEFAULT 0,
    exercises_json  JSONB DEFAULT '[]',          -- 完整题目列表
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_ex_batch_course ON exercise_batches(course_name);
CREATE INDEX idx_ex_batch_user ON exercise_batches(user_id);

-- 29. materials — 教学资料
CREATE TABLE materials (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),  -- 上传者
    filename        TEXT NOT NULL,
    course          TEXT DEFAULT '未分类',
    chapter         TEXT DEFAULT '',
    size_bytes      INTEGER DEFAULT 0,
    size_display    TEXT DEFAULT '',            -- 可读大小（如 "2.3 MB"）
    pages           INTEGER DEFAULT 0,
    text_preview    TEXT DEFAULT '',            -- 文本预览（前若干字）
    text_content    TEXT DEFAULT '',            -- 全文内容
    file_path       TEXT DEFAULT '',
    project_id      TEXT DEFAULT 'ta-project',  -- 数据来源
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_mat_course ON materials(course);
CREATE INDEX idx_mat_user ON materials(user_id);
CREATE INDEX idx_mat_project ON materials(project_id);

-- 30. questions — AI 生成题目
CREATE TABLE questions (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),  -- 出题人
    batch_id        UUID REFERENCES exercise_batches(id),
    course          TEXT DEFAULT '',
    question        TEXT NOT NULL,
    type            TEXT DEFAULT '',             -- 选择题/填空题/简答题
    options         JSONB DEFAULT '[]',          -- 选择题选项
    answer          TEXT DEFAULT '',             -- 参考答案
    difficulty      TEXT DEFAULT '',
    knowledge_point TEXT DEFAULT '',
    explanation     TEXT DEFAULT '',             -- 详细解析
    estimated_time  INTEGER DEFAULT 0,           -- 预计完成时间（分钟）
    status          question_status DEFAULT 'draft',
    scoring_rubric  TEXT DEFAULT '',             -- 评分标准
    common_mistakes TEXT DEFAULT '',             -- 常见错误
    cognitive_level TEXT DEFAULT '',             -- 认知层次
    source          TEXT DEFAULT '',             -- 来源
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_q_batch ON questions(batch_id);
CREATE INDEX idx_q_user ON questions(user_id);

-- 31. insight_reports — 学情分析报告
CREATE TABLE insight_reports (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),  -- 学生
    course_name     TEXT DEFAULT '',
    report_type     TEXT DEFAULT 'individual',   -- individual 个人 / class 班级
    report_json     JSONB NOT NULL,              -- 完整报告（综合指标/知识掌握/趋势/预警/建议/图表数据）
    project_id      TEXT DEFAULT 'ta-project',   -- 数据来源
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_insight_user ON insight_reports(user_id);
CREATE INDEX idx_insight_project ON insight_reports(project_id);

-- 32. teaching_aux — 教学辅助素材
CREATE TABLE teaching_aux (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id),  -- 创建教师
    course          TEXT DEFAULT '',
    chapter         TEXT DEFAULT '',
    aux_type        TEXT DEFAULT '',             -- difficulty 重难点 / classroom 课堂素材 / ppt 课件优化 / variant 变式题
    content_json    JSONB DEFAULT '{}',
    project_id      TEXT DEFAULT 'ta-project',   -- 数据来源
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_aux_course ON teaching_aux(course);
CREATE INDEX idx_aux_user ON teaching_aux(user_id);
CREATE INDEX idx_aux_project ON teaching_aux(project_id);

-- 33. llm_call_logs — LLM 用量统计
CREATE TABLE llm_call_logs (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER REFERENCES users(id),  -- 调用用户
    model               VARCHAR(100),
    function_name       VARCHAR(100),           -- 调用功能（备课/批改/学情等）
    prompt_tokens       INTEGER DEFAULT 0,
    completion_tokens   INTEGER DEFAULT 0,
    total_tokens        INTEGER DEFAULT 0,
    latency_ms          INTEGER DEFAULT 0,
    success             INTEGER DEFAULT 1,      -- 1=成功, 0=失败
    error_message       TEXT DEFAULT '',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_llm_func ON llm_call_logs(function_name);
CREATE INDEX idx_llm_user ON llm_call_logs(user_id);

-- 34. audit_logs — 教案操作审计日志
CREATE TABLE audit_logs (
    id              SERIAL PRIMARY KEY,
    plan_id         UUID NOT NULL REFERENCES lesson_plans(id),
    plan_name       TEXT DEFAULT '',            -- 教案名称（冗余）
    course_name     TEXT DEFAULT '',
    chapter         TEXT DEFAULT '',
    operation       audit_operation NOT NULL,
    operator        TEXT DEFAULT '系统',
    operator_role   TEXT DEFAULT '',            -- 教师/管理员
    session_index   INTEGER,                    -- 修改的具体流程索引（null=全教案操作）
    changes_before  JSONB,
    changes_after   JSONB,
    detail          TEXT DEFAULT '',
    ip_address      TEXT DEFAULT '',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_plan ON audit_logs(plan_id);
CREATE INDEX idx_audit_time ON audit_logs(created_at);

-- 35. plan_snapshots — 教案版本快照
CREATE TABLE plan_snapshots (
    id              SERIAL PRIMARY KEY,
    plan_id         UUID NOT NULL REFERENCES lesson_plans(id),
    version         INTEGER NOT NULL,
    plan_data       JSONB NOT NULL,             -- 完整教案 JSON
    created_by      TEXT DEFAULT '系统',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_snapshot_plan ON plan_snapshots(plan_id);

-- 36. agent_workflows — Agent 编排工作流
CREATE TABLE agent_workflows (
    id              UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),  -- 发起人
    type            TEXT NOT NULL,
    status          workflow_status DEFAULT 'pending',
    input_params    JSONB DEFAULT '{}',
    steps           JSONB DEFAULT '[]',
    final_output    JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);
CREATE INDEX idx_wf_type ON agent_workflows(type);
CREATE INDEX idx_wf_status ON agent_workflows(status);
CREATE INDEX idx_wf_user ON agent_workflows(user_id);

-- 37. project_registry — 项目注册表（互通桥梁）
CREATE TABLE project_registry (
    id              TEXT PRIMARY KEY,           -- "ta-project" / "student-project"
    name            TEXT NOT NULL,              -- "助教系统" / "助学系统"
    token_hash      TEXT NOT NULL,              -- SHA256 哈希的认证令牌
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);


-- ============================================================================
-- 第四部分: 外键关系总结
-- ============================================================================

-- users (1)
--  ├── quiz_sessions (N)
--  ├── error_questions (N)
--  ├── qa_history (N)
--  │    └── qa_feedback (N)
--  ├── learning_paths (N)
--  ├── daily_tasks (N)
--  ├── learning_records (N)
--  ├── user_resources (N)
--  ├── user_llm_config (1, UNIQUE)
--  ├── learning_stats (N, UNIQUE per day)
--  ├── conversation_sessions (N)
--  │    └── conversation_messages (N)
--  ├── user_memory_facts (N)
--  ├── knowledge_mastery (N)
--  ├── tutorial_documents (nullable FK)
--  ├── code_submissions (N)
--  ├── capability_sessions (N)
--  │    └── capability_events (N)
--  ├── pdf_books (N)
--  ├── lesson_plans (N)              ← 教师
--  ├── homework_grades (N)           ← 学生
--  ├── exercise_batches (N)          ← 教师
--  ├── materials (N)                 ← 上传者
--  ├── questions (N)                 ← 出题人
--  ├── insight_reports (N)           ← 学生
--  ├── teaching_aux (N)              ← 教师
--  ├── llm_call_logs (N, nullable)
--  └── agent_workflows (N, nullable)
--
-- lesson_plans (1)
--  ├── audit_logs (N)
--  └── plan_snapshots (N)
--
-- exercise_batches (1)
--  └── questions (N)
--
-- 独立表（无 FK）:
--  - knowledge_tags
--  - qa_patterns
--  - exercise_test_metadata
--  - rag_documents
--  - generated_images
--  - project_registry


-- ============================================================================
-- 第五部分: 初始种子数据
-- ============================================================================

-- 项目注册
INSERT INTO project_registry (id, name, token_hash, is_active) VALUES
    ('student-project', '助学系统', '', TRUE),
    ('ta-project',       '助教系统', '', TRUE)
ON CONFLICT (id) DO NOTHING;

-- Demo 学员账号
INSERT INTO users (username, password_hash, nickname, role, grade, learning_stage, learning_goal)
VALUES ('demo', '$2b$12$LJ3m4ys3Lk0TSwHBQRSMfOBbOdBNJZpVHWfUObiVoWSO7hFQhNR.6',
        'Demo学员', 'student', '大一/计算机科学', '入门', '掌握AI智能体开发')
ON CONFLICT (username) DO NOTHING;

-- Demo 教师账号
INSERT INTO users (username, password_hash, nickname, role, title, department)
VALUES ('teacher_demo', '$2b$12$LJ3m4ys3Lk0TSwHBQRSMfOBbOdBNJZpVHWfUObiVoWSO7hFQhNR.6',
        'Demo教师', 'teacher', '讲师', '计算机科学与技术学院')
ON CONFLICT (username) DO NOTHING;


-- ============================================================================
-- 完成
-- ============================================================================
-- 执行完毕后验证:
--   SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;
--   预期: 37 张表
--
-- 查看表大小:
--   SELECT tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename))
--   FROM pg_tables WHERE schemaname='public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
-- ============================================================================
