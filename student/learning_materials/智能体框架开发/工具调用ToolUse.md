# 工具调用与Function Calling：让AI学会使用工具

## 一、Function Calling是什么

大语言模型的知识存在天然的局限性——它们训练数据有截止日期，无法访问实时信息，也不能执行实际操作。**Function Calling（函数调用）** 正是为了解决这个问题而诞生的技术。它让模型能够"请求"调用外部函数或API，从而获得实时数据、执行计算、操作数据库等。

可以把Function Calling理解为：模型不再是只能"说"，还能"做"。当用户问"今天北京天气怎么样"时，模型不会凭空编造（或拒绝回答），而是生成一个函数调用请求，告诉系统："请帮我调用get_weather函数，参数是city='北京'"。系统执行这个函数后，将真实的天气数据反馈给模型，模型再基于这些数据生成自然语言的回答。

Image-Prompt(英文绘图词): A 2D vector illustration showing an AI agent at center, a user on the left asking "What is the weather in Beijing?", and a function-call arrow from the AI to a cloud API icon on the right returning structured JSON data. The AI then generates a natural language reply back to the user. Flat-design minimalist style, tech light blue #409EFF primary color, white background, dark blue #1a1a2e text labels. Rounded rectangular nodes connected by directional arrows, thin-line weather and gear icons, centered symmetric layout with moderate whitespace, academic learning atmosphere for educational software UI.

## 二、定义工具Schema

要让模型知道有哪些工具可用、何时使用它们，你需要为每个工具定义一个**Schema（模式定义）**。一个标准的工具Schema包含以下要素：

### 工具名称（name）

简短、描述性的名称，模型会用它来标识工具。建议使用蛇形命名法（snake_case），如`search_database`、`send_email`。

### 工具描述（description）

用自然语言说明工具的功能和使用场景。这是模型判断"何时调用此工具"的核心依据。描述应该清晰说明：
- 该工具做什么
- 什么情况下应该使用它
- 有什么限制或注意事项

### 参数定义（parameters）

使用JSON Schema格式定义工具接受的参数：

```json
{
  "name": "get_stock_price",
  "description": "获取指定股票代码的当前价格。当用户询问某只股票的价格时使用此工具。",
  "parameters": {
    "type": "object",
    "properties": {
      "symbol": {
        "type": "string",
        "description": "股票代码，如AAPL（苹果）、TSLA（特斯拉）"
      },
      "currency": {
        "type": "string",
        "enum": ["USD", "CNY", "EUR"],
        "description": "价格显示的货币单位，默认为USD"
      }
    },
    "required": ["symbol"]
  }
}
```

### Schema设计要点

- **描述比约束更重要**：模型通过描述文本来理解参数含义，而不是通过类型限制。因此描述要写得清楚详细
- **使用enum限制选项**：对于有固定选项的参数，使用enum明确可选值
- **标明必填和可选**：required字段让模型知道哪些参数必须提供
- **添加默认值说明**：在description中说明参数的默认行为

Image-Prompt(英文绘图词): A 2D vector illustration of a tool definition card floating at center, displaying JSON Schema fields: name, description, parameters with type/object/properties structure. Surrounding the card are annotated labels pointing to each field with explanatory callouts for "tool identifier", "when to use this", "required vs optional", and "enum for fixed choices". Flat-design minimalist style, tech light blue #409EFF accent on the schema card borders, white background, dark blue #1a1a2e annotation text. Clean academic layout with rounded corners and thin-line curly-bracket icons, moderate whitespace.

## 三、模型如何决定调用工具

当你把工具Schema和用户消息一起发送给模型时，模型会进行以下判断过程：

1. **分析用户意图**：理解用户到底想要什么
2. **匹配可用工具**：在可用工具列表中寻找能完成此需求的工具
3. **提取参数**：从用户消息中提取工具所需的参数值
4. **决策输出**：如果找到合适的工具，输出函数调用请求；如果不需要工具，直接输出文本回复

这里有一个关键点：**是否调用工具完全是模型的判断**，你无法强制模型调用某个特定工具（除非在System Prompt中明确要求）。因此，工具描述的质量直接决定了模型调用工具的准确性。

Image-Prompt(英文绘图词): A 2D vector illustration of a decision flowchart with four sequential rounded nodes arranged horizontally: (1) "Analyze User Intent" with a magnifying glass icon pointed at a user message bubble, (2) "Match Available Tools" with a toolbox icon scanning a tool list, (3) "Extract Parameters" with a form input icon pulling values from user text, (4) "Decision Output" with a branching diamond leading to either a "Function Call" JSON block or a plain "Text Reply" speech bubble. Flat-design minimalist style, tech light blue #409EFF flow arrows and node borders, white background, dark blue #1a1a2e labels inside each rounded rectangle. Academic learning atmosphere.

## 四、工具执行的完整流程

### 完整交互流程

```
用户输入："帮我查一下苹果公司今天的股价"

Step 1: 系统将用户消息 + 工具列表发送给LLM
        ↓
Step 2: LLM分析后决定调用 get_stock_price 工具
        输出: { "name": "get_stock_price", "arguments": { "symbol": "AAPL" } }
        ↓
Step 3: 系统识别到这是函数调用，执行 get_stock_price("AAPL")
        得到结果: { "symbol": "AAPL", "price": 195.32, "change": "+2.1%" }
        ↓
Step 4: 系统将函数执行结果作为新的消息发送给LLM
        ↓
Step 5: LLM基于函数返回的数据生成自然语言回答
        输出: "苹果公司（AAPL）今天的股价是195.32美元，上涨了2.1%。"
```

### 代码实现示例

```python
import json

def run_agent_with_tools(user_message, tools, llm):
    messages = [{"role": "user", "content": user_message}]
    
    while True:
        # 调用LLM，传入工具定义
        response = llm.chat(
            messages=messages,
            tools=tools,
            tool_choice="auto"  # 让模型自行决定是否调用工具
        )
        
        # 检查模型是否要求调用工具
        if response.has_tool_calls():
            for tool_call in response.tool_calls:
                tool_name = tool_call.name
                tool_args = json.loads(tool_call.arguments)
                
                # 执行实际的工具函数
                tool_result = execute_tool(tool_name, tool_args)
                
                # 将工具调用和结果添加到消息历史
                messages.append(response.message)  # 助手的工具调用请求
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result)
                })
            # 继续循环，让模型根据工具结果生成最终回复
            continue
        
        # 没有工具调用，返回最终文本回复
        return response.content

def execute_tool(tool_name, args):
    tools_registry = {
        "get_stock_price": lambda args: fetch_stock_price(args["symbol"]),
        "search_database": lambda args: db_search(args["query"]),
        "send_email": lambda args: send_email(**args)
    }
    return tools_registry[tool_name](args)
```

Image-Prompt(英文绘图词): A 2D vector illustration of a 5-step vertical pipeline workflow. Top: a "User Input" chat bubble. Step 1 arrow down to an "LLM Analysis" rounded node with a brain icon. Step 2 arrow down to "Tool Execution" with a spinning gear icon. Step 3 arrow down to "Result Return" with a data document icon. Step 4 arrow down to "Final Response" with a natural language speech bubble at bottom. A dashed loop-back arrow on the right side curves from Step 3 back to Step 1, labeled "Continue loop until no tool call". Flat-design minimalist style, tech light blue #409EFF arrows and node accents, white background, dark blue #1a1a2e text labels. Centered vertical layout, thin-line icons, academic learning atmosphere for educational software UI.

## 五、工具设计的最佳实践

### 原则一：单一职责

每个工具只做一件事。与其设计一个"万能的数据库操作工具"，不如拆分为`query_database`、`insert_record`、`update_record`等独立工具。这样模型的"工具选择"更准确。

### 原则二：参数扁平化

避免深层嵌套的参数结构。模型在生成嵌套JSON参数时更容易出错。尽量保持参数结构简单：

```json
// 好的设计
{
  "query": "SELECT * FROM users",
  "limit": 10,
  "offset": 0
}

// 避免的设计
{
  "database": {
    "name": "users",
    "operation": {"type": "query", "filters": {...}}
  }
}
```

### 原则三：明确的错误处理

工具执行可能失败——数据库连接超时、API返回错误、参数不合法等。工具的返回值应该包含明确的成功/失败标识：

```python
def search_database(query, limit=10):
    try:
        results = db.execute(query).fetchmany(limit)
        return {
            "success": True,
            "data": results,
            "count": len(results)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "suggestion": "请检查SQL语法或数据库连接"
        }
```

当模型收到`{"success": false, ...}`时，它可以尝试修正参数后重试，而不是困惑地编造结果。

### 原则四：合理控制工具数量

提供给模型的工具不是越多越好。工具太多会导致模型"选择困难"，增加选错工具的概率。一般来说，控制在5-15个以内比较合理。如果确实需要更多工具，可以考虑使用工具分组或动态工具发现。

### 原则五：工具描述要具体

不要写"搜索信息"这样模糊的描述。要写"在公司的产品数据库中搜索商品信息，支持按名称、分类、价格范围筛选"。描述越具体，模型判断越准确。

Image-Prompt(英文绘图词): A 2D vector illustration of five horizontally arranged rounded icon cards, each representing a best practice principle: (1) "Single Responsibility" with a single clean gear icon, (2) "Flat Parameters" with a simple two-field form icon, (3) "Error Handling" with a shield-checkmark icon showing success/fail return structure, (4) "Tool Count Limit" with a numbered badge reading "5-15" and a toolbox, (5) "Specific Description" with a magnifying glass over a detailed document. Flat-design minimalist style, tech light blue #409EFF card borders and accents, white background, dark blue #1a1a2e titles below each card. Centered symmetric horizontal layout, thin-line icons, clean academic infographic.

## 六、MCP协议简介

**MCP（Model Context Protocol）** 是一个开放协议，由Anthropic发布，旨在标准化AI模型与外部工具、数据源的交互方式。你可以将MCP理解为"工具调用的USB接口标准"——就像USB让不同品牌的外设能即插即用，MCP让不同的工具和AI系统能够标准化地连接。

### MCP的核心概念

- **MCP Server**：提供工具的服务端。每个MCP Server可以暴露多个工具
- **MCP Client**：嵌入在智能体应用中的客户端，负责连接MCP Server并调用工具
- **标准化的工具描述格式**：与Function Calling的Schema类似，但更加标准化
- **资源（Resources）**：除了工具，MCP还支持暴露数据资源（如文件、数据库内容）
- **传输层**：支持stdio（标准输入输出）和HTTP等多种通信方式

### 为什么MCP重要

在MCP出现之前，为AI智能体集成工具意味着编写大量的胶水代码——每个工具都有自己的一套接口规范。MCP提供了一种统一的方式，让工具开发者只需要编写一次MCP Server，就能被任何支持MCP的智能体使用。

### 简单示例

一个MCP Server可以提供这样的工具定义：

```json
{
  "name": "github_search_repos",
  "description": "Search GitHub repositories",
  "inputSchema": {
    "type": "object",
    "properties": {
      "query": {"type": "string", "description": "Search query"},
      "language": {"type": "string", "description": "Programming language filter"}
    }
  }
}
```

任何MCP Client都可以发现并调用这个工具，无需了解底层的GitHub API细节。

Image-Prompt(英文绘图词): A 2D vector illustration showing a central MCP hub labeled "Model Context Protocol" with a USB-plug metaphor connector design. Left side shows three AI agent icons (MCP Clients) plugging into the hub via standardized connectors. Right side shows three tool server nodes (MCP Servers) exposing capabilities: a database icon, a file system icon, and an API gateway icon, each displaying standardized JSON tool definitions. Thin bidirectional communication arrows connect through the hub. Flat-design minimalist style, tech light blue #409EFF hub and connector accents, white background, dark blue #1a1a2e labels. Rounded shapes, thin-line connection cables, academic atmosphere.

## 七、总结

Function Calling让大语言模型从"纸上谈兵"进化为"知行合一"。掌握了工具调用的设计和实现，你就能构建出真正有用的AI智能体——它们能查数据、发邮件、操作系统，成为你业务中的得力助手。

在实际开发中，不要过度依赖模型对工具的"自动选择"。始终在代码层面添加安全校验——检查敏感操作的参数、限制工具的调用频率、记录所有工具调用的审计日志。记住：**模型负责"决定做什么"，你负责"确保做得安全"**。

Image-Prompt(英文绘图词): A 2D vector illustration of an AI agent transforming from a "talking head" silhouette on the left into an "action-oriented" figure with tool-holding hands on the right, symbolizing the evolution from pure conversation to real-world capability execution. A large shield icon with a checkmark overlays the right side representing security guardrails, audit logging, and safety controls. A bridge of thin-line code brackets connects the two halves. Flat-design minimalist style, tech light blue #409EFF primary color for the bridge and shield, white background, dark blue #1a1a2e text labels. Centered horizontal composition, rounded shapes, academic atmosphere.
