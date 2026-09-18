from __future__ import annotations

import asyncio
import sys

from audacity_mcp_shared.constants import PipePaths, Timeouts
from audacity_mcp_shared.error_codes import AudacityMCPError, ErrorCode
from audacity_mcp_shared.pipe_protocol import format_command, parse_response

if sys.platform == "win32":
    import ctypes
    import ctypes.wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    GENERIC_READ = 0x80000000
    GENERIC_WRITE = 0x40000000
    OPEN_EXISTING = 3
    INVALID_HANDLE_VALUE = ctypes.wintypes.HANDLE(-1).value  # 0xFFFFFFFFFFFFFFFF on 64-bit

    kernel32.CreateFileW.restype = ctypes.wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        ctypes.wintypes.LPCWSTR,  # lpFileName
        ctypes.wintypes.DWORD,    # dwDesiredAccess
        ctypes.wintypes.DWORD,    # dwShareMode
        ctypes.c_void_p,          # lpSecurityAttributes
        ctypes.wintypes.DWORD,    # dwCreationDisposition
        ctypes.wintypes.DWORD,    # dwFlagsAndAttributes
        ctypes.wintypes.HANDLE,   # hTemplateFile
    ]

    kernel32.WriteFile.restype = ctypes.wintypes.BOOL
    kernel32.WriteFile.argtypes = [
        ctypes.wintypes.HANDLE,            # hFile
        ctypes.c_void_p,                   # lpBuffer
        ctypes.wintypes.DWORD,             # nNumberOfBytesToWrite
        ctypes.POINTER(ctypes.wintypes.DWORD),  # lpNumberOfBytesWritten
        ctypes.c_void_p,                   # lpOverlapped
    ]

    kernel32.ReadFile.restype = ctypes.wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        ctypes.wintypes.HANDLE,            # hFile
        ctypes.c_void_p,                   # lpBuffer
        ctypes.wintypes.DWORD,             # nNumberOfBytesToRead
        ctypes.POINTER(ctypes.wintypes.DWORD),  # lpNumberOfBytesRead
        ctypes.c_void_p,                   # lpOverlapped
    ]

    kernel32.CloseHandle.restype = ctypes.wintypes.BOOL
    kernel32.CloseHandle.argtypes = [ctypes.wintypes.HANDLE]

    kernel32.WaitNamedPipeW.restype = ctypes.wintypes.BOOL
    kernel32.WaitNamedPipeW.argtypes = [
        ctypes.wintypes.LPCWSTR,  # lpNamedPipeName
        ctypes.wintypes.DWORD,    # nTimeOut (ms)
    ]

    ERROR_PIPE_BUSY = 231


class AudacityClient:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._to_pipe = None
        self._from_pipe = None
        # (future, command) of a worker whose caller timed out but which is
        # still waiting for Audacity's reply; see _run/_await_pending.
        self._pending = None

    def _open_pipes(self):
        try:
            if sys.platform == "win32":
                # Audacity requires FromSrvPipe opened first, and both need read+write access
                self._from_pipe = self._win32_open_pipe(PipePaths.FROM_SRV, GENERIC_READ | GENERIC_WRITE)
                self._to_pipe = self._win32_open_pipe(PipePaths.TO_SRV, GENERIC_READ | GENERIC_WRITE)
            else:
                self._posix_open_pipes()
        except AudacityMCPError:
            self._close_pipes()
            raise
        except FileNotFoundError:
            self._close_pipes()
            raise AudacityMCPError(
                ErrorCode.PIPE_NOT_FOUND,
                "Audacity pipe not found. Is Audacity running with mod-script-pipe enabled? "
                "(Edit > Preferences > Modules > mod-script-pipe = Enabled, then restart Audacity)",
            )
        except OSError as e:
            self._close_pipes()
            raise AudacityMCPError(ErrorCode.PIPE_OPEN_FAILED, str(e))

    def _posix_open_pipes(self):
        # Audacity's mod-script-pipe relay opens its WRITE end (FROM) first and
        # blocks for a reader, so the client must open FROM before TO. The reverse
        # order (the historical bug) races the relay and yields immediate empty
        # reads. Open FROM read-only + O_NONBLOCK so it never hangs and reads are
        # driven by select()/os.read in _posix_send_raw. Open TO with O_NONBLOCK
        # too (it raises ENXIO until the relay's read end is up — poll briefly),
        # then clear O_NONBLOCK so os.write to it behaves normally. We deliberately
        # keep RAW integer fds here (no buffered file object): the relay closes
        # both ends right after each reply, and a buffered reader's readahead/EOF
        # handling drops the reply, whereas os.read() returns the bytes reliably.
        import errno
        import fcntl
        import os
        import time

        to_path, from_path = PipePaths.resolve()
        from_fd = os.open(from_path, os.O_RDONLY | os.O_NONBLOCK)
        try:
            deadline = time.monotonic() + Timeouts.PIPE_OPEN
            while True:
                try:
                    to_fd = os.open(to_path, os.O_WRONLY | os.O_NONBLOCK)
                    break
                except OSError as e:
                    if e.errno == errno.ENXIO and time.monotonic() < deadline:
                        time.sleep(0.01)
                        continue
                    raise
        except BaseException:
            os.close(from_fd)
            raise

        flags = fcntl.fcntl(to_fd, fcntl.F_GETFL)
        fcntl.fcntl(to_fd, fcntl.F_SETFL, flags & ~os.O_NONBLOCK)

        self._from_pipe = from_fd  # raw int fd (read, non-blocking)
        self._to_pipe = to_fd      # raw int fd (write, blocking)

    def _win32_open_pipe(self, pipe_path: str, access: int) -> ctypes.wintypes.HANDLE:
        for _ in range(3):
            handle = kernel32.CreateFileW(
                pipe_path,
                access,
                0,     # no sharing
                None,  # default security
                OPEN_EXISTING,
                0,     # default attributes
                None,  # no template
            )
            if handle != INVALID_HANDLE_VALUE:
                return handle
            err = ctypes.get_last_error()
            if err == 2:  # ERROR_FILE_NOT_FOUND
                raise AudacityMCPError(
                    ErrorCode.PIPE_NOT_FOUND,
                    "Audacity pipe not found. Is Audacity running with mod-script-pipe enabled? "
                    "(Edit > Preferences > Modules > mod-script-pipe = Enabled, then restart Audacity)",
                )
            if err == ERROR_PIPE_BUSY:
                # Wait up to 5 seconds for pipe to become available
                kernel32.WaitNamedPipeW(pipe_path, 5000)
                continue
            raise AudacityMCPError(
                ErrorCode.PIPE_OPEN_FAILED,
                f"Failed to open pipe {pipe_path}: Win32 error {err}",
            )
        raise AudacityMCPError(
            ErrorCode.PIPE_OPEN_FAILED,
            f"Pipe {pipe_path} remained busy after retries",
        )

    def _close_pipes(self):
        if sys.platform == "win32":
            for handle in (self._to_pipe, self._from_pipe):
                if handle is not None:
                    try:
                        kernel32.CloseHandle(handle)
                    except OSError:
                        pass
        else:
            import os

            for fd in (self._to_pipe, self._from_pipe):
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
        self._to_pipe = None
        self._from_pipe = None

    # Audacity's mod-script-pipe relay (Linux) tears down and reopens BOTH FIFO
    # ends after every command cycle. Even a fresh per-command open races that
    # reopen, so any single attempt succeeds only ~50% of the time (empty read /
    # broken pipe), with successes and failures alternating cycle-to-cycle. A
    # bounded retry — closing our ends between attempts so the relay finishes its
    # cycle and we reopen clean — makes it reliable. A bad cycle fails fast
    # (immediate empty read), so the retries are cheap in the common case.
    #
    # A retry is ONLY for that fast failure. A *slow* reply (Audacity still busy
    # with the previous effect, or with this command) must never be retried: each
    # retry re-sent the command, and closing our read end while Audacity still
    # owed us a reply made its eventual write hit a reader-less FIFO — SIGPIPE,
    # which kills Audacity. So the worker below keeps the pipes open and waits for
    # the reply for up to LONG_COMMAND regardless of how long the *caller* is
    # willing to wait; execute() gives up on the caller's behalf but leaves the
    # worker running as the reader of record (see _pending).
    _POSIX_SEND_ATTEMPTS = 6

    def _send_raw(self, command_str: str) -> str:
        if sys.platform == "win32":
            if self._to_pipe is None or self._from_pipe is None:
                self._open_pipes()
            return self._win32_send_raw(command_str)

        import time

        last_raw = ""
        last_err = None
        for attempt in range(self._POSIX_SEND_ATTEMPTS):
            try:
                self._open_pipes()  # always fresh; never cache a fd across commands
                raw = self._posix_send_raw(command_str)
                if "BatchCommand finished" in raw:
                    return raw  # complete, well-formed response
                if raw.strip():
                    last_raw = raw  # non-empty but no terminator: keep as fallback
            except AudacityMCPError as e:
                if e.code == ErrorCode.PIPE_TIMEOUT:
                    raise  # Audacity is busy, not a relay race: never re-send
                last_err = e
            finally:
                self._close_pipes()  # tear our ends down so the relay re-cycles
            time.sleep(0.05 * (attempt + 1))

        if last_raw:
            return last_raw
        raise last_err or AudacityMCPError(
            ErrorCode.PIPE_READ_FAILED,
            f"Empty response from Audacity pipe after {self._POSIX_SEND_ATTEMPTS} attempts",
        )

    def _win32_send_raw(self, command_str: str) -> str:
        data = command_str.encode("utf-8")
        bytes_written = ctypes.wintypes.DWORD()
        try:
            ok = kernel32.WriteFile(
                self._to_pipe,
                data,
                len(data),
                ctypes.byref(bytes_written),
                None,
            )
            if not ok:
                raise OSError(f"WriteFile failed: Win32 error {ctypes.get_last_error()}")
        except OSError as e:
            self._close_pipes()
            raise AudacityMCPError(ErrorCode.PIPE_WRITE_FAILED, str(e))

        try:
            response_parts = []
            buf = ctypes.create_string_buffer(65536)
            while True:
                bytes_read = ctypes.wintypes.DWORD()
                ok = kernel32.ReadFile(
                    self._from_pipe,
                    buf,
                    len(buf),
                    ctypes.byref(bytes_read),
                    None,
                )
                if not ok:
                    err = ctypes.get_last_error()
                    raise OSError(f"ReadFile failed: Win32 error {err}")
                if bytes_read.value == 0:
                    break
                chunk = buf.raw[:bytes_read.value].decode("utf-8")
                response_parts.append(chunk)
                accumulated = "".join(response_parts)
                if "\n\n" in accumulated:
                    break
            return "".join(response_parts)
        except OSError as e:
            self._close_pipes()
            raise AudacityMCPError(ErrorCode.PIPE_READ_FAILED, str(e))

    def _posix_send_raw(self, command_str: str) -> str:
        # Operates on the raw int fds from _posix_open_pipes. Closing is left to
        # the caller (_send_raw's retry loop), which tears the pipes down between
        # attempts so the relay can complete its cycle.
        #
        # The FIRST byte of the reply may take as long as Audacity needs — it
        # only answers once its main thread is free, and after a heavy effect on
        # a long file that can be minutes. Waiting here (up to LONG_COMMAND) is
        # what keeps our read end open so Audacity's late write cannot SIGPIPE
        # it. Only once the reply has started is a stall treated as a dead relay
        # (PIPE_READ between chunks).
        import os
        import select
        import time

        try:
            os.write(self._to_pipe, command_str.encode("utf-8"))
        except OSError as e:
            raise AudacityMCPError(ErrorCode.PIPE_WRITE_FAILED, str(e))

        try:
            chunks = []
            first_byte_deadline = time.monotonic() + Timeouts.LONG_COMMAND
            while True:
                if chunks:
                    wait = Timeouts.PIPE_READ
                else:
                    wait = max(0.0, first_byte_deadline - time.monotonic())
                ready, _, _ = select.select([self._from_pipe], [], [], wait)
                if not ready:
                    if chunks:
                        raise AudacityMCPError(
                            ErrorCode.PIPE_TIMEOUT,
                            f"Pipe read timed out after {Timeouts.PIPE_READ}s mid-reply — "
                            "Audacity may have stopped responding",
                        )
                    raise AudacityMCPError(
                        ErrorCode.PIPE_TIMEOUT,
                        f"No reply from Audacity within {Timeouts.LONG_COMMAND}s — "
                        "it may be stuck (a modal dialog?) or have stopped responding",
                    )
                chunk = os.read(self._from_pipe, 65536)
                if not chunk:  # EOF: relay closed its write end
                    break
                chunks.append(chunk)
                # Audacity terminates every reply with this status line.
                if b"BatchCommand finished" in b"".join(chunks):
                    break
            return b"".join(chunks).decode("utf-8", errors="replace")
        except AudacityMCPError:
            raise
        except OSError as e:
            raise AudacityMCPError(ErrorCode.PIPE_READ_FAILED, str(e))

    async def _await_pending(self, timeout: float, command: str) -> None:
        # A previous command's worker is still waiting for Audacity's reply. It
        # owns the pipes, so nothing may be sent until it finishes. Wait for it
        # within this command's own budget; if Audacity is still busy after
        # that, refuse without touching the pipe — a clean "busy, retry later"
        # rather than a second command queued behind the first.
        pending = self._pending
        if pending is None:
            return
        fut, prev_command = pending
        try:
            await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
        except (asyncio.TimeoutError, TimeoutError):
            raise AudacityMCPError(
                ErrorCode.PIPE_TIMEOUT,
                f"Audacity is still busy finishing an earlier command ({prev_command}); "
                f"{command} was not sent. Wait for Audacity to become idle and retry.",
            )
        except Exception:  # noqa: S110 - the worker's own outcome was already reported to its caller
            pass
        self._pending = None

    async def _run(self, command: str, cmd_str: str, timeout: float) -> dict:
        async with self._lock:
            await self._await_pending(timeout, command)
            loop = asyncio.get_running_loop()
            fut = loop.run_in_executor(None, self._send_raw, cmd_str)
            try:
                raw = await asyncio.wait_for(asyncio.shield(fut), timeout=timeout)
            except (asyncio.TimeoutError, TimeoutError):
                # The caller stops waiting, but the worker must NOT be torn down:
                # it stays as the reader of record until Audacity's reply lands
                # (or LONG_COMMAND passes), so the late write never hits a closed
                # FIFO. Closing the fds here from the event-loop thread — the
                # old behaviour — was exactly what killed Audacity with SIGPIPE.
                self._pending = (fut, command)
                raise AudacityMCPError(
                    ErrorCode.PIPE_TIMEOUT,
                    f"Command timed out after {timeout}s: {command}. Audacity is still busy; "
                    "its reply will be collected in the background and the next command "
                    "waits for it.",
                )
            except AudacityMCPError:
                raise
            except Exception as e:
                raise AudacityMCPError(ErrorCode.COMMAND_FAILED, str(e))
        return parse_response(raw)

    async def execute(self, command: str, extra_params: dict | None = None, **params) -> dict:
        cmd_str = format_command(command, extra_params=extra_params, **params)
        return await self._run(command, cmd_str, Timeouts.COMMAND)

    async def execute_long(self, command: str, extra_params: dict | None = None, **params) -> dict:
        cmd_str = format_command(command, extra_params=extra_params, **params)
        return await self._run(command, cmd_str, Timeouts.LONG_COMMAND)

    def close_sync(self) -> None:
        """Close the pipes; safe to register with atexit.

        (Registering the async close() there only built a coroutine object at
        exit that was never awaited: nothing got closed and Python warned.)
        """
        if self._pending is not None:
            return  # the worker owns the pipes and closes them when the reply lands
        self._close_pipes()

    async def close(self):
        self.close_sync()
