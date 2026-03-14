from mcp.server.fastmcp import FastMCP
from shared.error_codes import AudacityMCPError, ErrorCode


def register(mcp: FastMCP):
    from server.main import client

    @mcp.tool()
    async def effect_amplify(ratio: float = 1.0) -> dict:
        """Amplify the selected audio by a ratio. Select audio first.

        Args:
            ratio: Amplification ratio (e.g. 1.5 = 150%, 0.5 = 50%). Must be > 0. Default: 1.0
        """
        if ratio <= 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "ratio must be > 0")
        return await client.execute_long("Amplify", Ratio=ratio)

    @mcp.tool()
    async def effect_fade_in() -> dict:
        """Apply a fade-in to the selected audio. Select the region to fade first."""
        return await client.execute("FadeIn")

    @mcp.tool()
    async def effect_fade_out() -> dict:
        """Apply a fade-out to the selected audio. Select the region to fade first."""
        return await client.execute("FadeOut")

    @mcp.tool()
    async def effect_reverb(
        room_size: float = 75.0,
        pre_delay: float = 10.0,
        reverberance: float = 50.0,
        hf_damping: float = 50.0,
        tone_low: float = 100.0,
        tone_high: float = 100.0,
        wet_gain: float = -1.0,
        dry_gain: float = -1.0,
        stereo_width: float = 100.0,
        wet_only: bool = False,
    ) -> dict:
        """Apply reverb effect to the selected audio.

        Args:
            room_size: Room size percentage (0-100). Default: 75
            pre_delay: Pre-delay in ms (0-200). Default: 10
            reverberance: Reverberance percentage (0-100). Default: 50
            hf_damping: High frequency damping (0-100). Default: 50
            tone_low: Tone low percentage (0-100). Default: 100
            tone_high: Tone high percentage (0-100). Default: 100
            wet_gain: Wet signal gain in dB. Default: -1.0
            dry_gain: Dry signal gain in dB. Default: -1.0
            stereo_width: Stereo width (0-100). Default: 100
            wet_only: Output only the wet signal. Default: False
        """
        for name, val, lo, hi in [
            ("room_size", room_size, 0, 100), ("pre_delay", pre_delay, 0, 200),
            ("reverberance", reverberance, 0, 100), ("hf_damping", hf_damping, 0, 100),
            ("tone_low", tone_low, 0, 100), ("tone_high", tone_high, 0, 100),
            ("stereo_width", stereo_width, 0, 100),
        ]:
            if not lo <= val <= hi:
                raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"{name} must be {lo}-{hi}")
        return await client.execute_long(
            "Reverb",
            RoomSize=room_size,
            PreDelay=pre_delay,
            Reverberance=reverberance,
            HfDamping=hf_damping,
            ToneLow=tone_low,
            ToneHigh=tone_high,
            WetGain=wet_gain,
            DryGain=dry_gain,
            StereoWidth=stereo_width,
            WetOnly=wet_only,
        )

    @mcp.tool()
    async def effect_echo(delay: float = 0.5, decay: float = 0.5) -> dict:
        """Apply echo effect to the selected audio.

        Args:
            delay: Delay time in seconds. Default: 0.5
            decay: Decay factor (0-1, lower = faster decay). Default: 0.5
        """
        if delay <= 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "delay must be > 0")
        if not 0 < decay < 1:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "decay must be between 0 and 1")
        return await client.execute_long("Echo", Delay=delay, Decay=decay)

    @mcp.tool()
    async def effect_change_pitch(semitones: float = 0.0) -> dict:
        """Change the pitch of the selected audio without changing tempo.

        Args:
            semitones: Number of semitones to shift (negative = lower, positive = higher)
        """
        return await client.execute_long("ChangePitch", Semitones=semitones)

    @mcp.tool()
    async def effect_change_tempo(percent: float = 0.0) -> dict:
        """Change the tempo of the selected audio without changing pitch.

        Args:
            percent: Percentage change (-95 to 3000, e.g. 50 = 50% faster, -25 = 25% slower)
        """
        if not -95 <= percent <= 3000:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "percent must be -95 to 3000")
        return await client.execute_long("ChangeTempo", Percentage=percent)

    @mcp.tool()
    async def effect_change_speed(percent: float = 0.0) -> dict:
        """Change speed of the selected audio (changes both tempo and pitch together).

        Args:
            percent: Percentage change (-99 to 4900, e.g. 100 = double speed)
        """
        if not -99 <= percent <= 4900:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "percent must be -99 to 4900")
        return await client.execute_long("ChangeSpeed", Percentage=percent)

    @mcp.tool()
    async def effect_equalization(curve_name: str = "Default", length: int = 4001) -> dict:
        """Apply EQ curve to the selected audio.

        Args:
            curve_name: Name of the EQ preset curve. Default: "Default"
            length: Filter length (odd number, 21-8191). Default: 4001
        """
        if not 21 <= length <= 8191:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "length must be 21-8191")
        if length % 2 == 0:
            raise AudacityMCPError(ErrorCode.INVALID_PARAMETER, "length must be an odd number")
        return await client.execute_long(
            "FilterCurve",
            CurveName=curve_name,
            FilterLength=length,
        )

    @mcp.tool()
    async def effect_phaser(
        stages: int = 2,
        dry_wet: int = 128,
        frequency: float = 0.4,
        phase: float = 0.0,
        depth: int = 100,
        feedback: int = 0,
    ) -> dict:
        """Apply phaser effect to the selected audio.

        Args:
            stages: Number of phaser stages (2-24, even only). Default: 2
            dry_wet: Dry/wet mix (0=dry, 255=wet). Default: 128
            frequency: LFO frequency in Hz (0.01-40). Default: 0.4
            phase: LFO start phase in degrees (0-360). Default: 0
            depth: Modulation depth (0-255). Default: 100
            feedback: Feedback percentage (-100 to 100). Default: 0
        """
        if not 2 <= stages <= 24 or stages % 2 != 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "stages must be even, 2-24")
        if not 0 <= dry_wet <= 255:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "dry_wet must be 0-255")
        if not 0.01 <= frequency <= 40:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "frequency must be 0.01-40")
        if not 0 <= phase <= 360:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "phase must be 0-360")
        if not 0 <= depth <= 255:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "depth must be 0-255")
        if not -100 <= feedback <= 100:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "feedback must be -100 to 100")
        return await client.execute_long(
            "Phaser",
            Stages=stages,
            DryWet=dry_wet,
            Freq=frequency,
            Phase=phase,
            Depth=depth,
            Feedback=feedback,
        )

    @mcp.tool()
    async def effect_wahwah(
        frequency: float = 1.5,
        phase: float = 0.0,
        depth: int = 70,
        resonance: float = 2.5,
        offset: int = 30,
    ) -> dict:
        """Apply wahwah effect to the selected audio.

        Args:
            frequency: LFO frequency in Hz (0.1-4.0). Default: 1.5
            phase: LFO start phase (0-360). Default: 0
            depth: Modulation depth (0-100). Default: 70
            resonance: Resonance (0.1-10). Default: 2.5
            offset: Frequency offset (0-100). Default: 30
        """
        if not 0.1 <= frequency <= 4.0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "frequency must be 0.1-4.0")
        if not 0 <= phase <= 360:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "phase must be 0-360")
        if not 0 <= depth <= 100:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "depth must be 0-100")
        if not 0.1 <= resonance <= 10:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "resonance must be 0.1-10")
        if not 0 <= offset <= 100:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "offset must be 0-100")
        return await client.execute_long(
            "Wahwah",
            Freq=frequency,
            Phase=phase,
            Depth=depth,
            Resonance=resonance,
            Offset=offset,
        )

    @mcp.tool()
    async def effect_distortion(
        distortion_type: str = "Hard Clipping",
        threshold_db: float = -6.0,
    ) -> dict:
        """Apply distortion effect to the selected audio.

        Args:
            distortion_type: Type of distortion. Default: "Hard Clipping"
            threshold_db: Distortion threshold in dB (-100 to 0). Default: -6.0
        """
        if not -100 <= threshold_db <= 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "threshold_db must be -100 to 0")
        return await client.execute_long(
            "Distortion",
            Type=distortion_type,
            Threshold=threshold_db,
        )

    @mcp.tool()
    async def effect_paulstretch(stretch_factor: float = 10.0, time_resolution: float = 0.25) -> dict:
        """Extreme time-stretch effect (creates ambient/drone textures). Select audio first.

        Args:
            stretch_factor: How much to stretch (1.0 = no change, 10.0 = 10x longer). Default: 10.0
            time_resolution: Time resolution in seconds (smaller = better quality, slower). Default: 0.25
        """
        if stretch_factor < 1.0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "stretch_factor must be >= 1.0")
        return await client.execute_long(
            "PaulStretch",
            StretchFactor=stretch_factor,
            TimeResolution=time_resolution,
        )

    @mcp.tool()
    async def effect_repeat(count: int = 1) -> dict:
        """Repeat the selected audio a number of times.

        Args:
            count: Number of times to repeat (1-128). Default: 1
        """
        if not 1 <= count <= 128:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "count must be 1-128")
        return await client.execute_long("Repeat", Count=count)

    @mcp.tool()
    async def effect_high_pass_filter(
        frequency: float = 40.0,
        rolloff: str = "dB12",
    ) -> dict:
        """Apply a high-pass filter to remove low frequencies below the cutoff.
        Essential as step 1 in mastering chains to remove sub-rumble.

        Args:
            frequency: Cutoff frequency in Hz. Default: 40 (removes sub-bass rumble)
            rolloff: Rolloff steepness - "dB6" (6 dB/octave) or "dB12" (12 dB/octave). Default: "dB12"
        """
        if frequency <= 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "frequency must be > 0")
        if rolloff not in ("dB6", "dB12"):
            raise AudacityMCPError(ErrorCode.INVALID_PARAMETER, "rolloff must be 'dB6' or 'dB12'")
        return await client.execute_long(
            "High-passFilter",
            frequency=frequency,
            rolloff=rolloff,
        )

    @mcp.tool()
    async def effect_low_pass_filter(
        frequency: float = 20000.0,
        rolloff: str = "dB6",
    ) -> dict:
        """Apply a low-pass filter to remove high frequencies above the cutoff.

        Args:
            frequency: Cutoff frequency in Hz. Default: 20000
            rolloff: Rolloff steepness - "dB6" (6 dB/octave) or "dB12" (12 dB/octave). Default: "dB6"
        """
        if frequency <= 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "frequency must be > 0")
        if rolloff not in ("dB6", "dB12"):
            raise AudacityMCPError(ErrorCode.INVALID_PARAMETER, "rolloff must be 'dB6' or 'dB12'")
        return await client.execute_long(
            "Low-passFilter",
            frequency=frequency,
            rolloff=rolloff,
        )

    @mcp.tool()
    async def effect_bass_and_treble(
        bass: float = 0.0,
        treble: float = 0.0,
        gain: float = 0.0,
    ) -> dict:
        """Adjust bass and treble frequencies with a simple tonal shaping tool.

        Args:
            bass: Bass adjustment in dB (-30 to 30). Default: 0
            treble: Treble adjustment in dB (-30 to 30). Default: 0
            gain: Output gain in dB (-30 to 30). Default: 0
        """
        for name, val in [("bass", bass), ("treble", treble), ("gain", gain)]:
            if not -30 <= val <= 30:
                raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"{name} must be -30 to 30")
        return await client.execute_long(
            "BassAndTreble",
            Bass=bass,
            Treble=treble,
            Gain=gain,
        )

    @mcp.tool()
    async def effect_reverse() -> dict:
        """Reverse the selected audio. Select a region first."""
        return await client.execute_long("Reverse")

    @mcp.tool()
    async def effect_invert() -> dict:
        """Invert (flip phase) the selected audio. Useful for phase cancellation."""
        return await client.execute("Invert")

    @mcp.tool()
    async def effect_repair() -> dict:
        """Repair a very short damaged section of audio (max 128 samples).
        Select the damaged region first — must be extremely short.
        Audacity will show an error popup if the selection is too long."""
        return await client.execute_long("Repair")

    @mcp.tool()
    async def effect_auto_duck(
        duck_amount_db: float = -12.0,
        inner_fade_down_len: float = 0.0,
        inner_fade_up_len: float = 0.0,
        outer_fade_down_len: float = 0.5,
        outer_fade_up_len: float = 0.5,
        threshold_db: float = -30.0,
        maximum_pause: float = 1.0,
    ) -> dict:
        """Auto Duck: automatically reduce volume when audio is detected on another track.
        Place the control track (e.g. narration) above the track to duck (e.g. music).
        Select the track to duck before running.

        Args:
            duck_amount_db: How much to reduce volume in dB (-24 to 0). Default: -12
            inner_fade_down_len: Inner fade down length in seconds (>= 0). Default: 0
            inner_fade_up_len: Inner fade up length in seconds (>= 0). Default: 0
            outer_fade_down_len: Outer fade down length in seconds (>= 0). Default: 0.5
            outer_fade_up_len: Outer fade up length in seconds (>= 0). Default: 0.5
            threshold_db: Threshold for duck trigger in dB (-100 to 0). Default: -30
            maximum_pause: Maximum pause between ducking regions in seconds (>= 0). Default: 1.0
        """
        if not -24 <= duck_amount_db <= 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "duck_amount_db must be -24 to 0")
        for name, val in [
            ("inner_fade_down_len", inner_fade_down_len),
            ("inner_fade_up_len", inner_fade_up_len),
            ("outer_fade_down_len", outer_fade_down_len),
            ("outer_fade_up_len", outer_fade_up_len),
            ("maximum_pause", maximum_pause),
        ]:
            if val < 0:
                raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"{name} must be >= 0")
        if not -100 <= threshold_db <= 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "threshold_db must be -100 to 0")
        return await client.execute_long(
            "AutoDuck",
            DuckAmountDb=duck_amount_db,
            InnerFadeDownLen=inner_fade_down_len,
            InnerFadeUpLen=inner_fade_up_len,
            OuterFadeDownLen=outer_fade_down_len,
            OuterFadeUpLen=outer_fade_up_len,
            ThresholdDb=threshold_db,
            MaximumPause=maximum_pause,
        )

    @mcp.tool()
    async def effect_notch_filter(
        frequency: float = 60.0,
        q: float = 1.0,
    ) -> dict:
        """Remove a specific frequency (e.g. 50/60Hz hum) with a notch filter.

        Args:
            frequency: Center frequency to remove in Hz. Default: 60 (US mains hum)
            q: Q factor / sharpness of the notch (0.1-20). Higher = narrower notch. Default: 1.0
        """
        if frequency <= 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "frequency must be > 0")
        if not 0.1 <= q <= 20:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "q must be 0.1-20")
        return await client.execute_long(
            "NotchFilter",
            Frequency=frequency,
            Q=q,
        )

    @mcp.tool()
    async def effect_vocal_reduction(
        action: int = 0,
        low_cutoff: float = 120.0,
        high_cutoff: float = 9000.0,
        strength: float = 1.0,
    ) -> dict:
        """Vocal Reduction and Isolation: remove or isolate vocals from a stereo track.

        Args:
            action: 0=Remove Vocals, 1=Isolate Vocals, 2=Remove Vocals (Mono),
                    3=Isolate Vocals (Mono), 4=Remove Center, 5=Isolate Center. Default: 0
            low_cutoff: Low frequency cutoff in Hz. Default: 120
            high_cutoff: High frequency cutoff in Hz. Default: 9000
            strength: Effect strength (0-50). Default: 1.0
        """
        if not 0 <= action <= 5:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "action must be 0-5")
        if low_cutoff <= 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "low_cutoff must be > 0")
        if high_cutoff <= low_cutoff:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "high_cutoff must be > low_cutoff")
        if not 0 <= strength <= 50:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "strength must be 0-50")
        return await client.execute_long(
            "VocalReductionAndIsolation",
            Action=action,
            LowCutoff=low_cutoff,
            HighCutoff=high_cutoff,
            Strength=strength,
        )

    @mcp.tool()
    async def effect_adjustable_fade(
        fade_type: int = 0,
        curve: float = 0.0,
    ) -> dict:
        """Apply an adjustable fade with curve control.

        Args:
            fade_type: 0=fade up (in), 1=fade down (out). Default: 0
            curve: Curve shape (0=linear, positive=exponential, negative=logarithmic). Default: 0
        """
        if fade_type not in (0, 1):
            raise AudacityMCPError(ErrorCode.INVALID_PARAMETER, "fade_type must be 0 (up) or 1 (down)")
        return await client.execute_long(
            "AdjustableFade",
            type=fade_type,
            curve=curve,
        )

    @mcp.tool()
    async def effect_studio_fade_out() -> dict:
        """Apply a professional studio-quality fade out to the selected audio.
        Uses a specially shaped curve that sounds more natural than a linear fade."""
        return await client.execute_long("StudioFadeOut")

    @mcp.tool()
    async def effect_crossfade_clips() -> dict:
        """Crossfade between two adjacent clips on the same track.
        Select the junction point between two clips first."""
        return await client.execute("CrossfadeClips")

    @mcp.tool()
    async def effect_crossfade_tracks() -> dict:
        """Crossfade between two overlapping tracks.
        Align the tracks so they overlap, select both, then run this effect."""
        return await client.execute_long("CrossfadeTracks")

    @mcp.tool()
    async def effect_clip_fix(
        threshold: float = 95.0,
    ) -> dict:
        """Attempt to repair clipped (distorted) audio by reconstructing peaks.

        Args:
            threshold: Clipping threshold as percentage of max amplitude (0-100). Default: 95
        """
        if not 0 <= threshold <= 100:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "threshold must be 0-100")
        return await client.execute_long("ClipFix", threshold=threshold)

    @mcp.tool()
    async def effect_sliding_stretch(
        rate_change_start: float = 0.0,
        rate_change_end: float = 0.0,
        pitch_change_start: float = 0.0,
        pitch_change_end: float = 0.0,
    ) -> dict:
        """Change tempo and/or pitch gradually across the selection (sliding time stretch).

        Args:
            rate_change_start: Tempo change at start in % (-99 to 3000). Default: 0
            rate_change_end: Tempo change at end in % (-99 to 3000). Default: 0
            pitch_change_start: Pitch change at start in semitones (-12 to 12). Default: 0
            pitch_change_end: Pitch change at end in semitones (-12 to 12). Default: 0
        """
        for name, val in [("rate_change_start", rate_change_start), ("rate_change_end", rate_change_end)]:
            if not -99 <= val <= 3000:
                raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"{name} must be -99 to 3000")
        for name, val in [("pitch_change_start", pitch_change_start), ("pitch_change_end", pitch_change_end)]:
            if not -12 <= val <= 12:
                raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"{name} must be -12 to 12")
        return await client.execute_long(
            "SlidingStretch",
            RatePercentChangeStart=rate_change_start,
            RatePercentChangeEnd=rate_change_end,
            PitchHalfStepsStart=pitch_change_start,
            PitchHalfStepsEnd=pitch_change_end,
        )

    @mcp.tool()
    async def effect_tremolo(
        frequency: float = 5.0,
        depth: float = 40.0,
        waveform: int = 0,
    ) -> dict:
        """Apply tremolo (volume oscillation) effect to the selected audio.

        Args:
            frequency: Tremolo speed in Hz (1-1000). Default: 5
            depth: Tremolo depth as percentage (0-100). Default: 40
            waveform: 0=Sine, 1=Triangle, 2=Sawtooth, 3=InverseSawtooth, 4=Square. Default: 0
        """
        if not 1 <= frequency <= 1000:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "frequency must be 1-1000")
        if not 0 <= depth <= 100:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "depth must be 0-100")
        if not 0 <= waveform <= 4:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "waveform must be 0-4")
        return await client.execute_long(
            "Tremolo",
            Frequency=frequency,
            Depth=depth,
            Waveform=waveform,
        )
