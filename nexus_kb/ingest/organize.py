"""
自动整理引擎 — 分析内容而非文件夹名，智能合并重组

整理逻辑（大局出发）：
  1. 先用知识图谱社区检测，找出内容的"自然分组"（不管文件夹名叫什么）
  2. 同一社区的文件 → 应该在一个文件夹里
  3. 合并时跳过 SHA256 完全相同的文件
  4. 生成整理方案 → 预览 → 用户确认 → 执行
  5. 保留原结构备份，可撤销
"""

import os, shutil, hashlib, json, time, logging
from collections import defaultdict
from difflib import SequenceMatcher

logger = logging.getLogger("nexus_kb.organize")


class AutoOrganizer:
    """基于内容的知识库自动整理。"""

    def __init__(self, knowledge_base):
        self.kb = knowledge_base
        self.backup_dir = os.path.join(self.kb.data_dir, ".organize_backups")

    # ========================================
    # 分析
    # ========================================

    def analyze(self) -> dict:
        """
        全面分析，返回整理建议。
        核心思路：用社区检测找内容分组，不是靠文件夹名猜测。
        """
        # 1. 用社区检测发现内容的自然分组
        communities = self.kb.detect_communities()
        community_map = {}
        for cid, node_ids in communities.items():
            for nid in node_ids:
                community_map[nid] = cid

        # 2. 按社区分组文件
        community_files = defaultdict(list)
        for root, dirs, files in os.walk(self.kb.data_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                if f.startswith("."):
                    continue
                fp = os.path.join(root, f)
                fp_norm = os.path.normpath(fp).replace(os.sep, "/")
                cid = community_map.get(fp_norm, -1)
                community_files[cid].append(fp)

        # 3. 为每个社区推荐一个主文件夹
        suggestions = []
        for cid, files in community_files.items():
            if cid == -1 or len(files) < 2:
                continue
            # 分析这个社区的文件：找共同主题
            topic = self._infer_topic(files, cid)
            main_dir = self._pick_main_folder(files)
            suggestions.append({
                "topic": topic,
                "main_folder": main_dir,
                "file_count": len(files),
                "source_folders": list(set(os.path.dirname(f) for f in files)),
                "files": files[:10],  # 前10个作为示例
            })

        # 4. 发现需要合并的文件夹组
        merge_groups = self._find_merge_groups()

        # 5. SHA256 完全重复
        dups = self._find_exact_duplicates()

        return {
            "communities": len(communities),
            "topic_groups": len(suggestions),
            "suggestions": suggestions[:10],
            "merge_groups": merge_groups[:10],
            "exact_duplicates": len(dups),
            "total_dup_files": sum(d["count"] for d in dups),
        }

    def _infer_topic(self, files: list, community_id) -> str:
        """从文件内容推断主题。"""
        # 从知识图谱中找这个社区的节点
        words = []
        for fp in files:
            fp_norm = os.path.normpath(fp).replace(os.sep, "/")
            node = self.kb.graph.nodes.get(fp_norm, {})
            name = node.get("name", os.path.basename(fp))
            words.extend(name.split("_"))
            words.extend(name.split("-"))
            words.extend(name.split())

        # 词频统计
        from collections import Counter
        # 过滤掉日期、数字、短词
        stop = {"md", "txt", "json", "py", "2026", "2025", "2024", "the", "and", "for", "with"}
        filtered = [w for w in words if len(w) > 1 and w.lower() not in stop]
        top = Counter(filtered).most_common(5)
        return ", ".join(w for w, _ in top) if top else f"group_{community_id}"

    def _pick_main_folder(self, files: list) -> str:
        """在社区里选一个最好的文件夹作为主目录。"""
        if not files:
            return ""
        # 选包含文件最多的文件夹
        dir_counts = defaultdict(int)
        for fp in files:
            dir_counts[os.path.dirname(fp)] += 1
        return max(dir_counts, key=dir_counts.get)

    def _find_merge_groups(self) -> list:
        """
        发现应该合并的文件夹组。
        策略：
        1. 只看顶层文件夹
        2. 名字子串匹配（中文"股票研究"包含"股票"）
        3. 内容采样对比（文件夹里抽几个文件，看主题是否相似）
        """
        folders = []
        for d in os.listdir(self.kb.data_dir):
            dp = os.path.join(self.kb.data_dir, d)
            if not os.path.isdir(dp) or d.startswith("."):
                continue
            file_count = sum(len(files) for _, _, files in os.walk(dp))
            # 采样文件内容做主题词
            sample_texts = []
            for root, _, files in os.walk(dp):
                for f in files[:3]:
                    try:
                        fp = os.path.join(root, f)
                        if os.path.getsize(fp) < 1024 * 1024:
                            with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                                sample_texts.append(fh.read()[:500])
                    except:
                        pass
                break

            # 从文件名和内容中提取关键词
            keywords = self._extract_keywords(d, sample_texts)
            folders.append({
                "path": dp, "name": d, "files": file_count,
                "keywords": keywords, "samples": sample_texts,
            })

        pairs = []
        seen = set()
        for i in range(len(folders)):
            for j in range(i + 1, len(folders)):
                a, b = folders[i], folders[j]
                pair_key = (a["path"], b["path"])
                if pair_key in seen:
                    continue
                seen.add(pair_key)

                # 信号1：名字子串匹配（中文友好）
                name_score = self._name_match_score(a["name"], b["name"])

                # 信号2：关键词重叠
                kw_overlap = len(a["keywords"] & b["keywords"])
                kw_union = len(a["keywords"] | b["keywords"])
                kw_score = kw_overlap / kw_union if kw_union else 0

                # 信号3：内容文本重叠
                content_score = self._content_overlap_score(a["samples"], b["samples"])

                score = name_score * 0.4 + kw_score * 0.35 + content_score * 0.25
                if score > 0.2:
                    pairs.append({
                        "folder1": {"path": a["path"], "name": a["name"], "files": a["files"]},
                        "folder2": {"path": b["path"], "name": b["name"], "files": b["files"]},
                        "name_score": round(name_score, 2),
                        "keyword_score": round(kw_score, 2),
                        "content_score": round(content_score, 2),
                        "score": round(score, 2),
                        "combined_files": a["files"] + b["files"],
                    })

        pairs.sort(key=lambda x: -x["score"])
        return pairs

    def _name_match_score(self, name1: str, name2: str) -> float:
        """中文友好的文件夹名匹配。支持子串、翻译、缩写。"""
        n1, n2 = name1.lower(), name2.lower()
        # 直接子串包含
        if n1 in n2 or n2 in n1:
            return 0.8
        # 序列匹配
        sim = SequenceMatcher(None, n1, n2).ratio()
        # 去空格/下划线后比较
        clean1 = n1.replace(" ", "").replace("_", "").replace("-", "")
        clean2 = n2.replace(" ", "").replace("_", "").replace("-", "")
        clean_sim = SequenceMatcher(None, clean1, clean2).ratio()
        # 常见翻译映射
        trans = {"股票": "stock", "记忆": "memory", "日记": "diary", "笔记": "notes",
                 "研究": "research", "数据": "data", "学习": "learn", "开发": "dev"}
        trans_match = False
        for cn, en in trans.items():
            if (cn in n1 and en in n2) or (cn in n2 and en in n1):
                trans_match = True
                break
        trans_bonus = 0.5 if trans_match else 0
        return max(sim, clean_sim, trans_bonus)

    def _extract_keywords(self, name: str, sample_texts: list) -> set:
        """从文件夹名和内容中提取关键词。"""
        keywords = set()
        # 从文件夹名提取
        for part in name.lower().replace("_", " ").replace("-", " ").split():
            if len(part) > 1:
                keywords.add(part)
        # 中文 n-gram
        for i in range(len(name) - 1):
            keywords.add(name[i:i+2].lower())
        # 从内容中提取高频词
        from collections import Counter
        all_text = " ".join(sample_texts)
        words = [w for w in all_text.lower().split() if len(w) > 2]
        top_words = Counter(words).most_common(10)
        keywords.update(w for w, _ in top_words)
        return keywords

    def _content_overlap_score(self, samples1: list, samples2: list) -> float:
        """两组采样文本的词汇重叠率。"""
        if not samples1 or not samples2:
            return 0
        words1 = set(" ".join(samples1).lower().split())
        words2 = set(" ".join(samples2).lower().split())
        if not words1 or not words2:
            return 0
        return len(words1 & words2) / min(len(words1), len(words2))

    def _find_exact_duplicates(self) -> list:
        """SHA256 完全重复。"""
        hash_map = defaultdict(list)
        for root, dirs, files in os.walk(self.kb.data_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for f in files:
                fp = os.path.join(root, f)
                try:
                    if os.path.getsize(fp) > 50 * 1024 * 1024:
                        continue
                    h = self._hash_file(fp)
                    hash_map[(h, os.path.getsize(fp))].append(fp)
                except OSError:
                    pass

        dups = []
        for (h, size), files in hash_map.items():
            if len(files) > 1:
                dups.append({"hash": h[:16], "size": size, "count": len(files), "files": files})
        dups.sort(key=lambda x: -x["count"])
        return dups

    # ========================================
    # 执行
    # ========================================

    def execute_merge(self, merge_groups: list = None, dry_run: bool = True) -> dict:
        """
        执行合并：把分散的文件夹内容归拢。
        如果 dry_run=True，只返回计划不执行。
        """
        if merge_groups is None:
            merge_groups = self._find_merge_groups()

        plan = []
        for group in merge_groups[:20]:
            if group["score"] < 0.4:  # 阈值太低不合并
                continue
            # 选文件多的做主目录
            a, b = group["folder1"], group["folder2"]
            main = a if a["files"] >= b["files"] else b
            sub = b if a["files"] >= b["files"] else a

            # 扫描 sub 中的文件，跳过与 main 中 SHA256 重复的
            moves = []
            skips = []
            main_hashes = set()
            for root, _, files in os.walk(main["path"]):
                for f in files:
                    try:
                        fp = os.path.join(root, f)
                        if os.path.getsize(fp) < 50 * 1024 * 1024:
                            main_hashes.add(self._hash_file(fp))
                    except: pass

            for root, _, files in os.walk(sub["path"]):
                for f in files:
                    try:
                        fp = os.path.join(root, f)
                        if os.path.getsize(fp) >= 50 * 1024 * 1024:
                            skips.append(fp)
                            continue
                        h = self._hash_file(fp)
                        if h in main_hashes:
                            skips.append(fp)
                        else:
                            rel = os.path.relpath(fp, sub["path"])
                            dest = os.path.join(main["path"], f"_[from_{sub['name']}]_{rel}")
                            moves.append({"from": fp, "to": dest})
                    except: pass

            if moves:
                plan.append({
                    "main": main["path"], "sub": sub["path"],
                    "moves": len(moves), "skips": len(skips),
                    "moves_preview": moves[:5],
                })

        if not dry_run and plan:
            os.makedirs(self.backup_dir, exist_ok=True)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            log_path = os.path.join(self.backup_dir, f"merge_{timestamp}.json")

            executed = []
            for p in plan:
                for m in p["moves"]:
                    os.makedirs(os.path.dirname(m["to"]), exist_ok=True)
                    shutil.move(m["from"], m["to"])
                executed.append(p)

            with open(log_path, "w") as f:
                json.dump(executed, f, ensure_ascii=False, indent=2)
            return {"status": "executed", "plan": plan, "log": log_path}

        return {"status": "dry_run" if dry_run else "no_changes", "plan": plan}

    def _hash_file(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
