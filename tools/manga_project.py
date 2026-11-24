"""漫剧工程目录管理：建集目录、归档素材、生成进度表。

目录规范:
  manga/<作品名>/
    README.md              总说明 + 进度表
    00_素材/
      定妆图/              角色定妆参考图
      音色/                克隆出来的角色音色
      小说原文/            清洗过的章节原文
      定妆.txt             风格 + 人物 + 场景圣经（唯一事实源）
    01_第01-10集/
      EP01_标题/
        01_分镜任务书.txt
        02_官方分镜.txt
        03_段表.json
        04_APIprompt.json
        05_成片.mp4
        06_抽帧/
"""
import io
import json
import os
import re
import shutil
import sys

ROOT = "manga"


def group_dir(ep_no):
    g = (ep_no - 1) // 10 + 1
    a = (g - 1) * 10 + 1
    b = g * 10
    return "%02d_第%02d-%02d集" % (g, a, b)


def ep_dir(work, ep_no, title):
    return os.path.join(ROOT, work, group_dir(ep_no), "EP%02d_%s" % (ep_no, title))


def new_episode(work, ep_no, title, chapter_text=None):
    d = ep_dir(work, ep_no, title)
    for sub in ("", "06_抽帧"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    if chapter_text:
        io.open(os.path.join(d, "00_章节原文.txt"), "w", encoding="utf-8").write(chapter_text)
    print("已建:", d)
    return d


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    cmd = args[0]
    if cmd == "new":
        work, ep_no, title = args[1], int(args[2]), args[3]
        src = args[4] if len(args) > 4 else None
        text = io.open(src, encoding="utf-8").read() if src else None
        new_episode(work, ep_no, title, text)
    elif cmd == "dir":
        work, ep_no, title = args[1], int(args[2]), args[3]
        print(ep_dir(work, ep_no, title))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
