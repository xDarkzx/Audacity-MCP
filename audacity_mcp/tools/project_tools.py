import os
from mcp.server.fastmcp import FastMCP
from audacity_mcp_shared.constants import ALLOWED_EXPORT_FORMATS
from audacity_mcp_shared.error_codes import AudacityMCPError, ErrorCode


_BLOCKED_DIRS = None


def _get_blocked_dirs():
    """Directories that should never be written to."""
    global _BLOCKED_DIRS
    if _BLOCKED_DIRS is None:
        _BLOCKED_DIRS = set()
        if os.name == "nt":
            win_dir = os.environ.get("WINDIR", r"C:\Windows")
            _BLOCKED_DIRS.add(os.path.realpath(win_dir).lower())
            prog = os.environ.get("PROGRAMFILES", r"C:\Program Files")
            _BLOCKED_DIRS.add(os.path.realpath(prog).lower())
            prog86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
            _BLOCKED_DIRS.add(os.path.realpath(prog86).lower())
    return _BLOCKED_DIRS


def _safe_path(path: str) -> str:
    """Validate and canonicalize a file path. Returns the resolved absolute path."""
    if not os.path.isabs(path):
        raise AudacityMCPError(ErrorCode.INVALID_PATH, "Path must be absolute")
    resolved = os.path.realpath(path)
    # Block system directories
    for blocked in _get_blocked_dirs():
        if resolved.lower().startswith(blocked + os.sep) or resolved.lower() == blocked:
            raise AudacityMCPError(
                ErrorCode.INVALID_PATH,
                f"Cannot access system directory: {blocked}",
            )
    return resolved


def register(mcp: FastMCP):
    from audacity_mcp.main import client

    @mcp.tool()
    async def project_new() -> dict:
        """Create a new empty Audacity project."""
        return await client.execute("New")

    @mcp.tool()
    async def project_open(path: str) -> dict:
        """Open an existing Audacity project file (.aup3).

        Args:
            path: Absolute path to the .aup3 project file
        """
        path = _safe_path(path)
        return await client.execute("OpenProject2", Filename=path)

    @mcp.tool()
    async def project_save() -> dict:
        """Save the current Audacity project. ONLY call this when the user explicitly asks to save.
        Do NOT auto-save after effects or pipelines — the user controls when to save."""
        return await client.execute("SaveProject2")

    @mcp.tool()
    async def project_save_as(path: str) -> dict:
        """Save the current project to a new .aup3 file. ONLY call when user explicitly asks.
        Do NOT auto-save after effects or pipelines.

        Args:
            path: Absolute path for the new .aup3 file
        """
        path = _safe_path(path)
        return await client.execute("SaveProject2", Filename=path)

    @mcp.tool()
    async def project_close() -> dict:
        """Close the current Audacity project."""
        return await client.execute("Close")

    @mcp.tool()
    async def project_import_audio(path: str) -> dict:
        """Import an audio file into the current project. Creates a new track.

        Args:
            path: Absolute path to the audio file (wav, mp3, ogg, flac, etc.)
        """
        path = _safe_path(path)
        return await client.execute("Import2", Filename=path)

    def _default_music_folder() -> str:
        """Get the user's Music folder, works on any system."""
        home = os.path.expanduser("~")
        music = os.path.join(home, "Music")
        if not os.path.exists(music):
            os.makedirs(music, exist_ok=True)
        return music

    @mcp.tool()
    async def get_default_export_folder() -> dict:
        """Get the default folder for exporting audio files.
        Returns the user's Music folder path. Use this when the user doesn't specify where to save."""
        return {"path": _default_music_folder()}

    @mcp.tool()
    async def project_export_audio(path: str, num_channels: int = 2) -> dict:
        """Export the project audio to a file. Format is determined by file extension.

        MANDATORY: ALWAYS tell the user where the file will be saved BEFORE exporting.
        Example: "I'll save your audio to C:\\Users\\Name\\Music\\file.mp3"

        NEVER save directly to the user's home folder (e.g. C:\\Users\\Name\\file.mp3).
        ALWAYS save to a subfolder. If the user doesn't specify a path, call get_default_export_folder
        to get their Music folder and save there. Acceptable locations:
        - Music folder: C:\\Users\\Name\\Music\\file.mp3
        - Documents folder: C:\\Users\\Name\\Documents\\file.mp3
        - Desktop: C:\\Users\\Name\\Desktop\\file.mp3
        NEVER save to C:\\Users\\Name\\file.mp3 — this clutters the user's home directory.

        Args:
            path: Absolute path for exported file. Extension determines format (wav, mp3, ogg, flac, aiff).
            num_channels: Number of channels (1=mono, 2=stereo). Default: 2
        """
        path = _safe_path(path)
        # Block saving directly to user home folder
        home = os.path.realpath(os.path.expanduser("~"))
        parent = os.path.dirname(path)
        if os.path.realpath(parent) == home:
            raise AudacityMCPError(
                ErrorCode.INVALID_PATH,
                f"Do not save directly to the home folder. Use a subfolder like Music or Documents. "
                f"Call get_default_export_folder to get the correct path."
            )
        ext = os.path.splitext(path)[1].lstrip(".").lower()
        if ext not in ALLOWED_EXPORT_FORMATS:
            raise AudacityMCPError(
                ErrorCode.INVALID_FORMAT,
                f"Unsupported format: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXPORT_FORMATS))}",
            )
        if os.path.exists(path):
            raise AudacityMCPError(
                ErrorCode.INVALID_PATH,
                f"File already exists: {path}. Use a different filename to avoid overwriting.",
            )
        # Create output directory if it doesn't exist
        parent_dir = os.path.dirname(path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
        return await client.execute_long("Export2", Filename=path, NumChannels=num_channels)

    @mcp.tool()
    async def project_export_labels(path: str) -> dict:
        """Export all labels to a text file.

        Args:
            path: Absolute path for the exported labels file
        """
        path = _safe_path(path)
        if os.path.exists(path):
            raise AudacityMCPError(
                ErrorCode.INVALID_PATH,
                f"File already exists: {path}. Use a different filename to avoid overwriting.",
            )
        return await client.execute("ExportLabels", Filename=path)

    @mcp.tool()
    async def project_get_info(info_type: str = "Tracks") -> dict:
        """Get information about the current project.

        Args:
            info_type: Type of info to retrieve. One of: Tracks, Clips, Envelopes, Labels, Boxes, Commands
        """
        allowed = {"Tracks", "Clips", "Envelopes", "Labels", "Boxes", "Commands"}
        if info_type not in allowed:
            raise AudacityMCPError(
                ErrorCode.INVALID_PARAMETER,
                f"Invalid info_type: {info_type}. Allowed: {', '.join(sorted(allowed))}",
            )
        return await client.execute("GetInfo", Type=info_type)

    @mcp.tool()
    async def project_edit_metadata() -> dict:
        """Open the metadata editor dialog to view/edit track metadata (title, artist, etc.).
        This opens a modal dialog in Audacity — the command waits until the user closes it."""
        return await client.execute_long("EditMetaData")

    @mcp.tool()
    async def project_import_midi(path: str) -> dict:
        """Import a MIDI file into the current project.

        Args:
            path: Absolute path to the MIDI file (.mid, .midi)
        """
        path = _safe_path(path)
        return await client.execute("ImportMIDI", Filename=path)
