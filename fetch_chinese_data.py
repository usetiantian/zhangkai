# -*- coding: utf-8 -*-
"""CC老师的中文数据下载脚本 — Wikipedia ZH + 技术文档 (v18.5n)

用法: python fetch_chinese_data.py
输出: .nexus/data/wm_v2/wiki_zh_texts.json (会被训练管道读取)
"""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import io
from pathlib import Path

# 修复 Windows GBK 终端编码
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# -- 配置 --
NEXUS_HOME = Path(os.environ.get("NEXUS_HOME", Path.home() / ".nexus"))
OUTPUT_FILE = NEXUS_HOME / "data" / "wm_v2" / "wiki_zh_texts.json"
TEXT_DIR = NEXUS_HOME / "data" / "external" / "zh_texts" / "2026-07-11"
UA = "Nexus/18.5n (CC-Trainer; Chinese data collection)"

# -- Wikipedia API --
WIKI_API = "https://zh.wikipedia.org/w/api.php"

def fetch_wikipedia_articles(titles: list, delay: float = 1.5) -> list:
    """通过 MediaWiki API 批量获取中文维基百科文章。"""
    articles = []
    for i, title in enumerate(titles):
        try:
            params = {
                "action": "query",
                "format": "json",
                "titles": title,
                "prop": "extracts",
                "exintro": 0,       # 全文，非仅摘要
                "explaintext": 1,   # 纯文本
                "exlimit": 1,
            }
            url = WIKI_API + "?" + urllib.parse.urlencode(params)
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            
            pages = data.get("query", {}).get("pages", {})
            for page_id, page in pages.items():
                text = page.get("extract", "")
                if text and len(text) > 200:
                    articles.append({
                        "title": page.get("title", title),
                        "page_id": page_id,
                        "text": text,
                        "length": len(text),
                        "source": "zh.wikipedia.org",
                        "fetched_at": time.time(),
                    })
                    print(f"  [{i+1}/{len(titles)}] [OK] {page.get('title', title)[:50]} ({len(text)}字)")
                else:
                    print(f"  [{i+1}/{len(titles)}] [WARN]  {title[:50]} — 内容太短或不存在")
        except Exception as e:
            print(f"  [{i+1}/{len(titles)}] [FAIL] {title[:50]} — {e}")
        
        time.sleep(delay)  # 礼貌限速
    
    return articles

def fetch_wikipedia_category(category: str, limit: int = 30, delay: float = 1.5) -> list:
    """获取某个分类下的文章标题列表，然后下载内容。"""
    print(f"\n[目录] 分类: {category}")
    try:
        # 获取分类成员
        params = {
            "action": "query",
            "format": "json",
            "list": "categorymembers",
            "cmtitle": f"Category:{category}",
            "cmlimit": min(limit, 50),
            "cmtype": "page",
        }
        url = WIKI_API + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        
        titles = [m["title"] for m in data.get("query", {}).get("categorymembers", [])]
        print(f"  找到 {len(titles)} 个页面标题")
        return fetch_wikipedia_articles(titles, delay)
    except Exception as e:
        print(f"  [FAIL] 分类获取失败: {e}")
        return []

# -- arXiv 中文摘要 --
def fetch_arxiv_chinese(query: str = "machine learning", max_results: int = 20) -> list:
    """从 arXiv 获取论文摘要（英文也可作为训练数据）。"""
    articles = []
    try:
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        url = "http://export.arxiv.org/api/query?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as resp:
            xml = resp.read().decode("utf-8")
        
        # 简单解析 XML（不引入额外依赖）
        entries = re.findall(r'<entry>(.*?)</entry>', xml, re.DOTALL)
        for entry in entries:
            title_m = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
            summary_m = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
            if title_m and summary_m:
                title = re.sub(r'\s+', ' ', title_m.group(1).strip())
                summary = re.sub(r'\s+', ' ', summary_m.group(1).strip())
                if len(summary) > 200:
                    articles.append({
                        "title": title,
                        "text": f"{title}\n\n{summary}",
                        "length": len(summary),
                        "source": "arxiv.org",
                        "fetched_at": time.time(),
                    })
            if len(articles) >= max_results:
                break
        print(f"  arXiv '{query}': {len(articles)} 篇")
    except Exception as e:
        print(f"  arXiv 失败: {e}")
    return articles

# -- Python 中文文档 --
def fetch_python_zh_docs() -> list:
    """获取 Python 官方中文文档部分内容。"""
    articles = []
    pages = [
        ("Python 语言参考", "https://docs.python.org/zh-cn/3/reference/index.html"),
        ("Python 标准库", "https://docs.python.org/zh-cn/3/library/index.html"),
        ("Python 教程", "https://docs.python.org/zh-cn/3/tutorial/index.html"),
    ]
    # 使用 raw .rst 文件（中文翻译仓库）
    raw_urls = [
        ("Python 数据模型", "https://raw.githubusercontent.com/python/python-docs-zh-cn/3.12/reference/datamodel.rst"),
        ("Python 表达式", "https://raw.githubusercontent.com/python/python-docs-zh-cn/3.12/reference/expressions.rst"),
        ("Python 简单语句", "https://raw.githubusercontent.com/python/python-docs-zh-cn/3.12/reference/simple_stmts.rst"),
        ("Python 内置函数", "https://raw.githubusercontent.com/python/python-docs-zh-cn/3.12/library/functions.rst"),
        ("Python 内置类型", "https://raw.githubusercontent.com/python/python-docs-zh-cn/3.12/library/stdtypes.rst"),
        ("Python 数学模块", "https://raw.githubusercontent.com/python/python-docs-zh-cn/3.12/library/math.rst"),
        ("Python itertools", "https://raw.githubusercontent.com/python/python-docs-zh-cn/3.12/library/itertools.rst"),
        ("Python functools", "https://raw.githubusercontent.com/python/python-docs-zh-cn/3.12/library/functools.rst"),
        ("Python collections", "https://raw.githubusercontent.com/python/python-docs-zh-cn/3.12/library/collections.rst"),
        ("Python typing", "https://raw.githubusercontent.com/python/python-docs-zh-cn/3.12/library/typing.rst"),
    ]
    
    for name, url in raw_urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            # 清理 RST 标记
            text = re.sub(r'\.\.\s+[a-z-]+::.*', '', raw)  # 指令
            text = re.sub(r':\w+:`[^`]*`', '', text)       # 角色
            text = re.sub(r'`[^`]*`', '', text)             # 内联代码
            text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # 粗体
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = text.strip()
            if len(text) > 500:
                articles.append({
                    "title": name,
                    "text": text[:10000],
                    "length": min(len(text), 10000),
                    "source": "python-docs-zh-cn",
                    "fetched_at": time.time(),
                })
                print(f"  [OK] {name} ({min(len(text), 10000)}字)")
            else:
                print(f"  [WARN]  {name} — 内容不足")
        except Exception as e:
            print(f"  [FAIL] {name} — {e}")
        time.sleep(0.8)
    
    return articles

# ===============================================
# 主流程
# ===============================================

def main():
    print("=" * 60)
    print("  CC老师中文数据采集器 v18.5n")
    print("=" * 60)
    
    all_articles = []
    
    # -- 1. Wikipedia 中文: 编程/技术类 --
    print("\n[搜索] [1/5] Wikipedia 中文 — 编程与技术")
    tech_titles = [
        "Python",
        "机器学习",
        "深度学习",
        "人工神经网络",
        "自然语言处理",
        "计算机视觉",
        "强化学习",
        "Transformer模型",
        "GPT-4",
        "反向传播算法",
        "卷积神经网络",
        "循环神经网络",
        "生成对抗网络",
        "自编码器",
        "注意力机制",
        "迁移学习",
        "梯度下降法",
        "损失函数",
        "激活函数",
        "过拟合",
        "正则化_(数学)",
        "贝叶斯推断",
        "马尔可夫链",
        "蒙特卡罗方法",
        "线性回归",
        "逻辑回归",
        "支持向量机",
        "决策树",
        "随机森林",
        "K-均值算法",
    ]
    articles = fetch_wikipedia_articles(tech_titles, delay=1.2)
    all_articles.extend(articles)
    print(f"  → 已收集 {len(articles)} 篇技术文章")
    
    # -- 2. Wikipedia 中文: 数学/科学类 --
    print("\n[搜索] [2/5] Wikipedia 中文 — 数学与科学")
    math_titles = [
        "微积分",
        "线性代数",
        "概率论",
        "数理统计",
        "信息论",
        "图论",
        "组合数学",
        "数论",
        "拓扑学",
        "群论",
        "微分方程",
        "最优化",
        "数值分析",
        "傅里叶变换",
        "拉普拉斯变换",
        "矩阵",
        "特征值和特征向量",
        "奇异值分解",
        "主成分分析",
        "熵_(信息论)",
        "KL散度",
        "交叉熵",
        "物理学",
        "量子力学",
        "统计力学",
    ]
    articles = fetch_wikipedia_articles(math_titles, delay=1.0)
    all_articles.extend(articles)
    print(f"  → 已收集 {len(articles)} 篇数学文章")
    
    # -- 3. Wikipedia 中文: 计算机科学 --
    print("\n[搜索] [3/5] Wikipedia 中文 — 计算机科学")
    cs_titles = [
        "算法",
        "数据结构",
        "时间复杂度",
        "排序算法",
        "哈希表",
        "二叉树",
        "动态规划",
        "贪心算法",
        "分治法",
        "数据库",
        "SQL",
        "NoSQL",
        "操作系统",
        "Linux",
        "计算机网络",
        "TCP/IP协议族",
        "HTTP",
        "编译器",
        "编程语言",
        "C语言",
        "Java",
        "JavaScript",
        "Rust_(编程语言)",
        "Go_(编程语言)",
        "Git",
        "Docker",
        "Kubernetes",
        "REST",
        "API",
        "软件工程",
    ]
    articles = fetch_wikipedia_articles(cs_titles, delay=1.0)
    all_articles.extend(articles)
    print(f"  → 已收集 {len(articles)} 篇CS文章")
    
    # -- 4. Wikipedia 中文: 通用类 --
    print("\n[搜索] [4/5] Wikipedia 中文 — 通用知识")
    general_titles = [
        "中国历史",
        "中国古代四大发明",
        "人工智能",
        "大数据",
        "云计算",
        "物联网",
        "区块链",
        "5G",
        "量子计算",
        "机器人",
        "自动驾驶汽车",
        "虚拟现实",
        "增强现实",
        "元宇宙",
        "可再生能源",
        "太阳系",
        "银河系",
        "DNA",
        "基因编辑",
        "进化论",
    ]
    articles = fetch_wikipedia_articles(general_titles, delay=1.0)
    all_articles.extend(articles)
    print(f"  → 已收集 {len(articles)} 篇通用文章")
    
    # -- 5. Python 中文文档 --
    print("\n[搜索] [5/5] Python 中文官方文档")
    docs = fetch_python_zh_docs()
    all_articles.extend(docs)
    print(f"  → 已收集 {len(docs)} 篇文档")
    
    # -- 保存 --
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)
    
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    
    total_chars = sum(a["length"] for a in all_articles)
    print(f"\n{'='*60}")
    print(f"  [统计] 采集完成!")
    print(f"  文章数: {len(all_articles)}")
    print(f"  总字数: {total_chars:,}")
    print(f"  输出:   {OUTPUT_FILE}")
    print(f"  文本:   {TEXT_DIR}")
    print(f"{'='*60}")
    
    # 保存摘要
    summary = {
        "date": "2026-07-11",
        "total_articles": len(all_articles),
        "total_chars": total_chars,
        "sources": {},
    }
    for a in all_articles:
        src = a.get("source", "unknown")
        summary["sources"][src] = summary["sources"].get(src, 0) + 1
    
    summary_file = TEXT_DIR / "summary.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    return all_articles

if __name__ == "__main__":
    main()
