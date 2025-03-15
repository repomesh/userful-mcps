import base64
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool
from services.docker_service import DockerService
from plantuml_renderer import main as render_diagram


async def serve():
    server = Server(name="mcp-plantuml")

    @server.list_tools()
    async def list_tools():
        return [
            Tool(
                name="render_diagram",
                description="Render PlantUML text to image/PDF",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "input": {"type": "string"},
                        "output": {"type": "string"},
                    },
                },
            ),
            Tool(
                name="check_docker",
                description="Verify Docker is running for PlantUML server",
                inputSchema={"type": "object", "properties": {}},
            ),
            Tool(
                name="convert_format",
                description="Convert PlantUML output between formats (PNG/SVG/PDF)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "input": {"type": "string"},
                        "format": {"type": "string"},
                    },
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(tool_name: str, input_data: dict) -> list[TextContent]:
        if tool_name == "render_diagram":
            input_file = _handle_input_file(input_data["input"])
            output_file = input_data["output"]
            render_diagram(input_file, output_file)
            return [TextContent(type="text", text=f"Diagram rendered to {output_file}")]

        elif tool_name == "check_docker":
            docker_service = DockerService()
            if docker_service.is_running():
                return [TextContent(type="text", text="Docker is running.")]
            else:
                return [TextContent(type="text", text="Docker is not running.")]

        elif tool_name == "convert_format":
            # Placeholder for format conversion logic
            return [
                TextContent(type="text", text="Format conversion not yet implemented.")
            ]
        else:
            return [TextContent(type="text", text="Tool name is invalid")]

    def _handle_input_file(input_data):
        if input_data.startswith("data:"):
            header, encoded = input_data.split(",", 1)
            data = base64.b64decode(encoded)
            temp_file = open("temp.puml", "wb")
            temp_file.write(data)
            temp_file.close()
            return temp_file.name
        return input_data

    docker_service = DockerService()
    if not docker_service.is_running():
        raise RuntimeError("Docker must be running for PlantUML server.")

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)


def main():
    import asyncio

    asyncio.run(serve())
