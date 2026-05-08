# AI SQL Agent — CLI 演示命令集

> 以下命令可直接在终端运行，展示 Rich 终端输出效果。
> 每组的「📸 截图建议」标注了最适合截图的环节。

---

## 前置条件

```bash
# 安装
pip install ai-sql-agent

# 配置环境变量（或在 .env 文件中设置）
# AI_DEFAULT_PROVIDER=longcat
# AI_LONGCAT_API_KEY=your_api_key_here
```

---

## 演示 1: 基础 — 自然语言转 SQL

**场景**：展示 NL → SQL 的核心能力

```bash
ai-sql -p longcat ask "查询每个部门的平均工资，只显示大于18000的"
```

**📸 截图点**：Rich 输出的 SQL 代码块（Monokai 语法高亮 + 行号）+ 黄色解释面板

---

## 演示 2: 达梦方言 — 国产数据库适配

**场景**：展示生成达梦特有语法

```bash
ai-sql -p longcat -d dm ask "查询最近30天新增用户按天统计"
```

**📸 截图点**：生成的 SQL 中出现 `SYSDATE`、`TO_CHAR`、`NVL` 等达梦特有函数

---

## 演示 3: Agent 工作流 — 完整自动化

**场景**：展示 Agent 自动拆解 → 生成 → 执行 → 分析

```bash
ai-sql -p longcat agent "分析上个月的销售趋势，找出消费金额Top10的客户"
```

**📸 截图点**：
- 蓝色面板：Task Understanding
- 表格：Sub-tasks 列表（展示工具调用链）
- 青色面板：Generated SQL
- 绿色表格：查询结果
- 黄色面板：Summary 综合报告

---

## 演示 4: SQL 解释 — 可读性

**场景**：将复杂 SQL 转为自然语言

```bash
ai-sql explain "SELECT d.name, AVG(e.salary) FROM employee e JOIN department d ON e.department_id = d.id WHERE e.status = 1 GROUP BY d.name HAVING AVG(e.salary) > 20000"
```

**📸 截图点**：Markdown 格式的分步解释面板

---

## 演示 5: SQL 优化 — 性能建议

**场景**：展示性能问题检测和优化方案

```bash
ai-sql optimize "SELECT * FROM orders WHERE user_id IN (SELECT user_id FROM users WHERE status = 1)"
```

**📸 截图点**：
- 红色面板：Issues Found（发现的问题列表）
- 绿色面板：Optimized SQL（优化后的 SQL）

---

## 演示 6: 交互模式 — 多轮对话

**场景**：展示连续提问的上下文理解

```bash
ai-sql -p longcat interactive
```

然后在交互模式中输入：

```
sql-agent> 查询每个部门的平均工资
sql-agent> 只显示大于20000的
sql-agent> 按工资从高到低排序
```

**📸 截图点**：多轮对话的上下文连贯性

---

## 截图建议

### 终端设置
- **字体**：JetBrains Mono 或 SF Mono，14px
- **主题**：深色背景（Monokai/Dracula），突出 Rich 的彩色输出
- **窗口宽度**：120 字符以上，确保 SQL 代码块不换行

### 推荐截图顺序
1. 先运行 `agent` 命令（信息量最大，一张图展示完整流程）
2. 再运行 `ask` 命令（简洁，突出 SQL 高亮）
3. 最后 `optimize` 命令（红绿对比，视觉冲击力强）

### 后期处理
- 可添加序号标注（①②③）说明每个面板的含义
- 可添加箭头连接 Tool Calling 的调用链
- 建议分辨率：1920×1080 或更高，方便公众号排版
