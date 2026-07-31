import asyncio
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

from services.agent_tool_service import build_tool_schemas
from services.conversation_export_service import _redact_text
from services.learning_analytics_service import UnsafeSQL, validate_student_sql
from services.search_service import (
    TavilyUnavailableError,
    filter_search_results,
    rewrite_search_query,
    tavily_advanced_search,
)


class SearchQualityTests(unittest.TestCase):
    def test_memory_query_is_kept_in_ai_agent_context(self):
        rewritten = rewrite_search_query("帮我搜一下智能体记忆")
        self.assertIn("AI Agent", rewritten)
        self.assertIn("短期记忆", rewritten)
        self.assertIn("长期记忆", rewritten)

    def test_filters_japanese_low_quality_and_near_duplicates(self):
        raw = [
            {
                "title": "Agent memory: short-term and long-term memory",
                "url": "https://docs.example.edu/agent-memory",
                "content": "AI Agent 短期记忆与长期记忆的架构和区别",
                "score": 0.92,
            },
            {
                "title": "Agent memory: short-term and long-term memory",
                "url": "https://copy.example.com/same",
                "content": "AI Agent 短期记忆与长期记忆的架构和区别",
                "score": 0.88,
            },
            {
                "title": "エージェントメモリとは何ですか",
                "url": "https://jp.example.com/memory",
                "content": "これはエージェントのメモリについての記事です",
                "score": 0.95,
            },
            {
                "title": "无关购物页面",
                "url": "https://shop.example.com/item",
                "content": "夏季商品促销",
                "score": 0.05,
            },
        ]
        results = filter_search_results("智能体记忆", raw, max_results=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["url"], "https://docs.example.edu/agent-memory")
        self.assertIn("quality", results[0])

    def test_missing_key_has_clear_unavailable_state(self):
        with patch("services.search_service.get_tavily_api_key", return_value=""):
            with self.assertRaisesRegex(TavilyUnavailableError, "Tavily 高级搜索暂不可用"):
                asyncio.run(tavily_advanced_search(1, "智能体记忆"))


class NL2SQLGuardrailTests(unittest.TestCase):
    def test_accepts_single_user_read_only_query(self):
        sql = validate_student_sql(
            "SELECT knowledge_tag, COUNT(*) AS n FROM learning_records "
            "WHERE user_id = ? GROUP BY knowledge_tag"
        )
        self.assertTrue(sql.endswith("LIMIT 50"))

    def test_rejects_write_join_or_scope_bypass(self):
        unsafe = [
            "UPDATE learning_records SET duration_seconds = 0 WHERE user_id = ?",
            "SELECT * FROM learning_records JOIN qa_history ON 1=1 WHERE learning_records.user_id = ?",
            "SELECT * FROM learning_records WHERE user_id = ? OR 1=1",
            "SELECT * FROM users WHERE user_id = ?",
        ]
        for sql in unsafe:
            with self.subTest(sql=sql):
                with self.assertRaises(UnsafeSQL):
                    validate_student_sql(sql)


class ToolAndExportTests(unittest.TestCase):
    def test_tools_are_function_calling_schemas(self):
        schemas = build_tool_schemas(
            allow_web=True,
            allow_knowledge=True,
            allow_analytics=True,
            allow_mind_map=True,
        )
        names = {item["function"]["name"] for item in schemas}
        self.assertEqual(
            names,
            {"web_search", "knowledge_search", "analyze_learning_data", "generate_mind_map"},
        )
        self.assertTrue(all(item["type"] == "function" for item in schemas))

    def test_export_redacts_secrets_and_personal_identifiers(self):
        text = "key=" + "tvly-" + ("a" * 24) + " email=a@example.com phone=13800138000"
        redacted = _redact_text(text, anonymize=True)
        self.assertNotIn("tvly-", redacted)
        self.assertNotIn("a@example.com", redacted)
        self.assertNotIn("13800138000", redacted)
        self.assertIn("[REDACTED_SECRET]", redacted)


if __name__ == "__main__":
    unittest.main()
