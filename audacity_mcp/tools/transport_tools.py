from mcp.server.fastmcp import FastMCP
from audacity_mcp_shared.error_codes import AudacityMCPError, ErrorCode


def register(mcp: FastMCP):
    from audacity_mcp.main import client

    @mcp.tool()
    async def transport_play() -> dict:
        """Start playback from the current cursor position."""
        return await client.execute("Play")

    @mcp.tool()
    async def transport_stop() -> dict:
        """Stop playback or recording."""
        return await client.execute("Stop")

    @mcp.tool()
    async def transport_pause() -> dict:
        """Toggle pause during playback or recording."""
        return await client.execute("Pause")

    @mcp.tool()
    async def transport_record() -> dict:
        """Start recording on a new track."""
        return await client.execute("Record1stChoice")

    @mcp.tool()
    async def transport_set_cursor(time: float) -> dict:
        """Set the playback cursor position.

        Args:
            time: Position in seconds
        """
        if time < 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Time must be >= 0")
        return await client.execute("SelectTime", Start=time, End=time)

    @mcp.tool()
    async def transport_get_play_position() -> dict:
        """Get the current playback position in seconds."""
        return await client.execute("GetInfo", Type="Boxes")

    @mcp.tool()
    async def transport_play_region(start: float, end: float) -> dict:
        """Play a specific time region.

        Args:
            start: Start time in seconds
            end: End time in seconds
        """
        if start < 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Start must be >= 0")
        if end <= start:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "End must be > start")
        await client.execute("SelectTime", Start=start, End=end)
        return await client.execute("Play")
