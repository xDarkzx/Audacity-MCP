import os
from mcp.server.fastmcp import FastMCP
from audacity_mcp_shared.error_codes import AudacityMCPError, ErrorCode
from audacity_mcp_shared.constants import MAX_LABEL_LENGTH


async def count_existing_labels(client) -> int:
    """Total label count across all label tracks in the project.

    SetLabel's Label= parameter is a flat index of the label to edit - it is
    NOT "whichever label was just added". AddLabel doesn't report the new
    label's index back, so the only way to target it correctly is to know
    how many labels existed right before adding it (the new one lands at
    that index, since AddLabel appends). Getting this wrong was a real bug:
    every SetLabel(Label=0, ...) call retargeted the very first label ever
    created instead of the one just added, leaving every other label blank.

    GetInfo Type=Labels returns JSON, structure varies by Audacity version
    (nested per label-track vs. flattened), so this walks the parsed JSON
    looking for [start, end, text]-shaped leaves rather than assuming one
    fixed schema.
    """
    import json as _json
    result = await client.execute("GetInfo", Type="Labels")
    raw = result.get("message", "")
    if not raw:
        return 0
    try:
        parsed = _json.loads(raw)
    except (ValueError, TypeError):
        return 0

    count = 0

    def _walk(node):
        nonlocal count
        if not isinstance(node, list):
            return
        if (len(node) == 3 and isinstance(node[0], (int, float))
                and isinstance(node[1], (int, float)) and isinstance(node[2], str)):
            count += 1
            return
        for item in node:
            _walk(item)

    _walk(parsed)
    return count


def register(mcp: FastMCP):
    from audacity_mcp.main import client

    @mcp.tool()
    async def label_add(text: str = "") -> dict:
        """Add a label at the current cursor position or selection.

        Args:
            text: Label text. Default: empty
        """
        if len(text) > MAX_LABEL_LENGTH:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"Label text too long (max {MAX_LABEL_LENGTH})")
        index = await count_existing_labels(client) if text else 0
        result = await client.execute("AddLabel")
        if text:
            await client.execute("SetLabel", Label=index, Text=text)
        return result

    @mcp.tool()
    async def label_add_at(start: float, end: float, text: str = "") -> dict:
        """Add a label at a specific time range.

        Args:
            start: Start time in seconds
            end: End time in seconds
            text: Label text. Default: empty
        """
        if start < 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "Start must be >= 0")
        if end < start:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "End must be >= start")
        if len(text) > MAX_LABEL_LENGTH:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"Label text too long (max {MAX_LABEL_LENGTH})")
        index = await count_existing_labels(client) if text else 0
        await client.execute("SelectTime", Start=start, End=end)
        result = await client.execute("AddLabel")
        if text:
            await client.execute("SetLabel", Label=index, Text=text)
        return result

    @mcp.tool()
    async def label_get_all() -> dict:
        """Get all labels in the project."""
        return await client.execute("GetInfo", Type="Labels")

    @mcp.tool()
    async def label_import(path: str) -> dict:
        """Import labels from a text file.

        Args:
            path: Absolute path to the labels text file
        """
        if not os.path.isabs(path):
            raise AudacityMCPError(ErrorCode.INVALID_PATH, "Path must be absolute")
        return await client.execute("ImportLabels", Filename=path)

    @mcp.tool()
    async def label_export(path: str) -> dict:
        """Export all labels to a text file.

        Args:
            path: Absolute path for the output labels file
        """
        if not os.path.isabs(path):
            raise AudacityMCPError(ErrorCode.INVALID_PATH, "Path must be absolute")
        return await client.execute("ExportLabels", Filename=path)

    @mcp.tool()
    async def label_regular_intervals(
        interval: float = 30.0,
        adjust: bool = False,
        label_text: str = "",
    ) -> dict:
        """Create labels at regular time intervals across the selection or project.

        Args:
            interval: Time between labels in seconds. Default: 30
            adjust: Adjust interval to fit selection evenly. Default: False
            label_text: Text for each label (labels will be numbered). Default: empty
        """
        if interval <= 0:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "interval must be > 0")
        if len(label_text) > MAX_LABEL_LENGTH:
            raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, f"Label text too long (max {MAX_LABEL_LENGTH})")
        params = {"Interval": interval, "Adjust": adjust}
        if label_text:
            params["Label"] = label_text
        return await client.execute("RegularIntervalLabels", **params)
