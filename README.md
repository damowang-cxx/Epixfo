# epixfo 航空头程运单监控系统

面向货代 / 物流公司的航空头程运单监控系统。系统围绕“运单录入、航司识别、航司查询、官方数据解析、生命周期更新、异常提醒、角色权限、在线状态和审计日志”建设，由 FastAPI 后端和 Next.js 前端组成。

当前阶段为一期后端 + 一期前端。箱号业务只保留表结构，暂未开发完整业务流程。

## 当前功能

### 后端

- 认证：登录、刷新 token、登出、当前用户查询。
- 用户权限：支持 `admin`、`route_staff`、`customer_service`、`customs_staff` 四类角色。
- 运单管理：创建、编辑、列表筛选、详情、作废、管理员手动状态、手动触发查询。
- 运单速查：`POST /api/v1/waybills/lookup`，只查询并展示结果，不创建运单，也不写入数据库。
- 航司配置：航司列表、航司创建、运单前三位前缀映射、适配器配置。
- 监控流程：根据 `next_query_at` 扫描到期运单，触发适配器查询、保存查询快照、解析官方数据、更新生命周期、生成异常。
- 异常中心：活动异常列表、确认、解决、忽略。
- 在线状态：心跳、在线用户、用户每日在线时长。
- 审计日志：记录关键操作。
- 箱号预留：`box_documents`、`boxes` 表结构已预留，业务页面和完整流程暂未开发。

### 前端

- Next.js App Router 前端位于 `apps/web`。
- 浏览器只访问 Next.js；Next API Route 作为 BFF 层读取 HttpOnly Cookie，并用 Bearer token 转发请求到 FastAPI。
- 已实现页面：登录、总览、运单列表、运单速查、新建运单、运单详情、异常中心、航司配置、用户管理、在线状态、审计日志、监控任务。

### 航司能力边界

- `784 / CZ` 已注册为 `cz_adapter`。
- 当前 CZ 适配器走 `csair` 查询链路，并经过 normalizer 和 parser 转换为系统标准数据结构。
- 其他航司尚未接入，需要后续按“Spider / Normalizer / Adapter”模式扩展。

## 技术栈

| 层 | 技术 |
| --- | --- |
| 后端 | Python 3.11+、FastAPI、SQLAlchemy 2.x、Alembic、Pydantic v2 |
| 数据库 | PostgreSQL、`psycopg` |
| 认证 | JWT access token + refresh token |
| 航司查询 | Adapter Registry、requests、BeautifulSoup、lxml、OpenCV、NumPy |
| 前端 | Next.js 16、React 19、TypeScript、Tailwind CSS 4、Radix UI、lucide-react |
| 调度 | 应用内监控调度器，由环境变量控制 |

## 目录结构

```text
epixfo/
├─ app/                         # FastAPI 后端
│  ├─ main.py                    # FastAPI 应用入口
│  ├─ api/                       # 路由与依赖
│  │  └─ v1/                     # auth / users / waybills / carriers / alerts / presence / audit / monitor
│  ├─ core/                      # config / database / security / exceptions / logging
│  ├─ models/                    # SQLAlchemy ORM
│  ├─ schemas/                   # Pydantic schema
│  ├─ services/                  # 业务服务
│  ├─ repositories/              # 数据访问封装
│  ├─ adapters/carrier_query/    # 航司查询适配器、csair 查询链路、normalizer
│  ├─ parsers/                   # 官方数据解析与状态标准化
│  ├─ tasks/                     # 监控调度任务
│  ├─ cli/                       # 命令行工具，例如 create_admin
│  └─ utils/                     # 通用工具
├─ alembic/                      # 数据库迁移
├─ apps/web/                     # Next.js 前端
│  ├─ app/                       # 页面和 Next API Routes
│  ├─ components/                # UI、布局、业务组件
│  ├─ lib/                       # API client、BFF 工具、类型、常量
│  └─ package.json
├─ tests/                        # pytest 测试
├─ pyproject.toml
├─ alembic.ini
└─ .env.example
```

## 快速开始

以下命令以 Windows PowerShell 为例。

### 1. 准备 PostgreSQL

```powershell
psql -U postgres -h localhost -c "CREATE DATABASE epixfo;"
```

如果本机 PostgreSQL 用户、密码或端口不同，请同步修改 `.env` 中的 `DATABASE_URL`。

### 2. 启动后端

```powershell
cd D:\code\letme\epixfo

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
pip install -e ".[dev]"

Copy-Item .env.example .env
notepad .env

alembic upgrade head

python -m app.cli.create_admin --username admin --password "ChangeMe@123" --display-name "管理员"

uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

验证：

- 健康检查：[http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Swagger 文档：[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 3. 启动前端

另开一个 PowerShell 窗口：

```powershell
cd D:\code\letme\epixfo\apps\web

Copy-Item .env.local.example .env.local
npm install
npm run dev
```

访问：

- 前端：[http://localhost:3000](http://localhost:3000)
- 默认后端代理地址：`http://127.0.0.1:8000/api/v1`

> 前端脚本已使用 `next dev --webpack` 和 `next build --webpack`。这是为了避开部分 Windows 环境下 Next/SWC 原生包加载异常导致 Turbopack 不可用的问题。

## 配置说明

### 后端 `.env`

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `postgresql+psycopg://postgres:postgres@localhost:5432/epixfo` | PostgreSQL 连接串 |
| `JWT_SECRET` | `change-me-in-production` | JWT 签名密钥，生产环境必须替换 |
| `ENVIRONMENT` | `local` | 运行环境 |
| `APP_TIMEZONE` | `Asia/Shanghai` | 业务时间判断使用的时区 |
| `ENABLE_MONITOR_SCHEDULER` | `false` | 是否启动应用内监控调度 |
| `MONITOR_SCHEDULER_INTERVAL_SECONDS` | `60` | 调度扫描间隔 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | access token 有效期 |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `14` | refresh token 有效期 |

代码还支持以下阈值配置：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `WEIGHT_MISMATCH_ABSOLUTE_THRESHOLD` | `1.0` | 重量差异绝对阈值，单位 kg |
| `WEIGHT_MISMATCH_PERCENT_THRESHOLD` | `0.02` | 重量差异百分比阈值 |
| `VOLUME_MISMATCH_ABSOLUTE_THRESHOLD` | `0.01` | 体积差异绝对阈值，单位 CBM |
| `VOLUME_MISMATCH_PERCENT_THRESHOLD` | `0.02` | 体积差异百分比阈值 |

### 前端 `apps/web/.env.local`

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `NEXT_PUBLIC_APP_NAME` | 航空头程运单监控系统 | 前端应用名称 |
| `BACKEND_API_URL` | `http://127.0.0.1:8000/api/v1` | Next.js 服务端转发到 FastAPI 的地址 |

## 核心接口

### 认证

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login` | 登录，返回 access token 和 refresh token |
| `POST` | `/api/v1/auth/refresh` | 刷新 token |
| `POST` | `/api/v1/auth/logout` | 登出并吊销 refresh token |
| `GET` | `/api/v1/auth/me` | 当前用户 |

### 运单

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/waybills` | 运单列表，支持筛选和分页 |
| `POST` | `/api/v1/waybills` | 创建运单 |
| `POST` | `/api/v1/waybills/lookup` | 运单速查，不写入数据库 |
| `GET` | `/api/v1/waybills/{id}` | 运单详情 |
| `PATCH` | `/api/v1/waybills/{id}` | 编辑运单 |
| `POST` | `/api/v1/waybills/{id}/void` | 管理员作废运单 |
| `POST` | `/api/v1/waybills/{id}/manual-status` | 管理员手动切换生命周期 |
| `POST` | `/api/v1/waybills/{id}/trigger-query` | 手动触发查询 |
| `GET` | `/api/v1/waybills/{id}/official-info` | 官方运单信息 |
| `GET` | `/api/v1/waybills/{id}/official-flight-segments` | 官方航段 |
| `GET` | `/api/v1/waybills/{id}/status-events` | 货物状态事件 |
| `GET` | `/api/v1/waybills/{id}/assembly-events` | 货物组装事件 |
| `GET` | `/api/v1/waybills/{id}/query-snapshots` | 查询快照 |
| `GET` | `/api/v1/waybills/{id}/alerts` | 运单异常 |

### 配置、异常、在线、审计和监控

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/carriers` | 航司列表 |
| `POST` | `/api/v1/carriers` | 创建航司 |
| `GET` | `/api/v1/carrier-prefix-mappings` | 前缀映射列表 |
| `POST` | `/api/v1/carrier-prefix-mappings` | 创建前缀映射 |
| `PATCH` | `/api/v1/carrier-prefix-mappings/{id}` | 编辑前缀映射 |
| `GET` | `/api/v1/alerts` | 异常列表 |
| `POST` | `/api/v1/alerts/{id}/acknowledge` | 确认异常 |
| `POST` | `/api/v1/alerts/{id}/resolve` | 解决异常 |
| `POST` | `/api/v1/alerts/{id}/ignore` | 忽略异常 |
| `POST` | `/api/v1/presence/heartbeat` | 用户心跳 |
| `GET` | `/api/v1/presence/online-users` | 在线用户 |
| `GET` | `/api/v1/presence/users/{id}/daily-stats` | 每日在线统计 |
| `GET` | `/api/v1/audit-logs` | 审计日志 |
| `POST` | `/api/v1/monitor/due-waybills/run` | 手动触发到期运单扫描 |

## 前端路由

| 路径 | 说明 |
| --- | --- |
| `/login` | 登录页 |
| `/` | 总览 |
| `/waybills` | 运单列表 |
| `/waybills/lookup` | 运单速查 |
| `/waybills/new` | 新建运单 |
| `/waybills/[id]` | 运单详情、编辑、官方信息、事件、快照、异常 |
| `/alerts` | 异常中心 |
| `/carriers` | 航司配置 |
| `/users` | 用户管理 |
| `/presence` | 在线状态 |
| `/audit-logs` | 审计日志 |
| `/monitor` | 监控任务 |

## 角色与权限

| 角色 | 说明 |
| --- | --- |
| `admin` | 查看全部数据；管理用户；作废运单；手动切换生命周期；处理异常；查看在线状态和审计日志；触发监控任务 |
| `route_staff` | 创建、编辑、查看运单；手动触发查询；查看异常；创建客服和出口报关账号；维护航司配置 |
| `customer_service` | 只读；只能查看 `warehouse_received` 及之后状态的运单；隐藏报价、航空费、付款日期、做数据收费、内部备注等敏感字段 |
| `customs_staff` | 只读；只能查看计划航班日期在当前自然日起三天内的运单 |

生命周期状态：

```text
created
waiting_monitor
monitoring
warehouse_received
loaded
departed
arrived
pickup_notified
picked_up
closed
voided
```

## 航司查询链路

当前查询链路按以下层次组织：

```text
Spider / Client -> Normalizer -> CarrierQueryAdapter -> Parser -> ParsedCarrierData -> MonitorService
```

- Spider / Client：负责访问航司官网或接口。
- Normalizer：把航司原始返回整理为统一 JSON 形态。
- Adapter：实现 `CarrierQueryAdapter` 协议，返回 `CarrierQueryResult`。
- Parser：把统一 JSON 转为官方运单信息、航段、状态事件、组装事件。
- MonitorService：保存快照，写入标准表，更新生命周期并触发异常判断。

新增航司时，优先新增对应航司的查询实现、normalizer 和 adapter；业务层不应关心底层是 protocol、playwright 还是 hybrid。

## 测试与校验

### 后端

```powershell
cd D:\code\letme\epixfo
pytest
```

### 前端

```powershell
cd D:\code\letme\epixfo\apps\web
npm run typecheck
npm run lint
npm run build
```

## 常见问题

### 数据库连接失败

检查 PostgreSQL 是否启动，以及 `.env` 中的 `DATABASE_URL` 是否与本机账号、密码、数据库名和端口一致。

### `JWT_SECRET` 未配置

本地可以使用默认值，生产环境必须替换为强随机字符串，例如：

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### 前端登录 401

常见原因：

- 后端没有启动。
- `apps/web/.env.local` 中的 `BACKEND_API_URL` 指向错误。
- 管理员账号尚未创建。
- 用户名或密码错误。

### 端口占用

后端改端口：

```powershell
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

前端改端口：

```powershell
npm run dev -- --port 3001
```

如果前端代理的后端端口变化，记得同步修改 `apps/web/.env.local` 中的 `BACKEND_API_URL`。

### Next/SWC Windows 警告

部分 Windows 环境会出现 Next/SWC 原生包不是有效 Win32 应用的警告。当前前端脚本已经使用 Webpack：

```json
{
  "dev": "next dev --webpack",
  "build": "next build --webpack"
}
```

只要 `npm run build` 成功，可以暂时忽略该警告。

## 当前边界

- 已有完整的一期后端和一期前端主流程。
- CZ 查询链路已接入当前代码，其他航司待扩展。
- 箱号业务只预留表结构，未实现页面和业务流。
- Excel 导出、微信通知、更多航司适配属于后续阶段。
