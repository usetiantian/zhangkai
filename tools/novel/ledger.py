"""生成一本新书的写作台账骨架（空白模板）。

用法: python tools/novel/ledger.py <书名> <目标目录> [--chapters 200] [--vols 8]
"""
import io
import os
import sys

TPL = """# 《{title}》写作台账

> 每写完一章立即更新本表。这是这本书唯一的事实源。
> 生成工具：tools/novel/ledger.py

## 一、主角档案

**{protagonist}**，{age}，{origin}。{tagline}

- 出身：
- 家产：
- 他会的活：
- 不能说的向往：
- 名字来历：

## 二、境界/力量体系（每一阶都要写代价）

| 阶 | 名 | 门槛 | 说明 | 代价 |
|---|---|---|---|---|
| 一 |  |  |  |  |
| 二 |  |  |  |  |
| 三 |  |  |  |  |

## 三、地图

1. ：

## 四、技能与器物

| 名称 | 说明 | 代价 |
|---|---|---|
|  |  |  |

## 五、女主/主要配角

- ：

## 六、反派与阴谋线

| 人物 | 身份 | 目标 | 与主角的关系 |
|---|---|---|---|
|  |  |  |  |

## 七、伏笔追踪

| # | 伏笔 | 埋（章） | 回收（章） | 状态 |
|---|---|---|---|---|
| 1 |  |  |  | ⬜ |

## 八、爽点公式（本书记法）

1. 解法型：
2. 识破型：
3. 有人接住型：
4. 账本型：
5. 器物型：

**禁**：境界压制、对方下跪、围观者惊叹。

## 九、卷纲

**第一卷（1-{chapters}章）**：

## 十、章节进度

| 章 | 标题 | 字数 | 评级 | 状态 | 一句话 |
|---|---|---|---|---|---|
| 01 |  |  |  | ⬜ |  |

## 十一、角色状态推进（每章回写）

| 章 | 角色 | 状态变化 | 代价 |
|---|---|---|---|
"""


def main():
    args = sys.argv[1:]
    title = args[0]
    outdir = args[1]
    chapters = 200
    prot = "主角"
    age = "？"
    origin = "？"
    tagline = ""
    for i, a in enumerate(args):
        if a == "--chapters":
            chapters = int(args[i + 1])
        if a == "--protagonist":
            prot = args[i + 1]
        if a == "--age":
            age = args[i + 1]
        if a == "--origin":
            origin = args[i + 1]
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, "00_写作台账.md")
    if os.path.exists(p):
        print("已存在，不覆盖:", p)
        return
    io.open(p, "w", encoding="utf-8").write(TPL.format(
        title=title, chapters=chapters, protagonist=prot, age=age, origin=origin, tagline=tagline))
    print("已生成:", p)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
