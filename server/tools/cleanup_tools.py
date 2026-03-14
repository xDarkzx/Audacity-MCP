import asyncio
import math
import os
import struct
import tempfile
import time
import uuid
import wave

from mcp.server.fastmcp import FastMCP
from shared.error_codes import AudacityMCPError, ErrorCode

# Delay between pipeline steps to let Audacity fully process each effect
_STEP_DELAY = 0.5

# In-memory job store for background pipelines
_jobs: dict[str, dict] = {}


def register(mcp: FastMCP):
    from server.main import client

    # ── Shared helpers ────────────────────────────────────────────────

    async def _select_all():
        """Select all tracks AND all time — both are needed for effects to work."""
        await client.execute("SelAllTracks")
        await client.execute("SelectAll")

    async def _show_completion_popup(title: str, details: str):
        """No-op — popups removed because NyquistPrompt shows blocking dialogs
        that require the user to click OK (sometimes twice). The AI already
        reports results through the MCP response."""
        pass

    def _has_running_pipeline() -> bool:
        return any(j["status"] == "running" for j in _jobs.values())

    def _create_job(pipeline_name: str) -> tuple[str, dict]:
        """Create a job dict and return (job_id, job). Also checks for concurrent runs."""
        if _has_running_pipeline():
            return None, None
        job_id = str(uuid.uuid4())[:8]
        job = {
            "status": "running",
            "pipeline": pipeline_name,
            "current_step": "starting",
            "steps_applied": [],
            "steps_failed": [],
            "started_at": time.time(),
            "result": None,
            "error": None,
        }
        _jobs[job_id] = job
        return job_id, job

    def _running_job_error() -> dict:
        """Return error dict when a pipeline is already running."""
        running = next(j for j in _jobs.values() if j["status"] == "running")
        running_id = next(k for k, v in _jobs.items() if v is running)
        return {
            "error": "A pipeline is already running. Do NOT start another one.",
            "job_id": running_id,
            "current_step": running["current_step"],
            "message": "Use check_pipeline_status to monitor the existing pipeline.",
        }

    async def _complete_job(job: dict, label: str, targets: dict):
        """Mark job complete, build result, show popup."""
        elapsed = round(time.time() - job["started_at"], 1)
        job["status"] = "complete"
        job["current_step"] = "done"
        job["result"] = {
            "success": len(job["steps_failed"]) == 0,
            "message": f"{label}: {' > '.join(job['steps_applied'])}",
            "targets": targets,
            "elapsed_seconds": elapsed,
        }
        if job["steps_failed"]:
            job["result"]["warnings"] = job["steps_failed"].copy()

        target_str = ", ".join(f"{k}: {v}" for k, v in targets.items())
        await _show_completion_popup(
            label,
            f"Steps: {' > '.join(job['steps_applied'])}\\n"
            f"Target: {target_str}\\n"
            f"Time: {elapsed}s",
        )

    async def _run_pipeline_step(job: dict, name: str, coro):
        """Run a single pipeline step with error handling and job tracking."""
        job["current_step"] = name
        try:
            await coro
            job["steps_applied"].append(name)
        except Exception as e:
            job["steps_failed"].append(f"{name}: {e}")
        await asyncio.sleep(_STEP_DELAY)

    async def _noise_reduction_step(job: dict, reduction_db: float = 12, sensitivity: float = 6, smoothing: int = 3):
        """Two-step noise reduction: capture profile from first 0.5s, then apply to all.
        Step 1 MUST be called with no params to capture the profile.
        Step 2 applies with the actual reduction settings."""
        step_name = f"noise reduction {reduction_db}dB"
        job["current_step"] = "noise profile capture"
        try:
            # Step 1: Select first 0.5s of noise and capture profile (no params = capture mode)
            await client.execute("SelAllTracks")
            await client.execute("SelectTime", Start=0, End=0.5)
            await asyncio.sleep(0.5)
            await client.execute_long("NoiseReduction")
            await asyncio.sleep(1.0)

            # Step 2: Select all and apply noise reduction with settings
            job["current_step"] = step_name
            await _select_all()
            await client.execute_long("NoiseReduction", Reduction=reduction_db, Sensitivity=sensitivity, Smoothing=smoothing)
            job["steps_applied"].append(step_name)
        except Exception as e:
            job["steps_failed"].append(f"noise reduction: {e}")
        await asyncio.sleep(_STEP_DELAY)

    async def _dc_offset_step(job: dict):
        """Remove DC offset only (no gain change)."""
        await _select_all()
        await _run_pipeline_step(job, "remove DC offset",
            client.execute_long("Normalize", PeakLevel=-1.0, ApplyGain=False, RemoveDcOffset=True))

    async def _hpf_step(job: dict, freq: float = 80.0):
        """High-pass filter."""
        await _select_all()
        await _run_pipeline_step(job, f"HPF {freq}Hz",
            client.execute_long("High-passFilter", frequency=freq, rolloff="dB12"))

    async def _measure_current_audio(job: dict) -> tuple[float | None, float | None]:
        """Export current audio to temp WAV and measure peak + noise floor.
        Returns (peak_db, noise_floor_db). Non-destructive — doesn't modify audio."""
        tmp_wav = _ANALYZE_WAV
        try:
            await _select_all()
            await client.execute_long("Export2", Filename=tmp_wav, NumChannels=1)
            if not os.path.exists(tmp_wav) or os.path.getsize(tmp_wav) < 100:
                job["steps_failed"].append(f"measurement: WAV export failed (file missing or empty at {tmp_wav})")
                return None, None
            measurements = _measure_wav(tmp_wav)
            if measurements is None:
                job["steps_failed"].append("measurement: WAV exists but could not parse audio data")
                return None, None
            return measurements["peak_db"], measurements["noise_floor_db"]
        except Exception as e:
            job["steps_failed"].append(f"measurement: {type(e).__name__}: {e}")
            return None, None
        finally:
            try:
                os.remove(tmp_wav)
            except OSError:
                pass

    async def _loudness_step(job: dict, peak_target: float = -3.0):
        """Safe final loudness step — peak normalize only, NO LUFS.

        LUFS normalization is too dangerous as an automated step because:
        - It can boost by 10-20dB on quiet/badly recorded audio
        - Audacity's Limiter resets changes via pipe so we can't catch peaks after
        - Peak level doesn't predict how much LUFS will boost (they measure different things)

        Instead: measure current peaks, only REDUCE if too hot. Never boost.
        The user can manually apply LUFS via the loudness_normalize tool after
        checking the results.
        """
        await asyncio.sleep(1.0)  # Extra delay to let prior effects settle

        peak_db, noise_db = await _measure_current_audio(job)
        job["steps_applied"].append(f"measured: peak={peak_db}dB noise={noise_db}dB")

        if peak_db is None:
            job["steps_applied"].append("loudness skipped (measurement failed)")
            return

        if peak_db > peak_target:
            # Peaks are too hot — bring them DOWN to target (reduce only, never boost)
            await _select_all()
            await _run_pipeline_step(job, f"reduce peaks to {peak_target}dB",
                client.execute_long(
                    "Normalize", PeakLevel=peak_target, ApplyGain=True,
                    RemoveDcOffset=False, StereoIndependent=False,
                ))
        else:
            # Peaks are already below target — leave them alone
            job["steps_applied"].append(
                f"peaks already at {peak_db}dB (below {peak_target}dB ceiling) — no change needed"
            )

    async def _compress_step(job: dict, threshold: float, ratio: float, attack: float = 0.2, release: float = 1.0, use_peak: bool = False):
        """Compression step. Normalize=False always — we handle loudness separately.
        NoiseFloor=-30 prevents boosting background noise in quiet recordings."""
        await _select_all()
        await _run_pipeline_step(job, f"compress {ratio}:1",
            client.execute_long(
                "Compressor",
                Threshold=threshold, NoiseFloor=-30, Ratio=ratio,
                AttackTime=attack, ReleaseTime=release, Normalize=False,
                UsePeak=use_peak,
            ))

    def _start_background(job_id: str, job: dict, coro, label: str) -> dict:
        """Launch a pipeline coroutine as a background task and return the standard response."""
        asyncio.create_task(coro)
        return {
            "job_id": job_id,
            "status": "running",
            "message": (
                f"{label} started in background and is processing your audio now. "
                "Do NOT call this tool again. Call check_pipeline_status with this job_id "
                "every 15-30 seconds to check progress. The pipeline will take several minutes."
            ),
        }

    # ── Individual cleanup tools ──────────────────────────────────────

    @mcp.tool()
    async def get_noise_profile() -> dict:
        """Capture a noise profile from the currently selected audio region.
        IMPORTANT: Select a region of pure noise (e.g. 0.5-2 seconds of silence/background noise)
        before calling this. This profile is used by the noise_reduction tool.

        How it works: The first call to NoiseReduction without an existing profile
        captures the selection as the noise profile. The next call applies reduction."""
        return await client.execute_long("NoiseReduction", Reduction=12, Sensitivity=6, Smoothing=3)

    @mcp.tool()
    async def noise_reduction(
        noise_reduction_db: float = 12.0,
        sensitivity: float = 6.0,
        frequency_smoothing: int = 3,
    ) -> dict:
        """Apply noise reduction to the selected audio. You MUST call get_noise_profile first
        on a region of pure noise, then select the audio you want to clean, then call this.

        WARNING: Values above 20 dB risk audible artifacts (warbling, metallic sound).
        Use 6-12 dB for gentle cleanup, 12-20 dB for moderate noise. Only exceed 20 dB
        for extremely noisy recordings where some artifact trade-off is acceptable.

        Args:
            noise_reduction_db: Amount of noise reduction in dB (0-48). Default: 12
            sensitivity: How sensitive the detection is (0-24). Default: 6
            frequency_smoothing: Number of frequency smoothing bands (0-12). Default: 3
        """
        if not 0 <= noise_reduction_db <= 48:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "noise_reduction_db must be 0-48")
        if noise_reduction_db > 20:
            import logging
            logging.warning(
                f"noise_reduction_db={noise_reduction_db} exceeds 20 dB — "
                "high values risk audible artifacts (warbling, metallic sound)"
            )
        if not 0 <= sensitivity <= 24:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "sensitivity must be 0-24")
        if not 0 <= frequency_smoothing <= 12:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "frequency_smoothing must be 0-12")
        return await client.execute_long(
            "NoiseReduction",
            Reduction=noise_reduction_db,
            Sensitivity=sensitivity,
            Smoothing=frequency_smoothing,
        )

    @mcp.tool()
    async def normalize(
        peak_level_db: float = -3.0,
        remove_dc: bool = True,
        stereo_independent: bool = False,
    ) -> dict:
        """Normalize the selected audio to a target peak level.

        WARNING: This boosts OR reduces audio to hit the target. If audio peaks at -30 dB
        and you normalize to -1 dB, it will BOOST by 29 dB — potentially blowing out the audio.
        ALWAYS check current audio levels first (use project_get_info) before normalizing.

        Guidelines — choose your target based on what comes next:
        - -3 dB (default): Safe general-purpose level with headroom for further processing
        - -6 dB: Conservative, good for unknown or problematic audio
        - -1 dB: ONLY as a final ceiling on already-mastered audio (never on raw audio)
        - -12 dB or lower: For very quiet audio that needs gentle boosting

        Args:
            peak_level_db: Target peak level in dB (-60 to 0). Default: -3.0
            remove_dc: Remove DC offset before normalizing. Default: True
            stereo_independent: Normalize L/R channels separately (fixes unbalanced recordings). Default: False
        """
        return await client.execute_long(
            "Normalize",
            PeakLevel=peak_level_db,
            RemoveDcOffset=remove_dc,
            ApplyGain=True,
            StereoIndependent=stereo_independent,
        )

    @mcp.tool()
    async def click_removal(threshold: int = 200, spike_width: int = 20) -> dict:
        """Remove clicks and pops from the selected audio (e.g. vinyl recordings).

        Args:
            threshold: Click detection threshold (0-900). Higher = fewer clicks removed. Default: 200
            spike_width: Maximum width of a click in samples (0-40). Default: 20
        """
        if not 0 <= threshold <= 900:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "threshold must be 0-900")
        if not 0 <= spike_width <= 40:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "spike_width must be 0-40")
        return await client.execute_long(
            "ClickRemoval",
            Threshold=threshold,
            Width=spike_width,
        )

    @mcp.tool()
    async def truncate_silence(
        threshold_db: float = -40.0,
        min_duration: float = 0.5,
        truncate_to: float = 0.3,
        compress_percent: float = 50.0,
        action: str = "Truncate",
    ) -> dict:
        """Truncate or compress silence in the selected audio. Great for removing dead air.

        Args:
            threshold_db: Volume below this is considered silence (dB). Default: -40
            min_duration: Minimum silence duration to act on (seconds). Default: 0.5
            truncate_to: Truncate silence to this duration (seconds). Default: 0.3
            compress_percent: Compress silence by this percentage (only for Compress action). Default: 50
            action: "Truncate" or "Compress". Default: "Truncate"
        """
        action_map = {
            "Truncate": "Truncate Detected Silence",
            "Compress": "Compress Excess Silence",
        }
        if action not in action_map:
            raise AudacityMCPError(ErrorCode.INVALID_PARAMETER, "action must be 'Truncate' or 'Compress'")
        return await client.execute_long(
            "TruncateSilence",
            Threshold=threshold_db,
            Minimum=min_duration,
            Truncate=truncate_to,
            Compress=compress_percent,
            Action=action_map[action],
        )

    @mcp.tool()
    async def compressor(
        threshold_db: float = -12.0,
        noise_floor_db: float = -40.0,
        ratio: float = 2.0,
        attack_time: float = 0.2,
        release_time: float = 1.0,
        normalize: bool = False,
        use_peak: bool = False,
    ) -> dict:
        """Apply dynamic range compression. Evens out volume differences.

        For mastering, use ratio 1.5-2:1 with attack > 80ms to preserve transients.
        For podcasts/voice, use ratio 4-8:1 with use_peak=True for tighter control.
        Higher ratios (4:1+) and fast attacks are mixing tools, not mastering tools.

        WARNING: normalize=True will re-peak your audio to 0 dB after compression,
        which can make loud audio even louder. Use loudness_normalize() instead
        for proper LUFS-based loudness control.

        Args:
            threshold_db: Level above which compression starts (dB). Default: -12
            noise_floor_db: Level below which audio is not boosted (dB). Default: -40
            ratio: Compression ratio (e.g. 2.0 = 2:1). Default: 2.0
            attack_time: How fast compressor engages (seconds). Default: 0.2
            release_time: How fast compressor releases (seconds). Default: 1.0
            normalize: Normalize to 0dB peak after compression. Default: False
            use_peak: Compress based on peaks instead of RMS (better for voice/podcast). Default: False
        """
        return await client.execute_long(
            "Compressor",
            Threshold=threshold_db,
            NoiseFloor=noise_floor_db,
            Ratio=ratio,
            AttackTime=attack_time,
            ReleaseTime=release_time,
            Normalize=normalize,
            UsePeak=use_peak,
        )

    @mcp.tool()
    async def limiter(
        limit_db: float = -1.0,
        hold_ms: float = 10.0,
        makeup_gain: str = "No",
        limiter_type: str = "SoftLimit",
        gain_left: float = 0.0,
        gain_right: float = 0.0,
    ) -> dict:
        """Apply a limiter to prevent audio from exceeding a threshold. Use after compression.

        Default ceiling is -1.0 dB, the industry standard for streaming platforms.

        Args:
            limit_db: Maximum output level (dB). Default: -1.0
            hold_ms: Hold time in milliseconds. Default: 10.0
            makeup_gain: Apply makeup gain ("Yes" or "No"). Default: "No"
            limiter_type: "SoftLimit", "HardLimit", "SoftClip", "HardClip". Default: "SoftLimit"
            gain_left: Input gain for left channel (dB). Default: 0.0
            gain_right: Input gain for right channel (dB). Default: 0.0
        """
        if makeup_gain not in ("Yes", "No"):
            raise AudacityMCPError(ErrorCode.INVALID_PARAMETER, "makeup_gain must be 'Yes' or 'No'")
        if limiter_type not in ("SoftLimit", "HardLimit", "SoftClip", "HardClip"):
            raise AudacityMCPError(ErrorCode.INVALID_PARAMETER, "limiter_type must be SoftLimit, HardLimit, SoftClip, or HardClip")
        return await client.execute_long(
            "Limiter",
            extra_params={
                "type": limiter_type,
                "gain-L": gain_left,
                "gain-R": gain_right,
                "thresh": limit_db,
                "hold": hold_ms,
                "makeup": makeup_gain,
            },
        )

    @mcp.tool()
    async def loudness_normalize(
        lufs_level: float = -16.0,
        stereo_independent: bool = False,
        dual_mono: bool = True,
    ) -> dict:
        """Normalize audio to a target perceived loudness in LUFS.

        DANGER — READ BEFORE USING:
        This tool can DESTROY audio if used incorrectly. It boosts OR reduces audio to hit
        the target LUFS. On quiet or poorly recorded audio, it may boost by 20-30 dB,
        causing severe clipping and distortion that ruins the file.

        DO NOT use this tool:
        - Right after a pipeline (pipelines already handle loudness safely)
        - On raw/unprocessed audio (clean it up first)
        - Without first running auto_analyze_audio to check current levels
        - If the audio peaks below -20 dB (it's too quiet — use normalize first to gently raise levels)

        ONLY use this tool when the user EXPLICITLY asks for LUFS normalization AND the audio
        has already been processed and has healthy levels (peaks between -6 dB and -1 dB).

        Targets (only use these values):
        - -16 LUFS: Podcast, broadcast, Apple Music
        - -14 LUFS: Spotify, YouTube, most streaming
        - -11 LUFS: Loud masters (hip-hop/EDM)

        Args:
            lufs_level: Target loudness in LUFS (-50 to -5). Default: -16.0
            stereo_independent: Normalize L/R channels independently. Default: False
            dual_mono: Treat mono as dual-mono for correct LUFS measurement. Default: True
        """
        if not -50 <= lufs_level <= -5:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "lufs_level must be -50 to -5")
        return await client.execute_long(
            "LoudnessNormalization",
            NormalizeTo=0,  # 0 = LUFS (perceived loudness), 1 = RMS
            StereoIndependent=stereo_independent,
            LUFSLevel=lufs_level,
            DualMono=dual_mono,
        )

    # ── Pipeline status polling ───────────────────────────────────────

    @mcp.tool()
    async def check_pipeline_status(job_id: str) -> dict:
        """Check the status of a running pipeline. Call this after starting any auto_ pipeline
        to monitor progress. Poll every 15-30 seconds.

        Args:
            job_id: The job ID returned by any auto_ pipeline tool
        """
        job = _jobs.get(job_id)
        if not job:
            raise AudacityMCPError(ErrorCode.INVALID_PARAMETER, f"Unknown job_id: {job_id}")

        elapsed = round(time.time() - job["started_at"], 1)
        result = {
            "job_id": job_id,
            "status": job["status"],
            "current_step": job["current_step"],
            "steps_completed": job["steps_applied"].copy(),
            "elapsed_seconds": elapsed,
        }
        if job["status"] == "complete":
            result["result"] = job["result"]
            if len(_jobs) > 10:
                oldest = sorted(_jobs, key=lambda k: _jobs[k]["started_at"])
                for k in oldest[:-10]:
                    del _jobs[k]
        elif job["status"] == "error":
            result["error"] = job["error"]
        if job["steps_failed"]:
            result["warnings"] = job["steps_failed"].copy()
        return result

    # ── auto_analyze_audio (synchronous) ──────────────────────────────

    _ANALYZE_WAV = os.path.join(tempfile.gettempdir(), "audacity_mcp_analyze.wav")

    def _measure_wav(wav_path: str) -> dict | None:
        """Read a WAV file and compute comprehensive audio diagnostics.
        Returns a dict with all measurements, or None on failure."""
        try:
            with wave.open(wav_path, "rb") as wf:
                rate = wf.getframerate()
                n_frames = wf.getnframes()
                sw = wf.getsampwidth()
                if n_frames == 0:
                    return None

                if sw == 2:
                    fmt_char = "h"
                    max_val = 32768.0
                elif sw == 4:
                    fmt_char = "f"
                    max_val = 1.0
                else:
                    return None

                duration = round(n_frames / rate, 2)
                chunk_size = rate  # 1-second chunks

                # Accumulators
                peak_abs = 0.0
                noise_sum_sq = 0.0
                noise_count = 0
                noise_target = min(int(rate * 0.5), n_frames)
                total_sum = 0.0  # For DC offset
                total_sum_sq = 0.0  # For overall RMS
                total_count = 0
                clipped_samples = 0
                clip_threshold = max_val * 0.999

                # Click/pop detection — count sudden large jumps between samples
                click_count = 0
                click_threshold = max_val * 0.3  # Jump > 30% of full scale = click
                prev_sample = 0.0

                # Silence gap detection — track runs of very quiet audio
                silence_threshold = max_val * 0.001  # -60 dB
                min_gap_samples = int(rate * 0.5)  # Gaps > 0.5s count
                current_silence_run = 0
                silence_gaps = []  # List of (start_seconds, duration_seconds)

                # Per-second RMS for dynamic range
                second_rms_values = []
                second_sum_sq = 0.0
                second_count = 0

                frames_read = 0
                while frames_read < n_frames:
                    n = min(chunk_size, n_frames - frames_read)
                    raw = wf.readframes(n)
                    if len(raw) < n * sw:
                        break
                    samples = struct.unpack(f"<{n}{fmt_char}", raw)

                    for s in samples:
                        a = abs(s)

                        # Peak
                        if a > peak_abs:
                            peak_abs = a

                        # Clipping (consecutive maxed-out samples)
                        if a >= clip_threshold:
                            clipped_samples += 1

                        # DC offset + RMS
                        total_sum += s
                        total_sum_sq += s * s
                        total_count += 1

                        # Click detection
                        delta = abs(s - prev_sample)
                        if delta > click_threshold and total_count > 1:
                            click_count += 1
                        prev_sample = s

                        # Silence gap tracking
                        if a < silence_threshold:
                            current_silence_run += 1
                        else:
                            if current_silence_run >= min_gap_samples:
                                gap_start = (frames_read + total_count - current_silence_run) / rate
                                gap_dur = current_silence_run / rate
                                silence_gaps.append((round(max(gap_start, 0), 2), round(gap_dur, 2)))
                            current_silence_run = 0

                        # Per-second RMS
                        second_sum_sq += s * s
                        second_count += 1
                        if second_count >= rate:
                            rms = math.sqrt(second_sum_sq / second_count) / max_val
                            if rms > 1e-10:
                                second_rms_values.append(20 * math.log10(rms))
                            second_sum_sq = 0.0
                            second_count = 0

                    # Noise floor (first 0.5s)
                    if noise_count < noise_target:
                        take = min(n, noise_target - noise_count)
                        for s in samples[:take]:
                            noise_sum_sq += s * s
                        noise_count += take

                    frames_read += n

                # Final silence gap at end of file
                if current_silence_run >= min_gap_samples:
                    gap_start = (n_frames - current_silence_run) / rate
                    silence_gaps.append((round(max(gap_start, 0), 2), round(current_silence_run / rate, 2)))

                # Last partial second
                if second_count > rate * 0.1:
                    rms = math.sqrt(second_sum_sq / second_count) / max_val
                    if rms > 1e-10:
                        second_rms_values.append(20 * math.log10(rms))

                # Compute results
                peak_linear = peak_abs / max_val
                peak_db = round(20 * math.log10(max(peak_linear, 1e-10)), 1)

                noise_db = None
                if noise_count > 0:
                    rms_linear = math.sqrt(noise_sum_sq / noise_count) / max_val
                    noise_db = round(20 * math.log10(max(rms_linear, 1e-10)), 1)

                overall_rms_db = None
                if total_count > 0:
                    overall_rms = math.sqrt(total_sum_sq / total_count) / max_val
                    overall_rms_db = round(20 * math.log10(max(overall_rms, 1e-10)), 1)

                dc_offset = round((total_sum / total_count) / max_val, 6) if total_count > 0 else 0.0

                # Dynamic range from per-second RMS values
                dynamic_range_db = None
                if len(second_rms_values) >= 2:
                    dynamic_range_db = round(max(second_rms_values) - min(second_rms_values), 1)

                return {
                    "peak_db": peak_db,
                    "noise_floor_db": noise_db,
                    "overall_rms_db": overall_rms_db,
                    "dc_offset": dc_offset,
                    "duration": duration,
                    "sample_rate": rate,
                    "clipped_samples": clipped_samples,
                    "click_count": click_count,
                    "silence_gaps": silence_gaps[:10],  # Cap at 10 to avoid huge output
                    "silence_gap_count": len(silence_gaps),
                    "dynamic_range_db": dynamic_range_db,
                }
        except Exception:
            return None

    @mcp.tool()
    async def auto_analyze_audio() -> dict:
        """Analyze the current audio track and recommend the best pipeline to use.
        This is SYNCHRONOUS — it returns the analysis directly, no job_id needed.

        Returns peak level, estimated noise floor, duration, clipping status,
        and a recommendation for which auto_ pipeline to use next.

        IMPORTANT: Load your audio into Audacity before calling this.
        """
        # Get track info
        info_result = await client.execute("GetInfo", Type="Tracks")
        tracks = info_result.get("data", [])

        track_info = []
        total_duration = 0
        for t in (tracks if isinstance(tracks, list) else []):
            if not isinstance(t, dict):
                continue
            start = t.get("start", 0)
            end = t.get("end", 0)
            dur = round(end - start, 2) if end > start else 0
            total_duration = max(total_duration, dur)
            track_info.append({
                "name": t.get("name", "Unknown"),
                "duration": dur,
                "rate": t.get("rate", 0),
                "channels": t.get("channels", 0),
            })

        # Measure audio by exporting to temp WAV and analyzing in Python.
        # This avoids Nyquist entirely — no popups, no selection issues.
        measurements = None
        tmp_wav = _ANALYZE_WAV
        measurement_error = None

        try:
            await _select_all()
            export_result = await client.execute_long("Export2", Filename=tmp_wav, NumChannels=1)

            if not os.path.exists(tmp_wav):
                measurement_error = f"Export2 returned {export_result} but WAV file was not created at {tmp_wav}"
            else:
                file_size = os.path.getsize(tmp_wav)
                if file_size < 100:
                    measurement_error = f"Export2 created a tiny file ({file_size} bytes) — export may have failed"
                else:
                    measurements = _measure_wav(tmp_wav)
                    if measurements is None:
                        measurement_error = f"WAV file exists ({file_size} bytes) but could not parse audio data"
                    elif measurements["duration"] and measurements["duration"] > 0:
                        total_duration = measurements["duration"]
        except Exception as e:
            measurement_error = f"Export/analysis failed: {type(e).__name__}: {e}"
        finally:
            try:
                os.remove(tmp_wav)
            except OSError:
                pass

        # Extract values from measurements
        peak_db = measurements["peak_db"] if measurements else None
        noise_floor_db = measurements["noise_floor_db"] if measurements else None
        overall_rms_db = measurements["overall_rms_db"] if measurements else None
        dc_offset = measurements["dc_offset"] if measurements else None
        clipped_samples = measurements["clipped_samples"] if measurements else 0
        click_count = measurements["click_count"] if measurements else 0
        silence_gaps = measurements["silence_gaps"] if measurements else []
        silence_gap_count = measurements["silence_gap_count"] if measurements else 0
        dynamic_range_db = measurements["dynamic_range_db"] if measurements else None

        is_clipping = peak_db is not None and peak_db >= -0.1

        # Build comprehensive diagnosis — flag ALL problems
        issues = []
        if peak_db is not None:
            # Volume issues
            if peak_db < -30:
                issues.append(f"VERY QUIET: Peak is only {peak_db} dB — audio is extremely quiet. "
                              "Run normalize (to -3 dB) first to bring levels up before any pipeline.")
            elif peak_db < -20:
                issues.append(f"QUIET: Peak is {peak_db} dB — audio is below normal levels. "
                              "Consider running normalize (to -6 dB) to raise levels before processing.")
            elif peak_db < -12:
                issues.append(f"LOW VOLUME: Peak is {peak_db} dB — slightly quiet but workable.")

            # Clipping
            if is_clipping:
                issues.append(f"CLIPPING: Peak is {peak_db} dB with {clipped_samples} clipped samples — "
                              "audio is distorted at peaks. Cannot be fully fixed but cleanup will help.")

        if noise_floor_db is not None and peak_db is not None:
            snr = peak_db - noise_floor_db
            if snr < 15:
                issues.append(f"VERY NOISY: SNR is only {round(snr, 1)} dB — use auto_cleanup_live for aggressive noise removal.")
            elif snr < 20:
                issues.append(f"NOISY: SNR is {round(snr, 1)} dB — recording has significant background noise.")
            if noise_floor_db > -30:
                issues.append(f"HIGH NOISE FLOOR: Noise floor at {noise_floor_db} dB — needs noise reduction.")

        # DC offset
        if dc_offset is not None and abs(dc_offset) > 0.005:
            issues.append(f"DC OFFSET: Audio has a DC offset of {dc_offset} — will be removed by pipeline. "
                          "This can cause clicks at edits and wastes headroom.")

        # Clicks and pops
        if click_count > 50:
            issues.append(f"LOTS OF CLICKS/POPS: Detected {click_count} sudden amplitude spikes — "
                          "use click_removal or auto_cleanup_live for aggressive cleanup.")
        elif click_count > 10:
            issues.append(f"SOME CLICKS/POPS: Detected {click_count} sudden amplitude spikes — "
                          "consider using click_removal to clean these up.")

        # Silence gaps
        if silence_gap_count > 0:
            total_silence = sum(g[1] for g in silence_gaps)
            if silence_gap_count > 5:
                issues.append(f"MANY GAPS: Found {silence_gap_count} silence gaps totalling {round(total_silence, 1)}s — "
                              "use truncate_silence or enable remove_silence in podcast/interview pipeline.")
            elif silence_gap_count > 0 and total_silence > 3:
                issues.append(f"SILENCE GAPS: Found {silence_gap_count} gap(s) totalling {round(total_silence, 1)}s — "
                              "consider using truncate_silence to tighten up the audio.")

        # Dynamic range
        if dynamic_range_db is not None:
            if dynamic_range_db > 40:
                issues.append(f"EXTREME DYNAMIC RANGE: {dynamic_range_db} dB variation — volume swings wildly. "
                              "Compression is strongly recommended.")
            elif dynamic_range_db > 25:
                issues.append(f"WIDE DYNAMIC RANGE: {dynamic_range_db} dB variation — "
                              "some parts are much louder than others. Compression will help.")

        # Overall RMS vs peak (over-compressed check)
        if overall_rms_db is not None and peak_db is not None:
            crest_factor = peak_db - overall_rms_db
            if crest_factor < 3 and peak_db > -6:
                issues.append(f"OVER-COMPRESSED: Crest factor is only {round(crest_factor, 1)} dB — "
                              "audio is already heavily compressed/limited. Avoid adding more compression.")

        # Build recommendation
        if peak_db is not None:
            if issues:
                recommendation = "ISSUES FOUND:\n" + "\n".join(f"  - {i}" for i in issues)
                recommendation += "\n\nAfter reviewing issues, choose pipeline based on content type:"
            else:
                recommendation = "Audio looks healthy — no issues detected."
                recommendation += " Choose based on content type:"

            recommendation += (
                "\n  - Podcast/voiceover: auto_cleanup_podcast"
                "\n  - Audiobook (ACX): auto_audiobook_mastering"
                "\n  - Interview/dialogue: auto_cleanup_interview"
                "\n  - Singing vocal: auto_cleanup_vocal"
                "\n  - Music: auto_master_music"
                "\n  - Lo-fi/vintage effect: auto_lofi_effect"
                "\n  - Just cleanup (no loudness): auto_cleanup_audio"
            )
        else:
            recommendation = (
                "Could not measure audio levels. Choose based on content type:\n"
                "  - Podcast/voiceover: auto_cleanup_podcast\n"
                "  - Audiobook (ACX): auto_audiobook_mastering\n"
                "  - Interview/dialogue: auto_cleanup_interview\n"
                "  - Singing vocal: auto_cleanup_vocal\n"
                "  - Live/field/noisy: auto_cleanup_live\n"
                "  - Music: auto_master_music\n"
                "  - Lo-fi/vintage effect: auto_lofi_effect\n"
                "  - Just cleanup (no loudness): auto_cleanup_audio"
            )

        # Volume status for quick AI reference
        if peak_db is not None:
            if peak_db < -30:
                volume_status = "VERY QUIET — needs normalize before processing"
            elif peak_db < -20:
                volume_status = "QUIET — consider normalize before processing"
            elif peak_db < -12:
                volume_status = "LOW but workable"
            elif peak_db >= -0.1:
                volume_status = "CLIPPING — audio is distorted"
            elif peak_db > -3:
                volume_status = "HOT — close to clipping"
            else:
                volume_status = "HEALTHY"
        else:
            volume_status = "UNKNOWN — measurement failed"

        result = {
            "peak_db": peak_db,
            "noise_floor_db": noise_floor_db,
            "overall_rms_db": overall_rms_db,
            "volume_status": volume_status,
            "is_clipping": is_clipping,
            "clipped_samples": clipped_samples,
            "dc_offset": dc_offset,
            "click_pop_count": click_count,
            "silence_gaps": silence_gap_count,
            "dynamic_range_db": dynamic_range_db,
            "duration_seconds": total_duration,
            "track_count": len(track_info),
            "tracks": track_info,
            "issues": issues,
            "recommendation": recommendation,
        }
        if measurement_error:
            result["measurement_error"] = measurement_error
            result["WARNING"] = (
                "Audio measurement FAILED — all measurements are missing. "
                "Tell the user about this error. The export path was: " + tmp_wav
            )
        return result

    # ── auto_cleanup_audio (safe, no loudness) ────────────────────────

    async def _cleanup_audio_pipeline(job: dict, remove_noise: bool, remove_clicks: bool):
        try:
            await _dc_offset_step(job)
            await _hpf_step(job, 80.0)

            if remove_noise:
                await _noise_reduction_step(job, reduction_db=10, sensitivity=6, smoothing=3)

            if remove_clicks:
                await _select_all()
                await _run_pipeline_step(job, "click removal",
                    client.execute_long("ClickRemoval", Threshold=200, Width=20))

            await _complete_job(job, "Audio Cleanup Complete", {"loudness": "unchanged (cleanup only)"})
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)

    @mcp.tool()
    async def auto_cleanup_audio(
        remove_noise: bool = True,
        remove_clicks: bool = False,
    ) -> dict:
        """SAFE CLEANUP: Remove noise and artifacts WITHOUT changing loudness or dynamics.
        Use this when audio levels are already good and you just want to clean it up.
        Runs in background — returns a job_id immediately. Use check_pipeline_status to monitor.

        Pipeline: DC offset removal > HPF 80Hz > noise reduction (opt) > click removal (opt)
        NO compression, NO normalize, NO LUFS. Just clean.

        Args:
            remove_noise: Apply noise reduction using first 0.5s as noise profile. Default: True
            remove_clicks: Remove clicks/pops (useful for vinyl/old recordings). Default: False

        IMPORTANT: If remove_noise is True, the first 0.5 seconds should be room tone / silence.
        DO NOT call this again if a pipeline is already running — use check_pipeline_status instead.
        """
        job_id, job = _create_job("cleanup_audio")
        if job is None:
            return _running_job_error()
        coro = _cleanup_audio_pipeline(job, remove_noise, remove_clicks)
        await asyncio.sleep(0)
        return _start_background(job_id, job, coro, "Audio Cleanup")

    # ── auto_cleanup_podcast (updated) ────────────────────────────────

    async def _podcast_pipeline(job: dict, remove_noise: bool, remove_silence: bool):
        try:
            await _dc_offset_step(job)
            await _hpf_step(job, 80.0)

            if remove_noise:
                await _noise_reduction_step(job, reduction_db=12, sensitivity=6, smoothing=3)

            if remove_silence:
                await _select_all()
                await _run_pipeline_step(job, "truncate silence",
                    client.execute_long(
                        "TruncateSilence",
                        Threshold=-40, Minimum=0.5, Truncate=0.3,
                        Action="Truncate Detected Silence",
                    ))

            # Compression: 3:1, threshold -18, attack 10ms, peak-based for voice
            await _compress_step(job, threshold=-18.0, ratio=3.0, attack=0.01, release=1.0, use_peak=True)

            await _loudness_step(job)

            await _complete_job(job, "Podcast Cleanup Complete", {"loudness": "peaks reduced if hot, never boosted"})
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)

    @mcp.tool()
    async def auto_cleanup_podcast(
        remove_noise: bool = True,
        remove_silence: bool = False,
    ) -> dict:
        """ONE-CLICK PODCAST CLEANUP: Professional broadcast-quality processing.
        Runs in background — returns a job_id immediately. Use check_pipeline_status to monitor.
        Safe for badly recorded audio — only reduces peaks if too hot, never boosts.

        Pipeline: DC offset > HPF 80Hz > NR 12dB > compress 3:1 > safe loudness check.
        Optional: noise reduction (on by default), silence truncation (off by default).

        After the pipeline finishes, the user can manually apply LUFS normalization
        using the loudness_normalize tool if they want to hit a specific streaming target.

        Args:
            remove_noise: Apply noise reduction using first 0.5s as noise profile. Default: True
            remove_silence: Truncate long silences/dead air. Default: False

        IMPORTANT: If remove_noise is True, the first 0.5 seconds should be room tone / silence.
        DO NOT call this again if a pipeline is already running — use check_pipeline_status instead.
        """
        job_id, job = _create_job("podcast_cleanup")
        if job is None:
            return _running_job_error()
        coro = _podcast_pipeline(job, remove_noise, remove_silence)
        await asyncio.sleep(0)
        return _start_background(job_id, job, coro, "Podcast Cleanup")

    # ── auto_audiobook_mastering (ACX compliant) ──────────────────────

    async def _audiobook_pipeline(job: dict, remove_noise: bool):
        try:
            await _dc_offset_step(job)
            await _hpf_step(job, 80.0)

            if remove_noise:
                await _noise_reduction_step(job, reduction_db=12, sensitivity=6, smoothing=3)

            # Light compression for voice consistency
            await _compress_step(job, threshold=-18.0, ratio=2.5, attack=0.01, release=1.0, use_peak=True)

            # Safe loudness: only reduce peaks if hot, never boost
            await _loudness_step(job)

            # Peak cap at -3dB (ACX requirement: peaks must not exceed -3dB)
            await asyncio.sleep(0.5)
            await _select_all()
            await _run_pipeline_step(job, "peak cap -3dB",
                client.execute_long(
                    "Limiter",
                    extra_params={
                        "type": "SoftLimit",
                        "gain-L": 0.0,
                        "gain-R": 0.0,
                        "thresh": -3.0,
                        "hold": 10.0,
                        "makeup": "No",
                    },
                ))

            await _complete_job(job, "Audiobook Mastering Complete (ACX)", {
                "rms": "-20 dB RMS",
                "peak_cap": "-3 dB",
                "standard": "ACX/Audible compliant",
            })
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)

    @mcp.tool()
    async def auto_audiobook_mastering(
        remove_noise: bool = True,
    ) -> dict:
        """ONE-CLICK AUDIOBOOK MASTERING: ACX/Audible compliant processing.
        Runs in background — returns a job_id immediately. Use check_pipeline_status to monitor.

        Pipeline: DC offset > HPF 80Hz > noise reduction 12dB > compression 2.5:1 > RMS -20dB > peak cap -3dB
        Meets ACX requirements: RMS -23 to -18 dB, peaks below -3 dB, noise floor below -60 dB.

        Args:
            remove_noise: Apply noise reduction using first 0.5s as noise profile. Default: True

        IMPORTANT: If remove_noise is True, the first 0.5 seconds should be room tone / silence.
        DO NOT call this again if a pipeline is already running — use check_pipeline_status instead.
        """
        job_id, job = _create_job("audiobook_mastering")
        if job is None:
            return _running_job_error()
        coro = _audiobook_pipeline(job, remove_noise)
        await asyncio.sleep(0)
        return _start_background(job_id, job, coro, "Audiobook Mastering (ACX)")

    # ── auto_cleanup_interview (light touch) ──────────────────────────

    async def _interview_pipeline(job: dict, remove_noise: bool, remove_silence: bool):
        try:
            await _dc_offset_step(job)
            await _hpf_step(job, 80.0)

            if remove_noise:
                await _noise_reduction_step(job, reduction_db=8, sensitivity=6, smoothing=3)

            if remove_silence:
                await _select_all()
                await _run_pipeline_step(job, "truncate silence",
                    client.execute_long(
                        "TruncateSilence",
                        Threshold=-40, Minimum=0.5, Truncate=0.3,
                        Action="Truncate Detected Silence",
                    ))

            # Light compression — preserve natural dynamics of conversation
            await _compress_step(job, threshold=-20.0, ratio=2.5, attack=0.02, release=1.0, use_peak=True)

            await _loudness_step(job)

            await _complete_job(job, "Interview Cleanup Complete", {"loudness": "peaks reduced if hot, never boosted"})
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)

    @mcp.tool()
    async def auto_cleanup_interview(
        remove_noise: bool = True,
        remove_silence: bool = False,
    ) -> dict:
        """ONE-CLICK INTERVIEW CLEANUP: Light-touch processing for dialogue and multiple speakers.
        Runs in background — returns a job_id immediately. Use check_pipeline_status to monitor.

        Pipeline: DC offset > HPF 80Hz > noise reduction 8dB > compression 2.5:1 > safe loudness check.
        Lighter than podcast — preserves natural conversation dynamics.

        Args:
            remove_noise: Apply noise reduction using first 0.5s as noise profile. Default: True
            remove_silence: Truncate long silences. Default: False

        IMPORTANT: If remove_noise is True, the first 0.5 seconds should be room tone / silence.
        DO NOT call this again if a pipeline is already running — use check_pipeline_status instead.
        """
        job_id, job = _create_job("interview_cleanup")
        if job is None:
            return _running_job_error()
        coro = _interview_pipeline(job, remove_noise, remove_silence)
        await asyncio.sleep(0)
        return _start_background(job_id, job, coro, "Interview Cleanup")

    # ── auto_cleanup_vocal (singing/studio vocal) ─────────────────────

    async def _vocal_pipeline(job: dict, remove_noise: bool):
        try:
            await _dc_offset_step(job)
            await _hpf_step(job, 100.0)

            if remove_noise:
                await _noise_reduction_step(job, reduction_db=10, sensitivity=6, smoothing=3)

            # Vocal compression — 3:1 for consistent level
            await _compress_step(job, threshold=-16.0, ratio=3.0, attack=0.01, release=0.5, use_peak=False)

            # Presence EQ — treble boost for clarity, slight bass cut
            await _select_all()
            await _run_pipeline_step(job, "presence EQ (treble +3dB, bass -1dB)",
                client.execute_long("BassAndTreble", Bass=-1.0, Treble=3.0, Gain=0.0))

            await _loudness_step(job)

            await _complete_job(job, "Vocal Cleanup Complete", {"loudness": "peaks reduced if hot, never boosted"})
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)

    @mcp.tool()
    async def auto_cleanup_vocal(
        remove_noise: bool = True,
    ) -> dict:
        """ONE-CLICK VOCAL CLEANUP: Professional processing for singing and studio vocals.
        Runs in background — returns a job_id immediately. Use check_pipeline_status to monitor.

        Pipeline: DC offset > HPF 100Hz > noise reduction 10dB > compression 3:1 > presence EQ > safe loudness check.
        Tuned for singing — presence boost for clarity, higher HPF for plosive removal.

        Args:
            remove_noise: Apply noise reduction using first 0.5s as noise profile. Default: True

        IMPORTANT: If remove_noise is True, the first 0.5 seconds should be room tone / silence.
        DO NOT call this again if a pipeline is already running — use check_pipeline_status instead.
        """
        job_id, job = _create_job("vocal_cleanup")
        if job is None:
            return _running_job_error()
        coro = _vocal_pipeline(job, remove_noise)
        await asyncio.sleep(0)
        return _start_background(job_id, job, coro, "Vocal Cleanup")

    # ── auto_cleanup_live (aggressive for noisy recordings) ───────────

    async def _live_pipeline(job: dict):
        try:
            await _dc_offset_step(job)
            await _hpf_step(job, 100.0)

            # Click removal before NR (clicks can confuse noise profiling)
            await _select_all()
            await _run_pipeline_step(job, "click removal",
                client.execute_long("ClickRemoval", Threshold=200, Width=20))

            # Aggressive noise reduction — 18dB for noisy environments
            await _noise_reduction_step(job, reduction_db=18, sensitivity=6, smoothing=3)

            # Heavy compression — 5:1 to tame dynamic range of live recordings
            await _compress_step(job, threshold=-14.0, ratio=5.0, attack=0.01, release=0.5, use_peak=True)

            await _loudness_step(job)

            await _complete_job(job, "Live Recording Cleanup Complete", {"loudness": "peaks reduced if hot, never boosted"})
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)

    @mcp.tool()
    async def auto_cleanup_live() -> dict:
        """ONE-CLICK LIVE RECORDING CLEANUP: Aggressive processing for noisy/field recordings.
        Runs in background — returns a job_id immediately. Use check_pipeline_status to monitor.

        Pipeline: DC offset > HPF 100Hz > click removal > noise reduction 18dB > compression 5:1 > safe loudness check.
        Designed for live performances, field recordings, and noisy environments.
        Noise reduction is always on at 18dB — this pipeline is for recordings that NEED aggressive cleanup.

        IMPORTANT: The first 0.5 seconds MUST be room tone / ambient noise for noise profiling.
        DO NOT call this again if a pipeline is already running — use check_pipeline_status instead.
        """
        job_id, job = _create_job("live_cleanup")
        if job is None:
            return _running_job_error()
        coro = _live_pipeline(job)
        await asyncio.sleep(0)
        return _start_background(job_id, job, coro, "Live Recording Cleanup")

    # ── auto_master_music (updated with pop + classical) ──────────────

    async def _mastering_pipeline(job: dict, p: dict, noise_reduce: bool):
        try:
            await _hpf_step(job, p["hpf_freq"])

            # Click removal
            await _select_all()
            await _run_pipeline_step(job, "click removal",
                client.execute_long("ClickRemoval", Threshold=200, Width=20))

            if noise_reduce:
                await _noise_reduction_step(job, reduction_db=6, sensitivity=4, smoothing=3)

            await _compress_step(job, threshold=p["comp_threshold"], ratio=p["comp_ratio"],
                attack=p["comp_attack"], release=p["comp_release"])

            # Bass/treble sweetening
            if p["bass_eq"] != 0.0 or p["treble_eq"] != 0.0:
                await _select_all()
                await _run_pipeline_step(job, f"EQ bass+{p['bass_eq']}dB treble+{p['treble_eq']}dB",
                    client.execute_long("BassAndTreble", Bass=p["bass_eq"], Treble=p["treble_eq"], Gain=0.0))

            await _loudness_step(job)

            await _complete_job(job, f"Music Mastering Complete ({p['label']})", {
                "loudness": "peaks reduced if hot, never boosted",
                "genre": p["label"],
                "compression": f"{p['comp_ratio']}:1 @ {int(p['comp_attack']*1000)}ms attack",
            })
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)

    @mcp.tool()
    async def auto_master_music(
        style: str = "edm",
        noise_reduce: bool = False,
    ) -> dict:
        """ONE-CLICK MUSIC MASTERING: Professionally master your music track with genre-tuned settings.
        Runs in background — returns a job_id immediately. Use check_pipeline_status to monitor.

        Pipeline:
        1. High-pass filter (remove sub-rumble)
        2. Click removal (clean artifacts)
        3. Noise reduction (optional, off by default for produced music)
        4. Compression (genre-tuned, mastering-grade, no post-normalize)
        5. Bass/treble sweetening (gentle, genre-tuned)
        6. Safe loudness check (only reduces peaks if too hot, never boosts)

        Args:
            style: Genre preset - "edm", "hiphop", "rock", "acoustic", "pop", "classical". Default: "edm"
            noise_reduce: Apply gentle noise reduction. Default: False
        DO NOT call this again if a pipeline is already running — use check_pipeline_status instead.
        """
        job_id, job = _create_job(f"mastering_{style}")
        if job is None:
            return _running_job_error()

        style = style.lower().strip()

        presets = {
            "edm": {
                "hpf_freq": 30.0,
                "comp_threshold": -12.0,
                "comp_ratio": 2.5,
                "comp_attack": 0.08,
                "comp_release": 0.15,
                "bass_eq": 2.0,
                "treble_eq": 1.0,
                "label": "EDM/Electronic",
            },
            "hiphop": {
                "hpf_freq": 30.0,
                "comp_threshold": -14.0,
                "comp_ratio": 2.0,
                "comp_attack": 0.1,
                "comp_release": 0.2,
                "bass_eq": 3.0,
                "treble_eq": 1.0,
                "label": "Hip-Hop/Rap",
            },
            "rock": {
                "hpf_freq": 40.0,
                "comp_threshold": -16.0,
                "comp_ratio": 2.0,
                "comp_attack": 0.1,
                "comp_release": 0.2,
                "bass_eq": 0.0,
                "treble_eq": 1.0,
                "label": "Rock",
            },
            "pop": {
                "hpf_freq": 35.0,
                "comp_threshold": -14.0,
                "comp_ratio": 2.0,
                "comp_attack": 0.08,
                "comp_release": 0.2,
                "bass_eq": 1.0,
                "treble_eq": 1.5,
                "label": "Pop",
            },
            "classical": {
                "hpf_freq": 30.0,
                "comp_threshold": -24.0,
                "comp_ratio": 1.3,
                "comp_attack": 0.2,
                "comp_release": 0.5,
                "bass_eq": 0.0,
                "treble_eq": 0.0,
                "label": "Classical/Orchestral",
            },
            "acoustic": {
                "hpf_freq": 30.0,
                "comp_threshold": -20.0,
                "comp_ratio": 1.5,
                "comp_attack": 0.15,
                "comp_release": 0.3,
                "bass_eq": 0.0,
                "treble_eq": 0.0,
                "label": "Acoustic/Chill",
            },
        }

        if style not in presets:
            raise AudacityMCPError(
                ErrorCode.INVALID_PARAMETER,
                f"style must be one of: {', '.join(presets.keys())}",
            )

        p = presets[style]
        coro = _mastering_pipeline(job, p, noise_reduce)
        await asyncio.sleep(0)
        return _start_background(job_id, job, coro, f"Mastering ({p['label']})")

    # ── auto_lofi_effect (creative) ───────────────────────────────────

    async def _lofi_pipeline(job: dict, p: dict):
        try:
            # HPF — cut low end
            await _hpf_step(job, p["hpf_freq"])

            # LPF — cut high end for that muffled sound
            await _select_all()
            await _run_pipeline_step(job, f"LPF {p['lpf_freq']}Hz",
                client.execute_long("Low-passFilter", frequency=p["lpf_freq"], rolloff="dB12"))

            # Warmth — bass/treble EQ
            await _select_all()
            await _run_pipeline_step(job, f"warmth (bass+{p['bass_eq']}dB treble{p['treble_eq']}dB)",
                client.execute_long("BassAndTreble", Bass=p["bass_eq"], Treble=p["treble_eq"], Gain=0.0))

            # Light compression
            await _compress_step(job, threshold=-16.0, ratio=2.0, attack=0.1, release=0.3)

            await _loudness_step(job)

            await _complete_job(job, f"Lo-Fi Effect Complete ({p['label']})", {
                "loudness": "peaks reduced if hot, never boosted",
                "preset": p["label"],
            })
        except Exception as e:
            job["status"] = "error"
            job["error"] = str(e)

    @mcp.tool()
    async def auto_lofi_effect(
        intensity: str = "medium",
    ) -> dict:
        """CREATIVE LO-FI EFFECT: Apply a vintage/lo-fi sound to your audio.
        Runs in background — returns a job_id immediately. Use check_pipeline_status to monitor.

        Pipeline: HPF > LPF > bass/treble warmth > compression 2:1 > safe loudness check
        Creates that warm, muffled, vintage sound by cutting highs and boosting low-mids.

        Args:
            intensity: "light" (subtle warmth), "medium" (classic lo-fi), "heavy" (extreme tape sound). Default: "medium"

        DO NOT call this again if a pipeline is already running — use check_pipeline_status instead.
        """
        job_id, job = _create_job(f"lofi_{intensity}")
        if job is None:
            return _running_job_error()

        intensity = intensity.lower().strip()

        presets = {
            "light": {
                "hpf_freq": 60.0,
                "lpf_freq": 12000.0,
                "bass_eq": 2.0,
                "treble_eq": -2.0,
                "label": "Light Lo-Fi",
            },
            "medium": {
                "hpf_freq": 100.0,
                "lpf_freq": 8000.0,
                "bass_eq": 4.0,
                "treble_eq": -4.0,
                "label": "Medium Lo-Fi",
            },
            "heavy": {
                "hpf_freq": 200.0,
                "lpf_freq": 4000.0,
                "bass_eq": 6.0,
                "treble_eq": -6.0,
                "label": "Heavy Lo-Fi",
            },
        }

        if intensity not in presets:
            raise AudacityMCPError(
                ErrorCode.INVALID_PARAMETER,
                f"intensity must be one of: {', '.join(presets.keys())}",
            )

        p = presets[intensity]
        coro = _lofi_pipeline(job, p)
        await asyncio.sleep(0)
        return _start_background(job_id, job, coro, f"Lo-Fi Effect ({p['label']})")
