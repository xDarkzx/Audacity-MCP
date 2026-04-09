# Changelog

All notable changes to AudacityMCP will be documented in this file.

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
