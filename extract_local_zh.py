# -*- coding: utf-8 -*-
"""CC老师 本地中文数据提取器 — 知识库+小说+七猫 -> 训练数据 (v18.5n)

来源:
  1. D:\node\知识库原始数据 — 10.6M字 (AI/数学/物理/历史/哲学/经济...)
  2. D:\node\小说 — 1.0M字 (12部经典网文)
  3. D:\node\阅读笔记\七猫免费小说 — 1.2M字 (网文素材+写作练习+原创)

输出:
  - .nexus/nexus_agent/zh_corpus/*.py (训练管道自动读取)
  - .nexus/data/wm_v2/wiki_zh_texts.json
"""

import json
import re
import sys
import io
import time
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def log(msg):
    print(msg, flush=True)

NEXUS_HOME = Path.home() / ".nexus"
PY_DIR = NEXUS_HOME / "nexus_agent" / "zh_corpus"
JSON_OUT = NEXUS_HOME / "data" / "wm_v2" / "wiki_zh_texts.json"

SOURCES = [
    ("知识库", Path(r"D:\node\知识库原始数据"), ["*.md"]),
    ("小说", Path(r"D:\node\小说"), ["*.txt"]),
    ("七猫", Path(r"D:\node\阅读笔记\七猫免费小说"), ["*.txt", "*.md"]),
]

CHUNK_SIZE = 3000  # 每块最大字符数

def clean_text(text):
    """基础清洗。"""
    # 移除过多空白
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    text = re.sub(r'[ \t]{3,}', '  ', text)
    # 移除纯符号行
    lines = [l for l in text.split('\n') if len(l.strip()) > 2 or l.strip() == '']
    text = '\n'.join(lines)
    return text.strip()

def chunk_text(text, max_chars=CHUNK_SIZE):
    """将长文本切成适合训练的块。"""
    chunks = []
    while len(text) > max_chars:
        # 在句子边界切割
        split_at = text.rfind('\n', 0, max_chars)
        if split_at < max_chars // 2:
            split_at = text.rfind('。', 0, max_chars)
        if split_at < max_chars // 2:
            split_at = max_chars
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        chunks.append(text)
    return chunks

def extract_all():
    """提取所有中文数据。"""
    all_articles = []
    
    for src_name, src_path, patterns in SOURCES:
        if not src_path.exists():
            log(f"  [SKIP] {src_name}: 路径不存在")
            continue
        
        log(f"\n[提取] {src_name}")
        src_files = 0
        src_chars = 0
        
        for pattern in patterns:
            for f in sorted(src_path.rglob(pattern)):
                try:
                    text = f.read_text(encoding='utf-8', errors='replace')
                    text = clean_text(text)
                    if len(text) < 50:
                        continue
                    
                    # 切块
                    chunks = chunk_text(text)
                    for i, chunk in enumerate(chunks):
                        chunk_name = f"{src_name}_{f.stem[:30]}"
                        if len(chunks) > 1:
                            chunk_name += f"_p{i+1}"
                        
                        all_articles.append({
                            "title": chunk_name,
                            "text": chunk,
                            "length": len(chunk),
                            "source": f"local-{src_name}",
                            "file": str(f),
                            "fetched_at": time.time(),
                        })
                    
                    src_files += 1
                    src_chars += len(text)
                    
                    if src_files % 50 == 0:
                        log(f"  ... {src_files} 文件, {src_chars:,} 字")
                        
                except Exception as e:
                    pass  # 跳过无法读取的文件
        
        log(f"  >> {src_name}: {src_files} 文件, {src_chars:,} 字")
    
    return all_articles

def save_all(articles):
    """保存为 JSON 和 .py 文件。"""
    # 清空旧的 zh_corpus
    PY_DIR.mkdir(parents=True, exist_ok=True)
    for old in PY_DIR.glob("zh_*.py"):
        old.unlink()
    
    # 保存 .py 文件
    for i, a in enumerate(articles):
        title = re.sub(r'[\\/:*?"<>|]', '_', a["title"])[:50]
        fname = f"zh_{i:05d}_{title}.py"
        content = f'# -*- coding: utf-8 -*-\n"""\n{a["text"]}\n"""\n'
        try:
            (PY_DIR / fname).write_text(content, encoding='utf-8')
        except Exception as e:
            log(f"  [WARN] 写入失败 {fname}: {e}")
    
    # 保存 JSON
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(JSON_OUT, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    
    n_py = len(list(PY_DIR.glob("zh_*.py")))
    return n_py

def main():
    log("=" * 55)
    log("  CC老师 本地中文数据提取器")
    log("=" * 55)
    
    # 提取
    articles = extract_all()
    
    # 统计
    total_chars = sum(a["length"] for a in articles)
    sources = {}
    for a in articles:
        s = a.get("source", "?")
        sources[s] = sources.get(s, 0) + 1
    
    log(f"\n[统计]")
    log(f"  总块数: {len(articles)}")
    log(f"  总字数: {total_chars:,}")
    for s, n in sorted(sources.items()):
        chars = sum(a["length"] for a in articles if a.get("source") == s)
        log(f"  {s}: {n} 块, {chars:,} 字")
    
    # 保存
    log(f"\n[保存]")
    n_py = save_all(articles)
    log(f"  .py 文件: {n_py} -> {PY_DIR}")
    log(f"  JSON:     {JSON_OUT}")
    log(f"\n  完成! 训练管道将读取 {n_py} 个中文语料文件。")

if __name__ == "__main__":
    main()
