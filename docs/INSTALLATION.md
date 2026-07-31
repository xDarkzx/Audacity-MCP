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

`install.bat`/`install.sh` only install the code sitting right next to them — they don't fetch anything from PyPI or GitHub themselves. So get the whole repo first, then run the script from inside it:

1. Click the green **Code** button on the [repo page](https://github.com/xDarkzx/Audacity-MCP) → **Download ZIP** → extract it, **or** clone it:
   ```bash
   git clone https://github.com/xDarkzx/Audacity-MCP.git
   cd Audacity-MCP
   ```
2. Run the installer from inside that folder:
   - **Windows:** double-click `install.bat`, or from the same terminal: `.\install.bat`
   - **macOS / Linux:** `bash install.sh`

The installer handles Steps 2 and 3 for you — skip to [Verify It Works](#verify-it-works). It explains what it's about to do and asks for confirmation before touching either Audacity's or Claude Desktop's config file, and always backs up an existing file first.

> **Want to see everything it would do before it does it?** Read the script first — it's plain text, nothing hidden (`cat install.sh` / open `install.bat` in Notepad) — or add `--dry-run` to print every action it would take (installing the package, editing Audacity's config, editing Claude Desktop's config) without changing anything:
> ```bash
> bash install.sh --dry-run
> ```
> Windows: `install.bat --dry-run`.
>
> If the script ever gets separated from the rest of the repo folder (moved or downloaded on its own), it will refuse to run with a clear error instead of trying to fetch the code from somewhere else.

### Option B: pip install from PyPI (recommended)

```bash
pip install audacity-mcp-server
```

That's it. This gives you the `audacity-mcp` command (the PyPI package is named `audacity-mcp-server`, but the installed command is still `audacity-mcp`). No git clone needed.

### Option C: From source (for developers)

<details>
<summary>Click to expand</summary>

```bash
git clone https://github.com/xDarkzx/Audacity-MCP.git
cd AudacityMCP
pip install -e .
```

When running from source, use `python -m audacity_mcp.main` anywhere this guide says `audacity-mcp`.

To include dev/test dependencies:

```bash
pip install -e ".[dev]"
```

</details>

## Step 3: Connect Your AI Client

Pick your client below. Each section shows the **complete config file** — copy the whole thing, change the path, and you're done.

### Claude Desktop

**Option A: Installed with pip** (recommended — simplest config)

If you installed via `pip install audacity-mcp-server` or the one-click installer, your config is just:

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
      "args": ["-m", "audacity_mcp.main"],
      "cwd": "C:\\Users\\YourName\\Projects\\AudacityMCP"
    }
  }
}
```

> **How to find your Python path:** Open a terminal and run `where python` (Windows) or `which python` (macOS/Linux). Copy that path into the `command` field.
>
> **How to set cwd:** This is the folder where you cloned AudacityMCP. It must contain the `audacity_mcp/` folder inside it.

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
<summary>Recommended: edit the config through Claude Desktop itself</summary>

This is the most reliable way to edit the config manually — Claude Desktop opens its own real config file, so there's no risk of editing the wrong one (see the Windows Store note below for why that matters).

1. Open **Claude Desktop**
2. Click **Settings** (gear icon)
3. Go to the **Developer** tab
4. Click **Edit Config** — this opens `claude_desktop_config.json` directly
5. Add the `"audacity"` entry inside the existing `"mcpServers"` block (see the examples above for the exact JSON), keeping any other servers you already have configured
6. Save the file and **restart Claude Desktop**

</details>

<details>
<summary>Config file locations (if you'd rather find the file yourself)</summary>

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows (standard install):** `%APPDATA%\Claude\claude_desktop_config.json`
- **Windows (Microsoft Store build)**: `%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\claude_desktop_config.json` — the Store build redirects `%APPDATA%` into its own isolated package folder, so the standard path above is a dead file it never reads. The `<id>` segment varies per install; look for a folder under `%LOCALAPPDATA%\Packages\` starting with `Claude_`. If you're not sure which build you have, use the **Edit Config** method above instead — it always opens the correct file regardless of install type.

</details>

Save the config and **restart Claude Desktop** — for the Microsoft Store build, fully quit it first (closing the window can leave it running in the background).

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
      "args": ["-m", "audacity_mcp.main"],
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

**TL;DR:** Run `pip install audacity-mcp-server` and your config is just `"command": "audacity-mcp"` — no paths needed.

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
audacity-mcp-setup-gpu
```

Not comfortable with a terminal? Download [`setup_gpu.bat`](../setup_gpu.bat) (Windows) or [`setup_gpu.sh`](../setup_gpu.sh) (macOS/Linux) from the repo and double-click it (or run it) instead — same thing, no typing required.

This one command detects your GPU, installs the two required packages (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`) into the same Python environment `audacity-mcp` runs from, and then actually loads a model on the GPU to confirm it works — instead of you finding out later that transcription silently fell back to CPU. No CUDA toolkit install needed.

> **Important:** GPU acceleration requires an **NVIDIA** GPU specifically — it uses faster-whisper's CTranslate2 backend, which doesn't support AMD or Intel graphics, or Apple Silicon/macOS (no ROCm/oneAPI/Metal path). This isn't something a driver update can fix; if your GPU isn't NVIDIA, transcription runs on CPU, full stop. If it *is* NVIDIA, the model doesn't matter — GeForce, Quadro, RTX Axxx workstation cards, older GTX — any of them work as long as the driver is reasonably current. "GeForce" vs "not GeForce" isn't the deciding factor.

**Don't have an NVIDIA GPU, or ran into the manual pip install before this script existed?** `audacity-mcp-setup-gpu` is safe to run either way — it detects "no NVIDIA GPU" cleanly and just confirms CPU is fine, no errors.

<details>
<summary>Manual install / troubleshooting (if you'd rather not use the script)</summary>

```bash
pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

Make sure this installs into the **same** Python environment that runs `audacity-mcp` — a common failure mode is installing these into a different venv or system Python than the one Claude Desktop actually launches. Run `where audacity-mcp` (Windows) / `which audacity-mcp` (macOS/Linux) to see which install is in use, then use that same Python's `pip`.

**To verify it's actually using the GPU** (rather than silently falling back to CPU):
- Watch Task Manager → Performance → GPU while transcribing — usage should spike.
- Or run `nvidia-smi` right as a transcription starts — you should see a `python.exe`/`python` process listed with memory allocated.
- Or reproduce the exact code path directly: `python -c "from faster_whisper import WhisperModel; WhisperModel('tiny', device='cuda', compute_type='float16'); print('GPU OK')"`. If this throws an error, that's the same error the server swallows internally before falling back to CPU.

</details>

<details>
<summary>Ran <code>audacity-mcp-setup-gpu</code>, it said success, but transcription is STILL on CPU?</summary>

This means the script installed and verified GPU support in one Python environment, but Claude Desktop is launching `audacity-mcp` from a **different** one — so it can't see what was just installed. This mainly happens if you have more than one Python installed (e.g. python.org **and** a Microsoft Store one), or if you set up AudacityMCP from source and the config still points at an old/moved Python — a normal one-Python, one-sitting install won't hit this.

To fix it:

1. Note the Python path `audacity-mcp-setup-gpu` printed, e.g. `Installing nvidia-cublas-cu12 and nvidia-cudnn-cu12... (into C:\Python314\python.exe)` — that exact path is the one that has GPU support.
2. Open your Claude Desktop config: `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS).
3. Find the `"audacity"` entry under `"mcpServers"`. If `"command"` is the plain string `"audacity-mcp"`, run `where audacity-mcp` (Windows) / `which audacity-mcp` (macOS) and check the path it resolves to — is it tied to the *same* Python as step 1?
4. If it doesn't match (or you're not sure), edit the entry to point directly at the Python from step 1:
   ```json
   "audacity": {
     "command": "C:\\Python314\\python.exe",
     "args": ["-m", "audacity_mcp.main"]
   }
   ```
   (macOS/Linux: use that platform's path instead, no double backslashes needed.)
5. Save, restart Claude Desktop, and try transcription again.

We deliberately don't auto-edit this file for you — it's shared with any other MCP servers you've configured, and a script silently rewriting it is more risk than it's worth. This is a five-minute manual fix once you know what to look for.

</details>

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
| Transcription works but is slow / seems to be on CPU | GPU packages missing or no NVIDIA GPU | Run `audacity-mcp-setup-gpu` — it detects your GPU, installs what's needed, and confirms GPU transcription actually works (or tells you why not) |
| `audacity-mcp-setup-gpu` said success, but transcription is still on CPU | Claude Desktop is launching `audacity-mcp` from a *different* Python than the one the script just verified | See ["Ran `audacity-mcp-setup-gpu`... still on CPU?"](#transcription-setup-optional) above — usually a multi-Python or from-source config pointing at a stale/different interpreter |
| Model download fails | Network issue | Check internet and retry — models cache after first download |
| Long file's transcript/labels stop partway through, no error shown | Fixed in v0.1.14 — a background job watchdog was killing jobs after 10 minutes of *total* runtime instead of 10 minutes of no progress, cutting off long files mid-way through labeling | Update to v0.1.14+ (`pip install --upgrade audacity-mcp`). If it still happens on a very long file, it's a genuinely stuck job now, not a false timeout |
| Config not working | Wrong path or JSON syntax | Copy the complete example above, replace paths, validate JSON at jsonlint.com |
| Installer says config not found, but Audacity runs fine | You're running a **portable** Audacity (a `Portable Settings` folder next to the executable) | It stores `audacity.cfg` there instead of the normal location — enable `mod-script-pipe` manually (Preferences → Modules) |
| Ran `install.bat`, it said "Configured Claude Desktop", but Audacity never shows up as a tool in Claude | Claude Desktop installed via the **Microsoft Store** redirects its config into an isolated per-package folder — `install.bat` versions before the fix (check `CHANGELOG.md`) only wrote to the standard `%APPDATA%\Claude\` path, which the Store build never reads | Update to the latest `install.bat` and re-run it (it now writes to both locations), or add the config manually — see ["Recommended: edit the config through Claude Desktop itself"](#claude-desktop) above, which always finds the right file regardless of install type |
