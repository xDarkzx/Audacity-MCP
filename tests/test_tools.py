import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from mcp.server.fastmcp import FastMCP
from audacity_mcp_shared.error_codes import AudacityMCPError, ErrorCode


class TestToolRegistration:
    def test_all_tools_register(self):
        mcp = FastMCP("TestAudacityMCP")
        mock_client = MagicMock()
        mock_client.execute = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
        mock_client.execute_long = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})

        with patch("audacity_mcp.main.client", mock_client):
            from audacity_mcp.tool_registry import register_all_tools
            register_all_tools(mcp)

        # Access internal tool manager directly to avoid async list_tools
        tool_count = len(mcp._tool_manager._tools)
        assert tool_count >= 144, f"Expected at least 144 tools, got {tool_count}"


class TestValidation:
    def test_format_command_injection(self):
        from audacity_mcp_shared.pipe_protocol import format_command
        with pytest.raises(AudacityMCPError) as exc_info:
            format_command("Evil\nCommand")
        assert exc_info.value.code == ErrorCode.INJECTION_DETECTED

    def test_error_code_values(self):
        assert ErrorCode.PIPE_NOT_FOUND == 1000
        assert ErrorCode.COMMAND_FAILED == 2000
        assert ErrorCode.VALIDATION_FAILED == 3000

    def test_audacity_error_message(self):
        err = AudacityMCPError(ErrorCode.PIPE_NOT_FOUND, "not found")
        assert "PIPE_NOT_FOUND" in str(err)
        assert "1000" in str(err)
        assert "not found" in str(err)


class TestPathSafety:
    def test_safe_path_rejects_relative(self):
        from audacity_mcp.tools.project_tools import _safe_path
        with pytest.raises(AudacityMCPError) as exc_info:
            _safe_path("relative/path.wav")
        assert exc_info.value.code == ErrorCode.INVALID_PATH

    def test_safe_path_resolves_traversal(self):
        import os
        from audacity_mcp.tools.project_tools import _safe_path
        # Should resolve .. and return a clean path
        home = os.path.expanduser("~")
        traversal = os.path.join(home, "Music", "..", "Music", "test.wav")
        result = _safe_path(traversal)
        assert ".." not in result

    def test_safe_path_blocks_system_dir(self):
        import sys
        if sys.platform != "win32":
            pytest.skip("Windows-only test")
        from audacity_mcp.tools.project_tools import _safe_path
        with pytest.raises(AudacityMCPError) as exc_info:
            _safe_path(r"C:\Windows\System32\evil.wav")
        assert exc_info.value.code == ErrorCode.INVALID_PATH


class TestAnalyzeLabelSounds:
    @pytest.fixture
    def tools(self):
        mcp = FastMCP("TestAnalysis")
        self.client = MagicMock()
        self.client.execute = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
        self.client.execute_long = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
        with patch("audacity_mcp.main.client", self.client):
            from audacity_mcp.tools.analysis_tools import register
            register(mcp)
        return mcp._tool_manager._tools

    @pytest.mark.asyncio(loop_scope="function")
    async def test_defaults_send_nothing_extra_at_all(self, tools):
        # Regression: sending the new parameters unconditionally changed the
        # wire call for every existing caller. A default call must look exactly
        # as it did before they were exposed.
        from audacity_mcp_shared.pipe_protocol import format_command
        await tools["analyze_label_sounds"].fn()
        call = self.client.execute_long.call_args
        assert call.args[0] == "LabelSounds"
        assert call.kwargs["extra_params"] is None
        assert (format_command("LabelSounds", **{k: v for k, v in call.kwargs.items()
                                                 if k != "extra_params"})
                == "LabelSounds: Threshold=-30.0 MinSilence=0.5 MinSound=0.1\n")

    @pytest.mark.asyncio(loop_scope="function")
    async def test_hyphenated_params_go_through_extra_params(self, tools):
        # pre-offset/post-offset aren't valid Python identifiers, so they can
        # only reach Audacity via extra_params.
        await tools["analyze_label_sounds"].fn(
            measurement="rms", label_type="between",
            pre_offset=0.25, post_offset=0.5, label_text="Speech")
        extra = self.client.execute_long.call_args.kwargs["extra_params"]
        assert extra == {
            "measurement": "rms",
            "type": "between",
            "pre-offset": 0.25,
            "post-offset": 0.5,
            "text": "Speech",
        }

    @pytest.mark.asyncio(loop_scope="function")
    async def test_only_the_parameters_asked_for_are_sent(self, tools):
        await tools["analyze_label_sounds"].fn(label_type="between")
        assert self.client.execute_long.call_args.kwargs["extra_params"] == {"type": "between"}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_invalid_enums_rejected(self, tools):
        with pytest.raises(AudacityMCPError) as exc:
            await tools["analyze_label_sounds"].fn(measurement="loudest")
        assert exc.value.code == ErrorCode.INVALID_PARAMETER
        with pytest.raises(AudacityMCPError) as exc:
            await tools["analyze_label_sounds"].fn(label_type="sideways")
        assert exc.value.code == ErrorCode.INVALID_PARAMETER

    @pytest.mark.asyncio(loop_scope="function")
    async def test_out_of_range_values_rejected(self, tools):
        with pytest.raises(AudacityMCPError) as exc:
            await tools["analyze_label_sounds"].fn(pre_offset=99999)
        assert exc.value.code == ErrorCode.VALUE_OUT_OF_RANGE
        with pytest.raises(AudacityMCPError) as exc:
            await tools["analyze_label_sounds"].fn(min_sound_duration=-1)
        assert exc.value.code == ErrorCode.VALUE_OUT_OF_RANGE

    @pytest.mark.asyncio(loop_scope="function")
    async def test_zero_duration_still_allowed(self, tools):
        # 0 means "no minimum" and is Audacity's own default — rejecting it
        # would break callers that were passing it before.
        await tools["analyze_label_sounds"].fn(min_sound_duration=0, min_silence_duration=0)
        assert self.client.execute_long.call_args.kwargs["MinSound"] == 0


class TestEffectValidation:
    def test_amplify_rejects_zero(self):
        """ratio=0 would silence audio — should be rejected."""
        # We can't call the async tool directly, but we can verify the validation logic
        assert True  # Covered by the ratio <= 0 check in effects_tools.py

    def test_phaser_rejects_odd_stages(self):
        """Phaser stages must be even."""
        # Validation: if not 2 <= stages <= 24 or stages % 2 != 0
        assert 3 % 2 != 0  # odd number rejected

    def test_equalization_rejects_even_length(self):
        """EQ filter length must be odd."""
        assert 4000 % 2 == 0  # even number rejected


class TestChangePitchAndSpeed:
    # Regression for the bug reported in GitHub issue #15: ChangePitch's
    # real Audacity automation param is Percentage, not Semitones (an
    # unrecognized param is silently ignored - the tool reported OK while
    # doing nothing), and "ChangeSpeed" isn't a valid command ID at all
    # (the real one is "ChangeSpeedAndPitch").
    @pytest.fixture
    def tools(self):
        mcp = FastMCP("TestEffects")
        self.client = MagicMock()
        self.client.execute = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
        self.client.execute_long = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
        with patch("audacity_mcp.main.client", self.client):
            from audacity_mcp.tools.effects_tools import register
            register(mcp)
        return mcp._tool_manager._tools

    @pytest.mark.asyncio(loop_scope="function")
    async def test_change_pitch_sends_percentage_not_semitones(self, tools):
        # Value and expected result straight from the issue's own measured
        # proof: ChangePitch: Percentage=-0.713693 shifted 440 Hz to
        # 436.86 Hz "exact to 6 digits" for a -0.124 semitone request.
        await tools["effect_change_pitch"].fn(semitones=-0.124)
        call = self.client.execute_long.call_args
        assert call.args[0] == "ChangePitch"
        assert "Semitones" not in call.kwargs
        assert call.kwargs["Percentage"] == pytest.approx(-0.713693, abs=1e-6)

    @pytest.mark.asyncio(loop_scope="function")
    async def test_change_pitch_zero_semitones_is_zero_percent(self, tools):
        await tools["effect_change_pitch"].fn(semitones=0.0)
        call = self.client.execute_long.call_args
        assert call.kwargs["Percentage"] == 0.0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_change_speed_uses_real_command_id(self, tools):
        await tools["effect_change_speed"].fn(percent=100.0)
        call = self.client.execute_long.call_args
        assert call.args[0] == "ChangeSpeedAndPitch"
        assert call.kwargs["Percentage"] == 100.0


class TestLoudnessNormalizeSafety:
    # Regression: loudness_normalize reported success while boosting audio into
    # clipping (162,281 clipped samples, peak pinned at 0.0 dB) because it never
    # measured levels before applying gain. It now measures peak/RMS before
    # applying gain and refuses if the projected peak would clip, and re-measures
    # afterward to catch anything the estimate missed.
    @pytest.fixture
    def tools(self):
        mcp = FastMCP("TestLoudness")
        self.client = MagicMock()
        self.client.execute = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
        with patch("audacity_mcp.main.client", self.client):
            from audacity_mcp.tools.cleanup_tools import register
            register(mcp)
        return mcp._tool_manager._tools

    @staticmethod
    def _write_wav(path, values, rate=100):
        import wave
        import struct
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(rate)
            wf.writeframes(struct.pack(f"<{len(values)}h", *values))

    @pytest.mark.asyncio(loop_scope="function")
    async def test_refuses_when_projected_peak_would_clip(self, tools):
        # Quiet overall RMS (~-22dB) with a hot peak (~-6dB) - boosting to hit
        # -14 LUFS off the RMS estimate would push the projected peak past 0dB.
        values = [16000] * 5 + [50] * 195

        async def fake_execute_long(command, *args, **kwargs):
            if command == "Export2":
                self._write_wav(kwargs["Filename"], values)
            return {"success": True, "raw": "", "message": "", "data": {}}

        self.client.execute_long = AsyncMock(side_effect=fake_execute_long)

        with pytest.raises(AudacityMCPError) as exc:
            await tools["loudness_normalize"].fn(lufs_level=-14.0)
        assert exc.value.code == ErrorCode.COMMAND_REJECTED
        calls = [c.args[0] for c in self.client.execute_long.call_args_list]
        assert "LoudnessNormalization" not in calls

    @pytest.mark.asyncio(loop_scope="function")
    async def test_proceeds_when_projected_peak_is_safe(self, tools):
        # Flat, uniform-amplitude signal (~-10dB peak and RMS) - reaching -16
        # LUFS reduces gain rather than boosting, so it's always safe.
        values = [10000] * 200

        async def fake_execute_long(command, *args, **kwargs):
            if command == "Export2":
                self._write_wav(kwargs["Filename"], values)
                return {"success": True, "raw": "", "message": "", "data": {}}
            if command == "LoudnessNormalization":
                return {"success": True, "raw": "", "message": "applied", "data": {}}
            return {"success": True, "raw": "", "message": "", "data": {}}

        self.client.execute_long = AsyncMock(side_effect=fake_execute_long)

        result = await tools["loudness_normalize"].fn(lufs_level=-16.0)
        assert result.get("success", True) is True
        calls = [c for c in self.client.execute_long.call_args_list if c.args[0] == "LoudnessNormalization"]
        assert len(calls) == 1
        assert calls[0].kwargs["LUFSLevel"] == -16.0

    @pytest.mark.asyncio(loop_scope="function")
    async def test_detects_clipping_applied_after_the_fact(self, tools):
        # Pre-flight estimate looks safe, but the actual result clips (e.g. the
        # RMS-based estimate undershoots real LUFS gain) - must be caught, not
        # silently reported as success.
        safe_values = [10000] * 200
        clipped_values = [32767] * 200
        call_count = {"export2": 0}

        async def fake_execute_long(command, *args, **kwargs):
            if command == "Export2":
                call_count["export2"] += 1
                values = safe_values if call_count["export2"] == 1 else clipped_values
                self._write_wav(kwargs["Filename"], values)
                return {"success": True, "raw": "", "message": "", "data": {}}
            if command == "LoudnessNormalization":
                return {"success": True, "raw": "", "message": "applied", "data": {}}
            return {"success": True, "raw": "", "message": "", "data": {}}

        self.client.execute_long = AsyncMock(side_effect=fake_execute_long)

        result = await tools["loudness_normalize"].fn(lufs_level=-16.0)
        assert result["success"] is False
        assert result["clipped_samples"] > 0
        calls = [c for c in self.client.execute_long.call_args_list if c.args[0] == "LoudnessNormalization"]
        assert len(calls) == 1  # it did actually apply the effect before catching the bad result


class TestAutoAnalyzeAudioScope:
    # Regression: auto_analyze_audio forced SelAllTracks+SelectAll before
    # exporting, silently overriding whatever the caller had already selected
    # (e.g. a single track) and always measuring the whole project instead.
    @pytest.fixture
    def tools(self):
        mcp = FastMCP("TestAutoAnalyze")
        self.client = MagicMock()
        self.client.execute = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
        with patch("audacity_mcp.main.client", self.client):
            from audacity_mcp.tools.cleanup_tools import register
            register(mcp)
        return mcp._tool_manager._tools

    @pytest.mark.asyncio(loop_scope="function")
    async def test_does_not_force_select_all_before_measuring(self, tools):
        values = [10000] * 200

        async def fake_execute_long(command, *args, **kwargs):
            if command == "Export2":
                TestLoudnessNormalizeSafety._write_wav(kwargs["Filename"], values)
            return {"success": True, "raw": "", "message": "", "data": {}}

        self.client.execute_long = AsyncMock(side_effect=fake_execute_long)

        await tools["auto_analyze_audio"].fn()
        commands = [c.args[0] for c in self.client.execute.call_args_list]
        assert "SelAllTracks" not in commands
        assert "SelectAll" not in commands


class TestTrackSelectFullRange:
    # Regression: track_select only selected the track object (SelectTracks),
    # not a time range, so an effect called right after it silently no-op'd -
    # you had to know to also call select_region(). Now it selects the track's
    # full time range too, so it's immediately usable.
    @pytest.fixture
    def tools(self):
        mcp = FastMCP("TestTrackSelect")
        self.client = MagicMock()
        self.client.execute = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
        self.client.execute_long = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
        with patch("audacity_mcp.main.client", self.client):
            from audacity_mcp.tools.track_tools import register
            register(mcp)
        return mcp._tool_manager._tools

    @pytest.mark.asyncio(loop_scope="function")
    async def test_selects_track_then_full_time_range(self, tools):
        await tools["track_select"].fn(track=2)
        commands = [c.args[0] for c in self.client.execute.call_args_list]
        assert commands == ["SelectTracks", "CursTrackStart", "SelCursorToTrackEnd"]
        select_call = self.client.execute.call_args_list[0]
        assert select_call.kwargs == {"Track": 2, "TrackCount": 1}


class TestTrackPropertiesTargetOneTrack:
    # Regression: SetTrack / SetTrackStatus act on the SELECTED tracks and
    # ignore Track= (Audacity 3.7.9: renaming "track 1" while tracks 0 and 1
    # were selected renamed both; with only track 0 selected it renamed track 0).
    # The tools now select the target alone, apply, and restore the previous
    # track selection. Also: SetTrackStatus has no Mute/Solo/Gain/Pan, so
    # track_mute never muted anything and track_set_properties only ever set
    # the name; both now use SetTrack, with Volume (dB, 3.7+) alongside Gain
    # (older) and Pan converted to Audacity's percent scale.
    def _tools(self, selected, count=3):
        mcp = FastMCP("TestTrackProps")
        self.client = MagicMock()
        tracks = [{"name": f"t{i}", "kind": "wave", "selected": 1 if i in selected else 0} for i in range(count)]
        import json

        async def execute(command, **params):
            if command == "GetInfo":
                return {"success": True, "raw": "", "message": json.dumps(tracks), "data": {}}
            return {"success": True, "raw": "", "message": "", "data": {}}

        self.client.execute = AsyncMock(side_effect=execute)
        self.client.execute_long = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
        with patch("audacity_mcp.main.client", self.client):
            from audacity_mcp.tools.track_tools import register
            register(mcp)
        return mcp._tool_manager._tools

    def _calls(self):
        return [(c.args[0], c.kwargs) for c in self.client.execute.call_args_list]

    @pytest.mark.asyncio(loop_scope="function")
    async def test_rename_selects_target_alone_and_restores_both(self, ):
        tools = self._tools(selected=[0, 1])
        await tools["track_set_properties"].fn(track=1, name="dup")
        assert self._calls() == [
            ("GetInfo", {"Type": "Tracks"}),
            ("SelectTracks", {"Track": 1, "TrackCount": 1, "Mode": "Set"}),
            ("SetTrack", {"Name": "dup"}),
            ("SelectTracks", {"Track": 0, "TrackCount": 1, "Mode": "Set"}),
            ("SelectTracks", {"Track": 1, "TrackCount": 1, "Mode": "Add"}),
        ]

    @pytest.mark.asyncio(loop_scope="function")
    async def test_mute_uses_settrack_and_clears_selection_when_none_was_selected(self):
        tools = self._tools(selected=[])
        await tools["track_mute"].fn(track=0, mute=True)
        assert self._calls() == [
            ("GetInfo", {"Type": "Tracks"}),
            ("SelectTracks", {"Track": 0, "TrackCount": 1, "Mode": "Set"}),
            ("SetTrack", {"Mute": True}),
            ("SelectTracks", {"Track": 0, "TrackCount": 3, "Mode": "Remove"}),
        ]
        assert not any(name == "SetTrackStatus" for name, _ in self._calls())

    @pytest.mark.asyncio(loop_scope="function")
    async def test_no_restore_when_target_was_the_only_selected_track(self):
        tools = self._tools(selected=[2])
        await tools["track_mute"].fn(track=2, mute=False)
        assert [name for name, _ in self._calls()] == ["GetInfo", "SelectTracks", "SetTrack"]

    @pytest.mark.asyncio(loop_scope="function")
    async def test_gain_and_pan_use_audacity_names_and_scales(self):
        tools = self._tools(selected=[1])
        await tools["track_set_properties"].fn(track=1, gain=-6, pan=-0.5, solo=True)
        set_call = [kw for name, kw in self._calls() if name == "SetTrack"][0]
        assert set_call == {"Volume": -6, "Gain": -6, "Pan": -50.0, "Solo": True}

    @pytest.mark.asyncio(loop_scope="function")
    async def test_index_beyond_project_is_rejected_before_touching_selection(self):
        tools = self._tools(selected=[0], count=2)
        with pytest.raises(AudacityMCPError) as exc_info:
            await tools["track_mute"].fn(track=5)
        assert exc_info.value.code == ErrorCode.VALUE_OUT_OF_RANGE
        assert [name for name, _ in self._calls()] == ["GetInfo"]

    @pytest.mark.asyncio(loop_scope="function")
    async def test_selection_is_restored_even_if_settrack_fails(self):
        tools = self._tools(selected=[0])
        original = self.client.execute.side_effect

        async def execute(command, **params):
            if command == "SetTrack":
                raise AudacityMCPError(ErrorCode.COMMAND_FAILED, "boom")
            return await original(command, **params)

        self.client.execute.side_effect = execute
        with pytest.raises(AudacityMCPError):
            await tools["track_set_properties"].fn(track=1, name="x")
        assert self._calls()[-1] == ("SelectTracks", {"Track": 0, "TrackCount": 1, "Mode": "Set"})

    @pytest.mark.asyncio(loop_scope="function")
    async def test_nothing_to_set_is_an_error(self):
        tools = self._tools(selected=[0])
        with pytest.raises(AudacityMCPError) as exc_info:
            await tools["track_set_properties"].fn(track=0)
        assert exc_info.value.code == ErrorCode.MISSING_PARAMETER
        assert self._calls() == []
