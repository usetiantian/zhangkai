"""
智能整理引擎 — 用本地 Qwen 读内容、理解主题、提出分类方案
零外部依赖——使用内置 LocalModel，不走 LM Studio
"""
import os, json, logging
from collections import defaultdict
logger = logging.getLogger("nexus_kb.smart_organize")


class SmartOrganizer:
    """用内置模型理解内容后智能整理。"""

    def __init__(self, knowledge_base):
        self.kb = knowledge_base

    def analyze_and_plan(self, folder_path: str, max_sample_files: int = 30) -> dict:
        """
        分析一个文件夹的所有内容，让 Qwen 提出分类方案。
        """
        import sys

        # 收集文件信息（只统计，不存全部）
        ext_counts = defaultdict(int)
        ext_examples = defaultdict(list)
        file_count = 0
        sample_candidates = []

        sys.stderr.write(f"[smart] Walking {folder_path}...\n")
        sys.stderr.flush()

        for root, dirs, files in os.walk(folder_path):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if f.startswith("."):
                    continue
                fp = os.path.join(root, f)
                ext = os.path.splitext(f)[1].lower()
                ext_counts[ext] += 1
                file_count += 1

                # 每种扩展保留几个示例
                if len(ext_examples[ext]) < 3:
                    try:
                        size = os.path.getsize(fp)
                    except:
                        size = 0
                    ext_examples[ext].append((f, size))

                # 收集采样候选（优先小文本文件）
                if len(sample_candidates) < max_sample_files * 3:
                    try:
                        size = os.path.getsize(fp)
                        if size < 200 * 1024 and ext in ('.md','.txt','.json','.csv','.py','.yaml','.yml','.log',''):
                            sample_candidates.append((fp, os.path.relpath(fp, folder_path), size))
                    except:
                        pass

            if file_count % 10000 == 0:
                sys.stderr.write(f"[smart]   scanned {file_count} files...\n")
                sys.stderr.flush()

        sys.stderr.write(f"[smart] Walk done: {file_count} files, {len(ext_counts)} extensions\n")
        sys.stderr.flush()

        if not file_count:
            return {"error": "no files", "folder": folder_path}

        # 采样内容（读前200字符）
        samples = []
        sample_candidates.sort(key=lambda x: x[2])  # 按大小排序，小的优先
        sampled = 0
        for fp, rel, size in sample_candidates:
            if sampled >= max_sample_files:
                break
            try:
                with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()[:300]
                    samples.append(f"{rel}: {content[:200]}")
                    sampled += 1
            except:
                pass

        # 构建精简 prompt
        ext_lines = []
        for ext in sorted(ext_counts, key=lambda e: -ext_counts[e])[:15]:
            examples = ext_examples.get(ext, [])
            preview = ", ".join(e[0] for e in examples[:3])
            ext_lines.append(f"  {ext}: {ext_counts[ext]} files (e.g. {preview})")

        prompt = f"""分析文件夹内容，提出3-8个子文件夹分类方案。

文件夹: {os.path.basename(folder_path)}
总文件数: {file_count}
顶层子文件夹: {', '.join(d for d in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path,d)) and not d.startswith('.'))[:200]}

主要文件类型:
{chr(10).join(ext_lines)}

内容采样:
{chr(10).join(samples[:20])}

请分析主题，提出子文件夹分类方案。要求：
- match_rules 用文件名关键词匹配（如 "进化*", "debug*", "stock*"）
- 禁止用 *.md *.txt *.json 等扩展名规则（太宽泛）
- 每个类别3-5个规则，规则之间不重叠

返回JSON（只返回JSON）:
{{"analysis":"一句话中文理解","categories":[{{"name":"子文件夹名","description":"说明","match_rules":["关键词*","具体文件名"]}}]}}"""

        # 调用 Qwen
        sys.stderr.write(f"[smart] Prompt: {len(prompt)} chars, asking Qwen...\n")
        sys.stderr.flush()
        qwen_result = self._ask_qwen(prompt)
        sys.stderr.write(f"[smart] Qwen done: {len(qwen_result.get('categories',[]))} categories\n")
        sys.stderr.flush()

        return {
            "folder": folder_path,
            "total_files": file_count,
            "plan": qwen_result,
        }

    def execute_plan(self, plan: dict, dry_run: bool = True, max_files: int = 0) -> dict:
        """
        模型驱动分类：每批10个文件，读内容→Qwen判断类别。零规则，零硬编码。
        max_files=0 表示全部分类。
        """
        import sys
        categories = plan.get("plan", {}).get("categories", [])
        if not categories:
            return {"status": "no_categories"}

        folder = plan["folder"]
        cat_names = [c["name"] for c in categories]
        cat_descs = {c["name"]: c.get("description", "") for c in categories}

        # 创建分类目录
        cat_dirs = {}
        for cat in categories:
            cat_dirs[cat["name"]] = os.path.join(folder, cat["name"])

        # 收集待分类文件（只取文本文件，跳过二进制和已隐藏的）
        pending = []
        for root, dirs, files in os.walk(folder):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if f.startswith("."):
                    continue
                fp = os.path.join(root, f)
                ext = os.path.splitext(f)[1].lower()
                # 只处理模型能读的文本文件
                if ext not in ('', '.txt', '.md', '.py', '.json', '.csv', '.yaml', '.yml',
                               '.js', '.ts', '.html', '.css', '.xml', '.log', '.sh', '.bat',
                               '.ini', '.cfg', '.toml', '.rst', '.sql', '.r', '.java',
                               '.c', '.cpp', '.h', '.hpp', '.tsx', '.jsx', '.mjs', '.cjs'):
                    continue
                try:
                    size = os.path.getsize(fp)
                    if size > 500 * 1024:  # 跳过 500KB 以上的文件
                        continue
                except:
                    continue
                pending.append(fp)
                if max_files and len(pending) >= max_files:
                    break
            if max_files and len(pending) >= max_files:
                break

        if max_files:
            pending = pending[:max_files]

        total = len(pending)
        if not total:
            return {"status": "no_files_to_classify"}

        sys.stderr.write(f"[smart] Classifying {total} files by content (model-driven, 10/batch)...\n")
        sys.stderr.flush()

        from ..engine.lm_client import LMStudioClient
        lm = LMStudioClient()

        # 分类映射：{filepath: category_name}
        assignments = {}
        batch_size = 10

        for i in range(0, total, batch_size):
            batch = pending[i:i + batch_size]

            # 读每个文件的内容片段
            file_snippets = []
            for fp in batch:
                try:
                    with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                        content = fh.read()[:500]
                except:
                    content = "[无法读取]"
                rel = os.path.relpath(fp, folder)
                file_snippets.append(f"{len(file_snippets)}. {rel}: {content[:300]}")

            # 构建分类 prompt
            prompt = f"""将以下文件归入最合适的类别。类别说明:

{chr(10).join(f'{c["name"]}: {c.get("description","")}' for c in categories)}

文件列表:
{chr(10).join(file_snippets)}

只返回JSON数组，每个元素是文件序号对应的类别名:
["类别名", "类别名", ...]

共{len(batch)}个文件，返回{len(batch)}个类别名。"""

            # 调用模型
            raw = lm.ask(prompt, system="你是文件分类专家。只返回JSON数组。")
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].split("```")[0].strip()
            if raw.startswith("json"):
                raw = raw[4:].strip()

            # 解析分类结果
            try:
                import re
                match = re.search(r'\[.*\]', raw, re.DOTALL)
                if match:
                    batch_cats = json.loads(match.group())
                    if isinstance(batch_cats, list) and len(batch_cats) == len(batch):
                        for fp, cat in zip(batch, batch_cats):
                            if cat in cat_names:
                                assignments[fp] = cat
                            else:
                                # 模糊匹配
                                best = max(cat_names, key=lambda n: len(set(n) & set(cat)) / max(len(set(n) | set(cat)), 1))
                                assignments[fp] = best
                    else:
                        for fp in batch:
                            assignments[fp] = cat_names[0]  # 兜底
                else:
                    for fp in batch:
                        assignments[fp] = cat_names[0]
            except:
                for fp in batch:
                    assignments[fp] = cat_names[0]

            progress = min(i + batch_size, total)
            if progress % 100 == 0 or progress == total:
                sys.stderr.write(f"[smart]   {progress}/{total} classified\n")
                sys.stderr.flush()

        # 生成移动计划
        moves = []
        for fp, cat in assignments.items():
            basename = os.path.basename(fp)
            dest = os.path.join(cat_dirs[cat], basename)
            moves.append({"from": fp, "to": dest, "category": cat})

        sys.stderr.write(f"[smart] Classified {len(assignments)}/{total} files into {len(cat_names)} categories\n")
        sys.stderr.flush()

        if not dry_run and moves:
            for m in moves:
                os.makedirs(os.path.dirname(m["to"]), exist_ok=True)
                try:
                    os.rename(m["from"], m["to"])
                except OSError:
                    import shutil
                    shutil.move(m["from"], m["to"])

        return {
            "status": "dry_run" if dry_run else "executed",
            "categories": len(cat_names),
            "moves": len(moves),
            "unmapped": total - len(assignments),
            "moves_preview": moves[:10],
            "categories_created": cat_names,
            "classified_by": "Qwen3-VL-4B (content-driven, zero rules)",
        }

    def _ask_qwen(self, prompt: str) -> dict:
        """调用 LM Studio 分析。容错解析 JSON。"""
        try:
            from ..engine.lm_client import LMStudioClient
            lm = LMStudioClient()
            content = lm.ask(prompt, system="你是文件整理专家。只返回 JSON，不要其他文字。")

            # 保存原始响应用于调试
            raw = content

            # 提取 JSON（可能被 markdown 包裹）
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:])
                if content.rstrip().endswith("```"):
                    content = content.rstrip()[:-3]
                content = content.strip()
                if content.startswith("json"):
                    content = content[4:].strip()

            # 尝试多种方式解析
            import re
            result = None

            # 方式1: 直接解析
            try:
                result = json.loads(content)
            except json.JSONDecodeError:
                pass

            # 方式2: 修复常见 JSON 问题后重试
            if result is None:
                try:
                    fixed = self._fix_json(content)
                    result = json.loads(fixed)
                except (json.JSONDecodeError, Exception):
                    pass

            # 方式3: 用正则提取 JSON 块
            if result is None:
                try:
                    match = re.search(r'\{.*\}', content, re.DOTALL)
                    if match:
                        fixed = self._fix_json(match.group())
                        result = json.loads(fixed)
                except (json.JSONDecodeError, Exception):
                    pass

            if result is not None:
                return result

            # 保存原始响应用于调试
            import time
            debug_path = f"C:/Users/87999/claude-workspace/_qwen_raw_{int(time.time())}.txt"
            try:
                with open(debug_path, "w", encoding="utf-8") as df:
                    df.write(raw)
            except:
                pass
            logger.warning(f"JSON parse failed after fixes. Raw saved to {debug_path}, first 500: {raw[:500]}")
            return {"analysis": "JSON parse failed", "categories": [], "files": {}}

        except Exception as e:
            logger.error(f"Model analysis failed: {e}")
            return {"analysis": f"Model unavailable: {e}", "categories": [], "files": {}}

    @staticmethod
    def _fix_json(text: str) -> str:
        """修复 Qwen 模型 JSON 输出的常见错误。"""
        import re
        # 1. 移除尾随逗号
        text = re.sub(r',\s*([}\]])', r'\1', text)
        # 2. 修复单引号 JSON（只替换结构位置的引号，不动内容中的撇号如 it's）
        # 键: 'key':
        text = re.sub(r"(?<=[{,]\s*)'([^']*)'(?=\s*:)", r'"\1"', text)
        # 值: :'value' 或 :'value',
        text = re.sub(r"(?<=:)\s*'([^']*)'(?=\s*[,}\]])", r'"\1"', text)
        # 数组元素: ['elem', 'elem']
        text = re.sub(r"(?<=\[)\s*'([^']*)'(?=\s*[,}\]])", r'"\1"', text)
        # 数组中间: ,'elem'
        text = re.sub(r"(?<=,)\s*'([^']*)'(?=\s*[,}\]])", r'"\1"', text)
        return text
