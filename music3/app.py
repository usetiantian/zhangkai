#!/usr/bin/env python3
"""app.py -- music3 desktop app.

Starts the local backend, shows a small control panel, and opens the studio
UI in the default browser. Everything runs on the user's own machine: prompts
never leave the box except to the local ComfyUI.
"""
import json, os, sys, threading, webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))
if not getattr(sys, "frozen", False):
    sys.path.insert(0, HERE)

import doctor

APP_NAME = "music3 音乐工作室"
CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "music3")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
DEFAULT_CONFIG = {
    "comfy_url": "http://127.0.0.1:8188",
    "comfy_root": "",
    "port": 8899,
    "auto_open": True,
    "last_model_dir": "",
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        if os.path.isfile(CONFIG_PATH):
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("config save failed:", e)


def resource_dir(*parts):
    """Works both from source and from a PyInstaller bundle."""
    base = getattr(sys, "_MEIPASS", HERE)
    return os.path.join(base, *parts)


def start_server(port):
    import server as S
    S.STATIC = resource_dir("static")
    S.COMFY = load_config()["comfy_url"]
    httpd = S.ThreadingHTTPServer(("127.0.0.1", port), S.Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def probe_app(url, timeout=2):
    """Return the /api/health payload if a music3 instance is already serving url."""
    try:
        import urllib.request
        with urllib.request.urlopen(url.rstrip("/") + "/api/health", timeout=timeout) as r:
            d = json.loads(r.read().decode("utf-8"))
            return d if d.get("app") == "music3" else None
    except Exception:
        return None


def main():
    import tkinter as tk
    from tkinter import ttk

    cfg = load_config()
    try:
        want = int(cfg.get("port") or 0) or 8899
    except Exception:
        want = 8899

    # already running? just open it.
    existing = probe_app("http://127.0.0.1:%d" % want)
    if existing:
        webbrowser.open("http://127.0.0.1:%d" % want)
        return

    port = want
    try:
        start_server(port)
    except OSError:
        port = doctor.free_port()
        start_server(port)

    url = "http://127.0.0.1:%d" % port
    state = {"rep": None, "url": url}

    # remember the live URL so the user can get back to it later
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(os.path.join(CONFIG_DIR, "runtime.json"), "w", encoding="utf-8") as f:
            json.dump({"url": url, "port": port, "pid": os.getpid()}, f)
    except Exception:
        pass

    root = tk.Tk()
    root.title(APP_NAME)
    root.configure(bg="#0b0d14")
    root.resizable(False, False)
    root.geometry("480x560")

    def clear(w):
        for c in w.winfo_children():
            w.destroy()

    def label(parent, text, size=10, color="#8b93a8", bold=False):
        return tk.Label(parent, text=text, bg="#0b0d14", fg=color,
                        font=("Microsoft YaHei UI", size, "bold" if bold else "normal"),
                        justify="left", anchor="w", wraplength=430)

    def refresh():
        clear(body)
        rep = doctor.report(cfg["comfy_url"], cfg.get("comfy_root") or None)
        state["rep"] = rep

        label(body, "环境状态", 11, "#e8ecf5", True).pack(anchor="w", pady=(0, 8))

        rows = []
        rows.append(("ComfyUI 服务", "✓ 运行中" if rep["comfy_alive"] else "✗ 未连接",
                     "#38d39f" if rep["comfy_alive"] else "#ff5c72"))
        n = sum(1 for m in rep["models"] if m["present"])
        need = sum(1 for m in rep["models"] if m["key"] != "unet_lowvram")
        rows.append(("模型文件", "%d/%d 已就位" % (n, len(rep["models"])),
                     "#38d39f" if n >= need else "#ffb020"))
        if rep.get("gpu"):
            g = rep["gpu"]
            rows.append(("显卡", ("%s · %d GB" % (g["name"], g["vram_mb"] // 1024)) if g["ok"]
                         else ("未检测到 (%s)" % g["reason"]),
                         "#38d39f" if g["ok"] else "#ff5c72"))
        if rep.get("comfy_root"):
            rows.append(("ComfyUI 目录", rep["comfy_root"], "#8b93a8"))

        for k, v, c in rows:
            f = ttk.Frame(body)
            f.pack(fill="x", pady=3)
            ttk.Label(f, text=k, width=14, anchor="w").pack(side="left")
            tk.Label(f, text=v, bg="#0b0d14", fg=c,
                     font=("Microsoft YaHei UI", 10, "bold" if c != "#8b93a8" else "normal"),
                     anchor="w").pack(side="left", fill="x", expand=True)

        if not rep["comfy_alive"] or n < need:
            tk.Frame(body, height=12, bg="#0b0d14").pack()
            label(body, "还差一步：", 10, "#ffb020", True).pack(anchor="w")
            if not rep["comfy_alive"]:
                label(body, "• ComfyUI 没跑起来。启动 run_nvidia_gpu.bat，"
                            "或点下面「打开 ComfyUI 目录」。").pack(anchor="w")
            if n < need:
                label(body, "• 缺模型文件。共约 14 GB，从 hf-mirror.com/Comfy-Org/"
                            "MiniMax-Music3 下载放到对应目录。").pack(anchor="w")
            tk.Frame(body, height=10, bg="#0b0d14").pack()
            tk.Label(body, text="模型仓库（hf 镜像，国内直连更快）：\n%s\n\n官方源：\n%s"
                     % (rep["model_repo"], rep["model_repo_alt"]),
                     bg="#0b0d14", fg="#5d6579", font=("Consolas", 8),
                     justify="left", anchor="w").pack(anchor="w")

        tk.Frame(body, height=14, bg="#0b0d14").pack()
        label(body, "由 MiniMax-Music3 驱动", 9, "#5d6579").pack(anchor="w")

    body = tk.Frame(root, bg="#0b0d14", padx=20, pady=16)
    body.pack(fill="both", expand=True)

    style = ttk.Style()
    try:
        style.theme_use("clam")
        style.configure("TButton", padding=(10, 7))
    except Exception:
        pass

    btns = tk.Frame(root, bg="#0b0d14", padx=20, pady=14)
    btns.pack(fill="x")

    def open_ui():
        webbrowser.open(state["url"])

    def open_folder():
        r = state.get("rep")
        if r and r.get("comfy_root") and os.path.isdir(r["comfy_root"]):
            os.startfile(r["comfy_root"])  # noqa: S606 - Windows shell open
        else:
            os.startfile(os.path.expanduser("~"))

    tk.Button(btns, text="🎵  打开工作室", command=open_ui, bg="#7c5cff", fg="white",
              activebackground="#5b3ff0", relief="flat", bd=0, height=1,
              font=("Microsoft YaHei UI", 10, "bold"), cursor="hand2").pack(fill="x", pady=(0, 8))
    row = tk.Frame(btns, bg="#0b0d14")
    row.pack(fill="x")
    tk.Button(row, text="重新检测", command=refresh, bg="#1b1f2e", fg="#e8ecf5",
              relief="flat", bd=0, font=("Microsoft YaHei UI", 9), cursor="hand2").pack(side="left", fill="x", expand=True, padx=(0, 5))
    tk.Button(row, text="ComfyUI 目录", command=open_folder, bg="#1b1f2e", fg="#e8ecf5",
              relief="flat", bd=0, font=("Microsoft YaHei UI", 9), cursor="hand2").pack(side="left", fill="x", expand=True, padx=(5, 0))

    footer = tk.Frame(root, bg="#0b0d14")
    footer.pack(fill="x", padx=20, pady=(0, 12))
    tk.Label(footer, text="music3 音乐工作室 v1.0.0  ·  模型: MiniMax-Music3 (Community License)",
             bg="#0b0d14", fg="#3d4456", font=("Microsoft YaHei UI", 8)).pack(anchor="w")

    root.after(300, refresh)
    if cfg.get("auto_open"):
        root.after(900, open_ui)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        try:
            base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else HERE
            log = os.path.join(base, "music3-error.log")
            with open(log, "w", encoding="utf-8") as f:
                f.write(traceback.format_exc())
            print("启动失败，日志:", log)
        except Exception:
            traceback.print_exc()
        try:
            import tkinter.messagebox as mb
            mb.showerror("music3 启动失败", "详见同目录的 music3-error.log")
        except Exception:
            pass
