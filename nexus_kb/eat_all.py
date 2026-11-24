"""后台慢慢吃 — 逐文件摄入 D:/node。Qwen 自动分类扩展名，不硬编码。"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from nexus_kb import KnowledgeBase
from nexus_kb.ingest.parser import _PARSERS
import time

kb = KnowledgeBase("D:/node")

# 读 Qwen 自动分类的扩展名（不硬编码！）
CLASSIFY_PATH = "D:/node/.nexus/ext_classification.json"
if os.path.exists(CLASSIFY_PATH):
    with open(CLASSIFY_PATH, "r", encoding="utf-8") as f:
        ext_class = json.load(f)
    TEXT_EXTS = set(ext_class.get("TEXT", []))
    PARSE_EXTS = set(ext_class.get("PARSE", []))
    BINARY_EXTS = set(ext_class.get("BINARY", []))
    print(f"Using Qwen classification: TEXT={len(TEXT_EXTS)} PARSE={len(PARSE_EXTS)} BINARY={len(BINARY_EXTS)}")
else:
    # Fallback（但理论上不应该走到这里）
    TEXT_EXTS = {'.txt','.md','.py','.json','.csv','.yaml','.log','.js','.ts'}
    PARSE_EXTS = {'.pdf','.docx','.pptx','.xlsx'}
    BINARY_EXTS = {'.jpg','.png','.mp4','.zip','.pyc','.pyd'}
    print("WARNING: Using fallback hardcoded classification")

total = 0
ok = 0
registered = 0
skipped = 0
failed = 0
start = time.time()

for root, dirs, files in os.walk("D:/node"):
    dirs[:] = [d for d in dirs if not d.startswith(".")]
    for f in files:
        if f.startswith("."):
            continue
        fp = os.path.join(root, f)
        ext = os.path.splitext(f)[1].lower()

        try:
            if ext in TEXT_EXTS:
                r = kb.ingest_file(fp)
            elif ext in PARSE_EXTS:
                r = kb.ingest_file(fp)  # 慢但还是要
            else:
                # 二进制：仅注册到图谱，不解析内容
                h = kb._hash_file(fp)
                fp_norm = os.path.normpath(fp).replace(os.sep, "/")
                if fp_norm not in kb._ingested or kb._ingested[fp_norm] != h:
                    kb._ingested[fp_norm] = h
                    kb.graph.add_entity(fp_norm, os.path.basename(f), "binary",
                        owner="system", size=os.path.getsize(fp), ext=ext,
                        ingested_at=time.time())
                    registered += 1
                total += 1
                if total % 5000 == 0:
                    kb._save_state()
                    elapsed = time.time() - start
                    print(f"[{total:>6}] ok={ok} reg={registered} skip={skipped} fail={failed}  {total/elapsed:.1f}/s  {f[:40]}", flush=True)
                continue

            total += 1
            if r.get("status") == "ok":
                ok += 1
            elif r.get("status") == "skipped":
                skipped += 1
            else:
                failed += 1

        except Exception as e:
            failed += 1
            total += 1

        if total % 5000 == 0:
            kb._save_state()
            elapsed = time.time() - start
            print(f"[{total:>6}] ok={ok} reg={registered} skip={skipped} fail={failed}  {total/elapsed:.1f}/s  {f[:40]}", flush=True)

kb.save()
elapsed = time.time() - start
print(f"\nDone: {total} files in {elapsed/60:.1f} min")
print(f"  ok={ok}  registered={registered}  skipped={skipped}  failed={failed}")
print(f"  Graph: {kb.graph.stats()}")
print(f"  RAG: {kb.rag.stats()}")
