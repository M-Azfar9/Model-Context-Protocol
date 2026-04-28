# For init 
uv init .

# Setting fastmcp
uv add fastmcp

# For inspection
uv run fastmcp dev inspector --server-spec main.py


# For Running
uv run fastmcp run main.py



# For running in claude-desktop
uv run fastmcp install claude-desktop main.py


# We can also convert the fastapi app to MCP server
mcp = FastMCP.from_fastapi(
    app = {pass here app name of fastapi},
    name = {your mcp server name}
)