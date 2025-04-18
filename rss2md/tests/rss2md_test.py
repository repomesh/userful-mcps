import unittest
import json
import os
import sys
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from contextlib import AsyncExitStack

# Import necessary components from the mcp library
try:
    from mcp import ClientSession, StdioServerParameters, types
    from mcp.client.stdio import stdio_client
except ImportError as e:
    print(
        f"ERROR: Could not import mcp components. Ensure mcp library is installed correctly. {e}"
    )
    sys.exit(1)

# --- Configuration ---
# Assumes the test script is in a 'tests' subdirectory next to the script
MCP_SCRIPT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "src", "rss2md", "main.py")
)
TEST_RSS_URL = (
    "https://rss.beehiiv.com/feeds/fMHDv0Uk41.xml"  # The URL to use for success tests
)

# Configure basic logging for the test script itself
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [TEST] %(message)s"
)
logger = logging.getLogger(__name__)


# --- Test Case using IsolatedAsyncioTestCase ---
class TestRssMarkdownMCP(unittest.IsolatedAsyncioTestCase):
    server_params: StdioServerParameters = None

    @classmethod
    def setUpClass(cls):
        """Check prerequisites once for the test class."""
        logger.info("Setting up TestRssMarkdownMCP class...")

        # Ensure the MCP script exists
        if not os.path.exists(MCP_SCRIPT_PATH):
            # Adjust path finding if script is elsewhere relative to test
            alt_path = os.path.abspath(
                os.path.join(os.path.dirname(__file__), "rss_to_markdown_mcp.py")
            )
            if os.path.exists(alt_path):
                cls.MCP_SCRIPT_PATH = alt_path
            else:
                raise RuntimeError(
                    f"MCP script not found at expected paths: {MCP_SCRIPT_PATH} or {alt_path}"
                )
        else:
            cls.MCP_SCRIPT_PATH = MCP_SCRIPT_PATH

        logger.info(f"Using MCP script path: {cls.MCP_SCRIPT_PATH}")

        # Define server parameters (used in each test's setup)
        server_env = os.environ.copy()
        cls.server_params = StdioServerParameters(
            command=sys.executable,  # Use the same python interpreter
            args=[cls.MCP_SCRIPT_PATH],
            env=server_env,
        )
        logger.info("TestRssMarkdownMCP class setup complete.")

    @classmethod
    def tearDownClass(cls):
        logger.info("Tearing down TestRssMarkdownMCP class.")

    async def test_01_list_tools(self):
        """Test listing tools using ClientSession."""
        logger.info("Running test_01_list_tools...")
        async with AsyncExitStack() as stack:
            try:
                read, write = await stack.enter_async_context(
                    stdio_client(self.server_params)
                )
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                logger.info("MCP Session initialized for test_01_list_tools")
            except Exception as e:
                self.fail(f"MCP setup failed for test_01_list_tools: {e}")

            try:
                response: types.ListToolsResult = await session.list_tools()
                logger.info(f"Received list_tools response: {response}")

                self.assertIsInstance(response, types.ListToolsResult)
                self.assertIsInstance(response.tools, list)
                self.assertEqual(len(response.tools), 1)

                tool = response.tools[0]
                self.assertIsInstance(tool, types.Tool)
                self.assertEqual(tool.name, "fetch_rss_to_markdown")  # Check tool name
                self.assertIsNotNone(tool.description)
                self.assertIsNotNone(tool.inputSchema)

                logger.info("test_01_list_tools PASSED")
            except Exception as e:
                logger.error(f"test_01_list_tools failed: {e}", exc_info=True)
                self.fail(f"test_01_list_tools encountered an error: {e}")
        logger.info("MCP Session closed for test_01_list_tools")

    async def test_02_success_last_days(self):
        """Test successful fetch using filter_last_days."""
        logger.info("Running test_02_success_last_days...")
        tool_name = "fetch_rss_to_markdown"
        tool_args = {"rss_url": TEST_RSS_URL, "filter_last_days": 2}

        async with AsyncExitStack() as stack:
            try:
                read, write = await stack.enter_async_context(
                    stdio_client(self.server_params)
                )
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                logger.info("MCP Session initialized for test_02")
            except Exception as e:
                self.fail(f"MCP setup failed for test_02: {e}")

            try:
                result: types.CallToolResult = await session.call_tool(
                    tool_name, tool_args
                )
                logger.info(f"Received call_tool result: {result}")

                self.assertIsInstance(result, types.CallToolResult)
                # Check if isError is False or None (older mcp.py versions might use None)
                self.assertIn(
                    result.isError,
                    [False, None],
                    f"Result indicates an error. Content: {result.content}",
                )
                self.assertIsInstance(result.content, list)
                self.assertEqual(len(result.content), 1)

                content_item = result.content[0]
                self.assertIsInstance(content_item, types.TextContent)
                self.assertEqual(content_item.type, "text")

                tool_output = json.loads(content_item.text)
                logger.info(f"Parsed tool output status: {tool_output.get('status')}")

                self.assertEqual(tool_output.get("status"), "success")
                self.assertIn("markdown_content", tool_output)
                self.assertIsInstance(tool_output["markdown_content"], str)
                # Check for basic structure, not exact content as it changes
                self.assertIn(
                    "# ",
                    tool_output["markdown_content"],
                    "Markdown should contain a feed title",
                )
                # Content might be empty if no articles in last 2 days, so don't mandate "##"
                logger.info(f"Markdown length: {len(tool_output['markdown_content'])}")

                logger.info("test_02_success_last_days PASSED")

            except Exception as e:
                logger.error(f"test_02_success_last_days failed: {e}", exc_info=True)
                self.fail(f"test_02_success_last_days encountered an error: {e}")
        logger.info("MCP Session closed for test_02")

    async def test_03_success_since_date(self):
        """Test successful fetch using filter_since_date."""
        logger.info("Running test_03_success_since_date...")
        tool_name = "fetch_rss_to_markdown"
        # Calculate date 5 days ago in YYYY-MM-DD format
        since_date = (datetime.now(timezone.utc) - timedelta(days=5)).strftime(
            "%Y-%m-%d"
        )
        tool_args = {"rss_url": TEST_RSS_URL, "filter_since_date": since_date}

        async with AsyncExitStack() as stack:
            try:
                read, write = await stack.enter_async_context(
                    stdio_client(self.server_params)
                )
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                logger.info("MCP Session initialized for test_03")
            except Exception as e:
                self.fail(f"MCP setup failed for test_03: {e}")

            try:
                result: types.CallToolResult = await session.call_tool(
                    tool_name, tool_args
                )
                logger.info(f"Received call_tool result: {result}")

                self.assertIsInstance(result, types.CallToolResult)
                self.assertIn(
                    result.isError,
                    [False, None],
                    f"Result indicates an error. Content: {result.content}",
                )
                self.assertIsInstance(result.content, list)
                self.assertEqual(len(result.content), 1)

                content_item = result.content[0]
                self.assertIsInstance(content_item, types.TextContent)
                tool_output = json.loads(content_item.text)
                logger.info(f"Parsed tool output status: {tool_output.get('status')}")

                self.assertEqual(tool_output.get("status"), "success")
                self.assertIn("markdown_content", tool_output)
                self.assertIsInstance(tool_output["markdown_content"], str)
                self.assertIn(
                    "# ",
                    tool_output["markdown_content"],
                    "Markdown should contain a feed title",
                )

                logger.info("test_03_success_since_date PASSED")

            except Exception as e:
                logger.error(f"test_03_success_since_date failed: {e}", exc_info=True)
                self.fail(f"test_03_success_since_date encountered an error: {e}")
        logger.info("MCP Session closed for test_03")

    async def test_04_error_invalid_url_scheme(self):
        """Test error handling for invalid URL scheme."""
        logger.info("Running test_04_error_invalid_url_scheme...")
        tool_name = "fetch_rss_to_markdown"
        tool_args = {"rss_url": "ftp://example.com/feed.xml", "filter_last_days": 1}

        async with AsyncExitStack() as stack:
            # Setup session
            read, write = await stack.enter_async_context(
                stdio_client(self.server_params)
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            # Test call
            result: types.CallToolResult = await session.call_tool(tool_name, tool_args)
            logger.info(f"Received call_tool result (expected error): {result}")

            self.assertTrue(result.isError)
            error_output = json.loads(result.content[0].text)
            self.assertEqual(error_output.get("status"), "error")
            self.assertIn("Invalid URL scheme", error_output.get("error_message", ""))

            logger.info("test_04_error_invalid_url_scheme PASSED")
        logger.info("MCP Session closed for test_04")

    async def test_05_error_fetch_failed(self):
        """Test error handling for a non-existent URL."""
        logger.info("Running test_05_error_fetch_failed...")
        tool_name = "fetch_rss_to_markdown"
        tool_args = {
            "rss_url": "http://thisserverdoesnotexist.invalid/rss.xml",
            "filter_last_days": 1,
        }

        async with AsyncExitStack() as stack:
            # Setup session
            read, write = await stack.enter_async_context(
                stdio_client(self.server_params)
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            # Test call
            result: types.CallToolResult = await session.call_tool(tool_name, tool_args)
            logger.info(f"Received call_tool result (expected error): {result}")

            self.assertTrue(result.isError)
            error_output = json.loads(result.content[0].text)
            self.assertEqual(error_output.get("status"), "error")
            # Error message might vary depending on network/DNS setup, check for common patterns
            error_msg = error_output.get("error_message", "")
            self.assertTrue(
                "HTTP error" in error_msg
                or "Failed to parse feed" in error_msg
                or "timed out" in error_msg
                or "resolve host" in error_msg
                or "Name or service not known" in error_msg,  # Common DNS error
                f"Unexpected error message for fetch failure: {error_msg}",
            )

            logger.info("test_05_error_fetch_failed PASSED")
        logger.info("MCP Session closed for test_05")

    async def test_06_error_missing_filter(self):
        """Test error handling when no filter is provided."""
        logger.info("Running test_06_error_missing_filter...")
        tool_name = "fetch_rss_to_markdown"
        tool_args = {"rss_url": TEST_RSS_URL}  # Missing filter

        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(
                stdio_client(self.server_params)
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            result: types.CallToolResult = await session.call_tool(tool_name, tool_args)
            logger.info(f"Received call_tool result (expected error): {result}")

            self.assertTrue(result.isError)
            error_output = json.loads(result.content[0].text)
            self.assertEqual(error_output.get("status"), "error")
            self.assertIn("Exactly one of", error_output.get("error_message", ""))
            self.assertIn("must be provided", error_output.get("error_message", ""))

            logger.info("test_06_error_missing_filter PASSED")
        logger.info("MCP Session closed for test_06")

    async def test_07_error_both_filters(self):
        """Test error handling when both filters are provided."""
        logger.info("Running test_07_error_both_filters...")
        tool_name = "fetch_rss_to_markdown"
        tool_args = {
            "rss_url": TEST_RSS_URL,
            "filter_last_days": 1,
            "filter_since_date": "2024-01-01",
        }  # Both filters provided

        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(
                stdio_client(self.server_params)
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            result: types.CallToolResult = await session.call_tool(tool_name, tool_args)
            logger.info(f"Received call_tool result (expected error): {result}")

            self.assertTrue(result.isError)
            error_output = json.loads(result.content[0].text)
            self.assertEqual(error_output.get("status"), "error")
            self.assertIn("Provide either", error_output.get("error_message", ""))
            self.assertIn("not both", error_output.get("error_message", ""))

            logger.info("test_07_error_both_filters PASSED")
        logger.info("MCP Session closed for test_07")

    async def test_08_error_invalid_date_format(self):
        """Test error handling for invalid date string format."""
        logger.info("Running test_08_error_invalid_date_format...")
        tool_name = "fetch_rss_to_markdown"
        tool_args = {"rss_url": TEST_RSS_URL, "filter_since_date": "last tuesday"}

        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(
                stdio_client(self.server_params)
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            result: types.CallToolResult = await session.call_tool(tool_name, tool_args)
            logger.info(f"Received call_tool result (expected error): {result}")

            self.assertTrue(result.isError)
            error_output = json.loads(result.content[0].text)
            self.assertEqual(error_output.get("status"), "error")
            self.assertIn("Invalid date format", error_output.get("error_message", ""))

            logger.info("test_08_error_invalid_date_format PASSED")
        logger.info("MCP Session closed for test_08")

    async def test_09_error_invalid_days_type(self):
        """Test error handling for non-integer filter_last_days."""
        logger.info("Running test_09_error_invalid_days_type...")
        tool_name = "fetch_rss_to_markdown"
        tool_args = {
            "rss_url": TEST_RSS_URL,
            "filter_last_days": "two",
        }  # String instead of int

        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(
                stdio_client(self.server_params)
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            result: types.CallToolResult = await session.call_tool(tool_name, tool_args)
            logger.info(f"Received call_tool result (expected error): {result}")

            self.assertTrue(result.isError)
            error_output = json.loads(result.content[0].text)
            self.assertEqual(error_output.get("status"), "error")
            self.assertIn(
                "Input validation error", error_output.get("error_message", "")
            )  # Pydantic error
            self.assertIn("filter_last_days", error_output.get("error_message", ""))
            self.assertIn(
                "Input should be a valid integer", error_output.get("error_message", "")
            )

            logger.info("test_09_error_invalid_days_type PASSED")
        logger.info("MCP Session closed for test_09")

    async def test_10_unknown_tool(self):
        """Test calling a non-existent tool."""
        logger.info("Running test_10_unknown_tool...")
        tool_name = "non_existent_tool"
        tool_args = {}

        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(
                stdio_client(self.server_params)
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            result: types.CallToolResult = await session.call_tool(tool_name, tool_args)
            logger.info(f"Received call_tool result (expected error): {result}")

            self.assertTrue(result.isError)
            error_output = json.loads(result.content[0].text)
            self.assertEqual(error_output.get("status"), "error")
            self.assertIn("Unknown tool", error_output.get("error_message", ""))
            self.assertIn(tool_name, error_output.get("error_message", ""))

            logger.info("test_10_unknown_tool PASSED")
        logger.info("MCP Session closed for test_10")


if __name__ == "__main__":
    # Note: Running these tests requires network access to fetch the RSS feed.
    # They might be flaky if the network is down or the feed URL changes.
    unittest.main()
