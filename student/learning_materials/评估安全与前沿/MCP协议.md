# 模型上下文协议（MCP）

## 引言

在AI Agent的开发中，一个核心痛点是：**每个Agent需要对接的工具、数据源、外部服务都有不同的API格式**。一个Agent要查询数据库，需要写一套SQL连接代码；要调用搜索API，又需要另一套HTTP客户端代码；要访问文件系统，又是一种接口。这种碎片化让Agent开发变得低效、脆弱、难以规模化。

**MCP（Model Context Protocol，模型上下文协议）** 正是为了解决这个问题而诞生的。它由Anthropic提出并开源，定义了AI模型与外部工具、数据源之间的**标准通信协议**——就像HTTP定义了浏览器和服务器之间的通信标准一样，MCP定义了AI Agent和外部能力之间的通信标准。

Image-Prompt(英文绘图词): A flat-design before-after comparison illustration: left side shows the traditional fragmented approach with three Agent boxes (Agent1, Agent2, Agent3) each independently connecting to three Tool boxes via tangled crossing lines (M x N complexity, marked "Chaos"), right side shows the MCP approach with all three Agents connecting to a single central "MCP Protocol" hub layer which then routes to all three Tools via clean parallel lines (marked "Standardized"), tech-blue #409EFF on white background, 2D vector academic style with clearly labeled complexity reduction.

---

## MCP是什么

### 核心定位

MCP是一个**开放标准**，其目标是成为"AI应用的USB-C接口"——就像USB-C统一了设备的物理连接一样，MCP统一了AI Agent与外部工具的逻辑连接。

```
传统方式：每个Agent独自对接每个工具（M x N复杂度）
┌──────┐ ┌──────┐ ┌──────┐
│Agent1│ │Agent2│ │Agent3│
└──┬───┘ └──┬───┘ └──┬───┘
   │        │        │
   │  ┌─────┼────────┼─────┐
   ├──┤ 自定义API 1     ├──┤
   │  └─────────────────┘  │
   │  ┌─────────────────┐  │
   ├──┤ 自定义API 2     ├──┤
   │  └─────────────────┘  │
   ...

MCP方式：Agent只需实现MCP Client，工具只需实现MCP Server
┌──────┐ ┌──────┐ ┌──────┐
│Agent1│ │Agent2│ │Agent3│  ← 只需实现MCP Client
└──┬───┘ └──┬───┘ └──┬───┘
   │        │        │
   └────────┼────────┘
            │
      ┌─────▼──────┐
      │ MCP Protocol│  ← 统一的协议层
      └─────┬──────┘
            │
   ┌────────┼────────┐
   │        │        │
┌──▼───┐ ┌──▼───┐ ┌──▼───┐
│Tool 1│ │Tool 2│ │Tool 3│  ← 只需实现MCP Server
└──────┘ └──────┘ └──────┘
```

### 核心价值

| 价值 | 说明 |
|------|------|
| **标准化** | 一个协议连接所有工具，减少集成工作 |
| **互操作性** | 任何MCP Agent可以连接任何MCP Server |
| **安全性** | 统一的权限控制和认证机制 |
| **可扩展** | 易于添加新的工具和数据源 |
| **开源** | Apache 2.0许可，社区驱动 |

Image-Prompt(英文绘图词): A flat-design USB-C hub analogy illustration: a universal "MCP" connector hub in the center shaped like a hexagonal port, with multiple tool cables radiating outward to different tool icons (a database cylinder labeled "SQL", a file folder, a globe for API, a magnifying glass for search, an email envelope), and an AI Agent plug on the left side connecting to the hub, the tagline "AI's Universal Connector" in tech-blue #409EFF on white background, 2D vector academic style.

---

## MCP架构

### Client-Server架构

```
┌──────────────────────────────────────────────────────────┐
│                      MCP 架构                             │
│                                                          │
│  ┌─────────────────────┐    ┌─────────────────────┐     │
│  │    MCP Client       │    │    MCP Server       │     │
│  │   (Host/Agent)      │    │   (Tool/Data)       │     │
│  │                     │    │                     │     │
│  │ • 发起连接          │    │ • 暴露资源(Resources)│     │
│  │ • 请求工具/资源     │◄──►│ • 提供工具(Tools)    │     │
│  │ • 处理结果          │    │ • 提供提示(Prompts)  │     │
│  │ • 管理会话          │    │ • 响应请求          │     │
│  └─────────────────────┘    └─────────────────────┘     │
│                                                          │
│              传输层 (Transport Layer)                     │
│  ┌─────────────────┐  ┌─────────────────┐               │
│  │  stdio          │  │  SSE / HTTP     │               │
│  │ (本地进程通信)   │  │ (远程网络通信)   │               │
│  └─────────────────┘  └─────────────────┘               │
└──────────────────────────────────────────────────────────┘
```

### 三大核心原语

MCP定义了三种核心交互原语，覆盖了Agent与外部世界交互的主要模式：

| 原语 | 用途 | 类比 | 示例 |
|------|------|------|------|
| **Resources（资源）** | 暴露数据给模型读取 | GET请求 | 文件内容、数据库记录、API响应 |
| **Tools（工具）** | 让模型执行操作 | POST请求 | 发送邮件、创建文件、执行代码 |
| **Prompts（提示模板）** | 预定义的交互模板 | 快捷指令 | "写一封邮件""分析这段数据" |

```python
# ============ MCP三大原语的概念模型 ============

class MCPServerCapabilities:
    """
    MCP Server的能力声明。

    每个MCP Server启动时声明自己提供哪些Resources、Tools、Prompts。
    """

    def __init__(self):
        self.resources = []   # 可读的数据
        self.tools = []       # 可调用的工具
        self.prompts = []     # 预定义的提示模板

    def register_resource(self, uri: str, name: str,
                           description: str, mime_type: str):
        """
        注册一个资源（只读数据）。

        Resources是MCP Server向模型暴露数据的方式。
        类似于REST API的GET端点。
        """
        self.resources.append({
            "uri": uri,               # 统一资源标识符
            "name": name,             # 人类可读名称
            "description": description,  # 描述
            "mimeType": mime_type,    # 内容类型
        })

    def register_tool(self, name: str, description: str,
                       input_schema: dict):
        """
        注册一个工具（可执行操作）。

        Tools是MCP Server向模型暴露可执行功能的方式。
        类似于REST API的POST端点。
        """
        self.tools.append({
            "name": name,
            "description": description,
            "inputSchema": input_schema,  # JSON Schema定义参数
        })

    def register_prompt(self, name: str, description: str,
                         arguments: list):
        """
        注册一个提示模板。

        Prompts为用户提供预定义的交互模板。
        例如：标准的"代码审查"、"邮件撰写"模板。
        """
        self.prompts.append({
            "name": name,
            "description": description,
            "arguments": arguments,
        })
```

Image-Prompt(英文绘图词): A flat-design Client-Server architecture diagram: left block labeled "MCP Client (Host/Agent)" containing three action items (initiate connection, request tools/resources, process results, manage sessions), right block labeled "MCP Server (Tool/Data)" containing three capability items (expose Resources, provide Tools, offer Prompts, respond to requests), bidirectional arrows between them, and a bottom "Transport Layer" bar with two sub-boxes: "stdio (Local IPC)" with a pipe icon and "SSE / HTTP (Remote)" with a cloud network icon, tech-blue #409EFF on white background, 2D vector academic style.

---

## Resources（资源）

### 资源模型

Resources是MCP中最基础的原语——它代表任何模型可能需要读取的数据。

```python
class ResourceProvider:
    """
    MCP Resource提供者。

    Resources的核心特点：
    1. 只读（Read-only）：资源不应该被模型修改
    2. URI标识：每个资源通过URI唯一标识
    3. 可发现：模型可以通过list_resources发现可用资源
    4. 内容类型：支持文本、JSON、二进制等多种格式
    """

    def __init__(self):
        self.resources = {}

    # ============ 资源类型示例 ============

    def provide_file_resource(self, file_path: str):
        """文件资源：暴露文件系统内容"""
        uri = f"file://{file_path}"
        self.resources[uri] = {
            "uri": uri,
            "name": f"文件: {file_path}",
            "description": f"读取文件 {file_path} 的内容",
            "mimeType": self._guess_mime_type(file_path),
            "handler": lambda: open(file_path).read()
        }

    def provide_database_resource(self, table_name: str,
                                    query: str = None):
        """数据库资源：暴露数据库查询结果"""
        uri = f"db://{table_name}"
        if query:
            uri += f"?query={query}"

        def db_handler():
            import sqlite3
            conn = sqlite3.connect("database.db")
            result = conn.execute(query or f"SELECT * FROM {table_name}")
            return result.fetchall()

        self.resources[uri] = {
            "uri": uri,
            "name": f"数据库: {table_name}",
            "description": f"查询表 {table_name} 的数据",
            "mimeType": "application/json",
            "handler": db_handler
        }

    def provide_api_resource(self, api_url: str, name: str):
        """API资源：暴露外部API数据"""
        uri = f"api://{name}"

        def api_handler():
            import requests
            response = requests.get(api_url)
            return response.json()

        self.resources[uri] = {
            "uri": uri,
            "name": name,
            "description": f"从 {api_url} 获取的数据",
            "mimeType": "application/json",
            "handler": api_handler
        }

    def read_resource(self, uri: str) -> dict:
        """读取指定资源"""
        if uri not in self.resources:
            return {
                "error": f"Resource not found: {uri}",
                "available_resources": list(self.resources.keys())
            }

        resource = self.resources[uri]
        try:
            content = resource["handler"]()
            return {
                "uri": uri,
                "mimeType": resource["mimeType"],
                "content": content
            }
        except Exception as e:
            return {
                "uri": uri,
                "error": str(e)
            }
```

Image-Prompt(英文绘图词): A flat-design resource model diagram showing three data source types connected to a standardized Resource layer: a file icon with URI "file:///workspace/report.txt", a database cylinder with URI "db://analytics/users", and an API globe with URI "api://weather/latest", each flowing through a read-only lock icon and displaying MIME type badges (text/plain, application/json), all converging into a "list_resources / read_resource" interface, tech-blue #409EFF on white background, 2D vector academic style.

---

## Tools（工具）

### 工具模型

```python
class ToolProvider:
    """
    MCP Tool提供者。

    Tools的核心特点：
    1. 可执行（Executable）：工具可以执行修改性操作
    2. 声明式接口：通过JSON Schema描述输入参数
    3. 结构化输出：返回结构化的结果
    4. 错误处理：标准的错误返回格式
    """

    def __init__(self):
        self.tools = {}

    def register_tool(self, name: str, description: str,
                       input_schema: dict, handler: callable):
        """
        注册工具。

        input_schema使用JSON Schema格式定义参数，这样
        模型可以理解工具需要什么参数。
        """
        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "handler": handler
        }

    def call_tool(self, name: str, arguments: dict) -> dict:
        """
        调用工具。

        核心流程：
        1. 验证工具是否存在
        2. 验证参数是否符合Schema
        3. 执行工具处理函数
        4. 返回结构化结果
        """
        if name not in self.tools:
            return {
                "isError": True,
                "content": [{"type": "text",
                            "text": f"Tool not found: {name}"}]
            }

        tool = self.tools[name]

        # 验证参数
        validation_error = self._validate_arguments(
            arguments, tool["inputSchema"]
        )
        if validation_error:
            return {
                "isError": True,
                "content": [{"type": "text",
                            "text": f"Invalid arguments: {validation_error}"}]
            }

        # 执行工具
        try:
            result = tool["handler"](**arguments)
            return {
                "isError": False,
                "content": [{"type": "text", "text": str(result)}]
            }
        except Exception as e:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool error: {str(e)}"}]
            }

    def _validate_arguments(self, args: dict,
                              schema: dict) -> Optional[str]:
        """使用JSON Schema验证参数"""
        import jsonschema
        try:
            jsonschema.validate(args, schema)
            return None
        except jsonschema.ValidationError as e:
            return str(e)


# ============ 工具注册示例 ============

def create_email_tool():
    """创建发送邮件的工具"""
    tool = ToolProvider()
    tool.register_tool(
        name="send_email",
        description="发送电子邮件",
        input_schema={
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "format": "email",
                    "description": "收件人邮箱地址"
                },
                "subject": {
                    "type": "string",
                    "description": "邮件主题"
                },
                "body": {
                    "type": "string",
                    "description": "邮件正文内容"
                },
                "cc": {
                    "type": "string",
                    "format": "email",
                    "description": "抄送邮箱（可选）"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "normal", "high"],
                    "description": "优先级"
                }
            },
            "required": ["to", "subject", "body"]
        },
        handler=lambda to, subject, body, cc=None, priority="normal":
            f"邮件已发送至 {to}（主题: {subject}）"
    )
    return tool
```

Image-Prompt(英文绘图词): A flat-design tool execution flow diagram: left side shows a JSON Schema parameter definition block with fields (to, subject, body, priority) and type annotations, flowing into a central "Tool Handler" gear icon that performs validation (green checkmark path) and execution, with an error branch (red cross path) returning structured error response, the output shown as a standardized result box with `isError: false` and `content: [{type: "text", text: "..."}]` format, tech-blue #409EFF on white background, 2D vector academic style.

---

## Prompts（提示模板）

```python
class PromptProvider:
    """
    MCP Prompt提供者。

    Prompts为用户提供预定义的、结构化的交互模板。
    这有助于引导用户有效使用Agent的能力。
    """

    def __init__(self):
        self.prompts = {}

    def register_prompt(self, name: str, description: str,
                         template: str, arguments: list = None):
        """
        注册提示模板。

        arguments: 模板中的可替换参数列表。
        例如：{"name": "recipient", "description": "收件人名称", "required": True}
        """
        self.prompts[name] = {
            "name": name,
            "description": description,
            "template": template,
            "arguments": arguments or []
        }

    def get_prompt(self, name: str,
                    arguments: dict = None) -> dict:
        """获取填充后的提示"""
        if name not in self.prompts:
            return {"error": f"Prompt not found: {name}"}

        prompt = self.prompts[name]
        template = prompt["template"]

        # 填充参数
        if arguments:
            for key, value in arguments.items():
                template = template.replace(f"{{{{{key}}}}}",
                                            str(value))

        return {
            "description": prompt["description"],
            "messages": [
                {
                    "role": "user",
                    "content": {"type": "text", "text": template}
                }
            ]
        }


# ============ 提示模板示例 ============
prompts = PromptProvider()
prompts.register_prompt(
    name="code_review",
    description="代码审查提示模板",
    template=(
        "请对以下代码进行全面审查，包括：\n"
        "1. 代码质量和可读性\n"
        "2. 潜在的Bug和安全漏洞\n"
        "3. 性能优化建议\n"
        "4. 命名和注释规范\n\n"
        "代码:\n```{{language}}\n{{code}}\n```"
    ),
    arguments=[
        {"name": "language", "description": "编程语言", "required": True},
        {"name": "code", "description": "待审查的代码", "required": True}
    ]
)
```

Image-Prompt(英文绘图词): A flat-design prompt template diagram: a parameterized template block with placeholder slots marked `{{language}}` and `{{code}}` shown as empty input fields, user arguments flowing from the right to fill each slot, the complete filled template emerging at the bottom as a structured message object with `role: "user"` and `content: {type: "text", text: "..."}`, with a "code_review" name badge, tech-blue #409EFF on white background, 2D vector academic style.

---

## 传输层

### stdio传输（本地）

```python
import subprocess
import json
import sys


class StdioMCPTransport:
    """
    基于stdio的MCP传输层。

    适用于本地进程间通信。
    MCP Server作为子进程运行，通过标准输入/输出进行JSON-RPC通信。

    优势：简单、零网络开销、天然隔离
    适用：本地工具（文件系统、本地数据库、CLI工具）
    """

    def __init__(self, server_command: list[str]):
        """
        server_command: 启动MCP Server的命令
        例如：["python", "my_mcp_server.py"]
              ["node", "mcp-server.js"]
              ["npx", "@modelcontextprotocol/server-filesystem"]
        """
        self.process = subprocess.Popen(
            server_command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    def send_request(self, method: str, params: dict = None) -> dict:
        """发送JSON-RPC请求并接收响应"""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params or {}
        }

        # 通过stdin发送
        request_str = json.dumps(request) + "\n"
        self.process.stdin.write(request_str)
        self.process.stdin.flush()

        # 通过stdout接收响应
        response_str = self.process.stdout.readline()
        return json.loads(response_str)

    def close(self):
        """关闭连接"""
        self.process.stdin.close()
        self.process.terminate()
        self.process.wait()


# ============ 本地MCP Server示例 ============
class LocalFileSystemMCPServer:
    """
    本地文件系统MCP Server。

    通过stdio与Agent通信，提供文件操作能力。
    """

    def __init__(self, allowed_directories: list[str]):
        self.allowed_dirs = allowed_directories

    def start(self):
        """启动stdio监听循环"""
        for line in sys.stdin:
            request = json.loads(line.strip())
            response = self.handle_request(request)
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()

    def handle_request(self, request: dict) -> dict:
        """处理JSON-RPC请求"""
        method = request.get("method")
        params = request.get("params", {})

        if method == "tools/list":
            return self._list_tools()
        elif method == "tools/call":
            return self._call_tool(
                params.get("name"),
                params.get("arguments", {})
            )
        elif method == "resources/list":
            return self._list_resources()
        elif method == "resources/read":
            return self._read_resource(params.get("uri"))
        else:
            return {
                "jsonrpc": "2.0",
                "id": request["id"],
                "error": {"code": -32601,
                         "message": f"Method not found: {method}"}
            }
```

### SSE/HTTP传输（远程）

```python
import asyncio
from aiohttp import web
import json


class SSEMCPTransport:
    """
    基于SSE（Server-Sent Events）的MCP远程传输层。

    适用于跨网络的Agent-工具通信。
    使用SSE（单向推送）+ HTTP POST（请求-响应）的组合。

    适用：远程API、云服务、分布式工具
    """

    def __init__(self, host: str = "localhost", port: int = 8000):
        self.host = host
        self.port = port
        self.clients = {}  # client_id -> asyncio.Queue

    async def start_server(self):
        """启动MCP HTTP服务器"""
        app = web.Application()
        app.router.add_get("/sse", self.handle_sse_connect)
        app.router.add_post("/messages", self.handle_message)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        print(f"MCP SSE Server running on http://{self.host}:{self.port}")

    async def handle_sse_connect(self, request):
        """
        处理SSE连接。

        Client通过SSE建立持久连接，Server通过此连接推送事件。
        """
        response = web.StreamResponse()
        response.headers["Content-Type"] = "text/event-stream"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Connection"] = "keep-alive"
        await response.prepare(request)

        client_id = str(id(request))
        queue = asyncio.Queue()
        self.clients[client_id] = queue

        try:
            # 发送endpoint事件，告知Client消息发送地址
            await response.write(
                f"event: endpoint\n"
                f"data: /messages?sessionId={client_id}\n\n"
            )

            # 持续监听并推送事件
            while True:
                data = await queue.get()
                await response.write(
                    f"event: message\n"
                    f"data: {json.dumps(data)}\n\n"
                )
        except asyncio.CancelledError:
            pass
        finally:
            del self.clients[client_id]
        return response

    async def handle_message(self, request):
        """处理Client发来的请求消息"""
        data = await request.json()
        session_id = request.query.get("sessionId")

        # 处理请求并生成响应
        response = await self.process_request(data)

        # 通过SSE推送响应
        if session_id in self.clients:
            await self.clients[session_id].put(response)

        return web.Response(text="OK")

    async def process_request(self, request: dict) -> dict:
        """处理JSON-RPC请求"""
        # 与stdio版本相同
        pass
```

Image-Prompt(英文绘图词): A flat-design transport layer comparison: left panel "stdio (Local)" showing two local process boxes connected by a bidirectional pipe with stdin/stdout labeled arrows, a subprocess icon, and "JSON-RPC over standard I/O" label; right panel "SSE / HTTP (Remote)" showing a cloud network with a Server-Sent Events stream (unidirectional push arrow) and HTTP POST request-response pair, a session ID token, and a client queue; both panels connected by a "Transport Abstraction" bridge labeled "MCP supports both local and remote communication", tech-blue #409EFF on white background, 2D vector academic style.

---

## MCP与Function Calling的对比

| 维度 | Function Calling (OpenAI/Anthropic) | MCP |
|------|-----------------------------------|-----|
| **定位** | 模型内置的工具调用能力 | 独立的协议标准 |
| **标准化** | 各厂商定义格式不同 | 统一的开放标准 |
| **可移植性** | 绑定特定模型提供商 | 不绑定任何模型 |
| **发现机制** | 需要手动定义函数列表 | Server自动声明能力 |
| **工具注册** | 在API调用时传入 | Server启动时声明 |
| **通信方式** | API请求-响应（内联） | 持久连接 + JSON-RPC |
| **安全模型** | 依赖API密钥 | 独立的权限和认证层 |
| **适用场景** | 简单工具调用 | 复杂工具生态 |

### 两者的关系

```
Function Calling 和 MCP 不是竞争关系，而是互补关系：

Function Calling: "模型如何调用工具"（模型侧的接口）
MCP: "工具如何被模型发现和调用"（工具侧的接口）

理想状态：
模型使用Function Calling格式发起工具调用
→ MCP Client转换为标准的MCP请求
→ MCP Server执行并返回结果
→ MCP Client转换为Function Calling响应格式
→ 模型接收结果

MCP是Function Calling的后端标准化层。
```

Image-Prompt(英文绘图词): A flat-design complementary relationship diagram: left puzzle piece labeled "Function Calling" (model-side interface, showing a brain icon with "How models call tools" caption), right puzzle piece labeled "MCP" (tool-side standard, showing a server rack icon with "How tools are discovered and called" caption), the two pieces fitting together with an integration bridge arrow between them labeled "MCP is the backend standardization layer for Function Calling", tech-blue #409EFF on white background, 2D vector academic style.

---

## 代码示例：完整的MCP集成

```python
import asyncio
import json
from typing import Any


class MCPClient:
    """
    MCP Client：Agent侧的MCP实现。

    提供工具发现、资源读取、工具调用等能力。
    """

    def __init__(self):
        self.servers = {}       # server_name -> transport
        self.tools = {}         # tool_name -> (server, tool_info)
        self.resources = {}     # resource_uri -> (server, resource_info)
        self.prompts = {}       # prompt_name -> (server, prompt_info)

    async def connect_stdio_server(self, name: str,
                                     command: list[str]):
        """连接一个stdio MCP Server"""
        transport = StdioMCPTransport(command)
        self.servers[name] = transport

        # 发现Server提供的能力
        await self._discover_capabilities(name, transport)

    async def connect_sse_server(self, name: str,
                                   url: str):
        """连接一个远程SSE MCP Server"""
        transport = SSEMCPTransport()
        await transport.connect(url)
        self.servers[name] = transport

        # 发现能力
        await self._discover_capabilities(name, transport)

    async def _discover_capabilities(self, server_name: str,
                                       transport):
        """发现MCP Server提供的能力"""
        # 获取工具列表
        tools_resp = await transport.send("tools/list")
        for tool in tools_resp.get("tools", []):
            tool_key = f"{server_name}:{tool['name']}"
            self.tools[tool_key] = (server_name, tool)

        # 获取资源列表
        resources_resp = await transport.send("resources/list")
        for resource in resources_resp.get("resources", []):
            self.resources[resource["uri"]] = (server_name, resource)

        # 获取提示模板列表
        prompts_resp = await transport.send("prompts/list")
        for prompt in prompts_resp.get("prompts", []):
            prompt_key = f"{server_name}:{prompt['name']}"
            self.prompts[prompt_key] = (server_name, prompt)

    def get_available_tools(self) -> list[dict]:
        """获取所有可用工具（转换为Model可理解的格式）"""
        tools_list = []
        for tool_key, (server_name, tool_info) in self.tools.items():
            tools_list.append({
                "name": tool_key,
                "description": tool_info["description"],
                "input_schema": tool_info.get("inputSchema", {}),
            })
        return tools_list

    async def call_tool(self, tool_key: str,
                          arguments: dict) -> Any:
        """调用指定工具"""
        if tool_key not in self.tools:
            raise ValueError(f"Unknown tool: {tool_key}")

        server_name, tool_info = self.tools[tool_key]
        transport = self.servers[server_name]

        result = await transport.send(
            "tools/call",
            {"name": tool_info["name"], "arguments": arguments}
        )
        return result

    async def read_resource(self, uri: str) -> Any:
        """读取资源"""
        server_name, resource_info = self.resources[uri]
        transport = self.servers[server_name]

        result = await transport.send(
            "resources/read", {"uri": uri}
        )
        return result

    async def get_prompt(self, prompt_key: str,
                           arguments: dict = None) -> dict:
        """获取提示模板"""
        server_name, prompt_info = self.prompts[prompt_key]
        transport = self.servers[server_name]

        result = await transport.send(
            "prompts/get",
            {"name": prompt_info["name"],
             "arguments": arguments or {}}
        )
        return result


# ============ 使用示例 ============
async def main():
    client = MCPClient()

    # 连接本地文件系统Server
    await client.connect_stdio_server(
        "filesystem",
        ["npx", "@modelcontextprotocol/server-filesystem",
         "/workspace"]
    )

    # 连接数据库Server
    await client.connect_stdio_server(
        "database",
        ["python", "mcp_servers/database_server.py",
         "--db", "analytics.db"]
    )

    # 连接远程API Server
    await client.connect_sse_server(
        "weather",
        "https://mcp-server.example.com/weather"
    )

    # 获取所有可用工具（传给LLM）
    available_tools = client.get_available_tools()
    print(f"可用工具: {[t['name'] for t in available_tools]}")

    # 调用工具
    result = await client.call_tool(
        "filesystem:read_file",
        {"path": "/workspace/report.txt"}
    )

    # 读取资源
    data = await client.read_resource("db://analytics/users")

    # 使用提示模板
    prompt = await client.get_prompt(
        "code_review:standard",
        {"language": "python", "code": "def foo(): pass"}
    )
```

Image-Prompt(英文绘图词): A flat-design MCPClient hub diagram: a central "MCPClient" hub box containing three management registries (tools{}, resources{}, prompts{}), connected to three MCP Server boxes radiating outward — "filesystem (stdio)" with file icon and pipe symbol, "database (stdio)" with DB cylinder and pipe, "weather (SSE)" with cloud and network waves — each showing their capability discovery arrows (tools/list, resources/list, prompts/list) flowing back to the hub, tech-blue #409EFF on white background, 2D vector academic style.

---

## 小结

MCP正在成为AI Agent工具调用的标准协议。它的核心价值在于**用统一的接口替代碎片化的集成**——让Agent开发者只需关心"我的Agent需要什么能力"，而不需要关心"每个工具的具体API是什么"。

**关键概念**：
1. **Client-Server架构**：Agent作为MCP Client，工具作为MCP Server
2. **三大原语**：Resources（读数据）、Tools（执行操作）、Prompts（交互模板）
3. **传输层**：stdio（本地）+ SSE/HTTP（远程）
4. **JSON-RPC**：基于JSON-RPC 2.0的标准化通信

**与Function Calling的关系**：MCP不是Function Calling的替代品，而是工具侧的标准化层。Function Calling定义了模型如何"想要"调用工具，MCP定义了工具如何"被"发现和调用。

**未来展望**：
- MCP生态正在快速增长，越来越多的工具提供MCP Server
- MCP可能成为AI Agent时代的"协议标准"，类似于HTTP之于Web
- 与A2A（Agent-to-Agent）协议形成互补，覆盖"Agent-工具"和"Agent-Agent"的通信

记住：**标准化的价值不在于技术的先进性，而在于降低整个生态的协作成本**。MCP的愿景就是让AI Agent与外部世界的连接像插USB设备一样简单。

Image-Prompt(英文绘图词): A flat-design summary hub-and-spoke diagram: a central "MCP Protocol" hub circle with four orbiting concept satellites connected by dotted lines — "Client-Server Architecture" (two paired blocks), "Three Primitives: Resources / Tools / Prompts" (three interlocking shapes), "Transport: stdio + SSE/HTTP" (dual-path arrows), and "JSON-RPC 2.0" (code bracket icon), with a USB-C connector symbol at the center representing the universal-connection vision, tech-blue #409EFF on white background, 2D vector academic style, clean minimalist orbital layout.
