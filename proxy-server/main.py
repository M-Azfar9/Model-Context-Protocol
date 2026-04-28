from fastmcp import FastMCP


mcp = FastMCP.as_proxy(
    "https://mcp-browser-insights.fastmcp.app/mcp",
    name = "proxy server"
)

if __name__ == "__main__":
    mcp.run()
