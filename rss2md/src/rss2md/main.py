import os
import json
import logging
import socket
from typing import Dict, Optional, Union, Any, List
from datetime import datetime, timedelta, timezone, MAXYEAR
import time  # For feedparser's struct_time

# --- Core Libraries ---
import feedparser
from markdownify import markdownify
from pydantic import BaseModel, Field, model_validator, ValidationError
from dateutil.parser import parse as dateutil_parse  # For robust date string parsing

# --- MCP Libraries ---
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# --- Constants ---
FETCH_RSS_TOOL_NAME = "fetch_rss_to_markdown"
DEFAULT_TIMEOUT = 15  # seconds for fetching feed


# --- Input Schema ---
class FetchRssInput(BaseModel):
    rss_url: str = Field(..., description="The full URL of the RSS or Atom feed.")
    filter_since_date: Optional[str] = Field(
        None,
        description="ISO 8601 date string (e.g., 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MM:SSZ'). Returns articles published on or after this date (UTC).",
    )
    filter_last_days: Optional[int] = Field(
        None,
        gt=0,
        description="Positive integer for days back from now (UTC). Returns articles published within this period.",
    )

    @model_validator(mode="after")
    def check_exactly_one_filter(self) -> "FetchRssInput":
        if self.filter_since_date is None and self.filter_last_days is None:
            raise ValueError(
                "Exactly one of 'filter_since_date' or 'filter_last_days' must be provided."
            )
        if self.filter_since_date is not None and self.filter_last_days is not None:
            raise ValueError(
                "Provide either 'filter_since_date' or 'filter_last_days', not both."
            )
        return self


# --- Helper Functions ---


def _parse_iso_date_to_utc(date_str: str) -> datetime:
    """Parses an ISO 8601 date string and returns a timezone-aware UTC datetime."""
    try:
        dt = dateutil_parse(date_str)
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            # Assume UTC if no timezone info is present
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            # Convert to UTC
            dt = dt.astimezone(timezone.utc)
        # Handle potential year > MAXYEAR after timezone conversion if dateutil_parse was too lenient
        if dt.year > MAXYEAR:
            raise ValueError("Date year out of range")
        return dt
    except Exception as e:
        raise ValueError(f"Invalid date format for '{date_str}': {e}")


def _calculate_cutoff_date(input_data: FetchRssInput) -> datetime:
    """Determines the UTC cutoff datetime based on input filters."""
    now_utc = datetime.now(timezone.utc)
    if input_data.filter_since_date:
        return _parse_iso_date_to_utc(input_data.filter_since_date)
    elif input_data.filter_last_days:
        return now_utc - timedelta(days=input_data.filter_last_days)
    else:
        # Should be unreachable due to pydantic validation, but belts and suspenders
        raise ValueError("No valid filter provided.")


def _struct_time_to_utc_datetime(st: Optional[time.struct_time]) -> Optional[datetime]:
    """Converts feedparser's struct_time to a timezone-aware UTC datetime."""
    if st is None:
        return None
    try:
        # feedparser.struct_time can sometimes have tm_year=0 etc. Handle this.
        # Create datetime in UTC directly if possible, assuming feedparser gives UTC offset 0
        # or handle potential timezone info if feedparser becomes more sophisticated.
        # For simplicity and common RSS practice, we'll assume UTC if offset is 0 or not present clearly.
        ts = time.mktime(st)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)

        # Basic sanity check for year range, mktime might produce odd results for bad input struct_time
        if not (1 <= dt.year <= MAXYEAR):
            return None  # Invalid date produced

        return dt
    except (TypeError, ValueError, OverflowError):
        # Handle cases where struct_time is invalid or out of range
        return None


def _get_best_content(entry: feedparser.FeedParserDict) -> str:
    """Extracts the best available content field, prioritizing full content."""
    if hasattr(entry, "content") and entry.content:
        # content often is a list, take the first item's value
        return entry.content[0].get("value", "")
    elif hasattr(entry, "summary"):
        return entry.summary
    elif hasattr(entry, "description"):
        return entry.description
    else:
        return ""  # No content found


# --- Main Server Logic ---


async def serve() -> None:
    logger = logging.getLogger(__name__)
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    server = Server("mcp-rss-markdown")  # Renamed server

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=FETCH_RSS_TOOL_NAME,
                description="Fetches an RSS feed, filters articles by date, and returns matching articles formatted as a Markdown list.",
                inputSchema=FetchRssInput.model_json_schema(),
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name != FETCH_RSS_TOOL_NAME:
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"status": "error", "error_message": f"Unknown tool: {name}"}
                    ),
                )
            ]

        original_timeout = socket.getdefaulttimeout()
        try:
            # 1. Validate Inputs using Pydantic
            try:
                input_data = FetchRssInput(**arguments)
            except ValidationError as e:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "status": "error",
                                "error_message": f"Input validation error: {e}",
                            }
                        ),
                    )
                ]

            # Basic URL scheme check
            if not (
                input_data.rss_url.startswith("http://")
                or input_data.rss_url.startswith("https://")
            ):
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "status": "error",
                                "error_message": "Invalid URL scheme. Only http:// or https:// allowed.",
                            }
                        ),
                    )
                ]

            # 2. Set Timeout and Fetch Feed
            logger.info(f"Fetching RSS feed: {input_data.rss_url}")
            socket.setdefaulttimeout(DEFAULT_TIMEOUT)
            feed = feedparser.parse(input_data.rss_url)
            socket.setdefaulttimeout(original_timeout)  # Reset timeout immediately

            # 3. Check for Fetch/Parse Errors
            if feed.bozo:
                bozo_exception = feed.get("bozo_exception", "Unknown parsing error")
                logger.warning(
                    f"Feed is bozo (potentially malformed). URL: {input_data.rss_url}, Exception: {bozo_exception}"
                )
                # Continue processing, but log the warning. Might still contain usable entries.
                # If feed.entries is empty AND it's bozo, treat as error below.

            if feed.get("status", 200) >= 400:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "status": "error",
                                "error_message": f"HTTP error fetching feed: Status {feed.status}",
                            }
                        ),
                    )
                ]

            if not feed.entries and feed.bozo:
                # If it's malformed AND resulted in zero entries, report the parsing error
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "status": "error",
                                "error_message": f"Failed to parse feed: {feed.get('bozo_exception', 'Unknown parsing error')}",
                            }
                        ),
                    )
                ]

            # 4. Determine Filter Date
            try:
                cutoff_date_utc = _calculate_cutoff_date(input_data)
                logger.info(
                    f"Filtering articles published on or after: {cutoff_date_utc.isoformat()}"
                )
            except ValueError as e:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps({"status": "error", "error_message": str(e)}),
                    )
                ]

            # 5. Filter and Format Entries
            markdown_entries = []
            feed_title = feed.feed.get("title", "Untitled Feed")

            for entry in feed.entries:
                entry_title = entry.get("title", "No Title")
                entry_link = entry.get("link", "")
                entry_desc = entry.get(
                    "summary", entry.get("description", "")
                )  # Simple description/summary

                # Get and parse publication date
                published_struct = entry.get("published_parsed")
                entry_date_utc = _struct_time_to_utc_datetime(published_struct)

                if entry_date_utc is None:
                    logger.debug(
                        f"Skipping entry '{entry_title}' due to missing or unparseable date."
                    )
                    continue  # Skip entries with unparseable/missing dates

                # Apply filter
                if entry_date_utc >= cutoff_date_utc:
                    logger.debug(
                        f"Including entry '{entry_title}' (Date: {entry_date_utc.isoformat()})"
                    )

                    # Extract and convert content
                    html_content = _get_best_content(entry)
                    try:
                        # Basic sanitization by stripping dangerous tags
                        markdown_content = markdownify(
                            html_content, strip=["script", "style", "iframe"]
                        )
                    except Exception as conv_e:
                        logger.warning(
                            f"Markdown conversion failed for entry '{entry_title}': {conv_e}. Using description/summary instead."
                        )
                        # Fallback to description/summary if conversion fails
                        markdown_content = markdownify(
                            entry_desc, strip=["script", "style", "iframe"]
                        )

                    # Format entry
                    formatted_date = entry_date_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
                    entry_md = (
                        f"## {entry_title}\n"
                        f"**Published:** {formatted_date}\n"
                        f"**Link:** <{entry_link}>\n"
                        f"**Description:** {entry_desc}\n\n"
                        f"**Content:**\n\n{markdown_content}\n\n---"
                    )
                    markdown_entries.append(entry_md)
                else:
                    logger.debug(
                        f"Excluding entry '{entry_title}' (Date: {entry_date_utc.isoformat()})"
                    )

            # 6. Assemble Final Markdown
            if not markdown_entries:
                final_markdown = f"# {feed_title}\n\nNo articles found matching the specified date filter."
            else:
                final_markdown = f"# {feed_title}\n\n" + "\n\n".join(markdown_entries)

            logger.info(
                f"Successfully processed feed. Found {len(markdown_entries)} matching articles."
            )
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {"status": "success", "markdown_content": final_markdown}
                    ),
                )
            ]

        except Exception as e:
            logger.exception(
                f"Unhandled error processing RSS feed: {e}"
            )  # Log the full traceback
            return [
                TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "status": "error",
                            "error_message": f"An unexpected error occurred: {e}",
                        }
                    ),
                )
            ]
        finally:
            # Ensure timeout is always reset
            socket.setdefaulttimeout(original_timeout)

    # --- Run Server ---
    options = server.create_initialization_options()
    logger.info("Starting RSS-to-Markdown MCP server...")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, options, raise_exceptions=False
        )  # Set raise_exceptions=False for production


# --- Entry Point ---
def main():
    import asyncio

    # Ensure necessary libraries are installed:
    # pip install mcp.py feedparser markdownify python-dateutil pydantic
    asyncio.run(serve())


if __name__ == "__main__":
    main()
