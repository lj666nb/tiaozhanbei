"""数据模型（用于类型注解）"""
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class User:
    id: Optional[int] = None
    username: str = ""
    password_hash: str = ""
    nickname: str = ""
    grade: str = ""
    learning_stage: str = "入门"
    learning_goal: str = ""
    avatar: str = ""
    programming_background: str = ""
    years_experience: int = 0
    answer_preference: str = "分步清晰"

@dataclass
class QuizSession:
    id: Optional[int] = None
    user_id: int = 0
    stage: str = "入门"
    questions_json: str = "[]"
    answers_json: str = "[]"
    score: float = 0
    total: int = 0
    report_json: str = "{}"
    status: str = "pending"

@dataclass
class ErrorQuestion:
    id: Optional[int] = None
    user_id: int = 0
    question_data: str = ""
    user_answer: str = ""
    correct_answer: str = ""
    error_type: str = ""
    knowledge_tag: str = ""
    reviewed: int = 0

@dataclass
class QAHistory:
    id: Optional[int] = None
    user_id: int = 0
    question: str = ""
    answer: str = ""
    question_type: str = "text"
    knowledge_tags: str = ""
    explanation_level: str = "standard"

@dataclass
class LearningPath:
    id: Optional[int] = None
    user_id: int = 0
    path_data_json: str = "{}"
    progress_json: str = "{}"
    status: str = "active"

@dataclass
class DailyTask:
    id: Optional[int] = None
    user_id: int = 0
    task_data_json: str = "{}"
    completed: int = 0
    date: str = ""

@dataclass
class LearningRecord:
    id: Optional[int] = None
    user_id: int = 0
    knowledge_tag: str = ""
    action_type: str = ""
    duration_seconds: int = 0
    result_json: str = "{}"

@dataclass
class UserLLMConfig:
    id: Optional[int] = None
    user_id: int = 0
    provider: str = "openai"
    api_key: str = ""
    base_url: str = "https://api.openai.com"
    model_name: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 4096
