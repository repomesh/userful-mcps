# ./useful-mcps/tests/test_mermaid_mcp.py
import unittest
import json
import os
import sys
import tempfile
import logging
import asyncio
from contextlib import AsyncExitStack  # Correct import

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
MCP_SCRIPT_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "mermaid", "mermaid_mcp.py")
)
ACCESS_TOKEN_ENV_VAR = "MERMAID_ACCESS_TOKEN"

# Configure basic logging for the test script itself
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - [TEST] %(message)s"
)
logger = logging.getLogger(__name__)


# --- Test Case using IsolatedAsyncioTestCase ---
class TestMermaidMCP(unittest.IsolatedAsyncioTestCase):
    access_token: str = None
    server_params: StdioServerParameters = None

    @classmethod
    def setUpClass(cls):
        """Check prerequisites once for the test class."""
        logger.info("Setting up TestMermaidMCP class...")
        cls.access_token = os.environ.get(ACCESS_TOKEN_ENV_VAR)
        if not cls.access_token:
            raise unittest.SkipTest(
                f"Environment variable {ACCESS_TOKEN_ENV_VAR} not set. Skipping MCP tests."
            )

        # Ensure the MCP script exists
        if not os.path.exists(MCP_SCRIPT_PATH):
            raise RuntimeError(f"MCP script not found at {MCP_SCRIPT_PATH}")

        # Define server parameters (used in each test's setup)
        server_env = os.environ.copy()
        cls.server_params = StdioServerParameters(
            command=sys.executable,  # Use the same python interpreter
            args=[MCP_SCRIPT_PATH],
            env=server_env,
        )
        logger.info("TestMermaidMCP class setup complete.")

    @classmethod
    def tearDownClass(cls):
        logger.info("Tearing down TestMermaidMCP class.")

    # No asyncSetUp or asyncTearDown needed anymore

    async def test_01_list_tools(self):
        """Test listing tools using ClientSession."""
        logger.info("Running test_01_list_tools...")
        # --- Setup within test ---
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
            # --- End Setup ---

            # --- Test Logic ---
            try:
                response: types.ListToolsResult = await session.list_tools()
                logger.info(f"Received list_tools response: {response}")

                self.assertIsInstance(response, types.ListToolsResult)
                self.assertIsInstance(
                    response.tools, list, "Response.tools should be a list"
                )
                self.assertEqual(
                    len(response.tools), 1, "Expected one tool to be listed"
                )

                tool = response.tools[0]
                self.assertIsInstance(tool, types.Tool)
                self.assertEqual(
                    tool.name, "render_mermaid_chart", "Tool name mismatch"
                )
                self.assertIsNotNone(tool.description)
                self.assertIsNotNone(tool.inputSchema)

                logger.info("test_01_list_tools PASSED")
            except Exception as e:
                logger.error(f"test_01_list_tools failed: {e}", exc_info=True)
                self.fail(f"test_01_list_tools encountered an error: {e}")
            # --- End Test Logic ---
        # --- Teardown (implicit via async with) ---
        logger.info("MCP Session closed for test_01_list_tools")

    async def test_02_render_mermaid_chart_success(self):
        """Test the render_mermaid_chart tool successfully using ClientSession."""
        logger.info("Running test_02_render_mermaid_chart_success...")
        # --- Setup within test ---
        async with AsyncExitStack() as stack:
            try:
                read, write = await stack.enter_async_context(
                    stdio_client(self.server_params)
                )
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                logger.info("MCP Session initialized for test_02...")
            except Exception as e:
                self.fail(f"MCP setup failed for test_02: {e}")
            # --- End Setup ---

            # --- Test Logic ---
            tool_name = "render_mermaid_chart"
            output_path = None  # Define output_path before try block
            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".png", delete=False
                ) as tmp_file:
                    output_path = tmp_file.name
                if os.path.exists(output_path):
                    os.remove(output_path)

                mermaid_code = "graph LR;\nX-->Y;"
                tool_args = {"mermaid_code": mermaid_code, "output_path": output_path}

                result: types.CallToolResult = await session.call_tool(
                    tool_name, tool_args
                )
                logger.info(f"Received call_tool result: {result}")

                self.assertIsInstance(result, types.CallToolResult)
                self.assertFalse(
                    result.isError,
                    f"Result should not indicate an error. Content: {result.content}",
                )
                self.assertIsInstance(
                    result.content, list, "Result content should be a list"
                )
                self.assertEqual(len(result.content), 1, "Expected one content item")

                content_item = result.content[0]
                self.assertIsInstance(
                    content_item,
                    types.TextContent,
                    "Content item should be TextContent",
                )
                self.assertEqual(content_item.type, "text")

                tool_output = json.loads(content_item.text)
                logger.info(f"Parsed tool output: {tool_output}")

                self.assertIn(
                    "output_path", tool_output, "Tool output should contain output_path"
                )
                self.assertEqual(
                    os.path.abspath(tool_output["output_path"]),
                    os.path.abspath(output_path),
                    "Returned output path mismatch",
                )
                self.assertIn(
                    "document_id", tool_output, "Tool output should contain document_id"
                )

                self.assertTrue(
                    os.path.exists(output_path),
                    f"Output file '{output_path}' was not created.",
                )
                self.assertGreater(
                    os.path.getsize(output_path),
                    0,
                    f"Output file '{output_path}' is empty.",
                )

                logger.info("test_02_render_mermaid_chart_success PASSED")

            except Exception as e:
                logger.error(
                    f"test_02_render_mermaid_chart_success failed: {e}", exc_info=True
                )
                self.fail(
                    f"test_02_render_mermaid_chart_success encountered an error: {e}"
                )
            finally:
                # Ensure cleanup of temp file
                if output_path and os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                        logger.debug(f"Cleaned up temp file: {output_path}")
                    except OSError as err:
                        logger.warning(
                            f"Could not remove temp file {output_path}: {err}"
                        )
            # --- End Test Logic ---
        # --- Teardown (implicit via async with) ---
        logger.info("MCP Session closed for test_02...")

    async def test_03_render_mermaid_chart_missing_args(self):
        """Test render_mermaid_chart with missing arguments using ClientSession."""
        logger.info("Running test_03_render_mermaid_chart_missing_args...")
        # --- Setup within test ---
        async with AsyncExitStack() as stack:
            try:
                read, write = await stack.enter_async_context(
                    stdio_client(self.server_params)
                )
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                logger.info("MCP Session initialized for test_03...")
            except Exception as e:
                self.fail(f"MCP setup failed for test_03: {e}")
            # --- End Setup ---

            # --- Test Logic ---
            tool_name = "render_mermaid_chart"
            tool_args = {}
            try:
                result: types.CallToolResult = await session.call_tool(
                    tool_name, tool_args
                )
                logger.info(f"Received call_tool result (expected error): {result}")

                self.assertTrue(
                    result.isError,
                    "Result should indicate an error (isError should be True)",
                )
                self.assertIsInstance(
                    result.content, list, "Error content should be a list"
                )
                self.assertGreater(
                    len(result.content), 0, "Error content list should not be empty"
                )

                error_content = result.content[0]
                self.assertIsInstance(
                    error_content,
                    types.TextContent,
                    "Error content should be TextContent",
                )
                error_message = error_content.text
                logger.info(f"Caught expected error message: {error_message}")

                self.assertIn(
                    "mermaid_code",
                    error_message,
                    "Error should mention missing 'mermaid_code'",
                )
                self.assertIn(
                    "output_path",
                    error_message,
                    "Error should mention missing 'output_path'",
                )
                self.assertIn(
                    "Field required",
                    error_message,
                    "Error should mention 'Field required'",
                )

                logger.info(
                    "test_03_render_mermaid_chart_missing_args PASSED (Caught expected error result)"
                )
            except Exception as e:
                logger.error(
                    f"test_03_render_mermaid_chart_missing_args failed unexpectedly: {e}",
                    exc_info=True,
                )
                self.fail(
                    f"test_03_render_mermaid_chart_missing_args raised an unexpected exception: {e}"
                )
            # --- End Test Logic ---
        # --- Teardown (implicit via async with) ---
        logger.info("MCP Session closed for test_03...")

    async def test_04_unknown_tool(self):
        """Test calling a non-existent tool using ClientSession."""
        logger.info("Running test_04_unknown_tool...")
        # --- Setup within test ---
        async with AsyncExitStack() as stack:
            try:
                read, write = await stack.enter_async_context(
                    stdio_client(self.server_params)
                )
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                logger.info("MCP Session initialized for test_04...")
            except Exception as e:
                self.fail(f"MCP setup failed for test_04: {e}")
            # --- End Setup ---

            # --- Test Logic ---
            tool_name = "non_existent_tool"
            tool_args = {}
            try:
                result: types.CallToolResult = await session.call_tool(
                    tool_name, tool_args
                )
                logger.info(f"Received call_tool result (expected error): {result}")

                self.assertTrue(
                    result.isError,
                    "Result should indicate an error (isError should be True)",
                )
                self.assertIsInstance(
                    result.content, list, "Error content should be a list"
                )
                self.assertGreater(
                    len(result.content), 0, "Error content list should not be empty"
                )

                error_content = result.content[0]
                self.assertIsInstance(
                    error_content,
                    types.TextContent,
                    "Error content should be TextContent",
                )
                error_message = error_content.text
                logger.info(f"Caught expected error message: {error_message}")

                self.assertIn(
                    "Unknown tool",
                    error_message,
                    "Error message should indicate unknown tool",
                )
                self.assertIn(tool_name, error_message)

                logger.info(
                    "test_04_unknown_tool PASSED (Caught expected error result)"
                )
            except Exception as e:
                logger.error(
                    f"test_04_unknown_tool failed unexpectedly: {e}", exc_info=True
                )
                self.fail(f"test_04_unknown_tool raised an unexpected exception: {e}")
            # --- End Test Logic ---
        # --- Teardown (implicit via async with) ---
        logger.info("MCP Session closed for test_04...")


if __name__ == "__main__":
    unittest.main()
