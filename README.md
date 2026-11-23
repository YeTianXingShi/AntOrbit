# AntOrbit

面向 **Antigravity（反重力）** 客户端的自部署在线网站发布与通知推送平台。

让 Ant 可以一键将生成的网页/报告/交互原型部署到你自己的服务器上供远程访问（`/s/<slug>/`），支持内置表单提交、轻量 KV 状态存储以及 **Bark / ntfy** 通知推送。

---

## 核心特性

- **单容器一键部署（x86_64）**：Python FastAPI + SQLite + Vue 3 管理后台打包在单个 Docker 镜像中，零外部数据库依赖。
- **零配置路径托管**：站点统一通过 `https://<host>/s/<slug>/` 访问，无需泛域名解析和通配证书。
- **灵活权限与生命周期**：支持自定义或随机 `slug`、按站点设置访问密码（站点作用域 `HttpOnly` Cookie 隔离）、TTL 自动过期清理，以及按 `slug` 原地覆盖更新（保留历史表单与 KV 数据）。
- **轻量交互能力 + 内置 SDK**：页面只需引入 `<script src="/_antorbit/sdk.js"></script>`，即可调用 `AntOrbit.submit()` 提交表单/审批，以及 `AntOrbit.kv.get/set/list/delete` 读写轻量 JSON 状态。
- **全场景通知推送（Bark / ntfy）**：支持 Ant 独立推送消息、发布站点时一键推送访问链接、站点收到表单提交时自动推送提醒，支持点击通知直达页面与紧急级别设置。
- **标准 Antigravity 插件**：提供本地 stdio Python MCP Server（直接打包上传本地目录或内联 HTML）+ `SKILL.md`。

---

## 快速部署服务端（Docker）

镜像由 GitHub Actions 自动构建并发布到 GHCR（`linux/amd64`）：

```bash
cp .env.example .env
# 编辑 .env 设置 ANTORBIT_ADMIN_PASSWORD 和 ANTORBIT_PUBLIC_URL
docker compose up -d
```

启动后访问 `http://<你的服务器>:8000/admin/`：
1. 使用 `ANTORBIT_ADMIN_PASSWORD` 登录管理后台。
2. 在 **通知渠道** 中添加你的 Bark 或 ntfy 渠道并点击 **测试**。
3. 在 **API 密钥** 中生成一个 API Key（或在 `.env` 中通过 `ANTORBIT_API_KEY` 预设）。

> 如需 HTTPS，建议前置 Caddy 或 Nginx 反向代理到 `127.0.0.1:8000`，并在 `.env` 中配置 `ANTORBIT_PUBLIC_URL=https://你的域名`。

---

## 安装 Antigravity 客户端插件

前提：本机已安装 [`uv`](https://docs.astral.sh/uv/)（提供 `uvx` 命令）。

1. 将本仓库的 `plugin/` 目录复制到 Antigravity 插件目录：
   - **Windows**：`C:\Users\<用户名>\.gemini\config\plugins\antorbit\`
   - **macOS / Linux**：`~/.gemini/config/plugins/antorbit/`
2. 编辑该目录下的 `mcp_config.json`，填入你的服务器地址与 API Key：
   ```json
   {
     "mcpServers": {
       "antorbit": {
         "command": "uvx",
         "args": [
           "--from",
           "git+https://github.com/YeTianXingShi/AntOrbit.git#subdirectory=mcp",
           "antorbit-mcp"
         ],
         "env": {
           "ANTORBIT_URL": "https://your-antorbit-host.example.com",
           "ANTORBIT_API_KEY": "ao_your_api_key_here"
         }
       }
     }
   }
   ```
3. 在 Antigravity 的 Customizations 页面启用 **AntOrbit** 插件即可。

---

## 目录结构

```text
AntOrbit/
├── server/            # Python FastAPI 服务端（托管、交互 API、Bark/ntfy 推送、SQLite）
├── web/               # Vue 3 + Vite + Tailwind CSS 管理后台（/admin）
├── mcp/               # 本地 stdio Python MCP Server（antorbit-mcp）
├── plugin/            # Antigravity Plugin（plugin.json、mcp_config.json、SKILL.md、logo）
├── Dockerfile         # 多阶段构建（Node 22 + Python 3.12）
├── docker-compose.yml
└── .github/workflows/docker.yml  # 自动测试 + 构建推送 linux/amd64 镜像到 GHCR
```

---

## 本地开发测试

```bash
# 运行服务端测试
uv run --project server --extra dev pytest -v server/tests

# 运行 MCP Server 测试
uv run --project mcp --extra dev pytest -v mcp/tests

# 本地启动服务端
uv run --project server uvicorn app.main:app --app-dir server --reload --port 8000
```
