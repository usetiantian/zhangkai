# 2026-07-30 — Wending 引擎 3 处修复（不只信报告，去看源码）

## TL;DR

用户给我一份"wending 引擎运维报告"，我没直接信。**对比源码 + 实际文件**，发现：
- 报告里 3 个具体实验名（physics-ordered / qubit-flow / energy-efficient）**全假**
- 报告里说的 `D:\wending\experiments\` **不存在**（`data\experiments\` 存在）
- 但报告里 1 个观察**真**：失败率高（`_build/results/*.json` 全 fitness 0%）
- 还发现报告**没提但更严重**的问题：**API token 在 7 个文件里硬编码**

实际修了 3 处（每处都先看源码确认再动手）：
1. 🔴 Token 泄露 → env var 读取
2. 🟡 pymupdf 缺失 → `pip install pymupdf pymupdf4llm`
3. 🟠 placeholder 无限循环 → 双层防护

---

## 1. 🔴 API token 硬编码（7 个文件）

**位置**：`D:\wending\_build\` 下所有调 API 的 `.py`：
```
experiment.py:25       API_KEY = "sk-cp-..."
code_reader.py:24
meta_agent.py:11
reader.py:13
self_modify.py:7
self_optimize.py:7
vision.py:6
```

**修复**：全部替换为
```python
API_KEY = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("MINIMAXI_API_KEY", "")
```
+ 自动加 `import os`（如果缺）

**没动**（用户没要求）：
- ❌ 没 rotate token（同一 key Claude Code 也在用，rotate 断会话）
- ❌ 没清 git 历史（旧 commit 仍泄露 token）

**待办**：用户自己决定何时 rotate + 是否清历史

---

## 2. 🟡 pymupdf 缺失

**症状**：`pip show pymupdf` → not found
**已装**：
```
Successfully installed pymupdf-1.28.0 pymupdf4llm-1.28.0 pymupdf_layout-1.28.0
```

**安装位置**：`C:\Users\87999\AppData\Local\Programs\Python\Python312\`

**注意**：报告里说"pymupdf 缺失"是真，但说"导致 X 实验失败"是误 —— wending 是 AI-Scientist 风格的 ML 研究自动化，不是量子实验。pymupdf 主要影响 PDF 论文解析（code_reader.py 用），不直接决定 fitness=0%。

---

## 3. 🟠 Placeholder 无限循环（**真根因**）

### 症状
所有实验 fitness=`(0.0%, 0.0%)`。看 `D:\wending\data\experiments\09b55de1f0aa\run_1.py`：

```python
# experiment.py
# Replace this with your actual experiment code

def main():
    print("Experiment placeholder — add your code here.")

if __name__ == "__main__":
    main()
```

LLM 一直在生成 placeholder，engine 还在执行它（print 不报错 → returncode 0），但没写 `final_info.json` → 实验彻底无效。

### 双层防护

**Layer 1 — 写入前检测**（新加 `_is_placeholder`）：
```python
_PLACEHOLDER_PATTERNS = [
    r"#\s*replace this with",
    r"experiment\s*placeholder",
    r"add your code here",
    r"placeholder.*add",
    r"todo:\s*implement",
    r"pass\s*$",
]

def _is_placeholder(code: str) -> bool:
    if not code or len(code.strip()) < 80: return True
    lower = code.lower()
    if sum(1 for p in _PLACEHOLDER_PATTERNS if re.search(p, lower)) >= 1: return True
    body_lines = [ln for ln in code.splitlines() 
                  if ln.strip() and not ln.strip().startswith(("#", "import ", "from "))]
    if len(body_lines) < 3: return True
    return False
```

检测到 → 不写入 + 喂回明确指令让 LLM 重生成。

**Layer 2 — 假成功检测**（改 `run_experiment()`）：
```python
if os.path.exists(info_path):
    return True, next_prompt
else:
    return False, "Run N exited 0 but did not produce final_info.json..."
```

### 验证（实测失败的 run 文件）
```
[PLACEHOLDER] 09b55de1f0aa/run_1.py: '# experiment.py'
[real]        09b55de1f0aa/run_2.py: 'import os'   ← 边缘 case
[PLACEHOLDER] 09b55de1f0aa/run_3.py: 'import subprocess'
[real]        09b55de1f0aa/run_4.py: '# experiment.py'  ← 边缘 case
[PLACEHOLDER] 09b55de1f0aa/run_5.py: 'bash'
```

3/5 正确拦下；2/5 边缘 case 在 Layer 2 也会被 final_info.json 检查兜住。

---

## 教训（写下来防再犯）

### 不要信报告
今天用户给的"wending 运维报告"**典型 LLM 编的运维报告**：
- 具体实验名是编的（grep 不到任何匹配）
- 路径写错（`experiments\` vs `data\experiments\`）
- 把 ML 研究自动化包装成"量子计算"
- **漏掉了真正严重的问题（API token 泄露）**

下次收到任何"报告"都先：
1. grep 关键名词看是不是真的存在
2. 读源头代码而不是信总结
3. 主动找**报告没提**的问题（往往比报告里的更严重）

### Wending 真实身份
- 中文名"问鼎"，v0.1.0
- 基于 SakanaAI/AI-Scientist fork
- `engine.py` 启动 fetcher / digester / trainer / loop 四件套
- `_build/` 是开发副本（不是 production），源码改动直接影响下次跑

### 路径速查
```
D:\wending\                   # 根
├── _build\                   # 实际代码（我改的）
│   ├── experiment.py         # 核心：LLM 生成实验代码 + 执行
│   ├── engine.py             # 主引擎
│   ├── code_reader.py        # 读论文（用 pymupdf）
│   ├── reader.py, vision.py  # PDF / 视觉解析
│   ├── self_modify.py, self_optimize.py  # 自我改进
│   └── results\              # 历史实验 JSON
├── wending\                  # Python package
│   ├── core, knowledge, research, scheduler, training
├── data\                     # 运行数据
│   ├── experiments\          # ★ 实验输出在这里（不是 experiments\）
│   ├── evokg.db              # 知识图谱
│   └── wending_data\
└── vendor\AI-Scientist\      # SakanaAI fork
```

### Token 现在怎么用
下次 wending 跑之前要 `export MINIMAXI_API_KEY=sk-cp-...`（或 `ANTHROPIC_API_KEY`），不然 `_call_api` 会拿空 key 调用然后报 401。
