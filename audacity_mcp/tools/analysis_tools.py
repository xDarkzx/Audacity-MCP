import os
from mcp.server.fastmcp import FastMCP
from audacity_mcp_shared.constants import (
    LABEL_SOUNDS_MEASUREMENTS,
    LABEL_SOUNDS_TYPES,
    MAX_LABEL_LENGTH,
)
from audacity_mcp_shared.error_codes import AudacityMCPError, ErrorCode


def register(mcp: FastMCP):
    from audacity_mcp.main import client

    @mcp.tool()
    async def analyze_contrast() -> dict:
        """Analyze the contrast between foreground and background audio. Select a region first.
        Useful for checking accessibility compliance (WCAG)."""
        return await client.execute_long("ContrastAnalyser")

    @mcp.tool()
    async def analyze_find_clipping(duty_cycle_start: int = 3, duty_cycle_end: int = 3) -> dict:
        """Find clipping in the selected audio and create labels at clipped regions.

        Args:
            duty_cycle_start: Min number of consecutive clipped samples to detect (1-1000, default 3)
            duty_cycle_end: Min number of consecutive non-clipped samples to end a region (1-1000, default 3)
        """
        if not 1 <= duty_cycle_start <= 1000:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "duty_cycle_start must be 1-1000")
        if not 1 <= duty_cycle_end <= 1000:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "duty_cycle_end must be 1-1000")
        return await client.execute_long(
            "FindClipping",
            DutyCycleStart=duty_cycle_start,
            DutyCycleEnd=duty_cycle_end,
        )

    @mcp.tool()
    async def analyze_plot_spectrum() -> dict:
        """Open the Plot Spectrum window for the selected audio. Select a region first."""
        return await client.execute("PlotSpectrum")

    @mcp.tool()
    async def analyze_beat_finder(thres_val: int = 65) -> dict:
        """Find beats in the selected audio and add labels at beat positions.

        Args:
            thres_val: Beat detection threshold (0-100, lower = more sensitive). Default: 65
        """
        if not 0 <= thres_val <= 100:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Threshold must be 0-100")
        return await client.execute_long("BeatFinder", thresval=thres_val)

    @mcp.tool()
    async def analyze_label_sounds(
        threshold_db: float = -30.0,
        min_silence_duration: float = 0.5,
        min_sound_duration: float = 0.1,
        measurement: str = "peak",
        label_type: str = "before",
        pre_offset: float = 0.0,
        post_offset: float = 0.0,
        label_text: str = "",
    ) -> dict:
        """Automatically label regions of sound separated by silence.

        A good starting point for segmenting a long recording: label every
        passage of sound, or with label_type="between" label the silences
        instead so they can be trimmed with label_delete_regions.

        Args:
            threshold_db: Volume threshold to distinguish sound from silence (dB). Default: -30
            min_silence_duration: Minimum duration of silence between sounds (seconds). Default: 0.5
            min_sound_duration: Minimum duration of a sound region (seconds). Default: 0.1
            measurement: How level is measured — peak, avg or rms. Default: peak
            label_type: What to label — before, after, around or between the sounds. Default: before
            pre_offset: Seconds to extend each label before the sound starts. Default: 0
            post_offset: Seconds to extend each label after the sound ends. Default: 0
            label_text: Text for each label. Default: Audacity's own default
        """
        if measurement not in LABEL_SOUNDS_MEASUREMENTS:
            raise AudacityMCPError(
                ErrorCode.INVALID_PARAMETER,
                f"measurement must be one of {sorted(LABEL_SOUNDS_MEASUREMENTS)}")
        if label_type not in LABEL_SOUNDS_TYPES:
            raise AudacityMCPError(
                ErrorCode.INVALID_PARAMETER,
                f"label_type must be one of {sorted(LABEL_SOUNDS_TYPES)}")
        if min_silence_duration < 0 or min_sound_duration < 0:
            raise AudacityMCPError(
                ErrorCode.VALUE_OUT_OF_RANGE,
                "min_silence_duration and min_sound_duration must be >= 0")
        if not 0 <= pre_offset <= 3600 or not 0 <= post_offset <= 3600:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE,
                                   "pre_offset and post_offset must be 0-3600 seconds")
        if len(label_text) > MAX_LABEL_LENGTH:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE,
                                   f"Label text too long (max {MAX_LABEL_LENGTH})")

        # Only send a parameter that was actually asked for. Sending all of them
        # unconditionally changed the wire call for every existing caller, and
        # an unrecognised name is enough to make the whole command misbehave -
        # exactly the risk this tool already carries with Threshold/MinSilence/
        # MinSound (see CHANGELOG). Defaults here match Audacity's own, so
        # omitting them leaves the call as it was before these were exposed.
        extra_params = {}
        if measurement != "peak":
            extra_params["measurement"] = measurement
        if label_type != "before":
            extra_params["type"] = label_type
        if pre_offset:
            extra_params["pre-offset"] = pre_offset
        if post_offset:
            extra_params["post-offset"] = post_offset
        if label_text:
            extra_params["text"] = label_text

        return await client.execute_long(
            "LabelSounds",
            extra_params=extra_params or None,
            Threshold=threshold_db,
            MinSilence=min_silence_duration,
            MinSound=min_sound_duration,
        )

    @mcp.tool()
    async def analyze_sample_data_export(path: str, limit: int = 100) -> dict:
        """Export raw sample data from the selected audio to a text file for analysis.

        Args:
            path: Absolute path for the output file
            limit: Maximum number of samples to export. Default: 100
        """
        if not 1 <= limit <= 1000000:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "limit must be 1-1000000")
        from audacity_mcp.tools.project_tools import _safe_path
        path = _safe_path(path)
        if os.path.exists(path):
            raise AudacityMCPError(
                ErrorCode.INVALID_PATH,
                f"File already exists: {path}. Use a different filename to avoid overwriting.",
            )
        return await client.execute("SampleDataExport", Filename=path, Limit=limit)
