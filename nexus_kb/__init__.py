"""
Nexus KnowledgeBase — 活的知识库，不是死的文件夹索引

会自己看、自己想、自己整理。模型推理走 LM Studio HTTP API，不内置。

内核 = GraphEngine + RAGEngine + CommunityDetector + Orchestrator + Heartbeat + LMStudioClient
"""

import os, json, hashlib, time, logging

from .engine.graph import GraphEngine
from .engine.rag import RAGEngine
from .engine.community import CommunityDetector
from .engine.orchestrator import PlanExecuteReportOrchestrator
from .engine.self import KBSelf
from .engine.lm_client import LMStudioClient
from .ingest.parser import parse

logger = logging.getLogger("nexus_kb")


class KnowledgeBase:
    """湖库一体的知识库——丢文件进去 = 可搜索。"""

    def __init__(self, data_dir: str = None):
        self.data_dir = os.path.expanduser(data_dir or os.path.join(os.path.expanduser("~"), "nexus_library"))
        self.index_dir = os.path.join(self.data_dir, ".nexus")
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.index_dir, exist_ok=True)

        # 四件套 + LM 客户端
        self._lm = LMStudioClient()
        self.graph = GraphEngine()
        self.rag = RAGEngine()
        self.rag.set_lm(self._lm)  # 注入 LM 客户端用于语义向量
        self.community = CommunityDetector()
        self.orchestrator = PlanExecuteReportOrchestrator()
        self.self = KBSelf(self)  # 自我意识

        # 处理记录
        self._ingested = {}       # {filepath: sha256}
        self._load_state()

    # ========================================
    # 摄入
    # ========================================

    def ingest_text(self, text: str, source: str, owner: str = "default"):
        """摄入纯文本。source 可以是文件名或任意标识。"""
        self.rag.ingest_document(text, source)
        self.graph.add_entity(source, source, "document", owner=owner, size=len(text), ingested_at=time.time())
        self.graph.add_relation(owner, source, "owns")
        stats = self.graph.stats()
        logger.info(f"Ingested: {source} ({len(text)} chars) → graph: {stats['nodes']} nodes, {stats['edges']} edges")

    def ingest_file(self, filepath: str) -> dict:
        """摄入单个文件。自动检测格式。已处理过且未变化则跳过。"""
        if not os.path.isfile(filepath):
            return {"error": f"Not a file: {filepath}"}

        # 路径归一化（Windows 反斜杠 → 正斜杠，避免同一文件存两个 key）
        filepath = os.path.normpath(filepath).replace(os.sep, "/")

        h = self._hash_file(filepath)
        if filepath in self._ingested and self._ingested[filepath] == h:
            return {"status": "skipped", "reason": "unchanged", "file": filepath}

        text = self._parse_file(filepath)
        if not text:
            return {"error": f"Empty or unparseable: {filepath}"}

        self.ingest_text(text, filepath)
        self._ingested[filepath] = h
        self._save_state()
        return {"status": "ok", "file": filepath, "chars": len(text), "graph": self.graph.stats()}

    def ingest_directory(self, dirpath: str) -> list:
        """递归摄入整个目录。"""
        results = []
        for root, _, files in os.walk(dirpath):
            for f in files:
                fp = os.path.join(root, f)
                if fp.endswith(('.pyc', '.nexus')):   # 跳过索引文件
                    continue
                try:
                    r = self.ingest_file(fp)
                    results.append(r)
                except Exception as e:
                    results.append({"file": fp, "error": str(e)})
        return results

    # ========================================
    # 删除（红线：永不自主删文件）
    # ========================================

    def remove(self, filepath: str):
        """从索引中移除（文件本身不动）。"""
        filepath = os.path.normpath(filepath).replace(os.sep, "/")
        if filepath in self.graph.nodes:
            self.graph.remove_entity(filepath)
        self.rag.remove(filepath)
        self._ingested.pop(filepath, None)
        self._save_state()

    def suggest_delete(self, filepath: str, reason: str) -> dict:
        """
        A0.2: 把文件移到 待删除/ 并写原因。永久由用户决定。
        这是知识库唯一可以"动"文件的方式——不是真删，是标记。
        """
        trash_dir = os.path.join(self.data_dir, "待删除")
        os.makedirs(trash_dir, exist_ok=True)

        basename = os.path.basename(filepath)
        dst_file = os.path.join(trash_dir, basename)
        reason_file = os.path.join(trash_dir, f"{basename}.删除原因.md")

        # 写原因
        with open(reason_file, "w", encoding="utf-8") as f:
            f.write(f"# 建议删除: {basename}\n\n"
                    f"原路径: {filepath}\n"
                    f"原因: {reason}\n"
                    f"时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    f"要恢复: 把文件移回原位置即可。\n"
                    f"要彻底删除: 删除本目录下的文件。\n")

        # 移到待删除
        import shutil
        shutil.move(filepath, dst_file)

        # 从索引清除
        self.remove(filepath)
        return {"status": "moved_to_trash", "from": filepath, "to": dst_file, "reason": reason_file}

    # ========================================
    # 搜索
    # ========================================

    def search(self, query: str, top_k: int = 10) -> list:
        return self.rag.search(query, top_k)

    def reembed(self) -> dict:
        """用 LM Studio 的 Qwen 重新生成所有向量。搜索从 BOW 升级到语义理解。"""
        if not self._lm.is_available():
            return {"error": "LM Studio 不在线"}
        # 逐 chunk 走 LM Studio embedding API
        for i, ci in enumerate(self.rag._chunk_map):
            di = int(ci)
            if di < len(self.rag._docs):
                v = self._lm.embed(self.rag._docs[di]["text"][:1000])
                if v:
                    self.rag._vectors[i] = v
        self.save()
        return self.rag.stats()

    def ask(self, question: str) -> str:
        """搜索 + LM Studio 总结 → 直接回答。"""
        docs = self.search(question)
        if not docs:
            return "知识库里没找到相关内容。"

        context = "\n\n".join(
            f"[{d['source']}]\n{d['text']}" for d in docs
        )

        prompt = f"""根据以下知识库内容回答问题。信息不足就诚实说明。

知识库内容:
{context[:6000]}

问题: {question}"""

        return self._lm.ask(prompt, system="你是知识库问答系统。")

    # ========================================
    # 图谱
    # ========================================

    def graph_neighbors(self, node_id: str) -> list:
        return self.graph.get_neighbors(node_id)

    def graph_search(self, keyword: str) -> list:
        return self.graph.search(keyword)

    def detect_communities(self) -> dict:
        return self.community.detect(self.graph.nodes, self.graph.edges)

    # ========================================
    # LoRA 微调（Phase 5）
    # ========================================

    def train(self, user_id: str = "default", force: bool = False) -> dict:
        """触发 LoRA 微调。force=True 跳过阈值检查。训练数据从知识库内容提取。"""
        from .learn.trigger import TrainingTrigger
        trigger = TrainingTrigger(self, model_path=None)
        if not force and not trigger.should_train():
            return {"status": "skipped", "reason": "below threshold", "status_detail": trigger.status()}
        return trigger.train(user_id)

    def training_status(self) -> dict:
        """查看微调状态：距上次训练新增多少文档、是否该训练了。"""
        from .learn.trigger import TrainingTrigger
        return TrainingTrigger(self).status()

    # ========================================
    # 网络搜索（Phase 6）
    # ========================================

    def web_search(self, query: str, max_results: int = 5) -> list:
        """搜索网络，返回结果列表。"""
        from .learn.web import WebSearcher
        return WebSearcher().search(query, max_results)

    def web_search_and_ingest(self, query: str, max_results: int = 3) -> dict:
        """搜索网络 → 抓取内容 → 摄入知识库。"""
        from .learn.web import WebKnowledgeBridge
        bridge = WebKnowledgeBridge(self)
        return bridge.search_and_ingest(query, max_results)

    def web_fetch(self, url: str) -> dict:
        """抓取单个网页的纯文本内容。"""
        from .learn.web import WebCrawler
        return WebCrawler().fetch(url)

    def analyze_organization(self) -> dict:
        """
        分析知识库文件整理问题：完全重复、同名文件、相似文件夹、内容接近重复、社区聚类。
        """
        from .ingest.organize import FileOrganizer
        return FileOrganizer(self).summary()

    def find_duplicates(self) -> list:
        """查找 SHA256 完全重复的文件（同一文件多处存在）。"""
        from .ingest.organize import FileOrganizer
        return FileOrganizer(self).find_exact_duplicates()

    def auto_organize(self, dry_run: bool = True) -> dict:
        """
        自动整理知识库——分析内容聚类，建议合并方案。
        dry_run=True 只预览，dry_run=False 执行移动。
        """
        from .ingest.organize import AutoOrganizer
        org = AutoOrganizer(self)
        analysis = org.analyze()
        merge_plan = org.execute_merge(dry_run=dry_run)
        return {**analysis, "merge_plan": merge_plan}

    def sort_file(self, filepath: str) -> str:
        """模型读文件内容 → 自己判断放哪。"""
        top_dirs = [d for d in os.listdir(self.data_dir)
                    if os.path.isdir(os.path.join(self.data_dir, d)) and not d.startswith(".")]

        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
        except:
            return "未分类"

        preview = content[:3000]
        note = f"\n(文件共{len(content)}字符，以上是前3000字符)" if len(content) > 3000 else ""

        prompt = f"""知识库已有目录: {', '.join(top_dirs)}
文件内容:
{preview}{note}
这个文件应该放在哪个目录？只返回目录名。"""

        result = self._lm.ask(prompt, system="你是文件分类专家。只返回目录名。")
        return result.strip().split("\n")[0].strip() or "未分类"

    # ========================================
    # 自动摄入（Phase 3: 数据湖 + 监听）
    # ========================================

    def rescan(self) -> list:
        """重新扫描整个数据湖目录，摄入所有新文件和变化的文件。"""
        results = []
        for root, dirs, files in os.walk(self.data_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if f.startswith("."):
                    continue
                fp = os.path.normpath(os.path.join(root, f)).replace(os.sep, "/")
                try:
                    r = self.ingest_file(fp)
                    results.append(r)
                except Exception as e:
                    results.append({"file": fp, "error": str(e)})
        self._save_state()
        return results

    def watch(self, interval: float = 5.0):
        """返回一个 FileWatcher，可调用 watcher.run_once() 做单次扫描。"""
        from .ingest.watcher import FileWatcher
        w = FileWatcher(self, interval)
        w.start()
        return w

    # ========================================
    # 状态
    # ========================================

    def status(self) -> dict:
        s = {
            "graph": self.graph.stats(),
            "rag": self.rag.stats(),
            "ingested_files": len(self._ingested),
            "data_dir": self.data_dir,
            "index_dir": self.index_dir,
            "lm_studio": self._lm.is_available(),
        }
        # 显存监控（仅信息，不做门槛）
        try:
            from .engine.local_model import check_vram, check_ram
            s["vram"] = check_vram()
            s["ram"] = check_ram()
        except:
            pass
        return s

    def vram_status(self) -> dict:
        """显存/内存监控。模型走 LM Studio 不占用 KB 进程显存。"""
        try:
            from .engine.local_model import check_vram, check_ram
        except:
            return {"error": "无法检查显存"}
        vram = check_vram()
        ram = check_ram()
        return {
            "lm_studio_online": self._lm.is_available(),
            "vram": vram,
            "ram": ram,
        }

    # ========================================
    # 自主上网 — 凌晨自己搜论文、找资料
    # ========================================

    def search_and_learn(self, topics: list[str] = None) -> dict:
        """
        搜索网络 + 爬取内容 + 摄入知识库 + 写学习笔记。
        topics 不指定则自动从知识库中找出值得深入的主题。
        """
        if topics is None:
            topics = self._suggest_topics()

        from .learn.web import WebSearcher, WebCrawler
        searcher = WebSearcher()
        crawler = WebCrawler()

        learned = []
        for topic in topics[:3]:
            results = searcher.search(topic, max_results=3)
            if not results:
                continue

            for r in results[:2]:
                content = crawler.fetch(r["url"])
                if content.get("error"):
                    continue
                text = f"# {content['title']}\n来源: {content['url']}\n\n{content['text']}"
                source = f"web:{topic}:{content['title'][:40]}"
                self.ingest_text(text, source)
                learned.append({"topic": topic, "title": content["title"]})

        if learned:
            learn_dir = os.path.join(self.data_dir, "学习笔记")
            os.makedirs(learn_dir, exist_ok=True)
            note_path = os.path.join(learn_dir, f"学习_{time.strftime('%Y%m%d_%H%M')}.md")
            with open(note_path, "w", encoding="utf-8") as f:
                f.write(f"# 自动学习笔记\n\n> {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                for l in learned:
                    f.write(f"- [{l['topic']}] {l['title']}\n")

        return {"searched": len(topics), "learned": len(learned), "topics": topics}

    def _suggest_topics(self) -> list[str]:
        """从知识库中找出值得深入学习的主题。"""
        top_dirs = [d for d in os.listdir(self.data_dir)
                    if os.path.isdir(os.path.join(self.data_dir, d)) and not d.startswith(".")][:10]

        prompt = f"""这个知识库有这些领域: {', '.join(top_dirs)}
知识库目前有 {len(self._ingested)} 个文件。
请提出 3 个值得上网搜索学习的主题。每个主题一句话，用新行分隔。"""

        result = self._lm.ask(prompt, system="你是知识管理专家。推荐值得学习的主题。")
        topics = [t.strip().lstrip("0123456789.-• ").strip() for t in result.split("\n") if t.strip()]
        return topics[:3] or ["AI knowledge base latest research"]

    # ========================================
    # 跨域生成 — 活了就会自己写东西
    # ========================================

    def generate_wiki(self, target: str = None) -> dict:
        """读出知识库内容后，自动生成 wiki 页面。"""

        wiki_dir = os.path.join(self.data_dir, ".nexus", "wiki")
        os.makedirs(wiki_dir, exist_ok=True)

        generated = []

        if target is None:
            top_dirs = [d for d in os.listdir(self.data_dir)
                        if os.path.isdir(os.path.join(self.data_dir, d)) and not d.startswith(".")][:20]
            stats = self.graph.stats()

            prompt = f"""你是知识库的自省系统。分析这个知识库并生成概览:

知识库: {os.path.basename(self.data_dir)}
文件数: {len(self._ingested)}
图谱: {stats['nodes']} 节点, {stats['edges']} 边
顶层目录: {', '.join(top_dirs)}

请用 Markdown 写一份知识库概览，包含:
# 知识库概览
## 包含哪些领域
## 文件分布
## 知识关联
## 待扩展方向
## 推荐阅读路径"""

            overview = self._lm.ask(prompt, system="你是知识库分析师。写一份专业的Markdown概览。")
            path = os.path.join(wiki_dir, "概览.md")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# {os.path.basename(self.data_dir)} 知识库概览\n\n")
                f.write(f"> 自动生成于 {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(overview)
            generated.append({"type": "overview", "path": path})

        else:
            if os.path.isdir(target):
                files = [os.path.join(target, f) for f in os.listdir(target)
                         if os.path.isfile(os.path.join(target, f)) and not f.startswith(".")][:10]
                samples = []
                for fp in files[:5]:
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                            samples.append(f"{os.path.basename(fp)}: {fh.read()[:300]}")
                    except:
                        pass

                prompt = f"""分析目录内容并生成 wiki 页面:

目录: {os.path.basename(target)}
内容采样:
{chr(10).join(samples)}

请用 Markdown 写一份分析，包含:
# {os.path.basename(target)}
## 主题
## 关键文件
## 核心概念
## 与其他知识的关联"""

                page = self._lm.ask(prompt, system="你是知识库分析师。写一份Markdown分析。")
                path = os.path.join(wiki_dir, f"{os.path.basename(target)}.md")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"# {os.path.basename(target)}\n\n")
                    f.write(f"> 自动生成于 {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write(page)
                generated.append({"type": "topic", "path": path, "target": target})

        return {"generated": len(generated), "pages": generated, "wiki_dir": wiki_dir}

    def generate_insights(self, max_docs: int = 5000) -> dict:
        """
        图上跑社区检测 → 发现跨域关联 → 模型分析 → 写洞察文档。
        这是真正的"跨域生成文件"——基于图谱事实，不是 LLM 瞎编。

        max_docs: 超过此数量自动降采样，防止 O(n²) 爆内存。
        """
        import sys, math
        sys.stderr.write("[insight] Building content graph...\n")
        sys.stderr.flush()

        docs = self.rag._docs  # [{text, source, chunks}]
        if len(docs) < 10:
            return {"status": "not_enough_data", "message": f"需要至少 10 个文档，当前 {len(docs)}"}

        # 显存保护：估算向量矩阵大小
        n_total = min(len(self.rag._chunk_map), len(self.rag._vectors))
        if n_total > 0 and self.rag._vectors[0]:
            vec_dim = len(self.rag._vectors[0])
            vec_mem_mb = n_total * vec_dim * 4 / (1024 * 1024)  # float32 = 4 bytes
            sys.stderr.write(f"[insight] {n_total} vectors × {vec_dim}d = {vec_mem_mb:.0f}MB\n")
            sys.stderr.flush()

        # 自适应采样：文档越多，采样率越低（保证 O(anchors × candidates) 可控）
        if len(docs) > max_docs:
            oversample_msg = f"[insight] {len(docs)} docs > {max_docs} limit, aggressive sampling"
            sys.stderr.write(oversample_msg + "\n")
            sys.stderr.flush()

        # 自适应参数：doc 越多 → anchors 和 candidates 越少
        log_factor = max(1, int(math.log2(max(len(docs), 2))))
        n_anchors = max(50, min(1000, 50000 // log_factor))
        n_candidates = max(50, min(2000, 100000 // log_factor))

        from collections import defaultdict
        import random
        groups = defaultdict(set)
        seen_pairs = set()

        anchors = random.sample(range(n_total), min(n_anchors, n_total))

        for idx_i, i in enumerate(anchors):
            if not self.rag._vectors[i]: continue
            vi = self.rag._vectors[i]
            di = int(self.rag._chunk_map[i])
            best = []
            candidates = random.sample(range(n_total), min(n_candidates, n_total))
            for j in candidates:
                if j == i or not self.rag._vectors[j]: continue
                dj = int(self.rag._chunk_map[j])
                score = sum(x * y for x, y in zip(vi, self.rag._vectors[j]))
                best.append((score, di, dj))
            best.sort(reverse=True)
            # 取所有正相似度的（模型嵌入会有负值，BOW全是正的）
            for score, a, b in best:
                if score <= 0: break
                if (a, b) not in seen_pairs and a < len(docs) and b < len(docs):
                    if docs[a]["source"] != docs[b]["source"]:
                        seen_pairs.add((a, b))
                        groups[a].add(b)

            if (idx_i + 1) % 100 == 0:
                sys.stderr.write(f"[insight]   anchor {idx_i+1}/{len(anchors)}\n")
                sys.stderr.flush()

        # 2. 找跨域组：同一个组里文件来自不同顶层目录
        top_dirs = {d for d in os.listdir(self.data_dir)
                    if os.path.isdir(os.path.join(self.data_dir, d)) and not d.startswith(".")}

        cross_domain = []
        for group in groups.values():
            if len(group) < 2:
                continue
            sources = {docs[di]["source"] for di in group if di < len(docs)}
            dirs = set()
            for s in sources:
                rel = os.path.relpath(s, self.data_dir)
                top = rel.split(os.sep)[0]
                if top in top_dirs:
                    dirs.add(top)
            if len(dirs) >= 2:
                cross_domain.append({
                    "domains": list(dirs),
                    "files": list(sources),
                    "size": len(group),
                })

        if not cross_domain:
            return {"status": "no_cross_domain_found"}

        cross_domain.sort(key=lambda x: -x["size"])
        sys.stderr.write(f"[insight] Found {len(cross_domain)} cross-domain clusters\n")
        sys.stderr.flush()

        insight_dir = os.path.join(self.data_dir, "知识发现")
        os.makedirs(insight_dir, exist_ok=True)
        generated = []

        # 批量分析：每 20 个集群一组，减少调用次数且能发现跨集群元模式
        batch_size = 20
        for batch_start in range(0, len(cross_domain), batch_size):
            batch = cross_domain[batch_start:batch_start + batch_size]
            batch_descs = []
            for idx, cd in enumerate(batch):
                samples = []
                for fp in cd["files"][:3]:  # 每个集群取样 3 个文件
                    try:
                        with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                            content = fh.read()[:1000]
                        samples.append(f"{os.path.basename(fp)}: {content[:500]}")
                    except:
                        pass
                batch_descs.append(
                    f"集群{idx+1}: 领域={' & '.join(cd['domains'])}, "
                    f"文件数={cd['size']}, 采样:\n" + "\n".join(samples[:3])
                )

            prompt = f"""分析 {len(batch)} 个跨领域知识集群:

{chr(10).join(batch_descs)}

为每个集群写一段洞察(Markdown): 为什么关联？发现了什么？编号对应。"""

            report = self._lm.ask(prompt, system="你是跨领域知识发现专家。批量分析。")
            filename = f"跨域发现_{batch_start+1}-{batch_start+len(batch)}_{int(time.time())}.md"
            path = os.path.join(insight_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"# 跨领域发现 (集群 {batch_start+1}-{batch_start+len(batch)})\n\n")
                f.write(f"> 自动发现于 {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"> 分析 {len(batch)} 个集群\n\n")
                f.write(report)
            generated.append({"path": path, "count": len(batch)})

            sys.stderr.write(f"[insight] batch {batch_start+1}-{batch_start+len(batch)}/{len(cross_domain)}\n")
            sys.stderr.flush()

        # 更新知识图谱：加 related_to 边
        for cd in cross_domain:
            files = cd["files"]
            for i, f1 in enumerate(files):
                for f2 in files[i + 1:]:
                    f1_norm = os.path.normpath(f1).replace(os.sep, "/")
                    f2_norm = os.path.normpath(f2).replace(os.sep, "/")
                    self.graph.add_relation(f1_norm, f2_norm, "related_to")

        self.save()
        return {
            "cross_domain_clusters": len(cross_domain),
            "insights_generated": len(generated),
            "insights_dir": insight_dir,
            "generated": generated,
        }

    # ========================================
    # 心跳 — 活的知识库
    # ========================================

    def live(self):
        """活着的核心循环。感知→决策→执行→记录。"""
        return self.self.live()

    def heartbeat(self) -> dict:
        """
        活的知识库心跳。每次调用做四件事：
        1. 观察变化
        2. 检查定时任务（凌晨2-6点自动搜论文/下载资料）
        3. 检查是否该整理
        4. 检查是否该生成wiki
        """
        obs_path = os.path.join(self.index_dir, "observations.json")
        observations = self._load_observations(obs_path)

        now = time.time()
        new_obs = []

        # 观察1: 新文件数量
        prev_count = observations.get("last_file_count", 0)
        current_count = len(self._ingested)
        if current_count != prev_count:
            delta = current_count - prev_count
            new_obs.append({
                "time": now,
                "type": "growth",
                "message": f"文件从 {prev_count} 增长到 {current_count} ({delta:+d})",
                "delta": delta,
            })

        # 观察2: 图状态
        stats = self.graph.stats()
        prev_nodes = observations.get("last_node_count", 0)
        if stats["nodes"] != prev_nodes:
            new_obs.append({
                "time": now,
                "type": "graph_change",
                "message": f"图谱: {stats['nodes']} 节点, {stats['edges']} 边",
                "stats": stats,
            })

        # 观察3: 是否存在孤岛节点（没有边的节点）
        if stats["nodes"] > 0 and stats["edges"] == 0:
            new_obs.append({
                "time": now,
                "type": "warning",
                "message": "图谱完全断开——可能索引损坏，需要 rebuild",
                "severity": "high",
            })

        # 凌晨2-6点: 搜索任务
        now_local = time.localtime()
        if 2 <= now_local.tm_hour <= 6:
            last_search = observations.get("last_search_batch", 0)
            hours_since_search = (now - last_search) / 3600
            if hours_since_search > 24:
                new_obs.append({
                    "time": now,
                    "type": "cron_trigger",
                    "message": "凌晨搜索窗口，建议运行 search_and_learn()",
                })

        # 反思: 是否该整理了？
        last_organized = observations.get("last_organized", 0)
        hours_since = (now - last_organized) / 3600
        should_organize = hours_since > 72 and current_count > 100

        if should_organize:
            new_obs.append({
                "time": now,
                "type": "suggestion",
                "message": f"距上次整理已 {hours_since:.0f} 小时，建议运行 auto_organize()",
            })

        # 反思: 是否该生成 wiki？
        last_wiki = observations.get("last_wiki", 0)
        hours_since_wiki = (now - last_wiki) / 3600
        if hours_since_wiki > 168:  # 7 天
            new_obs.append({
                "time": now,
                "type": "suggestion",
                "message": f"距上次 wiki 生成已 {hours_since_wiki:.0f} 小时，建议运行 generate_wiki()",
            })

        # 保存
        if new_obs:
            observations.setdefault("history", []).extend(new_obs)
            if len(observations["history"]) > 100:
                observations["history"] = observations["history"][-100:]

        observations["last_file_count"] = current_count
        observations["last_node_count"] = stats["nodes"]
        observations["last_heartbeat"] = now

        self._save_observations(obs_path, observations)

        return {
            "alive": True,
            "observations": new_obs,
            "total_files": current_count,
            "graph": stats,
            "should_organize": should_organize,
            "hours_since_organize": round(hours_since, 1),
        }

    def reflect(self) -> dict:
        """深度反思——让 LM Studio 分析当前知识库状态。"""
        stats = self.graph.stats()
        rag_stats = self.rag.stats()
        top_dirs = [d for d in os.listdir(self.data_dir)
                    if os.path.isdir(os.path.join(self.data_dir, d)) and not d.startswith(".")]

        try:
            prompt = f"""你是知识库的自我反思系统。分析当前状态:

知识库: {os.path.basename(self.data_dir)}
文件数: {len(self._ingested)}
图谱: {stats['nodes']} 节点, {stats['edges']} 边
RAG: {rag_stats['docs']} 文档, {rag_stats['chunks']} 块
顶层目录: {', '.join(top_dirs[:20])}

请用中文回答:
1. 这个知识库健康吗？有什么问题？
2. 下一步应该做什么？
3. 有什么有趣的发现？
简洁，每点一句话。"""
            insight = self._lm.ask(prompt, system="你是知识库自省系统。简洁分析，给可行建议。")
        except:
            insight = "LM Studio 不可用，跳过反思"

        return {
            "insight": insight,
            "stats": {"files": len(self._ingested), **stats, "rag": rag_stats},
        }

    def _load_observations(self, path: str) -> dict:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except:
            pass
        return {"history": [], "last_file_count": 0, "last_node_count": 0, "last_organized": 0}

    def _save_observations(self, path: str, data: dict):
        try:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except:
            pass

    # ========================================
    # 持久化
    # ========================================

    def _load_state(self):
        state_path = os.path.join(self.index_dir, "state.json")
        if os.path.exists(state_path):
            with open(state_path, "r") as f:
                d = json.load(f)
            self._ingested = d.get("ingested", {})

        graph_path = os.path.join(self.index_dir, "graph.json")
        if os.path.exists(graph_path):
            try:
                self.graph = GraphEngine.load(graph_path)
            except Exception as e:
                logger.warning(f"Graph load failed: {e}, starting fresh")

        rag_dir = os.path.join(self.index_dir, "vectors")
        if os.path.exists(rag_dir):
            try:
                self.rag.load(rag_dir)
            except Exception as e:
                logger.warning(f"RAG load failed: {e}, starting fresh")

    def _save_state(self):
        state_path = os.path.join(self.index_dir, "state.json")
        with open(state_path, "w") as f:
            json.dump({"ingested": self._ingested, "updated": time.time()}, f, ensure_ascii=False)

        graph_path = os.path.join(self.index_dir, "graph.json")
        self.graph.save(graph_path)

        rag_dir = os.path.join(self.index_dir, "vectors")
        self.rag.save(rag_dir)

    def save(self):
        self._save_state()
        logger.info(f"KnowledgeBase saved: {self.graph.stats()['nodes']} nodes, {self.graph.stats()['edges']} edges")

    # ========================================
    # 文件解析
    # ========================================

    def _hash_file(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()

    def _parse_file(self, filepath: str) -> str:
        """解析文件为纯文本。委托给 ingest/parser.py。"""
        result = parse(filepath)
        if result.get("error"):
            logger.warning(f"Parse failed: {result['error']}")
            return ""
        return result["text"]
