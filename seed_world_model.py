# -*- coding: utf-8 -*-
"""Seed Nexus's canonical 256-D world-model space from existing local data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# Keep imports fail-fast: only encoder errors are allowed to use the hash fallback.
NEXUS = Path.home() / ".nexus"
os.chdir(NEXUS)
sys.path.insert(0, str(NEXUS))
from nexus_agent.neural import encoders  # noqa: E402
from nexus_agent.neural.world_model import get_unified_space  # noqa: E402

DIM = 256
DATA = NEXUS / "data"

def hash_vector(text: str):
    import numpy as np
    raw = hashlib.sha256(text.encode("utf-8")).digest() * 8
    v = np.frombuffer(raw[:DIM], dtype=np.uint8).astype(np.float32)
    v /= max(float(np.linalg.norm(v)), 1e-12)
    return v

def encode(text: str, hub):
    """Use the canonical encoder hub; fall back only when encoding fails."""
    try:
        import numpy as np
        v = np.asarray(hub.encode(text, "text"), dtype=np.float32).reshape(-1)
        if v.size != DIM:
            v = np.pad(v[:DIM], (0, max(0, DIM - v.size)))
        norm = float(np.linalg.norm(v))
        if norm > 0:
            return v / norm, "encoder"
    except Exception as exc:
        print(f"[WARN] encoder failed; using hash fallback: {exc}")
    return hash_vector(text), "hash_fallback"

def jsonl(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            yield json.loads(line)

def load_items(source: str):
    if source == "bilibili_seeds":
        for i, row in enumerate(json.loads((DATA / "bilibili_seeds.json").read_text(encoding="utf-8"))):
            audio = (row.get("audio_seed") or {}).get("text", "")
            topics = " ".join((row.get("text_seed") or {}).get("topics", []))
            text = " ".join(x for x in (row.get("title", ""), topics, audio) if x).strip()
            if text:
                yield text[:2000], f"bilibili:{row.get('title', '')[:80]}", {"seed_id": row.get("seed_id"), "source": "bilibili_seeds"}
    elif source == "identity_weights":
        from nexus_agent.living_core.identity import get_identity
        for w in get_identity()._weights.values():
            text = f"{w.pattern} => {w.response}".strip()
            if text:
                yield text[:2000], f"identity:{w.pattern[:80]}", {"source": "identity_weights", "key": w.key, "hits": w.hits}
    elif source == "curiosity":
        for name in ("unanswered_questions.jsonl", "research_tickets.jsonl"):
            for row in jsonl(DATA / "curiosity" / name):
                q = str(row.get("question", "")).strip()
                extra = str(row.get("context", "") or row.get("study_notes", "")).strip()
                text = " ".join(x for x in (q, extra) if x)
                if text:
                    yield text[:2000], f"curiosity:{q[:80]}", {"source": name}
    elif source == "conversations":
        for path in sorted((NEXUS / "conversations").glob("*.jsonl")):
            for row in jsonl(path):
                text = str(row.get("content", "")).strip()
                if text:
                    yield text[:2000], f"conversation:{row.get('role', '?')}:{text[:70]}", {"source": path.name, "role": row.get("role")}
    elif source == "experience":
        conn = sqlite3.connect(str(DATA / "experience_bank.db"))
        try:
            rows = conn.execute("SELECT id,type,content,significance FROM experiences WHERE type != 'test' AND type NOT LIKE 'test_%' ORDER BY id").fetchall()
        finally:
            conn.close()
        for ident, kind, content, significance in rows:
            text = str(content or "").strip()
            if text:
                yield text[:2000], f"experience:{kind}:{ident}", {"source": "experience_bank", "type": kind, "significance": significance}

def available(source: str) -> bool:
    return {"bilibili_seeds": DATA / "bilibili_seeds.json", "identity_weights": DATA / "neural" / "nexus_identity.weights", "curiosity": DATA / "curiosity", "conversations": NEXUS / "conversations", "experience": DATA / "experience_bank.db"}[source].exists()

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=("auto", "bilibili_seeds", "identity_weights", "identity", "curiosity", "conversations", "experience"), default="auto")
    parser.add_argument("--no-dedup", action="store_true", help="skip dedup and inject every seed")
    parser.add_argument("--limit", type=int, default=0, help="global maximum injections; 0 means all")
    parser.add_argument("--report-only", action="store_true", help="print planned injection count without writing disk")
    args = parser.parse_args()
    if args.limit < 0:
        parser.error("--limit must be >= 0")
    order = ["bilibili_seeds", "identity_weights", "curiosity", "conversations", "experience"]
    source = next((s for s in order if available(s)), None) if args.source == "auto" else args.source
    source = "identity_weights" if source == "identity" else source
    if source is None:
        print("[ERROR] no source is available")
        return 2
    space = get_unified_space(str(DATA / "world_model"))
    before = space.node_count()
    seeds = load_items(source)
    if not args.no_dedup:
        seen = set()
        seeds = (item for item in seeds if not (item[0][:60] in seen or seen.add(item[0][:60])))
    if args.limit:
        from itertools import islice
        seeds = islice(seeds, args.limit)
    if args.report_only:
        planned = sum(1 for _ in seeds)
        print(f"[REPORT-ONLY] source={source} nodes_before={before} would_inject={planned} "
              f"dedup={'off' if args.no_dedup else 'on'} limit={args.limit or 'all'}")
        return 0
    hub = encoders.get_encoder_hub()
    added = 0
    deduped = 0
    methods = {"encoder": 0, "hash_fallback": 0}
    started = time.time()
    print(f"[START] source={source} nodes_before={before} data_dir={space._data_dir}")
    # Sanity: snapshot the disk nodes.json BEFORE we start, so we can detect
    # whether add_node + periodic _save actually flushed to disk.
    disk_path = space._data_dir / "nodes.json"
    disk_before = json.loads(disk_path.read_text(encoding="utf-8")) if disk_path.exists() else {}
    disk_before_count = len([k for k in disk_before if not k.startswith("_")])
    print(f"[START] disk_nodes_before={disk_before_count}")
    for index, (text, label, metadata) in enumerate(seeds, 1):
        vector, method = encode(text, hub)
        # dedup=False is intentional: each source record is one seed node.
        # Sanity check: in-memory must grow by 1, and the returned nid must
        # actually exist in space._nodes. add_node returns the node id (str),
        # NOT a boolean or count, so we cannot trust a truthy return.
        nodes_before_call = space.node_count()
        ret = space.add_node(vector, label=label[:120], modality="text",
                             confidence=0.7, metadata=metadata, dedup=False)
        nodes_after_call = space.node_count()
        grew_in_mem = (nodes_after_call - nodes_before_call) >= 1
        ret_in_dict = (ret in space._nodes)
        if not grew_in_mem or not ret_in_dict:
            # add_node said OK but reality disagrees — do NOT count as added.
            deduped += 1
            print(f"[WARN] add_node returned {ret!r} but mem grew "
                  f"{nodes_before_call}->{nodes_after_call}, ret_in_dict={ret_in_dict} "
                  f"(idx={index}, label={label[:60]!r})")
        else:
            added += 1
            methods[method] += 1
        # Periodic progress + disk sanity (every 10 *actually added* nodes)
        if added and added % 10 == 0:
            try:
                disk_now = json.loads(disk_path.read_text(encoding="utf-8"))
                disk_now_count = len([k for k in disk_now if not k.startswith("_")])
            except Exception:
                disk_now_count = -1
            print(f"[PROGRESS] processed={added} mem_nodes={nodes_after_call} "
                  f"disk_nodes={disk_now_count} deduped={deduped}")
    # Force-flush to disk so disk_delta is always truthful.
    space.close()
    # Post-run disk check
    after = space.node_count()
    try:
        disk_after = json.loads(disk_path.read_text(encoding="utf-8"))
        disk_after_count = len([k for k in disk_after if not k.startswith("_")])
    except Exception:
        disk_after_count = -1
    result = {
        "source": source,
        "before_nodes": before,
        "added": added,
        "deduped_in_mem": deduped,
        "after_nodes": after,
        "disk_nodes_before": disk_before_count,
        "disk_nodes_after": disk_after_count,
        "disk_delta": disk_after_count - disk_before_count,
        "mem_delta": after - before,
        "truth_ok": (added == (after - before) == (disk_after_count - disk_before_count)),
        "methods": methods,
        "elapsed_sec": round(time.time() - started, 2),
    }
    if not result["truth_ok"]:
        print(f"[FAIL] truth check: added={added} mem_delta={after-before} "
              f"disk_delta={disk_after_count - disk_before_count}")
    log = DATA / "world_model" / "seeding_log.json"
    log.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DONE] {json.dumps(result, ensure_ascii=False)}")
    print(f"[LOG] {log}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
