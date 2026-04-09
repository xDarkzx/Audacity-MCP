import asyncio
import logging
import os
import sys
import tempfile
import time
import uuid
from mcp.server.fastmcp import FastMCP
from audacity_mcp_shared.error_codes import AudacityMCPError, ErrorCode
from audacity_mcp_shared.constants import WHISPER_MODEL_SIZES, TRANSCRIPTION_TASKS, SUBTITLE_FORMATS

_log = logging.getLogger("audacity_mcp.transcription")

_model_instance = None
_model_size_loaded = None
_model_lock = __import__("threading").Lock()

# Background jobs for transcription
_jobs: dict[str, dict] = {}
_MAX_COMPLETED_JOBS = 50
_STALE_JOB_TIMEOUT = 600  # 10 minutes

# Lock to prevent race condition in job creation
_job_lock = asyncio.Lock()


def _get_cache_dir() -> str:
    """Get a reliable cache directory for whisper models.
    MCP subprocesses on Windows sometimes can't resolve the default huggingface cache."""
    cache = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")
    os.makedirs(cache, exist_ok=True)
    return cache


def _check_whisper_installed() -> None:
    """Check that faster-whisper is installed. Gives a clean error if not."""
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        raise AudacityMCPError(
            ErrorCode.VALIDATION_FAILED,
            "Transcription requires 'faster-whisper'. Install it with: pip install faster-whisper  "
            "See the Transcription Setup section in the installation guide for details.",
        )


def _validate_model_size(model_size: str) -> None:
    if model_size not in WHISPER_MODEL_SIZES:
        raise AudacityMCPError(
            ErrorCode.INVALID_PARAMETER,
            f"Invalid model size '{model_size}'. Must be one of: {', '.join(sorted(WHISPER_MODEL_SIZES))}",
        )


def _validate_task(task: str) -> None:
    if task not in TRANSCRIPTION_TASKS:
        raise AudacityMCPError(
            ErrorCode.INVALID_PARAMETER,
            f"Invalid task '{task}'. Must be one of: {', '.join(sorted(TRANSCRIPTION_TASKS))}",
        )


def _setup_cuda_path():
    """Add NVIDIA pip package DLL paths to system PATH so faster-whisper can find them."""
    try:
        import nvidia.cublas
        if nvidia.cublas.__file__:
            cublas_bin = os.path.join(os.path.dirname(nvidia.cublas.__file__), "bin")
            if cublas_bin not in os.environ.get("PATH", ""):
                os.environ["PATH"] = cublas_bin + os.pathsep + os.environ.get("PATH", "")
    except (ImportError, AttributeError, OSError):
        pass
    try:
        import nvidia.cudnn
        if nvidia.cudnn.__file__:
            cudnn_bin = os.path.join(os.path.dirname(nvidia.cudnn.__file__), "bin")
            if cudnn_bin not in os.environ.get("PATH", ""):
                os.environ["PATH"] = cudnn_bin + os.pathsep + os.environ.get("PATH", "")
    except (ImportError, AttributeError, OSError):
        pass


def _cuda_is_available() -> bool:
    """Check if CUDA is actually usable — not just installed but functional."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        pass
    # Fallback: try loading CUDA library directly
    try:
        import ctypes
        if sys.platform == "win32":
            ctypes.cdll.LoadLibrary("cublas64_12.dll")
        elif sys.platform == "darwin":
            return False  # macOS has no CUDA support
        else:
            ctypes.cdll.LoadLibrary("libcublas.so")
        return True
    except OSError:
        return False


def _get_model(model_size: str):
    global _model_instance, _model_size_loaded
    # Fast path — no lock needed for read-only check
    if _model_instance is not None and _model_size_loaded == model_size:
        return _model_instance
    with _model_lock:
        # Re-check after acquiring lock (another thread may have loaded it)
        if _model_instance is not None and _model_size_loaded == model_size:
            return _model_instance
        # Free previous model to release GPU/CPU memory before loading new one
        if _model_instance is not None:
            del _model_instance
            _model_instance = None
            _model_size_loaded = None
            import gc
            gc.collect()
        _setup_cuda_path()
        from faster_whisper import WhisperModel
        cache_dir = _get_cache_dir()
        use_gpu = _cuda_is_available()
        if use_gpu:
            try:
                _log.info(f"Loading whisper model '{model_size}' on GPU...")
                _model_instance = WhisperModel(model_size, device="cuda", compute_type="float16",
                                                download_root=cache_dir)
                _log.info(f"Model '{model_size}' loaded on GPU")
            except Exception as e:
                _log.info(f"GPU failed ({e}), falling back to CPU...")
                use_gpu = False
        if not use_gpu:
            _log.info(f"Loading whisper model '{model_size}' on CPU...")
            _model_instance = WhisperModel(model_size, device="cpu", compute_type="int8",
                                            download_root=cache_dir)
            _log.info(f"Model '{model_size}' loaded on CPU")
        _model_size_loaded = model_size
    return _model_instance


def _run_transcription(temp_path: str, model_size: str, language: str | None, task: str):
    model = _get_model(model_size)
    kwargs = {"task": task}
    if language:
        kwargs["language"] = language
    segments, info = model.transcribe(temp_path, **kwargs)
    results = []
    for seg in segments:
        results.append({"start": round(seg.start, 3), "end": round(seg.end, 3), "text": seg.text.strip()})
    return results, info


def _format_timestamp_srt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_timestamp_vtt(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds % 1) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _segments_to_srt(segments: list[dict]) -> str:
    lines = []
    for i, seg in enumerate(segments, 1):
        lines.append(str(i))
        lines.append(f"{_format_timestamp_srt(seg['start'])} --> {_format_timestamp_srt(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def _segments_to_vtt(segments: list[dict]) -> str:
    lines = ["WEBVTT", ""]
    for seg in segments:
        lines.append(f"{_format_timestamp_vtt(seg['start'])} --> {_format_timestamp_vtt(seg['end'])}")
        lines.append(seg["text"])
        lines.append("")
    return "\n".join(lines)


def _segments_to_txt(segments: list[dict]) -> str:
    return "\n".join(seg["text"] for seg in segments)


def register(mcp: FastMCP):
    from audacity_mcp.main import client

    @mcp.tool()
    async def get_default_transcription_folder() -> dict:
        """Get the default folder for saving transcription files.
        Returns the user's Documents folder. Call this when the user doesn't specify where to save."""
        docs = os.path.join(os.path.expanduser("~"), "Documents")
        os.makedirs(docs, exist_ok=True)
        return {"path": docs}

    @mcp.tool()
    async def check_transcription_status(job_id: str) -> dict:
        """[EXPERIMENTAL] Check the status of a running transcription job.
        Call this after starting transcribe_audio, transcribe_to_labels, or transcribe_to_file.
        Poll every 10-15 seconds until status is 'complete' or 'error'.

        Args:
            job_id: The job ID returned when you started the transcription.
        """
        _cleanup_stale_jobs()
        job = _jobs.get(job_id)
        if not job:
            return {"error": f"No transcription job found with id '{job_id}'"}

        result = {
            "job_id": job_id,
            "status": job["status"],
            "current_step": job["current_step"],
            "steps_completed": job["steps_completed"],
            "elapsed_seconds": round(time.time() - job["started_at"], 1),
        }
        if job["status"] == "complete":
            result["result"] = job["result"]
        elif job["status"] == "error":
            result["error"] = job["error"]
        return result

    async def _transcribe_background(job: dict, model_size: str, language: str | None,
                                      task: str, select_all: bool, add_labels: bool,
                                      export_path: str | None, export_format: str | None):
        """Background transcription worker."""
        # Wait for FastMCP to send the response before doing any heavy work.
        # import faster_whisper and model loading block the event loop for seconds.
        await asyncio.sleep(1)
        temp_path = None
        loop = asyncio.get_running_loop()
        try:
            # Step 0: Check dependency (run import in thread to avoid blocking event loop)
            job["current_step"] = "checking faster-whisper installation"

            def _check_dep():
                import faster_whisper  # noqa: F401
                return True

            try:
                await loop.run_in_executor(None, _check_dep)
            except ImportError:
                job["status"] = "error"
                job["error"] = ("faster-whisper is not installed. "
                                "Run: pip install faster-whisper  "
                                "See Transcription Setup in the installation guide.")
                return
            job["steps_completed"].append("faster-whisper found")

            # Step 1: Export audio
            job["current_step"] = "exporting audio from Audacity"
            temp_path = os.path.join(tempfile.gettempdir(), f"audacity_mcp_transcribe_{uuid.uuid4().hex[:8]}.wav")

            if select_all:
                await client.execute("SelAllTracks")
                await client.execute("SelectAll")
            await client.execute_long("Export2", Filename=temp_path, NumChannels=1)

            if not os.path.exists(temp_path) or os.path.getsize(temp_path) < 100:
                job["status"] = "error"
                job["error"] = f"Audio export failed — WAV file not created or empty at {temp_path}"
                return

            file_size = os.path.getsize(temp_path)
            job["steps_completed"].append(f"exported audio ({round(file_size / 1024 / 1024, 1)} MB)")

            # Step 2: Load model (in thread — blocks for seconds)
            job["current_step"] = f"loading {model_size} model (first time downloads ~{_model_download_size(model_size)})"
            await loop.run_in_executor(None, _get_model, model_size)
            job["steps_completed"].append(f"model {model_size} loaded")

            # Step 3: Transcribe (in thread — blocks for 10-60+ seconds)
            job["current_step"] = "transcribing audio (this takes a while for long files)"
            segments, info = await loop.run_in_executor(
                None, _run_transcription, temp_path, model_size, language, task
            )
            job["steps_completed"].append(f"transcribed {len(segments)} segments")

            full_text = " ".join(seg["text"] for seg in segments)

            # Step 4: Optional — add labels to Audacity
            if add_labels:
                job["current_step"] = "adding labels to Audacity"
                for seg in segments:
                    await client.execute("SelectTime", Start=seg["start"], End=seg["end"])
                    await client.execute("AddLabel")
                    await client.execute("SetLabel", Label=0, Text=seg["text"])
                job["steps_completed"].append(f"added {len(segments)} labels")

            # Step 5: Optional — export to file
            if export_path and export_format:
                job["current_step"] = f"writing {export_format} file"
                formatters = {"srt": _segments_to_srt, "vtt": _segments_to_vtt, "txt": _segments_to_txt}
                content = formatters[export_format](segments)
                parent_dir = os.path.dirname(export_path)
                if parent_dir and not os.path.exists(parent_dir):
                    os.makedirs(parent_dir, exist_ok=True)
                with open(export_path, "w", encoding="utf-8") as f:
                    f.write(content)
                job["steps_completed"].append(f"saved {export_format} to {export_path}")

            # Done
            job["status"] = "complete"
            job["current_step"] = "done"
            job["result"] = {
                "success": True,
                "language": info.language,
                "language_probability": round(info.language_probability, 3),
                "duration": round(info.duration, 3),
                "segment_count": len(segments),
                "text": full_text,
                "segments": segments,
            }
            if add_labels:
                job["result"]["labels_added"] = len(segments)
            if export_path:
                job["result"]["export_path"] = export_path
                job["result"]["export_format"] = export_format

        except Exception as e:
            job["status"] = "error"
            job["current_step"] = "failed"
            job["error"] = f"{type(e).__name__}: {e}"
        finally:
            if temp_path:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _model_download_size(model_size: str) -> str:
        sizes = {"tiny": "75MB", "base": "145MB", "small": "488MB", "medium": "1.5GB", "large-v3": "3GB"}
        return sizes.get(model_size, "unknown")

    def _has_running_transcription() -> bool:
        return any(j["status"] == "running" for j in _jobs.values())

    def _has_running_pipeline() -> bool:
        try:
            from audacity_mcp.tools.cleanup_tools import _jobs as pipeline_jobs
            return any(j["status"] == "running" for j in pipeline_jobs.values())
        except ImportError:
            return False

    def _cleanup_stale_jobs():
        """Kill jobs running longer than timeout, evict oldest completed jobs."""
        now = time.time()
        for job_id, job in list(_jobs.items()):
            if job["status"] == "running" and (now - job["started_at"]) > _STALE_JOB_TIMEOUT:
                job["status"] = "error"
                job["error"] = "Timed out after 10 minutes — killed automatically"
                job["current_step"] = "timed out"
                task = job.get("_task")
                if task and not task.done():
                    task.cancel()

        completed = [(k, v) for k, v in _jobs.items() if v["status"] in ("complete", "error")]
        if len(completed) > _MAX_COMPLETED_JOBS:
            completed.sort(key=lambda x: x[1].get("started_at", 0))
            for k, _ in completed[:-_MAX_COMPLETED_JOBS]:
                del _jobs[k]

    async def _start_transcription(model_size: str, language: str | None, task: str,
                                    select_all: bool = True, add_labels: bool = False,
                                    export_path: str | None = None, export_format: str | None = None) -> dict:
        _log.info("_start_transcription called")
        async with _job_lock:
            _cleanup_stale_jobs()

            if _has_running_pipeline():
                _log.info("Blocked: a cleanup pipeline is running")
                return {
                    "error": "A cleanup pipeline is currently running. Wait for it to finish before transcribing.",
                    "message": "Use check_pipeline_status to monitor the existing pipeline.",
                }

            if _has_running_transcription():
                running = next(j for j in _jobs.values() if j["status"] == "running")
                running_id = next(k for k, v in _jobs.items() if v is running)
                _log.info(f"Already running: {running_id}")
                return {
                    "error": "A transcription is already running. Do NOT start another one.",
                    "job_id": running_id,
                    "current_step": running["current_step"],
                    "message": "Use check_transcription_status to monitor the existing job.",
                }

            job_id = str(uuid.uuid4())[:8]
            job = {
                "status": "running",
                "current_step": "starting",
                "steps_completed": [],
                "started_at": time.time(),
                "result": None,
                "error": None,
            }
            _jobs[job_id] = job

        coro = _transcribe_background(job, model_size, language, task,
                                       select_all, add_labels, export_path, export_format)
        job["_task"] = asyncio.create_task(coro)
        _log.info(f"Background task created, returning job_id={job_id}")
        return {
            "job_id": job_id,
            "status": "running",
            "message": f"Transcription started in background with {model_size} model. "
                       f"Use check_transcription_status('{job_id}') to monitor progress. "
                       "Poll every 10-15 seconds.",
        }

    @mcp.tool()
    async def transcribe_audio(
        model_size: str = "small",
        language: str | None = None,
        task: str = "transcribe",
    ) -> dict:
        """[EXPERIMENTAL] Transcribe the entire project audio using faster-whisper (local, offline).
        Requires separate setup — see installation guide. If this fails, tell the user
        transcription is experimental and point them to the Transcription Setup docs.

        Runs in BACKGROUND — returns a job_id immediately.
        Use check_transcription_status to monitor progress. Poll every 10-15 seconds.

        Do NOT call transcription_set_model first — this handles model loading automatically.

        After transcription completes, TELL the user where the transcript was saved
        or offer to save it. Always tell the user the file location so they can find it.

        Args:
            model_size: Whisper model - "tiny", "base", "small", "medium", "large-v3". Default: "small"
            language: ISO language code (e.g. "en", "fr") or None for auto-detect
            task: "transcribe" or "translate" (translate converts any language to English)
        """
        _validate_model_size(model_size)
        _validate_task(task)
        return await _start_transcription(model_size, language, task, select_all=True)

    @mcp.tool()
    async def transcribe_selection(
        model_size: str = "small",
        language: str | None = None,
        task: str = "transcribe",
    ) -> dict:
        """[EXPERIMENTAL] Transcribe only the currently selected audio region.
        Requires separate setup — see installation guide.

        Runs in BACKGROUND — returns a job_id immediately.
        Use check_transcription_status to monitor progress.

        Select a region first, then call this tool.

        Args:
            model_size: Whisper model - "tiny", "base", "small", "medium", "large-v3"
            language: ISO language code or None for auto-detect
            task: "transcribe" or "translate"
        """
        _validate_model_size(model_size)
        _validate_task(task)
        return await _start_transcription(model_size, language, task, select_all=False)

    @mcp.tool()
    async def transcribe_to_labels(
        model_size: str = "small",
        language: str | None = None,
    ) -> dict:
        """[EXPERIMENTAL] Transcribe audio and add Audacity labels at each segment timestamp.
        Requires separate setup — see installation guide.

        Runs in BACKGROUND — returns a job_id immediately.
        Use check_transcription_status to monitor progress.

        Args:
            model_size: Whisper model - "tiny", "base", "small", "medium", "large-v3"
            language: ISO language code or None for auto-detect
        """
        _validate_model_size(model_size)
        return await _start_transcription(model_size, language, "transcribe",
                                     select_all=True, add_labels=True)

    @mcp.tool()
    async def transcribe_to_file(
        path: str,
        format: str = "srt",
        model_size: str = "small",
        language: str | None = None,
    ) -> dict:
        """[EXPERIMENTAL] Transcribe audio and export to a subtitle or text file.
        Requires separate setup — see installation guide.

        ALWAYS tell the user where the file will be saved BEFORE starting.
        If user doesn't specify a path, call get_default_export_folder to get a real path.
        NEVER guess paths like /home/user/... — always use absolute Windows paths like C:\\Users\\Name\\Documents\\transcript.srt

        Runs in BACKGROUND — returns a job_id immediately.
        Use check_transcription_status to monitor progress.

        Args:
            path: Absolute path for the output file (e.g. "C:/Users/You/Documents/transcript.srt")
            format: Output format - "srt", "vtt", or "txt"
            model_size: Whisper model - "tiny", "base", "small", "medium", "large-v3"
            language: ISO language code or None for auto-detect
        """
        from audacity_mcp.tools.project_tools import _safe_path
        path = _safe_path(path)
        if os.path.exists(path):
            raise AudacityMCPError(
                ErrorCode.INVALID_PATH,
                f"File already exists: {path}. Use a different filename to avoid overwriting.",
            )
        if format not in SUBTITLE_FORMATS:
            raise AudacityMCPError(
                ErrorCode.INVALID_FORMAT,
                f"Invalid format '{format}'. Must be one of: {', '.join(sorted(SUBTITLE_FORMATS))}",
            )
        _validate_model_size(model_size)
        return await _start_transcription(model_size, language, "transcribe",
                                     select_all=True, export_path=path, export_format=format)

    @mcp.tool()
    async def transcription_set_model(model_size: str = "base") -> dict:
        """[EXPERIMENTAL] Pre-download a whisper model. ONLY call this if the user explicitly asks
        to download or change the model. Do NOT call this before transcribe_audio —
        transcription tools handle model loading automatically.
        Requires separate setup — see installation guide.

        Runs in BACKGROUND — returns a job_id immediately.
        Use check_transcription_status to monitor progress.

        Model sizes:
        - tiny: ~75MB (fastest, least accurate)
        - base: ~150MB (good balance for most use cases)
        - small: ~500MB (better accuracy, recommended)
        - medium: ~1.5GB (high accuracy)
        - large-v3: ~3GB (best accuracy, slowest)

        Args:
            model_size: Model to load - "tiny", "base", "small", "medium", "large-v3"
        """
        _validate_model_size(model_size)
        async with _job_lock:
            _cleanup_stale_jobs()
            job_id = str(uuid.uuid4())[:8]
            job = {
                "status": "running",
                "current_step": f"downloading and loading {model_size} model (~{_model_download_size(model_size)})",
                "steps_completed": [],
                "started_at": time.time(),
                "result": None,
                "error": None,
            }
            _jobs[job_id] = job

        async def _load():
            await asyncio.sleep(0.5)  # yield so FastMCP can send response first
            try:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, _get_model, model_size)
                job["status"] = "complete"
                job["current_step"] = "done"
                job["steps_completed"].append(f"model {model_size} loaded")
                job["result"] = {
                    "success": True,
                    "model_size": model_size,
                    "message": f"Model '{model_size}' loaded and ready for transcription",
                }
            except Exception as e:
                job["status"] = "error"
                job["error"] = f"{type(e).__name__}: {e}"

        job["_task"] = asyncio.create_task(_load())
        return {
            "job_id": job_id,
            "status": "running",
            "message": f"Downloading {model_size} model (~{_model_download_size(model_size)}). "
                       f"Use check_transcription_status('{job_id}') to monitor. "
                       "Poll every 10-15 seconds.",
        }
