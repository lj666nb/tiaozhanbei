# 合并流式响应片段

这是你的独立实验项目。请跟随左侧阶段清单，从创建文件开始完成项目。

## 项目目标

LangChain stream() 会持续产生 AIMessageChunk 迭代器，content 可能是字符串、None，或由文本块字典组成的列表。实现 normalize_stream_chunks(chunks)，按顺序抽取有效文本并拼接；必须支持一次性迭代器、消息字典和带 content 属性的真实消息片段对象；忽略 None、空字符串以及列表中非 text 类型的块。遇到完全不支持的片段结构要抛出 ValueError。

## 约定

- 核心可测试逻辑写在 `solution.py`
- 可运行的 LangChain 应用写在 `app.py`
- 真实 API Key 只放在本地 `.env`，不要提交
