# -*- coding: utf-8 -*-
"""
Qwen 知识提取器 — 本地精读外部数据, 提取结构化知识点 (2026-07-15)

数据源: data/external/{code,papers,math,zh_texts}/
去重: SHA256 指纹持久化, 重启不丢失
Qwen: embedding 过滤重复 + generate 提取知识
"""
import json
import hashlib
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("nexus.knowledge_extractor")

_NEXUS_HOME = Path.home() / ".nexus"
_EXTERNAL_DIR = _NEXUS_HOME / "data" / "external"
_FINGERPRINT_FILE = _NEXUS_HOME / "data" / "knowledge_fingerprints.json"

# Qwen prompt — 从代码/论文提取知识点
_EXTRACT_PROMPTS = {
    "code": (
        "从以下代码库摘要中提取 1-3 个关键知识点。每个知识点一行，格式: 领域|知识点|一句话说明。\n"
        "只输出有用的事实, 不输出废话。\n\n"
        "代码: {content}\n\n知识点:"
    ),
    "paper": (
        "从以下论文摘要中提取 1-3 个关键发现。每个发现一行，格式: 论文方向|发现|一句话说明。\n\n"
        "论文: {content}\n\n发现:"
    ),
    "math": (
        "从以下数学文档中提取 1-3 个关键公式/定理。每个一行，格式: 分支|公式名|用途。\n\n"
        "文档: {content}\n\n公式:"
    ),
    "text": (
        "从以下中文文本中提取 1-3 个关键概念。每个一行，格式: 主题|概念|说明。\n\n"
        "文本: {content}\n\n概念:"
    ),
}


class KnowledgeExtractor:
    """Qwen 驱动的外部知识提取器 — 去重持久化, 增量处理。"""

    def __init__(self):
        self._fingerprints: Dict[str, float] = {}
        self._load_fingerprints()

    def _load_fingerprints(self):
        """加载已处理文件的指纹。"""
        if _FINGERPRINT_FILE.exists():
            try:
                self._fingerprints = json.loads(_FINGERPRINT_FILE.read_text(encoding="utf-8"))
                logger.info("[KnowledgeExtractor] Loaded %d fingerprints", len(self._fingerprints))
            except Exception:
                logger.warning("[KnowledgeExtractor] Fingerprint file corrupted, resetting")
                self._fingerprints = {}

    def _save_fingerprints(self):
        """持久化指纹到磁盘。"""
        _FINGERPRINT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(_FINGERPRINT_FILE, "w", encoding="utf-8") as f:
            json.dump(self._fingerprints, f, ensure_ascii=False, indent=2)

    def _file_fingerprint(self, filepath: Path) -> str:
        """计算文件 SHA256 指纹。"""
        try:
            data = filepath.read_bytes()
            return hashlib.sha256(data).hexdigest()[:16]
        except Exception:
            return ""

    def _is_new(self, filepath: Path) -> bool:
        """检查文件是否未处理过（或已更新）。"""
        fp = self._file_fingerprint(filepath)
        if not fp:
            return False
        if fp not in self._fingerprints:
            return True
        # 检查文件是否被修改（mtime 比记录的时间晚）
        last_processed = self._fingerprints.get(fp, 0)
        return filepath.stat().st_mtime > last_processed

    def _mark_processed(self, filepath: Path):
        """标记文件已处理。"""
        fp = self._file_fingerprint(filepath)
        if fp:
            self._fingerprints[fp] = time.time()
            if len(self._fingerprints) > 10000:
                # 清理超过 30 天的旧指纹
                cutoff = time.time() - 30 * 86400
                self._fingerprints = {k: v for k, v in self._fingerprints.items() if v > cutoff}

    def _qwen_extract(self, content: str, category: str) -> List[str]:
        """用 Qwen 从内容中提取知识点。"""
        prompt_template = _EXTRACT_PROMPTS.get(category, _EXTRACT_PROMPTS["text"])
        prompt = prompt_template.format(content=content[:3000])
        try:
            from nexus_agent.nexus_brain import get_brain
            brain = get_brain()
            if brain and brain.is_loaded:
                result = brain._generate(prompt, max_tokens=200, temperature=0.2)
                if result and result.strip():
                    lines = [l.strip() for l in result.split("\n") if l.strip() and "|" in l]
                    return lines[:5]
        except Exception:
            pass
        return []

    def _qwen_dedup(self, items: List[str]) -> List[str]:
        """用 Qwen embedding 过滤与 EvoKG 已有知识重复的条目。"""
        if not items:
            return items
        try:
            from nexus_agent.qwen_enhance import semantic_similarity
            from nexus_agent.evokg import get_evokg
            kg = get_evokg()
            # 取各域已有知识做对比
            existing = []
            for domain in ["programming", "ai", "math", "finance", "tcm"]:
                results = kg.search_similar(domain, k=2)
                for r in results:
                    existing.append(r.get("label", ""))
            if not existing:
                return items

            filtered = []
            for item in items:
                text = item.split("|")[-1] if "|" in item else item
                max_sim = max(
                    (semantic_similarity(text, e) for e in existing if e),
                    default=0.0
                )
                if max_sim < 0.85:
                    filtered.append(item)
            return filtered
        except Exception:
            return items

    def scan_and_extract(self, max_files: int = 10) -> Dict:
        """扫描外部数据目录, 提取新文件的增量知识。

        Returns: {"extracted": int, "stored": int, "skipped": int, "errors": int}
        """
        stats = {"extracted": 0, "stored": 0, "skipped": 0, "errors": 0}
        all_items = []

        # 扫描各分类目录
        scan_map = {
            "code": _EXTERNAL_DIR / "code",
            "papers": _EXTERNAL_DIR / "papers",
            "math": _EXTERNAL_DIR / "math",
            "text": _EXTERNAL_DIR / "zh_texts",
        }

        for category, base_dir in scan_map.items():
            if not base_dir.exists():
                continue
            json_files = list(base_dir.rglob("*.json"))
            new_files = [f for f in json_files if self._is_new(f)][:max_files]

            for f in new_files:
                try:
                    data = json.loads(f.read_text(encoding="utf-8", errors="ignore"))
                    content = str(data)[:5000]

                    # Qwen 提取知识点
                    items = self._qwen_extract(content, category)
                    if items:
                        all_items.extend(items)
                        stats["extracted"] += len(items)
                    self._mark_processed(f)
                except Exception as e:
                    logger.debug("[KnowledgeExtractor] %s: %s", f.name, e)
                    stats["errors"] += 1

        # Qwen 语义去重
        unique_items = self._qwen_dedup(all_items)

        # 存储到 EvoKG
        for item in unique_items:
            try:
                from nexus_agent.evokg import get_evokg
                kg = get_evokg()
                parts = item.split("|")
                label = parts[-1].strip() if len(parts) > 1 else item.strip()
                domain = parts[0].strip() if parts else "general"
                kg.add_observation(
                    label=label[:200],
                    modality="text",
                    confidence=0.7,
                    metadata={"source": "external_extract", "domain": domain, "raw": item[:300]},
                )
                stats["stored"] += 1
            except Exception:
                stats["errors"] += 1

        self._save_fingerprints()
        if stats["stored"] > 0:
            logger.info("[KnowledgeExtractor] Extracted %d items (%d unique), stored %d",
                       stats["extracted"], len(unique_items), stats["stored"])
        return stats


_extractor: Optional[KnowledgeExtractor] = None


def get_knowledge_extractor() -> KnowledgeExtractor:
    global _extractor
    if _extractor is None:
        _extractor = KnowledgeExtractor()
    return _extractor
