from mcp.server.fastmcp import FastMCP
from shared.error_codes import AudacityMCPError, ErrorCode


def register(mcp: FastMCP):
    from server.main import client

    @mcp.tool()
    async def select_all() -> dict:
        """Select all audio in all tracks. Selects both tracks and time range."""
        await client.execute("SelAllTracks")
        return await client.execute("SelectAll")

    @mcp.tool()
    async def select_none() -> dict:
        """Deselect all audio."""
        return await client.execute("SelectNone")

    @mcp.tool()
    async def select_region(start: float, end: float) -> dict:
        """Select a time region in the current track(s). Many effects operate on the selection.

        Args:
            start: Start time in seconds
            end: End time in seconds
        """
        if start < 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Start must be >= 0")
        if end <= start:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "End must be > start")
        return await client.execute("SelectTime", Start=start, End=end)

    @mcp.tool()
    async def select_tracks(track: int, count: int = 1) -> dict:
        """Select one or more tracks by index.

        Args:
            track: Starting track index (0-based)
            count: Number of tracks to select
        """
        if track < 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Track index must be >= 0")
        if count < 1:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Count must be >= 1")
        return await client.execute("SelectTracks", Track=track, TrackCount=count)

    @mcp.tool()
    async def select_zero_crossing() -> dict:
        """Adjust the current selection boundaries to the nearest zero crossings.
        Useful before cuts to avoid audible clicks at edit points."""
        return await client.execute("ZeroCross")

    @mcp.tool()
    async def select_clip() -> dict:
        """Select the clip under the cursor."""
        return await client.execute("SelCursorToNextClipBoundary")

    @mcp.tool()
    async def cursor_set_position(time: float) -> dict:
        """Move the cursor to a specific time position.

        Args:
            time: Position in seconds
        """
        if time < 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Time must be >= 0")
        return await client.execute("SelectTime", Start=time, End=time)
