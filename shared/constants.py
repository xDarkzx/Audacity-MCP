import sys
from pathlib import Path


class PipePaths:
    if sys.platform == "win32":
        TO_SRV = r"\\.\pipe\ToSrvPipe"
        FROM_SRV = r"\\.\pipe\FromSrvPipe"
    else:
        TO_SRV = "/tmp/audacity_script_pipe.to.0"
        FROM_SRV = "/tmp/audacity_script_pipe.from.0"


class Timeouts:
    PIPE_OPEN = 5.0
    PIPE_READ = 10.0
    PIPE_WRITE = 5.0
    COMMAND = 30.0
    LONG_COMMAND = 600.0  # 10 minutes — large files (2-3hr podcasts) need this


ALLOWED_EXPORT_FORMATS = {"wav", "mp3", "ogg", "flac", "aiff", "mp4", "wma"}

ALLOWED_SAMPLE_RATES = {8000, 11025, 16000, 22050, 32000, 44100, 48000, 88200, 96000}

MAX_TRACKS = 500
MAX_LABEL_LENGTH = 1000

WHISPER_MODEL_SIZES = {"tiny", "base", "small", "medium", "large-v3"}
TRANSCRIPTION_TASKS = {"transcribe", "translate"}
SUBTITLE_FORMATS = {"srt", "vtt", "txt"}
