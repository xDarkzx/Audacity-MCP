# Changelog

All notable changes to AudacityMCP will be documented in this file.

## [0.1.20] - 2026-08-04

### Label Tools: From "Create Only" to a Full Editing Workflow

The Labels category could create labels but not read an index, rename, delete, or act on the audio underneath one. 13 new tools (131 → 144), no changes to existing tool behavior. See [PODCASTS.md](PODCASTS.md) for the transcript-based editing workflow (podcasts, interviews, lectures) this was built around — worth reading if that's not your use case, since it explains where these tools do and don't apply.

- **Read, search, edit:** `label_list` / `label_find` return parsed labels with the flat index `label_edit`/`label_delete` need; `label_edit` updates only the fields passed; `label_add_batch` validates a whole batch (up to 500) before sending anything, so one bad item can't leave a half-written list.
- **Delete a label without touching audio:** `label_delete` — Audacity has no "delete label N" command, so this selects the label's own span on its own track and split-deletes it, restoring any other label caught as collateral in the same region.
- **Delete one labeled take's audio by index:** `label_delete_audio_at` — deletes the audio under one label and clears the leftover marker it leaves behind. A custom composite (`SelAllTracks` → `SelectTime` → `Delete`/`SplitDelete` → cleanup), since Audacity has no single command for it. Originally named `label_delete_region`; renamed after live testing confirmed correct behavior but flagged the name as one letter from `label_delete_regions` below despite doing something different (by-index vs. by-selection).
- **Act on every labeled region in the current selection:** `label_cut_regions`, `label_delete_regions`, `label_silence_regions`, `label_split_regions`, `label_join_regions` — thin wrappers over Audacity's own labeled-region commands.
- **Export:** `label_export_chapters` (simple/cue/Podlove chapter formats) and `label_export_audio_segments` (per-label audio files, skipping point labels and never overwriting existing files).
- **`analyze_label_sounds`** now exposes all 8 `LabelSounds` parameters (previously 3): `measurement`, `label_type`, `pre_offset`, `post_offset`, `label_text`. Only sent when explicitly passed, so existing calls are unaffected. Open question worth checking before merge: the scripting reference documents `threshold`/`sil-dur`/`snd-dur`, but the three pre-existing parameters are sent as `Threshold`/`MinSilence`/`MinSound` — left as-is since it's a working call, but the duration parameters may never have reached Audacity if the documented names are the real ones.

**Testing:** `tests/test_label_tools.py` grew from 8 to 71 tests (suite total 92 → 161). Confirmed against a running Audacity: `label_delete`, `label_delete_audio_at`, `label_delete_regions`, `label_silence_regions`, `label_split_regions`, `label_join_regions`, `label_import`. Not yet independently live-tested: `label_cut_regions`, the new `LabelSounds` parameter names, and both export tools.

**Docs:** added `PODCASTS.md` (linked from the README); notes that `transcribe_to_file(format="srt")` followed by `label_import` is a working alternative to `transcribe_to_labels`, since Audacity's own label importer reads SRT directly (its `txt`/`vtt` formats do not import cleanly today).

### CI, Linting, and Release Process Improvements

Standard process maturity as the project grows — none of this changes the package itself, and it's aimed at keeping the project reliable and easy to contribute to, not at any contributor's intent.

- **Lint in CI**: added `ruff`, scoped to real bugs and security-relevant patterns (`F`/`S` rule categories) rather than style or formatting, so it gives fast, useful feedback without nitpicking anyone's formatting preferences — runs once per CI pass rather than duplicated across the full OS/Python test matrix, since static analysis doesn't vary by platform. Cleaned up everything it found in the existing codebase (a handful of dead imports and harmless typos; nothing behavioral) so the check starts clean for everyone.
- **Branch protection on `main`**: merging now requires every CI check to pass and at least one review — the same standard workflow most established open-source projects use, so contributors get a clear, predictable bar for what "ready to merge" means.
- **Dependabot**: enabled for both Python dependencies and GitHub Actions versions, plus automatic security-update PRs and vulnerability alerts, so the project stays current with upstream fixes automatically.
- **`SECURITY.md`** and GitHub's private vulnerability reporting: gives anyone a clear, documented, private channel to responsibly report an issue.
- Confirmed the existing CI setup already follows GitHub's recommended safe defaults (the `pull_request` trigger rather than `pull_request_target`, and Trusted Publishing via OIDC for PyPI with no stored token) — good practice already in place, now confirmed and documented.
- GitHub Actions bumped to their latest majors (`checkout`, `setup-python` to v7; `upload-artifact` to v7; `download-artifact` to v8), keeping the build/publish pipeline current.

## [0.1.19] - 2026-08-01

### install.bat: `goto` Out of an if/else Block Silently Corrupted Script Flow

Found while adding better error logging to `install.bat`: a real, serious bug that has been present since the "Configure Claude Desktop now? (y/n)" prompt was first added in v0.1.16.

- **Root cause**: `goto` cannot safely jump out of the middle of an `if (...) else (...)` compound statement in cmd.exe. The interpreter parses the whole if/else as one unit, and a `goto` escaping mid-way corrupts its parse state - subsequent lines can be silently skipped, duplicated, or executed out of order, with no error shown. Three places in `install.bat` did exactly this: the winget-install-failure path, the pip-install-failure path (both added today), and the "answered n to Configure Claude Desktop now?" path (present since v0.1.16). **The last one means answering "n" could have been silently ignored and the config touched anyway** - the opposite of what was asked for.
- Caught it concretely: added a diagnostic log file + "report this" message on every failure path (see below), tested the failure path in isolation, and found the script printed the error then barreled straight through the remaining steps to "SETUP COMPLETE" instead of stopping.
- **Fix**: every one of these now sets a plain flag variable inside the block instead of calling `goto` from within it, then checks that flag in a standalone statement immediately after the if/else closes (goto is only safe once execution is back at the top level, outside any block). Audited every remaining `goto` in the file - all others target labels from inside a plain `if (...)` with no accompanying `else`, which is safe.
- `install.sh` was never affected - bash doesn't have this pitfall, and its equivalent uses a real function call (`fail_exit()`), not a label jump.

### Better Error Visibility (Both Installers)

Prompted by an install failure report and the suspicion that more people silently give up than report bugs.

- Both scripts now write a log (`install-log.txt`, next to the script, overwritten each run) capturing Python version, each step reached, the resolved `audacity-mcp` command, and the Claude Desktop config merge result for every config file touched.
- Every failure path now prints where the log is and a link to file an issue with it attached, instead of just an error message and a dead end.

### Follow-up fix (same release): Claude Desktop Config Merge Was Silently Failing

Testing the above surfaced a second bug in the same code path, caught and fixed before wider use: the JSON merge logic was still passed to Python as one long `-c "..."` command-line string, and combined with the new `2>>"logfile"` stderr-capture redirect above, cmd.exe's naive same-line paren scanner corrupted the string being executed, producing a `SyntaxError` instead of running the merge. Separately, the merge logic itself had `cmd != 'audacity-mcp'` silently lose its `!` to `setlocal enabledelayedexpansion` (the same character-eating issue as `installed successfully!` elsewhere in this file), turning it into an assignment instead of a comparison. The fallback message shown on a genuine failure also hardcoded the broken bare `"audacity-mcp"` command instead of the real resolved path.

- **Fix**: the merge logic now lives in a real temporary `.py` file (`%TEMP%\audacity_mcp_merge_config.py`), invoked as `python "file.py"` instead of an inline one-liner - removing almost everything that could trip cmd's parser. The `!=` was rewritten as `not (... == ...)` to avoid the delayed-expansion pitfall entirely. The fallback message now shows the real resolved path. Failures capture Python's actual traceback into `install-log.txt`, and mention that a running Claude Desktop holding the file open is a common cause.
- **Verified against the real system**: ran the fixed installer against this machine's actual multi-server Claude Desktop config (both the standard and Microsoft Store paths, one with unrelated app-internal keys alongside `mcpServers`) with Claude Desktop open. Confirmed the `audacity` entry was correctly upgraded to the resolved path on both files, every other configured server and every unrelated top-level key was byte-for-byte untouched, and `.bak` backups were created. Also verified the "answered n" decline path leaves the file byte-for-byte untouched (checksum-verified) and the malformed-JSON error path produces a real captured traceback.

## [0.1.18] - 2026-08-01

### Claude Desktop Shows No Servers: Bare `"audacity-mcp"` Command Not Resolvable

A user reported Claude Desktop showed no MCP servers at all after installing, even though the config file had a correctly-formed `"audacity"` entry with `"command": "audacity-mcp"`.

- **Root cause**: that bare command relies on `audacity-mcp.exe`'s folder being on PATH for whatever process launches it. A terminal can resolve it fine (`where audacity-mcp` succeeds) while Claude Desktop — a GUI app that can be running with a PATH cached from before Python/pip were installed, or simply launched in an environment that doesn't inherit the same PATH as a freshly opened terminal — fails to spawn it, silently. Since Audacity was this user's only configured server, "no servers show" and "Audacity fails to spawn" were the same event.
- **Fix**: both installers now resolve the actual installed script's absolute path via the target Python's own `sysconfig.get_path('scripts')` (authoritative regardless of PATH) and write that full path into the Claude Desktop config instead of a bare `"audacity-mcp"` string — eliminating the PATH dependency for Claude Desktop's process entirely.
- **Also fixes existing broken installs, not just new ones**: config writing switched from crude `findstr`/`grep` text-scanning to a real JSON parse/merge (`python -c "import json; ..."`, since Python is already a hard dependency). Re-running the installer now detects and upgrades an old broken bare `"audacity-mcp"` entry left over from a previous install to the resolved absolute path, while leaving every other already-configured MCP server completely untouched — previously, re-running only ever skipped silently if an `"audacity"` key already existed, broken or not.

## [0.1.17] - 2026-08-01

### PyPI Package Renamed to `audacity-mcp-server`

Setting up the new tokenless PyPI publish workflow (see 0.1.16 below) surfaced that the `audacity-mcp` project on PyPI belongs to a different PyPI account than the one publishing this repo going forward, so Trusted Publishing couldn't be linked to it. Rather than depend on access to that other account, the package is published under a new name this account owns outright.

- PyPI package renamed: `audacity-mcp` → **`audacity-mcp-server`** (`pip install audacity-mcp-server`).
- The installed CLI command is unaffected — it's still `audacity-mcp` (and `audacity-mcp-setup-gpu`), since `[project.scripts]` in `pyproject.toml` is independent of the package's PyPI name. **No existing Claude Desktop config needs to change.**
- Updated `README.md` and `docs/INSTALLATION.md` pip-install references accordingly.
- The old `audacity-mcp` PyPI project is not affiliated with this repo and will not receive further updates from here.

## [0.1.16] - 2026-08-01

### install.bat/install.sh: Claude Desktop Never Getting Configured on Windows, and a Redundant Reinstall

A user reported the installer didn't seem to actually connect AudacityMCP to Claude Desktop.

- **Root cause**: the Microsoft Store / MSIX build of Claude Desktop redirects its `%APPDATA%` writes into an isolated per-package folder (`%LOCALAPPDATA%\Packages\Claude_<id>\LocalCache\Roaming\Claude\`) instead of the standard `%APPDATA%\Claude\` path. `install.bat` only ever wrote to the standard path, which that build never reads — so the config step silently did nothing useful for anyone on the Store build.
- **Fix**: config writing is now a shared subroutine, called once for the standard path and once for every `Claude_*` folder found under `%LOCALAPPDATA%\Packages\`, so both install types get configured.

**The installer was also always re-fetching the package it was sitting right next to.** Both scripts ran `pip install audacity-mcp` unconditionally — fetching fresh from PyPI even when run from inside a just-cloned/downloaded copy of the repo, which is the only way you'd have `install.bat`/`install.sh` in the first place. That's a pointless redundant download, and it also meant the installer could install an older *published* version instead of whatever fixes were sitting in the local copy the user just got.

- Both scripts now always install from the local folder the script itself lives in (`pip install "<script's own folder>"`), never from PyPI or GitHub.
- If the script is ever separated from the rest of the repo (moved or downloaded standalone, no `pyproject.toml` next to it), it now refuses to run with a clear error instead of silently trying to fetch the code from somewhere else.
- Fixed a related display bug in `install.bat`'s Python check: `%PYVER%` was expanding at parse-time (before the `for /f` that sets it, inside the same `if (...)` block) so the detected version always printed blank — `Found Python  - already installed`. Switched to delayed expansion (`!PYVER!`).

**Other hardening in this pass, since the whole install flow was under review:**

- Added `--dry-run` (`-n` on macOS/Linux) to both scripts — prints every action (package install, Audacity config edit, Claude Desktop config edit) without changing anything.
- Both scripts now explain what the Claude Desktop config step does and ask for an explicit y/n confirmation *before* touching that file at all, not just before overwriting it — matching the existing confirmation already in place for Audacity's config.
- Stripped a handful of non-ASCII characters (`──`, `—`) from `install.bat` that could cause cmd.exe to misparse the file under some codepages; both scripts are now pure ASCII.
- Restructured (not removed) the Python-missing detection/auto-install flow in both scripts to be more reliable about skipping the winget/brew/apt/dnf/pacman install offer when Python is already present.
- Updated `README.md` and `docs/INSTALLATION.md` to match: Quick Start / Option A now walks through "download or clone the repo, then run the installer from inside it" instead of a standalone single-file download or `curl | bash` one-liner (which no longer works now that the script requires the repo around it).

## [0.1.15] - 2026-07-29

### Transcription: Wrong-Language Retries, and Model Re-Downloads

Two separate reports while using transcription on real files.

**Retrying a bad language auto-detect required switching tools entirely.** A user's English audio got auto-detected and transcribed as Japanese. Fixing it meant removing the label track and starting over — but `transcribe_to_labels` and `transcribe_to_file` hardcoded `task="transcribe"` and never exposed the parameter at all, so there was no way to retry the *same* tool with `task="translate"` (forces English output) or an explicit `language`. The only way to recover was switching to `transcribe_audio` and manually reconstructing the labels from its output — exactly the tangle it took another Claude session an extra half-dozen tool calls to work around.

- Added `task` to `transcribe_to_labels` and `transcribe_to_file`, matching `transcribe_audio`/`transcribe_selection`.
- Added docstring guidance across all four transcription tools: auto-detect can occasionally misidentify the language (background music, noise, short/ambiguous clips) — if you already know the language, pass it explicitly instead of trusting auto-detect, and retry with the *same* tool rather than switching.

**A model that was already downloaded appeared to re-download on first use.** `_get_cache_dir()` hardcoded `~/.cache/huggingface/hub`, ignoring `HF_HOME`/`HUGGINGFACE_HUB_CACHE`. The manual pre-download command in the setup docs uses huggingface_hub's own default resolution, which *does* honor those variables — so anyone who has ever redirected their HF cache (common for moving model storage to a bigger/different drive) would have the pre-downloaded model in one place and the running server hardcoded to look in another, re-downloading every time. Not reproduced on this dev machine (no mismatch here), but the hardcoded-path bug is real and independently verifiable in the source regardless.

- `_get_cache_dir()` now checks `HUGGINGFACE_HUB_CACHE`, then `HF_HOME`, before falling back to the hardcoded default — the fallback still exists for its original purpose (some MCP subprocesses on Windows can't resolve huggingface_hub's own default cache path).
- Added `tests/test_transcription.py::TestGetCacheDir` and extended `TestTranscribeToLabels`/`TestTranscribeToFile` for the `task` parameter.

## [0.1.14] - 2026-07-29

### Long Transcriptions Getting Silently Truncated

Reported by a user: a 48-minute file only got ~23 minutes labeled, a 4.5-hour file only got ~45 minutes labeled — both cut off partway through, no error shown.

- **Root cause**: `_cleanup_stale_jobs()` killed any transcription job running longer than `_STALE_JOB_TIMEOUT` (10 minutes) measured from **job start**, regardless of whether it was still actively progressing. The label-adding loop does a `SelectTime`+`AddLabel`+`SetLabel` round trip *per segment* — a multi-hour transcript can have thousands of segments, so that loop alone can legitimately run past 10 minutes even when working correctly. The next time `check_transcription_status` got polled after the 10-minute mark, it silently cancelled the still-running task mid-loop, leaving only whatever labels had been added so far.
- **Fix**: staleness is now measured from **time since last progress**, not time since start. Every step transition and every single label added now updates a `last_progress_at` timestamp; a job only gets killed after 10 minutes with *no* forward progress (i.e. actually stuck), not just for running long on a big file. Also threaded progress reporting through the transcription step itself (`_run_transcription` now accepts an `on_progress` callback, called per-segment), so a slow CPU transcription of a very long file can't hit the same wall before labeling even starts.
- Added `tests/test_transcription.py::TestStaleJobCleanup` and `TestRunTranscriptionProgress`.

## [0.1.13] - 2026-07-28

### Labels Overwriting Each Other

Reported by a user: transcribing with `add_labels=True` (or adding several labels via `label_add`/`label_add_at` in a row, e.g. asking Claude to mark episode boundaries in a long track) left every label blank except the first, which ended up with the *last* label's text.

- **Root cause**: `label_add`, `label_add_at`, and the transcription auto-labeling loop all called `SetLabel(Label=0, ...)` unconditionally after `AddLabel`. `AddLabel` doesn't report back the index of the label it just created, and `Label=0` doesn't mean "the label just added" — it means "the very first label in the project," full stop. So every `SetLabel` call kept retargeting that same first label, overwriting it each time, while every other newly-created label stayed blank.
- **Fix**: added `count_existing_labels()` (`audacity_mcp/tools/label_tools.py`) — queries `GetInfo Type=Labels`, parses the JSON, and counts labels already in the project. Since `AddLabel` appends, the new label's index is exactly that count (or `count + i` for the i-th label added in a batch, in `label_add`/`label_add_at`/the transcription loop). Confirmed via a related [Audacity GitHub issue](https://github.com/audacity/audacity/issues/1577) that label indices are assigned in creation order, 0-based — the same assumption this fix relies on.
- **Known caveat, not addressed here**: that same GitHub issue shows `SetLabel` can fail past label index ~100 in some Audacity versions. Not something to work around speculatively without knowing which versions are affected, but worth knowing if a transcript has 100+ segments.
- **Not independently tested against a live Audacity instance** — verified via unit tests with mocked `GetInfo`/`SetLabel` responses and the corroborating GitHub issue, since no running Audacity was available to test against directly. Please verify against real Audacity before considering this fully closed.
- Added `tests/test_label_tools.py`.

## [0.1.12] - 2026-07-28

### GPU Detection False Negative

Reported by a user who ran `audacity-mcp-setup-gpu` (which confirmed GPU transcription worked) and restarted Claude Desktop, but the actual server logs still showed `Loading whisper model 'small' on CPU...` with no "GPU failed" message in between — meaning `_cuda_is_available()` returned `False` before a GPU attempt was even made.

- **Fixed `_cuda_is_available()`** (`audacity_mcp/tools/transcription_tools.py`): it trusted `torch.cuda.is_available()` exclusively when torch was importable, returning immediately on `False` without ever running the actual check that matters. faster-whisper runs on CTranslate2, not torch — a coincidentally-installed CPU-only (or mismatched-CUDA) torch build could silently mask a perfectly working `nvidia-cublas-cu12`/`nvidia-cudnn-cu12` install. Now torch is only trusted for a *positive* answer; `False` or an import failure falls through to the real `cublas64_12.dll`/`libcublas.so` load check.
- Most likely underlying cause for this specific report is still an environment mismatch (packages installed where `setup_gpu` ran vs. the Python Claude Desktop's config actually launches) — the torch issue is a separate, independently real bug found investigating the same report.
- Added `tests/test_transcription.py::TestCudaIsAvailable` covering: torch-False-falls-through, torch-True-short-circuits, no-torch-no-cublas, and the macOS no-CUDA path.

## [0.1.11] - 2026-07-28

### Double-Clickable GPU Setup

- **Added `setup_gpu.bat` (Windows) and `setup_gpu.sh` (macOS/Linux)** at the repo root, alongside `install.bat`/`install.sh`. Same one-click pattern: no terminal, no typed commands — just download and double-click (or run). They wrap `python -m audacity_mcp.setup_transcription` (not the bare `audacity-mcp-setup-gpu` command) so they only depend on `python` being on PATH, not pip's Scripts directory too. `setup_gpu.bat` runs via `cmd.exe`, not PowerShell, so it isn't affected by PowerShell's execution-policy restriction that blocks `.ps1` scripts by default on Windows.
- `install.bat`/`install.sh` now mention `setup_gpu.bat`/`setup_gpu.sh` in their "Next steps" so new users discover GPU setup without needing to read the docs.
- README + `docs/INSTALLATION.md` link to both scripts as an alternative to the `audacity-mcp-setup-gpu` command.

## [0.1.10] - 2026-07-28

### GPU Transcription Setup & Clarity

Prompted by a user report of transcription "seeming to time out / run on CPU" with no clear way to check why:

- **New `audacity-mcp-setup-gpu` command**: one-step GPU setup for transcription. Detects an NVIDIA GPU via `nvidia-smi`, installs `nvidia-cublas-cu12`/`nvidia-cudnn-cu12` into the exact Python environment `audacity-mcp` itself runs from (installing into the wrong environment was a real, common failure mode with the old manual instructions), and then actually loads a model on the GPU to confirm it works — instead of finding out later that it silently fell back to CPU. Cleanly reports "no NVIDIA GPU detected" and exits successfully (CPU is fine) rather than erroring when there's no GPU to find.
- **Fixed a real bug in `_setup_cuda_path()`** (`audacity_mcp/tools/transcription_tools.py`): it read `nvidia.cublas.__file__`/`nvidia.cudnn.__file__` to locate the DLL directories, but current `nvidia-cublas-cu12`/`nvidia-cudnn-cu12` releases are PEP 420 namespace packages with no `__init__.py`, so `__file__` is `None` — the function's own guard against that silently skipped every time, meaning it never actually added anything to PATH. Switched to `__path__`, which is always populated. (In practice this wasn't the root cause of the CPU-fallback report — testing showed `ctranslate2` finds the DLLs on its own regardless — but it was still dead, broken code worth fixing since it was found in the course of building the setup script.)
- **Documented in README + `docs/INSTALLATION.md`**: GPU acceleration is NVIDIA-only — AMD/Intel graphics and macOS aren't supported by faster-whisper's CTranslate2 backend at all, no driver update fixes that. GeForce vs. Quadro/RTX-workstation/older-GTX doesn't matter; any reasonably current NVIDIA GPU works. Added manual verification steps (Task Manager GPU usage, `nvidia-smi`, direct `WhisperModel` repro) for anyone who wants to check without the new script.
- Added `tests/test_transcription.py::TestSetupCudaPath` regression test for the namespace-package fix.

## [0.1.9] - 2026-07-25

### Snap / Flatpak Audacity Support (Linux)

Reported in [#7](https://github.com/xDarkzx/Audacity-MCP/issues/7): Snap-packaged Audacity on Ubuntu sandboxes `/tmp`, so the hardcoded pipe path never matched anything and the installer failed silently. Investigated the same class of issue across every OS/packaging combination we ship for (Windows installer/portable, macOS DMG/Homebrew/portable, Linux native/Snap/Flatpak/AppImage) and fixed the two real bugs found:

- **Pipe path auto-detection**: `PipePaths.resolve()` now re-detects the pipe directory on every connection instead of hardcoding `/tmp` at import time. It checks an `AUDACITY_PIPE_DIR` override first, then the plain `/tmp` path, then falls back to walking `/proc/*/comm` for a process named `audacity` and using `/proc/<pid>/root/tmp` — but only if both FIFOs actually exist there for the current uid, so a confined Audacity with mod-script-pipe disabled doesn't get mistaken for a working pipe. This isn't Snap-specific — it also fixes Flatpak, which sandboxes `/tmp` the same way via bubblewrap.
- **Installer config-path detection (`install.sh`)**: now falls back to Snap's (`~/snap/audacity/current/.config/audacity/audacity.cfg`) and Flatpak's (`~/.var/app/org.audacityteam.Audacity/config/audacity/audacity.cfg`) config locations when the standard `$XDG_CONFIG_HOME` path is missing, instead of stopping at step 3 with "config not found."
- **Documented, not fixed**: Audacity's portable mode (a `Portable Settings` folder next to the executable, on any OS) relocates `audacity.cfg` outside every path above. No user has hit this yet, and auto-detecting it requires locating Audacity's install directory, which the installer doesn't do — added a troubleshooting note (README + `docs/INSTALLATION.md`) with the manual workaround instead of building speculative detection for an unreported case.
- Added `tests/test_pipe_paths.py` covering the detection logic (override precedence, matching process found, FIFOs missing, non-`audacity` process skipped, non-Linux no-op).

## [0.1.7] - 2026-04-10

### macOS / Linux Compatibility

- **Fixed macOS import crash**: `ctypes.wintypes.HANDLE` type annotation was evaluated at class definition time on all platforms, causing `NameError` on macOS/Linux. Fixed with `from __future__ import annotations` for lazy evaluation.
- **Fixed cross-platform CUDA detection**: `_cuda_is_available()` hardcoded Windows DLL (`cublas64_12.dll`). Now uses `torch.cuda.is_available()` with platform-specific fallbacks (returns `False` on macOS, checks `libcublas.so` on Linux).
- **Fixed macOS pipe paths**: Merged community PR — pipes now use `os.getuid()` for correct user-specific paths instead of hardcoded UID 0.
- **Added macOS/Linux system directory protection**: `_safe_path()` now blocks `/System`, `/Library`, `/usr`, `/bin`, `/sbin`, `/etc`, `/var` on Unix systems. Previously only blocked Windows system directories.
- **Fixed path comparison**: Replaced `.lower()` with `os.path.normcase()` for correct case handling on all platforms.
- **Updated docstrings**: Export path examples changed from Windows-only (`C:\Users\Name\Music`) to platform-neutral (`~/Music`) format.

### Memory Leaks Fixed

- **Whisper model GPU/CPU memory leak**: When switching model sizes (e.g., `large-v3` → `small`), the old model was replaced but never explicitly freed. CUDA/CTranslate2 held references preventing garbage collection. Now explicitly `del`s the old model and calls `gc.collect()` before loading a new one.
- **Job dict memory growth**: Completed job cleanup (`_cleanup_stale_jobs`) only ran when creating new jobs. If 100+ jobs completed without new ones starting, all remained in memory. Now also runs on every `check_pipeline_status` / `check_transcription_status` call.

### Race Conditions Fixed

- **`transcription_set_model` bypassed job lock**: Created jobs and wrote to `_jobs` dict without acquiring `_job_lock`, risking corruption if called simultaneously with `_start_transcription`. Now properly acquires the lock.
- **Pipeline/transcription interleaving**: A running transcription didn't block starting a pipeline (and vice versa). Both send commands to the same Audacity pipe — interleaved commands could corrupt Audacity state. Now cross-check each other before starting.
- **Stale background tasks kept running**: `_cleanup_stale_jobs()` marked timed-out jobs as errored but the `asyncio.Task` continued executing. Now stores task references and calls `task.cancel()` on timeout.

### Pipe Reliability

- **Handle leak on partial pipe open**: If the first pipe opened but the second failed, the first handle was leaked. Now calls `_close_pipes()` in all error paths.
- **No shutdown cleanup**: Pipe handles (especially Windows kernel handles) were never released on server exit. Added `atexit.register(client.close)`.
- **POSIX pipes could hang forever**: `readline()` blocked with no timeout. If Audacity crashed mid-response, the server thread hung permanently (even `asyncio` cancellation can't interrupt OS-level blocking reads). Now uses `select.select()` with configurable timeout.
- **Backslash escaping in pipe protocol**: `_quote_value()` escaped `"` but not `\`. A path like `C:\new\test` could have `\n` and `\t` misinterpreted. Now escapes backslashes before quotes.

### Other Fixes

- **Temp file race on Windows**: Transcription used `NamedTemporaryFile` which on Windows creates then immediately closes a file — another process could grab the same path. Now uses UUID-based paths (matching the pattern already used in cleanup pipelines).

## [0.1.4] - 2026-03-16

### Easy Setup

- **One-click installer**: Added `install.bat` (Windows) and `install.sh` (macOS/Linux) that automatically install from PyPI and configure Claude Desktop — no git clone, no manual JSON editing.
- **`pip install audacity-mcp`** is now the primary install method (was previously git clone + `pip install -e .`).
- **README rewritten** to lead with one-click install and `pip install` from PyPI. Manual git clone steps moved to a collapsible section.
- **Installation guide updated**: Three clear options — one-click (easiest), pip install (recommended), from source (developers).

### Documentation

- Fixed tool counts in README: updated from 96 to 131 tools across all categories.
- Fixed test count in project structure: updated from 40 to 60 tests.
- Updated all references from `pip install -e .` to `pip install audacity-mcp`.

## [0.1.3] - 2026-03-15

### Added

- Added 32 new tools (99 → 131 total) across effects, editing, tracks, selection, transcription, and labels
- Fixed pipeline settings
- Live-tested on production audio

## [0.1.1] - 2026-03-15

### Security

- **Path traversal protection**: All file paths are now canonicalized with `os.path.realpath()` before use, preventing `../` traversal attacks. System directories (Windows, Program Files) are blocked.
- **Command injection hardening**: Fixed `_quote_value()` in pipe protocol to properly escape embedded double quotes, preventing malformed commands from reaching Audacity.
- **File overwrite protection**: Export tools (audio, labels, sample data, transcription) now refuse to overwrite existing files, preventing accidental data loss from AI-hallucinated paths.

### Bug Fixes

- **Memory leak**: Pipeline and transcription job stores (`_jobs` dicts) now cap at 50 completed entries and evict oldest automatically. Previously grew unbounded for the lifetime of the server process.
- **Stale job timeout**: Added 10-minute timeout to cleanup pipelines (was only in transcription). Stuck pipelines no longer block all future pipeline runs forever.
- **Race condition**: Pipeline and transcription job creation now uses `asyncio.Lock` to prevent near-simultaneous MCP calls from bypassing the concurrent-run check and starting two pipelines at once.
- **Temp file collision**: Analysis WAV files now use unique filenames (`uuid` suffix) instead of a fixed path, preventing data corruption if multiple server instances run simultaneously.
- **Removed `wma` from allowed export formats** — Audacity doesn't natively support WMA export; including it caused confusing errors.
- **`select_zero_crossing` called wrong command**: Was calling `SnapToOff` (disables snapping) instead of `ZeroCross` (find zero crossings). Users thought they were snapping to zero crossings but were actually turning snapping off.
- **`auto_analyze_audio` track info never parsed**: `GetInfo` returns JSON in the message field but code expected it in `data` dict. Track count and metadata were always empty. Now properly parses the JSON response.
- **Transcription export missing `SelAllTracks`**: `Export2` requires both track and time selection. Transcription only called `SelectAll` (time) but not `SelAllTracks`, which could cause incomplete exports on multi-track projects.
- **`parse_response` overwrote error messages**: When Audacity returned an error message followed by `BatchCommand finished: Failed!`, the batch line overwrote the actual error text. Error details are now preserved.
- **`effect_amplify` accepted ratio=0**: A ratio of 0 silences audio entirely. Now rejects values <= 0.
- **`check_pipeline_status` deleted other jobs**: Querying one completed job triggered cleanup that could delete other users' job results. Job eviction now only happens during `_create_job`.

### Validation

- **Effect parameter validation**: Added range checks to `reverb` (7 params), `phaser` (6 params), `wahwah` (5 params), `distortion`, and `equalization`. Previously these accepted any value, potentially crashing Audacity.
- **Generator duration caps**: `generate_tone`, `generate_noise`, and `generate_chirp` now enforce a 1-hour maximum duration to prevent runaway generation.
- **Analysis parameter validation**: Added bounds checking to `analyze_find_clipping` (duty cycle 1-1000) and `analyze_sample_data_export` (limit 1-1,000,000).

### Reliability

- **Narrowed exception handlers**: CUDA setup in transcription now catches only `ImportError`, `AttributeError`, `OSError` instead of bare `Exception`, so real bugs surface instead of being silently swallowed.
- **Thread-safe Whisper model loading**: Added `threading.Lock` around model initialization with double-checked locking pattern. Prevents concurrent transcription jobs from loading the model simultaneously and wasting memory.

### Tests

- Added 19 new tests (41 → 60 total): pipe protocol edge cases (negative floats, Unicode, Windows paths, embedded quotes, empty strings, large numbers), path safety validation, parse_response edge cases.

## [0.1.0] - 2025-12-01

### Added

- Initial release with 99 MCP tools across 11 modules
- Named pipe bridge to Audacity via mod-script-pipe
- 9 automated audio pipelines (analyze, cleanup, podcast, audiobook, interview, vocal, live, music mastering, lo-fi)
- Background job system with start/poll pattern for long-running operations
- Transcription support via faster-whisper (local, offline)
- Cross-platform pipe protocol (Windows Win32 API + Unix named pipes)
- Injection detection on pipe commands
- 41 passing tests
