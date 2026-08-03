# Transcript-Based Editing (Podcasts, Interviews, Lectures)

This document covers the label-driven tools built specifically for **transcript-based editing** — a workflow where you edit long-form spoken audio (a podcast episode, an interview, a lecture, a voice memo) by working from segment markers instead of scrubbing through the waveform by ear.

**Purpose statement:** these tools exist to serve that one workflow. If your editing needs are different — music production, mastering, sound design, one-off effect chains on a short clip — most of this document doesn't apply to you, and the label tools will likely just add friction rather than help. See [When these tools aren't the right fit](#when-these-tools-arent-the-right-fit) below.

## What "transcript-based editing" means here

A podcast or interview recording is usually edited by working through it segment by segment: cut the bad takes, tighten pauses, redact a name, pull a pull-quote for a trailer, ship chapter markers with the final file. Doing that by ear means constantly re-scrubbing the timeline to find the same three seconds. The alternative this project supports: put a label on every spoken segment once (via transcription or silence detection), then use the label list — not the waveform — as the map for every edit that follows.

## The workflow

### 1. Get segment markers onto the timeline

- **`transcribe_to_labels`** *(experimental, requires separate faster-whisper setup — see the installation guide)* — transcribes the project audio and drops one label per spoken segment, with the transcribed text as the label's text. This is the main entry point for transcript-based editing: after this call, `label_list` shows you the whole recording as a list of "sentence → time range" entries.
- **`analyze_label_sounds`** — an alternative when you want segment boundaries without needing the words: labels every passage of sound separated by silence (`label_type="before"`/`"after"`/`"around"`), or the silences themselves (`label_type="between"`, useful for finding dead air to trim). Tunable via `threshold_db`, `min_silence_duration`, `min_sound_duration`, `measurement` (peak/avg/rms), and `pre_offset`/`post_offset` to pad each label.
- Related but not label-producing: `transcribe_audio`/`transcribe_selection` (transcript only), `transcribe_to_file` (SRT/VTT/TXT export).

### 2. Read and search the labels

- **`label_list`** — every label with the flat index `label_edit`/`label_delete`/`label_delete_audio_at` expect. Call this before touching a specific label rather than guessing an index — labels shift as edits happen.
- **`label_find(query)`** — case-insensitive text search, for jumping straight to "the part where they mention the sponsor" in a long transcript.
- **`label_get_all`** — Audacity's raw `GetInfo` response, if you need the unparsed form for some reason. Prefer `label_list`.

### 3. Edit the label track itself

- **`label_edit(index, text=, start=, end=)`** — rename a label or nudge a boundary; only the fields you pass change.
- **`label_add`** / **`label_add_at(start, end, text=)`** — add one label, at the cursor/selection or at an explicit time range.
- **`label_add_batch(labels)`** — add a whole marker list in one call (up to 500), validated up front so a bad entry can't leave a half-written list behind.
- **`label_regular_intervals`** — evenly spaced labels, for a different kind of segmentation (e.g. chaptering a continuous mix with no natural pauses).

### 4. Remove a segment — three different operations, pick by scope

This is the part most likely to be reached for wrong, since the names are close:

| Tool | Removes | Scope | Timeline effect |
|------|---------|-------|------------------|
| `label_delete(index)` | The label only | One label, by index | None — no audio touched |
| `label_delete_audio_at(index, close_gap=True, delete_label=True)` | Audio + the label | One label, by index | Gap closes (or stays as silence with `close_gap=False`) |
| `label_delete_regions()` / `label_cut_regions()` | Audio under every label in the current selection | Bulk, by selection (no index) | Gaps close |
| `label_silence_regions()` / `label_split_regions()` / `label_join_regions()` | Nothing removed — replace with silence / split / rejoin clips | Bulk, by selection | Timeline length unchanged |

`label_delete_audio_at` is the one built specifically for this workflow's "delete this one bad take" case — pick a labeled segment out of `label_list` and remove it, audio and marker together, in a single call. It's a custom composite (several Audacity commands orchestrated: select all tracks → select the label's time range → delete/split-delete → clear the leftover marker), not a thin wrapper over one Audacity command, because Audacity has no built-in "delete this one labeled take" verb.

For bulk cleanup — "remove every label I marked as a bad take" — loop `label_delete_audio_at` over the indices (highest index first, so earlier deletions don't shift the ones still queued), or select the relevant tracks/time range and use `label_delete_regions` to remove everything caught in the selection at once.

### 5. Get the labeled work back out

- **`label_export_chapters(path, format=)`** — labels as a chapter/marker file: `"simple"` (`HH:MM:SS.mmm Title` per line), `"cue"` (cue sheet), or `"podlove"` (Podlove Simple Chapters JSON, the format most podcast hosts accept directly). Untitled labels become "Chapter 1", "Chapter 2", etc.
- **`label_export_audio_segments(directory, format=, num_channels=)`** — exports the audio under each label as its own file (`01_Segment_Title.wav`, …), for pulling a single labeled quote or shipping per-segment files. Point labels (no width) are skipped; existing files are never overwritten; capped at 100 segments per call.
- **`label_export` / `label_import`** — raw Audacity label-file round trip (`ExportLabels`/`ImportLabels`). Note: `label_export` combines every label track's contents into one `GetInfo` blob, so it doesn't distinguish which label track a marker came from if there's more than one.

## A concrete example

An hour-long interview, cut down for release:

1. `transcribe_to_labels` — one label per sentence, transcribed text included.
2. `label_find("um")` / read through `label_list` to spot filler, false starts, and the part where the guest asked to redact a name.
3. `label_delete_audio_at(index)` for each bad take (highest index first), or `label_silence_regions()` over the redacted section if it needs to stay in sync rather than get shorter.
4. `label_export_chapters(path, format="podlove")` for the podcast host's chapter markers.
5. `label_export_audio_segments(directory)` to pull the best answer out as a standalone clip for a trailer.

## Known limitations

- **`label_cut_regions` is not yet independently live-tested** against a running Audacity, unlike its siblings (`label_delete_regions`, `label_silence_regions`, `label_split_regions`, `label_join_regions`), which are.
- **`label_export`'s track-combining behavior** (all label tracks flattened into one response) is a known gap, not yet fixed.
- **Transcription tools are experimental** and need separate setup (`faster-whisper`, a downloaded model) — see the installation guide. Language auto-detection can occasionally misidentify short or noisy clips; pass `language` explicitly if you already know it.
- **`label_delete_audio_at`'s track-resolution** assumes a project with one label track; behavior with multiple label tracks on the same edit is less exercised.

## When these tools aren't the right fit

This whole toolset assumes you're editing *around markers* — segments with a start, an end, and (usually) some text. If that's not how your project works, reach for the rest of AudacityMCP instead:

- **Music production / mastering** — use the Effects and Cleanup & Mastering categories (EQ, compression, limiting, the one-click mastering pipelines) directly on the track; there's no transcript or segment structure to hang labels off of.
- **Sound design** — Generation and Effects tools (tone/noise/chirp generation, pitch/tempo/reverb) operate on raw selections, not labels.
- **A single one-off edit** ("trim the first 3 seconds", "normalize this track") — the plain Editing/Selection tools (`cut`, `trim`, `select_time`, etc.) are simpler and don't need a label track set up first.

Using the label tools outside a transcript/marker-driven workflow mostly just adds a layer of indirection — you'd be building and maintaining a label track for edits that don't need one.
