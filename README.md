# Useful Model Context Protocol Servers (MCPS)

A collection of standalone Python scripts that implement Model Context Protocol (MCP) servers for various utility functions. Each server provides specialized tools that can be used by AI assistants or other applications that support the MCP protocol.

## What is MCP?

The Model Context Protocol (MCP) is a standardized way for AI assistants to interact with external tools and services. It allows AI models to extend their capabilities by calling specialized functions provided by MCP servers.

## Available Servers

### YouTube Data Extractor (`ytdlp_mcp.py`)

A server that extracts information from YouTube videos using yt-dlp.

**Tools:**

- **Extract Chapters**: Get chapter information from a YouTube video
- **Extract Subtitles**: Get subtitles from a YouTube video for specific chapters

### Word Document Processor (`docx_replace_mcp.py`)

A server for manipulating Word documents, including template processing and PDF conversion.

**Tools:**

- **Process Template**: Replace placeholders in Word templates and manage content blocks
- **Get Template Keys**: Extract all replacement keys from a Word document template
- **Convert to PDF**: Convert a Word document (docx) to PDF format

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/useful-mcps.git
   cd useful-mcps
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Usage

### Running a Server

Each MCP server is a standalone Python script that can be run directly:

```bash
python ytdlp_mcp.py
```

or

```bash
python docx_replace_mcp.py
```

### Connecting to a Server

MCP servers communicate via standard input/output streams. To connect to a server from your application, you need to add following configuration to your MCP client:

- For Docx Tool

```
  "docx_replace": {
    "name": "docx",
    "command": "/home/quy.truong/.local/bin/uv",
    "args": [
      "run",
      "/home/quy.truong/sources/github.com/daltonnyx/useful-mcps/docx_replace_mcp.py"
    ],
    "env": {},
    "enabled": true
  }
```

- For youtube tool

```
  "ytdlp": {
    "name": "youtube",
    "command": "/home/quy.truong/.local/bin/uv",
    "args": [
      "run",
      "/home/quy.truong/sources/github.com/daltonnyx/useful-mcps/ytdlp_mcp.py"
    ],
    "env": {},
    "enabled": true
  }
```

## Tool-Specific Usage

### YouTube Data Extractor

#### Extract Chapters

```python
# Example arguments for extracting chapters
arguments = {
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
}
```

#### Extract Subtitles

```python
# Example arguments for extracting subtitles
arguments = {
    "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "en",
    "chapters": [
        {"title": "Introduction", "start_time": "00:00:00", "end_time": "00:01:30"}
    ]
}
```

### Word Document Processor

#### Process Template

```python
# Example arguments for processing a template
arguments = {
    "template_file": "/path/to/template.docx",  # Or base64-encoded content
    "replacements": {
        "name": "John Doe",
        "date": "2023-05-15"
    },
    "blocks": {
        "optional_section": True,  # Include this section
        "alternative_section": False  # Exclude this section
    },
    "output_filename": "/path/to/output.docx"  # Optional
}
```

#### Get Template Keys

```python
# Example arguments for getting template keys
arguments = {
    "template_file": "/path/to/template.docx"  # Or base64-encoded content
}
```

#### Convert to PDF

```python
# Example arguments for converting to PDF
arguments = {
    "docx_file": "/path/to/document.docx",  # Or base64-encoded content
    "pdf_output": "/path/to/output.pdf"  # Optional
}
```

## Development

### Adding a New MCP Server

To create a new MCP server:

1. Create a new Python file (e.g., `new_service_mcp.py`)
2. Implement the required classes and functions
3. Define a `serve()` function as the entry point

Basic template:

```python
import json
import logging
from typing import List, Dict, Any
from mcp import Server, Tool, TextContent, stdio_server

class MyTools:
    TOOL_NAME = "my.tool"

class MyInput:
    # Define your input schema using Pydantic
    pass

class MyService:
    def __init__(self):
        pass
        
    def my_function(self, param1, param2):
        # Implement your tool functionality
        return {"content": "Result"}

async def serve() -> None:
    server = Server("mcp-my-service")
    service = MyService()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=MyTools.TOOL_NAME,
                description="Description of my tool",
                inputSchema=MyInput.model_json_schema(),
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        try:
            if name == MyTools.TOOL_NAME:
                result = service.my_function(
                    arguments["param1"],
                    arguments["param2"],
                )
                return [TextContent(type="text", text=result["content"])]
            else:
                raise ValueError(f"Unknown tool: {name}")
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}))]

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options)

if __name__ == "__main__":
    import asyncio
    asyncio.run(serve())
```

### Testing

Run the tests using pytest:

```bash
pytest tests/
```

## License

[MIT License](LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
