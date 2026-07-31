import unittest

from services.document_loader import (
    _append_unit,
    _is_toc_page,
    _make_parent_child_chunks,
)
from services.mind_map_service import render_mind_map_svg
from services.personalization_service import _extract_explicit_facts


class RAGChunkQualityTests(unittest.TestCase):
    def test_navigation_page_is_rejected(self):
        self.assertTrue(
            _is_toc_page(
                [
                    "AI Agent 实现篇",
                    "❍第3章 通用型 Agent",
                    "❍第4章 知识型 Agent",
                    "❍第5章 多模态 Agent",
                ]
            )
        )

    def test_cross_page_sentence_is_joined(self):
        units = []
        _append_unit(units, "多模态智能体需要同时处理图像、语音和", 12)
        _append_unit(units, "文本，并交给规划器统一决策。", 13)
        self.assertEqual(len(units), 1)
        self.assertIn("统一决策。", units[0][0])

    def test_child_hits_return_complete_parent(self):
        units = [
            ("多模态智能体先采集图像、语音和文本。", 326),
            ("模态编码器把输入转换为统一表示。", 326),
            ("规划器结合记忆和工具选择下一步动作。", 326),
            ("执行器调用工具并将反馈返回规划器。", 327),
        ] * 15
        chunks = _make_parent_child_chunks(
            section="9.2.2 多模态智能体的构建与应用",
            units=units,
            source_path="book.pdf",
            title="AI Agent 开发全书",
            module="智能体",
            parent_offset=0,
        )
        self.assertGreaterEqual(len(chunks), 2)
        self.assertTrue(all(chunk.text.startswith("9.2.2") for chunk in chunks))
        self.assertTrue(all(chunk.metadata["embedding_text"] for chunk in chunks))
        self.assertTrue(all(chunk.text.endswith("。") for chunk in chunks))


class MindMapTests(unittest.TestCase):
    def test_svg_contains_real_nodes_lines_and_escaped_text(self):
        root = {
            "label": "智能体记忆",
            "children": [
                {"label": "短期记忆", "children": []},
                {"label": "长期记忆 <画像>", "children": []},
            ],
        }
        svg = render_mind_map_svg(root, "记忆架构")
        self.assertIn("<svg", svg)
        self.assertIn("<path", svg)
        self.assertIn("<rect", svg)
        self.assertIn("短期记忆", svg)
        self.assertIn("&lt;画像&gt;", svg)
        self.assertNotIn("<画像>", svg)


class MemoryGranularityTests(unittest.TestCase):
    def test_extracts_profile_tooling_interest_and_preference(self):
        facts = _extract_explicit_facts(
            "我是北京理工大学大二计算机专业学生，我正在研究RAG文档切分。"
            "我使用bge-large-zh，我倾向于用简单代码理解实现。"
        )
        mapped = {(category, key): value for category, key, value, _ in facts}
        self.assertIn(("profile", "学校"), mapped)
        self.assertIn(("profile", "年级"), mapped)
        self.assertIn(("profile", "专业"), mapped)
        self.assertIn(("interest", "当前研究方向"), mapped)
        self.assertIn(("tooling", "当前工具"), mapped)
        self.assertIn(("preference", "技术选择偏好"), mapped)


if __name__ == "__main__":
    unittest.main()
