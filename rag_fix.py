"""
修复 RAG 内存爆炸的根因——_docs 不该存全文。
运行: python rag_fix.py
作用: 把 9GB docs.json 转成 chunks.jsonl (只存分块, 不存全文)
      搜索时用分块文本匹配关键词, 结果返回分块内容
"""
import json, os, sys, time, shutil
sys.path.insert(0, 'D:/node')
from nexus_kb.engine.rag import RAGEngine
import numpy as np

INDEX_DIR = 'D:/node/.nexus/vectors'
DOCS_PATH = os.path.join(INDEX_DIR, 'docs.json')
CHUNKS_PATH = os.path.join(INDEX_DIR, 'chunks.jsonl')

print("=" * 60)
print("RAG 内存修复: 全文 → 分块")
print("=" * 60)

# 1. 加载旧数据
print("\n[1/3] 加载旧 docs.json (9GB)...")
t0 = time.time()
with open(DOCS_PATH, 'r', encoding='utf-8') as f:
    old_docs = json.load(f)
print(f"  {len(old_docs)} 文档, {time.time()-t0:.0f}s")

# 2. 提取分块, 丢弃全文
print("[2/3] 提取分块, 丢弃全文...")
t0 = time.time()
new_docs = []   # 只存 source
chunks = []     # 扁平化分块文本

for doc in old_docs:
    source = doc.get('source', '')
    chunk_texts = doc.get('chunks', [])
    if not chunk_texts and doc.get('text'):
        # 旧数据可能 chunks 为空但有 text, 临时分块
        text = doc.get('text', '')
        chunk_texts = [text[i:i+500] for i in range(0, len(text), 450)] or [text]

    chunk_start = len(chunks)
    chunks.extend(chunk_texts)
    new_docs.append({
        "source": source,
        "chunk_start": chunk_start,
        "chunk_count": len(chunk_texts)
    })

print(f"  {len(new_docs)} 新文档, {len(chunks)} 分块, {time.time()-t0:.0f}s")
old_size = os.path.getsize(DOCS_PATH) / 1024**3

# 3. 保存
print("[3/3] 保存...")
# Backup old docs.json
shutil.copy2(DOCS_PATH, DOCS_PATH + '.fulltext.bak')
print(f"  旧文件备份: docs.json.fulltext.bak ({old_size:.1f}GB)")

# Save new docs.json (tiny)
tmp = DOCS_PATH + '.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(new_docs, f, ensure_ascii=False)
os.replace(tmp, DOCS_PATH)
new_docs_size = os.path.getsize(DOCS_PATH) / 1024**2
print(f"  新 docs.json: {new_docs_size:.1f} MB (旧: {old_size:.1f} GB)")

# Save chunks.jsonl
with open(CHUNKS_PATH, 'w', encoding='utf-8') as f:
    for chunk in chunks:
        f.write(json.dumps(chunk, ensure_ascii=False) + '\n')
chunks_size = os.path.getsize(CHUNKS_PATH) / 1024**3
print(f"  chunks.jsonl: {chunks_size:.2f} GB")

total_new = new_docs_size / 1024 + chunks_size
print(f"\n总磁盘: {total_new:.2f} GB (旧: {old_size:.1f} GB)")
print(f"内存优化: Python 字符串按需加载, 不再全量入 RAM")
print(f"\n完成! 下次加载 KB 时内存占用应降至 ~3-5GB")
