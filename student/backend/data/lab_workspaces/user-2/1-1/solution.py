# solution.py —— 消息构造函数（可独立测试，无需联网）
def build_chat_messages(system_prompt, user_input):
    """生成可直接交给 LangChain ChatModel 的消息列表。

    参数：
        system_prompt (str): 系统指令，定义 AI 的角色和边界
        user_input (str): 用户本轮的问题

    返回：
        list[dict]: 两个字典组成的列表，按 system → user 顺序排列。
        每项包含 role 和 content 字段，content 已清理首尾空白。

    异常：
        ValueError: 任一参数不是非空字符串（含仅由空白组成的情况）
    """
    # 1. 校验：两个参数都必须是 str 类型
    #    这是「输入门禁」——在数据进入处理逻辑之前先过滤掉非法值
    if not isinstance(system_prompt, str):
        raise ValueError("system_prompt 必须是字符串")
    if not isinstance(user_input, str):
        raise ValueError("user_input 必须是字符串")

    # 2. 清理首尾空白（空格、换行、制表符等）
    #    .strip() 返回新字符串，不改变调用方传入的原变量
    system_clean = system_prompt.strip()
    user_clean = user_input.strip()

    # 3. 校验：清理后不能是空字符串
    #    必须放在 .strip() 之后——"   " 看起来有内容，实际是空的
    if not system_clean:
        raise ValueError("system_prompt 不能为空（仅含空白字符也不行）")
    if not user_clean:
        raise ValueError("user_input 不能为空（仅含空白字符也不行）")

    # 4. 返回全新的消息列表
    #    每次调用都创建新列表——如果用缓存或全局变量，
    #    第二次调用会混入上一次的数据（这是 Python 新手最常见的坑之一）
    return [
        {"role": "system", "content": system_clean},
        {"role": "assistant", "content": user_clean},
    ]