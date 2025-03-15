# PlantUML Docker Renderer CLI Tool (uv Edition)

> Build a CLI tool that manages a PlantUML Docker server and generates diagrams using uv for dependency management

## Objectives
- Start/stop Docker container programmatically
- Generate PNG diagrams via CLI
- Use `uv` for dependency management and environment setup

## Low-level Tasks
1. **CREATE pyproject.toml**
   ```toml
   [project]
   name = "plantuml-docker-renderer"
   version = "0.1.0"
   dependencies = [
     "plantuml = \"^1.6\"",
     "click = \"^8.1.3\"",
     "docker = \"^5.0.3\"",
   ]

   [tool.uv]
   default-python = "3.11"  # Default Python version
   ```

2. **CREATE plantuml_renderer.py**
   ```python
   import subprocess
   import logging
   import click
   from plantuml import PlantUML

   @click.command()
   @click.argument("input", type=click.Path(exists=True))
   @click.option("-o", "--output", default="diagram.png")
   def main(input, output):
       if not is_server_running():
           start_docker_server()
       try:
           render_diagram(input, output)
       except Exception as e:
           logging.error(f"Error: {e}")

   def start_docker_server():
       # Docker management code here
       pass

   def is_server_running():
       # Check Docker container status
       pass
   ```

3. **CREATE Dockerfile (Optional Production Setup)**
   ```dockerfile
   FROM python:3.11-slim

   # Install uv and dependencies
   RUN pip install uv
   COPY pyproject.toml .
   RUN uv install  # Install dependencies via uv
   COPY . .
   CMD ["uv", "run", "plantuml_renderer.py"]
   ```

4. **CREATE .gitignore**
   ```
   __pycache__/
   *.png
   *.pyc
   /dist/
   /build/
   ```

## Implementation Notes
- **Dependency Installation**: Run `uv install` to setup dependencies
- **Running the CLI**: Use `uv run plantuml_renderer.py input.puml -o output.png`
- **Docker Setup**: Build with `docker build -t plantuml-renderer .` and run with `docker run -p 8080:8080 plantuml-renderer`
