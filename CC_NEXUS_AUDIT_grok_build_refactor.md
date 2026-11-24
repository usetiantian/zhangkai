# 📋 CC 重构审计任务单 - 参照 grok-build 完整实现乾坤

## 🎯 核心要求

**❌ 禁止行为：**
- 不要只看模块名就自己瞎写！
- 不要复制粘贴，要拆解设计思想后用 Python 等价实现
- 不要跳过源码直接实现

**✅ 必须行为：**
- 每个模块先读 grok-build 的 Rust 完整源码（在 `C:\Users\87999\claude-workspace\grok-build`）
- 理解架构设计后再用 Python 重写
- 逐模块对照实现，不能遗漏任何功能
- 每次修改前备份原文件
- 每个模块都要有单元测试

---

## 📂 任务清单（按优先级排序）

### **【最高优先级】Sampler Actor 层重构**

**目标：** 参照 `xai-grok-sampler` crate 完整实现 Python Sampler Actor

**grok-build 源码路径：**
```
C:\Users\87999\claude-workspace\grok-build\crates\codegen\xai-grok-sampler\src\
├── actor.rs           # SamplerActor - Actor 模式采样器
├── client.rs          # SamplingClient - HTTP 客户端
├── retry.rs           # RetryPolicy - 重试策略（带抖动）
├── metrics.rs         # InferenceLatencyStats - 指标收集
├── events.rs          # SamplingEvent - 事件驱动
└── stream.rs          # 流式响应处理
```

**必须实现的 Python 等价模块：**

1. **`qiankun/agent/sampler_actor.py`**（新建）
   ```python
   class SamplerActor:
       """Actor 模式采样器 - 隔离状态 + 并发控制"""
       
       def __init__(self, config: Dict):
           # 从配置构建，不是硬编码！
           self.request_id_counter = 0
           self.active_requests = {}  # request_id -> request_state
           
       async def on_message(self, msg: Message) -> SamplingEvent | None:
           """Actor 模式：接收消息"""
           pass
       
       async def handle_request(
           self, 
           request_id: str, 
           prompt: str, 
           history: list[dict]
       ) -> SamplingResponse:
           """处理采样请求（带重试）"""
           pass
       
       def retry_with_backoff(
           self, 
           error: Exception, 
           attempt: int
       ) -> bool:
           """指数退避 + 抖动重试策略"""
           pass
       
       def record_metric(self, latency_ms: float) -> None:
           """记录指标（耗时、token 数）"""
           pass
   ```

2. **`qiankun/tools/llm/sampling_client.py`**（新建）
   ```python
   class SamplingClient:
       """HTTP 采样客户端 - 参照 client.rs"""
       
       async def stream_chat_completions(
           self,
           model_id: str,
           messages: list[dict],
           request_id: str
       ) -> AsyncGenerator[str]:
           """流式响应生成器"""
           pass
   ```

**验收标准：**
- [ ] SamplerActor 用 Actor 模式实现（无状态隔离）
- [ ] 重试策略带指数退避 + 抖动（参考 `retry_backoff_with_jitter`）
- [ ] 指标收集系统记录每次采样耗时
- [ ] 事件驱动架构处理采样事件

---

### **【最高优先级】Agent Builder 层重构**

**目标：** 参照 `xai-grok-agent` crate 完整实现 Python Agent Builder

**grok-build 源码路径：**
```
C:\Users\87999\claude-workspace\grok-build\crates\codegen\xai-grok-agent\src\
├── lib.rs              # 模块入口
├── agent.rs            # Agent 类型定义
├── builder.rs          # AgentBuilder - 构建器模式
├── config.rs           # AgentDefinition - 配置即代码
├── discovery.rs        # 工具发现机制
├── plugins.rs          # 插件系统
└── compaction.rs       # 上下文压缩策略
```

**必须实现的 Python 等价模块：**

1. **`qiankun/agent/builder.py`**（新建）
   ```python
   class AgentBuilder:
       """构建器模式 - 分步构建 Agent"""
       
       def with_tools(self, tools: dict) -> 'AgentBuilder':
           pass
       
       def with_system_prompt(self, prompt: str) -> 'AgentBuilder':
           pass
       
       def with_compaction_policy(self, policy: CompactionPolicy) -> 'AgentBuilder':
           pass
       
       def with_model_config(self, config: ModelConfig) -> 'AgentBuilder':
           pass
       
       def build(self) -> Agent:
           """最后一步：构建完整的 Agent"""
           pass
   ```

2. **`qiankun/config/agent_definition.py`**（新建）
   ```python
   @dataclass
   class AgentDefinition:  # 配置即代码！
       persona_name: str
       toolset: str = "grok"  # "grok" / "minimal" / "full"
       max_tokens: int = 4096
       system_prompt: Optional[str] = None
       compaction_policy: str = "token"  # "token" / "role" / "none"
   ```

**验收标准：**
- [ ] 使用构建器模式，分步构建 Agent
- [ ] 配置即代码（从 config.yaml 或环境加载）
- [ ] 有工具发现机制（自动扫描 tools/ 目录）
- [ ] 插件系统支持动态注册

---

### **【高优先级】Tools Runtime 层重构**

**目标：** 参照 `xai-tool-runtime` + `xai-tool-protocol` 实现完整工具系统

**grok-build 源码路径：**
```
C:\Users\87999\claude-workspace\grok-build\crates\common\xai-tool-runtime\src\
├── lib.rs              # 模块入口
├── runtime.rs          # ToolRuntime - 工具运行时
└── protocol.rs         # 工具协议定义
```

**必须实现的 Python 等价模块：**

1. **`qiankun/tools/runtime/tool_runtime.py`**（新建）
   ```python
   class ToolRuntime:
       """工具运行时 - 管理工具生命周期"""
       
       def register(self, tool_name: str, tool_impl: Tool) -> None:
           """注册工具"""
           pass
       
       async def invoke(
           self,
           tool_name: str,
           params: dict
       ) -> Any:
           """调用工具（带超时 + 错误处理）"""
           pass
   
   @dataclass
   class ToolProtocol:  # 工具协议定义
       name: str
       schema: dict  # JSON Schema
       implementation: Callable
   ```

2. **`qiankun/tools/mcp/tool_registry.py`**（新建）
   ```python
   class MCPToolRegistry:
       """MCP 工具注册表"""
       
       def connect_all(self) -> list[str]:
           """连接所有 MCP 服务器并注册工具"""
           pass
   
       def discover_tools(self) -> dict[str, ToolProtocol]:
           """自动发现可用工具"""
           pass
   ```

**验收标准：**
- [ ] 工具运行时管理生命周期（注册→调用→卸载）
- [ ] 支持 MCP 协议
- [ ] 自动工具发现机制

---

### **【高优先级】Compaction Policy 层重构**

**目标：** 参照 `xai-grok-compaction` crate 实现上下文压缩策略

**grok-build 源码路径：**
```
C:\Users\87999\claude-workspace\grok-build\crates\codegen\xai-grok-compaction\src\
├── lib.rs
└── compactor.rs        # 上下文压缩器
```

**必须实现的 Python 等价模块：**

1. **`qiankun/agent/compaction.py`**（新建）
   ```python
   @dataclass
   class CompactionPolicy:  # 配置即代码！
       strategy: str = "token"  # "token" / "role" / "summary"
       max_tokens: int = 4096
       
       def compact_history(self, messages: list[dict]) -> list[dict]:
           """压缩历史消息"""
           pass
   
   class TokenCompactor(CompactionPolicy):
       """基于 token 数的压缩策略"""
   
   class RoleBasedCompactor(CompactionPolicy):
       """基于角色的压缩策略（保留关键角色）"""
   ```

**验收标准：**
- [ ] 支持多种压缩策略（token/role/summary）
- [ ] 配置即代码，从 config.yaml 读取策略参数

---

### **【中优先级】Plugins & Discovery 层重构**

**目标：** 实现插件系统和工具发现机制

**必须实现的 Python 等价模块：**

1. **`qiankun/tools/plugins/plugin_registry.py`**（新建）
2. **`qiankun/tools/discovery/tool_discovery.py`**（新建）

---

## 📊 进度跟踪表

| 任务 ID | 任务名称 | 状态 | 负责人 | 截止时间 |
|--------|---------|------|--------|----------|
| TASK-001 | Sampler Actor 层重构 | ⏳ 待开始 | CC | T+2 天 |
| TASK-002 | Agent Builder 层重构 | ⏳ 待开始 | CC | T+2 天 |
| TASK-003 | Tools Runtime 层重构 | ⏳ 待开始 | CC | T+3 天 |
| TASK-004 | Compaction Policy 层重构 | ⏳ 待开始 | CC | T+3 天 |
| TASK-005 | Plugins & Discovery | ⏳ 待开始 | CC | T+4 天 |

---

## 🔍 审计监督规则（蓝莓职责）

### **我的职责：**
1. ✅ 每次提交前审核代码是否参照了 grok-build 源码
2. ✅ 检查每个模块都有单元测试
3. ✅ 确保没有遗漏任何功能
4. ✅ 验证设计思想被正确理解，不是简单复制粘贴

### **CC 必须遵守：**
- ❌ 禁止只看模块名就自己写
- ❌ 禁止跳过源码阅读
- ❌ 禁止遗漏功能点
- ✅ 必须每次修改前备份原文件
- ✅ 每个模块必须有单元测试
- ✅ 代码审查必须逐行对照 grok-build

---

## 🎯 验收流程

**阶段 1：代码审计（蓝莓）**
- 逐模块对照 grok-build 源码
- 检查是否遗漏任何功能
- 验证设计思想被正确理解

**阶段 2：单元测试（CC）**
- 每个关键路径必须有测试
- 覆盖率目标 ≥ 80%

**阶段 3：端到端测试（蓝莓 + CC）**
- 采样器→决策引擎→工具执行→结果反馈
- 完整链路验证

---

## 📝 提交规范

CC 每次提交必须包含：
```markdown
# [重构] <模块名> - 参照 grok-build/<crate-name>

## ✅ 对照清单
- [ ] 已读取 grok-build/<crate>/src/*.rs
- [ ] 理解了架构设计思想
- [ ] Python 等价实现完成
- [ ] 单元测试覆盖关键路径
- [ ] 与原文件对比差异说明

## 📊 功能对照表
| grok-build 功能 | qiankun 实现位置 | 状态 |
|----------------|------------------|------|
| SamplerActor.actor.rs | qiankun/agent/sampler_actor.py | ✅ |
```

---

**任务创建时间：** 2026-07-21  
**监督人：** 蓝莓  
**最终验收标准：** 乾坤系统功能完全对齐 grok-build，代码质量不降反升！
