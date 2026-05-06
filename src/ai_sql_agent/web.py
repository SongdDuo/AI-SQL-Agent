"""Web UI for AI SQL Agent — built-in HTTP server with interactive demo."""

import json
import logging
import os
import sqlite3
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Fix Windows encoding
if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from .agent import SQLAgent
from .assistant import SQLAssistant
from .config import DBConfig, build_provider, PROVIDER_PRESETS
from .db.connector import DBConnector
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
<title>🤖 AI SQL Agent</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#0a0e17;--surface:#111827;--surface2:#1e293b;--border:#1e3a5f;--cyan:#06b6d4;--green:#10b981;--purple:#8b5cf6;--orange:#f59e0b;--red:#ef4444;--text:#e2e8f0;--text2:#94a3b8;--text3:#64748b;--font:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans SC",sans-serif;--mono:"JetBrains Mono","Fira Code",Consolas,monospace}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--text);font-family:var(--font);line-height:1.7;overflow-x:hidden}
a{color:var(--cyan);text-decoration:none}
.container{max-width:960px;margin:0 auto;padding:0 20px}

/* Header */
.header{padding:20px 0;border-bottom:1px solid var(--border);background:rgba(10,14,23,.9);backdrop-filter:blur(12px);position:sticky;top:0;z-index:100}
.header .container{display:flex;align-items:center;justify-content:space-between}
.logo{font-weight:700;font-size:20px;color:#fff}
.logo span{color:var(--cyan)}
.badge{display:inline-flex;align-items:center;gap:4px;background:var(--surface2);border:1px solid var(--border);border-radius:16px;padding:4px 12px;font-size:12px;color:var(--cyan)}
.badge .dot{width:6px;height:6px;border-radius:50%;background:var(--green);animation:pulse 2s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}

/* Main */
.main{padding:30px 0}

/* Config bar */
.config-bar{display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;align-items:center}
.config-bar label{font-size:13px;color:var(--text2)}
.config-bar select,.config-bar input{background:var(--surface2);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:6px 10px;font-size:13px;font-family:var(--font)}
.config-bar select:focus,.config-bar input:focus{outline:none;border-color:var(--cyan)}
.config-bar input{width:260px}

/* Schema panel */
.schema-panel{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:20px}
.schema-panel h3{font-size:14px;color:var(--cyan);margin-bottom:10px}
.schema-table{display:inline-block;background:var(--surface2);border:1px solid var(--border);border-radius:6px;padding:8px 12px;margin:4px;font-size:12px}
.schema-table .tname{font-weight:600;color:var(--green);margin-bottom:4px}
.schema-table .tcols{color:var(--text3);line-height:1.5}

/* Chat area */
.chat-area{background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden}
.chat-messages{height:420px;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px}
.msg{display:flex;gap:10px;max-width:85%}
.msg.user{align-self:flex-end;flex-direction:row-reverse}
.msg .avatar{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0}
.msg.assistant .avatar{background:rgba(6,182,212,.15)}
.msg.user .avatar;background:rgba(139,92,246,.15)}
.msg .bubble{padding:10px 14px;border-radius:10px;font-size:14px;line-height:1.6}
.msg.assistant .bubble{background:var(--surface2);border:1px solid var(--border)}
.msg.user .bubble;background:rgba(139,92,246,.2);border:1px solid rgba(139,92,246,.3)}
.msg .bubble .sql-block{background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px;margin:8px 0;font-family:var(--mono);font-size:12px;white-space:pre-wrap;overflow-x:auto;color:var(--green)}
.msg .bubble .result-table{width:100%;border-collapse:collapse;margin:8px 0;font-size:12px}
.msg .bubble .result-table th,.msg .bubble .result-table td{border:1px solid var(--border);padding:4px 8px;text-align:left}
.msg .bubble .result-table th{background:var(--surface2);color:var(--cyan)}
.msg .bubble .result-table tr:nth-child(even){background:rgba(30,41,59,.5)}
.msg .bubble .error{color:var(--red);background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.3);border-radius:6px;padding:8px;margin:8px 0}
.msg .bubble .info{color:var(--orange);font-size:12px;margin-top:4px}

/* Loading dots */
.loading{display:flex;gap:4px;padding:4px 0}
.loading span{width:6px;height:6px;border-radius:50%;background:var(--cyan);animation:bounce .6s infinite}
.loading span:nth-child(2){animation-delay:.15s}
.loading span:nth-child(3){animation-delay:.3s}
@keyframes bounce{0%,80%,100%{transform:scale(.4);opacity:.4}40%{transform:scale(1);opacity:1}}

/* Input area */
.chat-input{display:flex;gap:8px;padding:12px;border-top:1px solid var(--border);background:var(--surface2)}
.chat-input input{flex:1;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:6px;padding:8px 12px;font-size:14px;font-family:var(--font)}
.chat-input input:focus{outline:none;border-color:var(--cyan)}
.chat-input button{background:var(--cyan);color:#000;border:none;border-radius:6px;padding:8px 16px;font-size:14px;font-weight:600;cursor:pointer;transition:all .2s}
.chat-input button:hover{background:#22d3ee}
.chat-input button:disabled{opacity:.5;cursor:not-allowed}

/* Examples */
.examples{display:flex;gap:6px;flex-wrap:wrap;padding:8px 16px;border-top:1px solid var(--border);background:rgba(17,24,39,.5)}
.examples button{background:var(--surface2);border:1px solid var(--border);color:var(--text2);border-radius:4px;padding:4px 10px;font-size:12px;cursor:pointer;transition:all .2s}
.examples button:hover{border-color:var(--cyan);color:var(--cyan)}

@media(max-width:640px){
  .config-bar{flex-direction:column;align-items:stretch}
  .config-bar input{width:100%}
  .chat-messages{height:350px}
}
</style>
</head>
<body>

<div class="header">
  <div class="container">
    <div class="logo">🤖 <span>AI</span> SQL Agent</div>
    <div class="badge"><span class="dot"></span> Powered by LongCat-2.0-Preview</div>
  </div>
</div>

<div class="main">
<div class="container">

  <div class="config-bar">
    <label>模型:</label>
    <select id="provider">
      <option value="longcat" selected>🐱 LongCat</option>
      <option value="longcat-flash">⚡ LongCat Flash</option>
      <option value="longcat-thinking">🧠 LongCat Thinking</option>
      <option value="longcat-omni">🎭 LongCat Omni</option>
      <option value="longcat-lite">🪶 LongCat Lite</option>
      <option value="openai">OpenAI GPT</option>
      <option value="claude">Claude</option>
      <option value="grok">Grok</option>
      <option value="glm">智谱 GLM</option>
      <option value="deepseek">DeepSeek</option>
      <option value="qwen">通义千问</option>
      <option value="kimi">Kimi</option>
      <option value="doubao">豆包</option>
      <option value="yuanbao">元宝</option>
    </select>
    <label>方言:</label>
    <select id="dialect">
      <option value="sqlite" selected>SQLite</option>
      <option value="mysql">MySQL</option>
      <option value="dm">达梦(DM)</option>
      <option value="postgres">PostgreSQL</option>
      <option value="standard">标准 SQL</option>
    </select>
    <input type="password" id="apiKey" placeholder="API Key (留空使用 .env 配置)" />
  </div>

  <div class="schema-panel" id="schemaPanel">
    <h3>📊 示例数据库 Schema（已内置假数据）</h3>
    <div id="schemaContent">加载中...</div>
  </div>

  <div class="chat-area">
    <div class="chat-messages" id="chatMessages">
      <div class="msg assistant">
        <div class="avatar">🤖</div>
        <div class="bubble">
          你好！我是 AI SQL Agent 👋<br><br>
          我已经内置了一个示例数据库，包含以下表：<br>
          • <b>department</b> — 部门表 (id, name, location, budget)<br>
          • <b>employee</b> — 员工表 (id, name, email, salary, hire_date, department_id, status)<br>
          • <b>customer</b> — 客户表 (id, name, email, city, register_date)<br>
          • <b>orders</b> — 订单表 (id, customer_id, total_amount, status, create_time)<br>
          • <b>product</b> — 产品表 (id, name, category, price, stock)<br><br>
          试试问我：<br>
          💡 "查询每个部门的平均工资"<br>
          💡 "最近30天的订单趋势"<br>
          💡 "消费金额最高的Top10客户"
        </div>
      </div>
    </div>
    <div class="examples">
      <button onclick="setQuery('查询每个部门的平均工资')">部门平均工资</button>
      <button onclick="setQuery('查询消费金额最高的Top10客户')">Top10客户</button>
      <button onclick="setQuery('最近30天的订单数量和金额统计')">订单趋势</button>
      <button onclick="setQuery('查询工资最高的5名员工及其部门')">高薪员工</button>
      <button onclick="setQuery('每个部门的员工数量和总预算')">部门预算</button>
      <button onclick="setQuery('查询库存不足100的产品')">库存不足</button>
    </div>
    <div class="chat-input">
      <input type="text" id="queryInput" placeholder="输入自然语言查询，如：查询每个部门的平均工资" onkeydown="if(event.key==='Enter')sendQuery()" />
      <button onclick="sendQuery()" id="sendBtn">发送</button>
    </div>
  </div>

</div>
</div>

<script>
const messages = document.getElementById('chatMessages');
const input = document.getElementById('queryInput');
const sendBtn = document.getElementById('sendBtn');

// Load schema
fetch('/api/schema').then(r=>r.json()).then(d=>{
  const c = document.getElementById('schemaContent');
  if(d.tables && d.tables.length){
    c.innerHTML = d.tables.map(t =>
      `<div class="schema-table"><div class="tname">${t.name}</div><div class="tcols">${t.columns}</div></div>`
    ).join('');
  } else {
    c.innerHTML = '<span style="color:var(--text3)">无表</span>';
  }
}).catch(()=>{});

function setQuery(q){ input.value=q; input.focus(); }

function addMsg(role, html){
  const div = document.createElement('div');
  div.className = 'msg ' + role;
  div.innerHTML = `<div class="avatar">${role==='assistant'?'🤖':'👤'}</div><div class="bubble">${html}</div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

function addLoading(){
  const div = document.createElement('div');
  div.className = 'msg assistant';
  div.id = 'loadingMsg';
  div.innerHTML = `<div class="avatar">🤖</div><div class="bubble"><div class="loading"><span></span><span></span><span></span></div></div>`;
  messages.appendChild(div);
  messages.scrollTop = messages.scrollHeight;
}

function removeLoading(){
  const el = document.getElementById('loadingMsg');
  if(el) el.remove();
}

function fmtTable(rows, cols){
  if(!rows || !rows.length) return '<div class="info">查询返回 0 行</div>';
  let html = '<table class="result-table"><thead><tr>';
  cols.forEach(c => html += `<th>${c}</th>`);
  html += '</tr></thead><tbody>';
  rows.forEach(r => {
    html += '<tr>';
    cols.forEach(c => html += `<td>${r[c]!==undefined?r[c]:''}</td>`);
    html += '</tr>';
  });
  html += '</tbody></table>';
  return html;
}

async function sendQuery(){
  const q = input.value.trim();
  if(!q) return;
  const provider = document.getElementById('provider').value;
  const dialect = document.getElementById('dialect').value;
  const apiKey = document.getElementById('apiKey').value.trim();

  addMsg('user', q);
  input.value = '';
  addLoading();
  sendBtn.disabled = true;

  try{
    const resp = await fetch('/api/ask', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query: q, provider, dialect, api_key: apiKey || undefined})
    });
    const data = await resp.json();
    removeLoading();

    let html = '';
    if(data.understanding){
      html += `<div style="color:var(--text3);font-size:12px;margin-bottom:6px">💭 ${data.understanding}</div>`;
    }
    if(data.sql){
      html += `<div class="sql-block">${data.sql}</div>`;
    }
    if(data.rows && data.columns){
      html += `<div style="font-size:12px;color:var(--green);margin:4px 0">📊 ${data.row_count} 行结果</div>`;
      html += fmtTable(data.rows, data.columns);
    }
    if(data.analysis){
      html += `<div style="margin-top:8px">${data.analysis}</div>`;
    }
    if(data.error){
      html += `<div class="error">❌ ${data.error}</div>`;
    }
    if(!html) html = data.answer || data.summary || '无返回结果';
    addMsg('assistant', html);
  }catch(e){
    removeLoading();
    addMsg('assistant', `<div class="error">❌ 请求失败: ${e.message}</div>`);
  }
  sendBtn.disabled = false;
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
            db_config = DBConfig(db_type="sqlite", name=":memory:")
            # Use file-based temp DB so schema is visible
            import tempfile, os
            tmp = tempfile.mktemp(suffix='.db')
            db_config.name = tmp
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

            # Build provider config
            p = build_provider(provider)
            if api_key:
                p.api_key = api_key

            # Create temp DB with sample data
            import tempfile, os
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

                # Try to execute
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
