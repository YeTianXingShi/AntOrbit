# AntOrbit Antigravity 插件

本插件为反重力（Antigravity）提供：
- **`antorbit` 本地 stdio MCP Server**（通过 `uvx` 运行）：支持直接打包上传本地站点目录或内联 HTML、管理站点、查询表单提交与 KV 状态，以及触发 Bark / ntfy 通知推送。
- **`antorbit` Skill**（`skills/antorbit/SKILL.md`）：指导 Ant 构建适配 `/s/<slug>/` 相对路径的静态与交互网页，并正确调用 `/_antorbit/sdk.js` 与通知推送。

---

## 安装步骤

### 1. 安装前置工具 `uv`

本插件通过 `uvx` 启动本地 Python MCP Server。若尚未安装 `uv`：

- **Windows（PowerShell）**：
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```
- **macOS / Linux**：
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

安装后重新打开终端，确认 `uvx --version` 正常输出。

### 2. 复制插件到 Antigravity 插件目录

将本 `plugin/` 目录复制为全局插件目录下的 `antorbit` 文件夹：

- **Windows**：`C:\Users\<用户名>\.gemini\config\plugins\antorbit\`
- **macOS / Linux**：`~/.gemini/config/plugins/antorbit/`

### 3. 配置服务端地址与 API Key

编辑安装后的 `mcp_config.json`，填入你的 AntOrbit 服务端地址（不含末尾 `/`）和在 `/admin` 生成的 API Key：

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
        "ANTORBIT_API_KEY": "ao_replace_with_your_api_key"
      }
    }
  }
}
```

### 4. 启用与验证

1. 在 Antigravity 的 **Customizations** 页面确认 **AntOrbit** 插件已启用。
2. 新一轮对话中即可直接使用，例如：“做一个测试网页发到 AntOrbit，并推送链接给我”。

---

## 升级与本地开发

- **刷新 `uvx` 缓存以拉取最新 MCP 代码**：
  ```bash
  uvx --refresh --from "git+https://github.com/YeTianXingShi/AntOrbit.git#subdirectory=mcp" antorbit-mcp --help
  ```
- **本地源码调试**：将 `mcp_config.json` 中的 `--from` 参数改为本地 `mcp/` 路径（例如 `E:/zhenProject/AntOrbit/mcp`）。
