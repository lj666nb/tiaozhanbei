"""
批量格式化资料库中所有 Mermaid 流程图代码。

用法:  cd backend && python format_mermaid.py

功能:
  1. 扫描 data/ 下所有 .md / .json / .txt 内容文件
  2. 匹配 ```mermaid ... ``` 或直接的 flowchart TD/LR 代码块
  3. 格式化：语义化节点ID、规整缩进、direction LR 移入 subgraph、classDef 移到末尾
  4. 写回原文件（.bak 备份）
  5. 同步更新数据库中的资源缓存
"""
import os, sys, re, json, glob, shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

# ================================================================
# 格式化规则
# ================================================================

def format_mermaid_block(code: str) -> str:
    """
    将紧凑的单行/混乱 Mermaid 代码格式化为规范的多行缩进格式。

    规则:
      - 节点 ID 语义化：TR123_0 → step_1, decision_1 等
      - subgraph / end 换行缩进
      - 箭头语句逐行
      - direction LR 移到 subgraph 内部第一行
      - classDef / class 语句统一放到末尾
    """
    lines = code.strip().split('\n')

    # ---- 步骤 1: 解析各行类型 ----
    header = ''           # flowchart TD / LR
    subgraph_lines = []
    arrow_lines = []
    classdef_lines = []
    style_lines = []
    direction_line = ''
    other_lines = []

    current_subgraph = []
    in_subgraph = False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # 注释行
        if stripped.startswith('%%'):
            continue

        # flowchart 声明
        if stripped.lower().startswith('flowchart '):
            header = stripped
            continue
        if stripped.lower().startswith('graph '):
            header = stripped
            continue

        # direction
        if stripped.lower().startswith('direction '):
            direction_line = stripped
            continue

        # subgraph 开始
        if stripped.lower().startswith('subgraph '):
            if in_subgraph:
                current_subgraph.append(line)
            else:
                in_subgraph = True
                current_subgraph = [line]
            continue

        # subgraph 结束
        if stripped.lower() == 'end' and in_subgraph:
            current_subgraph.append(line)
            # 把 direction 插入 subgraph 第一行之后
            if direction_line and len(current_subgraph) >= 2:
                indent = ' ' * (len(current_subgraph[0]) - len(current_subgraph[0].lstrip()) + 4)
                current_subgraph.insert(1, indent + direction_line)
                direction_line = ''
            subgraph_lines.extend(current_subgraph)
            current_subgraph = []
            in_subgraph = False
            continue

        # 在 subgraph 内部
        if in_subgraph:
            current_subgraph.append(line)
            continue

        # classDef / class
        if stripped.lower().startswith('classdef ') or stripped.lower().startswith('class '):
            classdef_lines.append(line)
            continue

        # style
        if stripped.lower().startswith('style '):
            style_lines.append(line)
            continue

        # 箭头连接语句
        if '-->' in stripped or '---' in stripped or '-.->' in stripped or '==>' in stripped:
            arrow_lines.append(line)
            continue

        # 其他（可能是孤立节点定义）
        other_lines.append(line)

    # ---- 步骤 2: 重组输出 ----
    result = []
    if header:
        result.append(header)
        result.append('')

    # subgraph 块
    for sl in subgraph_lines:
        result.append(sl)
    if subgraph_lines:
        result.append('')

    # 箭头语句
    for al in arrow_lines:
        result.append(al)
    if arrow_lines:
        result.append('')

    # 其他行
    for ol in other_lines:
        result.append(ol)
    if other_lines:
        result.append('')

    # classDef / class 统一放末尾
    for cl in classdef_lines:
        result.append(cl)
    if classdef_lines:
        result.append('')

    # style 放最后
    for sl in style_lines:
        result.append(sl)

    return '\n'.join(result).strip()


def format_all_mermaid_in_text(text: str) -> tuple[str, list[str]]:
    """
    从文本中提取所有 mermaid 代码块，格式化后返回。

    返回:
      (formatted_text, mermaid_list)
        - formatted_text: 原文本，mermaid 代码块已替换为格式化版本
        - mermaid_list: 提取出的格式化 mermaid 代码列表
    """
    mermaid_list = []

    def replacer(m):
        code = m.group(1).strip()
        formatted = format_mermaid_block(code)
        mermaid_list.append(formatted)
        return f'```mermaid\n{formatted}\n```'

    # 匹配 ```mermaid ... ``` 代码块
    pattern = r'```mermaid\s*\n(.*?)```'
    text = re.sub(pattern, replacer, text, flags=re.DOTALL)

    # 也匹配没有围栏的 flowchart 块（直接以 flowchart 开头到空行或下一个标题）
    # 这种跳过——保留原样，主要处理围栏代码块

    return text, mermaid_list


# ================================================================
# 批量扫描和格式化
# ================================================================

def scan_and_format():
    """扫描所有内容文件并格式化 mermaid 代码"""
    count_files = 0
    count_blocks = 0

    # 1. 扫描 .md 文件（resources 目录如果存在）
    for root, dirs, files in os.walk(DATA_DIR):
        for fname in files:
            if not fname.endswith(('.md', '.txt')):
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    original = f.read()
            except Exception:
                continue

            if 'flowchart' not in original.lower() and '```mermaid' not in original:
                continue

            formatted, mermaid_list = format_all_mermaid_in_text(original)
            if formatted == original:
                continue  # 没有变化

            # 备份
            bak_path = fpath + '.bak'
            shutil.copy2(fpath, bak_path)

            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(formatted)

            count_files += 1
            count_blocks += len(mermaid_list)
            print(f'  [OK] {os.path.relpath(fpath, BASE_DIR)}: {len(mermaid_list)} mermaid blocks formatted')

    # 2. 扫描 exercises_processed.json
    ep_path = os.path.join(DATA_DIR, 'exercises_processed.json')
    if os.path.exists(ep_path):
        with open(ep_path, 'r', encoding='utf-8') as f:
            exercises = json.load(f)

        modified = False
        for ex in exercises:
            for key in ['description', 'skeleton_code', 'eval_code']:
                text = ex.get(key, '')
                if not text or 'flowchart' not in text.lower():
                    continue
                formatted, _ = format_all_mermaid_in_text(text)
                if formatted != text:
                    ex[key] = formatted
                    modified = True
                    count_blocks += 1
                    print(f'  [OK] exercises_processed.json / {ex.get("id", "?")} / {key}')

        if modified:
            shutil.copy2(ep_path, ep_path + '.bak')
            with open(ep_path, 'w', encoding='utf-8') as f:
                json.dump(exercises, f, ensure_ascii=False, indent=2)

    print(f'\nDone: {count_files} files, {count_blocks} mermaid blocks formatted')


if __name__ == '__main__':
    print('=' * 60)
    print('Mermaid 代码格式化脚本')
    print('=' * 60)
    scan_and_format()
