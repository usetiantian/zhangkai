# -*- coding: utf-8 -*-
"""CC老师的中国数据采集器 v3 — 高质量清洗版 (v18.5n)

改进:
  1. 更好的HTML清洗 (html.unescape + 精准body提取)
  2. 从论文摘要提取英文+中文双语言数据
  3. 优质中文编程教学数据
  4. 输出为 .py 文件方便训练管道直接读取
"""

import json
import os
import re
import sys
import time
import urllib.request
import io
import html as html_mod
from pathlib import Path

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

NEXUS_HOME = Path(os.environ.get("NEXUS_HOME", Path.home() / ".nexus"))
OUTPUT_JSON = NEXUS_HOME / "data" / "wm_v2" / "wiki_zh_texts.json"
OUTPUT_PY_DIR = NEXUS_HOME / "nexus_agent" / "zh_corpus"  # 训练管道直接读
UA = "Mozilla/5.0 (compatible; Nexus/18.5n)"

def log(msg):
    print(msg, flush=True)

# ═══════════════════════════════════════════════
# HTML 清洗
# ═══════════════════════════════════════════════

def clean_html_docs(text):
    """针对性清洗 Python 文档 HTML。"""
    # HTML entities
    text = html_mod.unescape(text)
    # Remove nav/sidebar/header/footer blocks
    text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL)
    text = re.sub(r'<(?:header|footer|aside)[^>]*>.*?</\1>', '', text, flags=re.DOTALL)
    text = re.sub(r'<div[^>]*class="[^"]*(?:sidebar|navigation|related|sphinxsidebar|topbar)[^"]*"[^>]*>.*?</div>', '', text, flags=re.DOTALL)
    # Remove script/style
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    # Remove all HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove remaining entities
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    # Clean whitespace
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    # Remove leading navigation cruft
    lines = text.split('\n')
    cleaned = []
    started = False
    for line in lines:
        s = line.strip()
        if not started and len(s) > 40 and not s.startswith(('Python', 'Navigation', 'Previous', 'Next', '3.', 'Docs')) :
            started = True
        if started:
            cleaned.append(line)
    text = '\n'.join(cleaned).strip()
    return text

# ═══════════════════════════════════════════════
# 1. Python 中文文档
# ═══════════════════════════════════════════════

PYTHON_ZH_DOCS = [
    ("Python 内置函数", "https://docs.python.org/zh-cn/3/library/functions.html"),
    ("Python 内置类型", "https://docs.python.org/zh-cn/3/library/stdtypes.html"),
    ("Python 数据模型", "https://docs.python.org/zh-cn/3/reference/datamodel.html"),
    ("Python 表达式", "https://docs.python.org/zh-cn/3/reference/expressions.html"),
    ("Python 简单语句", "https://docs.python.org/zh-cn/3/reference/simple_stmts.html"),
    ("Python 复合语句", "https://docs.python.org/zh-cn/3/reference/compound_stmts.html"),
    ("Python 导入系统", "https://docs.python.org/zh-cn/3/reference/import.html"),
    ("Python itertools", "https://docs.python.org/zh-cn/3/library/itertools.html"),
    ("Python functools", "https://docs.python.org/zh-cn/3/library/functools.html"),
    ("Python collections", "https://docs.python.org/zh-cn/3/library/collections.html"),
    ("Python typing", "https://docs.python.org/zh-cn/3/library/typing.html"),
    ("Python dataclasses", "https://docs.python.org/zh-cn/3/library/dataclasses.html"),
    ("Python asyncio", "https://docs.python.org/zh-cn/3/library/asyncio.html"),
    ("Python pathlib", "https://docs.python.org/zh-cn/3/library/pathlib.html"),
    ("Python math", "https://docs.python.org/zh-cn/3/library/math.html"),
    ("Python random", "https://docs.python.org/zh-cn/3/library/random.html"),
    ("Python statistics", "https://docs.python.org/zh-cn/3/library/statistics.html"),
    ("Python json", "https://docs.python.org/zh-cn/3/library/json.html"),
    ("Python datetime", "https://docs.python.org/zh-cn/3/library/datetime.html"),
    ("Python logging", "https://docs.python.org/zh-cn/3/library/logging.html"),
    ("Python unittest", "https://docs.python.org/zh-cn/3/library/unittest.html"),
    ("Python subprocess", "https://docs.python.org/zh-cn/3/library/subprocess.html"),
    ("Python threading", "https://docs.python.org/zh-cn/3/library/threading.html"),
    ("Python re 正则表达式", "https://docs.python.org/zh-cn/3/library/re.html"),
    ("Python os 模块", "https://docs.python.org/zh-cn/3/library/os.html"),
    ("Python sys 模块", "https://docs.python.org/zh-cn/3/library/sys.html"),
    ("Python argparse", "https://docs.python.org/zh-cn/3/library/argparse.html"),
    ("Python enum", "https://docs.python.org/zh-cn/3/library/enum.html"),
    ("Python decimal", "https://docs.python.org/zh-cn/3/library/decimal.html"),
    ("Python 教程-类", "https://docs.python.org/zh-cn/3/tutorial/classes.html"),
    ("Python 教程-模块", "https://docs.python.org/zh-cn/3/tutorial/modules.html"),
    ("Python 教程-错误异常", "https://docs.python.org/zh-cn/3/tutorial/errors.html"),
    ("Python 教程-数据结构", "https://docs.python.org/zh-cn/3/tutorial/datastructures.html"),
    ("Python 教程-控制流", "https://docs.python.org/zh-cn/3/tutorial/controlflow.html"),
    ("Python 教程-输入输出", "https://docs.python.org/zh-cn/3/tutorial/inputoutput.html"),
]

def fetch_python_zh():
    articles = []
    for name, url in PYTHON_ZH_DOCS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=30) as r:
                html = r.read().decode("utf-8", errors="replace")
            
            # 提取 body 部分
            body = re.search(r'<div[^>]*role="main"[^>]*>(.*?)(?:<footer|<div[^>]*class="[^"]*footer)', html, re.DOTALL)
            if not body:
                body = re.search(r'<div[^>]*class="[^"]*body[^"]*"[^>]*>(.*?)</div>\s*(?:<footer|$)', html, re.DOTALL)
            content = body.group(1) if body else html
            
            text = clean_html_docs(content)
            if len(text) > 500:
                articles.append({
                    "title": name,
                    "text": text[:12000],
                    "length": min(len(text), 12000),
                    "source": "docs.python.org/zh-cn",
                    "fetched_at": time.time(),
                })
                log(f"  [OK] {name}: {min(len(text), 12000)} chars")
            else:
                log(f"  [SKIP] {name}: too short ({len(text)} chars)")
        except Exception as e:
            log(f"  [FAIL] {name}: {e}")
        time.sleep(0.4)
    return articles

# ═══════════════════════════════════════════════
# 2. 合成高质量中文编程教学
# ═══════════════════════════════════════════════

def generate_zh_tutorials():
    """生成中文编程教学数据 (质量优先)。"""
    tutorials = []
    
    data = [
        ("Python 面向对象编程详解", """
Python 的面向对象编程 (OOP) 是基于类的继承体系。理解 OOP 是成为高级 Python 开发者的关键。

类的定义使用 class 关键字:
  class Animal:
      def __init__(self, name):
          self.name = name
      def speak(self):
          pass

继承允许子类复用父类的属性和方法:
  class Dog(Animal):
      def speak(self):
          return f"{self.name} says Woof!"

多态使得不同类的对象可以通过相同的接口调用:
  def animal_sound(animal):
      print(animal.speak())
  animal_sound(Dog("Buddy"))  # Buddy says Woof!

封装通过命名约定实现:
  _protected: 单下划线表示受保护的属性
  __private: 双下划线触发名称改写机制

@property 装饰器允许将方法当作属性访问:
  class Circle:
      def __init__(self, radius):
          self._radius = radius
      @property
      def area(self):
          return 3.14159 * self._radius ** 2

抽象基类 (ABC) 定义接口规范:
  from abc import ABC, abstractmethod
  class Shape(ABC):
      @abstractmethod
      def area(self):
          pass

Mixin 模式用于多重继承中混入功能:
  class JSONSerializable:
      def to_json(self):
          import json
          return json.dumps(self.__dict__)
"""),

        ("Python 高级特性: 元类与描述符", """
元类 (Metaclass) 是创建类的类。默认的元类是 type。
理解元类可以帮助你理解 Python 对象模型的底层机制。

type 的两种用法:
  1. type(obj) 返回对象的类型
  2. type(name, bases, dict) 动态创建类

自定义元类:
  class SingletonMeta(type):
      _instances = {}
      def __call__(cls, *args, **kwargs):
          if cls not in cls._instances:
              cls._instances[cls] = super().__call__(*args, **kwargs)
          return cls._instances[cls]

描述符 (Descriptor) 是实现了 __get__、__set__ 或 __delete__ 的类。
它是 property、classmethod、staticmethod 的底层实现。

  class Validator:
      def __init__(self, min_value, max_value):
          self.min = min_value
          self.max = max_value
      def __set_name__(self, owner, name):
          self.name = name
      def __get__(self, obj, objtype=None):
          return obj.__dict__.get(self.name)
      def __set__(self, obj, value):
          if not self.min <= value <= self.max:
              raise ValueError(f"{self.name} must be between {self.min} and {self.max}")
          obj.__dict__[self.name] = value

__slots__ 用于限制实例属性，节省内存:
  class Point:
      __slots__ = ('x', 'y')
      def __init__(self, x, y):
          self.x, self.y = x, y
"""),

        ("Python 异步编程完整指南", """
异步编程允许在等待 IO 操作时执行其他任务，大幅提升 IO 密集型应用的性能。

核心概念:
  - 协程 (coroutine): 用 async def 定义的函数
  - 事件循环 (event loop): 调度和执行协程
  - Future/Task: 表示异步操作的结果

async/await 语法:
  import asyncio

  async def fetch_data(url):
      print(f"Fetching {url}...")
      await asyncio.sleep(1)  # 模拟网络请求
      return f"Data from {url}"

  async def main():
      # 并发执行多个请求
      tasks = [fetch_data(f"url_{i}") for i in range(5)]
      results = await asyncio.gather(*tasks)
      print(results)

  asyncio.run(main())

异步上下文管理器:
  class AsyncFile:
      async def __aenter__(self):
          await asyncio.sleep(0.1)
          return self
      async def __aexit__(self, *args):
          await asyncio.sleep(0.1)

异步迭代器:
  class AsyncCounter:
      def __init__(self, n):
          self.n = n
      def __aiter__(self):
          return self
      async def __anext__(self):
          if self.n <= 0:
              raise StopAsyncIteration
          await asyncio.sleep(0.1)
          self.n -= 1
          return self.n

异步生成器 (Python 3.6+):
  async def async_range(n):
      for i in range(n):
          await asyncio.sleep(0.1)
          yield i

常见陷阱:
  1. 不要在协程中调用同步阻塞函数
  2. 使用 asyncio.to_thread() 将阻塞操作放入线程池
  3. 注意取消操作 (CancelledError)
  4. 使用 asyncio.Semaphore 限制并发数
"""),

        ("Python 性能优化实战", """
Python 性能优化的黄金法则: 先测量，再优化。使用 cProfile 或 py-spy 分析瓶颈。

1. 选择合适的算法和数据结构:
   - 列表 vs 集合: 成员检查 O(1) vs O(n)
   - collections.deque: 双端操作 O(1)
   - heapq: 优先队列

2. 减少属性访问开销:
   # 慢
   for i in range(1000000):
       math.sqrt(i)
   # 快 (局部变量查找更快)
   sqrt = math.sqrt
   for i in range(1000000):
       sqrt(i)

3. 使用生成器减少内存:
   # 占用大量内存
   result = [x**2 for x in range(10000000)]
   # 惰性求值
   result = (x**2 for x in range(10000000))

4. 列表拼接:
   # 慢: 每次 + 创建新列表
   result = sum(([x] for x in range(100)), [])
   # 快: 用 extend 或列表推导
   result = []
   for x in range(100):
       result.extend([x])

5. 使用内置函数和标准库:
   - map/filter 在某些场景比推导式快
   - collections.Counter 替代手动计数
   - itertools 用于组合迭代
   - functools.lru_cache 缓存重复调用

6. 字符串操作:
   # 慢: 每次 += 创建新字符串
   result = ''
   for s in strings:
       result += s
   # 快: join
   result = ''.join(strings)

7. 使用 __slots__ 节省内存:
   class Point:
       __slots__ = ('x', 'y')
       def __init__(self, x, y):
           self.x, self.y = x, y

8. 考虑使用 C 扩展 (Cython/pybind11) 或 numba JIT 编译热点函数。

9. 向量化操作: NumPy 的矩阵运算比纯 Python 循环快 100 倍以上。

10. 内存管理: 使用 memoryview 和 buffer protocol 避免拷贝。"""),

        ("深度学习基础: 从感知机到Transformer", """
深度学习的发展经历了从简单感知机到复杂 Transformer 架构的演进。

感知机 (Perceptron) 是最简单的人工神经元:
  output = activation(w1*x1 + w2*x2 + b)

多层感知机 (MLP) 堆叠多个全连接层:
  h1 = ReLU(W1 @ x + b1)
  h2 = ReLU(W2 @ h1 + b2)
  output = softmax(W3 @ h2 + b3)

卷积神经网络 (CNN) 通过卷积核提取空间特征:
  - 卷积层: 局部连接 + 权重共享
  - 池化层: 降采样保留显著特征
  - 经典架构: LeNet, AlexNet, VGG, ResNet

循环神经网络 (RNN) 处理序列数据:
  - 隐藏状态传递时序信息: ht = tanh(W @ [xt, ht-1])
  - LSTM: 引入遗忘门、输入门、输出门解决长程依赖
  - GRU: 简化 LSTM，合并遗忘门和输入门

注意力机制 (Attention) 的革命:
  - 核心思想: 让模型关注输入的重要部分
  - 自注意力: Query, Key, Value 都来自同一输入
  - 交叉注意力: Query 来自解码器，Key/Value 来自编码器

Transformer 架构 = 自注意力 + 前馈网络:
  - 编码器: N 层自注意力 + FFN
  - 解码器: N 层掩码自注意力 + 交叉注意力 + FFN
  - 位置编码: 正弦函数或可学习的位置嵌入

关键创新:
  - 残差连接: x = LayerNorm(x + Sublayer(x))
  - 多头注意力: 并行多个注意力头
  - Scaled Dot-Product: Attention(Q,K,V) = softmax(QK^T/sqrt(dk))V

训练技巧:
  - AdamW 优化器: 解耦权重衰减
  - 学习率预热: 线性增长到峰值再余弦衰减
  - 梯度裁剪: 防止梯度爆炸
  - 混合精度训练: FP16 + FP32 动态缩放"""),

        ("Git 版本控制实用指南", """
Git 是分布式版本控制系统，掌握它可以高效管理代码变更。

基本工作流:
  git init          # 初始化仓库
  git add .         # 暂存所有更改
  git commit -m "message"  # 提交
  git push origin main     # 推送到远程
  git pull origin main     # 拉取远程更新

分支管理:
  git branch feature       # 创建分支
  git checkout -b feature  # 创建并切换
  git merge feature        # 合并分支
  git rebase main          # 变基到 main

撤销操作:
  git reset --soft HEAD~1   # 撤销提交但保留更改
  git reset --hard HEAD~1   # 完全撤销
  git revert HEAD           # 创建反向提交
  git checkout -- file.py   # 丢弃工作区更改

暂存与恢复:
  git stash                 # 暂存当前更改
  git stash pop             # 恢复暂存
  git stash list            # 查看暂存列表

查看历史:
  git log --oneline --graph --all  # 图形化日志
  git diff HEAD~1                  # 查看上次提交的改动
  git blame file.py                # 查看每行代码的作者

高级技巧:
  git cherry-pick <commit>  # 挑选特定提交
  git bisect                # 二分查找引入 bug 的提交
  git reflog                # 查看所有 HEAD 变更历史

提交信息规范:
  feat: 新功能
  fix: 修复 bug
  refactor: 代码重构
  docs: 文档更新
  test: 测试相关
  chore: 构建/工具变更"""),
    ]
    
    for title, content in data:
        tutorials.append({
            "title": title,
            "text": content,
            "length": len(content),
            "source": "nexus-zh-tutorial",
            "fetched_at": time.time(),
        })
    log(f"  [OK] 生成 {len(tutorials)} 条中文教程 (共 {sum(t['length'] for t in tutorials):,} 字)")
    return tutorials

# ═══════════════════════════════════════════════
# 3. 从本地资源提取
# ═══════════════════════════════════════════════

def extract_local():
    articles = []
    
    # 论文
    pf = NEXUS_HOME / "data" / "external" / "papers" / "2026-07-10.json"
    if pf.exists():
        with open(pf, 'r', encoding='utf-8') as f:
            papers = json.load(f)
        for p in papers:
            t = f"Title: {p.get('title','')}\nAbstract: {p.get('abstract','')}"
            if len(t) > 100:
                articles.append({"title": f"[论文] {p.get('title','')[:80]}", "text": t[:4000],
                               "length": min(len(t),4000), "source": "arxiv", "fetched_at": time.time()})
        log(f"  [OK] 论文: {len(papers)} 篇")
    
    # GitHub
    gd = NEXUS_HOME / "data" / "external" / "code" / "2026-07-10"
    count = 0
    if gd.exists():
        for gf in gd.glob("*.json"):
            try:
                with open(gf, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                desc = d.get('description','')
                rm = d.get('readme','')
                t = f"{desc}\n{rm}"[:5000]
                if len(t) > 100:
                    articles.append({"title": f"[GitHub] {gf.stem}", "text": t, "length": len(t),
                                   "source": "github", "fetched_at": time.time()})
                    count += 1
            except: pass
    log(f"  [OK] GitHub: {count} 个仓库")
    
    return articles

# ═══════════════════════════════════════════════
# 4. 保存为 .py 文件 (训练管道直接读取)
# ═══════════════════════════════════════════════

def save_as_py_files(articles):
    """将中文数据保存为 .py 文件，放在 nexus_agent/zh_corpus/ 下，
    这样 _stream_tokens 就能直接读到。"""
    OUTPUT_PY_DIR.mkdir(parents=True, exist_ok=True)
    
    for i, a in enumerate(articles):
        title = re.sub(r'[\\/:*?"<>|]', '_', a["title"])[:40]
        fname = f"zh_{i:04d}_{title}.py"
        fpath = OUTPUT_PY_DIR / fname
        
        text = a["text"]
        # 包装成 Python 多行注释
        content = f'# -*- coding: utf-8 -*-\n"""\n{text}\n"""\n'
        fpath.write_text(content, encoding="utf-8")
    
    log(f"\n  [OK] 保存 {len(articles)} 个 .py 文件到 {OUTPUT_PY_DIR}")
    return len(articles)

# ═══════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════

def main():
    log("=" * 50)
    log("  CC老师中文数据 v3 - 高质量版")
    log("=" * 50)
    
    all_articles = []
    
    log("\n[1/4] Python 中文文档 (清洗版)")
    docs = fetch_python_zh()
    all_articles.extend(docs)
    
    log("\n[2/4] 中文编程教程 (合成)")
    tuts = generate_zh_tutorials()
    all_articles.extend(tuts)
    
    log("\n[3/4] 本地资源提取")
    local = extract_local()
    all_articles.extend(local)
    
    # 保存 JSON
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(all_articles, f, ensure_ascii=False, indent=2)
    
    # 保存 .py 文件给训练管道
    log("\n[4/4] 保存为 .py 训练文件")
    n_py = save_as_py_files(all_articles)
    
    total_chars = sum(a["length"] for a in all_articles)
    log(f"\n{'='*50}")
    log(f"  采集完成!")
    log(f"  总文章: {len(all_articles)}")
    log(f"  总字数: {total_chars:,}")
    log(f"  JSON:   {OUTPUT_JSON}")
    log(f"  .py:    {OUTPUT_PY_DIR} ({n_py} 文件)")
    log(f"{'='*50}")

if __name__ == "__main__":
    main()
