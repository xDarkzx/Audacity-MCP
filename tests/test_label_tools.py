import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from audacity_mcp.tools.label_tools import count_existing_labels


def _mock_client(get_info_message: str = ""):
    c = MagicMock()

    async def _execute(command, *args, **kwargs):
        if command == "GetInfo":
            return {"success": True, "raw": "", "message": get_info_message, "data": {}}
        return {"success": True, "raw": "", "message": "", "data": {}}

    c.execute = AsyncMock(side_effect=_execute)
    return c


class TestCountExistingLabels:
    @pytest.mark.asyncio
    async def test_empty_message_returns_zero(self):
        client = _mock_client(get_info_message="")
        assert await count_existing_labels(client) == 0

    @pytest.mark.asyncio
    async def test_counts_labels_nested_per_track(self):
        # [track_name, [[start, end, text], ...]] per label track
        message = '[["Label Track", [[1.5, 1.5, "a"], [3.0, 3.0, "b"]]]]'
        client = _mock_client(get_info_message=message)
        assert await count_existing_labels(client) == 2

    @pytest.mark.asyncio
    async def test_counts_labels_across_multiple_tracks(self):
        message = (
            '[["Label Track", [[1.5, 1.5, "a"]]], '
            '["Label Track 2", [[2.0, 2.5, "b"], [4.0, 4.5, "c"]]]]'
        )
        client = _mock_client(get_info_message=message)
        assert await count_existing_labels(client) == 3

    @pytest.mark.asyncio
    async def test_no_existing_labels(self):
        message = '[["Label Track", []]]'
        client = _mock_client(get_info_message=message)
        assert await count_existing_labels(client) == 0

    @pytest.mark.asyncio
    async def test_malformed_json_returns_zero(self):
        client = _mock_client(get_info_message="not json{{{")
        assert await count_existing_labels(client) == 0


@pytest.fixture
def mock_client():
    return _mock_client()


@pytest.fixture
def registered_tools(mock_client):
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("TestLabels")
    with patch("audacity_mcp.main.client", mock_client):
        from audacity_mcp.tools.label_tools import register
        register(mcp)
    return mcp._tool_manager._tools


class TestLabelAddTargetsCorrectIndex:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_label_add_uses_existing_count_as_index_not_zero(self, registered_tools, mock_client):
        # Regression: SetLabel(Label=0, ...) always retargeted the FIRST
        # label ever created, not the one just added. With 2 labels already
        # present, the new one must be targeted at index 2, not 0.
        mock_client.execute = AsyncMock(side_effect=lambda command, *a, **kw: (
            {"success": True, "raw": "", "message": '[["Label Track", [[1.0, 1.0, "x"], [2.0, 2.0, "y"]]]]', "data": {}}
            if command == "GetInfo" else {"success": True, "raw": "", "message": "", "data": {}}
        ))
        tool = registered_tools["label_add"]
        await tool.fn(text="new label")

        set_label_calls = [c for c in mock_client.execute.call_args_list if c.args[0] == "SetLabel"]
        assert len(set_label_calls) == 1
        assert set_label_calls[0].kwargs["Label"] == 2
        assert set_label_calls[0].kwargs["Text"] == "new label"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_label_add_no_text_skips_setlabel(self, registered_tools, mock_client):
        tool = registered_tools["label_add"]
        await tool.fn(text="")
        set_label_calls = [c for c in mock_client.execute.call_args_list if c.args[0] == "SetLabel"]
        assert set_label_calls == []

    @pytest.mark.asyncio(loop_scope="function")
    async def test_label_add_at_uses_existing_count_as_index(self, registered_tools, mock_client):
        mock_client.execute = AsyncMock(side_effect=lambda command, *a, **kw: (
            {"success": True, "raw": "", "message": '[["Label Track", [[1.0, 1.0, "x"]]]]', "data": {}}
            if command == "GetInfo" else {"success": True, "raw": "", "message": "", "data": {}}
        ))
        tool = registered_tools["label_add_at"]
        await tool.fn(start=5.0, end=6.0, text="segment")

        set_label_calls = [c for c in mock_client.execute.call_args_list if c.args[0] == "SetLabel"]
        assert len(set_label_calls) == 1
        assert set_label_calls[0].kwargs["Label"] == 1
