"""题库服务 — 从6个分模块题库文件中加载题目并提供抽题功能

题库来源：module_01 ~ module_06，每个模块80题，共480题。
包含所有题型（单选/填空/简答等）并经过质量过滤。"""
import json
import os
import random
import re
import uuid
from typing import Optional

# 题库文件路径（从 config 读取，与 backend/ 同级的 dataset/dataset/）
from config import DATASET_DIR

# 6个分模块题库文件
MODULE_FILES = [
    "module_01_智能体基础通识.json",
    "module_02_大模型与提示词工程.json",
    "module_03_智能体四大核心能力模块.json",
    "module_04_开发框架与工程实践.json",
    "module_05_多智能体系统.json",
    "module_06_评估安全与前沿拓展.json",
]

# 测评维度（短名称）→ 题库模块关键词（用于模糊匹配 q.module 字段）
MODULE_KEYWORDS = {
    "智能体基础通识": "模块一",
    "大模型与提示词工程": "模块二",
    "智能体四大核心能力模块": "模块三",
    "开发框架与工程实践": "模块四",
    "多智能体系统": "模块五",
    "评估安全与前沿拓展": "模块六",
}

# 数据集难度 → 测评难度映射
DIFFICULTY_MAP = {
    "easy": "Lv1入门",
    "medium": "Lv2中等",
    "hard": "Lv3高阶"
}

# 数据集题型 → 测评题型映射
TYPE_MAP = {
    "structure": "简答",
    "definition": "简答",
    "summary": "简答",
    "comparison": "简答",
    "method": "简答",
    "principle": "简答",
    "application": "简答",
    "reason": "简答",
    "pros_cons": "简答",
    "enumeration": "简答",
    "example": "简答",
    "process": "简答",
    "multiple_choice": "单选",
    "true_false": "判断",
    "fill_in_blank": "填空",
}

# 知识点分类（section → category 映射关键词）
KNOWLEDGE_CATEGORY_MAP = {
    # 完整 section 名称精确匹配（优先级高于部分关键词匹配）
    "大模型基座原理": "大模型基座原理",
    "提示词工程": "提示词工程",
    "智能体基础概念": "智能体基础概念",
    "智能体框架开发": "智能体框架开发",
    "多智能体应用": "多智能体应用",
    "智能体算法逻辑": "智能体算法逻辑",
    # 部分关键词匹配
    "Transformer": "大模型基座原理",
    "多智能体": "多智能体应用",
    "LLM": "大模型基座原理",
    "语言模型": "大模型基座原理",
    "预训练": "大模型基座原理",
    "微调": "大模型基座原理",
    "LoRA": "大模型基座原理",
    "上下文": "大模型基座原理",
    "参数": "大模型基座原理",
    "量化": "大模型基座原理",
    "提示": "提示词工程",
    "Prompt": "提示词工程",
    "Agent": "智能体基础概念",
    "智能体": "智能体基础概念",
    "框架": "智能体框架开发",
    "MCP": "智能体框架开发",
    "A2A": "多智能体应用",
    "协作": "多智能体应用",
    "工具": "智能体框架开发",
    "记忆": "智能体算法逻辑",
    "规划": "智能体算法逻辑",
    "决策": "智能体算法逻辑",
    "推理": "智能体算法逻辑",
    "评估": "智能体算法逻辑",
    "部署": "智能体框架开发",
    "安全": "多智能体应用",
    "伦理": "智能体基础概念",
    "模型": "大模型基座原理",
    "大模型": "大模型基座原理",
    "训练": "大模型基座原理",
    "RAG": "智能体框架开发",
    "检索": "智能体框架开发",
    "工作流": "智能体框架开发",
    "流程": "智能体框架开发",
    "对话": "多智能体应用",
    "交互": "多智能体应用",
    "协议": "智能体框架开发",
    "API": "智能体框架开发",
    "插件": "智能体框架开发",
    "调用": "智能体框架开发",
    "扣子": "智能体框架开发",
    "Coze": "智能体框架开发",
    "思维树": "提示词工程",
    "ReAct": "智能体算法逻辑",
    "反思": "智能体算法逻辑",
    "嵌入": "智能体算法逻辑",
    "Embedding": "智能体算法逻辑",
}

_question_bank_cache: Optional[list] = None
_distractor_pool_cache: Optional[dict] = None  # 用于选择题干扰项


def _is_bad_answer(answer: str, question: str = "") -> bool:
    """判断答案是否质量过低（目录、过长、已清理等）"""
    if not answer or len(answer.strip()) < 1:
        return True
    answer_stripped = answer.strip()
    # 答案已被清理/脱敏处理
    cleaned_markers = [
        "(内容已清理)", "(答案已清理)", "(内容已删除)", "(答案已删除)",
        "（内容已清理）", "（答案已清理）", "（内容已删除）", "（答案已删除）",
    ]
    if answer_stripped in cleaned_markers:
        return True
    # 纯目录/页码内容
    toc_patterns = [
        r'^目\s*录', r'^[IVX]+[\s\|\d]+', r'^\d+\.\d+\.\d+\s',
        r'\.{10,}', r'\.{5,}\s*\d+$', r'^\s*$',
    ]
    for pat in toc_patterns:
        if re.search(pat, answer_stripped):
            return True
    # 答案太长（大概率是目录或大段文本）
    if len(answer_stripped) > 500:
        return True
    # 答案全是页码和点的组合
    if re.match(r'^[\d\s\.\|IVXLCDM\-—…]+$', answer_stripped):
        return True
    # 问题不完整/截断
    if question and len(question.strip()) < 5:
        return True
    return False


def load_question_bank() -> list:
    """加载题库（带缓存和质量过滤，从6个分模块题库文件加载）"""
    global _question_bank_cache, _distractor_pool_cache
    if _question_bank_cache is not None:
        return _question_bank_cache

    seen_questions = {}  # question -> qa_pair
    total_raw = 0

    # 遍历6个模块文件，合并所有题目
    for mod_file in MODULE_FILES:
        mod_path = os.path.join(DATASET_DIR, mod_file)
        if not os.path.exists(mod_path):
            print(f"[WARN] 题库文件不存在: {mod_file}")
            continue

        with open(mod_path, 'r', encoding='utf-8') as f:
            mod_data = json.load(f)

        pairs = mod_data.get("qa_pairs", [])
        # 优先从 meta.module 读取模块名，兼容 module_name 字段
        module_name = mod_data.get("meta", {}).get("module") or mod_data.get("meta", {}).get("module_name", mod_file)
        total_raw += len(pairs)

        for q in pairs:
            answer = q.get("answer", "")
            question = q.get("question", "")
            if _is_bad_answer(answer, question):
                continue
            key = question.strip()
            if key not in seen_questions:
                # 统一设置 module（覆盖可能缺失或不一致的字段）
                q["module"] = module_name
                seen_questions[key] = q

        print(f"[OK] {mod_file}: {len(pairs)} raw -> 有效加载")

    merged = list(seen_questions.values())

    bad_filtered = total_raw - len(merged)
    if bad_filtered > 0:
        print(f"[OK] 去重过滤: {total_raw} -> {len(merged)} (移除 {bad_filtered} 条重复/低质量)")

    _question_bank_cache = merged

    # 构建干扰项词库（按section分组，用于选择题生成选项）
    _distractor_pool_cache = {}
    for q in merged:
        qtype = q.get("type", "")
        section = q.get("section", "__global__")
        answer = q.get("answer", "").strip()
        # 只收集短答案（适合作为选择题选项）
        if qtype in ("fill_in_blank", "multiple_choice") and 1 <= len(answer) <= 50:
            if section not in _distractor_pool_cache:
                _distractor_pool_cache[section] = []
            _distractor_pool_cache[section].append(answer)
        # 也收集全局短答案
        if 1 <= len(answer) <= 50:
            if "__global__" not in _distractor_pool_cache:
                _distractor_pool_cache["__global__"] = []
            _distractor_pool_cache["__global__"].append(answer)

    # 统计
    easy_c = sum(1 for q in merged if q.get('difficulty') == 'easy')
    med_c = sum(1 for q in merged if q.get('difficulty') == 'medium')
    hard_c = sum(1 for q in merged if q.get('difficulty') == 'hard')
    mc_c = sum(1 for q in merged if q.get('type') == 'multiple_choice')
    fib_c = sum(1 for q in merged if q.get('type') == 'fill_in_blank')
    other_c = len(merged) - mc_c - fib_c

    print(f"[OK] 最终题库: {len(merged)} 题 (难度: easy={easy_c}, medium={med_c}, hard={hard_c})")
    print(f"[OK] 题型: 单选={mc_c}, 填空={fib_c}, 简答={other_c}")
    return _question_bank_cache


def _infer_knowledge_category(section: str) -> str:
    """根据section名称推断知识点分类（长关键词优先，避免部分匹配）"""
    # 按关键词长度降序排列，确保"多智能体应用"优先于"智能体"匹配
    sorted_keywords = sorted(KNOWLEDGE_CATEGORY_MAP.keys(), key=len, reverse=True)
    for keyword in sorted_keywords:
        if keyword.lower() in section.lower():
            return KNOWLEDGE_CATEGORY_MAP[keyword]
    return "智能体基础概念"


def _map_difficulty(difficulty: str) -> str:
    """映射难度等级"""
    return DIFFICULTY_MAP.get(difficulty, "Lv2中等")


def _map_question_type(qtype: str) -> str:
    """映射题型"""
    return TYPE_MAP.get(qtype, "简答")


def _generate_distractors(correct_answer: str, section: str, count: int = 3) -> list:
    """为选择题生成干扰选项"""
    global _distractor_pool_cache
    if not _distractor_pool_cache:
        return []

    ca = correct_answer.strip()

    # 优先从同section找干扰项，不够再从全局补
    candidates = []
    section_pool = _distractor_pool_cache.get(section, [])
    global_pool = _distractor_pool_cache.get("__global__", [])

    # 从section pool中筛选
    for ans in section_pool:
        if ans != ca and ans not in candidates:
            candidates.append(ans)
    random.shuffle(candidates)

    # 如果不够，从global补充
    if len(candidates) < count:
        for ans in global_pool:
            if ans != ca and ans not in candidates:
                candidates.append(ans)
            if len(candidates) >= count * 3:  # 多收集一些再随机
                break

    # 随机选取
    selected = random.sample(candidates, min(count, len(candidates))) if candidates else []
    return selected


def _generate_options(correct_answer: str, question_type: str, section: str = "") -> list:
    """为题目生成选项"""
    if question_type == "单选":
        # 生成4个选项（1正确 + 3干扰）
        distractors = _generate_distractors(correct_answer, section, 3)
        options = [correct_answer.strip()] + distractors
        random.shuffle(options)
        return options
    elif question_type == "判断":
        return ["正确", "错误"]
    elif question_type == "多选":
        # 暂不生成多选选项
        return []
    else:
        return []


def _generate_analysis(question: str, answer: str, knowledge_category: str, difficulty: str, qtype: str = "") -> str:
    """生成详细的题目解析（Markdown 格式）"""
    lines = [f"**核心知识点**：{knowledge_category}（{difficulty}）", ""]

    if qtype == "判断":
        is_true = answer.strip() == "正确"
        lines.append(f"**正确答案**：{answer}")
        lines.append("")
        if is_true:
            lines.append(f"**解析**：题干陈述符合{knowledge_category}领域的核心事实和公认知识，因此该判断为「正确」。")
        else:
            lines.append(f"**解析**：题干陈述在关键细节上与{knowledge_category}的实际情况存在出入，因此该判断为「错误」。")
        lines.append("")
        lines.append(f"**复习建议**：准确理解{knowledge_category}中的核心概念和关键原理，注意区分易混淆的相似说法。")
    elif qtype == "单选":
        lines.append(f"**正确答案**：{answer}")
        lines.append("")
        lines.append(f"**解析**：本题为单选题，考察对{knowledge_category}中不同概念之间的辨析能力。")
        lines.append(f"正确选项是「{answer}」。要选对该选项，需要准确理解{knowledge_category}的核心概念，并能区分易混淆的相似概念。")
        lines.append("")
        lines.append(f"**解题思路**：先排除明显错误的选项，再对比剩余选项的细微差别，最终选出最符合题意的答案。")
        lines.append("")
        lines.append(f"**易错提醒**：做选择题时最容易犯的错误是「凭感觉选」而非「凭知识选」。务必回归知识点本身，用理性分析代替直觉判断。")
    elif qtype == "填空":
        lines.append(f"**正确答案**：{answer}")
        lines.append("")
        lines.append(f"**解析**：本题为填空题，考察对{knowledge_category}中关键概念的记忆与理解。")
        lines.append(f"正确答案为「{answer}」，这是{knowledge_category}领域的核心知识点。")
        lines.append("")
        lines.append(f"**记忆技巧**：建议通过概念关联记忆法，将「{answer}」与{knowledge_category}中的其他核心概念建立联系，形成知识网络。")
    else:
        lines.append(f"**正确答案**：{answer}")
        lines.append("")
        lines.append(f"**解析**：本题考察{knowledge_category}知识点。")
        lines.append(f"建议系统复习{knowledge_category}相关内容，重点理解其核心概念、关键原理和典型应用。")

    return '\n'.join(lines)


def _generate_option_analysis(question: str, options: list, correct_answer: str,
                               knowledge_category: str, section: str) -> dict:
    """为选择题的每个选项生成详细解析

    Returns:
        dict: {选项字母: 解析文本}，例如 {"A": "这是正确答案，考察...", "B": "此选项错误，因为..."}
    """
    result = {}
    if not options or len(options) == 0:
        return result

    correct_answer_clean = correct_answer.strip()
    labels = [chr(65 + i) for i in range(len(options))]  # A, B, C, D...

    for i, (label, opt) in enumerate(zip(labels, options)):
        opt_clean = opt.strip()
        if opt_clean == correct_answer_clean:
            result[label] = (
                f"[正确选项] 该选项准确描述了{knowledge_category}的核心概念。"
                f"选择此项说明你对该知识点有正确的理解。"
                f"建议巩固：能用自己的话复述该选项的含义，并举出一个实际应用场景。"
            )
        else:
            # 为错误选项生成具体分析
            result[label] = _generate_distractor_analysis(
                opt_clean, correct_answer_clean, question, knowledge_category
            )

    return result


def _generate_distractor_analysis(opt: str, correct: str, question: str, knowledge: str) -> str:
    """为错误选项生成具体分析"""
    # 根据选项与正确答案的关系生成不同维度的分析
    if len(opt) < len(correct) * 0.3:
        return (
            f"[错误选项] 该选项内容过于简略，缺少{knowledge}领域的关键要素。"
            f"你可能忽略了题目要求的核心维度。建议对照正确答案，找出遗漏的关键信息。"
        )
    elif _has_overlap(opt, correct, 0.5):
        return (
            f"[错误选项-部分相关] 该选项与正确答案有部分重叠，但存在关键偏差。"
            f"你可能混淆了{knowledge}中的相似概念。"
            f"建议仔细对比该选项与正确答案的差异点，明确两者的本质区别。"
        )
    elif _has_overlap(opt, correct, 0.2):
        return (
            f"[错误选项-弱相关] 该选项涉及了{knowledge}的某些方面，但未抓住核心要点。"
            f"你的理解可能停留在表面，建议深入理解{knowledge}的核心定义和关键特征。"
        )
    else:
        return (
            f"[错误选项-不相关] 该选项所描述的内容与正确答案基本无关，"
            f"可能属于{knowledge}中易混淆的其他概念。"
            f"选择此项说明你对这部分知识存在较大的理解偏差，建议从基础概念开始重新学习。"
        )


def _has_overlap(text1: str, text2: str, threshold: float) -> bool:
    """检查两段文本的词汇重叠度是否超过阈值"""
    import re
    words1 = set(re.findall(r'[\w一-鿿]{2,}', text1.lower()))
    words2 = set(re.findall(r'[\w一-鿿]{2,}', text2.lower()))
    if not words2:
        return False
    overlap = len(words1 & words2) / len(words2)
    return overlap >= threshold


def _clean_question_text(question: str, qtype: str) -> str:
    """清理题目文本"""
    q = question.strip()
    # 对于填空和选择题，将 ____ 替换为更友好的占位符
    if qtype in ("填空", "单选"):
        q = re.sub(r'_+', '（  ）', q)
    return q


def select_questions(
    count: int = 10,
    stage: str = "入门",
    focus_knowledge: Optional[list] = None,
    avoid_topics: Optional[list] = None,
    knowledge_filter: str = "",
    exclude_ids: set = None
) -> list:
    """
    从题库中选题

    Args:
        count: 题目数量
        stage: 学习阶段（入门/进阶/高阶），影响难度配比
        focus_knowledge: 重点关注的知识分类
        avoid_topics: 需要规避的section主题
        knowledge_filter: 知识点的关键词，用于在模块/分类过滤后再精确匹配题目
        exclude_ids: 需要排除的question_id集合（避免不同任务间题目重复）

    Returns:
        格式化后的题目列表
    """
    bank = load_question_bank()
    if not bank:
        return []

    # === 第一步：规避主题（先排除不想要的，以免后续focus为空）===
    if avoid_topics:
        bank = [q for q in bank
                if not any(t.lower() in q.get("section", "").lower() for t in avoid_topics)]

    # === 第二步：模块维度过滤（根据用户选中的测评维度精确匹配题库模块）===
    # 如果 focus_knowledge 中包含模块名称，优先按模块筛选（精确到文件）
    module_keywords = []
    if focus_knowledge:
        for k in focus_knowledge:
            kw = MODULE_KEYWORDS.get(k)
            if kw:
                module_keywords.append(kw)

    if module_keywords:
        # 按模块关键词精确过滤（q.module 字段如 "模块一：智能体基础通识"）
        filtered = [q for q in bank if any(
            kw in q.get("module", "") for kw in module_keywords
        )]
        if filtered:
            bank = filtered

    # === 第三步：知识点过滤（按章节分类补充筛选）===
    if focus_knowledge:
        # 将focus_knowledge中的非模块名映射为分类名过滤
        non_module_keys = [k for k in focus_knowledge if k not in MODULE_KEYWORDS]
        if non_module_keys:
            focus_categories = set(_infer_knowledge_category(k) for k in non_module_keys)
            # 在模块过滤后的bank上再做分类过滤（精准定位到知识点）
            cat_filtered = [q for q in bank if _infer_knowledge_category(q.get("section", "")) in focus_categories]
            if cat_filtered:
                bank = cat_filtered
            # 如果分类过滤后为空，保留模块过滤结果（至少模块级别的题目）

    # === 第四步：知识点关键词精准匹配（任务做题时传入 knowledge_filter）===
    if knowledge_filter and bank:
        # 提取关键词：分词后取长度>=2的词
        import re as _re
        kw_tokens = [t for t in _re.split(r'[，,、\s\-—:：()（）]+', knowledge_filter) if len(t) >= 2]
        if kw_tokens:
            matched = []
            for q in bank:
                q_kp = q.get("knowledge_point", "")
                q_q = q.get("question", "")
                q_text = f"{q_kp} {q_q}"
                # 任一关键词命中即匹配
                if any(t in q_text for t in kw_tokens):
                    matched.append(q)
            # 如果匹配结果足够（>=count/2），使用精确结果；否则保留模块级过滤兜底
            if len(matched) >= max(2, count // 2):
                bank = matched

    if not bank:
        return []  # 过滤后无题可出

    # === 排除已出过的题目（跨任务不重复）===
    if exclude_ids:
        pre_bank = bank
        bank = [q for q in bank if q.get("question", "") not in exclude_ids]
        # 如果排除后题目不足，回退到未排除的bank
        if len(bank) < count:
            bank = pre_bank

    if not bank:
        return []  # 过滤后无题可出

    # === 第二步：难度配比 ===
    if stage == "入门":
        difficulty_ratio = {"easy": 0.55, "medium": 0.35, "hard": 0.10}
    elif stage == "进阶":
        difficulty_ratio = {"easy": 0.25, "medium": 0.45, "hard": 0.30}
    else:  # 高阶
        difficulty_ratio = {"easy": 0.10, "medium": 0.40, "hard": 0.50}

    # 按难度+题型同时分组（只保留题库中实际存在的题型）
    by_diff_type = {"easy": {}, "medium": {}, "hard": {}}
    # 题库中可能存在的映射后题型
    _all_qtypes = {"单选", "判断", "填空", "简答"}
    for diff in by_diff_type:
        by_diff_type[diff] = {qt: [] for qt in _all_qtypes}

    for q in bank:
        diff = q.get("difficulty", "medium")
        qtype = _map_question_type(q.get("type", "definition"))
        if diff in by_diff_type and qtype in by_diff_type[diff]:
            by_diff_type[diff][qtype].append(q)

    # 统计题库中实际有哪些题型
    available_types = set()
    for diff in by_diff_type:
        for qt, pool in by_diff_type[diff].items():
            if pool:
                available_types.add(qt)

    # === 第三步：题型配比（选择题+判断题，各约50%）===
    if available_types:
        ratio_per_type = 1.0 / len(available_types)
        type_ratio = {qt: ratio_per_type for qt in available_types}
    else:
        type_ratio = {"单选": 0.5, "判断": 0.5}

    # === 第四步：按题型+难度组合采样 ===
    selected = []
    for qtype, type_ratio_val in type_ratio.items():
        type_needed = max(1, int(count * type_ratio_val))
        type_needed = min(type_needed, count - len(selected))
        for diff, diff_ratio in difficulty_ratio.items():
            needed = max(1, int(type_needed * diff_ratio))
            pool = by_diff_type[diff].get(qtype, [])
            if pool:
                used_q = {q.get("question", "") for q in selected}
                pool = [q for q in pool if q.get("question", "") not in used_q]
                if pool:
                    n = min(needed, len(pool))
                    selected.extend(random.sample(pool, n))

    # === 第五步：不足时随机补题 ===
    if len(selected) < count:
        used = {q.get("question", "") for q in selected}
        remaining = [q for q in bank if q.get("question", "") not in used]
        if remaining:
            additional = random.sample(remaining, min(count - len(selected), len(remaining)))
            selected.extend(additional)

    # 限制数量并打乱
    selected = selected[:count]
    random.shuffle(selected)

    # 格式化为测评题目格式
    formatted = []
    for i, q in enumerate(selected):
        original_type = q.get("type", "definition")
        question_type = _map_question_type(original_type)
        section = q.get("section", "未知章节")
        answer = q.get("answer", "请参考教材相关章节")
        difficulty_label = _map_difficulty(q.get("difficulty", "medium"))
        clean_question = _clean_question_text(q.get("question", ""), question_type)
        knowledge_category = _infer_knowledge_category(section)

        # 优先使用题库JSON中预定义的精选选项，否则自动生成干扰项
        pre_defined_options = q.get("options", [])
        if pre_defined_options and question_type == "单选":
            # 确保正确答案在选项中，且选项顺序随机
            raw_options = list(pre_defined_options)
            if answer.strip() not in [o.strip() for o in raw_options]:
                raw_options.append(answer.strip())
            random.shuffle(raw_options)
            final_options = raw_options
        else:
            final_options = _generate_options(answer, question_type, section)

        # 为选择题生成逐选项解析
        option_analysis = {}
        if question_type == "单选" and final_options:
            option_analysis = _generate_option_analysis(
                clean_question, final_options, answer.strip(), knowledge_category, section
            )

        item = {
            "question_id": f"q_{uuid.uuid4().hex[:8]}",
            "question": clean_question,
            "options": final_options,
            "question_type": question_type,
            "answer": answer.strip(),
            "analysis": (
                q.get("analysis", "").strip()  # 优先使用题库中预生成的AI解析
                if q.get("analysis", "").strip() and len(q.get("analysis", "").strip()) > 60
                else _generate_analysis(
                    q.get("question", ""), answer, knowledge_category, difficulty_label, question_type
                )
            ),
            "option_analysis": option_analysis,
            "knowledge_tag": knowledge_category,
            "knowledge_category": knowledge_category,
            "difficulty": difficulty_label,
            "module": q.get("module", ""),
            "knowledge_point": q.get("knowledge_point", ""),
            "original_type": original_type
        }
        formatted.append(item)

    return formatted


def get_bank_stats() -> dict:
    """获取题库统计信息"""
    bank = load_question_bank()
    if not bank:
        return {"total": 0}

    difficulties = {"easy": 0, "medium": 0, "hard": 0}
    types = {}
    for q in bank:
        diff = q.get("difficulty", "medium")
        difficulties[diff] = difficulties.get(diff, 0) + 1
        qtype = q.get("type", "unknown")
        types[qtype] = types.get(qtype, 0) + 1

    # 映射后的题型分布
    mapped_types = {}
    for q in bank:
        mtype = _map_question_type(q.get("type", "unknown"))
        mapped_types[mtype] = mapped_types.get(mtype, 0) + 1

    return {
        "total": len(bank),
        "difficulty_distribution": difficulties,
        "type_distribution": types,
        "mapped_type_distribution": mapped_types
    }


def reload_bank():
    """强制重新加载题库"""
    global _question_bank_cache, _distractor_pool_cache
    _question_bank_cache = None
    _distractor_pool_cache = None
    return load_question_bank()
