"""Nexus RAG — 关键词+语义双通道"""
import os, json, logging, urllib.request, math, hashlib
logger = logging.getLogger("nexus.rag")

class RAGEngine:
    def __init__(self):
        self._docs = []
        self._chunk_map = []   # chunk_idx -> doc_idx
        self._vectors = []     # embedding vectors
        self._cache = {}

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
        try:
            body = json.dumps({"model":"text-embedding-nomic-embed-text-v1.5","input":text[:1000]}).encode()
            req = urllib.request.Request("http://127.0.0.1:1234/v1/embeddings", body, {"Content-Type":"application/json"})
            r = json.loads(urllib.request.urlopen(req, timeout=5).read())
            v = r["data"][0]["embedding"]
            self._cache[text] = v
            return v
        except:
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
        hits = {i for i, ci in enumerate(self._chunk_map) if query.lower() in self._docs[ci]["text"].lower()}
        idxs = hits if hits else range(len(self._vectors))
        scored = []
        for i in idxs:
            if i < len(self._vectors) and self._vectors[i]:
                scored.append((self._cos(qv, self._vectors[i]), i))
        scored.sort(reverse=True)
        seen = set()
        result = []
        for s, i in scored[:top_k*2]:
            d = self._docs[self._chunk_map[i]]
            k = d["source"]
            if k not in seen:
                seen.add(k)
                result.append({"text": d["text"][:300], "source": k, "score": round(s,3)})
        return result[:top_k]

    def stats(self): return {"docs": len(self._docs), "chunks": len(self._vectors), "has_embeddings": bool(self._vectors)}
