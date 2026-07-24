import os
import stat
import sys
from pathlib import Path


def _is_fifo(path: str) -> bool:
    try:
        return stat.S_ISFIFO(os.stat(path).st_mode)
    except OSError:
        return False


def _detect_snap_pipe_dir(uid: int) -> str | None:
    """Find the pipe directory inside a sandboxed Audacity's mount namespace.

    Snap (and similar confinement) hides the real /tmp from the host, so the
    FIFOs Audacity creates only show up under /proc/<pid>/root/tmp. Only Linux
    has /proc, and we require both FIFOs to exist for the current uid before
    trusting a candidate — otherwise a confined Audacity with mod-script-pipe
    disabled would look identical to a wrong pid.
    """
    if not sys.platform.startswith("linux"):
        return None
    try:
        pids = [entry for entry in os.listdir("/proc") if entry.isdigit()]
    except OSError:
        return None
    for pid in pids:
        try:
            with open(f"/proc/{pid}/comm") as f:
                comm = f.read().strip()
        except OSError:
            continue
        if comm != "audacity":
            continue
        candidate_dir = f"/proc/{pid}/root/tmp"
        to_path = f"{candidate_dir}/audacity_script_pipe.to.{uid}"
        from_path = f"{candidate_dir}/audacity_script_pipe.from.{uid}"
        if _is_fifo(to_path) and _is_fifo(from_path):
            return candidate_dir
    return None


class PipePaths:
    if sys.platform == "win32":
        TO_SRV = r"\\.\pipe\ToSrvPipe"
        FROM_SRV = r"\\.\pipe\FromSrvPipe"
    else:
        _uid = os.getuid()

        @staticmethod
        def resolve() -> tuple[str, str]:
            """Return (to_srv, from_srv) paths, re-detected on every call.

            Re-resolving per connection (rather than once at import) matters
            because the MCP server typically starts before Audacity, so any
            pid-based path found at import time would be stale for the rest
            of the session — and an Audacity restart changes the pid anyway.
            """
            uid = PipePaths._uid
            override = os.environ.get("AUDACITY_PIPE_DIR")
            if override:
                return (
                    f"{override}/audacity_script_pipe.to.{uid}",
                    f"{override}/audacity_script_pipe.from.{uid}",
                )

            default_to = f"/tmp/audacity_script_pipe.to.{uid}"
            default_from = f"/tmp/audacity_script_pipe.from.{uid}"
            if _is_fifo(default_to) and _is_fifo(default_from):
                return default_to, default_from

            snap_dir = _detect_snap_pipe_dir(uid)
            if snap_dir:
                return (
                    f"{snap_dir}/audacity_script_pipe.to.{uid}",
                    f"{snap_dir}/audacity_script_pipe.from.{uid}",
                )

            return default_to, default_from


class Timeouts:
    PIPE_OPEN = 5.0
    PIPE_READ = 10.0
    PIPE_WRITE = 5.0
    COMMAND = 30.0
    LONG_COMMAND = 600.0  # 10 minutes — large files (2-3hr podcasts) need this


ALLOWED_EXPORT_FORMATS = {"wav", "mp3", "ogg", "flac", "aiff", "mp4"}

ALLOWED_SAMPLE_RATES = {8000, 11025, 16000, 22050, 32000, 44100, 48000, 88200, 96000}

MAX_TRACKS = 500
MAX_LABEL_LENGTH = 1000

WHISPER_MODEL_SIZES = {"tiny", "base", "small", "medium", "large-v3"}
TRANSCRIPTION_TASKS = {"transcribe", "translate"}
SUBTITLE_FORMATS = {"srt", "vtt", "txt"}
