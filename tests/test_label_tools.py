import json
import os

import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from audacity_mcp_shared.error_codes import AudacityMCPError, ErrorCode
from audacity_mcp.tools.label_tools import (
    count_existing_labels,
    format_chapter_timestamp,
    format_chapters_cue,
    format_chapters_podlove,
    format_chapters_simple,
    get_parsed_labels,
    sanitize_filename,
)


def _mock_client(get_info_message: str = "", tracks_message: str = ""):
    c = MagicMock()

    async def _execute(command, *args, **kwargs):
        if command == "GetInfo":
            message = tracks_message if kwargs.get("Type") == "Tracks" else get_info_message
            return {"success": True, "raw": "", "message": message, "data": {}}
        return {"success": True, "raw": "", "message": "", "data": {}}

    c.execute = AsyncMock(side_effect=_execute)
    c.execute_long = AsyncMock(side_effect=_execute)
    return c


def _commands(mock_client):
    """Every command name sent via execute/execute_long, for membership checks."""
    calls = list(mock_client.execute.call_args_list) + list(mock_client.execute_long.call_args_list)
    return [c.args[0] for c in calls]


def _calls_for(mock_client, command, long=False):
    source = mock_client.execute_long if long else mock_client.execute
    return [c for c in source.call_args_list if c.args[0] == command]


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


# --- Podcast label tools ---------------------------------------------------

TWO_LABELS = '[["Label Track", [[0.0, 10.0, "Intro"], [10.0, 60.0, "Interview"]]]]'
TWO_TRACKS = '[["Label Track", [[1.0, 2.0, "a"]]], ["Chapters", [[5.0, 6.0, "b"]]]]'
ONE_WAVE_ONE_LABEL_TRACK = '[{"kind": "wave"}, {"kind": "label"}]'


def _register(mock_client):
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("TestLabels")
    with patch("audacity_mcp.main.client", mock_client):
        from audacity_mcp.tools.label_tools import register
        register(mcp)
    return mcp._tool_manager._tools


class TestGetParsedLabels:
    @pytest.mark.asyncio
    async def test_parses_index_timing_text_and_track(self):
        labels = await get_parsed_labels(_mock_client(TWO_LABELS))
        assert labels == [
            {"index": 0, "start": 0.0, "end": 10.0, "text": "Intro", "track": 0},
            {"index": 1, "start": 10.0, "end": 60.0, "text": "Interview", "track": 0},
        ]

    @pytest.mark.asyncio
    async def test_track_ordinal_increments_across_label_tracks(self):
        labels = await get_parsed_labels(_mock_client(TWO_TRACKS))
        assert [(label["index"], label["track"]) for label in labels] == [(0, 0), (1, 1)]

    @pytest.mark.asyncio
    async def test_flat_schema_has_no_track_ordinal(self):
        labels = await get_parsed_labels(_mock_client('[[1.0, 2.0, "a"], [3.0, 4.0, "b"]]'))
        assert [label["track"] for label in labels] == [None, None]
        assert [label["index"] for label in labels] == [0, 1]

    @pytest.mark.asyncio
    async def test_empty_and_malformed_yield_empty_list(self):
        assert await get_parsed_labels(_mock_client("")) == []
        assert await get_parsed_labels(_mock_client("not json{{{")) == []

    @pytest.mark.asyncio
    async def test_count_still_matches_parsed_length(self):
        client = _mock_client(TWO_TRACKS)
        assert await count_existing_labels(client) == len(await get_parsed_labels(client))


class TestLabelList:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_returns_count_and_labels(self):
        tools = _register(_mock_client(TWO_LABELS))
        result = await tools["label_list"].fn()
        assert result["count"] == 2
        assert result["labels"][1]["text"] == "Interview"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_project(self):
        result = await _register(_mock_client(""))["label_list"].fn()
        assert result == {"success": True, "count": 0, "labels": []}


class TestLabelFind:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_match_is_case_insensitive(self):
        result = await _register(_mock_client(TWO_LABELS))["label_find"].fn(query="INTER")
        assert result["count"] == 1
        assert result["matches"][0]["index"] == 1

    @pytest.mark.asyncio(loop_scope="function")
    async def test_no_matches(self):
        result = await _register(_mock_client(TWO_LABELS))["label_find"].fn(query="outro")
        assert result["count"] == 0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_query_rejected(self):
        with pytest.raises(AudacityMCPError) as exc:
            await _register(_mock_client(TWO_LABELS))["label_find"].fn(query="   ")
        assert exc.value.code == ErrorCode.INVALID_PARAMETER


class TestLabelEdit:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_sends_only_the_fields_provided(self):
        client = _mock_client(TWO_LABELS)
        await _register(client)["label_edit"].fn(index=1, text="Main interview")
        call = _calls_for(client, "SetLabel")[0]
        assert call.kwargs == {"Label": 1, "Text": "Main interview"}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_timing_edit_reports_before_and_after(self):
        client = _mock_client(TWO_LABELS)
        result = await _register(client)["label_edit"].fn(index=0, start=2.0)
        assert _calls_for(client, "SetLabel")[0].kwargs == {"Label": 0, "Start": 2.0}
        assert result["before"] == {"start": 0.0, "end": 10.0, "text": "Intro"}
        assert result["after"] == {"start": 2.0, "end": 10.0, "text": "Intro"}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_index_past_end_rejected(self):
        with pytest.raises(AudacityMCPError) as exc:
            await _register(_mock_client(TWO_LABELS))["label_edit"].fn(index=5, text="x")
        assert exc.value.code == ErrorCode.VALUE_OUT_OF_RANGE

    @pytest.mark.asyncio(loop_scope="function")
    async def test_no_fields_rejected(self):
        with pytest.raises(AudacityMCPError) as exc:
            await _register(_mock_client(TWO_LABELS))["label_edit"].fn(index=0)
        assert exc.value.code == ErrorCode.MISSING_PARAMETER

    @pytest.mark.asyncio(loop_scope="function")
    async def test_end_below_existing_start_rejected(self):
        # Only `end` is passed, so it has to be checked against the label's
        # current start rather than against a start in the same call.
        with pytest.raises(AudacityMCPError) as exc:
            await _register(_mock_client(TWO_LABELS))["label_edit"].fn(index=1, end=5.0)
        assert exc.value.code == ErrorCode.VALUE_OUT_OF_RANGE


class TestLabelAddBatch:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_indices_continue_from_existing_labels(self):
        client = _mock_client(TWO_LABELS)
        result = await _register(client)["label_add_batch"].fn(labels=[
            {"start": 100.0, "end": 200.0, "text": "Chapter 3"},
            {"start": 200.0, "end": 300.0, "text": "Chapter 4"},
        ])
        assert [c.kwargs["Label"] for c in _calls_for(client, "SetLabel")] == [2, 3]
        assert result == {"success": True, "added": 2, "base_index": 2}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_end_defaults_to_start_for_point_labels(self):
        client = _mock_client("")
        await _register(client)["label_add_batch"].fn(labels=[{"start": 12.5, "text": "cue"}])
        assert _calls_for(client, "SelectTime")[0].kwargs == {"Start": 12.5, "End": 12.5}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_text_skips_setlabel(self):
        client = _mock_client("")
        await _register(client)["label_add_batch"].fn(labels=[{"start": 1.0, "end": 2.0}])
        assert _calls_for(client, "SetLabel") == []

    @pytest.mark.asyncio(loop_scope="function")
    async def test_bad_item_sends_nothing_at_all(self):
        client = _mock_client("")
        with pytest.raises(AudacityMCPError) as exc:
            await _register(client)["label_add_batch"].fn(labels=[
                {"start": 0.0, "end": 1.0, "text": "fine"},
                {"start": 9.0, "end": 2.0, "text": "backwards"},
            ])
        assert exc.value.code == ErrorCode.VALUE_OUT_OF_RANGE
        assert client.execute.call_count == 0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_missing_start_rejected(self):
        with pytest.raises(AudacityMCPError) as exc:
            await _register(_mock_client(""))["label_add_batch"].fn(labels=[{"text": "no time"}])
        assert exc.value.code == ErrorCode.MISSING_PARAMETER

    @pytest.mark.asyncio(loop_scope="function")
    async def test_empty_list_rejected(self):
        with pytest.raises(AudacityMCPError) as exc:
            await _register(_mock_client(""))["label_add_batch"].fn(labels=[])
        assert exc.value.code == ErrorCode.INVALID_PARAMETER

    @pytest.mark.asyncio(loop_scope="function")
    async def test_over_the_batch_cap_rejected(self):
        from audacity_mcp.tools.label_tools import MAX_BATCH_LABELS
        too_many = [{"start": float(i), "end": float(i) + 1} for i in range(MAX_BATCH_LABELS + 1)]
        with pytest.raises(AudacityMCPError) as exc:
            await _register(_mock_client(""))["label_add_batch"].fn(labels=too_many)
        assert exc.value.code == ErrorCode.VALUE_OUT_OF_RANGE


class TestLabelRegionTools:
    @pytest.mark.parametrize("tool_name,command", [
        ("label_cut_regions", "CutLabels"),
        ("label_delete_regions", "DeleteLabels"),
        ("label_silence_regions", "SilenceLabels"),
        ("label_split_regions", "SplitLabels"),
        ("label_join_regions", "JoinLabels"),
    ])
    @pytest.mark.asyncio(loop_scope="function")
    async def test_issues_its_command_as_a_long_command(self, tool_name, command):
        client = _mock_client("")
        await _register(client)[tool_name].fn()
        assert [c.args[0] for c in client.execute_long.call_args_list] == [command]


class TestLabelDeleteRegion:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_closes_the_gap_by_default(self):
        client = _mock_client(TWO_LABELS)
        result = await _register(client)["label_delete_region"].fn(index=1)

        # All tracks first so label tracks ripple with the audio, then the
        # label's own span, then a gap-closing Delete.
        assert [c.args[0] for c in client.execute.call_args_list][:3] == [
            "GetInfo", "SelAllTracks", "SelectTime"]
        assert _calls_for(client, "SelectTime")[0].kwargs == {"Start": 10.0, "End": 60.0}
        assert [c.args[0] for c in client.execute_long.call_args_list] == ["Delete"]
        assert result["closed_gap"] is True
        assert result["duration_removed"] == 50.0
        assert result["deleted"]["text"] == "Interview"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_close_gap_false_uses_split_delete(self):
        client = _mock_client(TWO_LABELS)
        result = await _register(client)["label_delete_region"].fn(index=0, close_gap=False)
        assert [c.args[0] for c in client.execute_long.call_args_list] == ["SplitDelete"]
        assert result["closed_gap"] is False

    @pytest.mark.asyncio(loop_scope="function")
    async def test_point_label_has_no_audio_to_delete(self):
        labels = '[["Label Track", [[5.0, 5.0, "marker"]]]]'
        client = _mock_client(labels)
        with pytest.raises(AudacityMCPError) as exc:
            await _register(client)["label_delete_region"].fn(index=0)
        assert exc.value.code == ErrorCode.VALIDATION_FAILED
        assert client.execute_long.call_count == 0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_index_past_end_rejected(self):
        client = _mock_client(TWO_LABELS)
        with pytest.raises(AudacityMCPError) as exc:
            await _register(client)["label_delete_region"].fn(index=7)
        assert exc.value.code == ErrorCode.VALUE_OUT_OF_RANGE
        assert client.execute_long.call_count == 0


class TestChapterFormatters:
    @pytest.mark.parametrize("seconds,expected", [
        (0, "00:00:00.000"),
        (3661.5, "01:01:01.500"),
        (-5, "00:00:00.000"),
    ])
    def test_timestamp(self, seconds, expected):
        assert format_chapter_timestamp(seconds) == expected

    def test_simple_format(self):
        out = format_chapters_simple([
            {"start": 0.0, "end": 1.0, "text": "Intro"},
            {"start": 65.25, "end": 70.0, "text": ""},
        ])
        assert out == "00:00:00.000 Intro\n00:01:05.250 Chapter 2\n"

    def test_cue_format(self):
        out = format_chapters_cue([{"start": 61.0, "end": 70.0, "text": 'He said "hi"'}])
        assert 'FILE "audio" WAVE' in out
        assert "  TRACK 01 AUDIO" in out
        assert "    TITLE \"He said 'hi'\"" in out
        assert "    INDEX 01 01:01:00" in out

    def test_podlove_format(self):
        parsed = json.loads(format_chapters_podlove([{"start": 90.0, "end": 95.0, "text": "Topic"}]))
        assert parsed["chapters"] == [{"startTime": "00:01:30.000", "title": "Topic"}]

    @pytest.mark.parametrize("raw,expected", [
        ("Chapter One", "Chapter_One"),
        ("bad/name:here?", "badnamehere"),
        ("///", "segment"),
        ("", "segment"),
    ])
    def test_sanitize_filename(self, raw, expected):
        assert sanitize_filename(raw) == expected

    def test_sanitize_filename_truncates(self):
        assert len(sanitize_filename("x" * 200)) == 60


class TestLabelExportChapters:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_writes_simple_chapters(self, tmp_path):
        out = tmp_path / "chapters.txt"
        result = await _register(_mock_client(TWO_LABELS))["label_export_chapters"].fn(path=str(out))
        assert result["chapters"] == 2
        assert out.read_text() == "00:00:00.000 Intro\n00:00:10.000 Interview\n"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_podlove_format(self, tmp_path):
        out = tmp_path / "chapters.json"
        await _register(_mock_client(TWO_LABELS))["label_export_chapters"].fn(
            path=str(out), format="podlove")
        assert json.loads(out.read_text())["version"] == "1.2.0"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_unknown_format_rejected(self, tmp_path):
        with pytest.raises(AudacityMCPError) as exc:
            await _register(_mock_client(TWO_LABELS))["label_export_chapters"].fn(
                path=str(tmp_path / "c.txt"), format="mp3")
        assert exc.value.code == ErrorCode.INVALID_FORMAT

    @pytest.mark.asyncio(loop_scope="function")
    async def test_existing_file_not_overwritten(self, tmp_path):
        out = tmp_path / "chapters.txt"
        out.write_text("keep me")
        with pytest.raises(AudacityMCPError) as exc:
            await _register(_mock_client(TWO_LABELS))["label_export_chapters"].fn(path=str(out))
        assert exc.value.code == ErrorCode.INVALID_PATH
        assert out.read_text() == "keep me"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_no_labels_rejected(self, tmp_path):
        with pytest.raises(AudacityMCPError) as exc:
            await _register(_mock_client(""))["label_export_chapters"].fn(
                path=str(tmp_path / "c.txt"))
        assert exc.value.code == ErrorCode.VALIDATION_FAILED


class TestLabelExportAudioSegments:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_exports_one_file_per_region_label(self, tmp_path):
        client = _mock_client(TWO_LABELS)

        async def _export(command, *args, **kwargs):
            if command == "Export2":
                open(kwargs["Filename"], "w").write("audio")
            return {"success": True, "raw": "", "message": "", "data": {}}

        client.execute_long = AsyncMock(side_effect=_export)
        result = await _register(client)["label_export_audio_segments"].fn(directory=str(tmp_path))

        assert result["success"] is True
        assert sorted(os.listdir(tmp_path)) == ["01_Intro.wav", "02_Interview.wav"]
        assert [c.kwargs["NumChannels"] for c in _calls_for(client, "Export2", long=True)] == [2, 2]

    @pytest.mark.asyncio(loop_scope="function")
    async def test_point_labels_are_skipped_and_counted(self, tmp_path):
        labels = '[["Label Track", [[0.0, 10.0, "Real"], [20.0, 20.0, "Marker"]]]]'
        result = await _register(_mock_client(labels))["label_export_audio_segments"].fn(
            directory=str(tmp_path))
        assert result["skipped_point_labels"] == 1
        assert len(result["exported"]) == 1

    @pytest.mark.asyncio(loop_scope="function")
    async def test_existing_files_are_skipped_not_overwritten(self, tmp_path):
        (tmp_path / "01_Intro.wav").write_text("original")
        result = await _register(_mock_client(TWO_LABELS))["label_export_audio_segments"].fn(
            directory=str(tmp_path))
        assert result["skipped_existing"] == [str(tmp_path / "01_Intro.wav")]
        assert (tmp_path / "01_Intro.wav").read_text() == "original"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_reports_failure_when_no_file_appears(self, tmp_path):
        result = await _register(_mock_client(TWO_LABELS))["label_export_audio_segments"].fn(
            directory=str(tmp_path))
        assert result["success"] is False
        assert all(item["created"] is False for item in result["exported"])

    @pytest.mark.asyncio(loop_scope="function")
    async def test_bad_format_and_channel_count_rejected(self, tmp_path):
        tools = _register(_mock_client(TWO_LABELS))
        with pytest.raises(AudacityMCPError) as exc:
            await tools["label_export_audio_segments"].fn(directory=str(tmp_path), format="xyz")
        assert exc.value.code == ErrorCode.INVALID_FORMAT
        with pytest.raises(AudacityMCPError) as exc:
            await tools["label_export_audio_segments"].fn(directory=str(tmp_path), num_channels=3)
        assert exc.value.code == ErrorCode.VALUE_OUT_OF_RANGE


def _delete_client(before: str, after: str, tracks: str = ONE_WAVE_ONE_LABEL_TRACK):
    """Client whose label list changes once SplitDelete has been issued."""
    client = MagicMock()
    state = {"deleted": False}

    async def _execute(command, *args, **kwargs):
        if command == "SplitDelete":
            state["deleted"] = True
        if command == "GetInfo":
            if kwargs.get("Type") == "Tracks":
                message = tracks
            else:
                message = after if state["deleted"] else before
            return {"success": True, "raw": "", "message": message, "data": {}}
        return {"success": True, "raw": "", "message": "", "data": {}}

    client.execute = AsyncMock(side_effect=_execute)
    client.execute_long = AsyncMock(side_effect=_execute)
    return client


class TestLabelDelete:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_selects_only_the_owning_label_track_then_split_deletes(self):
        after = '[["Label Track", [[0.0, 10.0, "Intro"]]]]'
        client = _delete_client(TWO_LABELS, after)
        result = await _register(client)["label_delete"].fn(index=1)

        assert result["success"] is True
        assert result["deleted"] == {"start": 10.0, "end": 60.0, "text": "Interview"}
        assert _calls_for(client, "SelectTracks")[0].kwargs == {
            "Track": 1, "TrackCount": 1, "Mode": "Set"}
        assert _calls_for(client, "SelectTime")[0].kwargs == {"Start": 10.0, "End": 60.0}
        assert "SplitDelete" in _commands(client)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_point_label_gets_an_epsilon_region(self):
        from audacity_mcp.tools.label_tools import POINT_LABEL_EPSILON
        before = '[["Label Track", [[5.0, 5.0, "cue"], [9.0, 9.0, "other"]]]]'
        after = '[["Label Track", [[9.0, 9.0, "other"]]]]'
        client = _delete_client(before, after)
        await _register(client)["label_delete"].fn(index=0)
        assert _calls_for(client, "SelectTime")[0].kwargs == {
            "Start": 5.0 - POINT_LABEL_EPSILON, "End": 5.0 + POINT_LABEL_EPSILON}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_label_swallowed_by_the_region_is_re_added(self):
        # The nested label sits entirely inside the target's span, so
        # SplitDelete takes it too — it has to come back afterwards.
        before = '[["Label Track", [[0.0, 60.0, "Segment"], [10.0, 20.0, "Inner"]]]]'
        client = _delete_client(before, "[]")
        result = await _register(client)["label_delete"].fn(index=0)

        assert result["restored"] == 1
        add_label_calls = _calls_for(client, "AddLabel")
        assert len(add_label_calls) == 1
        assert _calls_for(client, "SetLabel")[0].kwargs == {"Label": 0, "Text": "Inner"}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_reports_failure_when_nothing_was_removed(self):
        client = _delete_client(TWO_LABELS, TWO_LABELS)
        result = await _register(client)["label_delete"].fn(index=0)
        assert result["success"] is False
        assert result["count_before"] == result["count_after"] == 2
        assert _calls_for(client, "AddLabel") == []

    @pytest.mark.asyncio(loop_scope="function")
    async def test_index_past_end_rejected(self):
        with pytest.raises(AudacityMCPError) as exc:
            await _register(_mock_client(TWO_LABELS))["label_delete"].fn(index=9)
        assert exc.value.code == ErrorCode.VALUE_OUT_OF_RANGE

    @pytest.mark.asyncio(loop_scope="function")
    async def test_unresolvable_track_refuses_rather_than_guessing(self):
        client = _delete_client(TWO_LABELS, TWO_LABELS, tracks='[{"kind": "wave"}]')
        with pytest.raises(AudacityMCPError) as exc:
            await _register(client)["label_delete"].fn(index=0)
        assert exc.value.code == ErrorCode.COMMAND_FAILED
        assert "SplitDelete" not in _commands(client)
