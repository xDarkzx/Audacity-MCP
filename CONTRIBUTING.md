# Contributing to AudacityMCP

Thanks for your interest in contributing! Here's how to get started.

## Development Setup

```bash
git clone https://github.com/xDarkzx/Audacity-MCP.git
cd AudacityMCP
pip install -e ".[dev]"
```

## Running Tests

```bash
pytest tests/ -x -q
```

All tests must pass before submitting a PR.

## Adding a New Tool

1. Choose the appropriate module in `server/tools/` (or create a new one)
2. Add your tool inside the `register(mcp)` function using the `@mcp.tool()` decorator
3. Validate all inputs — use `AudacityMCPError` with appropriate error codes
4. Use `client.execute()` for fast commands or `client.execute_long()` for effects that process audio
5. Add tests in `tests/`

Example:

```python
@mcp.tool()
async def my_tool(param: float = 1.0) -> dict:
    """Short description of what this tool does.

    Args:
        param: What this parameter controls. Default: 1.0
    """
    if param < 0:
        raise AudacityMCPError(ErrorCode.VALUE_OUT_OF_RANGE, "param must be >= 0")
    return await client.execute_long("AudacityCommand", Param=param)
```

## Code Style

- Python 3.10+
- Type hints on public functions
- No unnecessary comments or docstrings on obvious code
- Keep it simple — don't over-engineer
- No `exec`/`eval` — every operation maps to a static handler

## Security

- Validate all parameters before sending to Audacity
- Block injection characters (`\n`, `\r`, `\x00`) in string inputs
- Validate file paths are absolute
- Range-check all numeric inputs

## Pull Requests

- Keep PRs focused on a single change
- Include tests for new tools
- Make sure all existing tests still pass
- Describe what your change does and why

## Reporting Issues

Open an issue on GitHub with:
- What you expected to happen
- What actually happened
- Steps to reproduce
- Your OS and Audacity version
