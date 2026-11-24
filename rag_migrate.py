"""
RAG 内存修复 — 9GB docs.json → chunks (分块文本，按需加载)
一次性迁移，会短暂吃内存（必须读完旧文件才能转），之后永不再吃。

运行: python rag_migrate.py
"""
import json, os, sys, time, shutil, psutil

INDEX_DIR = 'D:/node/.nexus/vectors'
DOCS_PATH = os.path.join(INDEX_DIR, 'docs.json')
CHUNKS_PATH = os.path.join(INDEX_DIR, 'chunks.jsonl')

proc = psutil.Process()

def mem():
    return proc.memory_info().rss / 1024**3

def log(msg):
    print(f"[{mem():.1f}GB] {msg}", flush=True)

log("=== RAG 内存修复: 全文 → 分块 ===")

# 1. 加载旧数据 (这步必须吃内存 — 9GB JSON → Python 对象)
log("加载旧 docs.json...")
t0 = time.time()
with open(DOCS_PATH, 'r', encoding='utf-8') as f:
    old_docs = json.load(f)
log(f"加载完成: {len(old_docs)} 文档, {time.time()-t0:.0f}s")

# 2. 提取分块，丢全文
log("提取分块，丢弃全文...")
t0 = time.time()
new_docs = []
chunks = []

for doc in old_docs:
    source = doc.get('source', '')
    chunk_texts = doc.get('chunks', [])
    if not chunk_texts and doc.get('text'):
        text = doc.get('text', '')
        chunk_texts = [text[i:i+500] for i in range(0, len(text), 450)] or [text]
    chunk_start = len(chunks)
    chunks.extend(chunk_texts)
    new_docs.append({
        "source": source,
        "chunk_start": chunk_start,
        "chunk_count": len(chunk_texts)
    })

log(f"提取完成: {len(new_docs)} 文档, {len(chunks)} 分块, {time.time()-t0:.0f}s")

# 3. 释放旧数据
old_size = os.path.getsize(DOCS_PATH) / 1024**3
del old_docs
log(f"释放旧 docs 内存")

# 4. 保存新格式
log(f"保存新格式 (旧: {old_size:.1f}GB)...")

shutil.copy2(DOCS_PATH, DOCS_PATH + '.fulltext.bak')

tmp = DOCS_PATH + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(new_docs, f, ensure_ascii=False)
os.replace(tmp, DOCS_PATH)

with open(CHUNKS_PATH, 'w', encoding='utf-8') as f:
    for chunk in chunks:
        f.write(json.dumps(chunk, ensure_ascii=False) + '\n')

new_docs_mb = os.path.getsize(DOCS_PATH) / 1024**2
chunks_gb = os.path.getsize(CHUNKS_PATH) / 1024**3

log(f"新 docs.json: {new_docs_mb:.0f} MB")
log(f"chunks.jsonl: {chunks_gb:.2f} GB")
log(f"备份: docs.json.fulltext.bak ({old_size:.1f}GB) — 确认没问题后可删")
log(f"完成! 下次加载 KB: 只读 chunks.jsonl 需要的行, 不再全量入 RAM")
