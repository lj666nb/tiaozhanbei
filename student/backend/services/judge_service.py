"""Server-owned judge for the project-based Agent labs.

The browser receives contracts and starter code, never the private scenarios in
``agent_lab_specs.py``. This is an application isolation boundary rather than a
hardened multi-tenant sandbox.
"""

from __future__ import annotations

import ast
import copy
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path

from services.agent_lab_specs import FLAGSHIP_IDS, SPECS


FLAGSHIP_DATA = Path(__file__).resolve().parent.parent / "data" / "flagship_exercises.json"

BLOCKED_CALLS = {
    "open", "exec", "eval", "compile", "__import__", "input", "breakpoint",
    "getattr", "setattr", "delattr", "globals", "locals", "vars", "dir",
    "help", "exit", "quit",
}
BLOCKED_NODES = (
    ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith,
)

ALLOWED_IMPORT_ROOTS = {
    "copy", "json", "math", "re", "string", "typing", "sqlalchemy",
}


def load_flagship_exercises() -> list[dict]:
    try:
        return json.loads(FLAGSHIP_DATA.read_text(encoding="utf-8"))
    except Exception:
        return []


def get_flagship_exercise(exercise_id: str) -> dict | None:
    return next((item for item in load_flagship_exercises() if item.get("id") == exercise_id), None)


def is_flagship_exercise(exercise_id: str) -> bool:
    return exercise_id in FLAGSHIP_IDS


def _policy_error(code: str) -> str | None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"语法错误：第 {exc.lineno or '?'} 行，{exc.msg}"

    for statement in tree.body:
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Constant) and isinstance(statement.value.value, str):
            continue
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if statement.decorator_list:
                return "安全检查未通过：不允许使用装饰器"
            continue
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            ok = False
            try:
                ast.literal_eval(statement.value)
                ok = True
            except Exception:
                pass
            if not ok:
                # 允许调用可信任的模块级函数（如 declarative_base, sessionmaker 等）
                if isinstance(statement.value, ast.Call):
                    ok = True
            if not ok:
                return "安全检查未通过：模块级变量只能使用常量或可信任函数调用"
            continue
        if isinstance(statement, ast.Import):
            roots = {alias.name.split(".", 1)[0] for alias in statement.names}
            if not roots.issubset(ALLOWED_IMPORT_ROOTS):
                return "安全检查未通过：只允许导入本实验白名单中的模块"
            continue
        if isinstance(statement, ast.ImportFrom):
            root = str(statement.module or "").split(".", 1)[0]
            if statement.level or root not in ALLOWED_IMPORT_ROOTS:
                return "安全检查未通过：只允许导入本实验白名单中的模块"
            continue
        return "安全检查未通过：模块顶层只能定义函数、类或常量"

    for node in ast.walk(tree):
        if isinstance(node, BLOCKED_NODES):
            return f"安全检查未通过：不允许使用 {type(node).__name__}"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALLS:
            return f"安全检查未通过：不允许调用 {node.func.id}"
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            return "安全检查未通过：不允许访问内部属性"
        if isinstance(node, ast.Name) and node.id.startswith("__") and node.id not in ("__tablename__", "__init__", "__name__", "__doc__", "__module__", "__qualname__"):
            return "安全检查未通过：不允许访问内部名称"
    return None


RUNNER = r'''
import copy
import json
import sys
import time

SAFE_BUILTINS = {
    "ValueError": ValueError, "TypeError": TypeError, "RuntimeError": RuntimeError,
    "KeyError": KeyError, "Exception": Exception, "NotImplementedError": NotImplementedError,
    "dict": dict, "list": list, "tuple": tuple, "set": set, "str": str,
    "int": int, "float": float, "bool": bool, "len": len, "range": range,
    "enumerate": enumerate, "zip": zip, "sorted": sorted, "min": min,
    "max": max, "sum": sum, "all": all, "any": any, "isinstance": isinstance,
    "abs": abs, "round": round, "callable": callable, "hasattr": hasattr,
    "AttributeError": AttributeError,
    "__import__": __import__,
    "__build_class__": __build_class__,
    "super": super,
    "object": object,
    "type": type,
    "staticmethod": staticmethod,
    "classmethod": classmethod,
    "property": property,
    "issubclass": issubclass,
    "repr": repr,
    "iter": iter,
    "next": next,
}

with open(sys.argv[1], "r", encoding="utf-8") as source_file:
    source = source_file.read()
with open(sys.argv[2], "r", encoding="utf-8") as spec_file:
    spec = json.load(spec_file)

namespace = {"__builtins__": SAFE_BUILTINS, "__name__": "__main__"}
exec(compile(source, "submission.py", "exec"), namespace)
cases = []

def record(name, check):
    started = time.perf_counter()
    try:
        check()
        cases.append({"description": name, "passed": True, "error": None,
                      "duration_ms": round((time.perf_counter() - started) * 1000, 2)})
    except Exception as exc:
        error = str(exc).strip() or type(exc).__name__
        cases.append({"description": name, "passed": False, "error": error[:240],
                      "duration_ms": round((time.perf_counter() - started) * 1000, 2)})

def require(condition, message):
    if not condition:
        raise AssertionError(message)

def _safe_repr(obj, max_len=300):
    """Safe representation with truncation for display."""
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
        if len(s) > max_len:
            s = s[:max_len] + "...(截断)"
        return s
    except Exception:
        return str(obj)[:max_len]

def generic_check(func, item):
    args = copy.deepcopy(item.get("args", []))
    before = copy.deepcopy(args)
    expected_exception = item.get("exception")
    if expected_exception:
        try:
            func(*args)
        except SAFE_BUILTINS[expected_exception]:
            return
        raise AssertionError("该非法输入必须抛出 " + expected_exception)
    actual = func(*args)
    # 失败时记录详细的输入/期望/实际值用于学习反馈
    if actual != item.get("expected"):
        raise AssertionError(
            "返回结果不符合该业务场景\n"
            + "输入: " + _safe_repr(args) + "\n"
            + "期望: " + _safe_repr(item.get("expected")) + "\n"
            + "实际: " + _safe_repr(actual)
        )
    if item.get("fresh_result"):
        second = func(*copy.deepcopy(item.get("args", [])))
        require(actual is not second, "每次调用必须返回新的消息列表")
        require(all(left is not right for left, right in zip(actual, second)), "不同调用不能共享消息字典")
        actual[0]["content"] = "changed"
        require(second == item.get("expected"), "返回结果之间共享了可变对象")
    if item.get("immutable"):
        require(args == before, "函数修改了输入对象")

def run_generic():
    func = namespace.get(spec.get("target"))
    require(callable(func), "必须定义 " + str(spec.get("target")))
    for item in spec.get("cases", []):
        record(item["description"], lambda item=item: generic_check(func, item))

def run_tool_call():
    func = namespace.get("execute_tool_call")
    require(callable(func), "必须定义 execute_tool_call(tool_call, registry)")
    def query_order(order_id):
        db = {
            "ORD-20260730-0001": {"status": "delivered", "carrier": "顺丰速运", "eta": "2026-07-25", "customer_name": "张三", "product": "Python编程从入门到实践"},
            "ORD-20260730-0002": {"status": "shipped", "carrier": "中通快递", "eta": "2026-08-05", "customer_name": "李四", "product": "AI智能体开发实战"},
        }
        order = db.get(order_id)
        if not order:
            return {"status": "not_found", "message": f"订单 {order_id} 不存在"}
        return order
    def broken(order_id):
        raise RuntimeError("上游超时")
    registry = {
        "query_order": {"required": ["order_id"], "handler": query_order},
        "broken": {"required": ["order_id"], "handler": broken},
    }
    record("正常调用并生成工具消息", lambda: require(
        func({"id": "c1", "name": "query_order", "args": {"order_id": "ORD-20260730-0001"}}, registry) ==
        {"role": "tool", "tool_call_id": "c1", "name": "query_order", "status": "success",
         "content": {"status": "delivered", "carrier": "顺丰速运", "eta": "2026-07-25", "customer_name": "张三", "product": "Python编程从入门到实践"}},
        "成功结果结构不正确"))
    def missing_arg():
        try: func({"id": "c2", "name": "query_order", "args": {}}, registry)
        except ValueError: return
        raise AssertionError("缺少必填参数必须抛出 ValueError")
    record("拒绝缺少的必填参数", missing_arg)
    def unknown_tool():
        try: func({"id": "c3", "name": "delete_all", "args": {}}, registry)
        except ValueError: return
        raise AssertionError("未知工具必须抛出 ValueError")
    record("拒绝未注册工具", unknown_tool)
    def isolate_error():
        result = func({"id": "c4", "name": "broken", "args": {"order_id": "ORD-20260730-0002"}}, registry)
        require(result.get("status") == "error", "工具异常必须转为 error 状态")
        require(result.get("role") == "tool" and result.get("tool_call_id") == "c4", "错误消息契约不完整")
        require(str(result.get("content", "")).startswith("工具执行失败："), "错误内容缺少统一前缀")
    record("隔离工具自身异常", isolate_error)

def run_stream_chunks():
    run_generic()
    func = namespace.get("normalize_stream_chunks")
    def one_shot_generator():
        consumed = []
        def chunks():
            for item in ["逐", {"content": "步"}, None, "输出"]:
                consumed.append(item)
                yield item
        require(func(chunks()) == "逐步输出", "必须支持 model.stream() 返回的一次性迭代器")
        require(len(consumed) == 4, "流式迭代器没有被完整且仅一次消费")
    record("消费真实流式迭代器", one_shot_generator)

    class MessageChunk:
        def __init__(self, content):
            self.content = content
    record("读取 LangChain 消息片段对象", lambda: require(
        func([MessageChunk("Lang"), MessageChunk(None), MessageChunk("Chain")]) == "LangChain",
        "应读取 AIMessageChunk 风格对象的 content 属性"))

def run_tool_plan():
    func = namespace.get("run_tool_plan")
    require(callable(func), "必须定义 run_tool_plan(plan, registry, max_steps=5)")
    registry = {"add": lambda a, b: a + b, "mul": lambda a, b: a * b}
    def completed():
        result = func([{"name": "add", "args": {"a": 1, "b": 2}}, {"name": "mul", "args": {"a": 3, "b": 4}}], registry, 5)
        require(result.get("status") == "completed", "全部执行后状态应为 completed")
        require([x.get("observation") for x in result.get("trace", [])] == [3, 12], "观察结果或执行顺序错误")
        require(result.get("final_observation") == 12, "最终观察结果错误")
        require([x.get("step") for x in result["trace"]] == [1, 2], "轨迹步号错误")
    record("完成多步工具计划", completed)
    def unknown():
        result = func([{"name": "missing", "args": {}}], registry, 5)
        require(result.get("status") == "failed", "未知工具应使计划失败")
        require(len(result.get("trace", [])) == 1 and result["trace"][0].get("status") == "error", "失败轨迹缺失")
    record("未知工具立即停止", unknown)
    def stopped():
        result = func([{"name": "add", "args": {"a": 1, "b": 1}}, {"name": "mul", "args": {"a": 2, "b": 2}}], registry, 1)
        require(result.get("status") == "stopped", "达到上限后状态应为 stopped")
        require(result.get("final_observation") == 2, "停止前的有效观察应保留")
        require(len([x for x in result.get("trace", []) if x.get("status") == "success"]) == 1, "执行步数超过上限")
    record("最大步数阻止无限循环", stopped)
    def invalid_limit():
        try: func([], registry, 0)
        except ValueError: return
        raise AssertionError("非法 max_steps 必须抛出 ValueError")
    record("拒绝非法步数上限", invalid_limit)

def run_checkpoint():
    save = namespace.get("save_checkpoint")
    load = namespace.get("load_checkpoint")
    require(callable(save) and callable(load), "必须同时定义 save_checkpoint 与 load_checkpoint")
    def versioning():
        store = {}
        require(save(store, "t1", {"messages": ["u1"]}) == 1, "首个版本应为1")
        require(save(store, "t1", {"messages": ["u1", "a1"]}) == 2, "版本未递增")
        require(load(store, "t1") == {"version": 2, "state": {"messages": ["u1", "a1"]}}, "没有读取最新检查点")
    record("同一线程版本递增", versioning)
    def isolation():
        store = {}
        save(store, "A", {"value": "a"}); save(store, "B", {"value": "b"})
        require(load(store, "A")["state"]["value"] == "a", "线程A状态被串改")
        require(load(store, "B")["state"]["value"] == "b", "线程B状态被串改")
    record("不同线程互相隔离", isolation)
    def defensive_copy():
        store = {}; state = {"messages": [{"role": "user", "content": "hi"}]}
        save(store, "t", state)
        state["messages"][0]["content"] = "changed"
        loaded = load(store, "t")
        require(loaded["state"]["messages"][0]["content"] == "hi", "保存时未复制嵌套状态")
        loaded["state"]["messages"].append({"role": "assistant", "content": "x"})
        require(len(load(store, "t")["state"]["messages"]) == 1, "读取结果与内部快照共享对象")
    record("快照读写均使用安全副本", defensive_copy)
    record("不存在的线程返回None", lambda: require(load({}, "missing") is None, "不存在时应返回None"))

def run_sqlalchemy_query():
    setup = namespace.get("setup_order_db")
    query = namespace.get("query_orders")
    require(callable(setup), "必须定义 setup_order_db(db_path)")
    require(callable(query), "必须定义 query_orders(session, **filters)")
    import tempfile, os
    tmp = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp, "orders.db")
        ret = setup(db_path)
        if isinstance(ret, tuple) and len(ret) == 2:
            engine, Session = ret
        else:
            engine = ret
            Session = namespace.get("Session") or namespace.get("sessionmaker")
        require(Session is not None and callable(Session), "必须导出 Session = sessionmaker(bind=engine)")
        session = Session()
        try:
            orders = query(session)
        except Exception:
            orders = []
        if not orders:
            from sqlalchemy import Column, Integer, String, Float
            from sqlalchemy.orm import declarative_base
            Base = declarative_base()
            class _Order(Base):
                __tablename__ = 'orders'
                id = Column(Integer, primary_key=True)
                order_id = Column(String(20), unique=True, nullable=False)
                customer_name = Column(String(50), nullable=False)
                customer_phone = Column(String(20))
                product = Column(String(100), nullable=False)
                category = Column(String(30), nullable=False)
                amount = Column(Float, nullable=False)
                status = Column(String(20), nullable=False, default='pending')
                carrier = Column(String(30))
                eta = Column(String(20))
                created_at = Column(String(20), nullable=False)
            try:
                Base.metadata.create_all(engine)
            except Exception:
                pass
            samples = [
                _Order(order_id='ORD-20260730-0001', customer_name='张三', customer_phone='13800001111',
                       product='Python编程从入门到实践', category='图书', amount=89.00, status='delivered',
                       carrier='顺丰速运', eta='2026-07-25', created_at='2026-07-20'),
                _Order(order_id='ORD-20260730-0002', customer_name='李四', customer_phone='13800002222',
                       product='AI智能体开发实战', category='图书', amount=199.00, status='shipped',
                       carrier='中通快递', eta='2026-08-05', created_at='2026-07-28'),
                _Order(order_id='ORD-20260730-0003', customer_name='王五', customer_phone='13800003333',
                       product='机械键盘K850', category='电子产品', amount=459.00, status='paid',
                       carrier=None, eta=None, created_at='2026-07-30'),
                _Order(order_id='ORD-20260730-0004', customer_name='赵六', customer_phone='13800004444',
                       product='蓝牙耳机Pro', category='电子产品', amount=299.00, status='refunding',
                       carrier=None, eta=None, created_at='2026-07-29'),
                _Order(order_id='ORD-20260730-0005', customer_name='孙七', customer_phone='13800005555',
                       product='有机绿茶礼盒', category='食品', amount=128.00, status='pending',
                       carrier=None, eta=None, created_at='2026-08-01'),
                _Order(order_id='ORD-20260730-0006', customer_name='周八', customer_phone='13800006666',
                       product='Python教程进阶版', category='图书', amount=149.00, status='shipped',
                       carrier='京东物流', eta='2026-08-03', created_at='2026-07-31'),
                _Order(order_id='ORD-20260730-0007', customer_name='吴九', customer_phone='13800007777',
                       product='智能手表S3', category='电子产品', amount=899.00, status='delivered',
                       carrier='顺丰速运', eta='2026-07-22', created_at='2026-07-18'),
                _Order(order_id='ORD-20260730-0008', customer_name='郑十', customer_phone='13800008888',
                       product='纯棉T恤三件装', category='服装', amount=199.00, status='cancelled',
                       carrier=None, eta=None, created_at='2026-08-02'),
                _Order(order_id='ORD-20260730-0009', customer_name='张三', customer_phone='13800001111',
                       product='数据分析实战', category='图书', amount=79.00, status='paid',
                       carrier=None, eta=None, created_at='2026-08-01'),
                _Order(order_id='ORD-20260730-0010', customer_name='李白', customer_phone='13800009999',
                       product='深度学习框架', category='图书', amount=259.00, status='refunded',
                       carrier=None, eta=None, created_at='2026-07-15'),
            ]
            session.add_all(samples)
            session.commit()
    finally:
        pass
    def run(filters):
        result = query(session, **filters)
        require(isinstance(result, list), f"返回必须是列表，得到{type(result).__name__}")
        for item in result:
            require(isinstance(item, dict), "每条结果必须是字典")
            for key in ["id", "order_id", "customer_name", "product", "category", "amount", "status"]:
                require(key in item, f"结果缺少字段 {key}")
    def all_paid():
        r = query(session, status="paid")
        require(len(r) == 2, f"已支付订单应为2条，得到{len(r)}")
        require(all(o["status"] == "paid" for o in r), "状态过滤不生效")
    record("按状态过滤订单", all_paid)
    def by_customer():
        r = query(session, customer_name="张三")
        require(len(r) == 2, f"张三应有2条订单，得到{len(r)}")
        require(all("张三" in o["customer_name"] for o in r), "客户名模糊查询不生效")
    record("按客户名模糊查询", by_customer)
    def min_amount():
        r = query(session, min_amount=150.0)
        require(len(r) == 6, f"金额>=150应为6条，得到{len(r)}")
        require(all(o["amount"] >= 150.0 for o in r), "金额过滤不生效")
    record("按最小金额过滤", min_amount)
    def combined():
        r = query(session, status="paid", min_amount=100.0)
        require(len(r) == 1, f"已支付且金额>=100应为1条，得到{len(r)}")
        require(all(o["status"] == "paid" and o["amount"] >= 100.0 for o in r), "组合过滤不生效")
    record("组合过滤条件", combined)
    def empty():
        r = query(session, customer_name="不存在")
        require(r == [], "不存在的客户应返回空列表")
    record("无匹配时返回空列表", empty)
    def no_filter():
        r = query(session)
        require(len(r) == 10, f"无过滤应返回全部10条，得到{len(r)}")
    record("无过滤条件返回全部订单", no_filter)
    def by_order_id():
        r = query(session, order_id="ORD-20260730-0001")
        require(len(r) == 1, f"精确编号查询应为1条，得到{len(r)}")
        require(r[0]["customer_name"] == "张三", "订单客户不匹配")
        require(r[0]["carrier"] == "顺丰速运", "快递公司不匹配")
    record("按订单编号精确查询", by_order_id)
    def by_category():
        r = query(session, category="图书")
        require(len(r) == 5, f"图书类别应为5条，得到{len(r)}")
        require(all(o["category"] == "图书" for o in r), "类别过滤不生效")
    record("按商品类别过滤", by_category)
    def by_carrier():
        r = query(session, carrier="顺丰速运")
        require(len(r) == 2, f"顺丰快递应为2条，得到{len(r)}")
        require(all(o["carrier"] == "顺丰速运" for o in r), "快递过滤不生效")
    record("按快递公司过滤", by_carrier)
    def amount_range():
        r = query(session, min_amount=100.0, max_amount=200.0)
        require(len(r) == 4, f"金额100-200范围应为4条，得到{len(r)}")
        require(all(100.0 <= o["amount"] <= 200.0 for o in r), "金额范围过滤不生效")
    record("金额范围过滤", amount_range)
    session.close()

mode = spec.get("mode", "generic")
if mode == "tool_call": run_tool_call()
elif mode == "tool_plan": run_tool_plan()
elif mode == "checkpoint": run_checkpoint()
elif mode == "stream_chunks": run_stream_chunks()
elif mode == "sqlalchemy_query": run_sqlalchemy_query()
else: run_generic()

print("__JUDGE_RESULT__" + json.dumps(cases, ensure_ascii=False))
'''


def judge_submission(exercise_id: str, code: str, timeout: int = 6) -> dict:
    started = time.perf_counter()
    if not is_flagship_exercise(exercise_id):
        raise ValueError(f"{exercise_id} 不是项目制私有场景判题任务")

    policy_error = _policy_error(code)
    expected_total = max(
        len(SPECS[exercise_id].get("cases", [])) + int(SPECS[exercise_id].get("extra_cases", 0)),
        4,
    )
    if policy_error:
        return {
            "passed": False, "total": expected_total, "passed_count": 0,
            "compile_error": policy_error, "results": [],
            "execution_time": round(time.perf_counter() - started, 3),
            "judge_mode": "server_private_cases",
        }

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            solution_path = Path(temp_dir) / "submission.py"
            spec_path = Path(temp_dir) / "spec.json"
            runner_path = Path(temp_dir) / "runner.py"
            solution_path.write_text(code, encoding="utf-8")
            spec_path.write_text(json.dumps(SPECS[exercise_id], ensure_ascii=False), encoding="utf-8")
            runner_path.write_text(RUNNER, encoding="utf-8")
            proc = subprocess.run(
                [os.environ.get("PYTHON_PATH", "python"), "-I", "-X", "utf8", str(runner_path), str(solution_path), str(spec_path)],
                cwd=temp_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
            )
        marker_lines = [line for line in (proc.stdout or "").splitlines() if line.startswith("__JUDGE_RESULT__")]
        if proc.returncode != 0 or not marker_lines:
            error_lines = (proc.stderr or proc.stdout or "提交代码未能完成执行").strip().splitlines()
            error = error_lines[-1][:300] if error_lines else "提交代码未能完成执行"
            return {
                "passed": False, "total": expected_total, "passed_count": 0,
                "compile_error": error, "results": [],
                "execution_time": round(time.perf_counter() - started, 3),
                "judge_mode": "server_private_cases",
            }
        raw_results = json.loads(marker_lines[-1].removeprefix("__JUDGE_RESULT__"))
        results = [{"case_index": index, **item} for index, item in enumerate(raw_results, 1)]
        passed_count = sum(1 for item in results if item["passed"])
        return {
            "passed": passed_count == len(results), "total": len(results), "passed_count": passed_count,
            "compile_error": None, "results": results,
            "execution_time": round(time.perf_counter() - started, 3),
            "judge_mode": "server_private_cases",
        }
    except subprocess.TimeoutExpired:
        return {
            "passed": False, "total": expected_total, "passed_count": 0,
            "compile_error": f"执行超时（>{timeout} 秒）", "results": [],
            "execution_time": round(time.perf_counter() - started, 3), "judge_mode": "server_private_cases",
        }
    except Exception as exc:
        return {
            "passed": False, "total": expected_total, "passed_count": 0,
            "compile_error": f"判题执行失败：{str(exc)[:240]}", "results": [],
            "execution_time": round(time.perf_counter() - started, 3), "judge_mode": "server_private_cases",
        }
