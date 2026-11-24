# 当前会话状态 — 2026-07-18（重启后必须看）

## 今天做了什么
- ECC 安装为 OS 层（.claude/ 子目录，没碰灵魂文件）
- Nexus 从 Agent 平台简化为知识库
- **nexus_kb 独立知识库系统建成**（6 Phase，全部端到端测试通过）
- 内置 Qwen2-VL-2B 替代 LM Studio，零外部依赖

## 知识库在哪
- 代码：`nexus_kb/`
- 数据：`D:/node/`（92269文件），索引：`D:/node/.nexus/`
- 模型：`C:/Users/87999/.nexus/models/qwen2-vl-2b-instruct/`
- 设计文档：`specs/002-nexus-knowledge-base/PLAN.md`

## 怎么用（必须用 Python312 + CUDA）
```bash
# 跑模型必须用这个 Python（Hermes venv 是 CPU 版）
C:/Users/87999/AppData/Local/Programs/Python/Python312/python.exe

# 端到端测试
python nexus_kb/test_e2e.py

# 启动 HTTP API
python -c "from nexus_kb.api.server import serve; from nexus_kb import KnowledgeBase; serve(KnowledgeBase('D:/node'))"

# 后台摄入 D:/node
python nexus_kb/eat_all.py

# 分析整理
python -c "from nexus_kb import KnowledgeBase; kb=KnowledgeBase('D:/node'); print(kb.auto_organize())"
```

## 三个不准偏离
1. 不做 Agent 平台，做知识库
2. 用本地四件套，不调外部 API
3. 丢进去就行——不问用户，自动处理

## 核心踩坑记录
- Python 环境：Hermes venv（CPU torch）≠ Python312（CUDA torch）。跑模型必须用后者
- 日记 7/17 第 53 行就写了，7/18 又踩一次。下次先读日记
- 先查代码再断言：nexus/knowledge/ 四件套代码全有
