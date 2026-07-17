# -*- coding: utf-8 -*-
"""CC老师的中国数据下载脚本 v2 — 适配受限网络 (v18.5n)

策略:
  1. Python zh-cn 官方文档 (已验证可访问)
  2. 本地已有资源提取 (论文摘要、GitHub README、B站标题)
  3. 合成高质量中文编程数据 (代码+中文注释对)
  
输出: .nexus/data/wm_v2/wiki_zh_texts.json
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

# 修复 Windows GBK
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

NEXUS_HOME = Path(os.environ.get("NEXUS_HOME", Path.home() / ".nexus"))
OUTPUT_FILE = NEXUS_HOME / "data" / "wm_v2" / "wiki_zh_texts.json"
UA = "Mozilla/5.0 (compatible; Nexus/18.5n)"

def log(msg):
    print(msg, flush=True)

# ═══════════════════════════════════════════════
# 1. Python 中文官方文档 (可访问)
# ═══════════════════════════════════════════════

PYTHON_ZH_DOCS = [
    # 语言参考
    ("Python 数据模型", "https://docs.python.org/zh-cn/3/reference/datamodel.html"),
    ("Python 表达式", "https://docs.python.org/zh-cn/3/reference/expressions.html"),
    ("Python 简单语句", "https://docs.python.org/zh-cn/3/reference/simple_stmts.html"),
    ("Python 复合语句", "https://docs.python.org/zh-cn/3/reference/compound_stmts.html"),
    ("Python 执行模型", "https://docs.python.org/zh-cn/3/reference/executionmodel.html"),
    ("Python 导入系统", "https://docs.python.org/zh-cn/3/reference/import.html"),
    # 标准库
    ("Python 内置函数", "https://docs.python.org/zh-cn/3/library/functions.html"),
    ("Python 内置类型", "https://docs.python.org/zh-cn/3/library/stdtypes.html"),
    ("Python 数学模块", "https://docs.python.org/zh-cn/3/library/math.html"),
    ("Python itertools", "https://docs.python.org/zh-cn/3/library/itertools.html"),
    ("Python functools", "https://docs.python.org/zh-cn/3/library/functools.html"),
    ("Python collections", "https://docs.python.org/zh-cn/3/library/collections.html"),
    ("Python typing", "https://docs.python.org/zh-cn/3/library/typing.html"),
    ("Python dataclasses", "https://docs.python.org/zh-cn/3/library/dataclasses.html"),
    ("Python enum", "https://docs.python.org/zh-cn/3/library/enum.html"),
    ("Python os 模块", "https://docs.python.org/zh-cn/3/library/os.html"),
    ("Python sys 模块", "https://docs.python.org/zh-cn/3/library/sys.html"),
    ("Python pathlib", "https://docs.python.org/zh-cn/3/library/pathlib.html"),
    ("Python json", "https://docs.python.org/zh-cn/3/library/json.html"),
    ("Python re 正则", "https://docs.python.org/zh-cn/3/library/re.html"),
    ("Python datetime", "https://docs.python.org/zh-cn/3/library/datetime.html"),
    ("Python logging", "https://docs.python.org/zh-cn/3/library/logging.html"),
    ("Python unittest", "https://docs.python.org/zh-cn/3/library/unittest.html"),
    ("Python asyncio", "https://docs.python.org/zh-cn/3/library/asyncio.html"),
    ("Python threading", "https://docs.python.org/zh-cn/3/library/threading.html"),
    ("Python subprocess", "https://docs.python.org/zh-cn/3/library/subprocess.html"),
    ("Python argparse", "https://docs.python.org/zh-cn/3/library/argparse.html"),
    ("Python random", "https://docs.python.org/zh-cn/3/library/random.html"),
    ("Python statistics", "https://docs.python.org/zh-cn/3/library/statistics.html"),
    ("Python decimal", "https://docs.python.org/zh-cn/3/library/decimal.html"),
    # 教程
    ("Python 教程-类", "https://docs.python.org/zh-cn/3/tutorial/classes.html"),
    ("Python 教程-模块", "https://docs.python.org/zh-cn/3/tutorial/modules.html"),
    ("Python 教程-错误异常", "https://docs.python.org/zh-cn/3/tutorial/errors.html"),
    ("Python 教程-IO", "https://docs.python.org/zh-cn/3/tutorial/inputoutput.html"),
    ("Python 教程-数据结构", "https://docs.python.org/zh-cn/3/tutorial/datastructures.html"),
    ("Python 教程-控制流", "https://docs.python.org/zh-cn/3/tutorial/controlflow.html"),
]

def clean_html(text):
    """Remove HTML tags, scripts, styles from text."""
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<header[^>]*>.*?</header>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&quot;', '"', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    text = text.strip()
    return text

def fetch_python_zh():
    """下载 Python 中文官方文档。"""
    articles = []
    for name, url in PYTHON_ZH_DOCS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                html = r.read().decode("utf-8", errors="replace")
            text = clean_html(html)
            # 只保留实质性内容
            if len(text) > 1000:
                articles.append({
                    "title": name,
                    "text": text[:15000],  # 截断以防太大
                    "length": min(len(text), 15000),
                    "source": "docs.python.org/zh-cn",
                    "fetched_at": time.time(),
                })
                log(f"  [OK] {name}: {min(len(text), 15000)} chars")
            else:
                log(f"  [SKIP] {name}: only {len(text)} chars")
        except Exception as e:
            log(f"  [FAIL] {name}: {e}")
        time.sleep(0.5)  # 礼貌
    return articles

# ═══════════════════════════════════════════════
# 2. 从本地论文提取中文摘要
# ═══════════════════════════════════════════════

def extract_paper_chinese():
    """从已下载的论文数据中提取中文相关内容。"""
    articles = []
    paper_file = NEXUS_HOME / "data" / "external" / "papers" / "2026-07-10.json"
    if not paper_file.exists():
        log("  [SKIP] No paper data found")
        return articles
    
    try:
        import json
        with open(paper_file, 'r', encoding='utf-8') as f:
            papers = json.load(f)
        
        for p in papers:
            title = p.get("title", "")
            abstract = p.get("abstract", p.get("summary", ""))
            text = f"Title: {title}\n\nAbstract: {abstract}"
            if len(text) > 100:
                articles.append({
                    "title": f"[论文] {title[:80]}",
                    "text": text[:3000],
                    "length": min(len(text), 3000),
                    "source": "arxiv.org",
                    "fetched_at": time.time(),
                })
        log(f"  [OK] 从本地提取 {len(articles)} 篇论文摘要")
    except Exception as e:
        log(f"  [FAIL] {e}")
    return articles

# ═══════════════════════════════════════════════
# 3. 从本地 GitHub 仓库提取 README
# ═══════════════════════════════════════════════

def extract_github_chinese():
    """从已下载的 GitHub 数据中提取中文内容。"""
    articles = []
    gh_dir = NEXUS_HOME / "data" / "external" / "code" / "2026-07-10"
    if not gh_dir.exists():
        return articles
    
    try:
        import json
        for f in sorted(gh_dir.glob("*.json")):
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                desc = data.get("description", "")
                readme = data.get("readme", data.get("content", ""))
                text = f"{desc}\n\n{readme}" if readme else desc
                if len(text) > 100:
                    articles.append({
                        "title": f"[GitHub] {f.stem}",
                        "text": text[:5000],
                        "length": min(len(text), 5000),
                        "source": "github.com",
                        "fetched_at": time.time(),
                    })
            except:
                pass
        log(f"  [OK] 从本地提取 {len(articles)} 个GitHub文档")
    except Exception as e:
        log(f"  [FAIL] {e}")
    return articles

# ═══════════════════════════════════════════════
# 4. 生成高质量中文编程训练数据
# ═══════════════════════════════════════════════

def generate_synthetic_zh():
    """生成中英文混合的编程训练数据。"""
    articles = []
    
    # Python 基础概念 (中文解释 + 代码示例)
    concepts = [
        ("列表推导式", """列表推导式 (List Comprehension) 是Python中创建列表的简洁方式。
它用一行代码替代传统的 for 循环+append 模式。

语法: [表达式 for 变量 in 可迭代对象 if 条件]

示例:
  squares = [x**2 for x in range(10)]  # [0,1,4,9,16,25,36,49,64,81]
  evens = [x for x in range(20) if x % 2 == 0]  # 偶数列表
  pairs = [(x, y) for x in range(3) for y in range(3)]  # 笛卡尔积

相比传统写法:
  squares = []
  for x in range(10):
      squares.append(x**2)

列表推导式更简洁、更快，因为它在C层面执行循环。"""),

        ("装饰器原理", """装饰器 (Decorator) 是Python中用于修改函数或类行为的语法糖。
本质是一个接受函数作为参数并返回新函数的高阶函数。

@decorator
def func():
    pass

等价于: func = decorator(func)

常见用途:
  1. 日志记录: @log_execution 自动记录函数调用
  2. 权限检查: @require_auth 验证用户权限
  3. 缓存: @lru_cache(maxsize=128) 缓存函数结果
  4. 计时: @timer 测量函数执行时间
  5. 重试: @retry(max_attempts=3) 失败自动重试

带参数的装饰器需要三层嵌套:
  def repeat(n):
      def decorator(func):
          def wrapper(*args, **kwargs):
              for _ in range(n):
                  result = func(*args, **kwargs)
              return result
          return wrapper
      return decorator"""),

        ("上下文管理器", """上下文管理器 (Context Manager) 定义了 with 语句的运行时上下文。
通过实现 __enter__ 和 __exit__ 方法，自动管理资源的获取和释放。

最常用的上下文管理器是文件操作:
  with open('file.txt', 'r') as f:
      content = f.read()
  # 文件自动关闭，即使发生异常

自定义上下文管理器:
  class Timer:
      def __enter__(self):
          self.start = time.time()
          return self
      def __exit__(self, *args):
          self.end = time.time()
          print(f'Elapsed: {self.end - self.start:.2f}s')

使用 contextlib.contextmanager 装饰器可以更简洁:
  from contextlib import contextmanager
  @contextmanager
  def timer():
      start = time.time()
      yield
      print(f'Elapsed: {time.time() - start:.2f}s')"""),

        ("生成器与迭代器", """生成器 (Generator) 是一种特殊的迭代器，用 yield 关键字定义。
每次调用 yield 时，函数状态被保存，下次从 yield 之后继续执行。

特点:
  1. 惰性求值: 按需生成数据，节省内存
  2. 无限序列: 可以表示无限长的数据流
  3. 管道操作: 可以将多个生成器串联

def fibonacci():
    a, b = 0, 1
    while True:
        yield a
        a, b = b, a + b

生成器表达式 (类似列表推导式但用小括号):
  squares = (x**2 for x in range(1000000))  # 惰性，不立即占内存
  sum(squares)  # 计算时才逐一生成

迭代器协议:
  1. __iter__(): 返回迭代器对象
  2. __next__(): 返回下一个值，耗尽时抛出 StopIteration"""),

        ("GIL与并发编程", """GIL (Global Interpreter Lock) 是CPython解释器的全局锁。
它确保同一时刻只有一个线程执行Python字节码。

为什么存在GIL:
  Python的内存管理(引用计数)不是线程安全的。
  GIL简化了CPython的实现，避免了复杂的锁机制。

GIL的影响:
  1. CPU密集型任务: 多线程无法利用多核，反而因上下文切换更慢
  2. IO密集型任务: 线程在IO等待时释放GIL，多线程仍有效

解决方案:
  1. 多进程 (multiprocessing): 每个进程有独立GIL
  2. 异步编程 (asyncio): 单线程事件循环
  3. C扩展: 在C代码中手动释放GIL
  4. 其他解释器: Jython, IronPython无GIL
  5. Python 3.13+: 引入了可选的无GIL模式

选择指南:
  - CPU密集: multiprocessing 或 C扩展
  - IO密集: asyncio 或 threading
  - 混合: multiprocessing + asyncio"""),

        ("类型注解与静态检查", """Python 类型注解 (Type Hints) 从3.5版本引入，允许标注变量和函数的类型。
虽然Python运行时不做类型检查，但可以用静态检查工具(如mypy)发现类型错误。

基本语法:
  def greet(name: str) -> str:
      return f'Hello, {name}'

  x: int = 5
  names: list[str] = ['Alice', 'Bob']
  config: dict[str, int] = {'timeout': 30}

高级类型:
  from typing import Optional, Union, Literal, Callable, TypeVar
  
  T = TypeVar('T')
  def first(items: list[T]) -> Optional[T]:
      return items[0] if items else None

  Handler = Callable[[int, str], bool]  # 函数类型

数据类 (dataclasses):
  from dataclasses import dataclass
  @dataclass
  class Config:
      host: str = 'localhost'
      port: int = 8080
      debug: bool = False

类型注解的好处:
  1. IDE自动补全更准确
  2. 重构更安全
  3. 文档即代码
  4. 静态检查减少运行时错误"""),
    ]
    
    for title, content in concepts:
        articles.append({
            "title": title,
            "text": content,
            "length": len(content),
            "source": "nexus-synthetic-zh",
            "fetched_at": time.time(),
        })
    
    log(f"  [OK] 生成 {len(articles)} 条中文编程概念")
    return articles

# ═══════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════

def main():
    log("=" * 50)
    log("  CC老师中文数据采集器 v2")
    log("=" * 50)
    
    all_articles = []
    
    # 1. Python 中文文档 (主要来源)
    log("\n[1/4] Python 中文官方文档")
    docs = fetch_python_zh()
    all_articles.extend(docs)
    log(f"  >> {len(docs)} 篇文档")
    
    # 2. 本地论文
    log("\n[2/4] 本地论文摘要")
    papers = extract_paper_chinese()
    all_articles.extend(papers)
    
    # 3. 本地 GitHub
    log("\n[3/4] 本地 GitHub 文档")
    ghs = extract_github_chinese()
    all_articles.extend(ghs)
    
    # 4. 合成中文编程数据
    log("\n[4/4] 合成中文编程数据")
    synth = generate_synthetic_zh()
    all_articles.extend(synth)
    
    # 保存
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)
    
    total_chars = sum(a["length"] for a in all_articles)
    log(f"\n{'='*50}")
    log(f"  采集完成!")
    log(f"  总文章: {len(all_articles)}")
    log(f"  总字数: {total_chars:,}")
    log(f"  来源分布:")
    sources = {}
    for a in all_articles:
        s = a.get("source", "?")
        sources[s] = sources.get(s, 0) + 1
    for s, n in sorted(sources.items(), key=lambda x: -x[1]):
        log(f"    {s}: {n}篇")
    log(f"  输出: {OUTPUT_FILE}")
    log(f"{'='*50}")

if __name__ == "__main__":
    main()
