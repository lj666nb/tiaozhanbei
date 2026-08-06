import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch

from langchain_core.messages import AIMessageChunk

from services import lab_workspace_service as service


CORRECT_BUILD_CHAT_MESSAGES = '''
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

CORRECT_NORMALIZE_STREAM_CHUNKS = '''
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

CHAT_APP = '''
from langchain_openai import ChatOpenAI
from solution import build_chat_messages

model = ChatOpenAI(model="demo")
messages = build_chat_messages("称呼用户为小林", "推荐一座博物馆")
response = model.invoke(messages)
print(response.content)
'''

STREAM_APP = '''
from langchain_openai import ChatOpenAI
from solution import normalize_stream_chunks

model = ChatOpenAI(model="demo")
messages = [{"role": "user", "content": "你好"}]
parts = []
for chunk in model.stream(messages):
    text = normalize_stream_chunks([chunk])
    print(text, end="", flush=True)
    parts.append(text)
answer = "".join(parts)
'''


class LabWorkspaceServiceTests(unittest.TestCase):
    def test_streamed_tool_arguments_are_reconstructed_before_execution(self):
        first = AIMessageChunk(
            content="",
            tool_call_chunks=[{
                "name": "read_project_file",
                "args": '{"path":"sol',
                "id": "call-read-1",
                "index": 0,
            }],
        )
        second = AIMessageChunk(
            content="",
            tool_call_chunks=[{
                "name": None,
                "args": 'ution.py"}',
                "id": None,
                "index": 0,
            }],
        )

        calls = service._normalized_lab_tool_calls(first + second)

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["name"], "read_project_file")
        self.assertEqual(calls[0]["args"], {"path": "solution.py"})
        self.assertEqual(calls[0]["id"], "call-read-1")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root_patch = patch.object(service, "WORKSPACE_ROOT", Path(self.temp.name))
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp.cleanup()

    def test_workspace_starts_as_a_real_small_project(self):
        workspace = service.get_workspace(7, "1-1")
        self.assertEqual(workspace["project_name"], "agent-lab-1-1")
        self.assertEqual({item["path"] for item in workspace["files"]}, {"README.md", ".gitignore"})
        self.assertEqual(len(workspace["course"]["stages"]), 7)

    def test_workspace_exposes_guided_learning_contract(self):
        course = service.get_workspace(7, "1-1")["course"]

        self.assertIn("示例输入", course["input_output"])
        self.assertIn("消息顺序与 role 正确", course["acceptance"])
        self.assertIn("消息协议", course["skills"])
        self.assertTrue(course["prerequisites"])
        implementation = next(item for item in course["stages"] if item["id"] == "implementation")
        self.assertEqual(implementation["target_file"], "solution.py")
        self.assertGreaterEqual(len(implementation["micro_steps"]), 3)
        self.assertEqual(implementation["hints"][0]["level"], 1)
        self.assertGreaterEqual(len(implementation["hints"]), 3)

    def test_terminal_environment_does_not_inherit_backend_secrets(self):
        root = service._root(7, "1-1")
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://secret",
            "JWT_SECRET_KEY": "secret",
            "TAVILY_API_KEY": "secret",
        }):
            env, _ = service._terminal_environment(root, {})
        self.assertNotIn("DATABASE_URL", env)
        self.assertNotIn("JWT_SECRET_KEY", env)
        self.assertNotIn("TAVILY_API_KEY", env)

    def test_failed_case_feedback_contains_learning_next_action(self):
        feedback = service._judge_case_feedback({
            "compile_error": None,
            "results": [
                {
                    "case_index": 1,
                    "description": "拒绝空系统提示",
                    "passed": False,
                    "error": "该非法输入必须抛出 ValueError",
                }
            ],
        })

        self.assertEqual(feedback[0]["category"], "输入边界")
        self.assertIn("检查", feedback[0]["next_action"])

    def test_structure_and_dependency_checks_are_incremental(self):
        for name in ["requirements.txt", ".env", "solution.py", "app.py"]:
            service.save_file(7, "1-1", name, "")
        structure = service.check_stage(7, "1-1", "structure")
        self.assertTrue(structure["passed"])

        service.save_file(
            7, "1-1", "requirements.txt",
            "langchain>=1.0\nlangchain-openai>=1.0\npython-dotenv>=1.0\n",
        )
        root = service._root(7, "1-1")
        state = service._read_state(root)
        state["installed_requirements_hash"] = service._requirements_hash(root)
        service._write_state(root, state)
        dependencies = service.check_stage(7, "1-1", "dependencies")
        self.assertTrue(dependencies["passed"])
        self.assertIn("dependencies", dependencies["completed_stages"])

    def test_checker_reports_exact_missing_target(self):
        service.get_workspace(7, "1-1")
        service.save_file(7, "1-1", "solution.py", "def something_else():\n    return 1\n")
        result = service.check_stage(7, "1-1", "implementation")
        self.assertFalse(result["passed"])
        target = next(item for item in result["checks"] if item["label"] == "build_chat_messages")
        self.assertIn("还没有定义", target["detail"])

    def test_implementation_stage_rejects_a_function_with_no_behavior(self):
        service.get_workspace(7, "1-1")
        for body in ("pass", "raise NotImplementedError"):
            with self.subTest(body=body):
                service.save_file(
                    7, "1-1", "solution.py",
                    f"def build_chat_messages(system_prompt, user_input):\n    {body}\n",
                )

                result = service.check_stage(7, "1-1", "implementation")

                self.assertFalse(result["passed"])
                behavior = next(item for item in result["checks"] if item["label"] == "核心函数行为")
                self.assertFalse(behavior["passed"])
                self.assertIn("基础消息顺序", behavior["detail"])
                self.assertNotIn("implementation", result["completed_stages"])

    def test_implementation_stage_requires_all_business_scenarios(self):
        service.get_workspace(7, "1-1")
        service.save_file(7, "1-1", "solution.py", CORRECT_BUILD_CHAT_MESSAGES)

        result = service.check_stage(7, "1-1", "implementation")

        self.assertTrue(result["passed"], result)
        behavior = next(item for item in result["checks"] if item["label"] == "核心函数行为")
        self.assertRegex(behavior["detail"], r"通过 \d+/\d+ 个业务场景")
        self.assertGreaterEqual(len(behavior["cases"]), 9)
        self.assertIn("implementation", result["completed_stages"])

    def test_integration_stage_rechecks_solution_instead_of_trusting_a_definition(self):
        service.get_workspace(7, "1-1")
        service.save_file(
            7, "1-1", "solution.py",
            "def build_chat_messages(system_prompt, user_input):\n    raise NotImplementedError\n",
        )
        service.save_file(7, "1-1", "app.py", CHAT_APP)

        result = service.check_stage(7, "1-1", "integration")

        self.assertFalse(result["passed"])
        behavior = next(item for item in result["checks"] if item["label"] == "核心模块业务测试")
        self.assertFalse(behavior["passed"])
        self.assertGreaterEqual(len(behavior["cases"]), 9)

    def test_chat_integration_requires_personalized_messages_to_reach_invoke(self):
        service.get_workspace(7, "1-1")
        service.save_file(7, "1-1", "solution.py", CORRECT_BUILD_CHAT_MESSAGES)
        service.save_file(7, "1-1", "app.py", CHAT_APP)
        service.save_file(7, "1-1", ".env", "DEEPSEEK_API_KEY=unit-test-value\n")

        result = service.check_stage(7, "1-1", "integration")

        self.assertTrue(result["passed"], result)
        wiring = next(item for item in result["checks"] if item["label"] == "个性化消息接入")
        self.assertTrue(wiring["passed"])

    def test_integration_rechecks_current_project_env_key(self):
        service.get_workspace(7, "1-1")
        service.save_file(7, "1-1", "solution.py", CORRECT_BUILD_CHAT_MESSAGES)
        service.save_file(7, "1-1", "app.py", CHAT_APP)
        service.save_file(7, "1-1", ".env", "DEEPSEEK_API_KEY=unit-test-value\n")
        self.assertTrue(service.check_stage(7, "1-1", "integration")["passed"])

        service.save_file(7, "1-1", ".env", "DEEPSEEK_API_KEY=\n")
        result = service.check_stage(7, "1-1", "integration")

        self.assertFalse(result["passed"])
        key_check = next(item for item in result["checks"] if item["label"] == "项目 API Key")
        self.assertFalse(key_check["passed"])

    def test_stream_integration_requires_incremental_flush_inside_stream_loop(self):
        service.get_workspace(7, "1-3")
        service.save_file(7, "1-3", "solution.py", CORRECT_NORMALIZE_STREAM_CHUNKS)
        service.save_file(7, "1-3", "app.py", STREAM_APP)
        service.save_file(7, "1-3", ".env", "DEEPSEEK_API_KEY=unit-test-value\n")

        result = service.check_stage(7, "1-3", "integration")

        self.assertTrue(result["passed"], result)
        immediate = next(item for item in result["checks"] if item["label"] == "逐片段即时输出")
        self.assertTrue(immediate["passed"])

    def test_stream_integration_rejects_printing_only_after_collection(self):
        service.get_workspace(7, "1-3")
        service.save_file(7, "1-3", "solution.py", CORRECT_NORMALIZE_STREAM_CHUNKS)
        service.save_file(
            7, "1-3", "app.py",
            STREAM_APP.replace('print(text, end="", flush=True)\n    ', ''),
        )
        service.save_file(7, "1-3", ".env", "DEEPSEEK_API_KEY=unit-test-value\n")

        result = service.check_stage(7, "1-3", "integration")

        self.assertFalse(result["passed"])
        immediate = next(item for item in result["checks"] if item["label"] == "逐片段即时输出")
        self.assertFalse(immediate["passed"])

    def test_agent_mode_tools_can_write_files_and_run_terminal(self):
        service.get_workspace(7, "1-1")
        tool_names = {
            item["function"]["name"]
            for item in service._lab_tool_schemas(allow_writes=True)
        }
        self.assertIn("write_project_file", tool_names)
        self.assertIn("run_terminal_command", tool_names)

        written = service._execute_lab_tool(
            "write_project_file",
            {"path": "src/agent_created.py", "content": "print('agent-created')\n"},
            7,
            "1-1",
        )
        executed = service._execute_lab_tool(
            "run_terminal_command",
            {"command": "python src/agent_created.py"},
            7,
            "1-1",
        )

        self.assertIn("已写入", written)
        self.assertIn("命令退出状态：0", executed)
        self.assertIn("agent-created", executed)

    def test_terminal_supports_normal_shell_features(self):
        service.get_workspace(7, "1-1")
        result = service.run_terminal(7, "1-1", "echo first && echo second")
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("first", result["output"])
        self.assertIn("second", result["output"])

    def test_terminal_keeps_one_canonical_venv_and_project_directories(self):
        service.get_workspace(7, "1-1")
        created = service.create_directory(7, "1-1", "src/tools")
        self.assertEqual(created["path"], "src/tools")
        mkdir_command = "mkdir data\\cache" if os.name == "nt" else "mkdir -p data/cache"
        terminal_folder = service.run_terminal(7, "1-1", mkdir_command)
        self.assertEqual(terminal_folder["exit_code"], 0)
        workspace = service.get_workspace(7, "1-1")
        self.assertIn("src/tools", workspace["directories"])
        self.assertIn("data/cache", workspace["directories"])

        custom_env = service.run_terminal(7, "1-1", "python -m venv 123")
        self.assertEqual(custom_env["exit_code"], 0)
        self.assertIn("统一为 .venv", custom_env["output"])
        self.assertEqual(service.get_workspace(7, "1-1")["virtual_envs"], [".venv"])

    def test_terminal_can_create_and_read_project_files(self):
        service.get_workspace(7, "1-1")
        result = service.run_terminal(7, "1-1", "echo terminal-created > notes.txt")
        self.assertEqual(result["exit_code"], 0)
        file = service.read_file(7, "1-1", "notes.txt")
        self.assertFalse(file["binary"])
        self.assertIn("terminal-created", file["content"])

    def test_virtual_environment_is_browsable_and_activation_persists(self):
        service.get_workspace(7, "1-1")
        created = service.run_terminal(7, "1-1", "python -m venv venv")
        self.assertEqual(created["exit_code"], 0)
        entries = service.list_entries(7, "1-1")["entries"]
        self.assertTrue(any(item["name"] == ".venv" and item["virtual"] for item in entries))
        self.assertTrue(any(item["name"] == "pyvenv.cfg" for item in service.list_entries(7, "1-1", ".venv")["entries"]))

        activated = service.run_terminal(7, "1-1", "source .venv/bin/activate")
        self.assertEqual(activated["active_env"], ".venv")
        version = service.run_terminal(7, "1-1", "python --version")
        self.assertEqual(version["active_env"], ".venv")
        deactivated = service.run_terminal(7, "1-1", "deactivate")
        self.assertEqual(deactivated["active_env"], "")

    def test_terminal_stream_emits_output_before_done(self):
        service.get_workspace(7, "1-1")
        events = list(service.stream_terminal(7, "1-1", "echo streaming"))
        event_types = [item["type"] for item in events]
        self.assertEqual(event_types[0], "start")
        self.assertIn("output", event_types)
        self.assertEqual(event_types[-1], "done")
        self.assertIn("streaming", "".join(item.get("data", "") for item in events))

    def test_terminal_observation_redacts_credentials_for_tutor_context(self):
        service.get_workspace(7, "1-1")
        secret = "sk-this-is-a-fake-secret-value"
        service.run_terminal(7, "1-1", f"echo API_KEY={secret}")
        state = service._read_state(service._root(7, "1-1"))
        self.assertNotIn(secret, state["last_terminal"]["output"])
        self.assertIn("<redacted>", state["last_terminal"]["output"])

    def test_explorer_can_rename_duplicate_and_delete_entries(self):
        service.get_workspace(7, "1-1")
        service.save_file(7, "1-1", "src/tool.py", "print('ok')\n")
        moved = service.move_entry(7, "1-1", "src/tool.py", "src/main.py")
        self.assertTrue(moved["moved"])
        copied = service.duplicate_entry(7, "1-1", "src/main.py", "src/main-copy.py")
        self.assertTrue(copied["duplicated"])
        deleted = service.delete_entry(7, "1-1", "src/main-copy.py")
        self.assertTrue(deleted["deleted"])
        self.assertFalse(service._root(7, "1-1").joinpath("src/main-copy.py").exists())

    def test_progress_overview_uses_the_same_stage_state_as_workspace(self):
        service.get_workspace(7, "1-1")
        root = service._root(7, "1-1")
        service._write_state(root, {"completed_stages": ["structure", "environment"], "commands": []})
        overview = service.get_progress_overview(7)
        self.assertEqual(overview["1-1"]["completed_stages"], ["structure", "environment"])
        self.assertEqual(overview["1-1"]["total_stages"], len(service._course("1-1")["stages"]))

    def test_passed_state_restores_full_project_and_each_stage_result(self):
        service.get_workspace(7, "1-1")
        service.save_file(7, "1-1", "solution.py", CORRECT_BUILD_CHAT_MESSAGES)
        service.save_file(7, "1-1", "app.py", CHAT_APP)
        service.save_file(
            7, "1-1", "requirements.txt",
            "langchain\nlangchain-openai\npython-dotenv\n",
        )
        service.save_file(7, "1-1", ".env", "OPENAI_API_KEY=keep-local-secret\n")
        root = service._root(7, "1-1")
        course = service._course("1-1")
        passed_results = service._legacy_passed_stage_results(course)
        state = service._read_state(root)
        state.update({
            "acceptance_ever_passed": True,
            "passed_solution_code": CORRECT_BUILD_CHAT_MESSAGES,
            "passed_project_files": service._passed_project_snapshot(root),
            "passed_stage_results": passed_results,
        })
        service._write_state(root, state)

        service.save_file(7, "1-1", "solution.py", "raise NotImplementedError\n")
        service.save_file(7, "1-1", "app.py", "print('changed')\n")
        service.save_file(7, "1-1", "VARIANT_TASK.md", "old variant\n")
        service.save_file(7, "1-1", "scratch.txt", "temporary\n")

        restored = service.apply_project_state(
            7,
            "1-1",
            "passed",
            solution_code=CORRECT_BUILD_CHAT_MESSAGES,
        )
        files = {item["path"]: item["content"] for item in restored["files"]}

        self.assertEqual(files["solution.py"], CORRECT_BUILD_CHAT_MESSAGES)
        self.assertEqual(files["app.py"], CHAT_APP)
        self.assertNotIn("VARIANT_TASK.md", files)
        self.assertEqual(files["scratch.txt"], "temporary\n")
        self.assertIn("OPENAI_API_KEY=keep-local-secret", files[".env"])
        self.assertEqual(
            set(restored["completed_stages"]),
            {item["id"] for item in course["stages"]},
        )
        self.assertEqual(set(restored["stage_results"]), set(restored["completed_stages"]))
        self.assertTrue(all(item["passed"] for item in restored["stage_results"].values()))
        implementation = restored["stage_results"]["implementation"]
        business_check = next(
            item for item in implementation["checks"]
            if "业务测试点" in item["label"] or item["label"] == "核心函数行为"
        )
        self.assertGreaterEqual(len(business_check["cases"]), 9)
        self.assertTrue(all(item["passed"] for item in business_check["cases"]))

    def test_legacy_pass_record_is_upgraded_to_complete_project(self):
        service.get_workspace(7, "1-1")
        root = service._root(7, "1-1")
        state = service._read_state(root)
        state.update({
            "acceptance_ever_passed": True,
            "passed_solution_code": CORRECT_BUILD_CHAT_MESSAGES,
            "passed_project_files": {
                "README.md": "# old snapshot\n",
                "solution.py": CORRECT_BUILD_CHAT_MESSAGES,
            },
            "passed_stage_results": service._legacy_passed_stage_results(
                service._course("1-1"),
            ),
        })
        service._write_state(root, state)

        restored = service.apply_project_state(
            7,
            "1-1",
            "passed",
            solution_code=CORRECT_BUILD_CHAT_MESSAGES,
        )
        files = {item["path"]: item["content"] for item in restored["files"]}
        self.assertIn("app.py", files)
        self.assertIn("requirements.txt", files)
        self.assertIn("model.invoke(messages)", files["app.py"])
        self.assertIn("langchain-openai", files["requirements.txt"])

        implementation = restored["stage_results"]["implementation"]
        business_check = next(
            item for item in implementation["checks"]
            if "业务测试点" in item["label"] or item["label"] == "核心函数行为"
        )
        self.assertGreaterEqual(len(business_check["cases"]), 9)

    def test_initial_reset_keeps_local_env_and_virtual_environment(self):
        service.get_workspace(7, "1-1")
        root = service._root(7, "1-1")
        service.save_file(7, "1-1", ".env", "LLM_API_KEY=local-only\n")
        (root / ".venv").mkdir(parents=True, exist_ok=True)
        (root / ".venv" / "pyvenv.cfg").write_text("version = 3.11\n", encoding="utf-8")
        service.save_file(7, "1-1", "scratch.py", "print('remove me')\n")

        reset = service.get_workspace(7, "1-1", reset=True)
        files = {item["path"]: item["content"] for item in reset["files"]}

        self.assertTrue(reset["virtual_env"])
        self.assertIn(".env", files)
        self.assertNotIn("scratch.py", files)
        self.assertIn("README.md", files)


if __name__ == "__main__":
    unittest.main()
