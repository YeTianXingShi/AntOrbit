# AntOrbit

A self-hosted online website publishing and notification push platform built for the **Antigravity** client.

## Overview

AntOrbit consists of two parts:

1. **AntOrbit Server** (`server/` + `web/`) — Single-container Docker service (Python FastAPI + SQLite + Vue 3 Admin UI) for:
   - Path-based static & SPA site hosting (`/s/<slug>/`) with optional password protection and TTL auto-expiration
   - Lightweight interactive backend (form submissions + JSON KV store + built-in `/_antorbit/sdk.js`)
   - Notification push engine (Bark & ntfy built-in, extensible provider architecture)
   - Built-in Web Admin UI (`/admin`)
2. **AntOrbit Antigravity Plugin** (`plugin/` + `mcp/`) — Local stdio Python MCP Server + `SKILL.md` enabling Ant to publish local directories or inline HTML, read form submissions/KV state, and push notifications.
