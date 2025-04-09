import os
import sys
import json
import asyncio
import requests
import logging
from typing import Dict, Any, List, Optional

# Assuming mcp framework and pydantic are installed
from pydantic import BaseModel, Field
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# --- Configuration ---
BASE_URL = "https://www.mermaidchart.com"
MERMAID_ACCESS_TOKEN = "MERMAID_ACCESS_TOKEN"
DEFAULT_THEME = "light"  # Or "dark"

# --- Logging Setup ---
# Log to stderr to avoid interfering with stdio JSON communication
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


# --- Pydantic Input Model ---
class RenderMermaidChartInput(BaseModel):
    mermaid_code: str = Field(..., description="The Mermaid diagram code.")
    output_path: str = Field(
        ...,
        description="The file path where the PNG image should be saved (e.g., 'output/diagram.png').",
    )
    theme: Optional[str] = Field(
        default=DEFAULT_THEME, description="Theme for rendering ('light' or 'dark')."
    )


# --- Service Class for API Interaction (remains mostly the same) ---
class MermaidChartService:
    """Handles communication with the Mermaid Chart API."""

    # ... (Keep the MermaidChartService class exactly as defined in the previous version) ...
    # Including: __init__, _request, get_projects, create_document, get_png
    def __init__(self, access_token: str):
        if not access_token:
            # Log error to stderr
            logger.error("Access token cannot be empty.")
            raise ValueError("Access token cannot be empty.")
        self.access_token = access_token
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {self.access_token}"})
        self.base_url = BASE_URL

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Helper method for making API requests."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {method} {url} - {e}")
            error_detail = "No specific error detail provided."
            if e.response is not None:
                try:
                    error_data = e.response.json()
                    error_detail = error_data.get("message", json.dumps(error_data))
                except json.JSONDecodeError:
                    error_detail = e.response.text
            logger.error(f"Error detail: {error_detail}")
            raise  # Re-raise the exception after logging

    def get_projects(self) -> List[Dict[str, Any]]:
        """Fetches the list of projects for the user."""
        logger.info("Fetching projects...")
        endpoint = "/rest-api/projects"
        response = self._request("GET", endpoint)
        projects = response.json()
        logger.info(f"Found {len(projects)} projects.")
        return projects

    def create_document(self, code: str, project_id: str) -> Dict[str, Any]:
        """Creates a new document with the given Mermaid code in a project."""
        logger.info(f"Creating document in project {project_id}...")
        endpoint = f"/rest-api/projects/{project_id}/documents"
        payload = {"code": code}
        response = self._request("POST", endpoint, json=payload)
        document = response.json()
        logger.info(f"Document created successfully: ID {document.get('documentID')}")
        return document

    def get_png(
        self, document_id: str, major: str, minor: str, theme: str = DEFAULT_THEME
    ) -> bytes:
        """Retrieves the PNG image data for a specific document version."""
        logger.info(
            f"Fetching PNG for document {document_id} v{major}.{minor} (theme: {theme})..."
        )
        major_str = str(major)
        minor_str = str(minor)
        endpoint = f"/raw/{document_id}?version=v{major_str}.{minor_str}&theme={theme}&format=png"
        response = self._request("GET", endpoint)
        logger.info(f"PNG data received ({len(response.content)} bytes).")
        return response.content


# --- MCP Server Implementation ---
async def serve() -> None:
    logger.info("Initializing Mermaid MCP server...")
    server = Server("mcp-mermaid")  # Use a unique name for the server

    # Tool implementation function (moved outside the class structure for simplicity, similar to docx_replace)
    async def _render_mermaid_chart_impl(
        mermaid_code: str, output_path: str, theme: str
    ) -> Dict[str, Any]:
        """Internal logic for rendering the chart."""
        access_token = os.environ.get(MERMAID_ACCESS_TOKEN)
        if not access_token:
            raise ValueError(
                f"{MERMAID_ACCESS_TOKEN} environment variable is required."
            )

        service = MermaidChartService(access_token)

        if not mermaid_code:
            raise ValueError("Mermaid code cannot be empty.")
        if not output_path:
            raise ValueError("Output path cannot be empty.")
        if not output_path.lower().endswith(".png"):
            logger.warning("Output path does not end with .png, appending it.")
            output_path += ".png"

        # 1. Get projects and select the first one
        projects = service.get_projects()  # This is synchronous, might block asyncio loop if slow. Consider running in executor if needed.
        if not projects:
            raise RuntimeError(
                "No projects found. Please create a project in Mermaid Chart."
            )
        project_id = projects[0].get("id")
        if not project_id:
            raise RuntimeError("Could not determine Project ID from Mermaid Chart.")
        logger.info(f"Using project ID: {project_id}")

        # 2. Create the document
        document = service.create_document(mermaid_code, project_id)  # Synchronous
        document_id = document.get("documentID")
        major = document.get("major")
        minor = document.get("minor")

        if not all([document_id, major is not None, minor is not None]):
            raise RuntimeError(
                "Failed to create document or get necessary details (ID, version)."
            )

        # 3. Get the PNG data
        png_data = service.get_png(
            document_id, str(major), str(minor), theme
        )  # Synchronous

        # 4. Save the PNG data to the output file
        abs_output_path = os.path.abspath(output_path)
        logger.info(f"Saving PNG image to: {abs_output_path}")
        os.makedirs(os.path.dirname(abs_output_path), exist_ok=True)
        # File I/O is blocking, run in executor for better async performance
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, _save_file, abs_output_path, png_data)
        # with open(abs_output_path, "wb") as f:
        #     f.write(png_data) # Blocking I/O

        logger.info("Mermaid chart rendered successfully.")
        return {"output_path": abs_output_path, "document_id": document_id}

    def _save_file(path: str, data: bytes):
        """Helper function to run blocking file write in executor."""
        with open(path, "wb") as f:
            f.write(data)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        logger.info("Executing list_tools request")
        return [
            Tool(
                name="render_mermaid_chart",
                description="Renders Mermaid code using the Mermaid Chart API and saves it as a PNG image.",
                inputSchema=RenderMermaidChartInput.model_json_schema(),
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        logger.info(
            f"Executing call_tool request for '{name}' with arguments: {arguments}"
        )
        result_data = {}
        try:
            if name == "render_mermaid_chart":
                # Validate input using Pydantic model
                validated_input = RenderMermaidChartInput(**arguments)
                # Call the implementation function
                # Run the potentially blocking network/file operations
                result_data = await _render_mermaid_chart_impl(
                    mermaid_code=validated_input.mermaid_code,
                    output_path=validated_input.output_path,
                    theme=validated_input.theme
                    or DEFAULT_THEME,  # Ensure theme has a value
                )
                logger.info(f"Tool '{name}' executed successfully.")
                # Wrap successful result in TextContent
                return [TextContent(type="text", text=json.dumps(result_data))]
            else:
                logger.error(f"Unknown tool name: {name}")
                raise ValueError(f"Unknown tool: {name}")

        except (ValueError, RuntimeError, requests.exceptions.RequestException) as e:
            logger.error(f"Error executing tool '{name}': {e}", exc_info=True)
            # Wrap error in TextContent
            error_result = {"error": str(e)}
            return [TextContent(type="text", text=json.dumps(error_result))]
        except Exception as e:
            logger.exception(
                f"Unexpected error executing tool '{name}'."
            )  # Logs traceback
            error_result = {"error": f"An unexpected error occurred: {e}"}
            return [TextContent(type="text", text=json.dumps(error_result))]

    # --- Run the server using stdio ---
    logger.info("Starting stdio server loop...")
    options = server.create_initialization_options()
    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.info("stdio streams opened. Running server...")
            await server.run(
                read_stream, write_stream, options, raise_exceptions=False
            )  # Set raise_exceptions=False to handle errors gracefully within call_tool
    except Exception as e:
        logger.exception(
            "Critical error during server setup or run."
        )  # Log any error during setup/run
    finally:
        logger.info("Mermaid MCP server finished.")


# --- Main execution ---
def main():
    # Ensure access token is checked early, though actual use is in call_tool
    token = os.environ.get(MERMAID_ACCESS_TOKEN)
    if not token:
        logger.error(
            f"CRITICAL: Environment variable {MERMAID_ACCESS_TOKEN} is not set. The MCP will not be able to function."
        )
        # Exit early if the token is missing, as initialization within call_tool will fail anyway.
        sys.exit(f"Error: {MERMAID_ACCESS_TOKEN} not set.")

    # Run the asyncio event loop
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("Shutdown requested via KeyboardInterrupt.")
    except Exception as e:
        logger.exception(
            "Application level error."
        )  # Catch errors during asyncio.run if any


if __name__ == "__main__":
    main()
