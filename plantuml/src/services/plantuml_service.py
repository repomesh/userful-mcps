from plantuml import PlantUML

class PlantumlService:
    """Service to handle PlantUML diagram rendering."""

    def render_diagram(self, input: str, output: str) -> None:
        """Render a diagram from input file to output file."""
        server = PlantUML(url="http://localhost:8080/png/")
        server.processes_file(input, output)
