from mcp.server.fastmcp import FastMCP

from server.audacity_client import AudacityClient
from server.tool_registry import register_all_tools

mcp = FastMCP("AudacityMCP")
client = AudacityClient()

register_all_tools(mcp)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
