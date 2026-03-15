import sys
import pytest
from unittest.mock import patch, MagicMock
from audacity_mcp.audacity_client import AudacityClient
from audacity_mcp_shared.error_codes import AudacityMCPError, ErrorCode


@pytest.fixture
def client():
    return AudacityClient()


IS_WIN = sys.platform == "win32"

if IS_WIN:
    from audacity_mcp.audacity_client import INVALID_HANDLE_VALUE


class TestClientPipes:
    def test_pipe_not_found(self, client):
        if IS_WIN:
            with patch("server.audacity_client.kernel32") as mock_k32:
                mock_k32.CreateFileW.return_value = INVALID_HANDLE_VALUE
                with patch("ctypes.get_last_error", return_value=2):  # ERROR_FILE_NOT_FOUND
                    with pytest.raises(AudacityMCPError) as exc_info:
                        client._open_pipes()
                    assert exc_info.value.code == ErrorCode.PIPE_NOT_FOUND
        else:
            with patch("builtins.open", side_effect=FileNotFoundError("not found")):
                with pytest.raises(AudacityMCPError) as exc_info:
                    client._open_pipes()
                assert exc_info.value.code == ErrorCode.PIPE_NOT_FOUND

    def test_pipe_open_os_error(self, client):
        if IS_WIN:
            with patch("server.audacity_client.kernel32") as mock_k32:
                mock_k32.CreateFileW.return_value = INVALID_HANDLE_VALUE
                with patch("ctypes.get_last_error", return_value=5):  # ERROR_ACCESS_DENIED
                    with pytest.raises(AudacityMCPError) as exc_info:
                        client._open_pipes()
                    assert exc_info.value.code == ErrorCode.PIPE_OPEN_FAILED
        else:
            with patch("builtins.open", side_effect=OSError("permission denied")):
                with pytest.raises(AudacityMCPError) as exc_info:
                    client._open_pipes()
                assert exc_info.value.code == ErrorCode.PIPE_OPEN_FAILED

    def test_send_raw_write_failure(self, client):
        if IS_WIN:
            client._to_pipe = 123  # fake handle
            client._from_pipe = 456
            with patch("server.audacity_client.kernel32") as mock_k32:
                mock_k32.WriteFile.return_value = False
                mock_k32.CloseHandle.return_value = True
                with patch("ctypes.get_last_error", return_value=232):
                    with pytest.raises(AudacityMCPError) as exc_info:
                        client._send_raw("Play:\n")
                    assert exc_info.value.code == ErrorCode.PIPE_WRITE_FAILED
            assert client._to_pipe is None
        else:
            mock_to = MagicMock()
            mock_to.write.side_effect = OSError("broken pipe")
            mock_from = MagicMock()
            client._to_pipe = mock_to
            client._from_pipe = mock_from
            with pytest.raises(AudacityMCPError) as exc_info:
                client._send_raw("Play:\n")
            assert exc_info.value.code == ErrorCode.PIPE_WRITE_FAILED
            assert client._to_pipe is None


@pytest.mark.asyncio
class TestClientExecute:
    async def test_execute_formats_and_sends(self, client):
        with patch.object(client, "_send_raw", return_value="BatchCommand finished: OK\n"):
            with patch.object(client, "_open_pipes"):
                client._to_pipe = MagicMock()
                client._from_pipe = MagicMock()
                result = await client.execute("Play")
                assert result["success"] is True
