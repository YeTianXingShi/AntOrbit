# AntOrbit

面向 **Antigravity（反重力）** 客户端的自部署在线网站发布与通知推送平台。

让 Ant 可以一键将生成的网页、分析报告、数据看板或审批表单部署到你自己的服务器上供远程访问（`/s/<slug>/`），并支持通过 **Bark / ntfy** 将结果与访问链接推送到你的手机。

---

## 核心特性

- **单容器一键部署（x86_64）**：Python FastAPI + SQLite + Vue 3 管理后台打包在单个 Docker 镜像中，零外部数据库依赖。
- **零配置路径托管**：站点统一通过 `https://<your-domain>/s/<slug>/` 访问，无需泛域名解析与通配证书。
- **灵活权限与生命周期**：
  - 自定义 `slug` 或自动生成随机不可猜测 `slug`
  - 按站点可选访问密码（内置解锁页 + `Path=/s/<slug>/` 作用域 `HttpOnly` Cookie 隔离）
  - 可选 TTL 自动过期与后台定时清理
  - 复用 `slug` 原地覆盖更新静态资源时，自动保留该站点已有的表单提交与 KV 数据
- **轻量交互能力 + 内置资产（SDK & 统一 UI 样式）**：页面引入 `<script src="/_antorbit/sdk.js"></script>` 即可调用 `AntOrbit.submit()` 和 `AntOrbit.kv.*`；引入 `<link rel="stylesheet" href="/_antorbit/ui.css">` 即可直接复用 AntOrbit Slate + Sky 设计系统。
- **开箱即用的现代静态站点兼容**：自动改写 HTML/CSS 根路径至 `/s/<slug>/...`、SPA 深层路由自动注入 `<base>`、子目录 307 补尾斜杠、Clean URL（`about` → `about.html`）、单 HTML 目录自动入口、自定义 `404.html`、完整现代 MIME（`.mjs`/`.wasm`/`.woff2`/`.avif`/`.webmanifest`）、`GET`/`HEAD`、Gzip 压缩与分层 `Cache-Control` 缓存策略，发布时自动返回兼容性诊断 `warnings`。
- **全场景通知推送（Bark / ntfy）**：支持 Ant 独立推送消息、发布站点时一键推送链接、站点收到表单提交时自动推送提醒，支持点击通知直达网页与紧急级别设置。
- **标准 Antigravity 插件**：打包本地 stdio Python MCP Server（支持直接打包上传本地文件夹或内联 HTML）+ `SKILL.md`。

---

## 一、部署服务端（Docker）

预编译的 `linux/amd64` 镜像由 GitHub Actions 自动构建并发布至 GHCR：`ghcr.io/yetianxingshi/antorbit:latest`。

### 方式 A：集成 Caddy 自动反代与 HTTPS（推荐）

`antorbit` 不对外暴露宿主机端口，仅在 Docker 内网由 Caddy 自动申请并续签 SSL 证书：

```yaml
services:
  antorbit:
    image: ghcr.io/yetianxingshi/antorbit:latest
    container_name: antorbit
    restart: unless-stopped
    expose:
      - "8000"
    environment:
      ANTORBIT_ADMIN_PASSWORD: "请改成你的强密码"
      ANTORBIT_PUBLIC_URL: "https://your-domain.example.com"
      ANTORBIT_API_KEY: ""
      TZ: "Asia/Shanghai"
      ANTORBIT_DATA_DIR: "/data"
      ANTORBIT_MAX_UPLOAD_MB: "50"
      ANTORBIT_CLEANUP_INTERVAL_SEC: "300"
    volumes:
      - ./data:/data
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"

  caddy:
    image: caddy:2-alpine
    container_name: antorbit-caddy
    restart: unless-stopped
    depends_on:
      - antorbit
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    command: caddy reverse-proxy --from your-domain.example.com --to antorbit:8000
    volumes:
      - ./caddy_data:/data
      - ./caddy_config:/config
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

启动并查看证书签发日志：

```bash
docker compose up -d
docker compose logs -f caddy
```

> **使用 Cloudflare 代理（小黄云）时的注意事项**：
> 1. Cloudflare 的 SSL/TLS 加密模式**不要选择 `Flexible`**（会与 Caddy 自动 HTTPS 跳转形成重定向循环）。
> 2. 首次启动建议先设为 **`Full`**，待 Caddy 签发证书成功后再切换为 **`Full (strict)`**；后续续签会自动完成。
> 3. 服务器防火墙需放行 `80` 和 `443` 端口。

### 方式 B：单容器直接暴露端口（自行前置 Nginx / 仅内网使用）

可直接使用仓库根目录的 `docker-compose.yml` 与 `.env.example`：

```bash
cp .env.example .env
# 编辑 .env 设置 ANTORBIT_ADMIN_PASSWORD 和 ANTORBIT_PUBLIC_URL
docker compose up -d
```

---

## 二、服务端初始化（后台 `/admin`）

浏览器打开 `https://<你的域名>/admin/`（或 `http://<IP>:8000/admin/`），使用 `ANTORBIT_ADMIN_PASSWORD` 登录：

### 1. 生成 API Key
进入 **API 密钥** 页面 → 输入备注名（如 `my-pc`）→ 点击 **生成新 API Key** → 复制保存 `ao_...` 开头的密钥（仅展示一次）。

### 2. 配置通知渠道（Bark / ntfy）
进入 **通知渠道** 页面 → 点击 **+ 添加渠道**：

- **iOS（Bark）**：
  - 服务器地址：默认 `https://api.day.app`（支持自建 Bark）
  - Device Key：填入 Bark App 中的设备 Key
- **Android / 跨平台（ntfy）**：
  - 安卓客户端可从 [GitHub Releases](https://github.com/binwiederhier/ntfy-android)、[F-Droid](https://f-droid.org/packages/io.heckel.ntfy/) 或 Google Play 安装；服务端项目见 [binwiederhier/ntfy](https://github.com/binwiederhier/ntfy)。
  - 服务器地址：默认 `https://ntfy.sh`（支持自建 ntfy）
  - Topic：填写一个足够随机、不易猜测的主题名，并在手机端 ntfy App 订阅同一个 Topic。
  - 若使用带鉴权的自建/付费 ntfy，可填写 Access Token 或用户名/密码。

保存后点击渠道卡片上的 **测试** 按钮，手机收到推送即代表配置成功。

---

## 三、安装与配置 Antigravity 客户端插件

AntOrbit 插件包含三部分：
- **本地 stdio MCP Server**（`antorbit`）：由 `uvx` 自动拉取运行，支持直接打包本地目录上传或发送内联 HTML。
- **AntOrbit 发布 Skill**（`skills/antorbit/SKILL.md`）：教导 Ant 适配 `/s/<slug>/` 相对路径、接入 `/_antorbit/sdk.js` 并触发推送。
- **AntOrbit 网页生成规范 Skill**（`skills/antorbit-web-spec/SKILL.md`）：强约束统一的 **Slate + Sky 设计系统**、移动端/中文排版、4 类高频页面骨架（报告/看板/审批表/KV 工具），同时覆盖纯单文件 HTML、多文件静态站点与 Vite/Vue/React/Tailwind 构建项目。

### 步骤 1：安装 `uv`（提供 `uvx` 命令）

若本机尚未安装 `uv`，请先执行对应平台的安装命令，安装完成后**重开终端**验证 `uvx --version`：

- **Windows（PowerShell）**：
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **macOS / Linux**：
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

### 步骤 2：将 `plugin/` 目录安装到 Antigravity 插件目录

将本仓库中的 `plugin/` 文件夹完整复制为 Antigravity 全局插件目录下的 `antorbit` 文件夹：

- **Windows（PowerShell）**：
  ```powershell
  git clone --depth 1 https://github.com/YeTianXingShi/AntOrbit.git "$env:TEMP\AntOrbit"
  New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.gemini\config\plugins" | Out-Null
  Copy-Item -Recurse -Force "$env:TEMP\AntOrbit\plugin" "$env:USERPROFILE\.gemini\config\plugins\antorbit"
  Remove-Item -Recurse -Force "$env:TEMP\AntOrbit"
  ```
- **macOS / Linux**：
  ```bash
  git clone --depth 1 https://github.com/YeTianXingShi/AntOrbit.git /tmp/AntOrbit
  mkdir -p ~/.gemini/config/plugins
  rm -rf ~/.gemini/config/plugins/antorbit
  cp -r /tmp/AntOrbit/plugin ~/.gemini/config/plugins/antorbit
  rm -rf /tmp/AntOrbit
  ```

安装完成后目录结构应如下：

```text
~/.gemini/config/plugins/antorbit/
├── plugin.json
├── mcp_config.json
├── README.md
├── assets/
│   └── logo.svg
└── skills/
    ├── antorbit/
    │   └── SKILL.md
    └── antorbit-web-spec/
        ├── SKILL.md
        └── references/
            ├── design-tokens.md
            ├── frameworks-and-multifile.md
            └── page-patterns.md
```

> **推荐搭配安装的外部通用规范 Skill（可选）**：
> AntOrbit 内置的 `antorbit-web-spec` 负责统一视觉风格、移动端中文排版与 AntOrbit 交互闭环；搭配以下官方/社区通用 Skill 可进一步强化现代 Web 原生特性与 UI 细节质检：
> ```bash
> # Google Chrome 现代 Web 平台与 Baseline 最佳实践
> npx skills add GoogleChrome/modern-web-guidance
>
> # Vercel UI/UX 与无障碍细节审计清单
> npx skills add vercel-labs/agent-skills --skill web-design-guidelines
> ```

### 步骤 3：配置 `mcp_config.json`

打开 `~/.gemini/config/plugins/antorbit/mcp_config.json`（Windows 为 `C:\Users\<用户名>\.gemini\config\plugins\antorbit\mcp_config.json`），将 `ANTORBIT_URL` 与 `ANTORBIT_API_KEY` 替换为你的实际值：

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
        "ANTORBIT_URL": "https://your-domain.example.com",
        "ANTORBIT_API_KEY": "ao_your_api_key_here"
      }
    }
  }
}
```

> 提示：你也可以在服务端 `/admin` → **API 密钥** 页面底部直接一键复制自动填好地址与密钥的 `mcp_config.json`。

### 步骤 4：验证与启用

1. （可选）在终端手动预热一次 `uvx` 缓存，确认能拉取并启动：
   ```bash
   uvx --from "git+https://github.com/YeTianXingShi/AntOrbit.git#subdirectory=mcp" antorbit-mcp --help
   ```
2. 在 Antigravity 客户端的 **Customizations** 页面确认 **AntOrbit** 插件处于启用状态。
3. 新开一轮对话，直接对 Ant 说：
   - “帮我生成一个测试网页发布到 AntOrbit，并推送链接到我手机”
   - “帮我发一条手机测试通知”

### 升级插件与常见问题

- **升级 MCP Server 到最新版本**：`uvx` 会缓存 git 仓库，升级时可手动刷新缓存：
  ```bash
  uvx --refresh --from "git+https://github.com/YeTianXingShi/AntOrbit.git#subdirectory=mcp" antorbit-mcp --help
  ```
- **本地开发调试模式**：如果你修改了本地仓库的 `mcp/` 代码，可以把 `mcp_config.json` 中的 `--from` 改为本地路径（例如 `E:/zhenProject/AntOrbit/mcp`）。
- **提示 `ANTORBIT_URL` / `ANTORBIT_API_KEY` 未配置**：检查 `mcp_config.json` 的 JSON 语法是否正确，且 `ANTORBIT_URL` 末尾不要有多余路径（只需填 `https://your-domain.example.com`）。
- **页面资源 404**：AntOrbit 使用路径前缀 `/s/<slug>/` 托管站点，页面中静态资源请务必使用相对路径（`./app.js`、`assets/a.png`），Vite/SPA 构建需配置 `base: './'`。

---

## 四、MCP 工具一览

| 工具名 | 说明 |
| --- | --- |
| `publish_site` | 发布或更新站点（支持传本地目录 `directory` 自动打包 ZIP，或直接传内联 `html`），支持密码、TTL、交互开关及发布即推送 |
| `list_sites` | 列出所有已托管站点及访问统计 |
| `get_site` | 查看指定 `slug` 站点的详情 |
| `update_site` | 在不重新上传文件的情况下更新站点标题、密码、TTL、交互与推送设置 |
| `delete_site` | 永久删除站点及其静态文件、表单提交和 KV 数据 |
| `get_submissions` | 拉取站点收到的表单/审批提交记录 |
| `kv_list` / `kv_get` / `kv_set` / `kv_delete` | 读取、写入或删除站点的轻量 JSON KV 状态 |
| `list_channels` | 查看服务端可用的通知渠道列表（不含敏感凭证） |
| `send_notification` | 向指定渠道或默认渠道发送推送（支持点击跳转 `url`、紧急级别 `level` 与分组 `group`） |

---

## 五、内置浏览器 SDK（`/_antorbit/sdk.js`）

当站点开启 `allow_submit=true` 或 `kv_mode="read" | "readwrite"` 时，网页引入 `/_antorbit/sdk.js` 即可直接交互：

```html
<script src="/_antorbit/sdk.js"></script>
<script>
  // 提交表单 / 审批意见
  await window.AntOrbit.submit({ decision: 'approve', comment: 'LGTM' });

  // 读写轻量 JSON KV 状态
  const count = (await window.AntOrbit.kv.get('likes')) || 0;
  await window.AntOrbit.kv.set('likes', count + 1);
</script>
```

---

## 六、项目结构与本地开发

```text
AntOrbit/
├── server/                       # Python FastAPI 服务端（托管、交互 API、Bark/ntfy 推送、SQLite）
├── web/                          # Vue 3 + Vite + Tailwind CSS 管理后台（/admin）
├── mcp/                          # 本地 stdio Python MCP Server（antorbit-mcp）
├── plugin/                       # Antigravity Plugin（plugin.json、mcp_config.json、SKILL.md、logo）
├── Dockerfile                    # 多阶段构建（Node 22 + Python 3.12）
├── docker-compose.yml
└── .github/workflows/docker.yml  # 自动测试 + 构建推送 linux/amd64 镜像到 GHCR
```

```bash
# 运行服务端测试
uv run --project server --extra dev pytest -v server/tests

# 运行 MCP Server 测试
uv run --project mcp --extra dev pytest -v mcp/tests

# 本地启动服务端（开发模式）
uv run --project server uvicorn app.main:app --app-dir server --reload --port 8000
```
