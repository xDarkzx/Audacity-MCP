import importlib
import pkgutil
from mcp.server.fastmcp import FastMCP

import server.tools as tools_package


def register_all_tools(mcp: FastMCP):
    for finder, name, ispkg in pkgutil.iter_modules(tools_package.__path__):
        module = importlib.import_module(f"server.tools.{name}")
        if hasattr(module, "register"):
            module.register(mcp)
