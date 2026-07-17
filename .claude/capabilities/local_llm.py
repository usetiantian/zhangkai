#!/usr/bin/env python3
"""
CC 本地模型工具 — 调用 LM Studio 的 Qwen3-VL-4B
用途：读大文件、看图、embedding、简单判断
节省 DeepSeek API token 消耗
"""

import sys, json, base64, urllib.request, io

# 强制 UTF-8 输出，解决 Windows 控制台乱码
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

LM_STUDIO = "http://127.0.0.1:1234/v1"
MODEL = "qwen/qwen3-vl-4b"
EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"

def llm_chat(prompt, max_tokens=1024):
    """调用本地 Qwen 模型"""
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }).encode()
    req = urllib.request.Request(f"{LM_STUDIO}/chat/completions", body,
        {"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=60)
    data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]

def summarize_file(filepath, max_chars=8000):
    """用本地模型总结文件内容，返回摘要"""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()[:max_chars]
    prompt = f"用中文简洁总结以下文件的核心内容，不超过200字：\n\n{content}"
    return llm_chat(prompt, max_tokens=300)

def answer_question(question, context=""):
    """用本地模型回答简单问题"""
    prompt = f"{context}\n\n问题：{question}\n\n用中文简短回答："
    return llm_chat(prompt, max_tokens=500)

def classify_text(text, categories):
    """用本地模型分类文本"""
    cat_list = ", ".join(categories)
    prompt = f"将以下文本分类为以下类别之一：{cat_list}。只输出类别名称，不要解释。\n\n文本：{text[:2000]}"
    return llm_chat(prompt, max_tokens=50)

def embed(text):
    """生成 embedding 向量"""
    body = json.dumps({
        "model": EMBED_MODEL,
        "input": text,
    }).encode()
    req = urllib.request.Request(f"{LM_STUDIO}/embeddings", body,
        {"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())
    return data["data"][0]["embedding"]

def read_image(filepath, question="描述这张图片"):
    """用 Qwen3-VL 看图"""
    with open(filepath, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()
    ext = filepath.split(".")[-1].lower()
    mime = f"image/{ext}" if ext in ("png","jpg","jpeg","webp","gif") else "image/png"
    
    body = json.dumps({
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}}
            ]
        }],
        "max_tokens": 500,
        "temperature": 0.1,
    }).encode()
    req = urllib.request.Request(f"{LM_STUDIO}/chat/completions", body,
        {"Content-Type": "application/json"})
    resp = urllib.request.urlopen(req, timeout=120)
    data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]

# ── CLI ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    
    if cmd == "summarize" and len(sys.argv) > 2:
        print(summarize_file(sys.argv[2]))
    
    elif cmd == "ask" and len(sys.argv) > 2:
        context = sys.argv[3] if len(sys.argv) > 3 else ""
        print(answer_question(sys.argv[2], context))
    
    elif cmd == "classify" and len(sys.argv) > 3:
        cats = sys.argv[3].split(",")
        print(classify_text(sys.argv[2], cats))
    
    elif cmd == "embed" and len(sys.argv) > 2:
        vec = embed(sys.argv[2])
        print(json.dumps({"dim": len(vec), "vec": vec[:10]}))  # 只输出前10维
    
    elif cmd == "image" and len(sys.argv) > 2:
        question = sys.argv[3] if len(sys.argv) > 3 else "描述这张图片"
        print(read_image(sys.argv[2], question))
    
    else:
        print("""CC 本地模型工具 — 节省 DeepSeek token
用法:
  python local_llm.py summarize <文件>       — 总结文件
  python local_llm.py ask <问题> [上下文]    — 简单问答
  python local_llm.py classify <文本> <类1,类2> — 分类
  python local_llm.py embed <文本>           — 生成embedding
  python local_llm.py image <图片> [问题]    — 看图分析""")
