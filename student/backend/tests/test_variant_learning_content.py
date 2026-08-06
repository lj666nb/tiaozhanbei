"""Regression tests for the redesigned educational transfer stages."""

import json
import unittest

from services import capability_service
from services.agent_lab_faults import FAULT_PROFILES
from services.agent_lab_specs import FLAGSHIP_IDS
from tests.test_judge_service import CORRECT_SOLUTION


class VariantLearningContentTest(unittest.TestCase):
    def assert_variant_passes(self, exercise_id: str, code: str) -> None:
        result = capability_service._judge_variant_code(
            code, capability_service._get_variant_spec(exercise_id),
        )
        self.assertTrue(result["passed"], result)
        self.assertEqual(result["passed_count"], result["total"])

    def test_every_flagship_has_a_fault_profile(self):
        self.assertEqual(set(FAULT_PROFILES), set(FLAGSHIP_IDS))

    def test_public_fault_prompt_hides_private_root_cause(self):
        mutated, encoded = capability_service._build_mutation("1-1", CORRECT_SOLUTION)
        self.assertNotEqual(mutated, CORRECT_SOLUTION)
        metadata = json.loads(encoded)
        self.assertIn("故障现象", metadata["public"])
        self.assertNotIn("assistant", metadata["public"])
        self.assertIn("assistant", metadata["root_cause"])

    def test_complete_turn_trimming_variant(self):
        self.assert_variant_passes("1-2", r'''
def append_ticket_turn_and_trim(history, customer, agent, max_messages):
    if (not isinstance(history, list) or not isinstance(customer, str) or not customer.strip()
            or not isinstance(agent, str) or not agent.strip()
            or not isinstance(max_messages, int) or isinstance(max_messages, bool) or max_messages < 2):
        raise ValueError("输入非法")
    system = []
    turns = history
    if history and isinstance(history[0], dict) and history[0].get("role") == "system":
        if max_messages < 3:
            raise ValueError("窗口无法容纳系统消息和完整轮次")
        system = [dict(history[0])]
        turns = history[1:]
    if len(turns) % 2:
        raise ValueError("历史必须由完整轮次组成")
    for index, item in enumerate(turns):
        expected_role = "customer" if index % 2 == 0 else "agent"
        if (not isinstance(item, dict) or item.get("role") != expected_role
                or not isinstance(item.get("content"), str) or not item["content"].strip()):
            raise ValueError("历史消息非法")
    combined = [dict(item) for item in turns]
    combined.extend([
        {"role": "customer", "content": customer.strip()},
        {"role": "agent", "content": agent.strip()},
    ])
    capacity = max_messages - len(system)
    keep = (capacity // 2) * 2
    return system + combined[-keep:]
''')

    def test_real_tool_execution_variant(self):
        self.assert_variant_passes("2-4", r'''
def run_incident_response_plan(plan, registry, max_steps=5):
    if (not isinstance(plan, list) or not plan or not isinstance(registry, dict)
            or not isinstance(max_steps, int) or isinstance(max_steps, bool)
            or max_steps <= 0 or len(plan) > max_steps):
        raise ValueError("计划非法")
    for step in plan:
        if (not isinstance(step, dict) or not isinstance(step.get("name"), str)
                or not step["name"] or not isinstance(step.get("args"), dict)
                or step["name"] not in registry or not callable(registry[step["name"]])):
            raise ValueError("步骤非法")
    trace = []
    for step in plan:
        name = step["name"]
        try:
            observation = registry[name](**dict(step["args"]))
            trace.append({"step": name, "status": "success", "observation": observation})
        except Exception as exc:
            trace.append({"step": name, "status": "failed", "observation": str(exc)})
            return {"status": "failed", "failed_step": name, "trace": trace}
    return {"status": "completed", "failed_step": None, "trace": trace}
''')

    def test_normalized_retrieval_variant(self):
        self.assert_variant_passes("4-1", r'''
def retrieve_library_resources(query_terms, resources, top_k, min_score, department):
    if (not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0
            or not isinstance(min_score, (int, float)) or isinstance(min_score, bool) or min_score < 0):
        raise ValueError("参数非法")
    terms = {term.strip().lower() for term in query_terms if isinstance(term, str) and term.strip()}
    results = []
    for resource in resources:
        resource_terms = {
            term.strip().lower() for term in resource.get("terms", [])
            if isinstance(term, str) and term.strip()
        }
        score = len(terms & resource_terms) + (1 if resource.get("department") == department else 0)
        if score >= min_score:
            results.append({"id": resource["id"], "title": resource["title"], "score": score})
    return sorted(results, key=lambda item: (-item["score"], item["id"]))[:top_k]
''')

    def test_question_evidence_relevance_variant(self):
        self.assert_variant_passes("4-2", r'''
def build_auditable_policy_answer(question, evidence, current_year):
    if (not isinstance(question, str) or not question.strip() or not isinstance(evidence, list)
            or not isinstance(current_year, int) or isinstance(current_year, bool) or current_year <= 0):
        raise ValueError("输入非法")
    normalized_question = question.strip().lower()
    relevant = []
    ignored = 0
    for item in evidence:
        if (not isinstance(item, dict) or any(key not in item for key in ("id", "text", "year", "keywords"))
                or not isinstance(item["keywords"], list) or not item["keywords"]
                or any(not isinstance(keyword, str) or not keyword.strip() for keyword in item["keywords"])):
            raise ValueError("证据非法")
        if any(keyword.strip().lower() in normalized_question for keyword in item["keywords"]):
            relevant.append(item)
        else:
            ignored += 1
    stale = sum(1 for item in relevant if item["year"] < current_year - 1)
    valid = [item for item in relevant if item["year"] >= current_year - 1][:3]
    common = {"citations": [], "needs_human": True, "stale_sources": stale, "ignored_sources": ignored}
    if not evidence:
        return {"answer": "暂未找到可靠政策依据，已为你转接人工老师。", **common}
    if not relevant:
        return {"answer": "现有证据与问题不相关，无法可靠回答，已为你转接人工老师。", **common}
    if not valid:
        return {"answer": "现有资料已过期，无法可靠回答，已为你转接人工老师。", **common}
    return {
        "answer": "根据现行政策：" + "；".join(item["text"] for item in valid),
        "citations": [item["id"] for item in valid],
        "needs_human": False,
        "stale_sources": stale,
        "ignored_sources": ignored,
    }
''')


if __name__ == "__main__":
    unittest.main()
