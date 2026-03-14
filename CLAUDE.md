# AudacityMCP - Claude Instructions

## Project
MCP server for AI-driven audio editing in Audacity via mod-script-pipe.

## Architecture
- `server/` - FastMCP server with named pipe client
- `server/tools/` - One module per tool category
- `shared/` - Wire protocol, constants, error codes
- `tests/` - pytest unit tests

## Key Rules
- ZERO exec/eval - every operation maps to a static handler with input validation
- Named pipe communication to Audacity (not TCP)
- Security-first: validate all parameters before sending to Audacity
- Follow same patterns as BlenderMCP Pro (sister project)

## Git
- Push force, never pull
- GitHub: https://github.com/xDarkzx/Audacity-MCP

## Style
- Python 3.10+
- Type hints on public functions
- No unnecessary comments or docstrings on obvious code
- Keep it simple, don't over-engineer
