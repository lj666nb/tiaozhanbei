"""
综合测试脚本 — 验证冷部署后学习资源和代码界面的数据加载
测试场景:
1. 用户登录 (demo/demo123)
2. 获取知识标签
3. 获取习题列表和详情（代码编辑器左窗口数据源）
4. 获取学习资源
5. 获取本地学习资料
"""
import requests
import json
import sys

BASE = "http://localhost:8000"
PASS = 0
FAIL = 0

def test(name, fn):
    global PASS, FAIL
    try:
        fn()
        PASS += 1
        print(f"  [PASS] {name}")
    except Exception as e:
        FAIL += 1
        print(f"  [FAIL] {name}: {e}")

def test_login():
    """验证登录并获取 token"""
    global TOKEN
    resp = requests.post(f"{BASE}/api/auth/login", json={
        "username": "demo", "password": "demo123"
    })
    assert resp.status_code == 200, f"HTTP {resp.status_code}"
    data = resp.json()
    assert data["code"] == 200, f"code={data['code']}"
    TOKEN = data["data"]["access_token"]
    assert len(TOKEN) > 10, "Token too short"
    user = data["data"]["user"]
    assert user["username"] == "demo", f"Wrong user: {user}"

def test_verify_token():
    """验证 Token 有效性"""
    resp = requests.get(f"{BASE}/api/auth/verify", headers={
        "Authorization": f"Bearer {TOKEN}"
    })
    assert resp.status_code == 200
    assert resp.json()["code"] == 200

def test_knowledge_tags():
    """验证知识点标签已加载"""
    resp = requests.get(f"{BASE}/api/knowledge/tags", headers={
        "Authorization": f"Bearer {TOKEN}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    tags = data["data"]
    assert len(tags) > 0, "Empty knowledge tags"
    # 应该有至少6个分类
    categories = {t.get("category", "") for t in tags}
    assert len(categories) >= 6, f"Expected >=6 categories, got {len(categories)}: {categories}"
    print(f"      Categories: {categories}")

def test_exercise_list():
    """验证习题列表加载"""
    resp = requests.get(f"{BASE}/api/resources/exercises", headers={
        "Authorization": f"Bearer {TOKEN}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    exercises = data["data"]
    assert len(exercises) >= 60, f"Expected >=60 exercises, got {len(exercises)}"
    print(f"      Total exercises: {len(exercises)}")

def test_exercise_detail():
    """验证单个习题详情加载（CodeLab 左窗口数据源）"""
    test_exercises = ["1-1", "2-1", "3-1", "4-1", "5-1", "6-1"]
    for ex_id in test_exercises:
        resp = requests.get(f"{BASE}/api/resources/exercises/{ex_id}", headers={
            "Authorization": f"Bearer {TOKEN}"
        })
        assert resp.status_code == 200, f"Exercise {ex_id} HTTP {resp.status_code}"
        data = resp.json()
        assert data["code"] == 200
        ex = data["data"]
        assert ex.get("title"), f"Exercise {ex_id} has no title"
        assert ex.get("description"), f"Exercise {ex_id} has no description"
        # 验证关键字段
        assert len(ex.get("description", "")) > 20, f"Exercise {ex_id} description too short: {ex.get('description','')[:50]}"
        print(f"      {ex_id}: {ex['title'][:40]}... (desc: {len(ex['description'])} chars)")

def test_resources_list():
    """验证学习资源列表"""
    resp = requests.get(f"{BASE}/api/resources/list", headers={
        "Authorization": f"Bearer {TOKEN}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    resources = data["data"]["items"]
    total = data["data"]["total"]
    assert total >= 20, f"Expected >=20 total resources, got total={total}"
    print(f"      Resources on page 1: {len(resources)}, total: {total}")

def test_learning_material():
    """验证本地学习资料可读取"""
    resp = requests.get(f"{BASE}/api/learning/resource?knowledge=AI智能体定义", headers={
        "Authorization": f"Bearer {TOKEN}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["code"] == 200
    material = data["data"]
    assert material is not None, "Material is None"
    # 应该找到本地资料或者返回 fallback
    assert material.get("content"), "No content in material response"
    content_len = len(material.get("content", ""))
    print(f"      Content length: {content_len} chars, found: {material.get('found')}")

def test_code_evaluate():
    """验证代码评测功能可用"""
    resp = requests.post(f"{BASE}/api/learning/code-evaluate", json={
        "exercise_id": "1-1",
        "code": "def agent_definition_demo():\n    return {'perception': 'sensors', 'decision': 'planner', 'action': 'actuator', 'environment': 'world'}\n\nif __name__ == '__main__':\n    result = agent_definition_demo()\n    print(f'[PASS] test1: {result}')\n",
        "language": "python"
    }, headers={
        "Authorization": f"Bearer {TOKEN}"
    })
    assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    assert data["code"] == 200, f"API code={data['code']}: {data.get('message')}"
    result = data["data"]
    print(f"      Evaluation result: passed={result.get('passed')}, {result.get('passed_count')}/{result.get('total')}")

def test_exercise_test_metadata_seeded():
    """验证 exercise_test_metadata 表已被种子数据填充"""
    import sqlite3, os
    db_path = os.path.join(os.path.dirname(__file__), "backend", "data", "learning_platform.db")
    db_path = os.path.abspath(db_path)
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM exercise_test_metadata").fetchone()[0]
    conn.close()
    assert count >= 60, f"Expected >=60 rows in exercise_test_metadata, got {count}"
    print(f"      exercise_test_metadata rows: {count}")

def test_knowledge_tags_db_seeded():
    """验证 knowledge_tags 表已被种子数据填充"""
    import sqlite3, os
    db_path = os.path.join(os.path.dirname(__file__), "backend", "data", "learning_platform.db")
    db_path = os.path.abspath(db_path)
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM knowledge_tags").fetchone()[0]
    conn.close()
    assert count >= 30, f"Expected >=30 rows in knowledge_tags, got {count}"
    print(f"      knowledge_tags rows: {count}")


if __name__ == "__main__":
    TOKEN = None

    print("\n" + "="*60)
    print("AI智能体学科学习平台 — 冷部署数据完整性测试")
    print("="*60)

    print("\n[1] 认证测试")
    test("用户登录", test_login)
    test("Token 验证", test_verify_token)
    assert TOKEN is not None, "Login failed — cannot proceed"

    print("\n[2] 数据完整性测试")
    test("知识点标签已加载", test_knowledge_tags)
    test("知识点标签(DB)", test_knowledge_tags_db_seeded)
    test("习题列表", test_exercise_list)
    test("习题评测元数据(DB)", test_exercise_test_metadata_seeded)

    print("\n[3] CodeLab 左窗口数据源测试（核心）")
    test("习题详情加载(6个模块)", test_exercise_detail)

    print("\n[4] 学习资源测试")
    test("资源列表", test_resources_list)
    test("本地学习资料", test_learning_material)

    print("\n[5] 代码评测测试")
    test("代码沙箱评测", test_code_evaluate)

    print("\n" + "="*60)
    print(f"结果: {PASS} 通过, {FAIL} 失败, 共 {PASS+FAIL} 项测试")
    if FAIL > 0:
        print("FAIL: Some tests failed!")
        sys.exit(1)
    else:
        print("SUCCESS: All tests passed! Deployment data integrity confirmed.")
    print("="*60 + "\n")
