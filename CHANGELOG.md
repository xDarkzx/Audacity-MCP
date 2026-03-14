# Changelog

All notable changes to AudacityMCP will be documented in this file.

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
