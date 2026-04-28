"""
browser-history-mcp
====================
A FastMCP server providing read-only access to local browser history and bookmarks.
Supports: Google Chrome (primary), Mozilla Firefox (secondary).

All access is local and read-only. No browsing data is logged or transmitted.
"""

import json
import os
import shutil
import sqlite3
import tempfile
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHROME_EPOCH_OFFSET = 11_644_473_600  # seconds between 1601-01-01 and 1970-01-01

mcp = FastMCP(
    name="browser-history-mcp",
    instructions=(
        "Provides read-only access to local browser history and bookmarks. "
        "Use these tools to search history, find recent visits, identify top domains, "
        "and look up bookmarks stored in Chrome or Firefox."
    ),
)

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _chrome_profile_dirs() -> list[Path]:
    """Return all likely Chrome profile directories that contain a History file."""
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
    if not base.exists():
        return []
    dirs = []
    for candidate in base.iterdir():
        if candidate.is_dir() and (candidate / "History").exists():
            dirs.append(candidate)
    return dirs


def _firefox_profile_dirs() -> list[Path]:
    """Return all likely Firefox profile directories that contain places.sqlite."""
    base = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"
    if not base.exists():
        return []
    dirs = []
    for candidate in base.iterdir():
        if candidate.is_dir() and (candidate / "places.sqlite").exists():
            dirs.append(candidate)
    return dirs


def _safe_copy(src: Path) -> Optional[Path]:
    """
    Copy a SQLite file to a temp location so we can read it safely even when
    the browser has a lock on it.  Returns the temp path or None on failure.
    """
    try:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".sqlite")
        tmp.close()
        shutil.copy2(src, tmp.name)
        return Path(tmp.name)
    except Exception:
        return None


def _chrome_ts_to_dt(chrome_ts: int) -> datetime:
    """Convert Chrome's microseconds-since-1601 timestamp to UTC datetime."""
    unix_ts = chrome_ts / 1_000_000 - CHROME_EPOCH_OFFSET
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc)


def _firefox_ts_to_dt(ff_ts: int) -> datetime:
    """Convert Firefox's microseconds-since-Unix-epoch timestamp to UTC datetime."""
    return datetime.fromtimestamp(ff_ts / 1_000_000, tz=timezone.utc)


def _query_chrome_history(sql: str, params: tuple = ()) -> list[dict]:
    """Run a query against all Chrome History databases and return combined rows."""
    rows = []
    for profile in _chrome_profile_dirs():
        db_path = profile / "History"
        tmp = _safe_copy(db_path)
        if not tmp:
            continue
        try:
            con = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            cur = con.execute(sql, params)
            rows.extend([dict(r) for r in cur.fetchall()])
            con.close()
        except Exception:
            pass
        finally:
            tmp.unlink(missing_ok=True)
    return rows


def _query_firefox_history(sql: str, params: tuple = ()) -> list[dict]:
    """Run a query against all Firefox places databases and return combined rows."""
    rows = []
    for profile in _firefox_profile_dirs():
        db_path = profile / "places.sqlite"
        tmp = _safe_copy(db_path)
        if not tmp:
            continue
        try:
            con = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
            con.row_factory = sqlite3.Row
            cur = con.execute(sql, params)
            rows.extend([dict(r) for r in cur.fetchall()])
            con.close()
        except Exception:
            pass
        finally:
            tmp.unlink(missing_ok=True)
    return rows


def _chrome_bookmarks() -> list[dict]:
    """Parse all Chrome Bookmarks JSON files and return a flat list of bookmark dicts."""
    bookmarks = []

    def _walk(node, folder=""):
        if node.get("type") == "url":
            bookmarks.append({
                "title": node.get("name", ""),
                "url": node.get("url", ""),
                "folder": folder,
                "browser": "Chrome",
                "date_added": node.get("date_added", ""),
            })
        for child in node.get("children", []):
            _walk(child, folder=node.get("name", folder))

    for profile in _chrome_profile_dirs():
        bm_file = profile / "Bookmarks"
        if not bm_file.exists():
            continue
        try:
            data = json.loads(bm_file.read_text(encoding="utf-8"))
            roots = data.get("roots", {})
            for root_node in roots.values():
                if isinstance(root_node, dict):
                    _walk(root_node)
        except Exception:
            pass
    return bookmarks


def _firefox_bookmarks() -> list[dict]:
    """Query Firefox places.sqlite for bookmarks."""
    sql = """
        SELECT b.title, p.url, f.title AS folder, b.dateAdded
        FROM moz_bookmarks b
        JOIN moz_places p ON b.fk = p.id
        LEFT JOIN moz_bookmarks f ON b.parent = f.id
        WHERE b.type = 1 AND p.url NOT LIKE 'place:%'
        ORDER BY b.dateAdded DESC
        LIMIT 2000
    """
    rows = _query_firefox_history(sql)
    result = []
    for r in rows:
        result.append({
            "title": r.get("title") or "",
            "url": r.get("url", ""),
            "folder": r.get("folder") or "",
            "browser": "Firefox",
            "date_added": r.get("dateAdded", ""),
        })
    return result


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_history(
    query: str,
    limit: int = 30,
    browser: str = "all",
) -> str:
    """
    Search browser history by keyword (matches URL and page title).

    Args:
        query: Keyword or phrase to search for.
        limit: Maximum number of results to return (default 30, max 200).
        browser: Which browser to search — "chrome", "firefox", or "all".

    Returns:
        JSON list of matching history entries with title, url, visit_count, last_visit.
    """
    limit = min(limit, 200)
    results = []

    if browser in ("chrome", "all"):
        sql = """
            SELECT u.title, u.url, u.visit_count,
                   MAX(v.visit_time) AS last_visit_chrome_ts
            FROM urls u
            JOIN visits v ON u.id = v.url
            WHERE (u.title LIKE ? OR u.url LIKE ?)
            GROUP BY u.id
            ORDER BY last_visit_chrome_ts DESC
            LIMIT ?
        """
        pattern = f"%{query}%"
        for row in _query_chrome_history(sql, (pattern, pattern, limit)):
            ts = row.get("last_visit_chrome_ts", 0)
            dt = _chrome_ts_to_dt(ts).isoformat() if ts else ""
            results.append({
                "browser": "Chrome",
                "title": row.get("title") or "",
                "url": row.get("url", ""),
                "visit_count": row.get("visit_count", 1),
                "last_visit": dt,
            })

    if browser in ("firefox", "all"):
        sql = """
            SELECT p.title, p.url, p.visit_count,
                   MAX(h.visit_date) AS last_visit_ff_ts
            FROM moz_places p
            JOIN moz_historyvisits h ON p.id = h.place_id
            WHERE (p.title LIKE ? OR p.url LIKE ?)
            GROUP BY p.id
            ORDER BY last_visit_ff_ts DESC
            LIMIT ?
        """
        pattern = f"%{query}%"
        for row in _query_firefox_history(sql, (pattern, pattern, limit)):
            ts = row.get("last_visit_ff_ts", 0)
            dt = _firefox_ts_to_dt(ts).isoformat() if ts else ""
            results.append({
                "browser": "Firefox",
                "title": row.get("title") or "",
                "url": row.get("url", ""),
                "visit_count": row.get("visit_count", 1),
                "last_visit": dt,
            })

    if not results:
        return json.dumps({"message": f"No history found matching '{query}'.", "results": []}, indent=2)

    results.sort(key=lambda x: x["last_visit"], reverse=True)
    results = results[:limit]
    return json.dumps({"query": query, "count": len(results), "results": results}, indent=2)


@mcp.tool()
def get_recent_history(
    hours: int = 24,
    limit: int = 50,
    browser: str = "all",
) -> str:
    """
    Retrieve the most recently visited pages within the last N hours.

    Args:
        hours: How many hours back to look (default 24, max 720 = 30 days).
        limit: Maximum results to return (default 50, max 500).
        browser: "chrome", "firefox", or "all".

    Returns:
        JSON list of recent history entries sorted by visit time descending.
    """
    hours = min(hours, 720)
    limit = min(limit, 500)
    cutoff_dt = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
    results = []

    if browser in ("chrome", "all"):
        # Chrome timestamp in microseconds since 1601
        chrome_cutoff = int((cutoff_dt.timestamp() + CHROME_EPOCH_OFFSET) * 1_000_000)
        sql = """
            SELECT u.title, u.url, u.visit_count,
                   MAX(v.visit_time) AS last_visit_chrome_ts
            FROM urls u
            JOIN visits v ON u.id = v.url
            WHERE v.visit_time >= ?
            GROUP BY u.id
            ORDER BY last_visit_chrome_ts DESC
            LIMIT ?
        """
        for row in _query_chrome_history(sql, (chrome_cutoff, limit)):
            ts = row.get("last_visit_chrome_ts", 0)
            dt = _chrome_ts_to_dt(ts).isoformat() if ts else ""
            results.append({
                "browser": "Chrome",
                "title": row.get("title") or "",
                "url": row.get("url", ""),
                "visit_count": row.get("visit_count", 1),
                "last_visit": dt,
            })

    if browser in ("firefox", "all"):
        ff_cutoff = int(cutoff_dt.timestamp() * 1_000_000)
        sql = """
            SELECT p.title, p.url, p.visit_count,
                   MAX(h.visit_date) AS last_visit_ff_ts
            FROM moz_places p
            JOIN moz_historyvisits h ON p.id = h.place_id
            WHERE h.visit_date >= ?
            GROUP BY p.id
            ORDER BY last_visit_ff_ts DESC
            LIMIT ?
        """
        for row in _query_firefox_history(sql, (ff_cutoff, limit)):
            ts = row.get("last_visit_ff_ts", 0)
            dt = _firefox_ts_to_dt(ts).isoformat() if ts else ""
            results.append({
                "browser": "Firefox",
                "title": row.get("title") or "",
                "url": row.get("url", ""),
                "visit_count": row.get("visit_count", 1),
                "last_visit": dt,
            })

    if not results:
        return json.dumps({"message": f"No history found in the last {hours} hours.", "results": []}, indent=2)

    results.sort(key=lambda x: x["last_visit"], reverse=True)
    results = results[:limit]
    return json.dumps({"hours": hours, "count": len(results), "results": results}, indent=2)


@mcp.tool()
def get_top_domains(
    limit: int = 20,
    days: int = 30,
    browser: str = "all",
) -> str:
    """
    Identify the most frequently visited domains over the last N days.

    Args:
        limit: Number of top domains to return (default 20, max 100).
        days: How many days back to consider (default 30, max 365).
        browser: "chrome", "firefox", or "all".

    Returns:
        JSON list of domains sorted by visit count descending.
    """
    limit = min(limit, 100)
    days = min(days, 365)
    cutoff_dt = datetime.now(tz=timezone.utc) - timedelta(days=days)
    domain_counts: Counter = Counter()

    if browser in ("chrome", "all"):
        chrome_cutoff = int((cutoff_dt.timestamp() + CHROME_EPOCH_OFFSET) * 1_000_000)
        sql = """
            SELECT u.url
            FROM urls u
            JOIN visits v ON u.id = v.url
            WHERE v.visit_time >= ?
        """
        for row in _query_chrome_history(sql, (chrome_cutoff,)):
            parsed = urlparse(row.get("url", ""))
            if parsed.netloc:
                domain_counts[parsed.netloc] += 1

    if browser in ("firefox", "all"):
        ff_cutoff = int(cutoff_dt.timestamp() * 1_000_000)
        sql = """
            SELECT p.url
            FROM moz_places p
            JOIN moz_historyvisits h ON p.id = h.place_id
            WHERE h.visit_date >= ?
        """
        for row in _query_firefox_history(sql, (ff_cutoff,)):
            parsed = urlparse(row.get("url", ""))
            if parsed.netloc:
                domain_counts[parsed.netloc] += 1

    if not domain_counts:
        return json.dumps({"message": "No domain data found.", "results": []}, indent=2)

    top = [{"domain": d, "visits": c} for d, c in domain_counts.most_common(limit)]
    return json.dumps({"days": days, "count": len(top), "results": top}, indent=2)


@mcp.tool()
def search_bookmarks(
    query: str = "",
    browser: str = "all",
    limit: int = 50,
) -> str:
    """
    Search browser bookmarks by title, URL, or folder name.

    Args:
        query: Keyword to filter by (leave empty to list all bookmarks).
        browser: "chrome", "firefox", or "all".
        limit: Maximum results (default 50, max 500).

    Returns:
        JSON list of matching bookmarks with title, url, folder, browser.
    """
    limit = min(limit, 500)
    all_bookmarks = []

    if browser in ("chrome", "all"):
        all_bookmarks.extend(_chrome_bookmarks())
    if browser in ("firefox", "all"):
        all_bookmarks.extend(_firefox_bookmarks())

    if query:
        q = query.lower()
        all_bookmarks = [
            b for b in all_bookmarks
            if q in b.get("title", "").lower()
            or q in b.get("url", "").lower()
            or q in b.get("folder", "").lower()
        ]

    all_bookmarks = all_bookmarks[:limit]

    if not all_bookmarks:
        return json.dumps({"message": "No bookmarks found.", "results": []}, indent=2)

    # Strip date_added from output for cleanliness
    clean = [{"title": b["title"], "url": b["url"], "folder": b["folder"], "browser": b["browser"]}
             for b in all_bookmarks]
    return json.dumps({"query": query, "count": len(clean), "results": clean}, indent=2)


@mcp.tool()
def summarize_page_visits(
    url_contains: str,
    browser: str = "all",
) -> str:
    """
    Summarize visit history for pages matching a URL pattern.
    Shows title, URL, total visit count, first visit, and last visit.

    Args:
        url_contains: Partial URL or domain to match (e.g. "github.com").
        browser: "chrome", "firefox", or "all".

    Returns:
        JSON summary of matching page visits.
    """
    results = []
    pattern = f"%{url_contains}%"

    if browser in ("chrome", "all"):
        sql = """
            SELECT u.title, u.url, u.visit_count,
                   MIN(v.visit_time) AS first_visit_ts,
                   MAX(v.visit_time) AS last_visit_ts
            FROM urls u
            JOIN visits v ON u.id = v.url
            WHERE u.url LIKE ?
            GROUP BY u.id
            ORDER BY u.visit_count DESC
            LIMIT 100
        """
        for row in _query_chrome_history(sql, (pattern,)):
            first = _chrome_ts_to_dt(row["first_visit_ts"]).isoformat() if row.get("first_visit_ts") else ""
            last = _chrome_ts_to_dt(row["last_visit_ts"]).isoformat() if row.get("last_visit_ts") else ""
            results.append({
                "browser": "Chrome",
                "title": row.get("title") or "",
                "url": row.get("url", ""),
                "visit_count": row.get("visit_count", 1),
                "first_visit": first,
                "last_visit": last,
            })

    if browser in ("firefox", "all"):
        sql = """
            SELECT p.title, p.url, p.visit_count,
                   MIN(h.visit_date) AS first_visit_ts,
                   MAX(h.visit_date) AS last_visit_ts
            FROM moz_places p
            JOIN moz_historyvisits h ON p.id = h.place_id
            WHERE p.url LIKE ?
            GROUP BY p.id
            ORDER BY p.visit_count DESC
            LIMIT 100
        """
        for row in _query_firefox_history(sql, (pattern,)):
            first = _firefox_ts_to_dt(row["first_visit_ts"]).isoformat() if row.get("first_visit_ts") else ""
            last = _firefox_ts_to_dt(row["last_visit_ts"]).isoformat() if row.get("last_visit_ts") else ""
            results.append({
                "browser": "Firefox",
                "title": row.get("title") or "",
                "url": row.get("url", ""),
                "visit_count": row.get("visit_count", 1),
                "first_visit": first,
                "last_visit": last,
            })

    if not results:
        return json.dumps({"message": f"No visits found for '{url_contains}'.", "results": []}, indent=2)

    results.sort(key=lambda x: x["visit_count"], reverse=True)
    total_visits = sum(r["visit_count"] for r in results)
    return json.dumps({
        "url_contains": url_contains,
        "unique_pages": len(results),
        "total_visits": total_visits,
        "results": results,
    }, indent=2)


@mcp.tool()
def list_browser_profiles() -> str:
    """
    List all detected browser profiles and their status.
    Useful for diagnosing setup issues.

    Returns:
        JSON with detected Chrome and Firefox profile paths.
    """
    chrome_profiles = [str(p) for p in _chrome_profile_dirs()]
    firefox_profiles = [str(p) for p in _firefox_profile_dirs()]
    return json.dumps({
        "chrome": {
            "profile_count": len(chrome_profiles),
            "profiles": chrome_profiles,
        },
        "firefox": {
            "profile_count": len(firefox_profiles),
            "profiles": firefox_profiles,
        },
    }, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
