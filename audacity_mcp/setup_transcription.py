"""Standalone GPU setup/verification helper for local transcription.

Run with `audacity-mcp-setup-gpu` (installed alongside the `audacity-mcp`
console script). Running it as a console script rather than a loose
`python script.py` matters: it guarantees the GPU packages get installed
into, and get tested against, the exact same Python environment that
`audacity-mcp` itself runs from - installing into the wrong environment
(a different venv or system Python) is the most common reason GPU setup
silently doesn't work.
"""
import subprocess
import sys


def _detect_nvidia_gpu() -> str | None:
    """Return the first GPU name from `nvidia-smi`, or None if unavailable.

    No NVIDIA GPU (AMD/Intel graphics, or Apple Silicon/macOS - NVIDIA hasn't
    shipped macOS drivers in years) means `nvidia-smi` simply won't exist,
    which this treats the same as "no GPU": CPU transcription, no error.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return None
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[0] if lines else None


def _install_gpu_packages() -> bool:
    print("Installing nvidia-cublas-cu12 and nvidia-cudnn-cu12...")
    print(f"  (into {sys.executable})")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "nvidia-cublas-cu12", "nvidia-cudnn-cu12"]
    )
    return result.returncode == 0


def _add_nvidia_dlls_to_path() -> None:
    """Mirror transcription_tools._setup_cuda_path so this verifies the exact
    runtime condition the MCP server will hit, not just that pip succeeded.

    Uses __path__, not __file__: nvidia-cublas-cu12/nvidia-cudnn-cu12 are PEP
    420 namespace packages with no __init__.py, so __file__ is None on
    current package versions - a package dir (__path__) always exists.
    """
    import os
    for pkg in ("cublas", "cudnn"):
        try:
            module = __import__(f"nvidia.{pkg}", fromlist=[pkg])
            pkg_dir = next(iter(module.__path__), None)
            if not pkg_dir:
                continue
            bin_dir = os.path.join(pkg_dir, "bin")
            if bin_dir not in os.environ.get("PATH", ""):
                os.environ["PATH"] = bin_dir + os.pathsep + os.environ.get("PATH", "")
        except (ImportError, AttributeError, OSError):
            pass


def _verify_gpu_transcription() -> tuple[bool, str]:
    _add_nvidia_dlls_to_path()
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return False, "faster-whisper isn't installed. Run: pip install faster-whisper"
    try:
        WhisperModel("tiny", device="cuda", compute_type="float16")
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
    return True, "GPU transcription is working."


def main() -> int:
    print()
    print(" ============================================")
    print("  AudacityMCP - Transcription GPU Setup")
    print(" ============================================")
    print()
    print("Checking for an NVIDIA GPU (nvidia-smi)...")
    gpu_name = _detect_nvidia_gpu()

    if gpu_name is None:
        print()
        print(" No NVIDIA GPU detected.")
        print()
        print(" Transcription will use the CPU. That's completely fine for short")
        print(" clips - just slower for long files (a 3-minute file: ~10s on GPU")
        print(" vs 4+ minutes on CPU). GPU acceleration ONLY works with NVIDIA GPUs")
        print(" (AMD/Intel graphics, and Macs, aren't supported by faster-whisper's")
        print(" backend at all - this isn't something a driver update fixes).")
        print()
        print(" If you DO have an NVIDIA GPU: make sure its driver is installed and")
        print(" that `nvidia-smi` runs successfully in this terminal, then re-run:")
        print("   audacity-mcp-setup-gpu")
        print()
        return 0

    print(f"  Found: {gpu_name}")
    print()

    if not _install_gpu_packages():
        print()
        print(" ERROR: pip install failed - see the error above.")
        print(" Try running this terminal as administrator, or check your internet connection.")
        print()
        return 1

    print()
    print("Verifying GPU transcription actually works...")
    ok, message = _verify_gpu_transcription()

    print()
    if ok:
        print(f" {message}")
        print()
        print(" Done! Restart Claude Desktop (if it's open) - transcription will now use your GPU.")
        return 0
    else:
        print(f" GPU load failed: {message}")
        print()
        print(" The packages installed, but faster-whisper couldn't use the GPU.")
        print(" Common causes: an outdated NVIDIA driver, or a GPU too old for the")
        print(" compute capability faster-whisper's CTranslate2 backend requires.")
        print(" AudacityMCP will keep working - it automatically falls back to CPU.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
