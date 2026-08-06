import unittest

from routers.qa_router import (
    _curated_local_answer,
    _history_without_current_question,
    _is_degenerate_history,
    _local_qa_messages,
)


class LocalQAPromptTests(unittest.TestCase):
    def test_saved_current_question_is_not_sent_twice(self):
        history = [
            {"role": "user", "content": "上一题"},
            {"role": "assistant", "content": "上一题的回答"},
            {"role": "user", "content": "当前问题"},
        ]

        result = _history_without_current_question(history, "当前问题")

        self.assertEqual(len(result), 2)
        self.assertEqual(result[-1]["content"], "上一题的回答")

    def test_corrupted_assistant_history_is_excluded(self):
        corrupted = "。3。1。�。3。1。" * 30
        history = [
            {"role": "user", "content": "旧问题"},
            {"role": "assistant", "content": corrupted},
        ]

        messages = _local_qa_messages("什么是智能体？", history)

        self.assertTrue(_is_degenerate_history(corrupted))
        self.assertFalse(any(item["content"] == corrupted for item in messages))
        self.assertEqual(messages[-1], {"role": "user", "content": "什么是智能体？"})

    def test_optional_context_is_bounded(self):
        messages = _local_qa_messages("解释 RAG", [], "参考" * 5000)

        self.assertIn("解释 RAG", messages[-1]["content"])
        self.assertLess(len(messages[-1]["content"]), 1700)

    def test_tool_use_mechanism_uses_verified_teaching_answer(self):
        answer = _curated_local_answer("Agent的工具调用(Tool Use)是如何工作的？")

        self.assertIn("大模型本身不会直接运行", answer)
        self.assertIn("JSON Schema", answer)
        self.assertIn("ToolMessage", answer)
        self.assertIn("白名单", answer)
        self.assertIsNone(_curated_local_answer("帮我写一个排序函数"))


if __name__ == "__main__":
    unittest.main()
