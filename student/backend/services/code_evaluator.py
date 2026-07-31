"""
真实沙箱代码评测引擎 v2.0 — 对标头歌 Educoder 判题机制

四层校验流程:
  Layer 1: 语法预编译 — 捕获 SyntaxError/IndentationError/NameError
  Layer 2: 空逻辑拦截 — 检测纯 pass/空函数体，直接判定"未实现核心逻辑"
  Layer 3: 沙箱执行 + 目标函数/类动态查找
  Layer 4: 多组测试用例遍历 → 逐条比对返回值/对象状态 → 全部通过才算成功

安全措施: 受限内置函数 / 递归深度限制 / 执行超时(10s) / 输出捕获
"""
import sys, os, json, ast, io, threading, time, re as _re

# ── 安全内置函数白名单 ───────────────────────────────────────
_SAFE_BUILTINS = {
    'True','False','None','abs','all','any','bin','bool','bytearray','bytes',
    'callable','chr','classmethod','complex','delattr','dict','dir','divmod',
    'enumerate','filter','float','format','frozenset','getattr','hasattr',
    'hash','hex','id','int','isinstance','issubclass','iter','len','list',
    'locals','map','max','memoryview','min','next','object','oct','ord',
    'pow','print','property','range','repr','reversed','round','set',
    'setattr','slice','sorted','staticmethod','str','sum','super','tuple',
    'type','vars','zip',
    # CPython 内部函数 — 类/函数定义必需
    '__build_class__',
    # 异常类 — 测试代码 try/except 必需
    'Exception', 'BaseException',
    'TypeError', 'ValueError', 'KeyError', 'IndexError', 'NameError',
    'AttributeError', 'AssertionError', 'StopIteration', 'ZeroDivisionError',
    'ImportError', 'OSError', 'RuntimeError', 'SyntaxError', 'IndentationError',
    'LookupError', 'ArithmeticError', 'UnboundLocalError', 'NotImplementedError',
    'OverflowError', 'RecursionError', 'ReferenceError', 'UnicodeError',
    'SystemExit', 'KeyboardInterrupt',
}

# ── 空逻辑检测阈值 ───────────────────────────────────────────
# 用户代码中至少需要这么多行非注释/非空/非pass的有效代码
_MIN_EFFECTIVE_LINES = 1


def _make_safe_globals():
    import builtins
    safe = {
        '__builtins__': {k: getattr(builtins, k) for k in _SAFE_BUILTINS if hasattr(builtins, k)},
        '__name__': '__main__',
        '__build_class__': getattr(builtins, '__build_class__', None),
    }
    return safe


# ═══════════════════════════════════════════════════════════════
# 主评测入口
# ═══════════════════════════════════════════════════════════════

def evaluate_code(user_code: str, exercise_meta: dict) -> dict:
    """
    真实评测用户代码

    exercise_meta = {
        exercise_type: 'function' | 'class',
        target_function: str (函数名 或 类名),
        test_cases: [{args:[...], expected:any, description:str,
                      state_checks: [{attr: ..., method: ..., expected: ...}]}],
    }

    返回: { passed, total, passed_count, layer, compile_error,
            results: [{case_index, description, input_args, expected, actual, passed, error}] }
    """
    start = time.time()
    exercise_type = exercise_meta.get('exercise_type', 'function')
    target = exercise_meta.get('target_function', '')
    test_cases = exercise_meta.get('test_cases', [])
    locked_code = exercise_meta.get('locked_code', '')

    # 用户代码来自编辑器，已包含类声明+函数签名+实现+测试代码
    # locked_code 仅用于前端展示锁定区域，评测时直接使用用户完整代码
    full_code = user_code

    # ── Layer 1: 语法预编译校验 ──
    try:
        compile(full_code, '<submission>', 'exec')
    except SyntaxError as e:
        return _fail_result(test_cases, f'语法错误 (第{e.lineno}行): {e.msg}', 1, start)

    # ── Layer 2: 空逻辑拦截 ──
    pass_check = _check_empty_implementation(user_code)
    if pass_check['is_empty']:
        return _fail_result(test_cases,
            f'❌ 未实现核心逻辑，禁止空占位提交！\n'
            f'  {pass_check["reason"]}\n'
            f'  请将标记区域内的 pass 替换为实际业务代码。', 2, start)

    # ── Layer 3: 沙箱执行 + 动态查找目标 ──
    exec_result = _exec_with_timeout(full_code, timeout_sec=10)
    if exec_result['error']:
        return _fail_result(test_cases, exec_result['error'], 3, start)

    exec_locals = exec_result['locals']
    exec_globals = exec_result['globals']

    # 查找目标（函数 或 类）
    target_obj = _find_target(target, exec_locals, exec_globals)
    if isinstance(target_obj, str):
        # target_obj 是错误消息字符串
        return _fail_result(test_cases, target_obj, 3, start)

    # ── Layer 4: 多用例遍历 ──
    if exercise_type == 'output':
        return _evaluate_output_type(test_cases, exec_result['stdout'], start)

    return _evaluate_function_type(test_cases, target_obj, target, exercise_type, start)


# ═══════════════════════════════════════════════════════════════
# Layer 2: 空逻辑检测
# ═══════════════════════════════════════════════════════════════

def _check_empty_implementation(code: str) -> dict:
    """
    检测用户代码是否为空实现（纯 pass 或无有效逻辑）

    判断规则:
    1. 去除注释、空行、docstring 后，统计有效代码行
    2. 有效代码行 = 非 pass、非 def/class 声明、非 return None/pass 的语句
    3. 有效行数 < _MIN_EFFECTIVE_LINES → 判定为空实现
    """
    lines = code.split('\n')
    effective_lines = 0
    in_docstring = False

    for line in lines:
        stripped = line.strip()

        # 跳过空行
        if not stripped:
            continue

        # 处理多行文档字符串
        if stripped.startswith('"""') or stripped.startswith("'''"):
            if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                continue  # 单行 docstring
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue

        # 跳过注释
        if stripped.startswith('#'):
            continue

        # 跳过 def/class 声明行
        if stripped.startswith('def ') or stripped.startswith('class '):
            continue

        # 跳过装饰器
        if stripped.startswith('@'):
            continue

        # 纯 pass 不计入有效行
        if stripped == 'pass':
            continue

        # 只有 return 后面跟 None 或空 → 不计入
        if stripped == 'return' or stripped == 'return None':
            continue

        # 其他代码计入有效行
        effective_lines += 1

    if effective_lines < _MIN_EFFECTIVE_LINES:
        return {
            'is_empty': True,
            'reason': f'检测到用户代码中仅有 {effective_lines} 行有效逻辑代码（排除注释/pass/函数声明后）。需要至少 {_MIN_EFFECTIVE_LINES} 行业务代码。'
        }
    return {'is_empty': False, 'reason': ''}


# ═══════════════════════════════════════════════════════════════
# Layer 3: 沙箱执行 + 目标查找
# ═══════════════════════════════════════════════════════════════

def _exec_with_timeout(code: str, timeout_sec: int = 10) -> dict:
    """在受限环境中执行代码，带超时控制"""
    result = {'error': None, 'stdout': '', 'locals': {}, 'globals': {}}
    finished = threading.Event()

    def run_code():
        safe_globals = _make_safe_globals()
        safe_locals = {}
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        sys.setrecursionlimit(500)

        try:
            exec(code, safe_globals, safe_locals)
        except Exception as e:
            # 格式化错误信息，提取行号
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            if tb:
                last = tb[-1]
                result['error'] = f'{type(e).__name__}: {str(e)} (第{last.lineno}行)'
            else:
                result['error'] = f'{type(e).__name__}: {str(e)}'
        finally:
            result['stdout'] = sys.stdout.getvalue()
            sys.stdout = old_stdout
            sys.setrecursionlimit(1000)

            # 提取可调用对象和类
            for k, v in list(safe_globals.items()) + list(safe_locals.items()):
                if callable(v) and not k.startswith('_'):
                    result['globals'][k] = v
                elif isinstance(v, type) and not k.startswith('_'):
                    result['globals'][k] = v
            result['locals'] = safe_locals
        finished.set()

    thread = threading.Thread(target=run_code, daemon=True)
    thread.start()
    thread.join(timeout=timeout_sec)

    if not finished.is_set():
        result['error'] = f'⏱ 执行超时 (>{timeout_sec}秒)，请检查是否存在死循环或无限递归'

    return result


def _find_target(target: str, exec_locals: dict, exec_globals: dict):
    """
    动态查找目标函数或类
    返回: callable/class 或 错误字符串
    """
    if not target:
        return '题目未配置目标函数名 (target_function)'

    obj = exec_locals.get(target) or exec_globals.get(target)
    if obj is None:
        # 尝试在类内部查找方法
        for v in list(exec_locals.values()) + list(exec_globals.values()):
            if isinstance(v, type) and hasattr(v, target):
                obj = getattr(v, target)
                break

    if obj is None:
        return f'未找到 "{target}()"。请确认函数/类名拼写正确，且未被注释或删除。'
    return obj


# ═══════════════════════════════════════════════════════════════
# Layer 4: 多用例遍历 + 比对
# ═══════════════════════════════════════════════════════════════

def _evaluate_function_type(test_cases, target_obj, target, exercise_type, start):
    """函数型/类方法型评测：逐用例调用 + 比对返回值 + 对象状态"""
    results = []
    passed_count = 0
    is_class = exercise_type == 'class'

    for idx, tc in enumerate(test_cases):
        case_result = {
            'case_index': idx + 1,
            'description': tc.get('description', f'用例{idx+1}'),
            'input_args': tc.get('args', []),
            'expected': tc.get('expected'),
            'actual': None,
            'passed': False,
            'error': None
        }

        args = tc.get('args', [])
        if not isinstance(args, list):
            args = [args]

        try:
            if is_class:
                # 类题型：先实例化，再调用方法，最后检查对象状态
                actual = _evaluate_class_testcase(target_obj, args, tc)
            else:
                # 函数题型：直接调用
                actual = target_obj(*args)
            case_result['actual'] = _to_display(actual)

            if _match(actual, tc.get('expected')):
                case_result['passed'] = True
                passed_count += 1
        except Exception as e:
            case_result['error'] = f'{type(e).__name__}: {str(e)}'
            case_result['actual'] = None

        results.append(case_result)

    return _build_result(test_cases, results, passed_count, start)


def _evaluate_class_testcase(cls, args, tc):
    """执行类题型的测试用例：实例化 → 调用方法序列 → 检查状态 → 返回最终结果"""
    instance = cls(*args) if args else cls()

    # 执行方法调用序列
    method_calls = tc.get('method_calls', [])
    last_result = None
    for mc in method_calls:
        method_name = mc.get('method', '')
        method_args = mc.get('args', [])
        if not isinstance(method_args, list):
            method_args = [method_args]
        m = getattr(instance, method_name, None)
        if m is None:
            raise AttributeError(f'类中未找到方法 "{method_name}()"')
        last_result = m(*method_args)

    # 检查对象状态
    state_checks = tc.get('state_checks', [])
    for sc in state_checks:
        attr_name = sc.get('attr', '')
        check_method = sc.get('method', '')
        expected = sc.get('expected')

        if attr_name:
            actual_val = getattr(instance, attr_name, None)
        elif check_method:
            m = getattr(instance, check_method, None)
            actual_val = m() if m else None
        else:
            continue

        if not _match(actual_val, expected):
            return actual_val  # 状态不匹配，返回实际值用于比对

    return last_result


def _evaluate_output_type(test_cases, stdout_output, start):
    """输出型题目：比对控制台打印"""
    results = []
    passed_count = 0
    for idx, tc in enumerate(test_cases):
        expected = str(tc.get('expected', ''))
        passed = expected in stdout_output
        if passed:
            passed_count += 1
        results.append({
            'case_index': idx + 1,
            'description': tc.get('description', f'用例{idx+1}'),
            'expected': expected[:300],
            'actual': stdout_output[:500],
            'passed': passed,
            'error': None
        })
    return _build_result(test_cases, results, passed_count, start)


# ═══════════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════════

def _fail_result(test_cases, error_msg, layer, start):
    return {
        'passed': False, 'total': len(test_cases), 'passed_count': 0,
        'layer': layer, 'compile_error': error_msg,
        'results': [], 'execution_time': round(time.time() - start, 3)
    }


def _build_result(test_cases, results, passed_count, start):
    return {
        'passed': passed_count == len(test_cases) and len(test_cases) > 0,
        'total': len(test_cases),
        'passed_count': passed_count,
        'layer': 4,
        'compile_error': None,
        'results': results,
        'execution_time': round(time.time() - start, 3)
    }


def _match(actual, expected) -> bool:
    """深度比较实际值与期望值"""
    if actual == expected:
        return True
    if isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        return abs(actual - expected) < 1e-9
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.strip() == expected.strip()
    if isinstance(actual, (dict, list)) and isinstance(expected, (dict, list)):
        try:
            return json.dumps(actual, sort_keys=True, ensure_ascii=False) == \
                   json.dumps(expected, sort_keys=True, ensure_ascii=False)
        except Exception:
            pass
    return str(actual) == str(expected)


def _to_display(value) -> str:
    if value is None:
        return 'None'
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)[:500]
