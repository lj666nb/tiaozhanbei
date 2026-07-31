# Skills机制：可复用技能模块

## 引言

在构建AI Agent应用的过程中，一个反复出现的问题是：**如何将复杂的能力封装起来，让不同的Agent能够共享和复用？** 你花了两周时间精心调试了一个"代码审查Agent"的Prompt和工具链，但当你需要在另一个Agent中使用代码审查能力时，你不得不重新来过——复制粘贴Prompt、重新配置工具、重新测试。

**Skills机制**正是为解决这个问题而设计的。它的核心思想很简单：将一组相关的Prompt、工具配置、知识和工作流程打包为可复用的"技能模块"。就像一个软件库封装了可复用的代码一样，Skill封装了可复用的Agent能力。

Image-Prompt(英文绘图词): A flat-design before-after illustration: left side "Without Skills" shows three agent boxes each independently and redundantly building the same capabilities (code review, testing, documentation) with duplicated effort arrows and crossed-out efficiency; right side "With Skills" shows a central shared "Skill Library" repository from which three agents each pull pre-built skill modules via clean download arrows, labeled "Reusability", "Consistency", "Efficiency", tech-blue #409EFF on white background, 2D vector academic style.

---

## Skills的核心概念

### 什么是Skill

一个Skill是一个**自包含的能力模块**，包含完成特定类型任务所需的一切：

```
┌─────────────────────────────────────┐
│            Skill 包的组成            │
│                                     │
│  ┌─────────────────────────────┐    │
│  │  System Prompt              │    │
│  │  (角色定义、行为规范、约束)   │    │
│  ├─────────────────────────────┤    │
│  │  工具配置 (Tool Config)      │    │
│  │  (MCP Server连接、参数预设)   │    │
│  ├─────────────────────────────┤    │
│  │  知识库 (Knowledge Base)     │    │
│  │  (领域知识、最佳实践、示例)   │    │
│  ├─────────────────────────────┤    │
│  │  工作流 (Workflow)           │    │
│  │  (多步骤流程、决策逻辑)       │    │
│  ├─────────────────────────────┤    │
│  │  输入/输出Schema             │    │
│  │  (参数定义、输出格式)         │    │
│  └─────────────────────────────┘    │
└─────────────────────────────────────┘
```

### Skill vs Agent vs Tool

| 维度 | Tool（工具） | Skill（技能） | Agent（智能体） |
|------|------------|-------------|---------------|
| **粒度** | 原子操作 | 复合能力 | 自主实体 |
| **示例** | web_search | code_reviewer | 全栈开发Agent |
| **Prompt** | 工具描述 | 完整System Prompt | Agent人格 |
| **工具** | 无 | 包含一组工具配置 | 包含多种Skill |
| **状态** | 无状态 | 无状态 | 有状态（会话历史） |
| **复用性** | 高 | 很高 | 低（定制化强） |
| **独立性** | 完全依赖Agent | 可独立工作 | 完全独立 |

Image-Prompt(英文绘图词): A flat-design layered skill package diagram: a rectangular card showing a Skill's five stacked internal layers — "System Prompt" (top layer, role definition and constraints), "Tool Config" (MCP Server connections and parameter presets), "Knowledge Base" (domain knowledge and best practices documents), "Workflow" (multi-step process and decision logic), "I/O Schema" (bottom layer, parameter definition and output format) — with a comparison table below contrasting Tool (atomic wrench icon), Skill (composite toolbox icon), and Agent (autonomous robot icon) across granularity, reusability, and independence dimensions, tech-blue #409EFF on white background, 2D vector academic style.

---

## Skill的定义和注册

### Skill定义格式

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class SkillCategory(Enum):
    """Skill分类"""
    CODING = "coding"               # 代码相关
    ANALYSIS = "analysis"           # 分析相关
    CREATIVE = "creative"           # 创意相关
    COMMUNICATION = "communication" # 沟通相关
    DATA = "data"                   # 数据处理
    DOMAIN = "domain"               # 特定领域
    UTILITY = "utility"             # 工具性Skill


@dataclass
class SkillDefinition:
    """
    Skill的完整定义。

    这是Skill包的核心——定义了Skill的一切。
    """
    # 基本信息
    name: str                          # Skill名称（唯一标识）
    display_name: str                  # 显示名称
    version: str                       # 语义版本号 (如 "1.2.0")
    category: SkillCategory            # 分类
    description: str                   # 简短描述
    tags: List[str] = field(default_factory=list)

    # System Prompt
    system_prompt: str = ""            # Skill的核心Prompt

    # 工具
    tools: List[dict] = field(default_factory=list)
    # 格式：[{"name": "tool_name", "config": {...}}]

    # MCP Server
    mcp_servers: List[dict] = field(default_factory=list)
    # 格式：[{"name": "server_name", "command": ["node", "server.js"]}]

    # 知识
    knowledge_files: List[str] = field(default_factory=list)
    # 知识文件的路径

    # 输入/输出Schema
    input_schema: Optional[dict] = None
    output_schema: Optional[dict] = None

    # 元数据
    author: str = ""
    license: str = "MIT"
    dependencies: List[str] = field(default_factory=list)
    # 依赖的其他Skill

    # 示例
    examples: List[dict] = field(default_factory=list)
    # 格式：[{"input": "用户输入", "expected_output": "期望输出"}]

    # 约束
    constraints: Dict[str, Any] = field(default_factory=dict)
    # 如：{"max_tokens": 4000, "temperature": 0.3}

    def to_manifest(self) -> dict:
        """导出为manifest文件"""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "version": self.version,
            "category": self.category.value,
            "description": self.description,
            "tags": self.tags,
            "author": self.author,
            "license": self.license,
            "dependencies": self.dependencies,
            "tools": [t["name"] for t in self.tools],
            "mcp_servers": [s["name"] for s in self.mcp_servers],
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
        }
```

### Skill注册系统

```python
class SkillRegistry:
    """
    Skill注册中心。

    管理所有可用Skill的生命周期。
    """

    def __init__(self):
        self._skills: Dict[str, SkillDefinition] = {}
        self._category_index: Dict[str, set] = {}
        self._tag_index: Dict[str, set] = {}

    def register(self, skill: SkillDefinition) -> str:
        """
        注册一个Skill。

        如果同名Skill已存在，比较版本号——只接受更高版本。
        """
        skill_id = f"{skill.name}@{skill.version}"

        if skill.name in self._skills:
            existing = self._skills[skill.name]
            if self._compare_versions(skill.version,
                                       existing.version) <= 0:
                raise ValueError(
                    f"Skill {skill.name} v{skill.version} "
                    f"不高于已注册的 v{existing.version}"
                )

        self._skills[skill.name] = skill

        # 更新分类索引
        cat = skill.category.value
        if cat not in self._category_index:
            self._category_index[cat] = set()
        self._category_index[cat].add(skill.name)

        # 更新标签索引
        for tag in skill.tags:
            if tag not in self._tag_index:
                self._tag_index[tag] = set()
            self._tag_index[tag].add(skill.name)

        print(f"Skill已注册: {skill_id}")
        return skill_id

    def get(self, skill_name: str,
            version: str = None) -> Optional[SkillDefinition]:
        """获取Skill"""
        skill = self._skills.get(skill_name)
        if not skill:
            return None
        if version and skill.version != version:
            return None
        return skill

    def search(self, category: str = None,
               tags: List[str] = None,
               keyword: str = None) -> List[SkillDefinition]:
        """搜索Skill"""
        results = set(self._skills.keys())

        if category:
            results &= self._category_index.get(category, set())

        if tags:
            for tag in tags:
                results &= self._tag_index.get(tag, set())

        skills = [self._skills[name] for name in results]

        if keyword:
            keyword_lower = keyword.lower()
            skills = [
                s for s in skills
                if keyword_lower in s.description.lower()
                or keyword_lower in s.display_name.lower()
            ]

        return skills

    def list_all(self) -> List[dict]:
        """列出所有已注册Skill"""
        return [s.to_manifest() for s in self._skills.values()]

    def _compare_versions(self, v1: str, v2: str) -> int:
        """比较两个语义版本号"""
        from packaging import version
        v1_parsed = version.parse(v1)
        v2_parsed = version.parse(v2)
        if v1_parsed > v2_parsed:
            return 1
        elif v1_parsed < v2_parsed:
            return -1
        return 0
```

Image-Prompt(英文绘图词): A flat-design SkillDefinition dataclass diagram: a central labeled building block showing key fields (name, version, category, description, system_prompt, tools, mcp_servers, input_schema, output_schema) as structured slots, connected on the right to a "SkillRegistry" box with two index branches — category_index (coding, analysis, creative, etc.) and tag_index — showing the registration flow with a version comparison check (v1.2.0 > v1.1.0 checkmark), tech-blue #409EFF on white background, 2D vector academic style.

---

## Skill的加载与组合

### 热加载机制

```python
class SkillLoader:
    """
    Skill加载器。

    支持从多种来源加载Skill：
    - 本地目录
    - Git仓库
    - Skill市场（注册中心）
    - 包管理器
    """

    def __init__(self, registry: SkillRegistry):
        self.registry = registry

    def load_from_directory(self, skill_path: str) -> str:
        """
        从本地目录加载Skill。

        目录结构：
        skill_name/
        ├── skill.yaml        # Skill manifest
        ├── prompt.md         # System Prompt
        ├── tools.yaml        # 工具配置
        ├── knowledge/        # 知识库文件
        │   ├── best_practices.md
        │   └── examples.md
        └── tests/            # 测试用例
            └── test_cases.yaml
        """
        import yaml

        # 读取manifest
        with open(f"{skill_path}/skill.yaml", "r") as f:
            manifest = yaml.safe_load(f)

        # 读取System Prompt
        prompt_path = f"{skill_path}/{manifest.get('prompt_file', 'prompt.md')}"
        with open(prompt_path, "r") as f:
            system_prompt = f.read()

        # 读取工具配置
        tools = []
        tools_path = f"{skill_path}/tools.yaml"
        try:
            with open(tools_path, "r") as f:
                tools = yaml.safe_load(f)
        except FileNotFoundError:
            pass

        # 构建Skill定义
        skill_def = SkillDefinition(
            name=manifest["name"],
            display_name=manifest["display_name"],
            version=manifest["version"],
            category=SkillCategory(manifest["category"]),
            description=manifest["description"],
            tags=manifest.get("tags", []),
            system_prompt=system_prompt,
            tools=tools,
            author=manifest.get("author", ""),
            input_schema=manifest.get("input_schema"),
            output_schema=manifest.get("output_schema"),
            examples=manifest.get("examples", []),
            constraints=manifest.get("constraints", {}),
        )

        return self.registry.register(skill_def)

    def load_from_marketplace(self, skill_name: str,
                               version: str = "latest") -> str:
        """
        从Skill市场下载并加载。

        类似npm install / pip install。
        """
        # 1. 从市场获取Skill元数据
        metadata = self._fetch_marketplace_metadata(
            skill_name, version
        )

        # 2. 下载Skill包
        package_path = self._download_package(
            metadata["download_url"]
        )

        # 3. 验证包完整性
        if not self._verify_package(package_path,
                                     metadata["checksum"]):
            raise ValueError("Skill包校验失败")

        # 4. 加载
        return self.load_from_directory(package_path)

    def load_dependencies(self, skill: SkillDefinition):
        """递归加载Skill的依赖"""
        for dep in skill.dependencies:
            dep_name, dep_version = self._parse_dependency(dep)
            if not self.registry.get(dep_name):
                print(f"  加载依赖: {dep_name}@{dep_version}")
                self.load_from_marketplace(dep_name, dep_version)
```

### Skill组合

```python
class SkillComposer:
    """
    Skill组合器。

    将多个Skill组合成一个复合Skill或Agent配置。
    这是Skill机制最强大的能力——通过组合实现复杂功能。
    """

    def compose_agent(self, skills: List[str],
                       agent_config: dict = None) -> dict:
        """
        将多个Skill组合为一个Agent的完整配置。

        这是Agent开发的"乐高模式"。
        """
        agent_skills = []
        all_tools = []
        all_mcp_servers = []
        combined_prompt = ""
        all_knowledge = []

        for skill_name in skills:
            skill = self.registry.get(skill_name)
            if not skill:
                raise ValueError(f"Skill '{skill_name}' 未找到")

            agent_skills.append(skill)

            # 合并工具（去重）
            for tool in skill.tools:
                if tool["name"] not in [t["name"] for t in all_tools]:
                    all_tools.append(tool)

            # 合并MCP Server
            for server in skill.mcp_servers:
                if server["name"] not in [
                    s["name"] for s in all_mcp_servers
                ]:
                    all_mcp_servers.append(server)

            # 合并知识
            all_knowledge.extend(skill.knowledge_files)

        # 组合System Prompt
        combined_prompt = self._compose_system_prompt(
            agent_config or {}, agent_skills
        )

        agent_def = {
            "meta": agent_config or {},
            "skills": [s.name for s in agent_skills],
            "system_prompt": combined_prompt,
            "tools": all_tools,
            "mcp_servers": all_mcp_servers,
            "knowledge_files": all_knowledge,
        }

        return agent_def

    def _compose_system_prompt(self, config: dict,
                                skills: List[SkillDefinition]) -> str:
        """
        组合多个Skill的System Prompt。

        策略：
        1. 基础Agent Prompt（config中定义）
        2. 各Skill的领域Prompt（按优先级排列）
        3. 通用的协作规则和行为约束
        """
        parts = []

        # Agent基础角色
        if config.get("base_prompt"):
            parts.append(config["base_prompt"])

        # 各Skill的能力描述
        parts.append("\n## 你拥有的技能\n")
        for i, skill in enumerate(skills, 1):
            parts.append(
                f"### 技能{i}: {skill.display_name}\n"
                f"{skill.system_prompt[:500]}...\n"
            )

        # 协作规则
        parts.append("""
## 技能使用规则

1. 根据用户需求选择合适的技能
2. 可以在同一次交互中使用多个技能
3. 如果一个技能无法解决问题，尝试组合多个技能
4. 使用技能时遵循该技能的定义规范和输出格式
""")

        return "\n".join(parts)

    def create_skill_pipeline(self,
                               skill_sequence: List[str]) -> callable:
        """
        创建Skill流水线：按顺序执行一系列Skill。

        适用于有明确先后顺序的任务。
        """
        skills = [self.registry.get(s) for s in skill_sequence]

        def pipeline(input_data):
            result = input_data
            for skill in skills:
                result = self._execute_skill(skill, result)
            return result

        return pipeline

    def create_skill_ensemble(self,
                               skill_names: List[str],
                               vote_strategy: str = "majority") -> callable:
        """
        创建Skill集成：多个Skill并行处理，投票决定最终结果。

        适用于需要多角度分析的任务。
        """
        skills = [self.registry.get(s) for s in skill_names]

        def ensemble(input_data):
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = {
                    executor.submit(
                        self._execute_skill, skill, input_data
                    ): skill.name
                    for skill in skills
                }
                results = {}
                for future in concurrent.futures.as_completed(futures):
                    name = futures[future]
                    results[name] = future.result()

            # 投票
            if vote_strategy == "majority":
                return self._majority_vote(results)
            else:
                return self._synthesize_results(results)

        return ensemble
```

Image-Prompt(英文绘图词): A flat-design skill loading and composition pipeline: left side shows three loading sources (Local Directory folder, Git Repository, Marketplace cloud) feeding into a "SkillLoader" gear; center shows the "SkillComposer" module with three composition strategies as tabs — "Compose Agent" (multiple skills merging into one agent config with combined tools, prompts, and knowledge), "Create Pipeline" (sequential skill chain arrows), "Create Ensemble" (parallel skills voting into a majority result); output on the right is a complete "Agent Definition" JSON block, tech-blue #409EFF on white background, 2D vector academic style.

---

## Skill市场和生态

### 市场架构

```
┌──────────────────────────────────────────────────────┐
│                  Skill 市场生态                       │
│                                                      │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │ Skill发布│   │ Skill发现│   │ Skill使用│        │
│  │ 者       │   │          │   │ 者       │        │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘        │
│       │               │              │               │
│       └───────────────┼──────────────┘               │
│                       │                              │
│              ┌────────▼────────┐                     │
│              │  Skill Registry │                     │
│              │  (市场中心)      │                     │
│              └────────┬────────┘                     │
│                       │                              │
│       ┌───────────────┼───────────────┐              │
│       │               │               │              │
│  ┌────▼────┐    ┌────▼────┐    ┌────▼────┐          │
│  │ 版本管理│    │ 质量审核│    │ 安全扫描│          │
│  └─────────┘    └─────────┘    └─────────┘          │
└──────────────────────────────────────────────────────┘
```

### 市场API示例

```python
class SkillMarketplace:
    """
    Skill市场的核心功能。

    类似npm/PyPI，但专门为AI Skill设计。
    """

    def __init__(self, base_url: str):
        self.base_url = base_url

    async def search(self, query: str,
                     category: str = None,
                     sort_by: str = "downloads") -> list:
        """
        搜索Skill。

        类似 npm search / pip search。
        """
        # GET /api/v1/skills/search?q=code+review&category=coding
        pass

    async def get_skill_detail(self, skill_name: str) -> dict:
        """
        获取Skill详情。

        包括：版本历史、下载量、评分、依赖、README等。
        """
        # GET /api/v1/skills/{skill_name}
        pass

    async def download(self, skill_name: str,
                        version: str = "latest") -> bytes:
        """
        下载Skill包。
        """
        # GET /api/v1/skills/{skill_name}/download?version=1.2.0
        pass

    async def publish(self, skill_path: str,
                       auth_token: str) -> dict:
        """
        发布Skill到市场。
        """
        # POST /api/v1/skills/publish
        pass

    async def get_stats(self, skill_name: str) -> dict:
        """
        获取Skill的统计信息。

        包括：总下载量、周下载量、评分分布、依赖者数量。
        """
        pass
```

Image-Prompt(英文绘图词): A flat-design marketplace ecosystem diagram: three role columns — left "Skill Publishers" (uploading package icons), center "Skill Registry Hub" (central database cylinder with API endpoints labeled search/get/download/publish), right "Skill Consumers" (agents pulling skill packages with install arrows) — with three supporting pillars below: "Version Management" (version tree), "Quality Review" (checklist with approval stamp), "Security Scanning" (shield with vulnerability scan), the whole scene evoking an app-store-like ecosystem, tech-blue #409EFF on white background, 2D vector academic style.

---

## 在企业Agent平台中的应用

### 企业Skill管理平台

```python
class EnterpriseSkillPlatform:
    """
    企业级Skill管理平台。

    在企业内部管理Skill的创建、审核、发布和使用。
    """

    def __init__(self):
        self.registry = SkillRegistry()
        self.loader = SkillLoader(self.registry)
        self.composer = SkillComposer(self.registry)

        # 企业内部Skill
        self.internal_skills: Dict[str, dict] = {}

        # 第三方Skill（需审批）
        self.third_party_skills: Dict[str, dict] = {}

        # 审批工作流
        self.approval_queue: list = []

    def create_internal_skill(self, request: dict,
                               creator: str) -> str:
        """
        创建企业内部Skill。

        流程：创建 → 内部测试 → 安全审查 → 审批 → 发布
        """
        skill_id = f"internal-{request['name']}"

        skill_record = {
            "id": skill_id,
            "status": "draft",
            "creator": creator,
            "created_at": datetime.now(),
            "definition": request,
            "tests": [],
            "security_scan": None,
            "approvals": [],
        }

        self.internal_skills[skill_id] = skill_record
        return skill_id

    def submit_for_review(self, skill_id: str):
        """提交Skill审查"""
        skill = self.internal_skills[skill_id]
        skill["status"] = "under_review"

        # 添加到审批队列
        self.approval_queue.append(skill_id)

        # 触发自动化检查
        self._run_automated_checks(skill_id)

    def _run_automated_checks(self, skill_id: str):
        """运行自动化质量检查"""
        skill = self.internal_skills[skill_id]
        check_results = {}

        # 1. Prompt质量检查
        check_results["prompt_quality"] = self._check_prompt(
            skill["definition"].get("system_prompt", "")
        )

        # 2. 安全检查
        check_results["security"] = self._security_scan(
            skill["definition"]
        )

        # 3. 依赖检查
        check_results["dependencies"] = self._check_dependencies(
            skill["definition"].get("dependencies", [])
        )

        # 4. 性能检查
        check_results["performance"] = self._estimate_token_cost(
            skill["definition"]
        )

        skill["automated_checks"] = check_results

    def _check_prompt(self, prompt: str) -> dict:
        """检查Prompt质量"""
        issues = []

        if len(prompt) < 100:
            issues.append("System Prompt过短（<100字符）")
        if len(prompt) > 8000:
            issues.append("System Prompt过长（>8000字符），可能影响性能")

        # 检查是否包含安全指令
        safety_keywords = ["安全", "权限", "拒绝", "隐私", "safety"]
        if not any(kw in prompt.lower() for kw in safety_keywords):
            issues.append("缺少安全相关指令")

        return {
            "score": max(0, 100 - len(issues) * 20),
            "issues": issues
        }

    def _security_scan(self, definition: dict) -> dict:
        """安全扫描"""
        vulnerabilities = []

        # 检查工具权限
        tools = definition.get("tools", [])
        high_risk_tools = ["file_delete", "command_execute",
                           "db_write", "system_call"]
        for tool in tools:
            if tool["name"] in high_risk_tools:
                vulnerabilities.append({
                    "tool": tool["name"],
                    "risk": "high",
                    "recommendation": "添加权限范围限制"
                })

        return {
            "has_vulnerabilities": len(vulnerabilities) > 0,
            "vulnerabilities": vulnerabilities
        }

    def deploy_skill_to_agent(self, skill_name: str,
                                agent_id: str):
        """将Skill部署到Agent"""
        skill = self.registry.get(skill_name)
        if not skill:
            raise ValueError(f"Skill '{skill_name}' 未注册")

        # 获取Agent当前配置
        agent_config = self._get_agent_config(agent_id)

        # 注入Skill
        agent_config["skills"].append(skill.name)
        agent_config["system_prompt"] = (
            agent_config["system_prompt"] +
            f"\n\n## 技能: {skill.display_name}\n" +
            skill.system_prompt
        )
        agent_config["tools"].extend(skill.tools)

        # 更新Agent
        self._update_agent(agent_id, agent_config)
        print(f"Skill '{skill_name}' 已部署到 Agent '{agent_id}'")
```

### 典型企业用例

```
场景1：客服Agent平台
  - Skill: "产品FAQ"（产品知识问答）
  - Skill: "订单查询"（查询订单状态）
  - Skill: "退换货流程"（处理退换货申请）
  - Skill: "情绪安抚"（安抚不满意客户）
  → 根据客户需求动态组合这些Skill

场景2：开发Agent平台
  - Skill: "代码审查"（代码质量和安全性审查）
  - Skill: "单元测试生成"（自动生成测试用例）
  - Skill: "API文档生成"（从代码生成文档）
  - Skill: "数据库迁移"（生成和执行迁移脚本）
  → 开发人员按需加载Skill到他们的Agent中

场景3：数据分析Agent平台
  - Skill: "数据探索"（自动分析数据结构）
  - Skill: "可视化"（生成图表）
  - Skill: "统计检验"（执行统计假设检验）
  - Skill: "报告生成"（生成分析报告）
  → 分析人员组合Skill构建分析流水线
```

Image-Prompt(英文绘图词): A flat-design enterprise platform workflow diagram: a horizontal approval pipeline showing the internal skill creation journey through five stages — "Draft" (pencil icon) → "Internal Test" (flask icon) → "Security Scan" (shield icon with vulnerability list) → "Review & Approval" (checkmark stamp) → "Deploy to Agent" (agent injection arrow) — with three use-case panels below: Customer Service (speech bubble with FAQ/Order/Return/Emotion skill chips), Development (code brackets with Review/Test/Docs/Migration chips), Data Analysis (chart with Explore/Visualize/Stats/Report chips), tech-blue #409EFF on white background, 2D vector academic style.

---

## 版本管理与兼容性

```python
class SkillVersionManager:
    """
    Skill版本管理。

    处理Skill的版本兼容性和平滑升级。
    """

    @staticmethod
    def check_compatibility(required_version: str,
                              available_version: str) -> bool:
        """
        检查版本兼容性。

        语义版本规则：
        - 主版本号变化：不兼容的API变更
        - 次版本号变化：向下兼容的功能新增
        - 修订号变化：向下兼容的问题修正

        例如：Agent要求 skill>=1.2.0,<2.0.0
        """
        from packaging import version, specifiers
        spec = specifiers.SpecifierSet(f">={required_version}")
        return spec.contains(available_version)

    @staticmethod
    def resolve_dependencies(
            required_skills: List[str],
            available_versions: Dict[str, List[str]]) -> dict:
        """
        依赖解析：找到满足所有约束的版本组合。

        类似于pip/npm的依赖解析器。
        """
        # 使用回溯算法找到可行的版本组合
        resolved = {}
        # ... 依赖解析逻辑
        return resolved

    @staticmethod
    def deprecation_notice(skill_name: str,
                            current_version: str,
                            deprecated_in: str,
                            replacement: str = None):
        """标记Skill为弃用"""
        notice = {
            "skill": skill_name,
            "current_version": current_version,
            "deprecated_in": deprecated_in,
            "status": "deprecated",
            "migration_guide": None
        }
        if replacement:
            notice["replacement"] = replacement
            notice["migration_guide"] = (
                f"请迁移到 {replacement}。"
                f"当前Skill将在下一个主版本中移除。"
            )
        return notice
```

Image-Prompt(英文绘图词): A flat-design semantic versioning diagram: a version number "1.2.3" exploded into its three components — MAJOR (1) with "Breaking Changes" icon (broken chain), MINOR (2) with "Backward-Compatible Features" icon (plus in a circle), PATCH (3) with "Bug Fixes" icon (bandage) — and a dependency resolution tree branching from a root skill node through child nodes with version constraints ("skill>=1.2.0,<2.0.0"), with a deprecation notice flag on an outdated version node pointing to a replacement, tech-blue #409EFF on white background, 2D vector academic style.

---

## 小结

Skills机制代表了AI Agent开发从"手工作坊"走向"工业化生产"的关键一步。它让Agent能力的复用像使用软件库一样简单，大幅降低了复杂Agent系统的开发成本和维护难度。

**核心概念**：
1. **Skill = Prompt + Tools + Knowledge + Workflow**：封装完整能力的模块
2. **注册与发现**：通过注册中心管理可用Skill
3. **热加载**：运行时动态加载和卸载Skill
4. **组合**：通过组合多个Skill构建复杂Agent
5. **市场**：Skill的共享、分发和发现平台
6. **版本管理**：语义版本 + 依赖解析

**设计原则**：
- **单一职责**：每个Skill只做一件事，做好一件事
- **接口清晰**：定义明确的输入/输出Schema
- **独立可测**：每个Skill可以独立测试
- **可组合**：Skill之间可以自由组合
- **安全可控**：每个Skill有明确的安全边界

**企业应用要点**：
- 建立内部的Skill审批和发布流程
- 为Skill添加安全审查和性能评估
- 维护Skill的版本兼容性矩阵
- 建立Skill使用的最佳实践文档

Skills机制的美妙之处在于：它把"如何构建好的Agent"的知识从个人经验转化为可共享、可积累、可进化的组织资产。随着Skill生态的成熟，构建一个强大的Agent将越来越像"搭积木"——选择需要的Skills，组合、配置，完成。

Image-Prompt(英文绘图词): A flat-design puzzle assembly illustration: five individual puzzle pieces floating into place to form a complete Agent shape — pieces labeled "Prompt" (text bubble), "Tools" (wrench), "Knowledge" (book), "Workflow" (flowchart), and "I/O Schema" (brackets with arrows) — with five guiding design principle lines radiating outward like a compass: "Single Responsibility", "Clear Interface", "Independently Testable", "Composable", "Safe & Controlled", all tech-blue #409EFF on white background, 2D vector academic style, the assembled Agent puzzle glowing softly.
