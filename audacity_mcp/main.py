import atexit

from mcp.server.fastmcp import FastMCP

from audacity_mcp.audacity_client import AudacityClient
from audacity_mcp.tool_registry import register_all_tools

mcp = FastMCP("AudacityMCP")
client = AudacityClient()
atexit.register(client.close)

register_all_tools(mcp)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
