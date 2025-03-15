# Implement Docker Server Management Functions

> Adds robust Docker server management to the PlantUML renderer

## Objectives
- Implement `start_docker_server()` to launch PlantUML Docker container
- Implement `is_server_running()` to check container status
- Add error handling for Docker command failures
- Ensure idempotent server startup (no duplicate containers)
- Provide clear error messages for common issues

## Contexts
- plantuml_renderer.py: Core rendering logic
- pyproject.toml: Dependency management file

## Low-level Tasks
1. UPDATE plantuml_renderer.py:
   - Implement `start_docker_server()`:
     - Uses `subprocess.run` for Docker commands
     - Uses `plantuml/docker` image from Docker Hub
     - Maps port 8080 with `-p 8080:8080`
     - Handles `ContainerAlreadyRunning` scenario
   - Implement `is_server_running()`:
     - Parses `docker ps` output for container status
     - Returns boolean
   - Update `render_diagram()`:
     - Pre-check server status before rendering
     - Auto-start server if not running
   - Add exception handling blocks for:
     - Docker command failures (`subprocess.CalledProcessError`)
     - Port conflicts
     - Server startup timeouts

2. UPDATE pyproject.toml:
   - Add `click` dependency if missing (for future CLI enhancements)
   - Add comment about requiring Docker CLI in tool.poetry section

3. ADD healthcheck functionality:
   - Create `check_docker_install()` to verify Docker is installed
   - Create `wait_for_server()` with timeout logic
