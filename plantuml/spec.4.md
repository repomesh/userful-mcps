# Implement Stdio MCP Server for plantuml-python

> Create a stdio-based MCP server for plantuml-python that renders diagrams, checks Docker status, and handles file I/O. Reuse patterns from `useful-mcps` and integrate with Docker/PlantUML services.

## Objectives
- Create `plantuml_mcp.py` as the entrypoint with a `serve()` function
- Register 3 core tools: `render_diagram`, `check_docker`, `convert_format`
- Integrate with `DockerService` for Docker health checks
- Handle base64/file I/O using helpers from `docx_replace_mcp.py`
- Ensure temp files are cleaned up after processing

## Contexts
- `plantuml_renderer.py`: Contains `render_diagram()` logic
- `./services/docker_service.py`: Docker management (has `DockerService` class)
- `../useful-mcps/docx_replace_mcp.py`: Reference for stdio server patterns
- `../useful-mcps/ytdlp_mcp.py`: Tool registration examples

## Low-level Tasks
1. **CREATE plantuml_mcp.py**
   - Define `serve()` function using MCP's `stdio_server` framework
   - Import `Server`, `Tool`, `TextContent` from `mcp.stdio`
   - Initialize server with name `"mcp-plantuml"`

2. **REGISTER TOOLS**
   - UPDATE `list_tools()` to return 3 tools:
     ```python
     Tool(
         name="render_diagram",
         description="Render PlantUML text to image/PDF",
         inputSchema={...},
     ),
     Tool(
         name="check_docker",
         description="Verify Docker is running for PlantUML server",
         inputSchema={...},
     ),
     Tool
         name="convert_format",
         description="Convert PlantUML output between formats (PNG/SVG/PDF)",
         inputSchema={...},
     )
     ```

3. **IMPLEMENT `call_tool()` LOGIC**
   - UPDATE `call_tool()` to handle:
     - `render_diagram`: Calls `render_diagram()` from `plantuml_renderer.py`
     - `check_docker`: Uses `DockerService().is_running()`
     - `convert_format`: Adds format conversion logic (e.g., PNG → SVG)

4. **ADD I/O HANDLERS**
   - COPY `_handle_input_file` and `_encode_file_if_needed` from `docx_replace_mcp.py`
   - ADAPT to handle PlantUML-specific file types (e.g., `.puml` → `.png`)

5. **DOCKER HEALTH CHECK**
   - MODIFY `serve()` to run Docker check on startup:
   ```python
   docker_service = DockerService()
   if not docker_service.is_running():
       raise RuntimeError("Docker must be running for PlantUML server.")
   ```

6. **CLEANUP LOGIC**
   - Add temp file cleanup in `call_tool()` after processing:
   ```python
   finally:
       if is_temp:
           os.unlink(temp_file.name)
   ```

## Dependencies
- `mcp.stdio` for server infrastructure
- `plantuml-python`'s Docker/PlantUML services
- Reuse I/O helpers from `useful-mcps`
