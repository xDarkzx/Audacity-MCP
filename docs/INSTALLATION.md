# Installation Guide

Get AudacityMCP running in 3 steps: **enable the Audacity plugin → install AudacityMCP → connect your AI client**.

---

## Step 1: Enable mod-script-pipe in Audacity

AudacityMCP talks to Audacity through a built-in scripting plugin. You just need to flip it on.

1. Open **Audacity**
2. Go to **Edit → Preferences** (Windows/Linux) or **Audacity → Preferences** (macOS)
3. Click **Modules** in the left sidebar
4. Set `mod-script-pipe` to **Enabled**
5. Click **OK** and **restart Audacity**

That's it. The plugin creates named pipes that AudacityMCP connects to automatically.

> **Keep Audacity open** — the connection only works while Audacity is running.

## Step 2: Install AudacityMCP

### Option A: One-click installer (easiest)

- **Windows:** Download [`install.bat`](../install.bat) from the repo → double-click it
- **macOS / Linux:** Run this in your terminal:
  ```bash
  curl -fsSL https://raw.githubusercontent.com/xDarkzx/Audacity-MCP/main/install.sh | bash
  ```

The installer handles Steps 2 and 3 for you — skip to [Verify It Works](#verify-it-works).

### Option B: pip install from PyPI (recommended)

```bash
pip install audacity-mcp
```

That's it. This gives you the `audacity-mcp` command. No git clone needed.

### Option C: From source (for developers)

<details>
<summary>Click to expand</summary>

```bash
git clone https://github.com/xDarkzx/Audacity-MCP.git
cd AudacityMCP
pip install -e .
```

When running from source, use `python -m server.main` anywhere this guide says `audacity-mcp`.

To include dev/test dependencies:

```bash
pip install -e ".[dev]"
```

</details>

## Step 3: Connect Your AI Client

Pick your client below. Each section shows the **complete config file** — copy the whole thing, change the path, and you're done.

### Claude Desktop

**Option A: Installed with pip** (recommended — simplest config)

If you installed via `pip install audacity-mcp` or the one-click installer, your config is just:

```json
{
  "mcpServers": {
    "audacity": {
      "command": "audacity-mcp"
    }
  }
}
```

**Option B: Running from source** (no pip install)

If you skipped `pip install` and want to run directly from the cloned repo, you need to point the config at your Python and the repo folder. Here's a **complete, working config file** — just change the two paths:

```json
{
  "mcpServers": {
    "audacity": {
      "command": "C:\\Users\\YourName\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
      "args": ["-m", "server.main"],
      "cwd": "C:\\Users\\YourName\\Projects\\AudacityMCP"
    }
  }
}
```

> **How to find your Python path:** Open a terminal and run `where python` (Windows) or `which python` (macOS/Linux). Copy that path into the `command` field.
>
> **How to set cwd:** This is the folder where you cloned AudacityMCP. It must contain the `server/` folder inside it.

**Already have other stuff in your config?** That's fine — just add the `"audacity"` key inside the existing `mcpServers`, or add `mcpServers` alongside your other keys:

```json
{
  "mcpServers": {
    "audacity": {
      "command": "audacity-mcp"
    },
    "some-other-server": {
      "command": "some-other-command"
    }
  }
}
```

<details>
<summary>Config file locations (if you prefer to edit manually)</summary>

- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

</details>

Save the config and **restart Claude Desktop**.

### Claude Code (CLI)

```bash
claude --mcp-server audacity=audacity-mcp
```

Or add to your project's `.mcp.json` for persistent config:

```json
{
  "mcpServers": {
    "audacity": {
      "command": "audacity-mcp",
      "type": "stdio"
    }
  }
}
```

### Cursor

1. Open **Settings** → **Tools & MCP** → **New MCP Server**
2. Set type to `command`, enter `audacity-mcp`
3. Done

Or create `.cursor/mcp.json` in your project root (or `~/.cursor/mcp.json` for global):

```json
{
  "mcpServers": {
    "audacity": {
      "command": "audacity-mcp"
    }
  }
}
```

<details>
<summary>Running from source? Use this config instead</summary>

```json
{
  "mcpServers": {
    "audacity": {
      "command": "C:\\Users\\YourName\\AppData\\Local\\Programs\\Python\\Python311\\python.exe",
      "args": ["-m", "server.main"],
      "cwd": "C:\\Users\\YourName\\Projects\\AudacityMCP"
    }
  }
}
```

</details>

### Google Antigravity

1. Open an **Agent session**
2. Click **...** at the top of the Agent pane → **MCP Servers** → **Manage MCP Servers**
3. Click **View raw config**
4. Add to `mcp_config.json`:

```json
{
  "mcpServers": {
    "audacity": {
      "command": "audacity-mcp"
    }
  }
}
```

### Other MCP Clients

AudacityMCP uses **stdio transport**. Point any MCP-compatible client at the `audacity-mcp` command.

---

## Why Do I Need `command` and `cwd`?

The `command` field tells your AI client **what program to run** — it can't be removed. When you do `pip install -e .`, it creates the `audacity-mcp` shortcut command so you don't need a full Python path.

If you didn't pip install, you need the full Python path in `command` because the AI client needs to know where Python is on your system. The `cwd` tells it where the AudacityMCP code lives.

**TL;DR:** Run `pip install audacity-mcp` and your config is just `"command": "audacity-mcp"` — no paths needed.

---

## Important: Audacity Must Be Open

> **AudacityMCP does NOT open Audacity for you.** You must have Audacity running before you start chatting. The AI client cannot launch or control Audacity unless it's already open with mod-script-pipe enabled.

**Every time you want to use AudacityMCP:**
1. Open **Audacity** first
2. Load or record your audio
3. Then go to your AI client and start chatting

If Audacity isn't running, you'll get a "pipe not found" error.

---

## Verify It Works

1. **Open Audacity** (with mod-script-pipe enabled)
2. Open your AI client
3. Ask it:

```
"Get info about the current Audacity project"
```

If you see track/project info come back, you're all set.

---

## Transcription Setup (Optional)

AudacityMCP includes local transcription via [faster-whisper](https://github.com/SYSTRAN/faster-whisper). It needs a one-time setup before first use.

**Run these commands to install and pre-download the model:**

```bash
python -c "from faster_whisper import WhisperModel; WhisperModel('small', compute_type='auto'); print('Model ready!')"
```

This downloads the `small` model (~488 MB) — the best balance of speed and accuracy. You'll see download progress — wait for "Model ready!" before using transcription in Claude.

> **Why do this first?** If you skip this step, the model will download during your first transcription request, which can cause a timeout. Pre-downloading means transcription works instantly.

**Want a different model?** Replace `'base'` with your choice:

| Model | Download | RAM | Best For |
|-------|----------|-----|----------|
| `tiny` | 75 MB | ~1 GB | Quick drafts |
| `base` | 145 MB | ~1 GB | General use (recommended) |
| `small` | 488 MB | ~2 GB | Good accuracy |
| `medium` | 1.5 GB | ~5 GB | High accuracy |
| `large-v3` | 3.1 GB | ~10 GB | Best accuracy |

**GPU acceleration** (optional, NVIDIA only — highly recommended):

GPU makes transcription **10-20x faster**. A 3-minute file takes ~10 seconds on GPU vs 4+ minutes on CPU.

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

That's it — AudacityMCP automatically detects GPU and uses it. No CUDA toolkit install needed. If you don't have an NVIDIA GPU, skip this — CPU works fine, just slower on long files.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| "Load this module?" popup on every launch | mod-script-pipe is set to "Ask" instead of "Enabled" | Edit → Preferences → Modules → change mod-script-pipe to **Enabled** (not Ask) → OK → restart |
| "Pipe not found" | Audacity isn't running or mod-script-pipe isn't enabled | Open Audacity, enable the module (Step 1), restart |
| "Pipe timeout" | Audacity is busy with a long operation | Wait for it to finish — some effects take up to 2 minutes |
| Connection works once then fails | Pipe disconnected (Audacity crash/restart) | Just try again — AudacityMCP auto-reconnects |
| "Access denied" (Windows) | Running Audacity and client as different users | Run both as the same user (don't mix admin/non-admin) |
| Pipes missing in /tmp (macOS/Linux) | Audacity didn't create them | Check Audacity is running, check console for errors |
| "No module named faster_whisper" | Not installed | `pip install faster-whisper` |
| Model download fails | Network issue | Check internet and retry — models cache after first download |
| Config not working | Wrong path or JSON syntax | Copy the complete example above, replace paths, validate JSON at jsonlint.com |
