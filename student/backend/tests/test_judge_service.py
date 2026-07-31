"""Project-lab private judge regression and bypass tests."""

import unittest

from services.judge_service import judge_submission


CORRECT_SOLUTION = '''
def build_chat_messages(system_prompt, user_input):
    if not isinstance(system_prompt, str) or not system_prompt.strip():
        raise ValueError("system_prompt 不能为空")
    if not isinstance(user_input, str) or not user_input.strip():
        raise ValueError("user_input 不能为空")
    return [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": user_input.strip()},
    ]
'''

CORRECT_STREAM_SOLUTION = '''
def normalize_stream_chunks(chunks):
    parts = []
    for chunk in chunks:
        if chunk is None:
            continue
        if isinstance(chunk, str):
            content = chunk
        elif isinstance(chunk, dict):
            content = chunk.get("content")
        elif hasattr(chunk, "content"):
            content = chunk.content
        else:
            raise ValueError("不支持的片段")
        if content is None or content == "":
            continue
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text = block.get("text")
                    if isinstance(text, str) and text:
                        parts.append(text)
        else:
            raise ValueError("不支持的内容")
    return "".join(parts)
'''


class ProjectLabJudgeTest(unittest.TestCase):
    def test_correct_solution_passes_every_private_scenario(self):
        result = judge_submission("1-1", CORRECT_SOLUTION)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["passed_count"], 17)
        self.assertEqual(result["judge_mode"], "server_private_cases")

    def test_starter_not_implemented_error_fails_every_scenario(self):
        result = judge_submission(
            "1-1",
            'def build_chat_messages(system_prompt, user_input):\n    raise NotImplementedError\n',
        )
        self.assertFalse(result["passed"])
        self.assertEqual(result["passed_count"], 0)
        self.assertEqual(result["total"], 17)
        self.assertTrue(all(item["error"] == "NotImplementedError" for item in result["results"]))

    def test_stream_normalizer_handles_real_iterators_and_chunk_objects(self):
        result = judge_submission("1-3", CORRECT_STREAM_SOLUTION)
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["passed_count"], 8)

    def test_printing_pass_marker_cannot_bypass_judge(self):
        result = judge_submission("1-1", 'print("[PASS]" * 100)')
        self.assertFalse(result["passed"])
        self.assertIn("模块顶层", result["compile_error"])

    def test_import_and_file_access_are_rejected(self):
        for source in ("import os\n", "def build_chat_messages(a, b):\n    return open('x')\n"):
            with self.subTest(source=source):
                result = judge_submission("1-1", source)
                self.assertFalse(result["passed"])
                self.assertIn("安全检查未通过", result["compile_error"])

    def test_wrong_message_order_fails(self):
        wrong = CORRECT_SOLUTION.replace(
            '{"role": "system", "content": system_prompt.strip()},\n        {"role": "user", "content": user_input.strip()}',
            '{"role": "user", "content": user_input.strip()},\n        {"role": "system", "content": system_prompt.strip()}',
        )
        result = judge_submission("1-1", wrong)
        self.assertFalse(result["passed"])
        failed = [item["description"] for item in result["results"] if not item["passed"]]
        self.assertIn("基础消息顺序", failed)

    def test_missing_input_validation_fails(self):
        wrong = '''
def build_chat_messages(system_prompt, user_input):
    return [{"role": "system", "content": str(system_prompt).strip()}, {"role": "user", "content": str(user_input).strip()}]
'''
        result = judge_submission("1-1", wrong)
        self.assertFalse(result["passed"])
        failed = [item["description"] for item in result["results"] if not item["passed"]]
        self.assertIn("拒绝空用户消息", failed)


if __name__ == "__main__":
    unittest.main()
