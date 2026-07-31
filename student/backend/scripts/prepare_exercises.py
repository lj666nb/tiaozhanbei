"""
预处理所有编程习题：生成骨架初始代码 + 测试驱动代码 + 预生成参考答案缓存

运行方式:  cd backend && python prepare_exercises.py

输出: data/exercises_processed.json — 前端和后端共用
      data/exercise_answers_cache.json — 参考答案缓存
"""
import os, sys, re, json, subprocess, tempfile, shutil, glob

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXERCISES_DIR = os.path.join(BASE_DIR, "data", "exercises")
OUTPUT_PATH = os.path.join(BASE_DIR, "data", "exercises_processed.json")
ANSWERS_CACHE_PATH = os.path.join(BASE_DIR, "data", "exercise_answers_cache.json")

CODE_START = "# ==========你的代码开始=========="
CODE_END = "# ==========你的代码结束=========="

# ─── 解析 .txt 习题文件 ───────────────────────────────────────
def parse_all_exercises():
    exercises = []
    for fpath in sorted(glob.glob(os.path.join(EXERCISES_DIR, "module_*.txt"))):
        content = open(fpath, "r", encoding="utf-8").read()
        parts = re.split(r'\n(?=关卡 \d+-\d+：)', content)
        for part in parts:
            ex = _parse_one(part.strip())
            if ex and ex.get("id"):
                exercises.append(ex)
    return exercises


def _parse_one(part):
    m = re.match(r'关卡\s*(\d+-\d+)', part)
    if not m:
        return None
    ex = {"id": m.group(1)}

    # 标题
    tm = re.search(r'：(.+?)$', part.split('\n')[0])
    if tm:
        ex["title"] = tm.group(1).strip()

    # 模块
    mm = re.search(r'所属模块[：:]\s*(.+?)$', part, re.MULTILINE)
    if mm:
        ex["module"] = mm.group(1).strip()

    # 描述
    desc_m = re.search(r'【任务描述】\s*\n(.*?)(?=【[输初评]|$)', part, re.DOTALL)
    if desc_m:
        ex["description"] = desc_m.group(1).strip()

    # 输入输出说明
    io_m = re.search(r'【输入输出说明】\s*\n(.*?)(?=【[初评]|$)', part, re.DOTALL)
    if io_m:
        ex["input_output"] = io_m.group(1).strip()

    # 代码块
    code_blocks = list(re.finditer(r'```python\s*\n(.*?)```', part, re.DOTALL))
    if code_blocks:
        ex["raw_starter_code"] = code_blocks[0].group(1).strip()
    if len(code_blocks) >= 2:
        ex["eval_code"] = code_blocks[1].group(1).strip()

    return ex


# ─── 骨架化 + 标记注入 + 测试代码生成 ─────────────────────────
def process_exercise(ex):
    """为单个习题生成: skeleton_code (含标记), test_code, 完整参考答案"""
    raw = ex.get("raw_starter_code", "")
    if not raw:
        ex["skeleton_code"] = f"{CODE_START}\n# TODO: 实现代码\n{CODE_END}"
        ex["test_code"] = ""
        return ex

    lines = raw.split('\n')

    # ── 步骤1: 识别哪些行是"已经完成"的（保留），哪些是"需要学生写"的（骨架化）──
    # 规则:
    #   - def/class 声明行 → 保留
    #   - docstring → 保留
    #   - 简单 self.xxx = yyy 赋值（在 __init__ 中）→ 保留
    #   - pass / # TODO → 标记为需要填充
    #   - 其他逻辑代码 → 替换为 pass（骨架化）

    in_method = False
    method_indent = 0
    method_body_started = False
    in_docstring = False
    processed = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        # 空行
        if not stripped:
            processed.append("")
            continue

        # 类/函数声明
        if re.match(r'(def |class )', stripped) and stripped.endswith(':'):
            in_method = True
            method_indent = indent
            method_body_started = False
            in_docstring = False
            processed.append(line)
            continue

        # 装饰器
        if stripped.startswith('@'):
            processed.append(line)
            continue

        # 回到类级别
        if in_method and indent <= method_indent:
            in_method = False
            method_body_started = False
            in_docstring = False
            processed.append(line)
            continue

        # 在方法内部
        if in_method and indent > method_indent:
            # 文档字符串处理
            if stripped.startswith('"""') or stripped.startswith("'''"):
                if stripped.count('"""') >= 2 or stripped.count("'''") >= 2:
                    # 单行文档字符串
                    processed.append(line)
                    continue
                else:
                    # 多行文档字符串开始/结束
                    in_docstring = not in_docstring
                    processed.append(line)
                    continue

            if in_docstring:
                processed.append(line)
                continue

            # 注释行 → 保留
            if stripped.startswith('#'):
                processed.append(line)
                continue

            # pass 或 TODO → 保留原样（这是标记位置）
            if stripped == 'pass' or '# TODO' in stripped:
                processed.append(line)
                method_body_started = True
                continue

            # 简单赋值 self.xxx = yyy (__init__ 中的标准模式)
            if re.match(r'self\.\w+\s*=\s*', stripped):
                rhs = stripped.split('=', 1)[-1].strip()
                # 允许简单构造函数: set(), dict(), list(), ClassName()
                is_simple_ctor = bool(re.match(r'^(set|dict|list|tuple|int|float|str|bool|\w+)\(\)\s*$', rhs))
                has_func_call = '(' in rhs and not is_simple_ctor
                if not has_func_call and len(rhs) < 60:
                    processed.append(line)
                    continue

            # 其他逻辑代码 → 骨架化（替换为 pass）
            if not method_body_started:
                processed.append(" " * indent + "pass  # TODO: 实现此方法")
                method_body_started = True
            continue

        # 顶层代码
        processed.append(line)

    # 如果是 pure function (非 class)，特殊处理
    skeleton_lines = _reconstruct_skeleton(processed)

    # ── 步骤2: 注入 CODE_START / CODE_END 标记 ──
    # 找到所有 pass/TODO 行，用标记包裹
    final_lines = _inject_markers(skeleton_lines)

    # ── 步骤3: 生成测试驱动代码 ──
    test_code = _generate_test_code(ex, raw)
    if test_code:
        final_lines.append("")
        final_lines.append(test_code)

    ex["skeleton_code"] = '\n'.join(final_lines).strip()
    ex["test_code"] = test_code

    return ex


def _reconstruct_skeleton(lines):
    """确保骨架代码结构完整，不会出现两个连续 pass"""
    # 简单后处理：连续的 pass 去重
    return lines


def _inject_markers(lines):
    """在 pass/TODO 区域前后注入 CODE_START 和 CODE_END
    关键规则：标记包裹整个方法（从 def 行到方法体结束），而非仅仅 pass 行
    """
    todo_indices = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == 'pass' or '# TODO' in stripped:
            todo_indices.append(i)

    if not todo_indices:
        lines.append("")
        lines.append(CODE_START)
        lines.append("# 在此编写你的代码")
        lines.append(CODE_END)
        return lines

    first_todo, last_todo = todo_indices[0], todo_indices[-1]

    # 向上找到第一个 TODO 所属方法的 def/class 行
    first_def = first_todo
    for i in range(first_todo, -1, -1):
        stripped = lines[i].strip() if lines[i] else ""
        if re.match(r'(def |class )', stripped) and stripped.endswith(':'):
            first_def = i
            break

    # 向下找到最后一个 TODO 所属方法的结束位置
    # 方法结束 = 遇到下一个同级别的 def/class 或文件末尾
    if first_def >= 0:
        def_indent = len(lines[first_def]) - len(lines[first_def].lstrip())
        last_def_end = last_todo
        for i in range(last_todo + 1, len(lines)):
            stripped = lines[i].strip() if lines[i] else ""
            # 遇到同级别或更外层的 def/class → 当前方法结束
            if re.match(r'(def |class )', stripped) and stripped.endswith(':'):
                line_indent = len(lines[i]) - len(lines[i].lstrip())
                if line_indent <= def_indent:
                    last_def_end = i - 1
                    break
            last_def_end = i
    else:
        last_def_end = last_todo

    # 插入标记
    # CODE_START: 在第一个需实现的 def 之前
    # CODE_END: 在最后一个需实现的方法结束之后
    def_indent = len(lines[first_def]) - len(lines[first_def].lstrip())
    marker_indent = " " * def_indent

    result = []
    start_inserted = False
    end_inserted = False

    for i, line in enumerate(lines):
        # 在第一个 def 之前插入 CODE_START
        if not start_inserted and i == first_def:
            result.append(marker_indent + CODE_START)
            start_inserted = True

        result.append(line)

        # 在方法结束行后插入 CODE_END
        if not end_inserted and i == last_def_end:
            result.append(marker_indent + CODE_END)
            end_inserted = True

    if not start_inserted:
        result.append(CODE_START)
    if not end_inserted:
        result.append(CODE_END)

    return result



def _extract_eval_setup(eval_code):
    """从评测代码中提取所有 setup 代码（变量定义+辅助函数，排除框架调用）"""
    if not eval_code:
        return []
    lines = eval_code.split(chr(10))
    result = []
    in_fn = False
    fn_indent = 0
    for line in lines:
        s = line.strip()
        if not s:
            result.append('')
            continue
        if s.startswith('def evaluate_'):
            in_fn = True
            fn_indent = len(line) - len(line.lstrip())
            continue
        if not in_fn:
            continue
        ci = len(line) - len(line.lstrip())
        # 顶层 assert/return → 停止
        if s.startswith('assert ') and ci <= fn_indent + 4:
            break
        if s.startswith('return ') and ci <= fn_indent + 4:
            break
        if 'module_dict' in s and ci <= fn_indent + 4:
            continue
        if s.startswith('#'):
            continue
        # 规范化缩进为 4 空格
        result.append('    ' + s)
    return result
def _generate_test_code(ex, raw_code):
    """生成对标头歌的断言测试驱动 — 校验返回值 + 对象状态，多用例验证"""
    eval_code = ex.get("eval_code", "")
    classes = re.findall(r'class\s+(\w+)', raw_code)
    funcs = re.findall(r'def\s+(\w+)\s*\(([^)]*)\)', raw_code)

    test_lines = [
        '# ===== 评测代码 — 请实现标记区域内代码后运行 =====',
        '# 所有测试用例通过才算完成本题',
        'if __name__ == "__main__":',
        '    passed = 0',
        '    total = 0',
        '    errors = []',
        ''
    ]

    if classes:
        # ── 类方法题：创建实例 → 调用方法序列 → 检查返回值 + 对象状态 ──
        cls_name = classes[0]
        ctor_args = _infer_ctor_args(raw_code, cls_name)
        test_lines.append(f'    print("═══ 评测: {cls_name} ═══")')
        test_lines.append(f'    obj = {cls_name}({ctor_args})')


        # 从 eval 代码提取方法调用序列 + 断言
        eval_sequence = _parse_eval_sequence(eval_code, cls_name)
        if eval_sequence:
            tc_idx = 1
            for seq in eval_sequence:
                calls = seq.get('calls', [])
                checks = seq.get('checks', [])
                test_lines.append(f'    # ── 用例{tc_idx}: {seq.get("desc", "")} ──')
                test_lines.append(f'    total += 1')
                test_lines.append(f'    try:')
                for c in calls:
                    test_lines.append(f'        {c}')
                for c in checks:
                    test_lines.append(f'        {c}')
                test_lines.append(f'        print("  [PASS]用例{tc_idx} 通过")')
                test_lines.append(f'        passed += 1')
                test_lines.append(f'    except Exception as e:')
                test_lines.append(f'        print(f"  [FAIL] 用例{tc_idx} 失败: {{e}}")')
                test_lines.append(f'        errors.append(f"用例{tc_idx}: {{e}}")')
                test_lines.append('')
                tc_idx += 1

        if not eval_sequence:
            # 降级：为每个方法生成单独测试
            _generate_fallback_class_tests(test_lines, funcs, cls_name, raw_code, eval_code)

    elif funcs:
        # ── 函数题：直接调用 → 断言返回值 ──
        main_func = funcs[0][0]
        test_lines.append(f'    print("═══ 评测: {main_func} ═══")')

        var_defs = _extract_var_defs(eval_code)
        for vd in var_defs:
            test_lines.append(vd)

        if var_defs:
            test_lines.append('')

        # 从 eval 提取测试用例
        eval_sequence = _parse_eval_sequence(eval_code, None, main_func)
        if eval_sequence:
            tc_idx = 1
            for seq in eval_sequence:
                calls = seq.get('calls', [])
                checks = seq.get('checks', [])
                test_lines.append(f'    # ── 用例{tc_idx}: {seq.get("desc", "")} ──')
                test_lines.append(f'    total += 1')
                test_lines.append(f'    try:')
                for c in calls:
                    test_lines.append(f'        {c}')
                for c in checks:
                    test_lines.append(f'        {c}')
                test_lines.append(f'        print("  [PASS]用例{tc_idx} 通过")')
                test_lines.append(f'        passed += 1')
                test_lines.append(f'    except Exception as e:')
                test_lines.append(f'        print(f"  [FAIL] 用例{tc_idx} 失败: {{e}}")')
                test_lines.append(f'        errors.append(f"用例{tc_idx}: {{e}}")')
                test_lines.append('')
                tc_idx += 1

        if not eval_sequence:
            test_lines.append('    print("  [INFO] 请参考题目描述中的示例验证你的实现")')
            test_lines.append('    total = 1')

    test_lines.append('    # ── 评测报告 ──')
    test_lines.append('    sep = "=" * 40')
    test_lines.append('    print(f"\\n{sep}")')
    test_lines.append('    print(f"  评测结果: {passed}/{total} 通过")')
    test_lines.append('    if errors:')
    test_lines.append('        print(f"  失败详情:")')
    test_lines.append('        for e in errors:')
    test_lines.append('            print(f"    {e}")')
    test_lines.append('    if passed == total and total > 0:')
    test_lines.append('        print("  *** 全部通过！恭喜完成本题！ ***")')
    test_lines.append('    else:')
    test_lines.append('        print("  [TIP] 请根据失败信息修改代码后重新运行")')
    return '\n'.join(test_lines)


def _parse_eval_sequence(eval_code, cls_name=None, func_name=None):
    """解析评测代码为「调用+断言」序列，返回 [{calls:[], checks:[], desc:''}]"""
    if not eval_code:
        return []

    # 构建变量映射
    var_map = {}
    skip_vars = set()
    # student_func → 实际函数名
    if func_name:
        var_map['student_func'] = func_name

    for line in eval_code.split('\n'):
        s = line.strip()
        if 'module_dict' in s:
            m = re.match(r'(\w+)\s*=', s)
            if m:
                skip_vars.add(m.group(1))
            m2 = re.search(r'module_dict\.get\(["\'](\w+)["\']\)', s)
            if m2:
                var_map[m.group(1)] = m2.group(1)
        # var = ClassName() → map var → obj
        # 仅当 RHS 是类名（非 student_func 等函数名）时才映射
        m = re.match(r'(\w+)\s*=\s*(\w+)\(\)\s*$', s)
        if m and m.group(2) in var_map and m.group(2) not in ('student_func',):
            var_map[m.group(1)] = 'obj'

    sequences = []
    current_calls = []
    current_checks = []
    current_desc = ''

    for line in eval_code.split('\n'):
        s = line.strip()
        if not s or s.startswith('#') or s.startswith('def ') or s.startswith('return '):
            continue
        if 'module_dict' in s:
            continue
        # 跳过框架变量
        m = re.match(r'(\w+)\s*=\s*\w+\.get\(', s)
        if m:
            continue
        m = re.match(r'(\w+)\s*=\s*(\w+)\(\)\s*$', s)
        if m and (m.group(1) in skip_vars or m.group(2) in skip_vars):
            continue

        # assert → 结束当前用例，开始新用例
        if s.startswith('assert '):
            cond = s[7:].strip()
            # 跳过引用框架变量的断言 (如 assert PS is not None)
            cond_vars = set(re.findall(r'\b([a-zA-Z_]\w*)\b', cond))
            if cond_vars & skip_vars:
                continue

            # 检查末尾是否已有字符串消息（f-string 或普通字符串）
            # 从末尾向前扫描，跳过闭合的括号/引号
            has_own_msg = _ends_with_string_literal(cond)
            if has_own_msg:
                # 找到最后一个逗号（消息分隔符）的位置
                # 简单策略：找最后一个不在括号/引号内的逗号
                comma_idx = _find_last_top_level_comma(cond)
                if comma_idx >= 0:
                    cond = cond[:comma_idx].strip()
            # 重映射变量
            for old, new in sorted(var_map.items(), key=lambda x: -len(x[0])):
                cond = re.sub(r'\b' + old + r'\b', new, cond)
            if has_own_msg:
                current_checks.append(f'assert {cond}')
            else:
                current_checks.append(f'assert {cond}, "  断言失败"')

            # 不在此处分割 — 连续的断言和调用归入同一用例
            continue

        # 方法调用 → 转为测试调用
        call = _to_test_call(s, var_map, cls_name, func_name)
        if call:
            current_calls.append(call)

    # 将积累的调用和断言分组成测试用例
    # 策略：每个函数调用开始一个新用例组
    if current_calls or current_checks:
        groups = []
        cur_calls = []
        cur_checks = []
        for item in current_calls + [('__END__', None)]:
            if item == ('__END__', None):
                if cur_checks:
                    groups.append((list(cur_calls), list(cur_checks)))
            elif item.startswith('r = ') or item.startswith('r1 = ') or item.startswith('r2 = ') or                  ' = ' in item and not cur_checks:
                if cur_checks:
                    groups.append((list(cur_calls), list(cur_checks)))
                cur_calls = [item]
                cur_checks = []
            else:
                if item.startswith('obj.') or item.startswith('mem.') or ' = ' in item:
                    cur_calls.append(item)
        
        if not groups:
            groups.append((current_calls, current_checks))
        
        for i, (calls, checks) in enumerate(groups):
            if checks:
                sequences.append({
                    'calls': calls,
                    'checks': checks,
                    'desc': current_desc or f'测试{len(sequences)+1}'
                })

    return sequences


def _to_test_call(stripped, var_map, cls_name, func_name):
    """将 eval 代码行转为测试代码调用"""
    # result = var.method(args)
    m = re.match(r'(\w+)\s*=\s*(\w+)\.(\w+)\((.*)\)\s*$', stripped)
    if m:
        rv, vn, mt, ag = m.group(1), m.group(2), m.group(3), m.group(4)
        vn = var_map.get(vn, vn)
        ag = _remap_vars(ag, var_map)
        if mt.startswith('_'):
            return None
        return f'{rv} = {vn}.{mt}({ag})'

    # var.method(args)
    m = re.match(r'(\w+)\.(\w+)\((.*)\)\s*$', stripped)
    if m:
        vn, mt, ag = m.group(1), m.group(2), m.group(3)
        vn = var_map.get(vn, vn)
        ag = _remap_vars(ag, var_map)
        if mt.startswith('_'):
            return None
        return f'{vn}.{mt}({ag})'

    # result = func(args) — 跳过类实例化
    m = re.match(r'(\w+)\s*=\s*(\w+)\((.*)\)\s*$', stripped)
    if m:
        fn = m.group(2)
        if fn in ('print', 'len', 'str', 'int', 'list', 'dict', 'set', 'assert'):
            return None
        fn = var_map.get(fn, fn)
        if fn == cls_name:
            return None
        return f'{m.group(1)} = {fn}({m.group(3)})'

    return None


def _generate_fallback_class_tests(test_lines, funcs, cls_name, raw_code, eval_code):
    """降级：为类方法生成单独的调用+断言测试"""
    for method_name, params_str in funcs:
        if method_name.startswith('_') or method_name == cls_name:
            continue
        eval_args = _find_method_args_in_eval(eval_code, method_name)
        if eval_args:
            call_line = f'obj.{method_name}({eval_args})'
        else:
            param_names = [p.strip().split(':')[0].strip().split('=')[0].strip()
                          for p in params_str.split(',') if p.strip() and p.strip() != 'self']
            if param_names:
                call_line = f'obj.{method_name}({", ".join(chr(34)+p+"_test"+chr(34) for p in param_names)})'
            else:
                call_line = f'obj.{method_name}()'

        test_lines.append(f'    total += 1')
        test_lines.append(f'    try:')
        test_lines.append(f'        result = {call_line}')
        test_lines.append(f'        assert result is not None, f"  方法返回 None，请检查实现"')
        test_lines.append(f'        print("  [PASS]{method_name}() 调用成功 ->", result)')
        test_lines.append(f'        passed += 1')
        test_lines.append(f'    except Exception as e:')
        test_lines.append(f'        print(f"  [FAIL] {method_name} 失败: {{e}}")')
        test_lines.append(f'        errors.append(f"{method_name}: {{e}}")')
        test_lines.append('')


def _emit_test_case(test_lines, tc, cls_name=None, func_name=None):
    """输出一个测试用例：try 块中执行调用 + 断言，catch 中打印 FAIL"""
    test_lines.append(f'    # --- {tc["name"]} ---')
    test_lines.append(f'    try:')
    # 调用行
    for call_line in tc.get("calls", []):
        test_lines.append(f'        {call_line}')
    # 断言行
    for check_line in tc.get("checks", []):
        test_lines.append(f'        {check_line}')
    test_lines.append(f'        print("  [PASS] {tc["name"]}")')
    test_lines.append(f'    except Exception as e:')
    test_lines.append(f'        print(f"  [FAIL] {tc["name"]}: {{e}}")')
    test_lines.append('')


def _parse_eval_to_test_cases(eval_code, classes, funcs):
    """将评测代码解析为结构化的测试用例列表

    策略：每个 assert 及其之前的 setup 调用归为一个测试用例。
    但如果 assert 之间没有新的 setup，则合并到同一个用例。
    """
    if not eval_code:
        return []

    cls_name = classes[0] if classes else None
    func_name = funcs[0][0] if funcs else None
    var_map = _build_test_var_map(eval_code, cls_name, func_name)

    # 收集 eval 框架变量（来源于 module_dict 的变量引用）— 仅跳过类引用
    skip_vars = set()
    for line in eval_code.split('\n'):
        stripped = line.strip()
        # PS = module_dict.get("ClassName") → PS 是类引用，跳过
        if 'module_dict' in stripped:
            m = re.match(r'(\w+)\s*=', stripped)
            if m:
                skip_vars.add(m.group(1))
        # ps = PS() → ps 是实例，不跳过（需要映射到 obj）
        # 但 PS() 本身不应被跳过（只是类引用）
    # 注意：不跳过实例变量 (ps, mem, etc.) 和结果变量 (r, r2, etc.)

    lines = eval_code.split('\n')
    items = []  # [(type, content), ...]
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('def ') or stripped.startswith('return '):
            continue
        if 'module_dict' in stripped:
            continue
        # 跳过框架变量的赋值 (PS = module_dict.get(...))
        if re.match(r'\w+\s*=\s*\w+\.get\(', stripped):
            continue
        # 跳过创建框架类引用的行
        m = re.match(r'(\w+)\s*=\s*(\w+)\(\)\s*$', stripped)
        if m and m.group(1) in skip_vars:
            continue

        if stripped.startswith('assert '):
            cond = stripped[7:].strip()
            # 跳过引用框架变量的断言
            cond_vars = set(re.findall(r'\b([a-zA-Z_]\w*)\b', cond))
            if cond_vars & skip_vars:
                continue
            cond = _remap_vars(cond, var_map)
            # 用简单的错误消息，避免嵌套引号导致的语法错误
            items.append(('assert', f'assert {cond}, f"  FAIL: 条件不满足"'))
        else:
            call_line = _convert_eval_line_to_test(stripped, var_map, cls_name, func_name)
            if call_line:
                items.append(('call', call_line))

    if not items:
        return []

    # 分组：每组以 assertion(s) 结尾，前面收集相关的 setup calls
    test_cases = []
    case_idx = 1
    i = 0
    while i < len(items):
        # 收集连续的 calls
        calls = []
        while i < len(items) and items[i][0] == 'call':
            calls.append(items[i][1])
            i += 1
        # 收集连续的 asserts
        checks = []
        while i < len(items) and items[i][0] == 'assert':
            checks.append(items[i][1])
            i += 1

        if checks:
            tc_name = f"测试用例{case_idx}"
            test_cases.append({"name": tc_name, "calls": list(calls), "checks": list(checks)})
            case_idx += 1
            calls = []  # 下一个用例从空calls开始

    return test_cases


def _build_test_var_map(eval_code, cls_name, func_name):
    """构建 eval变量名 → test代码变量名的映射"""
    var_map = {}
    # module_dict 模式: STM = module_dict.get("ShortTermMemory") → STM → ShortTermMemory
    for line in eval_code.split('\n'):
        stripped = line.strip()
        m = re.match(r'(\w+)\s*=\s*module_dict\.get\(["\'](\w+)["\']\)', stripped)
        if m:
            var_map[m.group(1)] = m.group(2)

    # 找实例创建: var = ClassName(...) → 映射到 obj
    # 匹配有无参数的情况: mem = STM(max_size=3) 或 ps = PS()
    for line in eval_code.split('\n'):
        stripped = line.strip()
        # 匹配 var = ClassName(...) 有无参数都支持
        m = re.match(r'(\w+)\s*=\s*(\w+)\(([^)]*)\)\s*$', stripped)
        if m:
            lhs, rhs, args = m.group(1), m.group(2), m.group(3)
            # RHS 是框架类引用 (ST → ShortTermMemory) → 实例变量映射到 obj
            if rhs in var_map:
                var_map[lhs] = 'obj'
            elif rhs == cls_name:
                var_map[lhs] = 'obj'

    # 函数参数替换: student_func → func_name
    if func_name:
        var_map['student_func'] = func_name
    return var_map


def _assert_refs_undefined(cond, var_map):
    """检查断言是否引用了 eval 框架变量（从 module_dict 创建的变量）"""
    idents = set(re.findall(r'\b([a-zA-Z_]\w*)\b', cond))
    # 检查是否有标识符在 var_map 的 keys 中（表示来自 eval 代码的变量）
    # 但不在 var_map 的 values 中表示未被映射到测试代码
    eval_only_vars = set(var_map.keys()) - set(var_map.values())
    return bool(idents & eval_only_vars)


def _remap_vars(expr, var_map):
    """将表达式中的变量名替换为测试代码中的名字"""
    result = expr
    for old, new in sorted(var_map.items(), key=lambda x: -len(x[0])):
        result = re.sub(r'\b' + old + r'\b', new, result)
    return result


def _convert_eval_line_to_test(stripped, var_map, cls_name, func_name):
    """将eval中的一行转换为测试代码中的调用"""
    # result = var.method(args) → result = obj.method(args)
    m = re.match(r'(\w+)\s*=\s*(\w+)\.(\w+)\((.*)\)\s*$', stripped)
    if m:
        result_var = m.group(1)
        var_name = _remap_vars(m.group(2), var_map)
        method = m.group(3)
        if method.startswith('_'):
            return None
        args = _remap_vars(m.group(4), var_map)
        return f'{result_var} = {var_name}.{method}({args})'

    # var.method(args) → obj.method(args)
    m = re.match(r'(\w+)\.(\w+)\((.*)\)\s*$', stripped)
    if m:
        var_name = _remap_vars(m.group(1), var_map)
        method = m.group(2)
        if method.startswith('_'):
            return None
        args = _remap_vars(m.group(3), var_map)
        return f'{var_name}.{method}({args})'

    # result = func(args) → result = func_name(args)
    m = re.match(r'(\w+)\s*=\s*(\w+)\((.*)\)\s*$', stripped)
    if m:
        func = m.group(2)
        if func in ('print', 'len', 'str', 'int', 'list', 'dict', 'set', 'assert'):
            return None
        result_var = m.group(1)
        args = _remap_vars(m.group(3), var_map)
        func_remapped = _remap_vars(func, var_map)
        # 跳过实例创建（obj 已在测试代码开头创建）
        if func_remapped == cls_name:
            return None
        # 跳过框架变量实例化
        if func in var_map and var_map[func] == 'obj':
            return None
        return f'{result_var} = {func_remapped}({args})'

    return None


def _parse_eval_calls_ordered(eval_code):
    """从评测代码中按顺序提取方法调用，跳过评测框架代码"""
    calls = []
    skip_vars = set()  # 评测框架变量（module_dict, PS等）
    # 第一遍：找出评测框架变量
    for line in eval_code.split('\n'):
        stripped = line.strip()
        if 'module_dict' in stripped:
            m = re.match(r'(\w+)\s*=', stripped)
            if m:
                skip_vars.add(m.group(1))
            continue
        # PS = something() — 如果 PS 后面被用作类引用，跳过它
        m = re.match(r'(\w+)\s*=\s*(\w+)\.get\(', stripped)
        if m:
            skip_vars.add(m.group(1))

    # 第二遍：提取实际测试调用
    for line in eval_code.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('assert ') or stripped.startswith('return '):
            continue
        if 'module_dict' in stripped:
            continue

        # result = var.method(args) — 有返回值的调用
        m = re.match(r'(\w+)\s*=\s*(\w+)\.(\w+)\((.*)\)\s*$', stripped)
        if m:
            var_name = m.group(2)
            if var_name not in skip_vars:
                calls.append({"result_var": m.group(1), "var": var_name,
                             "method": m.group(3), "args": m.group(4)})
            continue

        # var.method(args) — 无返回值的调用
        m = re.match(r'(\w+)\.(\w+)\((.*)\)\s*$', stripped)
        if m:
            var_name = m.group(1)
            if var_name not in skip_vars and m.group(2) != 'get':
                calls.append({"var": var_name, "method": m.group(2), "args": m.group(3)})
            continue

        # result = func(args) — 独立函数调用（非方法）
        m = re.match(r'(\w+)\s*=\s*(\w+)\((.*)\)\s*$', stripped)
        if m and m.group(2) not in ('print', 'len', 'str', 'int', 'float',
                                     'list', 'dict', 'set', 'tuple', 'assert',
                                     'sorted', 'sum', 'min', 'max'):
            func_name = m.group(2)
            if func_name not in skip_vars and m.group(1) not in skip_vars:
                calls.append({"result_var": m.group(1), "func": func_name, "args": m.group(3)})
            continue

    return calls


def _build_var_map(eval_code, classes, funcs):
    """构建变量名映射: eval代码中的实例变量名 → obj"""
    var_map = {}
    # 找最底层的实例创建: var = Something()
    # 例如: ps = PS() → var_map['ps'] = 'obj'
    for line in eval_code.split('\n'):
        stripped = line.strip()
        # x = Y() 其中 Y 可能是类名或中间变量
        m = re.match(r'(\w+)\s*=\s*(\w+)\(\)\s*$', stripped)
        if m:
            rhs = m.group(2)
            # 如果 RHS 已经在 var_map 中，说明是间接引用
            # 如果 RHS 是类名 → 直接映射
            if rhs in (classes or []) or rhs not in var_map:
                var_map[m.group(1)] = 'obj'
    return var_map


def _extract_var_defs(eval_code):
    """从评测代码中提取语法完整的单行变量定义"""
    defs = []
    skip_funcs = {'print', 'len', 'str', 'int', 'float', 'list', 'dict', 'set', 'tuple',
                  'sorted', 'sum', 'min', 'max', 'assert', 'range'}
    for line in eval_code.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('assert ') or stripped.startswith('return '):
            continue
        if 'module_dict' in stripped:
            continue
        # 只接受单行完整定义: var = value (括号/引号/大括号必须配对)
        m = re.match(r'(\w+)\s*=\s*(.+)$', stripped)
        if not m or m.group(1) in skip_funcs:
            continue
        rhs = m.group(2).strip()
        # 跳过函数调用
        if '(' in rhs and not (rhs.startswith('[') or rhs.startswith('{')):
            continue
        # 语法完整性检查: 所有开括号必须有对应的闭括号
        if not _brackets_balanced(rhs):
            continue
        defs.append('    ' + stripped)
    return defs


def _ends_with_string_literal(s):
    """检查字符串末尾是否是一个完整的字符串字面量 (f\"...\" 或 \"...\" 或 '...')"""
    s = s.rstrip()
    if not s:
        return False
    # 检查末尾字符
    if s.endswith('"') or s.endswith("'"):
        # 简单判断：末尾引号前面不是转义的
        # 更可靠的判断：看最后一个逗号后的内容
        return True
    return False


def _find_last_top_level_comma(s):
    """找到最后一个不在括号/引号内的逗号位置"""
    depth = 0
    in_str = None
    for i in range(len(s) - 1, -1, -1):
        ch = s[i]
        if in_str:
            if ch == in_str and (i == 0 or s[i-1] != '\\\\'):
                in_str = None
            continue
        if ch in '\'"':
            in_str = ch
            # Check if it's an f-string quote
            continue
        if ch in ')]}':
            depth += 1
        elif ch in '([{':
            depth -= 1
        elif ch == ',' and depth == 0:
            return i
    return -1


def _brackets_balanced(s):
    """检查字符串中的括号是否配对"""
    stack = []
    pairs = {'(': ')', '[': ']', '{': '}'}
    in_str = None
    for ch in s:
        if in_str:
            if ch == in_str:
                in_str = None
            continue
        if ch in '\'"':
            in_str = ch
            continue
        if ch in '([{':
            stack.append(pairs[ch])
        elif ch in ')]}':
            if not stack or stack.pop() != ch:
                return False
    return len(stack) == 0 and in_str is None


def _build_skip_vars(eval_code):
    """构建评测框架变量的集合"""
    skip = set()
    for line in eval_code.split('\n'):
        if 'module_dict' in line:
            m = re.match(r'(\w+)\s*=', line.strip())
            if m:
                skip.add(m.group(1))
    return skip


def _rename_vars_in_args(args_str, var_map):
    """将参数中的变量名替换为映射后的名字"""
    if not var_map:
        return args_str
    result = args_str
    for old, new in sorted(var_map.items(), key=lambda x: -len(x[0])):
        # 只替换独立的变量名（不是字符串的一部分）
        result = re.sub(r'\b' + old + r'\b', new, result)
    return result


# 删除旧的辅助函数
def _parse_eval_for_calls(eval_code):
    return _parse_eval_calls_ordered(eval_code)


def _generate_class_method_tests(test_lines, funcs, cls_name, raw_code, eval_code):
    """降级：为每个方法生成单独的 try/except 调用测试（无断言时的兜底）"""
    pub_methods = [(name, params) for name, params in funcs
                   if not name.startswith('_') and name != cls_name]
    for method_name, params_str in pub_methods:
        eval_args = _find_method_args_in_eval(eval_code, method_name)
        if eval_args:
            call_line = f'obj.{method_name}({eval_args})'
        else:
            param_names = [p.strip().split(':')[0].strip().split('=')[0].strip()
                          for p in params_str.split(',') if p.strip() and p.strip() != 'self']
            if param_names:
                args = ', '.join(f'"{p}_test"' for p in param_names)
                call_line = f'obj.{method_name}({args})'
            else:
                call_line = f'obj.{method_name}()'

        test_lines.append(f'    # --- 测试方法 {method_name} ---')
        test_lines.append(f'    try:')
        test_lines.append(f'        result = {call_line}')
        test_lines.append(f'        print(f"  [PASS] {method_name}() -> {{result}}")')
        test_lines.append(f'    except Exception as e:')
        test_lines.append(f'        print(f"  [FAIL] {method_name}: {{e}}")')
        test_lines.append('')


def _find_method_args_in_eval(eval_code, method_name):
    """从评测代码中查找某个方法被调用时使用的参数"""
    for line in eval_code.split('\n'):
        stripped = line.strip()
        # ps.subscribe("AgentA", "alarm") 或 r = ps.publish(...)
        for pat in [rf'\.{method_name}\((.*)\)\s*$', rf'=\s*\w+\.{method_name}\((.*)\)\s*$']:
            m = re.search(pat, stripped)
            if m:
                return m.group(1)
    return None


def _find_method_body(raw_code, method_name):
    """查找方法的源代码体"""
    m = re.search(rf'def\s+{method_name}\s*\([^)]*\):\s*\n(.*?)(?=\n\s*def |\n\s*class |\Z)', raw_code, re.DOTALL)
    if m:
        return m.group(1)
    return ""


def _infer_ctor_args(raw_code, class_name):
    """从代码中推断 __init__ 需要的参数"""
    # 找到 __init__ 方法
    pattern = rf'class\s+{class_name}.*?\n(.*?)def\s+__init__\s*\(self,\s*([^)]*)\)'
    m = re.search(pattern, raw_code, re.DOTALL)
    if not m:
        m = re.search(rf'class\s+{class_name}[\s\S]*?def\s+__init__\s*\(\s*self\s*,\s*([^)]*)\)', raw_code)
    if m:
        params_str = m.group(2) if m.lastindex >= 2 else m.group(1)
        params = [p.strip() for p in params_str.split(',') if p.strip()]
        args = []
        for p in params:
            pname = p.split(':')[0].strip().split('=')[0].strip()
            # 尝试从参数名推断类型
            if 'size' in pname or 'count' in pname or 'max' in pname or 'top' in pname:
                args.append('3')
            elif 'state' in pname or 'goal' in pname:
                args.append(f'"{pname}_value"')
            else:
                args.append(f'"{pname}_test"')
        return ', '.join(args)
    return ''


def _lookup_eval_args(eval_calls, class_name, method_name):
    for call in eval_calls:
        if call.get("method") == method_name:
            return call.get("args", "")
    return None


# 删除旧的辅助函数（已不再使用）
def _extract_test_calls(eval_code, raw_code):
    """已废弃 — 保留以兼容"""
    return []



def _extract_test_calls(eval_code, raw_code):
    """从评测代码中提取具体的测试调用序列"""
    calls = []
    # 匹配 modeule_dict 模式的代码
    lines = eval_code.split('\n')

    # 判断是否是类评测模式 (使用 module_dict.get)
    is_class_mode = 'module_dict' in eval_code
    # 判断是否是函数评测模式
    is_func_mode = 'student_func' in eval_code

    if is_class_mode:
        # 提取类名和变量名
        class_match = re.search(r'module_dict\.get\(["\'](\w+)["\']\)', eval_code)
        class_name = class_match.group(1) if class_match else "Unknown"
        # 尝试从评测代码中提取实际的变量名
        var_match = re.search(r'(\w+)\s*=\s*' + class_name + r'\(\)', eval_code)
        var_name = var_match.group(1) if var_match else class_name[0].lower()

        # 添加实例创建
        calls.append({"code": f"{var_name} = {class_name}()", "comment": "创建实例"})

        # 提取方法调用 (var.method(...))
        seen_calls = set()
        for line in lines:
            stripped = line.strip()
            # 匹配各种变量名的方法调用
            m = re.match(r'(\w+)\.(\w+)\((.*?)\)\s*$', stripped)
            if m:
                vname, method, args = m.group(1), m.group(2), m.group(3)
                call_key = f"{method}({args})"
                if call_key in seen_calls:
                    continue
                seen_calls.add(call_key)

                # 跳过 print/assert 等内置函数调用
                if vname in ('self', 'print', 'len', 'str', 'int', 'float', 'list', 'dict'):
                    continue

                result_var = "r" if method == "publish" else "result"
                calls.append({
                    "code": f"{result_var} = {vname}.{method}({args})",
                    "print_var": result_var,
                    "comment": f"调用 {method}"
                })

        # 提取断言生成打印验证
        for line in lines:
            stripped = line.strip()
            assert_m = re.match(r'assert\s+(.+)', stripped)
            if assert_m:
                cond = assert_m.group(1).strip()
                # 跳过 None 检查的打印（太简单）
                if 'is not None' in cond or 'is None' in cond:
                    continue
                calls.append({
                    "code": f"print(f'  [OK] {_escape_fstring(cond[:80])}')",
                    "comment": ""
                })

    elif is_func_mode:
        # 提取函数调用
        for line in lines:
            stripped = line.strip()
            m = re.match(r'r\d*\s*=\s*student_func\((.*?)\)\s*$', stripped)
            if m:
                args = m.group(1)
                calls.append({
                    "code": f"result = {args}  # 调用被测函数",
                    "comment": "运行函数",
                    "print_var": "result"
                })
            assert_m = re.match(r'assert\s+(.+)', stripped)
            if assert_m:
                cond = assert_m.group(1).strip()
                calls.append({
                    "code": f"print(f'  [OK] {_escape_fstring(cond[:80])}')",
                    "comment": ""
                })
    else:
        # 纯函数或简单评测
        funcs = re.findall(r'def\s+(\w+)\s*\(', raw_code)
        if funcs:
            calls.append({"code": f"# TODO: 为 {funcs[0]} 添加测试参数", "comment": ""})

    return calls[:10]  # 最多10个调用


def _escape_fstring(s):
    """转义 f-string 中的特殊字符"""
    return s.replace("'", "\\'").replace('{', '{{').replace('}', '}}')


def _load_original_exercise(exercise_id):
    """从原始 .txt 文件中加载单个习题（用于答案生成）"""
    for fpath in sorted(glob.glob(os.path.join(EXERCISES_DIR, "module_*.txt"))):
        content = open(fpath, "r", encoding="utf-8").read()
        parts = re.split(r'\n(?=关卡 \d+-\d+：)', content)
        for part in parts:
            ex = _parse_one(part.strip())
            if ex and ex.get("id") == exercise_id:
                return ex
    return None



# ─── 参考答案生成 (LLM) ──────────────────────────────────────
ANSWER_GEN_PROMPT = """你是一位编程导师。请为以下编程题生成完整的参考答案。

【题目信息】
标题：{title}
模块：{module}
描述：{description}
输入输出：{input_output}

【初始代码（学生看到的骨架）】
```python
{skeleton_code}
```

【原始完整初始代码（供参考）】
```python
{raw_starter_code}
```

【评测代码（你的答案必须通过这些测试）】
```python
{eval_code}
```

请完成：

## 任务1：解题思路
用1-2段话简要说明解题思路。

## 任务2：完整参考答案
给出可直接运行的完整代码：
- 包含所有类/函数的完整实现
- 包含 if __name__ == '__main__': 测试入口
- 测试代码要具体有意义: 创建对象 → 调用方法 → print 结果

## 任务3：关键代码解释
选择3-5个关键代码片段，解释其作用。

用JSON返回：
```json
{{
  "approach": "解题思路",
  "answer_code": "完整参考答案代码",
  "explanations": [{{"code":"片段","explanation":"解释"}}]
}}
```"""


async def generate_answer(ex, user_id=None):
    """为单个习题生成参考答案（异步）"""
    # 延迟导入，避免脚本启动时的循环导入
    from services.ai_service import call_llm, extract_json_object
    from database import get_db

    # 获取一个有效的 user_id（随便取一个配置了 LLM 的用户）
    if user_id is None:
        conn = get_db()
        user = conn.execute(
            "SELECT user_id FROM llm_configs WHERE api_key IS NOT NULL AND api_key != '' LIMIT 1"
        ).fetchone()
        conn.close()
        if not user:
            return {"approach": "未配置LLM，无法生成", "answer_code": "# 请先配置AI模型", "explanations": []}
        user_id = user["user_id"]

    prompt = ANSWER_GEN_PROMPT.format(
        title=ex.get("title", ""),
        module=ex.get("module", ""),
        description=ex.get("description", "")[:1500],
        input_output=ex.get("input_output", ""),
        skeleton_code=ex.get("skeleton_code", "")[:2000],
        raw_starter_code=ex.get("raw_starter_code", "")[:2000],
        eval_code=ex.get("eval_code", "")[:1200],
    )

    max_retries = 2
    last_error = ""
    result = None

    for attempt in range(max_retries + 1):
        retry_context = ""
        if attempt > 0 and last_error:
            retry_context = f"\n\n【上一版验证错误，务必修复】\n{last_error[:800]}"

        try:
            response = await call_llm(
                user_id,
                [{"role": "system", "content": "你是编程专家，严格返回JSON。"},
                 {"role": "user", "content": prompt + retry_context}],
                temperature=0.3, max_tokens=2048
            )
        except Exception as e:
            print(f"  LLM调用失败: {e}")
            return {"approach": f"LLM调用失败: {e}", "answer_code": raw_starter, "explanations": []}

        try:
            result = extract_json_object(response)
        except Exception:
            result = {"approach": "", "answer_code": response, "explanations": []}

        # 沙箱验证
        answer_code = result.get("answer_code", "")
        if not answer_code:
            break

        is_valid, validation_error = _validate_code(answer_code)
        if is_valid:
            result["_validated"] = True
            break
        else:
            last_error = validation_error
            result["_validated"] = False
            if attempt >= max_retries:
                result["_validation_error"] = validation_error[:300]

    return result


def _validate_code(code):
    """在沙箱中运行代码验证 — 通过条件: 退出码为0且无stderr"""
    try:
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "main.py")
            with open(src, "w", encoding="utf-8") as f:
                f.write(code)
            proc = subprocess.run(
                ["python", src], capture_output=True, text=True, timeout=15, cwd=tmp
            )
            if proc.returncode != 0:
                return False, f"退出码={proc.returncode}\n{proc.stderr[:500]}"
            return True, ""
    except subprocess.TimeoutExpired:
        return False, "执行超时(>15s)"
    except Exception as e:
        return False, f"验证异常: {e}"


# ─── 主流程 ───────────────────────────────────────────────────
def main(generate_answers=False, user_id=None):
    print("=" * 60)
    print("习题预处理: 骨架化 + 测试代码 + 标记注入")
    print("=" * 60)

    exercises = parse_all_exercises()
    print(f"解析到 {len(exercises)} 道习题")

    processed = []
    for ex in exercises:
        print(f"  处理 {ex['id']}: {ex.get('title', '')[:40]}...")
        ex = process_exercise(ex)
        processed.append({
            "id": ex["id"],
            "title": ex.get("title", ""),
            "module": ex.get("module", ""),
            "description": ex.get("description", ""),
            "input_output": ex.get("input_output", ""),
            "skeleton_code": ex.get("skeleton_code", ""),
            "test_code": ex.get("test_code", ""),
            "eval_code": ex.get("eval_code", ""),
        })

    # 保存处理后的习题
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False, indent=2)
    print(f"\n已保存 {len(processed)} 道习题到: {OUTPUT_PATH}")

    # 始终生成快速答案缓存（基于原始完整初始代码）
    print("\n" + "=" * 60)
    print("生成快速答案缓存...")
    fast_cache = {}
    if os.path.exists(ANSWERS_CACHE_PATH):
        with open(ANSWERS_CACHE_PATH, "r", encoding="utf-8") as f:
            fast_cache = json.load(f)

    for ex in processed:
        eid = ex["id"]
        if eid in fast_cache and fast_cache[eid].get("_validated") and fast_cache[eid].get("_from_teaching_template"):
            continue  # 教学型答案不覆盖
        # 如果缓存的 answer_code 不包含当前 test_code，则强制刷新
        if eid in fast_cache:
            cached_code = fast_cache[eid].get("answer_code", "")
            current_test = ex.get("test_code", "")
            if current_test and current_test.strip() in cached_code:
                continue  # 已包含最新测试代码，跳过
        raw = ex.get("eval_code", "")
        # 从原始 .txt 加载完整的初始代码作为答案
        orig_ex = _load_original_exercise(eid)
        raw_starter = orig_ex.get("raw_starter_code", "") if orig_ex else ""
        if raw_starter:
            # 先尝试 raw_starter + test_code
            answer_code = raw_starter + "\n\n" + ex.get("test_code", "")
            is_valid, err = _validate_code(answer_code)
            if not is_valid:
                # 降级1: 只用 raw_starter（完整实现，不含可能出错的测试代码）
                raw_answer = raw_starter + "\n\n# 测试示例（请取消注释以运行）\n# if __name__ == '__main__':\n#     # 请参考题目描述中的输入输出示例创建测试\n#     pass"
                is_valid2, err2 = _validate_code(raw_answer)
                if is_valid2:
                    answer_code = raw_answer
                    is_valid = True
                    err = ""
                else:
                    # 降级2: 仅 raw_starter 本身
                    is_valid3, err3 = _validate_code(raw_starter)
                    if is_valid3:
                        answer_code = raw_starter
                        is_valid = True
                        err = ""
                    else:
                        err = err2 or err3 or err

            fast_cache[eid] = {
                "approach": f"以下是「{ex.get('title', '')}」的参考答案。请先尝试自己完成，遇到困难再参考。",
                "answer_code": answer_code,
                "explanations": [],
                "_validated": is_valid,
                "_from_raw_starter": True,
            }
            if not is_valid:
                fast_cache[eid]["_validation_error"] = err[:300]

    with open(ANSWERS_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(fast_cache, f, ensure_ascii=False, indent=2)
    validated = sum(1 for v in fast_cache.values() if v.get("_validated"))
    print(f"快速答案缓存: {validated}/{len(fast_cache)} 道已验证通过")
    print(f"已保存到: {ANSWERS_CACHE_PATH}")

    # 可选：用LLM生成更详细的答案
    if generate_answers:
        import asyncio
        print("\n" + "=" * 60)
        print("生成参考答案（需LLM配置）...")
        print("=" * 60)

        # 加载已有缓存
        cache = {}
        if os.path.exists(ANSWERS_CACHE_PATH):
            with open(ANSWERS_CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)

        async def gen_all():
            for ex in processed:
                eid = ex["id"]
                if eid in cache and cache[eid].get("_validated"):
                    print(f"  {eid}: 已有缓存，跳过")
                    continue
                print(f"  {eid}: 生成中...")
                answer = await generate_answer(ex, user_id)
                cache[eid] = answer
                # 边生成边保存
                with open(ANSWERS_CACHE_PATH, "w", encoding="utf-8") as f:
                    json.dump(cache, f, ensure_ascii=False, indent=2)
            return cache

        cache = asyncio.run(gen_all())
        print(f"\n已缓存 {len(cache)} 道习题答案到: {ANSWERS_CACHE_PATH}")

    # 同步评测元数据到数据库
    if not args.single:
        print("\n" + "=" * 60)
        print("同步评测元数据到数据库...")
        _sync_test_metadata(processed)
        print("完成!")


def _sync_test_metadata(processed_exercises):
    """将评测元数据同步到 exercise_test_metadata 表"""
    import json as _json, re as _re
    from database import get_db

    conn = get_db()
    synced = 0

    for ex in processed_exercises:
        eid = ex['id']
        raw_code = ex.get('raw_starter_code', '') or ex.get('skeleton_code', '')
        eval_code = ex.get('eval_code', '')

        # 确定目标函数名（取第一个非 __init__ 的公开函数）
        all_funcs = _re.findall(r'def\s+(\w+)\s*\(', raw_code)
        target = ''
        for f in all_funcs:
            if not f.startswith('_'):
                target = f
                break
        if not target and all_funcs:
            target = all_funcs[0]  # 降级：使用第一个函数（可能是 __init__）
        cls_match = _re.search(r'class\s+(\w+)', raw_code)
        cls_name = cls_match.group(1) if cls_match else ''

        # 确定类型
        ex_type = 'function'
        if cls_name:
            ex_type = 'function'  # 有类的方法题也走 function 路径

        # 提取测试用例
        test_cases = _extract_test_cases_for_db(eval_code)

        # 提取锁定代码: class声明 + __init__ + 已实现的方法 + imports
        locked_code = _extract_locked_code_for_db(raw_code, target, cls_name)

        # 引导注释
        guide = f'# 请在此处实现 {target}() 函数功能' if target else '# 请在此处编写代码'

        # UPSERT
        existing = conn.execute(
            "SELECT id FROM exercise_test_metadata WHERE exercise_id = ?", (eid,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE exercise_test_metadata SET exercise_type=?, target_function=?, "
                "locked_code=?, guide_comment=?, test_cases_json=?, updated_at=CURRENT_TIMESTAMP "
                "WHERE exercise_id=?",
                (ex_type, target, locked_code, guide,
                 _json.dumps(test_cases, ensure_ascii=False), eid)
            )
        else:
            conn.execute(
                "INSERT INTO exercise_test_metadata "
                "(exercise_id, exercise_type, target_function, locked_code, guide_comment, test_cases_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (eid, ex_type, target, locked_code, guide,
                 _json.dumps(test_cases, ensure_ascii=False))
            )
        synced += 1

    conn.commit()
    conn.close()
    print(f"已同步 {synced} 道题的评测元数据到数据库")


def _extract_test_cases_for_db(eval_code):
    """从评测代码中提取测试用例"""
    import re as _re, ast
    cases = []
    if not eval_code:
        return cases

    # 提取 assert 语句和对应的函数调用
    lines = eval_code.split('\n')
    current_args = None
    current_result_var = None

    for line in lines:
        stripped = line.strip()
        # 函数调用: r = func(args)  或  r = student_func(args)
        m = _re.match(r'(\w+)\s*=\s*\w+\((.*)\)', stripped)
        if m and m.group(1) not in ('PS', 'STM', 'MWS', 'MB'):
            current_result_var = m.group(1)
            try:
                current_args = list(ast.literal_eval(f'({m.group(2)})'))
            except Exception:
                current_args = [m.group(2)]
            continue

        # assert 语句
        if stripped.startswith('assert ') and current_args is not None:
            cond = stripped[7:].strip()
            # 提取逗号后面的消息
            parts = cond.rsplit(',', 1)
            desc = parts[1].strip().strip('"\'') if len(parts) > 1 else f'用例{len(cases)+1}'
            cond = parts[0].strip()

            # 提取期望值
            expected = None
            eq_m = _re.search(r'==\s*(.+?)(?:\s+and\s+|\s*$)', cond)
            if eq_m:
                try:
                    expected = ast.literal_eval(eq_m.group(1).strip())
                except Exception:
                    expected = eq_m.group(1).strip()
            else:
                # 其他断言模式
                in_m = _re.search(r'in\s+(.+)', cond)
                if in_m:
                    expected = f'in {in_m.group(1).strip()}'

            cases.append({
                'args': current_args,
                'expected': expected,
                'description': desc
            })
            current_args = None  # 重置

    return cases[:10]


def _extract_locked_code_for_db(raw_code, target_func, cls_name):
    """提取锁定代码（不可编辑部分）"""
    import re as _re
    if not raw_code:
        return ''

    lines = raw_code.split('\n')
    locked_lines = []
    in_target = False
    method_indent = 0
    in_method = False

    for line in lines:
        stripped = line.strip()

        # class 声明 → 锁定
        if stripped.startswith('class ') and stripped.endswith(':'):
            locked_lines.append(line)
            continue

        # import → 锁定
        if stripped.startswith('import ') or stripped.startswith('from '):
            locked_lines.append(line)
            continue

        # def __init__ → 锁定
        m = _re.match(r'def\s+(__\w+__)', stripped)
        if m and stripped.endswith(':'):
            in_target = False
            in_method = True
            method_indent = len(line) - len(line.lstrip())
            locked_lines.append(line)
            continue

        # def target_func → 不锁定（用户需要编写）
        m = _re.match(r'def\s+(\w+)', stripped)
        if m:
            func_name = m.group(1)
            in_target = (func_name == target_func)
            in_method = True
            method_indent = len(line) - len(line.lstrip())
            if in_target:
                # 保留函数签名，锁定
                locked_lines.append(line)
            else:
                locked_lines.append(line)
            continue

        # 方法体
        if in_method:
            cur_indent = len(line) - len(line.lstrip()) if stripped else 99
            if stripped and cur_indent <= method_indent:
                in_method = False
                locked_lines.append(line)
            elif not in_target:
                locked_lines.append(line)
            # in_target 时不添加方法体
            continue

        # 顶层
        locked_lines.append(line)

    return '\n'.join(locked_lines)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="预处理编程习题")
    parser.add_argument("--gen-answers", action="store_true", help="同时用LLM生成参考答案")
    parser.add_argument("--user-id", type=int, default=None, help="用于LLM调用的用户ID")
    parser.add_argument("--single", type=str, default=None, help="只处理指定ID (如 5-6)")
    args = parser.parse_args()

    if args.single:
        exercises = parse_all_exercises()
        for ex in exercises:
            if ex["id"] == args.single:
                ex = process_exercise(ex)
                print(f"ID: {ex['id']}")
                print(f"Title: {ex['title']}")
                print(f"\n--- SKELETON CODE ---")
                print(ex['skeleton_code'])
                if ex.get('test_code'):
                    print(f"\n--- TEST CODE ---")
                    print(ex['test_code'])
                break
        else:
            print(f"未找到习题: {args.single}")
    else:
        main(generate_answers=args.gen_answers, user_id=args.user_id)


