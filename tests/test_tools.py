import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from mcp.server.fastmcp import FastMCP
from shared.error_codes import AudacityMCPError, ErrorCode


class TestToolRegistration:
    def test_all_tools_register(self):
        mcp = FastMCP("TestAudacityMCP")
        mock_client = MagicMock()
        mock_client.execute = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
        mock_client.execute_long = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})

        with patch("server.main.client", mock_client):
            from server.tool_registry import register_all_tools
            register_all_tools(mcp)

        # Access internal tool manager directly to avoid async list_tools
        tool_count = len(mcp._tool_manager._tools)
        assert tool_count >= 99, f"Expected at least 99 tools, got {tool_count}"


class TestValidation:
    def test_format_command_injection(self):
        from shared.pipe_protocol import format_command
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
