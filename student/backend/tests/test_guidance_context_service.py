import asyncio
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import database
from services.agent_course import TRACK_NAMES, build_course_path
from services import guidance_context_service as guidance
from services import lab_workspace_service as workspace


class GuidanceContextServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.TemporaryDirectory()
        self.temp_workspace = tempfile.TemporaryDirectory()
        database.DATABASE_PATH = os.path.join(self.temp_db.name, "guidance-test.db")
        database.init_db()
        conn = database.get_db()
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, nickname) VALUES ('guide-test', 'x', '测试学员')"
        )
        self.user_id = cursor.lastrowid
        path = build_course_path(TRACK_NAMES, "标准")
        progress = {"current_day": 1, "completed_tasks": {}, "overall_progress": 0}
        conn.execute(
            "INSERT INTO learning_paths (user_id, path_data_json, progress_json) VALUES (?, ?, ?)",
            (self.user_id, json.dumps(path, ensure_ascii=False), json.dumps(progress, ensure_ascii=False)),
        )
        conn.commit()
        conn.close()
        self.workspace_patch = patch.object(workspace, "WORKSPACE_ROOT", Path(self.temp_workspace.name))
        self.workspace_patch.start()

    def tearDown(self):
        self.workspace_patch.stop()
        self.temp_workspace.cleanup()
        self.temp_db.cleanup()

    def test_current_path_material_and_project_are_one_context(self):
        workspace.get_workspace(self.user_id, "1-1")
        workspace.save_file(
            self.user_id,
            "1-1",
            "solution.py",
            "def build_chat_messages(system_prompt, user_input):\n    return []\n",
        )

        result = guidance.build_learning_context(
            self.user_id,
            "这个函数下一步应该怎么改？",
        )

        self.assertTrue(result["available"])
        self.assertEqual(result["lab_id"], "1-1")
        self.assertIn("项目1：发出第一条模型消息", result["topic"])
        self.assertIn("build_chat_messages", result["prompt"])
        self.assertIn("model.invoke", result["prompt"])
        self.assertIn("solution.py", result["project_files"])
        self.assertIn("扩展方案", result["prompt"])

    def test_explicit_lab_keeps_lab_and_path_aligned(self):
        result = guidance.build_learning_context(self.user_id, "如何实现条件路由？", "3-2")
        self.assertEqual(result["lab_id"], "3-2")
        self.assertIn("项目9：用条件边实现智能路由", result["topic"])
        self.assertIn("紧急或低置信度请求转人工", result["prompt"])

    def test_lab_assistant_receives_the_same_authoritative_context(self):
        workspace.get_workspace(self.user_id, "1-1")
        conn = database.get_db()
        conn.execute(
            """INSERT INTO user_llm_config (user_id, provider, api_key, base_url, model_name)
               VALUES (?, 'test', 'test-key', 'https://example.invalid', 'test-model')""",
            (self.user_id,),
        )
        conn.commit()
        conn.close()
        mocked = AsyncMock(return_value="先补参数校验，再返回 system/user 两条消息。")
        fake_ai_service = types.ModuleType("services.ai_service")
        fake_ai_service.call_llm = mocked
        with patch.dict(sys.modules, {"services.ai_service": fake_ai_service}):
            result = asyncio.run(
                workspace.ask_assistant(
                    self.user_id,
                    "1-1",
                    "我能不能直接改做一个网页聊天机器人？",
                    "solution.py",
                    "agent",
                )
            )

        system_prompt = mocked.await_args.args[1][0]["content"]
        user_prompt = mocked.await_args.args[1][1]["content"]
        self.assertIn("当前学习路径与项目上下文", system_prompt)
        self.assertIn("不得建议改做与本节目标不同的项目", system_prompt)
        self.assertIn("工具观察", user_prompt)
        self.assertEqual(result["learning_context"]["lab_id"], "1-1")
        self.assertIn("已观察项目", result["notice"])
        self.assertTrue(result["available"])
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["observations"][0]["tool"], "workspace_reader")

        restored = workspace.get_workspace(self.user_id, "1-1")["assistant"]["history"]
        self.assertEqual([item["role"] for item in restored], ["user", "assistant"])
        self.assertEqual(restored[0]["content"], "我能不能直接改做一个网页聊天机器人？")

    def test_lab_assistant_does_not_fake_an_agent_answer_without_model(self):
        workspace.get_workspace(self.user_id, "1-1")
        result = asyncio.run(
            workspace.ask_assistant(
                self.user_id,
                "1-1",
                "给我一个提示",
                "solution.py",
                "agent",
                "structure",
            )
        )
        self.assertFalse(result["available"])
        self.assertEqual(result["status"], "setup_required")
        self.assertEqual(result["answer"], "")
        self.assertIn("静态课程引导", result["error"])


if __name__ == "__main__":
    unittest.main()
