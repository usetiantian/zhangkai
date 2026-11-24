"""Nexus RAG — 关键词+语义双通道。numpy .npy 存储，不怕大文件损坏。"""
import os, json, logging, math, hashlib
import numpy as np
logger = logging.getLogger("nexus.rag")

class RAGEngine:
    def __init__(self):
        self._docs = []
        self._chunk_map = []   # chunk_idx -> doc_idx
        self._vectors = []     # embedding vectors
        self._cache = {}
        self._lm_client = None

    def set_lm(self, client):
        """注入 LM Studio 客户端，用于语义向量。"""
        self._lm_client = client

    def ingest_document(self, text: str, source: str = ""):
        chunks = self._chunk(text)
        di = len(self._docs)
        self._docs.append({"text": text, "source": source, "chunks": chunks})
        for c in chunks:
            self._vectors.append(self._embed(c))
            self._chunk_map.append(di)

    def _chunk(self, text, size=500, overlap=50):
        return [text[i:i+size] for i in range(0, len(text), size-overlap)] or [text]

    def _embed(self, text: str) -> list:
        if text in self._cache: return self._cache[text]
        # 优先用 LM Studio
        if self._lm_client:
            try:
                v = self._lm_client.embed(text)
                if v:
                    self._cache[text] = v
                    return v
            except Exception as e:
                logger.warning(f"LM embed failed: {e}")
        # 兜底：BOW
        return self._bow(text)

    def _bow(self, text, dim=128):
        words = text.lower().split()
        v = [0.0]*dim
        for w in words:
            v[int(hashlib.md5(w.encode()).hexdigest()[:8],16) % dim] += 1
        n = math.sqrt(sum(x*x for x in v)) or 1
        return [x/n for x in v]

    def _cos(self, a, b): return sum(x*y for x,y in zip(a,b))

    def search(self, query: str, top_k=5) -> list:
        if not self._docs: return []
        qv = self._embed(query)
        # 关键词预筛：用单个词匹配
        q_words = query.lower().split()
        hits = set()
        for i, ci in enumerate(self._chunk_map):
            text = self._docs[int(ci)]["text"].lower()
            if any(w in text for w in q_words):
                hits.add(i)
        # 没啥命中就全量向量搜索
        idxs = list(hits)[:200] if hits else range(min(len(self._vectors), 3000))
        scored = []
        for i in idxs:
            if i < len(self._vectors) and self._vectors[i]:
                scored.append((self._cos(qv, self._vectors[i]), i))
        scored.sort(reverse=True)
        seen = set()
        result = []
        for s, i in scored[:top_k*2]:
            d = self._docs[int(self._chunk_map[i])]
            k = d["source"]
            if k not in seen:
                seen.add(k)
                result.append({"text": d["text"][:500], "source": k, "score": round(s,3)})
        return result[:top_k]

    def stats(self): return {"docs": len(self._docs), "chunks": len(self._vectors), "has_embeddings": bool(self._vectors)}

    def reembed_all(self):
        """用模型重新生成所有向量。调用即升级搜索质量。"""
        if not self._model or not self._model.is_loaded():
            return False
        self._vectors = []
        import sys
        for ci in self._chunk_map:
            di = int(ci)
            if di < len(self._docs):
                chunk = self._docs[di]["text"][:1000]
                self._vectors.append(self._embed(chunk))
        return True

    def save(self, dirpath: str):
        """原子写入：先写 .tmp 再 rename，不会损坏已有数据。"""
        os.makedirs(dirpath, exist_ok=True)
        # docs 用 JSON（文本，较小）
        dp_tmp = os.path.join(dirpath, "docs.json.tmp")
        dp_final = os.path.join(dirpath, "docs.json")
        with open(dp_tmp, "w", encoding="utf-8") as f:
            json.dump(self._docs, f, ensure_ascii=False)
        os.replace(dp_tmp, dp_final)  # 原子替换

        # vectors 用 .npy（二进制，不怕截断）
        if self._vectors:
            for name, data in [("vectors", self._vectors), ("chunk_map", self._chunk_map)]:
                final = os.path.join(dirpath, f"{name}.npy")
                tmp = final + ".tmp"  # np.save appends .npy → actual file is vectors.npy.tmp.npy
                np.save(tmp, np.array(data, dtype=np.float32))
                os.replace(tmp + ".npy", final)

    def load(self, dirpath: str):
        dp = os.path.join(dirpath, "docs.json")
        if os.path.exists(dp):
            try:
                with open(dp, "r", encoding="utf-8") as f:
                    self._docs = json.load(f)
            except Exception:
                pass  # 损坏就算了，下次重索引

        vp = os.path.join(dirpath, "vectors.npy")
        cp = os.path.join(dirpath, "chunk_map.npy")
        if os.path.exists(vp) and os.path.exists(cp):
            try:
                self._vectors = np.load(vp).tolist()
                self._chunk_map = np.load(cp).tolist()
            except Exception:
                pass  # 损坏就空着，BOW 兜底

    def remove(self, source: str):
        remove_doc_indices = sorted(
            [i for i, d in enumerate(self._docs) if d.get("source") == source],
            reverse=True
        )
        if not remove_doc_indices:
            return

        for ci in sorted([i for i, d in enumerate(self._chunk_map) if int(d) in remove_doc_indices], reverse=True):
            if ci < len(self._vectors): del self._vectors[ci]
            if ci < len(self._chunk_map): del self._chunk_map[ci]

        for di in remove_doc_indices:
            del self._docs[di]

        for di in remove_doc_indices:
            for i in range(len(self._chunk_map)):
                if int(self._chunk_map[i]) > di:
                    self._chunk_map[i] = int(self._chunk_map[i]) - 1
