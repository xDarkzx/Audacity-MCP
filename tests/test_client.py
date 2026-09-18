import asyncio
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
            with patch("audacity_mcp.audacity_client.kernel32") as mock_k32:
                mock_k32.CreateFileW.return_value = INVALID_HANDLE_VALUE
                with patch("ctypes.get_last_error", return_value=2):  # ERROR_FILE_NOT_FOUND
                    with pytest.raises(AudacityMCPError) as exc_info:
                        client._open_pipes()
                    assert exc_info.value.code == ErrorCode.PIPE_NOT_FOUND
        else:
            with patch("os.open", side_effect=FileNotFoundError("not found")):
                with pytest.raises(AudacityMCPError) as exc_info:
                    client._open_pipes()
                assert exc_info.value.code == ErrorCode.PIPE_NOT_FOUND

    def test_pipe_open_os_error(self, client):
        if IS_WIN:
            with patch("audacity_mcp.audacity_client.kernel32") as mock_k32:
                mock_k32.CreateFileW.return_value = INVALID_HANDLE_VALUE
                with patch("ctypes.get_last_error", return_value=5):  # ERROR_ACCESS_DENIED
                    with pytest.raises(AudacityMCPError) as exc_info:
                        client._open_pipes()
                    assert exc_info.value.code == ErrorCode.PIPE_OPEN_FAILED
        else:
            with patch("os.open", side_effect=OSError("permission denied")):
                with pytest.raises(AudacityMCPError) as exc_info:
                    client._open_pipes()
                assert exc_info.value.code == ErrorCode.PIPE_OPEN_FAILED

    def test_send_raw_write_failure(self, client):
        if IS_WIN:
            client._to_pipe = 123  # fake handle
            client._from_pipe = 456
            with patch("audacity_mcp.audacity_client.kernel32") as mock_k32:
                mock_k32.WriteFile.return_value = False
                mock_k32.CloseHandle.return_value = True
                with patch("ctypes.get_last_error", return_value=232):
                    with pytest.raises(AudacityMCPError) as exc_info:
                        client._send_raw("Play:\n")
                    assert exc_info.value.code == ErrorCode.PIPE_WRITE_FAILED
            assert client._to_pipe is None
        else:
            # _posix_send_raw operates on raw fds (os.write/os.read), and closing
            # is left to the _send_raw retry loop's caller, not _posix_send_raw
            # itself - so test the write failure at that layer directly.
            client._to_pipe = 99  # fake fd
            client._from_pipe = 100
            with patch("os.write", side_effect=OSError("broken pipe")):
                with pytest.raises(AudacityMCPError) as exc_info:
                    client._posix_send_raw("Play:\n")
                assert exc_info.value.code == ErrorCode.PIPE_WRITE_FAILED


@pytest.mark.asyncio
class TestClientExecute:
    async def test_execute_formats_and_sends(self, client):
        with patch.object(client, "_send_raw", return_value="BatchCommand finished: OK\n"):
            with patch.object(client, "_open_pipes"):
                client._to_pipe = MagicMock()
                client._from_pipe = MagicMock()
                result = await client.execute("Play")
                assert result["success"] is True

    async def test_execute_timeout_is_pipe_timeout_not_command_failed(self, client):
        # Regression (issue #17): asyncio.TimeoutError is a distinct class from
        # the builtin TimeoutError on Python 3.10 - catching only the builtin
        # let every asyncio.wait_for timeout fall through to the generic
        # COMMAND_FAILED handler on that version. Raising asyncio.TimeoutError
        # explicitly (not the builtin) targets exactly the path that broke.
        # _send_raw is mocked so the real Win32/posix pipe code never runs -
        # only the wait_for/exception-handling path is under test here.
        with patch.object(client, "_send_raw", return_value="BatchCommand finished: OK\n"):
            with patch("audacity_mcp.audacity_client.asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                with patch.object(client, "_open_pipes"):
                    with pytest.raises(AudacityMCPError) as exc_info:
                        await client.execute("Play")
                    assert exc_info.value.code == ErrorCode.PIPE_TIMEOUT

    async def test_execute_long_timeout_is_pipe_timeout_not_command_failed(self, client):
        with patch.object(client, "_send_raw", return_value="BatchCommand finished: OK\n"):
            with patch("audacity_mcp.audacity_client.asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                with patch.object(client, "_open_pipes"):
                    with pytest.raises(AudacityMCPError) as exc_info:
                        await client.execute_long("Play")
                    assert exc_info.value.code == ErrorCode.PIPE_TIMEOUT


@pytest.mark.skipif(IS_WIN, reason="POSIX FIFO reader semantics")
class TestPosixLateReply:
    """Regression: a slow reply must be waited for, never re-sent, and the read end
    must stay open until it lands. Real os.pipe() pairs stand in for the FIFOs."""

    def _pipes(self, client):
        import os

        to_r, to_w = os.pipe()        # our command goes into to_w; to_r stands in for the relay
        from_r, from_w = os.pipe()    # the relay's reply comes from from_w; we read from_r
        client._to_pipe = to_w
        client._from_pipe = from_r
        return to_r, to_w, from_r, from_w

    def test_posix_send_raw_waits_past_pipe_read_for_first_byte(self, client):
        import os
        import threading

        from audacity_mcp_shared.constants import Timeouts

        to_r, to_w, from_r, from_w = self._pipes(client)
        try:
            # Reply arrives well after PIPE_READ: the old per-chunk gate raised
            # PIPE_TIMEOUT here, closed the read end and re-sent the command.
            with patch.object(Timeouts, "PIPE_READ", 0.05):
                t = threading.Timer(0.3, lambda: os.write(from_w, b"BatchCommand finished: OK\n"))
                t.start()
                raw = client._posix_send_raw("CursTrackStart:\n")
                t.join()
            assert "BatchCommand finished: OK" in raw
            assert os.read(to_r, 1024) == b"CursTrackStart:\n"  # sent exactly once
        finally:
            for fd in (to_r, to_w, from_r, from_w):
                os.close(fd)

    def test_posix_send_raw_stall_mid_reply_is_timeout(self, client):
        import os

        from audacity_mcp_shared.constants import Timeouts

        to_r, to_w, from_r, from_w = self._pipes(client)
        try:
            os.write(from_w, b"partial")  # reply started, then the relay goes silent
            with patch.object(Timeouts, "PIPE_READ", 0.05):
                with pytest.raises(AudacityMCPError) as exc_info:
                    client._posix_send_raw("GetInfo:\n")
            assert exc_info.value.code == ErrorCode.PIPE_TIMEOUT
        finally:
            for fd in (to_r, to_w, from_r, from_w):
                os.close(fd)

    def test_send_raw_never_retries_a_busy_timeout(self, client):
        # The retry loop exists for the Linux relay's fast empty-read race. A
        # PIPE_TIMEOUT means Audacity is busy; re-sending queued the same command
        # again and again behind the stalled one.
        busy = AudacityMCPError(ErrorCode.PIPE_TIMEOUT, "busy")
        with patch.object(client, "_open_pipes"), patch.object(client, "_close_pipes"):
            with patch.object(client, "_posix_send_raw", side_effect=busy) as send:
                with pytest.raises(AudacityMCPError) as exc_info:
                    client._send_raw("Play:\n")
        assert exc_info.value.code == ErrorCode.PIPE_TIMEOUT
        assert send.call_count == 1

    def test_send_raw_still_retries_fast_empty_reads(self, client):
        with patch.object(client, "_open_pipes"), patch.object(client, "_close_pipes"):
            with patch.object(client, "_posix_send_raw", side_effect=["", "BatchCommand finished: OK\n"]) as send:
                raw = client._send_raw("Play:\n")
        assert "OK" in raw
        assert send.call_count == 2


@pytest.mark.asyncio
class TestExecutePendingReply:
    """Regression: a caller-side timeout must leave the worker running as the
    reader of record instead of closing the pipes under it (SIGPIPE in Audacity),
    and the next command must wait for that worker rather than send on top of it."""

    async def test_timeout_keeps_worker_and_does_not_close_pipes(self, client):
        import time

        from audacity_mcp_shared.constants import Timeouts

        calls = []

        def slow_send(cmd):
            calls.append(("start", cmd, time.monotonic()))
            time.sleep(0.3)
            calls.append(("end", cmd, time.monotonic()))
            return "BatchCommand finished: OK\n"

        with patch.object(client, "_send_raw", side_effect=slow_send):
            with patch.object(client, "_close_pipes") as close:
                with patch.object(Timeouts, "COMMAND", 0.05):
                    with pytest.raises(AudacityMCPError) as exc_info:
                        await client.execute("CursTrackStart")
                assert exc_info.value.code == ErrorCode.PIPE_TIMEOUT
                assert client._pending is not None
                close.assert_not_called()

                # Next command waits for the pending worker, then sends its own.
                result = await client.execute("GetInfo")
        assert result["success"] is True
        assert client._pending is None
        names = [c[0] + ":" + c[1].split(":")[0] for c in calls]
        assert names == ["start:CursTrackStart", "end:CursTrackStart", "start:GetInfo", "end:GetInfo"]

    async def test_busy_worker_makes_next_command_refuse_without_sending(self, client):
        import time

        from audacity_mcp_shared.constants import Timeouts

        def slow_send(cmd):
            time.sleep(0.4)
            return "BatchCommand finished: OK\n"

        with patch.object(client, "_send_raw", side_effect=slow_send) as send:
            with patch.object(Timeouts, "COMMAND", 0.05):
                with pytest.raises(AudacityMCPError):
                    await client.execute("CursTrackStart")
                with pytest.raises(AudacityMCPError) as exc_info:
                    await client.execute("GetInfo")
            assert exc_info.value.code == ErrorCode.PIPE_TIMEOUT
            assert "still busy" in exc_info.value.message
            assert send.call_count == 1  # GetInfo was never sent
            await asyncio.sleep(0.5)     # let the worker finish before the test ends

    async def test_pending_worker_failure_is_swallowed_for_next_command(self, client):
        import time

        from audacity_mcp_shared.constants import Timeouts

        outcomes = [AudacityMCPError(ErrorCode.PIPE_TIMEOUT, "gave up"), "BatchCommand finished: OK\n"]

        def send(cmd):
            time.sleep(0.2)
            outcome = outcomes.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        with patch.object(client, "_send_raw", side_effect=send):
            with patch.object(Timeouts, "COMMAND", 0.05):
                with pytest.raises(AudacityMCPError):
                    await client.execute("Play")
            result = await client.execute("Stop")
        assert result["success"] is True
        assert client._pending is None

    async def test_close_leaves_pipes_to_pending_worker(self, client):
        client._pending = (asyncio.get_running_loop().create_future(), "Play")
        with patch.object(client, "_close_pipes") as close:
            await client.close()
        close.assert_not_called()
        client._pending = None
        with patch.object(client, "_close_pipes") as close:
            await client.close()
        close.assert_called_once()


class TestCloseSync:
    """Regression: atexit was given the async close(), which only produced an
    un-awaited coroutine at exit (RuntimeWarning, pipes left open)."""

    def test_close_sync_closes_pipes(self, client):
        with patch.object(client, "_close_pipes") as close:
            client.close_sync()
        close.assert_called_once()

    def test_close_sync_defers_to_pending_worker(self, client):
        client._pending = (MagicMock(), "Play")
        with patch.object(client, "_close_pipes") as close:
            client.close_sync()
        close.assert_not_called()

    def test_main_registers_a_sync_close_with_atexit(self):
        import importlib
        import inspect

        with patch("atexit.register") as register:
            import audacity_mcp.main as main
            importlib.reload(main)
        registered = [c.args[0] for c in register.call_args_list]
        assert main.client.close_sync in registered
        assert not any(inspect.iscoroutinefunction(fn) for fn in registered)
