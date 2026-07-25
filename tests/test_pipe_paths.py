import sys
import pytest

IS_WIN = sys.platform == "win32"

pytestmark = pytest.mark.skipif(IS_WIN, reason="Pipe path auto-detection is POSIX-only")

from audacity_mcp_shared.constants import PipePaths, _detect_snap_pipe_dir, _is_fifo


class TestResolveOverride:
    def test_audacity_pipe_dir_override_wins(self, monkeypatch):
        monkeypatch.setenv("AUDACITY_PIPE_DIR", "/proc/1234/root/tmp")
        to_path, from_path = PipePaths.resolve()
        uid = PipePaths._uid
        assert to_path == f"/proc/1234/root/tmp/audacity_script_pipe.to.{uid}"
        assert from_path == f"/proc/1234/root/tmp/audacity_script_pipe.from.{uid}"

    def test_override_skips_snap_detection(self, monkeypatch):
        monkeypatch.setenv("AUDACITY_PIPE_DIR", "/custom/dir")
        monkeypatch.setattr(
            "audacity_mcp_shared.constants._detect_snap_pipe_dir",
            lambda uid: pytest.fail("should not be called when override is set"),
        )
        to_path, from_path = PipePaths.resolve()
        assert to_path.startswith("/custom/dir/")


class TestDetectSnapPipeDir:
    def test_finds_matching_audacity_process(self, monkeypatch):
        # _detect_snap_pipe_dir always constructs its candidate path as the
        # literal "/proc/{pid}/root/tmp" (that's the real path it needs to
        # check on an actual Linux box) — it never knows about pytest's
        # tmp_path fixture, so the fake here must match that literal string,
        # not a tmp_path-prefixed one. _is_fifo itself is fully mocked below,
        # so no real files need to exist on disk for this test.
        uid = 1000
        expected_dir = "/proc/555/root/tmp"

        real_listdir = __import__("os").listdir
        real_open = open

        def fake_listdir(path):
            if path == "/proc":
                return ["1", "555", "self"]
            return real_listdir(path)

        def fake_open(path, *a, **kw):
            if path == "/proc/555/comm":
                import io
                return io.StringIO("audacity\n")
            if path == "/proc/1/comm":
                import io
                return io.StringIO("systemd\n")
            return real_open(path, *a, **kw)

        def fake_is_fifo(path):
            expected_to = f"{expected_dir}/audacity_script_pipe.to.{uid}"
            expected_from = f"{expected_dir}/audacity_script_pipe.from.{uid}"
            return path in (expected_to, expected_from)

        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr("os.listdir", fake_listdir)
        monkeypatch.setattr("builtins.open", fake_open)
        monkeypatch.setattr("audacity_mcp_shared.constants._is_fifo", fake_is_fifo)

        result = _detect_snap_pipe_dir(uid)
        assert result == expected_dir

    def test_returns_none_when_pipes_missing_for_matching_process(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr("os.listdir", lambda path: ["555"])

        import io
        monkeypatch.setattr("builtins.open", lambda path, *a, **kw: io.StringIO("audacity\n"))
        monkeypatch.setattr("audacity_mcp_shared.constants._is_fifo", lambda path: False)

        assert _detect_snap_pipe_dir(1000) is None

    def test_skips_non_audacity_processes(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "linux")
        monkeypatch.setattr("os.listdir", lambda path: ["1"])

        import io
        monkeypatch.setattr("builtins.open", lambda path, *a, **kw: io.StringIO("systemd\n"))
        monkeypatch.setattr(
            "audacity_mcp_shared.constants._is_fifo",
            lambda path: pytest.fail("should not check fifos for a non-audacity process"),
        )

        assert _detect_snap_pipe_dir(1000) is None

    def test_returns_none_on_non_linux(self, monkeypatch):
        monkeypatch.setattr("sys.platform", "darwin")
        assert _detect_snap_pipe_dir(1000) is None


class TestIsFifo:
    def test_missing_path_is_not_fifo(self):
        assert _is_fifo("/nonexistent/path/should/not/exist") is False
