# Tool Reference

Complete reference for all 99 tools in AudacityMCP.

---

## Table of Contents

- [Effects (17 tools)](#effects)
- [Cleanup & Mastering (18 tools)](#cleanup--mastering)
- [Editing (9 tools)](#editing)
- [Project Management (10 tools)](#project-management)
- [Track Management (8 tools)](#track-management)
- [Selection & Cursor (7 tools)](#selection--cursor)
- [Transport & Playback (7 tools)](#transport--playback)
- [Analysis (6 tools)](#analysis)
- [Generation (5 tools)](#generation)
- [Transcription — Experimental (7 tools)](#transcription--experimental)
- [Labels (5 tools)](#labels)

---

## Effects

### `effect_amplify`

Amplify the selected audio by a ratio.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `ratio` | float | 1.0 | Amplification ratio (1.5 = 150%, 0.5 = 50%) |

### `effect_fade_in`

Apply a fade-in to the selected audio. No parameters — select the region first.

### `effect_fade_out`

Apply a fade-out to the selected audio. No parameters — select the region first.

### `effect_reverb`

Apply reverb effect to the selected audio.

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `room_size` | float | 75.0 | 0-100 | Room size percentage |
| `pre_delay` | float | 10.0 | 0-200 | Pre-delay in ms |
| `reverberance` | float | 50.0 | 0-100 | Reverberance percentage |
| `hf_damping` | float | 50.0 | 0-100 | High frequency damping |
| `tone_low` | float | 100.0 | 0-100 | Tone low percentage |
| `tone_high` | float | 100.0 | 0-100 | Tone high percentage |
| `wet_gain` | float | -1.0 | — | Wet signal gain in dB |
| `dry_gain` | float | -1.0 | — | Dry signal gain in dB |
| `stereo_width` | float | 100.0 | 0-100 | Stereo width |
| `wet_only` | bool | False | — | Output only the wet signal |

### `effect_echo`

Apply echo effect to the selected audio.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `delay` | float | 0.5 | Delay time in seconds (must be > 0) |
| `decay` | float | 0.5 | Decay factor (0-1, lower = faster decay) |

### `effect_change_pitch`

Change the pitch without changing tempo.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `semitones` | float | 0.0 | Semitones to shift (negative = lower) |

### `effect_change_tempo`

Change the tempo without changing pitch.

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `percent` | float | 0.0 | -95 to 3000 | Percentage change (50 = 50% faster) |

### `effect_change_speed`

Change speed (changes both tempo and pitch together).

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `percent` | float | 0.0 | -99 to 4900 | Percentage change (100 = double speed) |

### `effect_equalization`

Apply EQ curve to the selected audio.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `curve_name` | str | "Default" | Name of the EQ preset curve |
| `length` | int | 4001 | Filter length (odd, 21-8191) |

### `effect_phaser`

Apply phaser effect.

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `stages` | int | 2 | 2-24 (even) | Number of phaser stages |
| `dry_wet` | int | 128 | 0-255 | Dry/wet mix (0=dry, 255=wet) |
| `frequency` | float | 0.4 | 0.01-40 | LFO frequency in Hz |
| `phase` | float | 0.0 | 0-360 | LFO start phase |
| `depth` | int | 100 | 0-255 | Modulation depth |
| `feedback` | int | 0 | -100 to 100 | Feedback percentage |

### `effect_wahwah`

Apply wahwah effect.

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `frequency` | float | 1.5 | 0.1-4.0 | LFO frequency in Hz |
| `phase` | float | 0.0 | 0-360 | LFO start phase |
| `depth` | int | 70 | 0-100 | Modulation depth |
| `resonance` | float | 2.5 | 0.1-10 | Resonance |
| `offset` | int | 30 | 0-100 | Frequency offset |

### `effect_distortion`

Apply distortion effect.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `distortion_type` | str | "Hard Clipping" | Type of distortion |
| `threshold_db` | float | -6.0 | Distortion threshold in dB |

### `effect_paulstretch`

Extreme time-stretch for ambient/drone textures.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `stretch_factor` | float | 10.0 | How much to stretch (>= 1.0) |
| `time_resolution` | float | 0.25 | Time resolution in seconds |

### `effect_repeat`

Repeat the selected audio.

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `count` | int | 1 | 1-128 | Number of repetitions |

### `effect_high_pass_filter`

Remove low frequencies below the cutoff. Essential as step 1 in mastering chains to remove sub-rumble.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `frequency` | float | 40.0 | Cutoff frequency in Hz |
| `rolloff` | str | "dB12" | Steepness: "dB6" or "dB12" |

### `effect_low_pass_filter`

Remove high frequencies above the cutoff.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `frequency` | float | 20000.0 | Cutoff frequency in Hz |
| `rolloff` | str | "dB6" | Steepness: "dB6" or "dB12" |

### `effect_bass_and_treble`

Simple tonal shaping — adjust bass and treble.

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `bass` | float | 0.0 | -30 to 30 | Bass adjustment in dB |
| `treble` | float | 0.0 | -30 to 30 | Treble adjustment in dB |
| `gain` | float | 0.0 | -30 to 30 | Output gain in dB |

---

## Cleanup & Mastering

### `get_noise_profile`

Capture a noise profile from the currently selected audio region. Select 0.5-2 seconds of pure background noise before calling. Required before using `noise_reduction`.

### `noise_reduction`

Apply noise reduction using a previously captured noise profile.

> **Warning:** Values above 20 dB risk audible artifacts (warbling, metallic sound). Use 6-12 dB for gentle cleanup.

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `noise_reduction_db` | float | 12.0 | 0-48 | Amount of reduction in dB |
| `sensitivity` | float | 6.0 | 0-24 | Detection sensitivity |
| `frequency_smoothing` | int | 3 | 0-12 | Frequency smoothing bands |

### `normalize`

Normalize to a target peak level.

> **Warning:** This boosts OR reduces to hit the target. If audio peaks at -30 dB and you target -1 dB, it boosts by 29 dB. Always check levels first.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `peak_level_db` | float | -3.0 | Target peak level in dB |
| `remove_dc` | bool | True | Remove DC offset first |
| `stereo_independent` | bool | False | Normalize L/R channels independently |

### `loudness_normalize`

Normalize to a target perceived loudness in LUFS — the modern standard for streaming.

> **Warning:** This boosts OR reduces to hit the target LUFS. For quiet audio, fix levels with `normalize` first.

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `lufs_level` | float | -16.0 | -50 to -5 | Target LUFS (-16 podcast/broadcast, -14 Spotify/YouTube) |
| `stereo_independent` | bool | False | — | Normalize channels independently |
| `dual_mono` | bool | True | — | Treat mono as dual-mono for correct measurement |

### `click_removal`

Remove clicks and pops (vinyl recordings, digital artifacts).

| Parameter | Type | Default | Range | Description |
|-----------|------|---------|-------|-------------|
| `threshold` | int | 200 | 0-900 | Detection threshold (higher = fewer removed) |
| `spike_width` | int | 20 | 0-40 | Max click width in samples |

### `truncate_silence`

Remove or compress silent regions.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold_db` | float | -40.0 | Volume below this = silence |
| `min_duration` | float | 0.5 | Minimum silence duration (s) |
| `truncate_to` | float | 0.3 | Truncate silence to this (s) |
| `compress_percent` | float | 50.0 | Compression percentage (for Compress action) |
| `action` | str | "Truncate" | "Truncate" or "Compress" |

### `compressor`

Dynamic range compression. Evens out volume differences.

> **Warning:** `normalize=True` re-peaks to 0 dB. Use `loudness_normalize` instead for proper loudness control.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold_db` | float | -12.0 | Compression starts above this (dB) |
| `noise_floor_db` | float | -40.0 | Don't boost below this (dB) |
| `ratio` | float | 2.0 | Compression ratio (2.0 = 2:1) |
| `attack_time` | float | 0.2 | Attack time in seconds |
| `release_time` | float | 1.0 | Release time in seconds |
| `normalize` | bool | False | Normalize after compression (caution!) |
| `use_peak` | bool | False | Compress based on peaks instead of RMS |

### `limiter`

Prevent audio from exceeding a threshold.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit_db` | float | -1.0 | Maximum output level (dB) |
| `hold_ms` | float | 10.0 | Hold time in ms |
| `makeup_gain` | str | "No" | Apply makeup gain ("Yes"/"No") |
| `limiter_type` | str | "SoftLimit" | "SoftLimit", "HardLimit", "SoftClip", "HardClip" |
| `gain_left` | float | 0.0 | Input gain for left channel (dB) |
| `gain_right` | float | 0.0 | Input gain for right channel (dB) |

### `check_pipeline_status`

Check the status of a running pipeline. Call this after starting any `auto_` pipeline to monitor progress.

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | str | Job ID returned by the pipeline |

### `auto_analyze_audio`

Analyze the current audio and recommend the best pipeline. **Synchronous** — returns results directly, no job_id.

Returns: `peak_db`, `noise_floor_db`, `is_clipping`, `duration`, `sample_rate`, `recommendation`.

### `auto_cleanup_audio`

**Safe cleanup** — removes noise and artifacts WITHOUT changing loudness or dynamics.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `remove_noise` | bool | True | Apply noise reduction |
| `remove_clicks` | bool | False | Apply click removal |

Pipeline: DC offset → HPF 80Hz → noise reduction (opt) → click removal (opt). No compression, no loudness change.

### `auto_cleanup_podcast`

**One-click podcast cleanup** — broadcast-quality processing for speech.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `remove_noise` | bool | True | Apply noise reduction |
| `remove_silence` | bool | False | Truncate silent gaps |

Pipeline: DC offset → HPF 80Hz → noise reduction 12dB → truncate silence (opt) → compression 3:1 → safe loudness check.

### `auto_audiobook_mastering`

**One-click audiobook mastering** — ACX/Audible compliant processing.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `remove_noise` | bool | True | Apply noise reduction |

Pipeline: DC offset → HPF 80Hz → noise reduction 12dB → compression 2.5:1 → safe loudness check.

### `auto_cleanup_interview`

**One-click interview cleanup** — light-touch processing for dialogue and multiple speakers.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `remove_noise` | bool | True | Apply noise reduction |
| `remove_silence` | bool | False | Truncate silent gaps |

Pipeline: DC offset → HPF 80Hz → noise reduction 8dB → truncate silence (opt) → compression 2.5:1 → safe loudness check.

### `auto_cleanup_vocal`

**One-click vocal cleanup** — processing for singing and studio vocals.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `remove_noise` | bool | True | Apply noise reduction |

Pipeline: DC offset → HPF 100Hz → noise reduction 10dB → compression 3:1 → presence EQ (treble +3dB, bass -1dB) → safe loudness check.

### `auto_cleanup_live`

**One-click live recording cleanup** — aggressive processing for noisy/field recordings. No parameters.

Pipeline: DC offset → HPF 100Hz → click removal → noise reduction 18dB → compression 5:1 → safe loudness check.

### `auto_master_music`

**One-click music mastering** with genre-tuned presets.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `style` | str | "edm" | Genre preset (see table below) |
| `noise_reduce` | bool | False | Apply gentle noise reduction |

| Style | HPF | Compression | EQ | Use For |
|-------|-----|-------------|-----|---------|
| `edm` | 30 Hz | 2.5:1 | Bass +2, Treble +1.5 | Electronic, dance |
| `hiphop` | 35 Hz | 3:1 | Bass +3, Treble +1 | Hip-hop, trap |
| `rock` | 40 Hz | 3:1 | Bass +1, Treble +2 | Rock, punk, metal |
| `acoustic` | 60 Hz | 1.5:1 | Bass -1, Treble +1 | Acoustic, folk |
| `pop` | 35 Hz | 2:1 | Bass +1, Treble +1.5 | Pop, R&B |
| `classical` | 30 Hz | 1.3:1 | No EQ | Classical, orchestral |

Pipeline: HPF → click removal → noise reduction (opt) → compression → EQ → safe loudness check.

### `auto_lofi_effect`

**Creative lo-fi/vintage effect** — apply warm, retro character.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `intensity` | str | "medium" | "light", "medium", or "heavy" |

Pipeline: HPF → LPF → warmth EQ → light compression → safe loudness check.

---

## Editing

### `edit_cut`
Cut selected audio to clipboard.

### `edit_copy`
Copy selected audio to clipboard.

### `edit_paste`
Paste from clipboard at cursor position.

### `edit_delete`
Delete selected audio (no clipboard).

### `edit_split`
Split audio into a new clip at selection boundaries.

### `edit_join`
Join selected clips into one clip.

### `edit_trim`
Delete everything except the selected region.

### `edit_silence`
Replace selected audio with silence.

### `edit_duplicate`
Duplicate selected audio into a new track.

### `edit_undo`
Undo the last operation.

### `edit_redo`
Redo the last undone operation.

---

## Project Management

### `project_new`
Create a new empty project.

### `project_open`

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | str | Path to .aup3 file |

### `project_save`
Save the current project.

### `project_save_as`

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | str | New file path |

### `project_close`
Close the current project.

### `project_import_audio`

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | str | Path to audio file |

### `project_export_audio`

Export audio to file. Format is inferred from extension.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | str | — | Output path (WAV, MP3, FLAC, OGG, AIFF, MP4, WMA) |
| `num_channels` | int | 2 | Number of channels |

### `project_export_labels`

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | str | Output text file path |

### `project_get_info`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `info_type` | str | "Tracks" | Info type to retrieve |

---

## Track Management

### `track_add_mono`
Add a new mono track.

### `track_add_stereo`
Add a new stereo track.

### `track_remove`
Remove selected track(s).

### `track_set_properties`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track` | int | — | Track index |
| `name` | str | None | Track name |
| `gain` | float | None | Gain in dB |
| `pan` | float | None | Pan (-1 to 1) |
| `mute` | bool | None | Mute state |
| `solo` | bool | None | Solo state |

### `track_get_info`
Get info about all tracks (names, types, rates).

### `track_mix_and_render`
Mix and render selected tracks into one.

### `track_mute`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track` | int | — | Track index |
| `mute` | bool | True | Mute state |

### `track_select`

| Parameter | Type | Description |
|-----------|------|-------------|
| `track` | int | Track index |

---

## Selection & Cursor

### `select_all`
Select all audio in all tracks.

### `select_none`
Deselect all audio.

### `select_region`

| Parameter | Type | Description |
|-----------|------|-------------|
| `start` | float | Start time in seconds |
| `end` | float | End time in seconds |

### `select_tracks`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `track` | int | — | Track index |
| `count` | int | 1 | Number of tracks |

### `select_zero_crossing`
Snap selection to nearest zero crossings (prevents clicks at edit points).

### `select_clip`
Select the clip under the cursor.

### `cursor_set_position`

| Parameter | Type | Description |
|-----------|------|-------------|
| `time` | float | Time in seconds |

---

## Transport & Playback

### `transport_play`
Start playback from cursor.

### `transport_stop`
Stop playback or recording.

### `transport_pause`
Toggle pause.

### `transport_record`
Start recording on a new track.

### `transport_set_cursor`

| Parameter | Type | Description |
|-----------|------|-------------|
| `time` | float | Position in seconds |

### `transport_get_play_position`
Get current playback position in seconds.

### `transport_play_region`

| Parameter | Type | Description |
|-----------|------|-------------|
| `start` | float | Start time in seconds |
| `end` | float | End time in seconds |

---

## Analysis

### `analyze_contrast`
Analyze contrast between foreground and background audio.

### `analyze_find_clipping`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `duty_cycle_start` | int | 3 | Start duty cycle |
| `duty_cycle_end` | int | 3 | End duty cycle |

Creates labels at clipped regions.

### `analyze_plot_spectrum`
Open the Plot Spectrum window.

### `analyze_beat_finder`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `thres_val` | int | 65 | Beat detection threshold |

Adds labels at detected beat positions.

### `analyze_label_sounds`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `threshold_db` | float | -30.0 | Sound/silence threshold |
| `min_silence_duration` | float | 0.5 | Min silence gap (s) |
| `min_sound_duration` | float | 0.1 | Min sound length (s) |

### `analyze_sample_data_export`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | str | — | Output text file path |
| `limit` | int | 100 | Max samples to export |

---

## Generation

### `generate_tone`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `waveform` | str | "Sine" | Sine, Square, Sawtooth, Square (no alias) |
| `frequency` | float | 440.0 | Frequency in Hz |
| `amplitude` | float | 0.8 | Amplitude (0-1) |
| `duration` | float | 1.0 | Duration in seconds |

### `generate_noise`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `noise_type` | str | "White" | White, Pink, or Brownian |
| `amplitude` | float | 0.8 | Amplitude (0-1) |
| `duration` | float | 1.0 | Duration in seconds |

### `generate_chirp`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `waveform` | str | "Sine" | Waveform type |
| `start_freq` | float | 440.0 | Start frequency (Hz) |
| `end_freq` | float | 1320.0 | End frequency (Hz) |
| `start_amp` | float | 0.8 | Start amplitude |
| `end_amp` | float | 0.1 | End amplitude |
| `duration` | float | 1.0 | Duration in seconds |

### `generate_dtmf`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sequence` | str | "0123456789" | DTMF key sequence |
| `duty_cycle` | float | 55.0 | Tone/silence ratio |
| `amplitude` | float | 0.8 | Amplitude (0-1) |
| `duration` | float | 1.0 | Total duration in seconds |

### `generate_rhythm_track`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tempo` | float | 120.0 | BPM |
| `beats_per_bar` | int | 4 | Time signature numerator |
| `number_of_bars` | int | 4 | Number of bars |
| `rhythm_pattern` | str | "Uniform" | Rhythm pattern type |

---

## Transcription — Experimental

> **This feature is experimental.** Requires separate setup (see [Transcription Setup](INSTALLATION.md#transcription-setup-optional)). Powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — runs locally, no API keys, fully offline and private.

All transcription tools run in the **background** and return a `job_id`. Use `check_transcription_status` to poll progress.

### `get_default_transcription_folder`

Get the default folder for saving transcription files (user's Documents folder). No parameters.

### `check_transcription_status`

Poll a running transcription job. Call every 10-15 seconds until status is `complete` or `error`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | str | The job ID returned when you started a transcription |

### `transcribe_audio`

Transcribe the entire project audio.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_size` | str | "small" | tiny, base, small, medium, large-v3 |
| `language` | str | None | Language code (auto-detect if None) |
| `task` | str | "transcribe" | "transcribe" or "translate" (to English) |

### `transcribe_selection`

Transcribe only the selected audio region. Same parameters as `transcribe_audio`.

### `transcribe_to_labels`

Transcribe and add Audacity labels at each segment.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_size` | str | "small" | Model size |
| `language` | str | None | Language code |

### `transcribe_to_file`

Transcribe and export as subtitle file.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | str | — | Output file path |
| `format` | str | "srt" | "srt", "vtt", or "txt" |
| `model_size` | str | "small" | Model size |
| `language` | str | None | Language code |

### `transcription_set_model`

Pre-download a model. Only needed if you want to switch models — transcription tools load automatically.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_size` | str | "base" | Model to pre-load |

---

## Labels

### `label_add`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | str | "" | Label text |

Adds at current cursor position or selection.

### `label_add_at`

| Parameter | Type | Description |
|-----------|------|-------------|
| `start` | float | Start time in seconds |
| `end` | float | End time in seconds |
| `text` | str | Label text (default: "") |

### `label_get_all`
Get all labels in the project.

### `label_import`

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | str | Text file path |

### `label_export`

| Parameter | Type | Description |
|-----------|------|-------------|
| `path` | str | Output text file path |
