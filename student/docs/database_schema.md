# AI智能体学科学习平台 — 数据库表结构文档

> 当前数据库：SQLite (`backend/data/learning_platform.db`)  
> 生成日期：2026-07-23  
> 总计：**25 张业务表**

---

## 表一览

| # | 表名 | 用途 | 关键外键 |
|:--:|------|------|----------|
| 1 | `users` | 用户账户 | — |
| 2 | `knowledge_tags` | 知识点标签库 | `parent_id` 自引用 |
| 3 | `quiz_sessions` | 测评会话 | `user_id` → users |
| 4 | `error_questions` | 错题本 | `user_id` → users, `session_id` → quiz_sessions |
| 5 | `qa_history` | 问答历史 | `user_id` → users |
| 6 | `learning_paths` | 学习路径 | `user_id` → users |
| 7 | `daily_tasks` | 每日任务 | `user_id` → users |
| 8 | `learning_records` | 学习行为记录 | `user_id` → users |
| 9 | `user_resources` | 资源收藏 | `user_id` → users |
| 10 | `user_llm_config` | 用户 LLM/API 配置 | `user_id` → users (UNIQUE) |
| 11 | `learning_stats` | 每日学习统计 | `user_id` → users, UNIQUE(user_id, date) |
| 12 | `qa_feedback` | 问答反馈（👍👎） | `qa_history_id` → qa_history, `user_id` → users |
| 13 | `qa_patterns` | 成功模式记忆库 | — |
| 14 | `conversation_sessions` | 对话会话 | `user_id` → users |
| 15 | `conversation_messages` | 对话消息 | `session_id` → conversation_sessions, `user_id` → users |
| 16 | `user_memory_facts` | 长期记忆 | `user_id` → users, UNIQUE(user_id, category, fact_key) |
| 17 | `knowledge_mastery` | 编程三维掌握度 | `user_id` → users, UNIQUE(user_id, knowledge_tag) |
| 18 | `tutorial_documents` | 教程文档 | `user_id` → users (nullable) |
| 19 | `exercise_test_metadata` | 习题评测元数据 | UNIQUE(exercise_id) |
| 20 | `code_submissions` | 代码提交记录 | `user_id` → users |
| 21 | `capability_sessions` | 能力验证会话 | `user_id` → users |
| 22 | `capability_events` | 能力验证事件 | `session_id` → capability_sessions, `user_id` → users |
| 23 | `pdf_books` | 电子书 | `user_id` → users |
| 24 | `rag_documents` | RAG 文档追踪 | — |
| 25 | `generated_images` | AI 生成配图 | — |

---

## 1. users — 用户表

```sql
CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    nickname        TEXT DEFAULT '',
    grade           TEXT DEFAULT '',
    learning_stage  TEXT DEFAULT '入门',
    learning_goal   TEXT DEFAULT '',
    avatar          TEXT DEFAULT '',
    programming_background TEXT DEFAULT '',
    years_experience INTEGER DEFAULT 0,
    answer_preference TEXT DEFAULT '分步清晰',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK, AUTOINCREMENT | 用户 ID |
| username | TEXT | UNIQUE, NOT NULL | 登录用户名 |
| password_hash | TEXT | NOT NULL | bcrypt 哈希密码 |
| nickname | TEXT | DEFAULT '' | 昵称 |
| grade | TEXT | DEFAULT '' | 身份/年级 |
| learning_stage | TEXT | DEFAULT '入门' | 学习阶段（入门/进阶/高阶） |
| learning_goal | TEXT | DEFAULT '' | 学习目标 |
| avatar | TEXT | DEFAULT '' | 头像 |
| programming_background | TEXT | DEFAULT '' | 技术背景 |
| years_experience | INTEGER | DEFAULT 0 | 从业年限 |
| answer_preference | TEXT | DEFAULT '分步清晰' | 回答偏好 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**种子数据**: `demo / demo123`（nickname=Demo学员, grade=大一/计算机科学）

---

## 2. knowledge_tags — 知识点标签表

```sql
CREATE TABLE knowledge_tags (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    description TEXT DEFAULT '',
    parent_id   INTEGER DEFAULT 0
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 标签 ID |
| name | TEXT | NOT NULL | 标签名 |
| category | TEXT | NOT NULL | 所属分类 |
| description | TEXT | DEFAULT '' | 描述 |
| parent_id | INTEGER | DEFAULT 0 | 父标签 ID（0=顶级） |

**种子数据**: 从 `backend/data/knowledge_tags.json` 导入，约 30+ 条

---

## 3. quiz_sessions — 测评会话表

```sql
CREATE TABLE quiz_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    stage           TEXT DEFAULT '入门',
    questions_json  TEXT DEFAULT '[]',
    answers_json    TEXT DEFAULT '[]',
    score           REAL DEFAULT 0,
    total           INTEGER DEFAULT 0,
    report_json     TEXT DEFAULT '{}',
    status          TEXT DEFAULT 'pending',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at    TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 会话 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| stage | TEXT | DEFAULT '入门' | 测评阶段 |
| questions_json | TEXT | DEFAULT '[]' | 题目 JSON |
| answers_json | TEXT | DEFAULT '[]' | 作答 JSON |
| score | REAL | DEFAULT 0 | 得分 |
| total | INTEGER | DEFAULT 0 | 总题数 |
| report_json | TEXT | DEFAULT '{}' | 诊断报告 JSON |
| status | TEXT | DEFAULT 'pending' | pending / completed |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| completed_at | TIMESTAMP | — | 完成时间 |

---

## 4. error_questions — 错题本

```sql
CREATE TABLE error_questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    session_id      INTEGER,
    question_data   TEXT NOT NULL,
    user_answer     TEXT DEFAULT '',
    correct_answer  TEXT DEFAULT '',
    error_type      TEXT DEFAULT '',
    knowledge_tag   TEXT DEFAULT '',
    reviewed        INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 错题 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| session_id | INTEGER | — | 关联测评会话 |
| question_data | TEXT | NOT NULL | 题目 JSON |
| user_answer | TEXT | DEFAULT '' | 用户答案 |
| correct_answer | TEXT | DEFAULT '' | 正确答案 |
| error_type | TEXT | DEFAULT '' | 错误类型 |
| knowledge_tag | TEXT | DEFAULT '' | 知识点标签 |
| reviewed | INTEGER | DEFAULT 0 | 0=未复习, 1=已复习 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

> ⚠️ `session_id` 列通过 migration 添加（非原始建表语句）

---

## 5. qa_history — 问答历史

```sql
CREATE TABLE qa_history (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    question          TEXT NOT NULL,
    answer            TEXT NOT NULL,
    question_type     TEXT DEFAULT 'text',
    knowledge_tags    TEXT DEFAULT '',
    explanation_level TEXT DEFAULT 'standard',
    rag_sources_json  TEXT DEFAULT '',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 问答 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| question | TEXT | NOT NULL | 问题 |
| answer | TEXT | NOT NULL | 回答 |
| question_type | TEXT | DEFAULT 'text' | text / code |
| knowledge_tags | TEXT | DEFAULT '' | JSON 知识点列表 |
| explanation_level | TEXT | DEFAULT 'standard' | beginner / standard / advanced |
| rag_sources_json | TEXT | DEFAULT '' | RAG 来源 JSON |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

> ⚠️ `rag_sources_json` 列通过 migration 添加

---

## 6. learning_paths — 学习路径

```sql
CREATE TABLE learning_paths (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    path_data_json  TEXT DEFAULT '{}',
    progress_json   TEXT DEFAULT '{}',
    status          TEXT DEFAULT 'active',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 路径 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| path_data_json | TEXT | DEFAULT '{}' | 路径结构 JSON |
| progress_json | TEXT | DEFAULT '{}' | 进度 JSON |
| status | TEXT | DEFAULT 'active' | active / archived |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

---

## 7. daily_tasks — 每日任务

```sql
CREATE TABLE daily_tasks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    task_data_json  TEXT DEFAULT '{}',
    completed       INTEGER DEFAULT 0,
    date            TEXT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 任务 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| task_data_json | TEXT | DEFAULT '{}' | 任务 JSON |
| completed | INTEGER | DEFAULT 0 | 0=未完成, 1=已完成 |
| date | TEXT | NOT NULL | 日期 (YYYY-MM-DD) |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

---

## 8. learning_records — 学习行为记录

```sql
CREATE TABLE learning_records (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    knowledge_tag     TEXT DEFAULT '',
    action_type       TEXT DEFAULT '',
    duration_seconds  INTEGER DEFAULT 0,
    result_json       TEXT DEFAULT '{}',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 记录 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| knowledge_tag | TEXT | DEFAULT '' | 知识点标签 |
| action_type | TEXT | DEFAULT '' | qa / quiz / quiz_start / review_error |
| duration_seconds | INTEGER | DEFAULT 0 | 持续秒数 |
| result_json | TEXT | DEFAULT '{}' | 结果 JSON |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

---

## 9. user_resources — 资源收藏

```sql
CREATE TABLE user_resources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    resource_id TEXT NOT NULL,
    collected   INTEGER DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 收藏 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| resource_id | TEXT | NOT NULL | 资源 ID |
| collected | INTEGER | DEFAULT 0 | 0=未收藏, 1=已收藏 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

---

## 10. user_llm_config — 用户 LLM 配置

```sql
CREATE TABLE user_llm_config (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER UNIQUE NOT NULL,
    provider          TEXT DEFAULT 'openai',
    api_key           TEXT DEFAULT '',
    base_url          TEXT DEFAULT 'https://api.openai.com',
    model_name        TEXT DEFAULT 'gpt-4o',
    temperature       REAL DEFAULT 0.7,
    max_tokens        INTEGER DEFAULT 4096,
    image_api_key     TEXT DEFAULT '',
    embedding_provider TEXT DEFAULT '',
    embedding_api_key TEXT DEFAULT '',
    embedding_model   TEXT DEFAULT 'text-embedding-v3',
    search_api_key    TEXT DEFAULT '',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 配置 ID |
| user_id | INTEGER | FK→users, UNIQUE, NOT NULL | 用户（一对一） |
| provider | TEXT | DEFAULT 'openai' | LLM 提供商 |
| api_key | TEXT | DEFAULT '' | LLM API Key |
| base_url | TEXT | DEFAULT 'https://api.openai.com' | API 地址 |
| model_name | TEXT | DEFAULT 'gpt-4o' | 模型名 |
| temperature | REAL | DEFAULT 0.7 | 温度参数 |
| max_tokens | INTEGER | DEFAULT 4096 | 最大 token |
| image_api_key | TEXT | DEFAULT '' | 生图 API Key |
| embedding_provider | TEXT | DEFAULT '' | 嵌入提供商 |
| embedding_api_key | TEXT | DEFAULT '' | 嵌入 API Key |
| embedding_model | TEXT | DEFAULT 'text-embedding-v3' | 嵌入模型 |
| search_api_key | TEXT | DEFAULT '' | 搜索 API Key |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

> ⚠️ `image_api_key`, `embedding_*`, `search_api_key` 通过 migration 添加

---

## 11. learning_stats — 每日学习统计

```sql
CREATE TABLE learning_stats (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id               INTEGER NOT NULL,
    date                  TEXT NOT NULL,
    study_duration        INTEGER DEFAULT 0,
    questions_done        INTEGER DEFAULT 0,
    correct_rate          REAL DEFAULT 0,
    knowledge_mastery_json TEXT DEFAULT '{}',
    mastery_detail_json   TEXT DEFAULT '{}',
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, date)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 统计 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| date | TEXT | NOT NULL | 日期 (YYYY-MM-DD) |
| study_duration | INTEGER | DEFAULT 0 | 学习时长(分钟) |
| questions_done | INTEGER | DEFAULT 0 | 做题数 |
| correct_rate | REAL | DEFAULT 0 | 正确率 |
| knowledge_mastery_json | TEXT | DEFAULT '{}' | 知识掌握度 JSON |
| mastery_detail_json | TEXT | DEFAULT '{}' | 掌握度详情 JSON |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**唯一约束**: `UNIQUE(user_id, date)` — 每人每天一条记录

> ⚠️ `mastery_detail_json` 通过 migration 添加

---

## 12. qa_feedback — 问答反馈

```sql
CREATE TABLE qa_feedback (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    qa_history_id   INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    rating          INTEGER NOT NULL,
    feedback_text   TEXT DEFAULT '',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (qa_history_id) REFERENCES qa_history(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 反馈 ID |
| qa_history_id | INTEGER | FK→qa_history, NOT NULL | 问答记录 |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| rating | INTEGER | NOT NULL | 1=👍, -1=👎 |
| feedback_text | TEXT | DEFAULT '' | 反馈文字 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

---

## 13. qa_patterns — 成功模式记忆库

```sql
CREATE TABLE qa_patterns (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text   TEXT NOT NULL,
    answer_text     TEXT NOT NULL,
    knowledge_tags  TEXT DEFAULT '',
    success_count   INTEGER DEFAULT 0,
    usage_count     INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 模式 ID |
| question_text | TEXT | NOT NULL | 问题文本 |
| answer_text | TEXT | NOT NULL | 回答文本 |
| knowledge_tags | TEXT | DEFAULT '' | JSON 知识点 |
| success_count | INTEGER | DEFAULT 0 | 好评数 |
| usage_count | INTEGER | DEFAULT 0 | 被检索次数 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

---

## 14. conversation_sessions — 对话会话

```sql
CREATE TABLE conversation_sessions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    title           TEXT DEFAULT '新对话',
    summary         TEXT DEFAULT '',
    turn_count      INTEGER DEFAULT 0,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 会话 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| title | TEXT | DEFAULT '新对话' | 会话标题 |
| summary | TEXT | DEFAULT '' | 摘要 |
| turn_count | INTEGER | DEFAULT 0 | 对话轮数 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| last_active_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 最后活跃时间 |

**索引**: `idx_conversation_user_active ON (user_id, last_active_at)`

---

## 15. conversation_messages — 对话消息

```sql
CREATE TABLE conversation_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    knowledge_tags  TEXT DEFAULT '[]',
    metadata        TEXT DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES conversation_sessions(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 消息 ID |
| session_id | INTEGER | FK→conversation_sessions, NOT NULL | 所属会话 |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| role | TEXT | NOT NULL | user / assistant |
| content | TEXT | NOT NULL | 消息内容 |
| knowledge_tags | TEXT | DEFAULT '[]' | JSON 知识点 |
| metadata | TEXT | DEFAULT '{}' | JSON 元数据（RAG来源等） |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**索引**: `idx_conversation_messages_session ON (session_id, created_at)`

> ⚠️ `metadata` 列通过 migration 添加

---

## 16. user_memory_facts — 长期记忆

```sql
CREATE TABLE user_memory_facts (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    memory_type       TEXT DEFAULT 'long_term',
    category          TEXT NOT NULL,
    fact_key          TEXT NOT NULL,
    fact_value        TEXT NOT NULL,
    confidence        REAL DEFAULT 0.8,
    mention_count     INTEGER DEFAULT 1,
    access_count      INTEGER DEFAULT 0,
    source_session_id INTEGER,
    embedding_id      TEXT DEFAULT '',
    first_seen_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, category, fact_key),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 记忆 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| memory_type | TEXT | DEFAULT 'long_term' | 记忆类型 |
| category | TEXT | NOT NULL | 分类 (preference / profile / interest / goal) |
| fact_key | TEXT | NOT NULL | 事实键 |
| fact_value | TEXT | NOT NULL | 事实值 |
| confidence | REAL | DEFAULT 0.8 | 置信度 |
| mention_count | INTEGER | DEFAULT 1 | 提及次数 |
| access_count | INTEGER | DEFAULT 0 | 访问次数 |
| source_session_id | INTEGER | — | 来源会话 |
| embedding_id | TEXT | DEFAULT '' | Chroma 向量 ID |
| first_seen_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 首次出现 |
| last_seen_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 最近出现 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**唯一约束**: `UNIQUE(user_id, category, fact_key)`  
**索引**: `idx_memory_user_category ON (user_id, category, mention_count)`

---

## 17. knowledge_mastery — 编程三维掌握度

```sql
CREATE TABLE knowledge_mastery (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           INTEGER NOT NULL,
    knowledge_tag     TEXT NOT NULL,
    source_exercise_id TEXT DEFAULT '',
    mastery_score     REAL DEFAULT 0.5,
    basic_score       REAL DEFAULT 0,
    explanation_score REAL DEFAULT 0,
    transfer_score    REAL DEFAULT 0,
    attempt_count     INTEGER DEFAULT 0,
    incorrect_count   INTEGER DEFAULT 0,
    last_activity_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_review_at    TIMESTAMP,
    next_review_at    TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, knowledge_tag),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 掌握度 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| knowledge_tag | TEXT | NOT NULL | 知识点标签 |
| source_exercise_id | TEXT | DEFAULT '' | 来源习题 |
| mastery_score | REAL | DEFAULT 0.5 | 综合掌握度 (0-1) |
| basic_score | REAL | DEFAULT 0 | 基本测试得分 |
| explanation_score | REAL | DEFAULT 0 | 用户解释得分 |
| transfer_score | REAL | DEFAULT 0 | 变式迁移得分 |
| attempt_count | INTEGER | DEFAULT 0 | 尝试次数 |
| incorrect_count | INTEGER | DEFAULT 0 | 错误次数 |
| last_activity_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 最近活动 |
| last_review_at | TIMESTAMP | — | 最近复习 |
| next_review_at | TIMESTAMP | — | 下次复习 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**唯一约束**: `UNIQUE(user_id, knowledge_tag)`  
**索引**: `idx_mastery_user_due ON (user_id, next_review_at, mastery_score)`

---

## 18. tutorial_documents — 教程文档

```sql
CREATE TABLE tutorial_documents (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    knowledge_tag     TEXT NOT NULL,
    title             TEXT DEFAULT '',
    content           TEXT NOT NULL,
    source_type       TEXT DEFAULT 'seed',
    user_id           INTEGER,
    parent_id         INTEGER,
    curriculum_version TEXT DEFAULT '',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 文档 ID |
| knowledge_tag | TEXT | NOT NULL | 知识点标签 |
| title | TEXT | DEFAULT '' | 标题 |
| content | TEXT | NOT NULL | 内容 |
| source_type | TEXT | DEFAULT 'seed' | seed / user_edit / ai_generated |
| user_id | INTEGER | — (nullable) | 用户（seed=null） |
| parent_id | INTEGER | — | 父文档 ID |
| curriculum_version | TEXT | DEFAULT '' | 课程版本 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**索引**: 
- `idx_tutorial_knowledge ON (knowledge_tag, user_id)`
- `idx_tutorial_user ON (user_id, source_type)`

**种子数据**: 从 `backend/data/tutorial_seed.json` 导入

---

## 19. exercise_test_metadata — 习题评测元数据

```sql
CREATE TABLE exercise_test_metadata (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id       TEXT UNIQUE NOT NULL,
    exercise_type     TEXT DEFAULT 'function',
    target_function   TEXT DEFAULT '',
    locked_code       TEXT DEFAULT '',
    guide_comment     TEXT DEFAULT '# 请在此处实现代码',
    test_cases_json   TEXT DEFAULT '[]',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 元数据 ID |
| exercise_id | TEXT | UNIQUE, NOT NULL | 习题编号 (如 1-1, 1-2) |
| exercise_type | TEXT | DEFAULT 'function' | function / class_method |
| target_function | TEXT | DEFAULT '' | 目标函数名 |
| locked_code | TEXT | DEFAULT '' | 锁定代码（不可编辑部分） |
| guide_comment | TEXT | DEFAULT '# 请在此处实现代码' | 引导注释 |
| test_cases_json | TEXT | DEFAULT '[]' | 测试用例 JSON |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 更新时间 |

**种子数据**: 从 `backend/data/exercises_processed.json` 自动生成

---

## 20. code_submissions — 代码提交记录

```sql
CREATE TABLE code_submissions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    exercise_id     TEXT NOT NULL,
    code            TEXT NOT NULL,
    passed          INTEGER DEFAULT 0,
    total           INTEGER DEFAULT 0,
    score           REAL DEFAULT 0,
    verified        INTEGER DEFAULT 0,
    results_json    TEXT DEFAULT '[]',
    submitted_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 提交 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| exercise_id | TEXT | NOT NULL | 习题编号 |
| code | TEXT | NOT NULL | 提交代码 |
| passed | INTEGER | DEFAULT 0 | 通过测试数 |
| total | INTEGER | DEFAULT 0 | 总测试数 |
| score | REAL | DEFAULT 0 | 得分 |
| verified | INTEGER | DEFAULT 0 | 0=未验证, 1=能力已验证 |
| results_json | TEXT | DEFAULT '[]' | 测试结果 JSON |
| submitted_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 提交时间 |

> ⚠️ `verified` 列通过 migration 添加

---

## 21. capability_sessions — 能力验证会话

```sql
CREATE TABLE capability_sessions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                 INTEGER NOT NULL,
    exercise_id             TEXT NOT NULL,
    exercise_title          TEXT DEFAULT '',
    knowledge_tag           TEXT DEFAULT '',
    status                  TEXT DEFAULT 'coding',
    original_code           TEXT DEFAULT '',
    defense_questions_json  TEXT DEFAULT '[]',
    defense_answers_json    TEXT DEFAULT '[]',
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
    report_json             TEXT DEFAULT '{}',
    started_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    code_passed_at          TIMESTAMP,
    completed_at            TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 会话 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| exercise_id | TEXT | NOT NULL | 习题编号 |
| exercise_title | TEXT | DEFAULT '' | 习题标题 |
| knowledge_tag | TEXT | DEFAULT '' | 知识点 |
| status | TEXT | DEFAULT 'coding' | coding→defense_pending→repair_pending→verified |
| original_code | TEXT | DEFAULT '' | 原始提交代码 |
| defense_questions_json | TEXT | DEFAULT '[]' | 答辩问题 |
| defense_answers_json | TEXT | DEFAULT '[]' | 答辩回答 |
| mutation_code | TEXT | DEFAULT '' | 故障注入代码 |
| mutation_description | TEXT | DEFAULT '' | 故障描述 |
| repair_code | TEXT | DEFAULT '' | 修复代码 |
| repair_explanation | TEXT | DEFAULT '' | 修复解释 |
| ai_usage | TEXT | DEFAULT '未使用' | AI 使用声明 |
| code_score | REAL | DEFAULT 0 | 代码得分 |
| defense_score | REAL | DEFAULT 0 | 答辩得分 |
| repair_score | REAL | DEFAULT 0 | 修复得分 |
| process_score | REAL | DEFAULT 0 | 过程证据得分 |
| total_score | REAL | DEFAULT 0 | 总得分 |
| verified | INTEGER | DEFAULT 0 | 是否已验证 |
| report_json | TEXT | DEFAULT '{}' | 验证报告 |
| started_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 开始时间 |
| code_passed_at | TIMESTAMP | — | 代码通过时间 |
| completed_at | TIMESTAMP | — | 完成时间 |

**索引**: `idx_capability_session_user_exercise ON (user_id, exercise_id, started_at)`

---

## 22. capability_events — 能力验证事件

```sql
CREATE TABLE capability_events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    event_type      TEXT NOT NULL,
    payload_json    TEXT DEFAULT '{}',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES capability_sessions(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 事件 ID |
| session_id | INTEGER | FK→capability_sessions, NOT NULL | 会话 |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| event_type | TEXT | NOT NULL | session_start / edit / submit / code_passed / defense_submit / repair_submit / verified |
| payload_json | TEXT | DEFAULT '{}' | 事件数据 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

**索引**: `idx_capability_events_session ON (session_id, created_at)`

---

## 23. pdf_books — 电子书

```sql
CREATE TABLE pdf_books (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    filename        TEXT NOT NULL,
    original_name   TEXT NOT NULL,
    file_size       INTEGER DEFAULT 0,
    cover           TEXT DEFAULT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 书籍 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| filename | TEXT | NOT NULL | 存储文件名 |
| original_name | TEXT | NOT NULL | 原始文件名 |
| file_size | INTEGER | DEFAULT 0 | 文件大小(字节) |
| cover | TEXT | DEFAULT NULL | 封面路径 |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 创建时间 |

> ⚠️ `cover` 列通过 migration 添加  
> 种子数据: `backend/data/pdf_books_seed.json` (7 本 AI Agent 教材)

---

## 24. rag_documents — RAG 文档追踪

```sql
CREATE TABLE rag_documents (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path     TEXT NOT NULL,
    source_type     TEXT NOT NULL,
    source_title    TEXT DEFAULT '',
    source_module   TEXT DEFAULT '',
    doc_hash        TEXT NOT NULL,
    chunk_count     INTEGER DEFAULT 0,
    char_count      INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending',
    error_msg       TEXT DEFAULT '',
    ingested_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 文档 ID |
| source_path | TEXT | NOT NULL | 源文件路径 |
| source_type | TEXT | NOT NULL | pdf / markdown / qa |
| source_title | TEXT | DEFAULT '' | 标题 |
| source_module | TEXT | DEFAULT '' | 所属模块 |
| doc_hash | TEXT | NOT NULL | 文件哈希 |
| chunk_count | INTEGER | DEFAULT 0 | 分块数 |
| char_count | INTEGER | DEFAULT 0 | 字符数 |
| status | TEXT | DEFAULT 'pending' | pending / ingested / error |
| error_msg | TEXT | DEFAULT '' | 错误信息 |
| ingested_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | 摄入时间 |

**索引**: `idx_rag_source ON (source_path)`, `idx_rag_status ON (status)`

---

## 25. generated_images — AI 生成配图

```sql
CREATE TABLE generated_images (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    prompt_hash     TEXT NOT NULL,
    prompt_text     TEXT NOT NULL,
    svg_content     TEXT,
    file_path       TEXT,
    provider        TEXT DEFAULT 'llm-svg',
    created_at      TEXT
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | INTEGER | PK | 图片 ID |
| user_id | INTEGER | NOT NULL | 用户 |
| prompt_hash | TEXT | NOT NULL | 提示词哈希 |
| prompt_text | TEXT | NOT NULL | 提示词原文 |
| svg_content | TEXT | — | SVG 内容 |
| file_path | TEXT | — | 文件路径 |
| provider | TEXT | DEFAULT 'llm-svg' | bundled / llm-svg |
| created_at | TEXT | — | 创建时间 |

**索引**: `idx_img_h ON (prompt_hash)`

---

## 外键关系图

```
users (1)
 ├── quiz_sessions (N)
 │    └── error_questions (N)
 ├── error_questions (N)
 ├── qa_history (N)
 │    └── qa_feedback (N)
 ├── learning_paths (1 per active)
 ├── daily_tasks (N)
 ├── learning_records (N)
 ├── user_resources (N)
 ├── user_llm_config (1, UNIQUE)
 ├── learning_stats (N, UNIQUE per day)
 ├── conversation_sessions (N)
 │    └── conversation_messages (N)
 ├── user_memory_facts (N, UNIQUE per category+key)
 ├── knowledge_mastery (N, UNIQUE per tag)
 ├── tutorial_documents (nullable FK)
 ├── code_submissions (N)
 ├── capability_sessions (N)
 │    └── capability_events (N)
 └── pdf_books (N)

独立表（无 FK）:
 - knowledge_tags
 - qa_patterns
 - exercise_test_metadata
 - rag_documents
 - generated_images
```

---

## SQLite → PostgreSQL 迁移关键差异

| SQLite | PostgreSQL |
|--------|------------|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` 或 `INTEGER GENERATED ALWAYS AS IDENTITY` |
| `TEXT DEFAULT ''` | `TEXT DEFAULT ''` (相同) |
| `REAL` | `REAL` 或 `DOUBLE PRECISION` |
| `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` | `TIMESTAMP DEFAULT CURRENT_TIMESTAMP` (相同) |
| `date('now')` | `CURRENT_DATE` |
| `datetime('now')` | `CURRENT_TIMESTAMP` 或 `NOW()` |
| `?` 占位符 | `%s` (psycopg2) 或 `$1, $2, ...` (asyncpg) |
| `last_insert_rowid()` | `RETURNING id` 子句 |
| 无 SCHEMA | 默认 `public` schema |
| 无连接池 | 建议使用连接池 (PgBouncer / psycopg2 pool) |
