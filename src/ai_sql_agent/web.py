"""Web UI for AI SQL Agent — Apple-style glassmorphism design."""

import json
import logging
import os
import sqlite3
import sys
import tempfile
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# Fix Windows encoding
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from .assistant import SQLAssistant
from .config import DBConfig, build_provider
from .db.dialects import DialectType

logger = logging.getLogger(__name__)

# ── Sample data SQL ──────────────────────────────────────────────────────────

SAMPLE_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS department (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    location VARCHAR(200),
    budget DECIMAL(15,2)
);
CREATE TABLE IF NOT EXISTS employee (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(200),
    salary DECIMAL(12,2),
    hire_date DATE,
    department_id INTEGER,
    status INTEGER DEFAULT 1,
    FOREIGN KEY (department_id) REFERENCES department(id)
);
CREATE TABLE IF NOT EXISTS customer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(200),
    city VARCHAR(100),
    register_date DATE
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    total_amount DECIMAL(15,2),
    status INTEGER DEFAULT 1,
    create_time DATETIME,
    FOREIGN KEY (customer_id) REFERENCES customer(id)
);
CREATE TABLE IF NOT EXISTS product (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(100),
    price DECIMAL(10,2),
    stock INTEGER DEFAULT 0
);
"""

SAMPLE_DATA_SQL = """
INSERT OR IGNORE INTO department (id, name, location, budget) VALUES
(1, '技术部', '北京', 5000000),
(2, '销售部', '上海', 3000000),
(3, '市场部', '广州', 2000000),
(4, '人事部', '深圳', 1500000),
(5, '财务部', '北京', 1800000);
INSERT OR IGNORE INTO employee (id, name, email, salary, hire_date, department_id, status) VALUES
(1, '张三', 'zhangsan@example.com', 25000, '2022-03-15', 1, 1),
(2, '李四', 'lisi@example.com', 18000, '2023-01-10', 1, 1),
(3, '王五', 'wangwu@example.com', 30000, '2021-06-20', 1, 1),
(4, '赵六', 'zhaoliu@example.com', 15000, '2023-07-01', 2, 1),
(5, '钱七', 'qianqi@example.com', 22000, '2022-09-15', 2, 1),
(6, '孙八', 'sunba@example.com', 16000, '2024-02-20', 3, 1),
(7, '周九', 'zhoujiu@example.com', 28000, '2020-11-05', 1, 1),
(8, '吴十', 'wushi@example.com', 12000, '2024-06-10', 4, 1),
(9, '郑十一', 'zhengshiyi@example.com', 19000, '2023-03-25', 5, 1),
(10, '王十二', 'wangshier@example.com', 35000, '2019-08-12', 1, 1);
INSERT OR IGNORE INTO customer (id, name, email, city, register_date) VALUES
(1, '客户A', 'a@example.com', '北京', '2024-01-15'),
(2, '客户B', 'b@example.com', '上海', '2024-03-20'),
(3, '客户C', 'c@example.com', '广州', '2024-05-10'),
(4, '客户D', 'd@example.com', '深圳', '2024-06-01'),
(5, '客户E', 'e@example.com', '杭州', '2024-08-15');
INSERT OR IGNORE INTO orders (id, customer_id, total_amount, status, create_time) VALUES
(1, 1, 15800, 1, '2025-04-01 10:30:00'),
(2, 2, 23500, 1, '2025-04-05 14:20:00'),
(3, 1, 8900, 1, '2025-04-10 09:15:00'),
(4, 3, 45600, 1, '2025-04-15 16:45:00'),
(5, 4, 12300, 0, '2025-04-18 11:00:00'),
(6, 5, 67800, 1, '2025-04-20 13:30:00'),
(7, 2, 34200, 1, '2025-04-22 10:00:00'),
(8, 3, 19500, 1, '2025-04-25 15:20:00'),
(9, 1, 52100, 1, '2025-04-28 08:45:00'),
(10, 5, 28700, 1, '2025-05-01 12:10:00'),
(11, 4, 41300, 1, '2025-05-03 14:00:00'),
(12, 2, 16800, 1, '2025-05-05 09:30:00');
INSERT OR IGNORE INTO product (id, name, category, price, stock) VALUES
(1, '笔记本电脑', '电子产品', 6999, 120),
(2, '机械键盘', '电子产品', 599, 300),
(3, '显示器', '电子产品', 2499, 80),
(4, '办公椅', '办公用品', 1299, 200),
(5, '打印机', '办公用品', 3599, 45),
(6, '鼠标', '电子产品', 199, 500),
(7, '耳机', '电子产品', 899, 250),
(8, '白板', '办公用品', 399, 150);
"""


def init_sample_db(db_config: DBConfig):
    """Initialize SQLite with sample data."""
    conn = sqlite3.connect(db_config.name or ":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SAMPLE_SCHEMA_SQL)
    conn.executescript(SAMPLE_DATA_SQL)
    conn.commit()
    conn.close()


# ── HTML Template ────────────────────────────────────────────────────────────

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI SQL Agent</title>
<style>
/* ── Reset & Base ─────────────────────────────────────────── */
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
body{font-family:-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text","Helvetica Neue","PingFang SC","Microsoft YaHei",sans-serif;line-height:1.6;overflow:hidden;height:100vh;transition:background .35s,color .35s}

/* ── CSS Variables — Light (default) ─────────────────────── */
:root{
  --bg:#f5f5f7;--bg2:#ffffff;--surface:rgba(255,255,255,.72);--surface-solid:#ffffff;
  --border:rgba(0,0,0,.08);--border2:rgba(0,0,0,.12);
  --text:#1d1d1f;--text2:#6e6e73;--text3:#86868b;
  --accent:#0071e3;--accent-hover:#0077ed;--accent-light:rgba(0,113,227,.1);
  --green:#34c759;--green-bg:rgba(52,199,89,.1);
  --red:#ff3b30;--red-bg:rgba(255,59,48,.08);
  --orange:#ff9500;--orange-bg:rgba(255,149,0,.1);
  --purple:#af52de;
  --glass:rgba(255,255,255,.65);--glass-border:rgba(255,255,255,.45);
  --glass-shadow:0 8px 32px rgba(0,0,0,.06),0 2px 8px rgba(0,0,0,.04);
  --glass-blur:40px;
  --radius:16px;--radius-sm:10px;--radius-xs:8px;
  --mono:"SF Mono","JetBrains Mono","Fira Code",Menlo,monospace;
  --transition:all .25s cubic-bezier(.4,0,.2,1);
}

/* ── Dark Theme ───────────────────────────────────────────── */
body.dark{
  --bg:#000000;--bg2:#1c1c1e;--surface:rgba(28,28,30,.72);--surface-solid:#1c1c1e;
  --border:rgba(255,255,255,.1);--border2:rgba(255,255,255,.16);
  --text:#f5f5f7;--text2:#86868b;--text3:#636366;
  --accent:#0a84ff;--accent-hover:#409cff;--accent-light:rgba(10,132,255,.15);
  --green:#30d158;--green-bg:rgba(48,209,88,.12);
  --red:#ff453a;--red-bg:rgba(255,69,58,.1);
  --orange:#ff9f0a;--orange-bg:rgba(255,159,10,.12);
  --purple:#bf5af2;
  --glass:rgba(28,28,30,.65);--glass-border:rgba(255,255,255,.12);
  --glass-shadow:0 8px 32px rgba(0,0,0,.3),0 2px 8px rgba(0,0,0,.2);
}

/* ── Scrollbar ────────────────────────────────────────────── */
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--text3);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:var(--text2)}

/* ── Banner ───────────────────────────────────────────────── */
.banner{
  height:52px;flex-shrink:0;
  background:var(--glass);
  backdrop-filter:blur(var(--glass-blur));-webkit-backdrop-filter:blur(var(--glass-blur));
  border-bottom:1px solid var(--border);
  display:flex;align-items:center;justify-content:space-between;
  padding:0 24px;position:relative;z-index:50;
  transition:var(--transition);
}
.banner-left{display:flex;align-items:center;gap:10px}
.banner-logo{font-size:18px;font-weight:700;letter-spacing:-.3px;color:var(--text)}
.banner-logo em{font-style:normal;color:var(--accent)}
.banner-badge{
  font-size:11px;font-weight:600;padding:3px 10px;border-radius:20px;
  background:var(--accent-light);color:var(--accent);
}
.banner-right{display:flex;align-items:center;gap:12px}

/* Theme toggle */
.theme-btn{
  width:32px;height:32px;border-radius:50%;border:1px solid var(--border);
  background:var(--surface);color:var(--text);cursor:pointer;
  display:flex;align-items:center;justify-content:center;font-size:16px;
  transition:var(--transition);
}
.theme-btn:hover{background:var(--accent-light);border-color:var(--accent);transform:scale(1.05)}

/* ── Layout ───────────────────────────────────────────────── */
.app{display:flex;height:calc(100vh - 52px);overflow:hidden}

/* ── Left Panel ───────────────────────────────────────────── */
.left-panel{
  width:340px;min-width:280px;max-width:420px;flex-shrink:0;
  background:var(--surface);
  backdrop-filter:blur(var(--glass-blur));-webkit-backdrop-filter:blur(var(--glass-blur));
  border-right:1px solid var(--border);
  display:flex;flex-direction:column;
  transition:var(--transition);
}
.panel-header{
  padding:16px 18px 12px;border-bottom:1px solid var(--border);
  font-size:13px;font-weight:600;color:var(--text2);text-transform:uppercase;letter-spacing:.5px;
  display:flex;align-items:center;gap:6px;
}

/* Schema section */
.schema-section{flex:1;overflow-y:auto;padding:12px}
.schema-group{margin-bottom:12px}
.schema-group-title{
  font-size:11px;font-weight:600;color:var(--text3);text-transform:uppercase;
  letter-spacing:.8px;padding:4px 6px 8px;
}
.schema-card{
  background:var(--glass);border:1px solid var(--border);border-radius:var(--radius-sm);
  padding:10px 14px;margin-bottom:6px;cursor:pointer;transition:var(--transition);
}
.schema-card:hover{border-color:var(--accent);background:var(--accent-light)}
.schema-card-name{font-size:13px;font-weight:600;color:var(--text);margin-bottom:2px}
.schema-card-cols{font-size:11px;color:var(--text3);line-height:1.5;word-break:break-all}

/* Config section */
.config-section{padding:12px 18px;border-top:1px solid var(--border)}
.config-row{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.config-row label{font-size:12px;font-weight:500;color:var(--text2);min-width:36px}
.config-row select,.config-row input{
  flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text);
  border-radius:var(--radius-xs);padding:6px 10px;font-size:12px;
  font-family:inherit;transition:var(--transition);outline:none;
}
.config-row select:focus,.config-row input:focus{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-light)}

/* ── Right Panel ──────────────────────────────────────────── */
.right-panel{flex:1;display:flex;flex-direction:column;min-width:0;background:var(--bg);transition:var(--transition)}

/* Chat messages */
.chat-messages{
  flex:1;overflow-y:auto;padding:20px 24px;
  display:flex;flex-direction:column;gap:16px;
}

/* Welcome / empty state */
.welcome{
  flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;
  gap:16px;padding:40px;text-align:center;
}
.welcome-icon{font-size:56px;animation:float 3s ease-in-out infinite}
@keyframes float{0%,100%{transform:translateY(0)}50%{transform:translateY(-8px)}}
.welcome h2{font-size:22px;font-weight:700;color:var(--text);letter-spacing:-.3px}
.welcome p{font-size:14px;color:var(--text2);max-width:420px}
.welcome-chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:4px}
.chip{
  font-size:13px;padding:8px 16px;border-radius:20px;border:1px solid var(--border);
  background:var(--glass);color:var(--text);cursor:pointer;transition:var(--transition);
  backdrop-filter:blur(20px);-webkit-backdrop-filter:blur(20px);
}
.chip:hover{border-color:var(--accent);background:var(--accent-light);color:var(--accent);transform:translateY(-1px)}

/* Message bubbles */
.msg{display:flex;gap:10px;max-width:88%;animation:msgIn .3s ease-out}
@keyframes msgIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.msg.user{align-self:flex-end;flex-direction:row-reverse}
.msg-avatar{
  width:30px;height:30px;border-radius:50%;flex-shrink:0;
  display:flex;align-items:center;justify-content:center;font-size:14px;
  margin-top:4px;
}
.msg.assistant .msg-avatar{background:linear-gradient(135deg,var(--accent),var(--purple))}
.msg.user .msg-avatar{background:linear-gradient(135deg,var(--green),var(--accent))}
.msg-bubble{
  padding:12px 16px;border-radius:var(--radius-sm);font-size:14px;
  line-height:1.65;word-break:break-word;
}
.msg.assistant .msg-bubble{
  background:var(--glass);border:1px solid var(--border);
  border-top-left-radius:4px;
}
.msg.user .msg-bubble{
  background:var(--accent);color:#fff;border-top-right-radius:4px;
}

/* SQL block */
.sql-block{
  background:var(--bg2);border:1px solid var(--border2);border-radius:var(--radius-xs);
  padding:12px;margin:10px 0;font-family:var(--mono);font-size:12.5px;
  white-space:pre-wrap;overflow-x:auto;color:var(--text);line-height:1.55;
}

/* Result table */
.result-table-wrap{margin:10px 0;overflow-x:auto;border-radius:var(--radius-xs);border:1px solid var(--border)}
.result-table{width:100%;border-collapse:collapse;font-size:12.5px}
.result-table th{
  background:var(--surface);color:var(--text2);font-weight:600;
  padding:8px 12px;text-align:left;border-bottom:1px solid var(--border);
  font-size:11px;text-transform:uppercase;letter-spacing:.4px;white-space:nowrap;
}
.result-table td{padding:7px 12px;border-bottom:1px solid var(--border);color:var(--text)}
.result-table tr:last-child td{border-bottom:none}
.result-table tr:hover td{background:var(--accent-light)}
.row-count{font-size:12px;color:var(--green);margin:6px 0 2px;font-weight:500}

/* Error / info */
.error-box{
  background:var(--red-bg);border:1px solid rgba(255,59,48,.2);border-radius:var(--radius-xs);
  padding:10px 14px;color:var(--red);font-size:13px;margin:8px 0;
}
.info-text{font-size:12px;color:var(--text3);margin-top:6px}

/* Typing indicator */
.typing{display:flex;gap:4px;padding:4px 0}
.typing i{width:7px;height:7px;border-radius:50%;background:var(--accent);animation:typingBounce .65s infinite}
.typing i:nth-child(2){animation-delay:.12s}
.typing i:nth-child(3){animation-delay:.24s}
@keyframes typingBounce{0%,80%,100%{transform:scale(.5);opacity:.3}40%{transform:scale(1);opacity:1}}

/* ── Input Area ───────────────────────────────────────────── */
.input-area{
  padding:14px 20px;border-top:1px solid var(--border);
  background:var(--glass);
  backdrop-filter:blur(var(--glass-blur));-webkit-backdrop-filter:blur(var(--glass-blur));
}
.input-row{display:flex;gap:10px;align-items:flex-end}
.input-wrap{
  flex:1;background:var(--bg);border:1px solid var(--border);border-radius:24px;
  display:flex;align-items:flex-end;padding:4px 4px 4px 16px;transition:var(--transition);
}
.input-wrap:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-light)}
.input-wrap textarea{
  flex:1;background:none;border:none;color:var(--text);font-size:14px;
  font-family:inherit;resize:none;outline:none;max-height:120px;padding:8px 0;
  line-height:1.5;
}
.input-wrap textarea::placeholder{color:var(--text3)}
.send-btn{
  width:36px;height:36px;border-radius:50%;border:none;background:var(--accent);
  color:#fff;cursor:pointer;font-size:16px;display:flex;align-items:center;
  justify-content:center;transition:var(--transition);flex-shrink:0;
}
.send-btn:hover{background:var(--accent-hover);transform:scale(1.05)}
.send-btn:disabled{opacity:.4;cursor:not-allowed;transform:none}

/* ── Responsive ───────────────────────────────────────────── */
@media(max-width:768px){
  .left-panel{position:absolute;left:0;top:52px;bottom:0;z-index:40;transform:translateX(-100%);box-shadow:4px 0 24px rgba(0,0,0,.12)}
  .left-panel.open{transform:translateX(0)}
  .menu-toggle{display:flex}
  .msg{max-width:92%}
}
@media(min-width:769px){
  .menu-toggle{display:none}
}

/* ── Sidebar toggle ───────────────────────────────────────── */
.menu-toggle{
  width:32px;height:32px;border-radius:50%;border:1px solid var(--border);
  background:var(--surface);color:var(--text);cursor:pointer;
  align-items:center;justify-content:center;font-size:16px;transition:var(--transition);
  display:none;margin-right:8px;
}
.menu-toggle:hover{background:var(--accent-light)}

/* ── Overlay for mobile ───────────────────────────────────── */
.overlay{display:none;position:absolute;inset:0;background:rgba(0,0,0,.3);z-index:35}
.overlay.show{display:flex}
</style>
</head>
<body>

<!-- Banner -->
<div class="banner">
  <div class="banner-left">
    <button class="menu-toggle" id="menuToggle" onclick="toggleSidebar()">☰</button>
    <div class="banner-logo">🤖 <em>AI</em>&nbsp;SQL&nbsp;Agent</div>
    <div class="banner-badge" id="bannerBadge">LongCat-2.0</div>
  </div>
  <div class="banner-right">
    <button class="theme-btn" id="themeBtn" onclick="toggleTheme()" title="切换主题">🌙</button>
  </div>
</div>

<!-- App -->
<div class="app">

  <!-- Left Panel: Schema + Config -->
  <div class="overlay" id="overlay" onclick="toggleSidebar()"></div>
  <div class="left-panel" id="leftPanel">
    <div class="panel-header">📊 数据表结构</div>
    <div class="schema-section" id="schemaSection">
      <div style="color:var(--text3);font-size:13px;padding:20px;text-align:center">加载中…</div>
    </div>
    <div class="config-section">
      <div class="config-row">
        <label>模型</label>
        <select id="provider" onchange="updateBadge()">
          <option value="longcat">🐱 LongCat</option>
          <option value="longcat-flash">⚡ LongCat Flash</option>
          <option value="longcat-thinking">🧠 LongCat Thinking</option>
          <option value="longcat-omni">🎭 LongCat Omni</option>
          <option value="longcat-lite">🍃 LongCat Lite</option>
          <option value="openai">🧪 OpenAI GPT</option>
          <option value="claude">🔮 Claude</option>
          <option value="grok">🚀 Grok</option>
          <option value="glm">🦅 智谱 GLM</option>
          <option value="deepseek">🐋 DeepSeek</option>
          <option value="qwen">☁️ 通义千问</option>
          <option value="kimi">🌙 Kimi</option>
          <option value="doubao">🫘 豆包</option>
          <option value="yuanbao">💎 元宝</option>
        </select>
      </div>
      <div class="config-row">
        <label>方言</label>
        <select id="dialect">
          <option value="sqlite">🪶 SQLite</option>
          <option value="mysql">🐬 MySQL</option>
          <option value="dm">🐉 达梦 DM</option>
          <option value="postgres">🐘 PostgreSQL</option>
          <option value="standard">📐 标准 SQL</option>
        </select>
      </div>
      <div class="config-row">
        <label>Key</label>
        <input type="password" id="apiKey" placeholder="留空使用 .env 配置" />
      </div>
    </div>
  </div>

  <!-- Right Panel: Chat -->
  <div class="right-panel">
    <div class="chat-messages" id="chatMessages">
      <div class="welcome" id="welcome">
        <div class="welcome-icon">🤖</div>
        <h2>你好，我是 AI SQL Agent</h2>
        <p>内置示例数据库，包含部门、员工、客户、订单、产品 5 张表。输入自然语言，我来帮你生成 SQL 并执行。</p>
        <div class="welcome-chips">
          <div class="chip" onclick="setQuery('查询每个部门的平均工资')">📊 部门平均工资</div>
          <div class="chip" onclick="setQuery('查询消费金额最高的Top10客户')">🏆 Top10 客户</div>
          <div class="chip" onclick="setQuery('最近30天的订单数量和金额统计')">📈 订单趋势</div>
          <div class="chip" onclick="setQuery('查询工资最高的5名员工及其部门')">💰 高薪员工</div>
          <div class="chip" onclick="setQuery('每个部门的员工数量和总预算')">🏢 部门预算</div>
          <div class="chip" onclick="setQuery('查询库存不足100的产品')">📦 库存不足</div>
        </div>
      </div>
    </div>
    <div class="input-area">
      <div class="input-row">
        <div class="input-wrap">
          <textarea id="queryInput" placeholder="输入自然语言查询…" rows="1"
            onkeydown="handleKey(event)" oninput="autoResize(this)"></textarea>
          <button class="send-btn" id="sendBtn" onclick="sendQuery()" title="发送 (Enter)">➤</button>
        </div>
      </div>
    </div>
  </div>

</div>

<script>
// ── Theme ─────────────────────────────────────────────────────
const savedTheme = localStorage.getItem('aistheme');
if (savedTheme === 'dark') document.body.classList.add('dark');
updateThemeIcon();

function toggleTheme() {
  document.body.classList.toggle('dark');
  localStorage.setItem('aistheme', document.body.classList.contains('dark') ? 'dark' : 'light');
  updateThemeIcon();
}
function updateThemeIcon() {
  document.getElementById('themeBtn').textContent = document.body.classList.contains('dark') ? '☀️' : '🌙';
}

// ── Sidebar (mobile) ─────────────────────────────────────────
function toggleSidebar() {
  document.getElementById('leftPanel').classList.toggle('open');
  document.getElementById('overlay').classList.toggle('show');
}

// ── Badge ────────────────────────────────────────────────────
const providerLabels = {
  longcat:'LongCat-2.0', 'longcat-flash':'Flash', 'longcat-thinking':'Thinking',
  'longcat-omni':'Omni', 'longcat-lite':'Lite', openai:'GPT', claude:'Claude',
  grok:'Grok', glm:'GLM', deepseek:'DeepSeek', qwen:'Qwen', kimi:'Kimi',
  doubao:'Doubao', yuanbao:'Yuanbao'
};
function updateBadge() {
  const p = document.getElementById('provider').value;
  document.getElementById('bannerBadge').textContent = providerLabels[p] || p;
}

// ── Schema ───────────────────────────────────────────────────
fetch('/api/schema')
  .then(r => r.json())
  .then(d => {
    const el = document.getElementById('schemaSection');
    if (!d.tables || !d.tables.length) {
      el.innerHTML = '<div style="color:var(--text3);font-size:13px;padding:20px;text-align:center">无数据表</div>';
      return;
    }
    el.innerHTML = `<div class="schema-group">
      <div class="schema-group-title">示例数据库 · ${d.tables.length} 张表</div>
      ${d.tables.map(t => `
        <div class="schema-card" onclick="setQuery('查询 ${t.name} 表的所有数据')">
          <div class="schema-card-name">${t.name}</div>
          <div class="schema-card-cols">${t.columns}</div>
        </div>`).join('')}
    </div>`;
  }).catch(() => {});

// ── Chat ─────────────────────────────────────────────────────
const messagesEl = document.getElementById('chatMessages');
const inputEl = document.getElementById('queryInput');
const sendBtn = document.getElementById('sendBtn');
let welcomeHidden = false;

function setQuery(q) {
  inputEl.value = q;
  inputEl.focus();
  autoResize(inputEl);
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendQuery(); }
}

function hideWelcome() {
  if (welcomeHidden) return;
  welcomeHidden = true;
  const w = document.getElementById('welcome');
  if (w) w.remove();
}

function addMsg(role, html) {
  hideWelcome();
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  const avatar = role === 'assistant' ? '🤖' : '👤';
  div.innerHTML = `<div class="msg-avatar">${avatar}</div><div class="msg-bubble">${html}</div>`;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function addLoading() {
  hideWelcome();
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.id = 'loadingMsg';
  div.innerHTML = `<div class="msg-avatar">🤖</div><div class="msg-bubble"><div class="typing"><i></i><i></i><i></i></div></div>`;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function removeLoading() {
  const el = document.getElementById('loadingMsg');
  if (el) el.remove();
}

function renderTable(rows, cols) {
  if (!rows || !rows.length) return '<div class="info-text">查询返回 0 行</div>';
  let html = '<div class="result-table-wrap"><table class="result-table"><thead><tr>';
  cols.forEach(c => html += `<th>${c}</th>`);
  html += '</tr></thead><tbody>';
  rows.forEach(r => {
    html += '<tr>';
    cols.forEach(c => html += `<td>${r[c] != null ? r[c] : ''}</td>`);
    html += '</tr>';
  });
  html += '</tbody></table></div>';
  return html;
}

async function sendQuery() {
  const q = inputEl.value.trim();
  if (!q) return;

  const provider = document.getElementById('provider').value;
  const dialect = document.getElementById('dialect').value;
  const apiKey = document.getElementById('apiKey').value.trim();

  addMsg('user', q);
  inputEl.value = '';
  inputEl.style.height = 'auto';
  addLoading();
  sendBtn.disabled = true;

  try {
    const resp = await fetch('/api/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query: q, provider, dialect, api_key: apiKey || undefined})
    });
    const data = await resp.json();
    removeLoading();

    let html = '';
    if (data.understanding && data.understanding !== q) {
      html += `<div style="color:var(--text3);font-size:12px;margin-bottom:8px">💭 ${data.understanding}</div>`;
    }
    if (data.sql) {
      html += `<div class="sql-block">${escapeHtml(data.sql)}</div>`;
    }
    if (data.rows && data.columns) {
      html += `<div class="row-count">📊 ${data.row_count} 行结果</div>`;
      html += renderTable(data.rows, data.columns);
    }
    if (data.analysis) {
      html += `<div style="margin-top:10px">${data.analysis}</div>`;
    }
    if (data.explanation) {
      html += `<div class="info-text" style="margin-top:8px">💡 ${data.explanation}</div>`;
    }
    if (data.error) {
      html += `<div class="error-box">❌ ${data.error}</div>`;
    }
    if (!html) html = data.answer || data.summary || '无返回结果';
    addMsg('assistant', html);
  } catch (e) {
    removeLoading();
    addMsg('assistant', `<div class="error-box">❌ 请求失败: ${e.message}</div>`);
  }
  sendBtn.disabled = false;
  inputEl.focus();
}

function escapeHtml(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}
</script>
</body>
</html>"""


# ── Request Handler ──────────────────────────────────────────────────────────

class Handler(SimpleHTTPRequestHandler):
    """HTTP handler for the web UI."""

    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
        elif self.path == '/api/schema':
            self._json(self._get_schema())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/ask':
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length) or b'{}')
            self._json(self._handle_ask(body))
        else:
            self.send_error(404)

    def _json(self, data):
        resp = json.dumps(data, ensure_ascii=False, default=str).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', len(resp))
        self.end_headers()
        self.wfile.write(resp)

    def _get_schema(self):
        try:
            tmp = tempfile.mktemp(suffix='.db')
            db_config = DBConfig(db_type="sqlite", name=tmp)
            init_sample_db(db_config)
            conn = sqlite3.connect(tmp)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            tables = []
            for (tname,) in cursor.fetchall():
                cursor.execute(f'PRAGMA table_info("{tname}")')
                cols = [f"{row[1]}({row[2]})" for row in cursor.fetchall()]
                tables.append({"name": tname, "columns": ", ".join(cols)})
            conn.close()
            os.unlink(tmp)
            return {"tables": tables}
        except Exception as e:
            return {"tables": [], "error": str(e)}

    def _handle_ask(self, body):
        query = body.get('query', '')
        provider = body.get('provider', 'longcat')
        dialect_str = body.get('dialect', 'sqlite')
        api_key = body.get('api_key', '')

        if not query:
            return {"error": "查询不能为空"}

        try:
            dialect_map = {
                'sqlite': DialectType.SQLITE, 'mysql': DialectType.MYSQL,
                'dm': DialectType.DM, 'postgres': DialectType.POSTGRES,
                'standard': DialectType.STANDARD,
            }
            dialect = dialect_map.get(dialect_str, DialectType.SQLITE)

            p = build_provider(provider)
            if api_key:
                p.api_key = api_key

            tmp = tempfile.mktemp(suffix='.db')
            db_config = DBConfig(db_type="sqlite", name=tmp)
            init_sample_db(db_config)

            try:
                assistant = SQLAssistant(
                    provider_name=provider,
                    provider=p,
                    db_config=db_config,
                    dialect=dialect,
                )
                result = assistant.generate_sql(query)

                response = {
                    "understanding": query,
                    "sql": result.get("sql", ""),
                    "explanation": result.get("explanation", ""),
                }

                sql = result.get("sql", "")
                if sql:
                    try:
                        rows, columns = assistant._db.execute(sql)
                        response["rows"] = rows[:50]
                        response["columns"] = columns
                        response["row_count"] = len(rows)
                        if rows:
                            analysis = assistant.analyze_result(query, rows, len(rows))
                            response["analysis"] = analysis
                    except Exception as e:
                        response["error"] = f"SQL 执行错误: {e}"

                assistant.close()
                return response
            finally:
                try:
                    os.unlink(tmp)
                except Exception:
                    pass

        except Exception as e:
            logger.exception("ask failed")
            return {"error": str(e)}

    def log_message(self, fmt, *args):
        logger.debug(f"HTTP {args}")


# ── Server entry ─────────────────────────────────────────────────────────────

def start_web(host: str = "127.0.0.1", port: int = 8080):
    """Start the web UI server."""
    server = HTTPServer((host, port), Handler)
    url = f"http://{host}:{port}"
    msg = (
        f"\n========================================\n"
        f"  AI SQL Agent Web UI\n"
        f"  打开浏览器访问: {url}\n"
        f"  内置示例数据库: department / employee / customer / orders / product\n"
        f"  API 端点: POST /api/ask\n"
        f"  按 Ctrl+C 停止服务\n"
        f"========================================\n"
    )
    sys.stdout.write(msg)
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stdout.write("\n已停止服务\n")
        sys.stdout.flush()
        server.server_close()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    start_web(port=port)
