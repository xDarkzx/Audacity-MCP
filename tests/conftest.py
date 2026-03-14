import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.execute = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
    client.execute_long = AsyncMock(return_value={"success": True, "raw": "", "message": "", "data": {}})
    return client
