#!/usr/bin/env python
"""DeepSeek 极简 CLI - 省 token 版"""
import os, sys, json, requests

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-v4-flash"
SYSTEM_PROMPT = "简洁回答，不废话。"

def chat(messages):
    r = requests.post(
        f"{BASE_URL}/v1/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={"model": MODEL, "messages": messages, "stream": True},
        stream=True, timeout=120
    )
    for line in r.iter_lines():
        if line:
            s = line.decode().lstrip("data: ").strip()
            if s == "[DONE]": break
            try:
                delta = json.loads(s)["choices"][0]["delta"]
                if "content" in delta:
                    sys.stdout.write(delta["content"])
                    sys.stdout.flush()
            except: pass
    print()

def main():
    if not API_KEY:
        print("请设置 DEEPSEEK_API_KEY 环境变量"); sys.exit(1)
    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    while True:
        try:
            user = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nbye"); break
        if not user: continue
        if user.lower() in ("/exit", "/quit"): break
        if user.lower() == "/clear":
            history = [{"role": "system", "content": SYSTEM_PROMPT}]
            print("cleared"); continue
        history.append({"role": "user", "content": user})
        chat(history)
        history = [history[0]] + history[-40:]

if __name__ == "__main__":
    main()
