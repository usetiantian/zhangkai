# CC 会话日记 — 2026-07-18

## 做了什么

### 知识库从死变活
- Qwen3-VL-4B 替换 2B：ModelScope 下载 8.89GB，transformers fp16 直载，视觉验证通过
- 摄入优化：Qwen 自动分类 150 扩展名，6.4/s，E2E 12/12 全过
- RAG 存储从 JSON 改 .npy + 原子写，再也不损坏
- 删除 smart_organize.py（292行→20行 sort_file()），能力内建

### 活了
- heartbeat()：观察、检测、建议
- reflect()：模型自省
- sort_file()：读内容→自己分类，零规则
- generate_insights()：向量+图→跨域发现→写洞察
  - 发现 CC↔AI私有数据 的 3 个关联
  - 洞察写入 D:/node/知识发现/

### CC 专属文件夹
- D:/node/CC/ 1828 个文件，723 个文本已可搜索

### 宪法新增
- A0.2 红线：永不自删文件，suggest_delete() 移到待删除/ + 原因

### 张凯的决策
- 每 3 天凌晨自动整理
- 不要确认，自动执行
- 知识库是智能体，不是死索引
- 不硬编码，一切模型驱动
- 来时路在 D:/node/CC/
