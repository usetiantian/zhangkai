# -*- coding: utf-8 -*-
"""CC 模型切换器(不依赖 Claude Code，坏了也能用它救回来)
用法:
  python cc_switch.py status   查看当前模式
  python cc_switch.py auto     自动切换模式: 智谱为主, 429自动落MiniMax (走本地代理)
  python cc_switch.py zhipu    直连智谱(急救用)
  python cc_switch.py minimax  直连MiniMax
每次修改前自动备份 settings.json
"""
import json, os, shutil, sys, time


def _load_keys():
    """密钥不写进代码：优先环境变量，其次 ~/.claude/cc_keys.json"""
    keys = {}
    p = os.path.join(os.path.expanduser("~"), ".claude", "cc_keys.json")
    try:
        with open(p, encoding="utf-8") as f:
            keys = json.load(f)
    except Exception:
        pass
    return keys


_KEYS = _load_keys()
SETTINGS = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
ZHIPU_TOKEN = os.environ.get("ZHIPU_API_KEY") or _KEYS.get("ZHIPU_TOKEN", "")
MINIMAX_TOKEN = os.environ.get("ANTHROPIC_AUTH_TOKEN") or _KEYS.get("MINIMAX_TOKEN", "")

def mode_of(d):
    url = d.get("env", {}).get("ANTHROPIC_BASE_URL", "")
    if "127.0.0.1:8790" in url: return "auto"
    if "bigmodel" in url: return "zhipu"
    if "minimaxi" in url: return "minimax"
    return "?"

def show():
    d = json.load(open(SETTINGS, encoding="utf-8"))
    e = d.get("env", {})
    print("当前模式: %s" % mode_of(d))
    print("  BASE_URL: %s" % e.get("ANTHROPIC_BASE_URL"))
    print("  MODEL:    %s" % e.get("ANTHROPIC_MODEL"))
    try:
        import requests
        r = requests.get("http://127.0.0.1:8790/__health", timeout=3)
        print("  本地代理: 运行中 %s" % r.json())
    except Exception:
        print("  本地代理: 未运行 (auto 模式需要它, 双击桌面 cc-auto.bat 启动)")

def _need(tok, name):
    if not tok:
        print("缺少 %s 密钥：设置环境变量 %s，或写入 %s"
              % (name, "ZHIPU_API_KEY" if name == "智谱" else "ANTHROPIC_AUTH_TOKEN",
                 os.path.join(os.path.expanduser("~"), ".claude", "cc_keys.json")))
        sys.exit(1)


def apply(mode):
    if mode in ("auto", "zhipu"):
        _need(ZHIPU_TOKEN, "智谱")
    if mode in ("auto", "minimax"):
        _need(MINIMAX_TOKEN, "MiniMax")
    d = json.load(open(SETTINGS, encoding="utf-8"))
    bak = SETTINGS + ".bak-switch-" + time.strftime("%Y%m%d_%H%M%S")
    shutil.copy2(SETTINGS, bak)
    e = d.get("env", {})
    e.pop("ANTHROPIC_API_KEY", None)
    if mode == "auto":
        e.update({"ANTHROPIC_BASE_URL": "http://127.0.0.1:8790",
                  "ANTHROPIC_AUTH_TOKEN": ZHIPU_TOKEN,
                  "ANTHROPIC_MODEL": "glm-5.3[1m]",
                  "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.3[1m]",
                  "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.3[1m]",
                  "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-5.3-flash[1m]"})
    elif mode == "zhipu":
        e.update({"ANTHROPIC_BASE_URL": "https://open.bigmodel.cn/api/anthropic",
                  "ANTHROPIC_AUTH_TOKEN": ZHIPU_TOKEN,
                  "ANTHROPIC_MODEL": "glm-5.3[1m]",
                  "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.3[1m]",
                  "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5.3[1m]",
                  "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-5.3-flash[1m]"})
    elif mode == "minimax":
        e.update({"ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
                  "ANTHROPIC_AUTH_TOKEN": MINIMAX_TOKEN,
                  "ANTHROPIC_MODEL": "MiniMax-M3[1m]",
                  "ANTHROPIC_DEFAULT_OPUS_MODEL": "MiniMax-M3[1m]",
                  "ANTHROPIC_DEFAULT_SONNET_MODEL": "MiniMax-M3[1m]",
                  "ANTHROPIC_DEFAULT_HAIKU_MODEL": "MiniMax-M3[1m]"})
    else:
        print("未知模式"); sys.exit(1)
    d["env"] = e
    json.dump(d, open(SETTINGS, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print("已切换到 %s 模式 (备份: %s)" % (mode, os.path.basename(bak)))
    print("重启 Claude Code 生效")

if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "status"
    if m == "status": show()
    else: apply(m)
