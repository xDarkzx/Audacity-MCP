from mcp.server.fastmcp import FastMCP
from shared.error_codes import AudacityMCPError, ErrorCode


def register(mcp: FastMCP):
    from server.main import client

    @mcp.tool()
    async def generate_tone(
        waveform: str = "Sine",
        frequency: float = 440.0,
        amplitude: float = 0.8,
        duration: float = 1.0,
    ) -> dict:
        """Generate a tone signal.

        Args:
            waveform: Wave type - "Sine", "Square", "Sawtooth", or "Square (no alias)". Default: "Sine"
            frequency: Frequency in Hz (1-20000). Default: 440
            amplitude: Amplitude (0-1). Default: 0.8
            duration: Duration in seconds. Default: 1.0
        """
        allowed_waves = {"Sine", "Square", "Sawtooth", "Square (no alias)"}
        if waveform not in allowed_waves:
            raise AudacityMCPError(
                ErrorCode.INVALID_PARAMETER,
                f"waveform must be one of: {', '.join(sorted(allowed_waves))}",
            )
        if not 1 <= frequency <= 20000:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "frequency must be 1-20000")
        if not 0 <= amplitude <= 1:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "amplitude must be 0-1")
        if not 0 < duration <= 3600:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "duration must be > 0 and <= 3600 (1 hour)")
        return await client.execute(
            "Tone",
            Waveform=waveform,
            Frequency=frequency,
            Amplitude=amplitude,
            Duration=duration,
        )

    @mcp.tool()
    async def generate_noise(
        noise_type: str = "White",
        amplitude: float = 0.8,
        duration: float = 1.0,
    ) -> dict:
        """Generate noise.

        Args:
            noise_type: "White", "Pink", or "Brownian". Default: "White"
            amplitude: Amplitude (0-1). Default: 0.8
            duration: Duration in seconds. Default: 1.0
        """
        allowed = {"White", "Pink", "Brownian"}
        if noise_type not in allowed:
            raise AudacityMCPError(ErrorCode.INVALID_PARAMETER, f"noise_type must be one of: {', '.join(sorted(allowed))}")
        if not 0 <= amplitude <= 1:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "amplitude must be 0-1")
        if not 0 < duration <= 3600:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "duration must be > 0 and <= 3600 (1 hour)")
        return await client.execute(
            "Noise",
            Type=noise_type,
            Amplitude=amplitude,
            Duration=duration,
        )

    @mcp.tool()
    async def generate_chirp(
        waveform: str = "Sine",
        start_freq: float = 440.0,
        end_freq: float = 1320.0,
        start_amp: float = 0.8,
        end_amp: float = 0.1,
        duration: float = 1.0,
    ) -> dict:
        """Generate a chirp (frequency sweep).

        Args:
            waveform: "Sine", "Square", "Sawtooth", or "Square (no alias)". Default: "Sine"
            start_freq: Starting frequency in Hz. Default: 440
            end_freq: Ending frequency in Hz. Default: 1320
            start_amp: Starting amplitude (0-1). Default: 0.8
            end_amp: Ending amplitude (0-1). Default: 0.1
            duration: Duration in seconds. Default: 1.0
        """
        if not 0 < duration <= 3600:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "duration must be > 0 and <= 3600 (1 hour)")
        return await client.execute(
            "Chirp",
            Waveform=waveform,
            StartFreq=start_freq,
            EndFreq=end_freq,
            StartAmp=start_amp,
            EndAmp=end_amp,
            Duration=duration,
        )

    @mcp.tool()
    async def generate_dtmf(
        sequence: str = "0123456789",
        duty_cycle: float = 55.0,
        amplitude: float = 0.8,
        duration: float = 1.0,
    ) -> dict:
        """Generate DTMF (telephone) tones.

        Args:
            sequence: DTMF characters (0-9, A-D, *, #). Default: "0123456789"
            duty_cycle: Tone vs silence ratio percentage (0-100). Default: 55
            amplitude: Amplitude (0-1). Default: 0.8
            duration: Total duration in seconds. Default: 1.0
        """
        import re
        if not re.match(r"^[0-9A-Da-d*#]+$", sequence):
            raise AudacityMCPError(ErrorCode.INVALID_PARAMETER, "sequence must contain only 0-9, A-D, *, #")
        return await client.execute(
            "DtmfTones",
            Sequence=sequence,
            DutyCycle=duty_cycle,
            Amplitude=amplitude,
            Duration=duration,
        )

    @mcp.tool()
    async def generate_rhythm_track(
        tempo: float = 120.0,
        beats_per_bar: int = 4,
        number_of_bars: int = 4,
        rhythm_pattern: str = "Uniform",
    ) -> dict:
        """Generate a click/rhythm track.

        Args:
            tempo: Tempo in BPM (30-300). Default: 120
            beats_per_bar: Beats per bar (1-32). Default: 4
            number_of_bars: Number of bars to generate (1-1000). Default: 4
            rhythm_pattern: "Uniform" or "Swing". Default: "Uniform"
        """
        if not 30 <= tempo <= 300:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "tempo must be 30-300")
        if not 1 <= beats_per_bar <= 32:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "beats_per_bar must be 1-32")
        if not 1 <= number_of_bars <= 1000:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "number_of_bars must be 1-1000")
        if rhythm_pattern not in ("Uniform", "Swing"):
            raise AudacityMCPError(ErrorCode.INVALID_PARAMETER, "rhythm_pattern must be 'Uniform' or 'Swing'")
        return await client.execute(
            "RhythmTrack",
            Tempo=tempo,
            BeatsPerBar=beats_per_bar,
            NumberOfBars=number_of_bars,
            RhythmPattern=rhythm_pattern,
        )
