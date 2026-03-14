from mcp.server.fastmcp import FastMCP


def register(mcp: FastMCP):
    from server.main import client

    @mcp.tool()
    async def edit_cut() -> dict:
        """Cut the selected audio to clipboard. Select a region first."""
        return await client.execute("Cut")

    @mcp.tool()
    async def edit_copy() -> dict:
        """Copy the selected audio to clipboard. Select a region first."""
        return await client.execute("Copy")

    @mcp.tool()
    async def edit_paste() -> dict:
        """Paste audio from clipboard at the cursor position."""
        return await client.execute("Paste")

    @mcp.tool()
    async def edit_delete() -> dict:
        """Delete the selected audio (does not copy to clipboard). Select a region first."""
        return await client.execute("Delete")

    @mcp.tool()
    async def edit_split() -> dict:
        """Split the selected audio into a new clip at the selection boundaries."""
        return await client.execute("SplitNew")

    @mcp.tool()
    async def edit_join() -> dict:
        """Join selected clips into one clip."""
        return await client.execute("Join")

    @mcp.tool()
    async def edit_trim() -> dict:
        """Trim audio outside the selection (delete everything except selected region)."""
        return await client.execute("Trim")

    @mcp.tool()
    async def edit_silence() -> dict:
        """Replace the selected audio with silence."""
        return await client.execute("Silence")

    @mcp.tool()
    async def edit_duplicate() -> dict:
        """Duplicate the selected audio into a new track."""
        return await client.execute("Duplicate")

    # Undo/Redo intentionally NOT exposed as tools.
    # These are destructive operations that can delete imported audio
    # and project data. Users should use Ctrl+Z/Ctrl+Y in Audacity directly.
