from mcp.server.fastmcp import FastMCP
from shared.error_codes import AudacityMCPError, ErrorCode
from shared.constants import MAX_TRACKS


def register(mcp: FastMCP):
    from server.main import client

    @mcp.tool()
    async def track_add_mono() -> dict:
        """Add a new mono audio track to the project."""
        return await client.execute("NewMonoTrack")

    @mcp.tool()
    async def track_add_stereo() -> dict:
        """Add a new stereo audio track to the project."""
        return await client.execute("NewStereoTrack")

    @mcp.tool()
    async def track_remove() -> dict:
        """Remove the currently selected track(s). Select tracks first with track_select."""
        return await client.execute("RemoveTracks")

    @mcp.tool()
    async def track_set_properties(
        track: int,
        name: str | None = None,
        gain: float | None = None,
        pan: float | None = None,
        mute: bool | None = None,
        solo: bool | None = None,
    ) -> dict:
        """Set properties of a track by index.

        Args:
            track: Track index (0-based)
            name: New track name
            gain: Track gain in dB (-36 to 36)
            pan: Track pan (-1.0=left to 1.0=right)
            mute: Mute the track
            solo: Solo the track
        """
        if track < 0 or track >= MAX_TRACKS:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"Track index must be 0-{MAX_TRACKS - 1}")
        params: dict = {"Track": track}
        if name is not None:
            params["Name"] = name
        if gain is not None:
            if not -36 <= gain <= 36:
                raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Gain must be -36 to 36 dB")
            params["Gain"] = gain
        if pan is not None:
            if not -1.0 <= pan <= 1.0:
                raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Pan must be -1.0 to 1.0")
            params["Pan"] = pan
        if mute is not None:
            params["Mute"] = mute
        if solo is not None:
            params["Solo"] = solo
        return await client.execute("SetTrackStatus", **params)

    @mcp.tool()
    async def track_get_info() -> dict:
        """Get information about all tracks in the project (names, types, rates, etc.)."""
        return await client.execute("GetInfo", Type="Tracks")

    @mcp.tool()
    async def track_mix_and_render() -> dict:
        """Mix and render selected tracks into a single track. Select tracks first."""
        return await client.execute("MixAndRender")

    @mcp.tool()
    async def track_mute(track: int, mute: bool = True) -> dict:
        """Mute or unmute a track.

        Args:
            track: Track index (0-based)
            mute: True to mute, False to unmute
        """
        if track < 0 or track >= MAX_TRACKS:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"Track index must be 0-{MAX_TRACKS - 1}")
        return await client.execute("SetTrackStatus", Track=track, Mute=mute)

    @mcp.tool()
    async def track_select(track: int) -> dict:
        """Select a track by index. Many operations require selecting a track first.

        Args:
            track: Track index (0-based)
        """
        if track < 0 or track >= MAX_TRACKS:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"Track index must be 0-{MAX_TRACKS - 1}")
        return await client.execute("SelectTracks", Track=track, TrackCount=1)

    @mcp.tool()
    async def track_add_label() -> dict:
        """Add a new empty label track to the project."""
        return await client.execute("NewLabelTrack")

    @mcp.tool()
    async def track_stereo_to_mono() -> dict:
        """Convert the selected stereo track to mono. Select the track first."""
        return await client.execute_long("StereoToMono")

    @mcp.tool()
    async def track_mix_and_render_to_new() -> dict:
        """Mix and render selected tracks into a new track, keeping the originals. Select tracks first."""
        return await client.execute_long("MixAndRenderToNewTrack")

    @mcp.tool()
    async def track_mute_all() -> dict:
        """Mute all tracks in the project."""
        return await client.execute("MuteAllTracks")

    @mcp.tool()
    async def track_unmute_all() -> dict:
        """Unmute all tracks in the project."""
        return await client.execute("UnmuteAllTracks")

    @mcp.tool()
    async def track_resample(rate: int = 44100) -> dict:
        """Resample the selected track to a new sample rate.

        Args:
            rate: Target sample rate in Hz (e.g. 44100, 48000, 96000). Must be > 0.
        """
        if not 1 <= rate <= 384000:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "rate must be 1-384000 Hz")
        return await client.execute("Resample", Rate=rate)

    @mcp.tool()
    async def track_align_end_to_end() -> dict:
        """Align selected tracks end-to-end (sequentially). Select the tracks first."""
        return await client.execute("Align_EndToEnd")
