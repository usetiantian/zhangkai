"""minimax client (2026-07-30, 替 qiankun 老的 LMStudio client).

通过 mmx CLI (MiniMax 官方工具) 调用 MiniMax-M3:
  - mmx text chat --messages-file   (文本生成 + multimodal)
  - mmx vision describe --image      (图片理解)

API key 通过 mmx 自带管理 (mmx auth login), 不需要这里管.
"""
import subprocess
import json
import os
import subprocess as _sp
from tempfile import NamedTemporaryFile
from pathlib import Path

# mmx CLI 路径 (在 PATH 上, 但保险用绝对路径)
MMX = os.environ.get("MMX_PATH", r"C:\Users\87999\AppData\Roaming\npm\mmx.cmd")


def _run_mmx(args, timeout=120):
    """调 mmx CLI, 返回 parsed JSON or raw text."""
    cmd = [MMX] + args + ["--output", "json"]
    try:
        r = _sp.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise RuntimeError(f"mmx CLI not found at {MMX}, run 'npm i -g mmx' or set MMX_PATH")
    if r.returncode != 0:
        # mmx 失败时 JSON 也会写到 stdout, 试 parse
        out = (r.stdout or "") + (r.stderr or "")
        try:
            return json.loads(out)
        except Exception:
            raise RuntimeError(f"mmx failed (rc={r.returncode}): {out[:500]}")
    out = r.stdout.strip()
    if not out:
        return {}
    # mmx --output json 输出形如 {"role": "assistant", "content": "..."} 或更复杂
    try:
        return json.loads(out)
    except Exception:
        # 可能是普通 text
        return {"content": out}


def chat(messages, model="MiniMax-M3", max_tokens=4096, temperature=0.7, timeout=120):
    """通用 chat: messages 是 list[{role, content}] (content 可 str 或 list).

    支持多模态: content 可以是 [{"type":"text","text":"..."}, {"type":"image_url","image_url":{...}}]
    """
    # mmx 期望 --messages-file 传 JSON
    msg_file = NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    try:
        json.dump(messages, msg_file, ensure_ascii=False)
        msg_file.close()
        args = [
            "text", "chat",
            "--model", model,
            "--messages-file", msg_file.name,
            "--max-tokens", str(max_tokens),
            "--temperature", str(temperature),
        ]
        result = _run_mmx(args, timeout=timeout)
    finally:
        try: os.unlink(msg_file.name)
        except Exception: pass
    # mmx 输出: {"role": "assistant", "content": "..."} 或更复杂
    if isinstance(result, dict):
        return result.get("content") or result.get("text") or str(result)
    return str(result)


def vision_describe(image_path, prompt="描述这张K线图，包括趋势、支撑位、阻力位、成交量特征。", model=None, timeout=120):
    """mmx vision describe: 图片理解, 替代 LMStudio qwen3-vl-4b."""
    args = ["vision", "describe", "--image", str(image_path), "--prompt", prompt]
    if model:
        args += ["--model", model]
    result = _run_mmx(args, timeout=timeout)
    if isinstance(result, dict):
        return result.get("content") or result.get("description") or str(result)
    return str(result)


def build_vision_messages(text_prompt, image_path):
    """构造 multimodal messages 数组 (vision + text), 给 chat() 用."""
    import base64
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    # 推断 mime
    ext = Path(image_path).suffix.lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "webp": "image/webp", "gif": "image/gif"}.get(ext.lstrip("."), "image/png")
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": text_prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ],
        }
    ]


if __name__ == "__main__":
    # 自测
    print("=== text chat ===")
    r = chat([{"role": "user", "content": "用一句话回答: 1+1=?"}], max_tokens=50)
    print(f"  -> {r}")
    print()
    print("=== vision describe ===")
    # 找一张测试图 (qiankun charts/ 里有)
    charts = list(Path(r"C:\Users\87999\claude-workspace\qiankun\charts").glob("*.png"))
    if charts:
        r = vision_describe(str(charts[0]), prompt="描述这张K线图")
        print(f"  -> {r[:300]}")
