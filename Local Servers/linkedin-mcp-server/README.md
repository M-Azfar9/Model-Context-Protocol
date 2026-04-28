# LinkedIn MCP Server (stickerdaniel)

GitHub: https://github.com/stickerdaniel/linkedin-mcp-server
PyPI:   https://pypi.org/project/linkedin-scraper-mcp/

## How it works
This server runs via `uvx` directly from PyPI — no cloning or manual install needed.
`uvx linkedin-scraper-mcp@latest` auto-downloads and runs the latest version on every startup.

The server uses Patchright (anti-detection browser engine) to automate LinkedIn in a
persistent browser profile saved at: `C:\Users\user\.linkedin-mcp\`

---

## One-time login (REQUIRED before first use)

Run this in your terminal after Claude Desktop starts the server:

```
uvx linkedin-scraper-mcp@latest --login
```

This opens a real browser window. Log in to LinkedIn manually (you have 5 minutes
for 2FA / captcha). Your session is saved and reused — you only need to do this once,
or whenever your session expires.

---

## claude_desktop_config.json entry

```json
"linkedin": {
  "command": "C:\\Users\\user\\AppData\\Roaming\\Python\\Python314\\Scripts\\uvx.exe",
  "args": ["linkedin-scraper-mcp@latest"],
  "env": {
    "UV_HTTP_TIMEOUT": "300"
  }
}
```

---

## Available tools once connected

| Tool                  | What it does                                      |
|-----------------------|---------------------------------------------------|
| get_person_profile    | Full profile: experience, education, skills, etc. |
| get_company_profile   | Company info from a LinkedIn company page         |
| search_jobs           | Search jobs by keyword + location                 |
| get_job_details       | Detailed info for a specific job posting          |
| get_recommended_jobs  | Your personalised LinkedIn job recommendations    |
| close_session         | Clean up the browser session                      |

---

## Tips & troubleshooting

- First tool call after startup may fail while Patchright downloads Chromium — just retry.
- If you hit a CAPTCHA: run `uvx linkedin-scraper-mcp@latest --login` again.
- Keep usage reasonable (< 20-30 profile lookups/day) to avoid LinkedIn flagging the account.
- Session files live at: `C:\Users\user\.linkedin-mcp\`

## Last updated
2026-04-25
