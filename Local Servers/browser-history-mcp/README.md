# Browser History MCP

A powerful [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server that provides read-only access to your local browser history and bookmarks. This allows AI assistants to help you find information you've seen before, summarize your browsing habits, or look up bookmarks stored in **Google Chrome** and **Mozilla Firefox**.

## Features

- **Multi-Browser Support**: Automatically detects and queries Chrome and Firefox profiles.
- **Safe Read-Access**: Copies database files to temporary locations to avoid "database is locked" errors while your browser is open.
- **Privacy First**: All processing is local. No data is transmitted externally; it only provides the data to your local AI assistant.
- **Deep Search**: Search history and bookmarks by keyword, URL, or folder name.
- **Insights**: Identify top domains and summarize visit patterns over time.

## Tools

The server exposes the following tools to the AI assistant:

- `search_history`: Search browser history by keyword (matches URL and page title).
- `get_recent_history`: Retrieve the most recently visited pages within a specific time range (e.g., last 24 hours).
- `get_top_domains`: Identify the most frequently visited domains over a custom period.
- `search_bookmarks`: Search through your bookmarks by title, URL, or folder.
- `summarize_page_visits`: Get a detailed breakdown of visit counts and timestamps for specific sites.
- `list_browser_profiles`: Diagnostic tool to see which browser profiles were detected.

## Setup

### Prerequisites
- [uv](https://github.com/astral-sh/uv) installed on your system.
- Google Chrome or Mozilla Firefox installed.

### Installation for Claude Desktop

Add this to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "browser-history": {
      "command": "uv",
      "args": [
        "run",
        "--path",
        "D:\\Ai Content\\MCP\\Local Servers\\browser-history-mcp\\main.py"
      ]
    }
  }
}
```

## Local Development

1. Clone the repository.
2. Install dependencies:
   ```bash
   uv sync
   ```
3. Run the server in development mode:
   ```bash
   uv run main.py
   ```

---
*Note: This server is currently optimized for Windows environments but follows standard paths that can be extended for macOS/Linux.*

