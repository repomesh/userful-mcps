# Implement Service-Oriented Architecture for plantuml-python

> Refactor procedural code into reusable service classes for better separation of concerns

## Objectives
- Create DockerService to encapsulate all Docker-related operations
- Create PlantumlService to handle diagram rendering logic
- Decouple CLI from infrastructure concerns
- Maintain backward compatibility with existing CLI interface

## Contexts
- plantuml_renderer.py: Contains current procedural implementation
- pyproject.toml: Project configuration file

## Low-level Tasks
1. CREATE services/docker_service.py:
   - Implement DockerService class with methods:
     - check_install()
     - start_server()
     - is_running()
     - wait_until_ready()
   - Add type hints and docstrings

2. CREATE services/plantuml_service.py:
   - Implement PlantumlService class with methods:
     - render_diagram(input, output)
     - generate_diagram_code()
   - Move rendering logic from main()

3. UPDATE plantuml_renderer.py:
   - Remove Docker-related logic
   - Remove rendering logic
   - Add service class imports
   - Refactor main() to use service instances

4. UPDATE cli.py:
   - Update CLI entrypoint to use service classes
   - Maintain existing command-line interface

5. UPDATE utils.py:
   - Move utility functions to appropriate service classes
   - Remove unused helper methods

## Dependencies
- Use dependency injection for service instances in main()
- Maintain single entrypoint in cli.py

## Validation
- Existing CLI functionality must remain unchanged
- Unit tests should be updated to test services in isolation
