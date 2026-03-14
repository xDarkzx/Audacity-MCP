import pytest
from shared.pipe_protocol import format_command, parse_response
from shared.error_codes import AudacityMCPError, ErrorCode


class TestFormatCommand:
    def test_simple_command(self):
        assert format_command("Play") == "Play:\n"

    def test_command_with_params(self):
        result = format_command("SelectTime", Start=1.0, End=5.0)
        assert result.startswith("SelectTime:")
        assert "Start=1.0" in result
        assert "End=5.0" in result
        assert result.endswith("\n")

    def test_command_with_string_param(self):
        result = format_command("Import2", Filename="/path/to/file.wav")
        assert "Filename=/path/to/file.wav" in result

    def test_quoted_value_with_spaces(self):
        result = format_command("Tone", Waveform="Square (no alias)")
        assert 'Waveform="Square (no alias)"' in result

    def test_bool_param(self):
        result = format_command("Normalize", RemoveDcOffset=True)
        assert "RemoveDcOffset=1" in result

    def test_bool_param_false(self):
        result = format_command("Normalize", RemoveDcOffset=False)
        assert "RemoveDcOffset=0" in result

    def test_injection_newline(self):
        with pytest.raises(AudacityMCPError) as exc_info:
            format_command("Play\nEvil")
        assert exc_info.value.code == ErrorCode.INJECTION_DETECTED

    def test_injection_in_value(self):
        with pytest.raises(AudacityMCPError) as exc_info:
            format_command("Import2", Filename="file\n\rEvil")
        assert exc_info.value.code == ErrorCode.INJECTION_DETECTED

    def test_injection_null_byte(self):
        with pytest.raises(AudacityMCPError) as exc_info:
            format_command("Import2", Filename="file\x00evil")
        assert exc_info.value.code == ErrorCode.INJECTION_DETECTED


class TestParseResponse:
    def test_success_response(self):
        raw = "BatchCommand finished: OK\n"
        result = parse_response(raw)
        assert result["success"] is True

    def test_failure_response(self):
        raw = "BatchCommand finished: Failed!\n"
        result = parse_response(raw)
        assert result["success"] is False

    def test_data_response(self):
        raw = "Name=Track 1\nRate=44100\nBatchCommand finished: OK\n"
        result = parse_response(raw)
        assert result["success"] is True
        assert result["data"]["Name"] == "Track 1"
        assert result["data"]["Rate"] == "44100"

    def test_empty_response(self):
        result = parse_response("")
        assert result["success"] is False

    def test_message_response(self):
        raw = "Some info message\nBatchCommand finished: OK\n"
        result = parse_response(raw)
        assert result["success"] is True
        assert "Some info message" in result["message"]
