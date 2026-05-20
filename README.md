# epixfo · 航空头程运单监控系统

面向货代/物流公司的**航空头程运单**全生命周期监控后台。围绕"运单创建 → 自动查询航司官网 → 解析事件 → 推进生命周期 → 触发异常告警"主链路展开，由 FastAPI 后端 + Next.js 前端构成。

> **当前阶段**：一期（phase one）。骨架、领域模型、生命周期/告警/权限/审计/调度全部就绪；**南方航空（CZ）适配器已接入真实查询**（vendored 自 spider/tang，纯 HTTP + OpenCV 解滑动验证码）；其他航司待二期补齐。

---

## 核心特性

- **运单管理**：创建、编辑、作废、人工状态推进、按多维度筛选分页。
- **承运人适配器**：基于 Protocol + Registry 抽象，支持 `protocol` / `playwright` / `hybrid` 三种查询方式。
- **监控调度**：asyncio 后台 loop，周期扫描到期运单，自动调用航司官网。
- **生命周期推断**：依据官方事件类型自动推算 11 种状态。
- **告警引擎**：9 类业务告警（航班变更、未起飞、重量/体积差异、查询失败等），三级严重度。
- **RBAC**：4 角色（admin / route_staff / customer_service / customs_staff），行级可见性 + 字段脱敏。
- **在线状态**：心跳上报、日在线时长统计。
- **审计日志**：操作前后数据 + IP / UA。

---

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.11+ · FastAPI · SQLAlchemy 2.0 · Alembic · `psycopg`（PostgreSQL） · Pydantic v2 |
| 前端 | Next.js 16（App Router） · React 19 · Tailwind CSS 4 · Radix UI · TypeScript 5 |
| 数据库 | PostgreSQL 14+ |
| 鉴权 | JWT 双 token（access + refresh） |
| 后台任务 | 内置 asyncio `MonitorScheduler`，由环境变量开关 |

---

## 目录结构

```
epixfo/
├── app/                          # 后端源码
│   ├── main.py                   # FastAPI 入口
│   ├── api/v1/                   # REST 路由（auth/users/waybills/carriers/alerts/audit/presence/monitor）
│   ├── core/                     # config / database / security / exceptions / logging
│   ├── models/                   # SQLAlchemy ORM（waybill / user / alert / carrier / presence / audit / box）
│   ├── schemas/                  # Pydantic schema
│   ├── services/                 # 业务服务（waybill / monitor / lifecycle / alert / permission / ...）
│   ├── repositories/             # 数据访问层
│   ├── adapters/carrier_query/   # 承运人查询适配器（Protocol + Registry）
│   ├── parsers/                  # 官网响应解析器 + 状态文本规范化
│   ├── tasks/scheduler.py        # 后台监控调度器
│   ├── cli/                      # 命令行工具（create_admin）
│   └── utils/
├── alembic/                      # 数据库迁移
│   └── versions/
├── apps/web/                     # 前端 Next.js 项目
│   ├── app/                      # App Router 页面
│   ├── components/               # UI 组件
│   ├── lib/                      # client-api / server-api / types
│   └── package.json
├── tests/                        # pytest 用例
├── pyproject.toml
├── alembic.ini
└── .env.example
```

---

## 快速开始 — Windows（开发环境）

> 命令均以 PowerShell 为准。

### 前置依赖

| 依赖 | 版本 | 验证 |
| --- | --- | --- |
| Python | 3.11+ | `python --version` |
| Node.js | 20+ | `node -v` |
| PostgreSQL | 14+ | `Get-Service postgresql*` |

### 1. 建库

```powershell
psql -U postgres -h localhost -c "CREATE DATABASE epixfo;"
```

如本机 `postgres` 账号不可用，参考下文"常见问题"确认账号密码。

### 2. 后端

```powershell
cd D:\code\letme\epixfo

# 虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 装依赖
python -m pip install --upgrade pip
pip install -e ".[dev]"

# 配置
Copy-Item .env.example .env
notepad .env   # 至少改 DATABASE_URL 和 JWT_SECRET

# 迁移
alembic upgrade head

# 创建管理员（密码请改为强随机串）
python -m app.cli.create_admin --username admin --password "ChangeMe@123" --display-name "管理员"

# 启动
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

> **PowerShell 提示**：若 `Activate.ps1` 被禁止执行，在管理员 PowerShell 中跑一次
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`。

验证：
- http://127.0.0.1:8000/health → `{"status":"ok"}`
- http://127.0.0.1:8000/docs → Swagger UI

### 3. 前端

另开一个 PowerShell 窗口：

```powershell
cd D:\code\letme\epixfo\apps\web

Copy-Item .env.local.example .env.local   # 默认指向 127.0.0.1:8000，无需修改

npm install
npm run dev
```

访问 http://localhost:3000，用刚创建的管理员账号登录。

---

## 部署 — Ubuntu（生产环境）

> 目标：Ubuntu 22.04 LTS / 24.04 LTS。所有命令以 `root` 或带 `sudo` 的用户执行。

### 1. 系统依赖

```bash
sudo apt update
sudo apt install -y \
  python3.11 python3.11-venv python3.11-dev \
  build-essential libpq-dev \
  postgresql postgresql-contrib \
  curl git

# Node.js 20（NodeSource）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

### 2. PostgreSQL 建库 + 专用账号

```bash
sudo -u postgres psql <<'SQL'
CREATE USER epixfo WITH PASSWORD 'use-a-strong-password';
CREATE DATABASE epixfo OWNER epixfo;
GRANT ALL PRIVILEGES ON DATABASE epixfo TO epixfo;
SQL
```

### 3. 部署用户与代码

```bash
sudo useradd -m -s /bin/bash epixfo
sudo -iu epixfo

git clone <你的仓库地址> ~/epixfo
cd ~/epixfo
```

### 4. 后端

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .

cp .env.example .env
# 编辑 .env：
#   DATABASE_URL=postgresql+psycopg://epixfo:<密码>@localhost:5432/epixfo
#   JWT_SECRET=<生成命令见下方>
#   ENVIRONMENT=production
#   ENABLE_MONITOR_SCHEDULER=true   # 生产环境通常打开
nano .env

# 生成 JWT 强随机密钥
python -c "import secrets; print(secrets.token_urlsafe(48))"

# 迁移 + 管理员
alembic upgrade head
python -m app.cli.create_admin --username admin --password "<强密码>" --display-name "管理员"
```

### 5. 后端 systemd 服务

`/etc/systemd/system/epixfo-api.service`：

```ini
[Unit]
Description=Epixfo API (FastAPI)
After=network.target postgresql.service

[Service]
Type=simple
User=epixfo
WorkingDirectory=/home/epixfo/epixfo
EnvironmentFile=/home/epixfo/epixfo/.env
ExecStart=/home/epixfo/epixfo/.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000 --workers 2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now epixfo-api
sudo systemctl status epixfo-api
```

### 6. 前端构建与运行

[next.config.ts](apps/web/next.config.ts) 已配置 `output: "standalone"`，构建产物自带最小依赖。

```bash
cd ~/epixfo/apps/web
cp .env.local.example .env.local
# 把 BACKEND_API_URL 改为内网后端地址，例如：
#   BACKEND_API_URL=http://127.0.0.1:8000/api/v1
nano .env.local

npm ci
npm run build
```

`/etc/systemd/system/epixfo-web.service`：

```ini
[Unit]
Description=Epixfo Web (Next.js)
After=network.target epixfo-api.service

[Service]
Type=simple
User=epixfo
WorkingDirectory=/home/epixfo/epixfo/apps/web
Environment=NODE_ENV=production
Environment=PORT=3000
Environment=HOSTNAME=127.0.0.1
ExecStart=/usr/bin/node .next/standalone/apps/web/server.js
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> Next standalone 产物路径会因 monorepo 嵌套而带前缀；如启动报"Cannot find module"，先 `ls apps/web/.next/standalone/` 确认 `server.js` 实际路径，再调整 `ExecStart`。

启用：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now epixfo-web
```

### 7. 反向代理（可选）

建议在前面套一层 nginx 终结 HTTPS、统一入口：

```nginx
server {
    listen 80;
    server_name epixfo.example.com;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

前端通过 Next.js 内部 API 代理后端，因此 nginx 仅需暴露 3000。HTTPS 用 Let's Encrypt（`certbot`）签发即可。

### 8. 监控调度器开关时机

[scheduler.py](app/tasks/scheduler.py) 默认关闭，仅当 `ENABLE_MONITOR_SCHEDULER=true` 时启动。建议：
- 一期 CZ 适配器仍是占位时**保持关闭**（开了也只会写一堆 `carrier_query_not_configured` 失败快照）。
- 二期航司接入后再打开，并按业务体量调 `MONITOR_SCHEDULER_INTERVAL_SECONDS`。

---

## 配置说明

### 后端：项目根 `.env`（参考 [.env.example](.env.example)）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/epixfo` | SQLAlchemy 连接串，密码含特殊字符需 URL 编码 |
| `JWT_SECRET` | `change-me-in-production` | JWT 签名密钥，**生产必须替换为强随机串** |
| `ENVIRONMENT` | `local` | `local` / `production` 等 |
| `APP_TIMEZONE` | `Asia/Shanghai` | 影响告警 / 调度时间判断 |
| `API_V1_PREFIX` | `/api/v1` | 路由前缀 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | access token 有效期 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `14` | refresh token 有效期 |
| `ENABLE_MONITOR_SCHEDULER` | `false` | 是否启动后台监控调度 |
| `MONITOR_SCHEDULER_INTERVAL_SECONDS` | `60` | 调度循环间隔 |
| `WEIGHT_MISMATCH_ABSOLUTE_THRESHOLD` | `1.0` | 重量差异绝对阈值（kg） |
| `WEIGHT_MISMATCH_PERCENT_THRESHOLD` | `0.02` | 重量差异百分比阈值 |
| `VOLUME_MISMATCH_ABSOLUTE_THRESHOLD` | `0.01` | 体积差异绝对阈值（m³） |
| `VOLUME_MISMATCH_PERCENT_THRESHOLD` | `0.02` | 体积差异百分比阈值 |

> 重量 / 体积告警逻辑：`abs(官方 - 订舱) > max(绝对阈值, 订舱 × 百分比阈值)`。

### 前端：`apps/web/.env.local`（参考 [apps/web/.env.local.example](apps/web/.env.local.example)）

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `NEXT_PUBLIC_APP_NAME` | `航空头程运单监控系统` | 浏览器标题 / 导航品牌 |
| `BACKEND_API_URL` | `http://127.0.0.1:8000/api/v1` | Next.js 服务端代理后端的内网地址 |

---

## 角色与权限矩阵

数据源：[app/services/permission_service.py](app/services/permission_service.py)。

| 角色 | 可见运单 | 运单写入 | 字段脱敏 | 告警处理 | 用户管理 | 在线/审计 |
| --- | --- | --- | --- | --- | --- | --- |
| `admin` 管理员 | 全部 | ✅ | 无 | ✅ | ✅ | ✅ |
| `route_staff` 航线操作 | 全部 | ✅ | 无 | ❌ | ✅ | ❌ |
| `customer_service` 客服 | 仅入仓后（`warehouse_received` 及之后状态） | ❌ | 隐藏 `quotation` / `air_freight_cost` / `payment_date` / `data_charge` / `internal_remark` | ❌ | ❌ | ❌ |
| `customs_staff` 关务 | 仅"今天起未来 3 天"航班 | ❌ | 无 | ❌ | ❌ | ❌ |

> 客服可见状态白名单：`warehouse_received` / `loaded` / `departed` / `arrived` / `pickup_notified` / `picked_up` / `closed`。

---

## 常用脚本

```bash
# 生成新迁移（修改 ORM 后）
alembic revision --autogenerate -m "add xxx"

# 应用迁移
alembic upgrade head

# 回滚一步
alembic downgrade -1

# 创建管理员账号
python -m app.cli.create_admin --username admin --password "<强密码>" --display-name "管理员"

# 手动触发到期运单一轮监控查询（需 admin token）
curl -X POST "http://127.0.0.1:8000/api/v1/monitor/due-waybills/run?limit=50" \
  -H "Authorization: Bearer <admin_access_token>"
```

---

## 测试

```bash
pytest
```

测试代码位于 [tests/](tests/)，覆盖配置、安全工具、监控规则、解析器、模型、健康检查等模块。

---

## 常见问题

| 现象 | 排查 |
| --- | --- |
| `psycopg.OperationalError: connection refused` | PostgreSQL 未启动；或 `DATABASE_URL` 端口 / 账号 / 密码错误 |
| 数据库密码含 `@` `:` `/` `#` | 在 `DATABASE_URL` 中做 URL 编码（`@` → `%40`，`#` → `%23`），或改为纯字母数字密码 |
| `.\.venv\Scripts\Activate.ps1` 被禁止 | 管理员 PowerShell：`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| `psql` / `alembic` 找不到命令 | 把 `C:\Program Files\PostgreSQL\<版本>\bin` 加到 PATH；alembic 需先激活 venv |
| 前端登录 401 | 后端未启 / `BACKEND_API_URL` 指向错误 / 管理员密码错 |
| 不知道 PostgreSQL 账号 | 默认安装的超级用户是 `postgres`，密码是装机时自己设置的；忘记可临时改 `pg_hba.conf` 为 `trust` 后重置 |
| 端口 3000 / 8000 占用 | Windows：`$env:PORT=3001; npm run dev` 或 `uvicorn ... --port 8001` |
| Next standalone 启动报模块找不到 | 看实际产物路径：`ls apps/web/.next/standalone/`，按其结构调整 systemd `ExecStart` |

---

## 承运人查询管道

```
Spider (csair / mu / hu ...)  →  Normalizer  →  Adapter  →  Parser  →  ParsedCarrierData
  原生 dict 字段名混乱           统一形态 dict   CarrierQueryResult   类型 + 语义规范化
```

- **Spider** ([app/adapters/carrier_query/csair/](app/adapters/carrier_query/csair/))：各航司原生爬虫，最易随官网改版而失效，独立可替换。
- **Normalizer** ([app/adapters/carrier_query/normalizers/](app/adapters/carrier_query/normalizers/))：把航司原生 dict 翻译成统一形态（`waybill_info / booking_info / status_events / assembly_events`）；也是写入 [`waybill_query_snapshots.raw_response`](app/models/waybill.py) JSONB 的快照内容，便于跨航司排障。
- **Adapter** ([app/adapters/carrier_query/cz_adapter.py](app/adapters/carrier_query/cz_adapter.py))：实现 `CarrierQueryAdapter` Protocol；内部调 Spider + Normalizer，包成 `CarrierQueryResult` 返回。
- **Parser** ([app/parsers/](app/parsers/))：统一形态 dict → `ParsedCarrierData`（类型转换 + 状态文本规范化）。

新增一家航司只需添加 `xxx_adapter.py` + `xxx/` spider 包 + `normalizers/xxx.py`，不动 Parser / Schema / 监控调度。

## 路线图与现状

- **一期（当前）**：
  - 领域模型、生命周期、告警、RBAC、审计、监控调度框架、前端全套页面已完成。
  - 承运人查询四层管道（Spider / Normalizer / Adapter / Parser）落地。
  - **南方航空（CZ）适配器已接入真实查询**：[csair/](app/adapters/carrier_query/csair/) vendored 自 spider/tang，通过纯 HTTP + OpenCV 解滑动验证码，无浏览器依赖。
- **二期（规划）**：
  - 接入更多航司（东航 MU / 国航 CA / 海航 HU 等），仅需重复"Spider + Normalizer + Adapter"三件套。
  - 把硬编码的 URL / Auth 迁移到 [`CarrierQueryConfig.config_json`](app/models/carrier.py) 由数据库下发。
  - `Box` / `BoxDocument` 模型（已在 [models/__init__.py](app/models/__init__.py) 中预留）落地"集装箱 / 报关单证"业务。
  - 微信等通知通道（`NotificationChannel.WECHAT_RESERVED` 已预留）。
