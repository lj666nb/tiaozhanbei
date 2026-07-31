# AI智能体学科学习平台 — 统一 PostgreSQL 数据库表结构文档

> 合并来源：助学系统（25 张表）+ 助教系统 Edu-TA（12 张表）  
> 数据库：PostgreSQL  
> 生成日期：2026-07-23  
> 总计：**37 张业务表**  
> DDL 脚本：[merged_schema.sql](merged_schema.sql)

---

## 合并概览

```
助学系统 (25 张)  ──┐
                    ├── 统一 PostgreSQL (37 张) ── 供两个项目分别使用
助教系统 (12 张)  ──┘
```

| 模块 | 表数 | 来源 | 主键风格 |
|------|:---:|------|:---:|
| 用户与认证 | 1 | 合并 | SERIAL |
| 学习路径与任务 | 3 | 助学 | SERIAL |
| 测评与诊断 | 2 | 助学 | SERIAL |
| 问答与对话 | 5 | 助学 | SERIAL |
| 长期记忆与掌握度 | 2 | 助学 | SERIAL |
| 编程实验室 | 4 | 助学 | SERIAL |
| 资源与 RAG | 6 | 助学 | SERIAL |
| 智能备课 | 3 | 助教 | UUID |
| 作业批改 | 1 | 助教 | UUID |
| 教学资料与题库 | 3 | 助教 | UUID |
| 学情分析 | 1 | 助教 | UUID |
| 教学辅助 | 1 | 助教 | UUID |
| LLM 日志 | 1 | 助教 | SERIAL |
| Agent 工作流 | 1 | 助教 | UUID |
| 教案审计 | 2 | 助教 | SERIAL |
| 项目互通 | 1 | 助教 | TEXT |

---

## 合并关键变更

### users 表统一

助学和助教原本各有各的用户概念。合并后统一为一张 `users` 表，通过 `role` 字段区分：

| role | 说明 | 可见字段 |
|------|------|----------|
| `student` | 学生（助学用户） | 全字段可用 |
| `teacher` | 教师（助教用户） | `title`/`department`/`school` 可用，学习相关字段忽略 |
| `admin` | 管理员 | 全字段可用 |

### 助教表增加 user_id

所有助教业务表现在直连 `users` 表：

| 助教表 | 新增字段 | 关联含义 |
|--------|----------|----------|
| `lesson_plans` | `user_id` | 创建教案的教师 |
| `homework_grades` | `user_id` | 学生 |
| `exercise_batches` | `user_id` | 出题教师 |
| `materials` | `user_id` | 上传者 |
| `questions` | `user_id` | 出题人 |
| `insight_reports` | `user_id` | 学生（替代原 `student_id TEXT`） |
| `teaching_aux` | `user_id` | 创建教师 |
| `llm_call_logs` | `user_id` | 调用用户 |
| `agent_workflows` | `user_id` | 发起人 |

### 互通兼容

保留 4 张表的 `project_id` 字段和 `project_registry` 表，确保现有助教系统代码平滑迁移：

- `homework_grades.project_id`
- `insight_reports.project_id`
- `materials.project_id`
- `teaching_aux.project_id`

### 类型升级

| SQLite | PostgreSQL | 说明 |
|--------|-----------|------|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` | 自增主键 |
| `TEXT` (UUID) | `UUID DEFAULT gen_random_uuid()` | UUID 主键 |
| `TEXT` (JSON) | `JSONB` | JSON 字段，支持索引和查询 |
| `TIMESTAMP` | `TIMESTAMPTZ` | 带时区时间戳 |
| `BOOLEAN` (0/1) | `BOOLEAN` | 真布尔类型 |
| `TEXT` (日期) | `DATE` | 纯日期类型 |

---

## 表一览

### 一、用户与认证（1 张）

| # | 表名 | 用途 | 主键 | 关键外键 |
|:--:|------|------|:--:|------|
| 1 | `users` | 统一用户（学生+教师+管理员） | SERIAL | — |

### 二、助学 — 学习路径与任务（3 张）

| # | 表名 | 用途 | 主键 | 关键外键 |
|:--:|------|------|:--:|------|
| 2 | `knowledge_tags` | 知识点标签库 | SERIAL | `parent_id` 自引用 |
| 3 | `learning_paths` | 学习路径 | SERIAL | `user_id` → users |
| 4 | `daily_tasks` | 每日任务 | SERIAL | `user_id` → users |

### 三、助学 — 测评与诊断（2 张）

| # | 表名 | 用途 | 主键 | 关键外键 |
|:--:|------|------|:--:|------|
| 5 | `quiz_sessions` | 测评会话 | SERIAL | `user_id` → users |
| 6 | `error_questions` | 错题本 | SERIAL | `user_id` → users |

### 四、助学 — 问答与对话（5 张）

| # | 表名 | 用途 | 主键 | 关键外键 |
|:--:|------|------|:--:|------|
| 7 | `qa_history` | 问答历史 | SERIAL | `user_id` → users |
| 8 | `qa_feedback` | 问答反馈（👍👎） | SERIAL | `qa_history_id` → qa_history, `user_id` → users |
| 9 | `qa_patterns` | 成功模式记忆库 | SERIAL | — |
| 10 | `conversation_sessions` | 对话会话 | SERIAL | `user_id` → users |
| 11 | `conversation_messages` | 对话消息 | SERIAL | `session_id` → conversation_sessions, `user_id` → users |

### 五、助学 — 长期记忆与掌握度（2 张）

| # | 表名 | 用途 | 主键 | 关键外键 |
|:--:|------|------|:--:|------|
| 12 | `user_memory_facts` | 长期记忆 | SERIAL | `user_id` → users, UNIQUE(user_id, category, fact_key) |
| 13 | `knowledge_mastery` | 编程三维掌握度 | SERIAL | `user_id` → users, UNIQUE(user_id, knowledge_tag) |

### 六、助学 — 编程实验室（4 张）

| # | 表名 | 用途 | 主键 | 关键外键 |
|:--:|------|------|:--:|------|
| 14 | `tutorial_documents` | 教程文档 | SERIAL | `user_id` → users (nullable) |
| 15 | `exercise_test_metadata` | 习题评测元数据 | SERIAL | UNIQUE(exercise_id) |
| 16 | `code_submissions` | 代码提交记录 | SERIAL | `user_id` → users |
| 17 | `capability_sessions` | 能力验证会话 | SERIAL | `user_id` → users |
| 18 | `capability_events` | 能力验证事件 | SERIAL | `session_id` → capability_sessions, `user_id` → users |

### 七、助学 — 资源与 RAG（6 张）

| # | 表名 | 用途 | 主键 | 关键外键 |
|:--:|------|------|:--:|------|
| 19 | `user_resources` | 资源收藏 | SERIAL | `user_id` → users |
| 20 | `user_llm_config` | 用户 LLM/API 配置 | SERIAL | `user_id` → users (UNIQUE) |
| 21 | `learning_stats` | 每日学习统计 | SERIAL | `user_id` → users, UNIQUE(user_id, date) |
| 22 | `pdf_books` | 电子书 | SERIAL | `user_id` → users |
| 23 | `rag_documents` | RAG 文档追踪 | SERIAL | — |
| 24 | `generated_images` | AI 生成配图 | SERIAL | — |

### 八、助教 — 智能备课（3 张）

| # | 表名 | 用途 | 主键 | 关键外键 |
|:--:|------|------|:--:|------|
| 25 | `lesson_plans` | 教案 | UUID | `user_id` → users |
| 26 | `audit_logs` | 教案操作审计日志 | SERIAL | `plan_id` → lesson_plans |
| 27 | `plan_snapshots` | 教案版本快照 | SERIAL | `plan_id` → lesson_plans |

### 九、助教 — 作业批改（1 张）

| # | 表名 | 用途 | 主键 | 关键外键 |
|:--:|------|------|:--:|------|
| 28 | `homework_grades` | 作业批改结果 | UUID | `user_id` → users |

### 十、助教 — 教学资料与题库（3 张）

| # | 表名 | 用途 | 主键 | 关键外键 |
|:--:|------|------|:--:|------|
| 29 | `materials` | 教学资料 | UUID | `user_id` → users |
| 30 | `exercise_batches` | AI 出题批次 | UUID | `user_id` → users |
| 31 | `questions` | AI 生成题目 | UUID | `batch_id` → exercise_batches, `user_id` → users |

### 十一、助教 — 学情分析与辅助（2 张）

| # | 表名 | 用途 | 主键 | 关键外键 |
|:--:|------|------|:--:|------|
| 32 | `insight_reports` | 学情分析报告 | UUID | `user_id` → users |
| 33 | `teaching_aux` | 教学辅助素材 | UUID | `user_id` → users |

### 十二、助教 — 基础服务（3 张）

| # | 表名 | 用途 | 主键 | 关键外键 |
|:--:|------|------|:--:|------|
| 34 | `llm_call_logs` | LLM 用量统计 | SERIAL | `user_id` → users |
| 35 | `agent_workflows` | Agent 编排工作流 | UUID | `user_id` → users |
| 36 | `project_registry` | 项目注册表 | TEXT | — |

---

## 自定义类型（ENUM）

| 类型名 | 值 | 用途 |
|--------|-----|------|
| `user_role` | `student`, `teacher`, `admin` | 用户角色 |
| `learning_stage` | `入门`, `进阶`, `高阶` | 学习阶段 |
| `explanation_level` | `beginner`, `standard`, `advanced` | 解答详细程度 |
| `tutorial_source_type` | `seed`, `user_modified`, `ai_generated` | 教程来源 |
| `audit_operation` | `create`, `view`, `edit`, `export`, `delete`, `restore` | 教案操作 |
| `workflow_status` | `pending`, `running`, `completed`, `failed` | 工作流状态 |
| `question_status` | `draft`, `published` | 题目发布状态 |

---

## 互通相关字段

以下 5 张表带有 `project_id` 字段，用于区分数据来源：

| 表 | 互通数据 | project_id 可选值 |
|------|------|------|
| `homework_grades` | 作业成绩 | `ta-project` / `student-project` |
| `insight_reports` | 学情分析 | `ta-project` / `student-project` |
| `materials` | 教学资料 | `ta-project` / `student-project` |
| `teaching_aux` | 教学辅助素材 | `ta-project` / `student-project` |
| `project_registry` | 项目注册 | 主键，定义所有合法 project_id |

---

## 详细表结构

### 1. users — 统一用户表

```sql
CREATE TABLE users (
    id                      SERIAL PRIMARY KEY,
    username                TEXT NOT NULL UNIQUE,
    password_hash           TEXT NOT NULL,              -- bcrypt 哈希
    nickname                TEXT DEFAULT '',
    role                    user_role DEFAULT 'student',
    title                   TEXT DEFAULT '',            -- 职称（教师）
    department              TEXT DEFAULT '',            -- 院系（教师）
    school                  TEXT DEFAULT '',            -- 学校
    grade                   TEXT DEFAULT '',            -- 年级（学生）
    learning_stage          learning_stage DEFAULT '入门',
    learning_goal           TEXT DEFAULT '',
    avatar                  TEXT DEFAULT '',
    programming_background  TEXT DEFAULT '',
    years_experience        INTEGER DEFAULT 0,
    answer_preference       TEXT DEFAULT '分步清晰',
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);
```

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 用户 ID |
| username | TEXT | UNIQUE, NOT NULL | 登录用户名 |
| password_hash | TEXT | NOT NULL | bcrypt 哈希密码 |
| nickname | TEXT | DEFAULT '' | 昵称 |
| **role** | user_role | DEFAULT 'student' | 新增：student / teacher / admin |
| **title** | TEXT | DEFAULT '' | 新增：职称 |
| **department** | TEXT | DEFAULT '' | 新增：所属院系 |
| **school** | TEXT | DEFAULT '' | 新增：所属学校 |
| grade | TEXT | DEFAULT '' | 身份/年级 |
| learning_stage | learning_stage | DEFAULT '入门' | 学习阶段 |
| learning_goal | TEXT | DEFAULT '' | 学习目标 |
| avatar | TEXT | DEFAULT '' | 头像 |
| programming_background | TEXT | DEFAULT '' | 编程背景 |
| years_experience | INTEGER | DEFAULT 0 | 从业年限 |
| answer_preference | TEXT | DEFAULT '分步清晰' | 回答偏好 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**种子数据**:
- `demo` / `demo123` — role=student, nickname=Demo学员
- `teacher_demo` / `demo123` — role=teacher, nickname=Demo教师

---

### 2. knowledge_tags — 知识点标签库

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 标签 ID |
| name | TEXT | NOT NULL | 标签名 |
| category | TEXT | NOT NULL | 所属分类 |
| description | TEXT | DEFAULT '' | 描述 |
| parent_id | INTEGER | DEFAULT 0 | 父标签 ID（0=顶级） |

### 3. learning_paths — 学习路径

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 路径 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| path_data_json | JSONB | DEFAULT '{}' | 路径结构 |
| progress_json | JSONB | DEFAULT '{}' | 进度 |
| status | TEXT | DEFAULT 'active' | active / archived |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

### 4. daily_tasks — 每日任务

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 任务 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| task_data_json | JSONB | DEFAULT '{}' | 任务 JSON |
| completed | INTEGER | DEFAULT 0 | 0=未完成, 1=已完成 |
| date | DATE | NOT NULL | 日期 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**: `(user_id, date)`

### 5. quiz_sessions — 测评会话

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 会话 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| stage | TEXT | DEFAULT '入门' | 测评阶段 |
| questions_json | JSONB | DEFAULT '[]' | 题目 |
| answers_json | JSONB | DEFAULT '[]' | 作答 |
| score | REAL | DEFAULT 0 | 得分 |
| total | INTEGER | DEFAULT 0 | 总题数 |
| report_json | JSONB | DEFAULT '{}' | 诊断报告 |
| status | TEXT | DEFAULT 'pending' | pending / completed |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| completed_at | TIMESTAMPTZ | — | 完成时间 |

### 6. error_questions — 错题本

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 错题 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| session_id | INTEGER | — | 关联测评会话 |
| question_data | JSONB | NOT NULL | 题目 JSON |
| user_answer | TEXT | DEFAULT '' | 用户答案 |
| correct_answer | TEXT | DEFAULT '' | 正确答案 |
| error_type | TEXT | DEFAULT '' | 错误类型 |
| knowledge_tag | TEXT | DEFAULT '' | 知识点标签 |
| reviewed | INTEGER | DEFAULT 0 | 0=未复习, 1=已复习 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

### 7. qa_history — 问答历史

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 问答 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| question | TEXT | NOT NULL | 问题 |
| answer | TEXT | NOT NULL | 回答 |
| question_type | TEXT | DEFAULT 'text' | text / code |
| knowledge_tags | JSONB | DEFAULT '[]' | 知识点列表 |
| explanation_level | explanation_level | DEFAULT 'standard' | 详细程度 |
| rag_sources_json | JSONB | DEFAULT '[]' | RAG 来源 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

### 8. qa_feedback — 问答反馈

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 反馈 ID |
| qa_history_id | INTEGER | FK→qa_history, NOT NULL | 问答记录 |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| rating | INTEGER | NOT NULL | 1=👍, -1=👎 |
| feedback_text | TEXT | DEFAULT '' | 反馈文字 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

### 9. qa_patterns — 成功模式记忆库

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 模式 ID |
| question_text | TEXT | NOT NULL | 问题文本 |
| answer_text | TEXT | NOT NULL | 回答文本 |
| knowledge_tags | JSONB | DEFAULT '[]' | 知识点 |
| success_count | INTEGER | DEFAULT 0 | 好评数 |
| usage_count | INTEGER | DEFAULT 0 | 被检索次数 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

### 10. conversation_sessions — 对话会话

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 会话 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| title | TEXT | DEFAULT '新对话' | 会话标题 |
| summary | TEXT | DEFAULT '' | 摘要 |
| turn_count | INTEGER | DEFAULT 0 | 对话轮数 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| last_active_at | TIMESTAMPTZ | DEFAULT NOW() | 最后活跃时间 |

**索引**: `(user_id, last_active_at)`

### 11. conversation_messages — 对话消息

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 消息 ID |
| session_id | INTEGER | FK→conversation_sessions, NOT NULL | 所属会话 |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| role | TEXT | NOT NULL | user / assistant |
| content | TEXT | NOT NULL | 消息内容 |
| knowledge_tags | JSONB | DEFAULT '[]' | 知识点 |
| metadata | JSONB | DEFAULT '{}' | 元数据（RAG来源等） |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**: `(session_id, created_at)`

### 12. user_memory_facts — 长期记忆

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 记忆 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| memory_type | TEXT | DEFAULT 'long_term' | 记忆类型 |
| category | TEXT | NOT NULL | preference / profile / interest / goal |
| fact_key | TEXT | NOT NULL | 事实键 |
| fact_value | TEXT | NOT NULL | 事实值 |
| confidence | REAL | DEFAULT 0.8 | 置信度 |
| mention_count | INTEGER | DEFAULT 1 | 提及次数 |
| access_count | INTEGER | DEFAULT 0 | 访问次数 |
| source_session_id | INTEGER | — | 来源会话 |
| embedding_id | TEXT | DEFAULT '' | Chroma 向量 ID |
| first_seen_at | TIMESTAMPTZ | DEFAULT NOW() | 首次出现 |
| last_seen_at | TIMESTAMPTZ | DEFAULT NOW() | 最近出现 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**UNIQUE**: `(user_id, category, fact_key)`  
**索引**: `(user_id, category, mention_count)`

### 13. knowledge_mastery — 编程三维掌握度

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 掌握度 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| knowledge_tag | TEXT | NOT NULL | 知识点 |
| source_exercise_id | TEXT | DEFAULT '' | 来源习题 |
| mastery_score | REAL | DEFAULT 0.5 | 综合掌握度 (0-1) |
| basic_score | REAL | DEFAULT 0 | 基本测试得分 |
| explanation_score | REAL | DEFAULT 0 | 用户解释得分 |
| transfer_score | REAL | DEFAULT 0 | 变式迁移得分 |
| attempt_count | INTEGER | DEFAULT 0 | 尝试次数 |
| incorrect_count | INTEGER | DEFAULT 0 | 错误次数 |
| last_activity_at | TIMESTAMPTZ | DEFAULT NOW() | 最近活动 |
| last_review_at | TIMESTAMPTZ | — | 最近复习 |
| next_review_at | TIMESTAMPTZ | — | 下次复习 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**UNIQUE**: `(user_id, knowledge_tag)`  
**索引**: `(user_id, next_review_at, mastery_score)`

### 14. tutorial_documents — 教程文档

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 文档 ID |
| knowledge_tag | TEXT | NOT NULL | 知识点标签 |
| title | TEXT | DEFAULT '' | 标题 |
| content | TEXT | NOT NULL | 内容 |
| source_type | tutorial_source_type | DEFAULT 'seed' | 来源类型 |
| user_id | INTEGER | FK→users (nullable) | 用户（NULL=种子数据） |
| parent_id | INTEGER | — | 父文档 ID |
| curriculum_version | TEXT | DEFAULT '' | 课程版本 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**索引**: `(knowledge_tag, user_id)`, `(user_id, source_type)`

### 15. exercise_test_metadata — 习题评测元数据

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 元数据 ID |
| exercise_id | TEXT | UNIQUE, NOT NULL | 习题编号 |
| exercise_type | TEXT | DEFAULT 'function' | function / class_method |
| target_function | TEXT | DEFAULT '' | 目标函数名 |
| locked_code | TEXT | DEFAULT '' | 锁定代码 |
| guide_comment | TEXT | DEFAULT '# 请在此处实现代码' | 引导注释 |
| test_cases_json | JSONB | DEFAULT '[]' | 测试用例 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

### 16. code_submissions — 代码提交记录

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 提交 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| exercise_id | TEXT | NOT NULL | 习题编号 |
| code | TEXT | NOT NULL | 提交代码 |
| passed | INTEGER | DEFAULT 0 | 通过测试数 |
| total | INTEGER | DEFAULT 0 | 总测试数 |
| score | REAL | DEFAULT 0 | 得分 |
| verified | INTEGER | DEFAULT 0 | 0=未验证, 1=已验证 |
| results_json | JSONB | DEFAULT '[]' | 测试结果 |
| submitted_at | TIMESTAMPTZ | DEFAULT NOW() | 提交时间 |

**索引**: `(user_id, exercise_id)`

### 17. capability_sessions — 能力验证会话

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 会话 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| exercise_id | TEXT | NOT NULL | 习题编号 |
| exercise_title | TEXT | DEFAULT '' | 习题标题 |
| knowledge_tag | TEXT | DEFAULT '' | 知识点 |
| status | TEXT | DEFAULT 'coding' | coding→defense_pending→repair_pending→verified |
| original_code | TEXT | DEFAULT '' | 原始提交代码 |
| defense_questions_json | JSONB | DEFAULT '[]' | 答辩问题 |
| defense_answers_json | JSONB | DEFAULT '[]' | 答辩回答 |
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
| report_json | JSONB | DEFAULT '{}' | 验证报告 |
| started_at | TIMESTAMPTZ | DEFAULT NOW() | 开始时间 |
| code_passed_at | TIMESTAMPTZ | — | 代码通过时间 |
| completed_at | TIMESTAMPTZ | — | 完成时间 |

**索引**: `(user_id, exercise_id, started_at)`

### 18. capability_events — 能力验证事件

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 事件 ID |
| session_id | INTEGER | FK→capability_sessions, NOT NULL | 会话 |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| event_type | TEXT | NOT NULL | 事件类型 |
| payload_json | JSONB | DEFAULT '{}' | 事件数据 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**: `(session_id, created_at)`

### 19. user_resources — 资源收藏

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 收藏 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| resource_id | TEXT | NOT NULL | 资源 ID |
| collected | INTEGER | DEFAULT 0 | 0=未收藏, 1=已收藏 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

### 20. user_llm_config — 用户 LLM 配置

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 配置 ID |
| user_id | INTEGER | FK→users, UNIQUE, NOT NULL | 用户（一对一） |
| provider | TEXT | DEFAULT 'openai' | LLM 提供商 |
| api_key | TEXT | DEFAULT '' | API Key |
| base_url | TEXT | DEFAULT 'https://api.openai.com' | API 地址 |
| model_name | TEXT | DEFAULT 'gpt-4o' | 模型名 |
| temperature | REAL | DEFAULT 0.7 | 温度 |
| max_tokens | INTEGER | DEFAULT 4096 | 最大 token |
| image_api_key | TEXT | DEFAULT '' | 生图 API Key |
| embedding_provider | TEXT | DEFAULT '' | 嵌入提供商 |
| embedding_api_key | TEXT | DEFAULT '' | 嵌入 API Key |
| embedding_model | TEXT | DEFAULT 'text-embedding-v3' | 嵌入模型 |
| search_api_key | TEXT | DEFAULT '' | 搜索 API Key |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

### 21. learning_stats — 每日学习统计

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 统计 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| date | DATE | NOT NULL | 日期 |
| study_duration | INTEGER | DEFAULT 0 | 学习时长(分钟) |
| questions_done | INTEGER | DEFAULT 0 | 做题数 |
| correct_rate | REAL | DEFAULT 0 | 正确率 |
| knowledge_mastery_json | JSONB | DEFAULT '{}' | 知识掌握度 |
| mastery_detail_json | JSONB | DEFAULT '{}' | 掌握度详情 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**UNIQUE**: `(user_id, date)`

### 22. pdf_books — 电子书

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 书籍 ID |
| user_id | INTEGER | FK→users, NOT NULL | 用户 |
| filename | TEXT | NOT NULL | 存储文件名 |
| original_name | TEXT | NOT NULL | 原始文件名 |
| file_size | INTEGER | DEFAULT 0 | 文件大小(字节) |
| cover | TEXT | DEFAULT NULL | 封面路径 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

### 23. rag_documents — RAG 文档追踪

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 文档 ID |
| source_path | TEXT | NOT NULL | 源文件路径 |
| source_type | TEXT | NOT NULL | pdf / markdown / qa |
| source_title | TEXT | DEFAULT '' | 标题 |
| source_module | TEXT | DEFAULT '' | 所属模块 |
| doc_hash | TEXT | NOT NULL | 文件哈希 |
| chunk_count | INTEGER | DEFAULT 0 | 分块数 |
| char_count | INTEGER | DEFAULT 0 | 字符数 |
| status | TEXT | DEFAULT 'pending' | pending / ingested / error |
| error_msg | TEXT | DEFAULT '' | 错误信息 |
| ingested_at | TIMESTAMPTZ | DEFAULT NOW() | 摄入时间 |

**索引**: `(source_path)`, `(status)`

### 24. generated_images — AI 生成配图

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 图片 ID |
| user_id | INTEGER | NOT NULL | 用户 |
| prompt_hash | TEXT | NOT NULL | 提示词哈希 |
| prompt_text | TEXT | NOT NULL | 提示词原文 |
| svg_content | TEXT | — | SVG 内容 |
| file_path | TEXT | — | 文件路径 |
| provider | TEXT | DEFAULT 'llm-svg' | bundled / llm-svg |
| created_at | TEXT | — | 创建时间 |

**索引**: `(prompt_hash)`

---

### 25. lesson_plans — 教案

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 教案 ID |
| **user_id** | INTEGER | FK→users, NOT NULL | **新增**：创建教案的教师 |
| course_name | TEXT | NOT NULL | 课程名称 |
| chapter | TEXT | DEFAULT '' | 章节名称 |
| total_hours | INTEGER | DEFAULT 2 | 课时数 |
| additional_requirements | TEXT | DEFAULT '' | 附加要求 |
| plan_data | JSONB | NOT NULL | 完整教案 JSON（目标/活动/作业/板书/评价量规） |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**索引**: `(course_name)`, `(user_id)`

### 26. audit_logs — 教案操作审计日志

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 审计 ID |
| plan_id | UUID | FK→lesson_plans, NOT NULL | 教案 ID |
| plan_name | TEXT | DEFAULT '' | 教案名称（冗余） |
| course_name | TEXT | DEFAULT '' | 课程名称 |
| chapter | TEXT | DEFAULT '' | 章节 |
| operation | audit_operation | NOT NULL | 操作类型 |
| operator | TEXT | DEFAULT '系统' | 操作人 |
| operator_role | TEXT | DEFAULT '' | 角色 |
| session_index | INTEGER | — | 流程索引（null=全教案） |
| changes_before | JSONB | — | 修改前快照 |
| changes_after | JSONB | — | 修改后快照 |
| detail | TEXT | DEFAULT '' | 操作描述 |
| ip_address | TEXT | DEFAULT '' | 操作 IP |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 操作时间 |

**索引**: `(plan_id)`, `(created_at)`

### 27. plan_snapshots — 教案版本快照

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 快照 ID |
| plan_id | UUID | FK→lesson_plans, NOT NULL | 教案 ID |
| version | INTEGER | NOT NULL | 版本号 |
| plan_data | JSONB | NOT NULL | 完整教案 JSON |
| created_by | TEXT | DEFAULT '系统' | 创建人 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**: `(plan_id)`

### 28. homework_grades — 作业批改结果

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 批改 ID |
| **user_id** | INTEGER | FK→users, NOT NULL | **新增**：学生 |
| student_name | TEXT | DEFAULT '' | 学生姓名（冗余） |
| course_name | TEXT | NOT NULL | 课程名称 |
| chapter | TEXT | DEFAULT '' | 所属章节 |
| question_text | TEXT | DEFAULT '' | 题目内容 |
| student_answer | TEXT | DEFAULT '' | 学生答案 |
| question_type | TEXT | DEFAULT '' | 题型 |
| max_score | REAL | DEFAULT 100 | 满分 |
| score | REAL | DEFAULT 0 | 得分 |
| percentage | REAL | DEFAULT 0 | 得分百分比 |
| feedback | TEXT | DEFAULT '' | 综合评语 |
| strengths | JSONB | DEFAULT '[]' | 优点列表 |
| weaknesses | JSONB | DEFAULT '[]' | 不足与错误 |
| suggestions | JSONB | DEFAULT '[]' | 改进建议 |
| knowledge_points | JSONB | DEFAULT '[]' | 涉及知识点 |
| detailed_analysis | TEXT | DEFAULT '' | 详细分析 |
| source_file | TEXT | DEFAULT '' | 来源文件名 |
| batch_id | TEXT | DEFAULT '' | 批次标识 |
| is_archived | BOOLEAN | DEFAULT FALSE | 是否已归档 |
| project_id | TEXT | DEFAULT 'ta-project' | 数据来源 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**: `(course_name)`, `(user_id)`, `(project_id)`

### 29. materials — 教学资料

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 资料 ID |
| **user_id** | INTEGER | FK→users, NOT NULL | **新增**：上传者 |
| filename | TEXT | NOT NULL | 文件名 |
| course | TEXT | DEFAULT '未分类' | 所属课程 |
| chapter | TEXT | DEFAULT '' | 所属章节 |
| size_bytes | INTEGER | DEFAULT 0 | 文件大小(字节) |
| size_display | TEXT | DEFAULT '' | 可读大小 |
| pages | INTEGER | DEFAULT 0 | 页数 |
| text_preview | TEXT | DEFAULT '' | 文本预览 |
| text_content | TEXT | DEFAULT '' | 全文内容 |
| file_path | TEXT | DEFAULT '' | 文件存储路径 |
| project_id | TEXT | DEFAULT 'ta-project' | 数据来源 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**: `(course)`, `(user_id)`, `(project_id)`

### 30. exercise_batches — AI 出题批次

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 批次 ID |
| **user_id** | INTEGER | FK→users, NOT NULL | **新增**：出题教师 |
| course_name | TEXT | NOT NULL | 课程名称 |
| chapter | TEXT | DEFAULT '' | 章节 |
| difficulty | TEXT | DEFAULT '中等' | 难度 |
| total | INTEGER | DEFAULT 0 | 题目总数 |
| exercises_json | JSONB | DEFAULT '[]' | 完整题目列表 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**: `(course_name)`, `(user_id)`

### 31. questions — AI 生成题目

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 题目 ID |
| **user_id** | INTEGER | FK→users, NOT NULL | **新增**：出题人 |
| batch_id | UUID | FK→exercise_batches | 所属批次 |
| course | TEXT | DEFAULT '' | 课程名称 |
| question | TEXT | NOT NULL | 题目内容 |
| type | TEXT | DEFAULT '' | 题型 |
| options | JSONB | DEFAULT '[]' | 选择题选项 |
| answer | TEXT | DEFAULT '' | 参考答案 |
| difficulty | TEXT | DEFAULT '' | 难度 |
| knowledge_point | TEXT | DEFAULT '' | 知识点 |
| explanation | TEXT | DEFAULT '' | 详细解析 |
| estimated_time | INTEGER | DEFAULT 0 | 预计完成时间(分钟) |
| status | question_status | DEFAULT 'draft' | 状态 |
| scoring_rubric | TEXT | DEFAULT '' | 评分标准 |
| common_mistakes | TEXT | DEFAULT '' | 常见错误 |
| cognitive_level | TEXT | DEFAULT '' | 认知层次 |
| source | TEXT | DEFAULT '' | 来源 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**: `(batch_id)`, `(user_id)`

### 32. insight_reports — 学情分析报告

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 报告 ID |
| **user_id** | INTEGER | FK→users, NOT NULL | **新增**：学生（替代原 student_id TEXT） |
| course_name | TEXT | DEFAULT '' | 课程名称 |
| report_type | TEXT | DEFAULT 'individual' | individual / class |
| report_json | JSONB | NOT NULL | 完整报告 |
| project_id | TEXT | DEFAULT 'ta-project' | 数据来源 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**: `(user_id)`, `(project_id)`

### 33. teaching_aux — 教学辅助素材

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 素材 ID |
| **user_id** | INTEGER | FK→users, NOT NULL | **新增**：创建教师 |
| course | TEXT | DEFAULT '' | 课程名称 |
| chapter | TEXT | DEFAULT '' | 章节 |
| aux_type | TEXT | DEFAULT '' | 类型：difficulty/classroom/ppt/variant |
| content_json | JSONB | DEFAULT '{}' | 内容 JSON |
| project_id | TEXT | DEFAULT 'ta-project' | 数据来源 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**: `(course)`, `(user_id)`, `(project_id)`

### 34. llm_call_logs — LLM 用量统计

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | SERIAL | PK | 日志 ID |
| **user_id** | INTEGER | FK→users | **新增**：调用用户 |
| model | VARCHAR(100) | — | 模型名称 |
| function_name | VARCHAR(100) | — | 调用功能 |
| prompt_tokens | INTEGER | DEFAULT 0 | 输入 token |
| completion_tokens | INTEGER | DEFAULT 0 | 输出 token |
| total_tokens | INTEGER | DEFAULT 0 | 总 token |
| latency_ms | INTEGER | DEFAULT 0 | 延迟(毫秒) |
| success | INTEGER | DEFAULT 1 | 1=成功, 0=失败 |
| error_message | TEXT | DEFAULT '' | 错误信息 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**: `(function_name)`, `(user_id)`

### 35. agent_workflows — Agent 编排工作流

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 工作流 ID |
| **user_id** | INTEGER | FK→users | **新增**：发起人 |
| type | TEXT | NOT NULL | 工作流类型 |
| status | workflow_status | DEFAULT 'pending' | 状态 |
| input_params | JSONB | DEFAULT '{}' | 输入参数 |
| steps | JSONB | DEFAULT '[]' | 执行步骤列表 |
| final_output | JSONB | — | 最终输出 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| completed_at | TIMESTAMPTZ | — | 完成时间 |

**索引**: `(type)`, `(status)`, `(user_id)`

### 36. project_registry — 项目注册表

| 列 | 类型 | 约束 | 说明 |
|----|------|------|------|
| id | TEXT | PK | "ta-project" / "student-project" |
| name | TEXT | NOT NULL | "助教系统" / "助学系统" |
| token_hash | TEXT | NOT NULL | SHA256 哈希的认证令牌 |
| is_active | BOOLEAN | DEFAULT TRUE | 是否启用 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 注册时间 |

---

## 外键关系图

```
users (1) ─────────────────────────────────────────────────────────────────
 ├── 助学侧 ───────────────────────────────────────────────────────────────
 │    ├── quiz_sessions (N)
 │    │    └── error_questions (N)
 │    ├── error_questions (N)
 │    ├── qa_history (N)
 │    │    └── qa_feedback (N)
 │    ├── learning_paths (N)
 │    ├── daily_tasks (N)
 │    ├── learning_records (N)
 │    ├── user_resources (N)
 │    ├── user_llm_config (1, UNIQUE)
 │    ├── learning_stats (N, UNIQUE per day)
 │    ├── conversation_sessions (N)
 │    │    └── conversation_messages (N)
 │    ├── user_memory_facts (N, UNIQUE per category+key)
 │    ├── knowledge_mastery (N, UNIQUE per tag)
 │    ├── tutorial_documents (nullable FK)
 │    ├── code_submissions (N)
 │    ├── capability_sessions (N)
 │    │    └── capability_events (N)
 │    └── pdf_books (N)
 │
 ├── 助教侧 ───────────────────────────────────────────────────────────────
 │    ├── lesson_plans (N)              ← 教师
 │    │    ├── audit_logs (N)
 │    │    └── plan_snapshots (N)
 │    ├── homework_grades (N)           ← 学生
 │    ├── exercise_batches (N)          ← 教师
 │    │    └── questions (N)
 │    ├── materials (N)                 ← 上传者
 │    ├── questions (N)                 ← 出题人
 │    ├── insight_reports (N)           ← 学生
 │    ├── teaching_aux (N)              ← 教师
 │    ├── llm_call_logs (N, nullable)
 │    └── agent_workflows (N, nullable)
 │
 └── (没有任何子表直接归属 teacher/admin role)

独立表（无 FK 到 users）:
 - knowledge_tags
 - qa_patterns
 - exercise_test_metadata
 - rag_documents
 - generated_images
 - project_registry
```

---

## 使用方式

### 助学系统连接

```python
# 使用 role='student' 的账号登录
# 所有 25 张助学表直接可用
# 教学资料可通过 homework_grades / insight_reports（project_id='student-project'）读取
```

### 助教系统连接

```python
# 使用 role='teacher' 的账号登录
# 12 张助教表直接可用
# user_id 现在直接关联 users 表，无需再维护独立的教师-学生映射
```

### 互通数据访问

```sql
-- 助学端查看自己的作业批改结果
SELECT * FROM homework_grades
WHERE user_id = <当前学生ID> AND project_id = 'student-project';

-- 助教端查看自己创建的所有教案
SELECT * FROM lesson_plans
WHERE user_id = <当前教师ID>;

-- 跨端数据：教师查看某学生的学情
SELECT ir.*, u.nickname
FROM insight_reports ir
JOIN users u ON ir.user_id = u.id
WHERE ir.course_name = 'AI智能体开发' AND u.role = 'student';
```

---

## 迁移指南

### 从 SQLite 迁移到本 PostgreSQL 结构

1. **导出 SQLite 数据** → CSV 或 JSON
2. **执行本 DDL**：`psql -h <host> -U <user> -d <db> -f merged_schema.sql`
3. **导入数据**：按表依赖顺序导入（先 users → 再助学表 → 再助教表）
4. **重整 SERIAL 序列**：
   ```sql
   SELECT setval('users_id_seq', COALESCE((SELECT MAX(id) FROM users), 1));
   -- 对其他 SERIAL 表重复此操作
   ```

### API 代码改动要点

| 原 SQLite 写法 | PostgreSQL 写法 |
|----------------|----------------|
| `?` 占位符 | `$1, $2, ...` (asyncpg/psycopg2) |
| `SELECT last_insert_rowid()` | `INSERT ... RETURNING id` |
| `datetime('now')` | `NOW()` |
| `date('now')` | `CURRENT_DATE` |
| `sqlite3.connect(...)` | `asyncpg.connect(...)` 或 `psycopg2.connect(...)` |
| 无连接池 | 建议 PgBouncer / psycopg2 pool |

---

## 驱动依赖

```
# requirements.txt 新增
psycopg2-binary>=2.9       # 同步驱动
# 或
asyncpg>=0.29              # 异步驱动（推荐 FastAPI）
```

---

> **文件**: [merged_schema.sql](merged_schema.sql) | **生成日期**: 2026-07-23 | **总表数**: 37
