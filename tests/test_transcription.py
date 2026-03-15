import pytest
from unittest.mock import patch, AsyncMock, MagicMock, PropertyMock
from audacity_mcp_shared.error_codes import AudacityMCPError, ErrorCode


class FakeSegment:
    def __init__(self, start, end, text):
        self.start = start
        self.end = end
        self.text = text


class FakeInfo:
    def __init__(self, language="en", language_probability=0.95, duration=10.5):
        self.language = language
        self.language_probability = language_probability
        self.duration = duration


def make_fake_segments():
    return [
        FakeSegment(0.0, 2.5, " Hello world"),
        FakeSegment(2.5, 5.0, " This is a test"),
    ]


def fake_transcribe(audio_path, **kwargs):
    return iter(make_fake_segments()), FakeInfo()


@pytest.fixture
def mock_client():
    c = MagicMock()
    c.execute = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
    c.execute_long = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
    return c


@pytest.fixture
def registered_tools(mock_client):
    from mcp.server.fastmcp import FastMCP
    mcp = FastMCP("TestTranscription")
    with patch("server.main.client", mock_client):
        from audacity_mcp.tools.transcription_tools import register
        register(mcp)
    return mcp._tool_manager._tools


class TestValidation:
    def test_invalid_model_size(self, registered_tools):
        tool = registered_tools["transcribe_audio"]
        with pytest.raises(AudacityMCPError) as exc:
            import asyncio
            asyncio.get_event_loop().run_until_complete(tool.fn(model_size="huge"))
        assert exc.value.code == ErrorCode.INVALID_PARAMETER

    def test_invalid_task(self, registered_tools):
        tool = registered_tools["transcribe_audio"]
        with pytest.raises(AudacityMCPError) as exc:
            import asyncio
            asyncio.get_event_loop().run_until_complete(tool.fn(task="summarize"))
        assert exc.value.code == ErrorCode.INVALID_PARAMETER

    def test_invalid_format(self, registered_tools):
        tool = registered_tools["transcribe_to_file"]
        with pytest.raises(AudacityMCPError) as exc:
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                tool.fn(path="/tmp/out.txt", format="docx")
            )
        assert exc.value.code == ErrorCode.INVALID_FORMAT

    def test_relative_path_rejected(self, registered_tools):
        tool = registered_tools["transcribe_to_file"]
        with pytest.raises(AudacityMCPError) as exc:
            import asyncio
            asyncio.get_event_loop().run_until_complete(
                tool.fn(path="relative/path.srt", format="srt")
            )
        assert exc.value.code == ErrorCode.INVALID_PATH

    def test_invalid_model_set(self, registered_tools):
        tool = registered_tools["transcription_set_model"]
        with pytest.raises(AudacityMCPError) as exc:
            import asyncio
            asyncio.get_event_loop().run_until_complete(tool.fn(model_size="xxx"))
        assert exc.value.code == ErrorCode.INVALID_PARAMETER


class TestTranscribeAudio:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_transcribe_returns_job_id(self, registered_tools, mock_client):
        tool = registered_tools["transcribe_audio"]
        result = await tool.fn(model_size="base")
        assert "job_id" in result
        assert result["status"] == "running"

    @pytest.mark.asyncio(loop_scope="function")
    async def test_transcribe_selection_returns_job_id(self, registered_tools, mock_client):
        tool = registered_tools["transcribe_selection"]
        result = await tool.fn(model_size="tiny")
        assert "job_id" in result


class TestTranscribeToLabels:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_returns_job_id(self, registered_tools, mock_client):
        tool = registered_tools["transcribe_to_labels"]
        result = await tool.fn(model_size="base")
        assert "job_id" in result


class TestTranscribeToFile:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_srt_returns_job_id(self, registered_tools, mock_client, tmp_path):
        tool = registered_tools["transcribe_to_file"]
        out_path = str(tmp_path / "test.srt")
        result = await tool.fn(path=out_path, format="srt", model_size="base")
        assert "job_id" in result

    @pytest.mark.asyncio(loop_scope="function")
    async def test_vtt_returns_job_id(self, registered_tools, mock_client, tmp_path):
        tool = registered_tools["transcribe_to_file"]
        out_path = str(tmp_path / "test.vtt")
        result = await tool.fn(path=out_path, format="vtt", model_size="base")
        assert "job_id" in result

    @pytest.mark.asyncio(loop_scope="function")
    async def test_txt_returns_job_id(self, registered_tools, mock_client, tmp_path):
        tool = registered_tools["transcribe_to_file"]
        out_path = str(tmp_path / "test.txt")
        result = await tool.fn(path=out_path, format="txt", model_size="base")
        assert "job_id" in result


class TestFormatters:
    def test_srt_timestamps(self):
        from audacity_mcp.tools.transcription_tools import _format_timestamp_srt
        assert _format_timestamp_srt(0.0) == "00:00:00,000"
        assert _format_timestamp_srt(61.5) == "00:01:01,500"
        assert _format_timestamp_srt(3661.123) == "01:01:01,123"

    def test_vtt_timestamps(self):
        from audacity_mcp.tools.transcription_tools import _format_timestamp_vtt
        assert _format_timestamp_vtt(0.0) == "00:00:00.000"
        assert _format_timestamp_vtt(61.5) == "00:01:01.500"

    def test_segments_to_srt(self):
        from audacity_mcp.tools.transcription_tools import _segments_to_srt
        segments = [{"start": 0.0, "end": 2.5, "text": "Hello"}, {"start": 2.5, "end": 5.0, "text": "World"}]
        srt = _segments_to_srt(segments)
        assert "1\n" in srt
        assert "2\n" in srt
        assert "00:00:00,000 --> 00:00:02,500" in srt

    def test_segments_to_vtt(self):
        from audacity_mcp.tools.transcription_tools import _segments_to_vtt
        segments = [{"start": 0.0, "end": 2.5, "text": "Hello"}]
        vtt = _segments_to_vtt(segments)
        assert vtt.startswith("WEBVTT")
        assert "00:00:00.000 --> 00:00:02.500" in vtt

    def test_segments_to_txt(self):
        from audacity_mcp.tools.transcription_tools import _segments_to_txt
        segments = [{"start": 0.0, "end": 2.5, "text": "Hello"}, {"start": 2.5, "end": 5.0, "text": "World"}]
        txt = _segments_to_txt(segments)
        assert txt == "Hello\nWorld"


class TestModelCaching:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_set_model_returns_job_id(self, registered_tools):
        tool = registered_tools["transcription_set_model"]
        result = await tool.fn(model_size="tiny")
        assert "job_id" in result
        assert result["status"] == "running"


class TestToolRegistration:
    def test_six_transcription_tools_registered(self, registered_tools):
        expected = {"transcribe_audio", "transcribe_selection", "transcribe_to_labels",
                    "transcribe_to_file", "transcription_set_model", "check_transcription_status"}
        assert expected.issubset(set(registered_tools.keys()))


class TestCheckStatus:
    @pytest.mark.asyncio(loop_scope="function")
    async def test_unknown_job_id(self, registered_tools):
        tool = registered_tools["check_transcription_status"]
        result = await tool.fn(job_id="nonexistent")
        assert "error" in result
