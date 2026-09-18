import json

from mcp.server.fastmcp import FastMCP
from audacity_mcp_shared.error_codes import AudacityMCPError, ErrorCode
from audacity_mcp_shared.constants import MAX_TRACKS


async def get_selected_track_indices(client) -> tuple[int, list[int]]:
    """(track count, indices of the currently selected tracks), from GetInfo Tracks."""
    result = await client.execute("GetInfo", Type="Tracks")
    raw = result.get("message", "")
    try:
        parsed = json.loads(raw) if raw else []
    except (ValueError, TypeError):
        parsed = []
    if not isinstance(parsed, list):
        parsed = []
    selected = [i for i, track in enumerate(parsed)
                if isinstance(track, dict) and track.get("selected")]
    return len(parsed), selected


async def apply_to_track(client, track: int, command: str, **params) -> dict:
    """Run a SetTrack-family command against exactly one track.

    Audacity's SetTrack / SetTrackStatus / SetTrackAudio / SetTrackVisuals act on
    the SELECTED tracks and ignore their Track= parameter (verified on 3.7.9:
    with only track 0 selected, `SetTrack Track=1 Name=x` renamed track 0; with
    both selected it renamed both; with none selected it did nothing). So the
    target is selected alone for the call, and the previous track selection is
    put back afterwards — SelectTracks touches only the track selection, never
    the time range, so an in-progress region selection survives.
    """
    count, previous = await get_selected_track_indices(client)
    if track >= count:
        raise AudacityMCPError(
            ErrorCode.VALUE_OUT_OF_RANGE,
            f"No track at index {track}: the project has {count} track(s)",
        )
    await client.execute("SelectTracks", Track=track, TrackCount=1, Mode="Set")
    try:
        return await client.execute(command, **params)
    finally:
        if previous == [track]:
            pass  # already what it was
        elif previous:
            await client.execute("SelectTracks", Track=previous[0], TrackCount=1, Mode="Set")
            for index in previous[1:]:
                await client.execute("SelectTracks", Track=index, TrackCount=1, Mode="Add")
        else:
            await client.execute("SelectTracks", Track=0, TrackCount=count, Mode="Remove")


def register(mcp: FastMCP):
    from audacity_mcp.main import client

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
        """Set properties of a track by index. Only the given track is changed;
        the current track selection is preserved.

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
        # SetTrack is the one command that carries all of these. SetTrackStatus
        # (used before) only knows Name/Selected/Focused and silently dropped
        # Gain, Pan, Mute and Solo.
        params: dict = {}
        if name is not None:
            params["Name"] = name
        if gain is not None:
            if not -36 <= gain <= 36:
                raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Gain must be -36 to 36 dB")
            # Audacity 3.7 renamed the parameter to Volume (dB); older versions
            # read Gain. Each version ignores the name it doesn't know.
            params["Volume"] = gain
            params["Gain"] = gain
        if pan is not None:
            if not -1.0 <= pan <= 1.0:
                raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Pan must be -1.0 to 1.0")
            params["Pan"] = pan * 100  # Audacity takes percent: -100 (left) to 100 (right)
        if mute is not None:
            params["Mute"] = mute
        if solo is not None:
            params["Solo"] = solo
        if not params:
            raise AudacityMCPError(ErrorCode.MISSING_PARAMETER, "Nothing to set: give at least one property")
        return await apply_to_track(client, track, "SetTrack", **params)

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
        """Mute or unmute a track. Only the given track is changed; the current
        track selection is preserved.

        Args:
            track: Track index (0-based)
            mute: True to mute, False to unmute
        """
        if track < 0 or track >= MAX_TRACKS:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"Track index must be 0-{MAX_TRACKS - 1}")
        # SetTrackStatus has no Mute parameter (it was silently ignored, so this
        # tool never muted anything); SetTrack does.
        return await apply_to_track(client, track, "SetTrack", Mute=mute)

    @mcp.tool()
    async def track_select(track: int) -> dict:
        """Select a track by index, including its full time range, so it's immediately
        ready for effects (e.g. compressor, normalize). To work on a sub-region instead,
        call select_region() afterward to narrow the time range.

        Args:
            track: Track index (0-based)
        """
        if track < 0 or track >= MAX_TRACKS:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"Track index must be 0-{MAX_TRACKS - 1}")
        result = await client.execute("SelectTracks", Track=track, TrackCount=1)
        await client.execute("CursTrackStart")
        await client.execute("SelCursorToTrackEnd")
        return result

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
