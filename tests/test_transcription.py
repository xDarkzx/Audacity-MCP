import os
import tempfile

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
    with patch("audacity_mcp.main.client", mock_client):
        from audacity_mcp.tools.transcription_tools import register
        register(mcp)
    return mcp._tool_manager._tools


class TestValidation:
    def test_invalid_model_size(self, registered_tools):
        tool = registered_tools["transcribe_audio"]
        with pytest.raises(AudacityMCPError) as exc:
            import asyncio
            asyncio.run(tool.fn(model_size="huge"))
        assert exc.value.code == ErrorCode.INVALID_PARAMETER

    def test_invalid_task(self, registered_tools):
        tool = registered_tools["transcribe_audio"]
        with pytest.raises(AudacityMCPError) as exc:
            import asyncio
            asyncio.run(tool.fn(task="summarize"))
        assert exc.value.code == ErrorCode.INVALID_PARAMETER

    def test_invalid_format(self, registered_tools):
        tool = registered_tools["transcribe_to_file"]
        # Format validation is what's under test here, not path validation —
        # use a genuinely cross-platform absolute path (a hardcoded POSIX
        # "/tmp/..." string isn't absolute on Windows, which would fail the
        # path check before the format check ever runs).
        out_path = os.path.join(tempfile.gettempdir(), "out.txt")
        with pytest.raises(AudacityMCPError) as exc:
            import asyncio
            asyncio.run(
                tool.fn(path=out_path, format="docx")
            )
        assert exc.value.code == ErrorCode.INVALID_FORMAT

    def test_relative_path_rejected(self, registered_tools):
        tool = registered_tools["transcribe_to_file"]
        with pytest.raises(AudacityMCPError) as exc:
            import asyncio
            asyncio.run(
                tool.fn(path="relative/path.srt", format="srt")
            )
        assert exc.value.code == ErrorCode.INVALID_PATH

    def test_invalid_model_set(self, registered_tools):
        tool = registered_tools["transcription_set_model"]
        with pytest.raises(AudacityMCPError) as exc:
            import asyncio
            asyncio.run(tool.fn(model_size="xxx"))
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


class TestSetupCudaPath:
    def test_adds_bin_dir_for_namespace_package_with_no_file(self, monkeypatch):
        # nvidia-cublas-cu12 / nvidia-cudnn-cu12 are PEP 420 namespace packages
        # (no __init__.py), so __file__ is None on current package versions -
        # only __path__ is reliably populated. Fake both that way.
        import sys
        import types
        from audacity_mcp.tools.transcription_tools import _setup_cuda_path

        for pkg in ("cublas", "cudnn"):
            fake_module = types.ModuleType(f"nvidia.{pkg}")
            fake_module.__file__ = None
            fake_module.__path__ = [f"/fake/nvidia/{pkg}"]
            monkeypatch.setitem(sys.modules, f"nvidia.{pkg}", fake_module)
        monkeypatch.setitem(sys.modules, "nvidia", types.ModuleType("nvidia"))
        monkeypatch.setenv("PATH", "")

        _setup_cuda_path()

        path = os.environ["PATH"]
        assert os.path.join("/fake/nvidia/cublas", "bin") in path
        assert os.path.join("/fake/nvidia/cudnn", "bin") in path


class TestCudaIsAvailable:
    def _fake_torch(self, cuda_available: bool):
        import types
        fake_torch = types.ModuleType("torch")
        fake_torch.cuda = types.SimpleNamespace(is_available=lambda: cuda_available)
        return fake_torch

    def test_torch_false_falls_through_to_ctypes_check(self, monkeypatch):
        # Regression: a coincidentally-installed CPU-only (or mismatched-CUDA)
        # torch build must not mask a working nvidia-cublas-cu12 install -
        # faster-whisper runs on CTranslate2, not torch.
        import sys
        from audacity_mcp.tools.transcription_tools import _cuda_is_available

        monkeypatch.setitem(sys.modules, "torch", self._fake_torch(cuda_available=False))
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr("ctypes.cdll.LoadLibrary", lambda name: object())

        assert _cuda_is_available() is True

    def test_torch_true_short_circuits(self, monkeypatch):
        import sys
        from audacity_mcp.tools.transcription_tools import _cuda_is_available

        monkeypatch.setitem(sys.modules, "torch", self._fake_torch(cuda_available=True))

        def _boom(name):
            pytest.fail("should not reach the ctypes check when torch reports True")

        monkeypatch.setattr("ctypes.cdll.LoadLibrary", _boom)

        assert _cuda_is_available() is True

    def test_no_torch_no_cublas_returns_false(self, monkeypatch):
        import builtins
        import sys
        from audacity_mcp.tools.transcription_tools import _cuda_is_available

        monkeypatch.delitem(sys.modules, "torch", raising=False)
        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("no torch")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        monkeypatch.setattr(sys, "platform", "win32")

        def _raise(name):
            raise OSError("DLL not found")

        monkeypatch.setattr("ctypes.cdll.LoadLibrary", _raise)

        assert _cuda_is_available() is False

    def test_macos_always_false(self, monkeypatch):
        import sys
        from audacity_mcp.tools.transcription_tools import _cuda_is_available

        monkeypatch.setitem(sys.modules, "torch", self._fake_torch(cuda_available=False))
        monkeypatch.setattr(sys, "platform", "darwin")

        assert _cuda_is_available() is False
