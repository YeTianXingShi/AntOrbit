# AntOrbit Antigravity Plugin

This plugin bundles:
- **`antorbit` local stdio MCP Server** (`mcp_config.json`, launched via `uvx`)
- **`antorbit` Skill** (`skills/antorbit/SKILL.md`) teaching Ant how to build path-safe interactive sites, integrate `/_antorbit/sdk.js`, and push Bark/ntfy notifications.

## Installation

1. Make sure [`uv`](https://docs.astral.sh/uv/) is installed so `uvx` is available on your `PATH`.
2. Copy this `plugin/` directory to your Antigravity plugins folder as `antorbit`:
   - **Windows**: `C:\Users\<YOU>\.gemini\config\plugins\antorbit\`
   - **macOS / Linux**: `~/.gemini/config/plugins/antorbit/`
3. Edit `mcp_config.json` inside that installed plugin folder and set:
   - `ANTORBIT_URL`: Your AntOrbit server base URL (e.g., `https://orbit.example.com`)
   - `ANTORBIT_API_KEY`: An API Key created in your AntOrbit `/admin` panel (or via `ANTORBIT_API_KEY` env var on the server)
4. Enable the **AntOrbit** plugin in Antigravity Customizations.

> **Local Development**: To run the MCP server from your local checkout instead of GitHub, change `--from` in `mcp_config.json` to your local `mcp/` folder path (e.g., `E:/zhenProject/AntOrbit/mcp`).
