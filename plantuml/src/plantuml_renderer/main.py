import subprocess
import logging
import click
from services.docker_service import DockerService
from services.plantuml_service import PlantumlService


@click.command()
@click.argument("input", type=click.Path(exists=True))
@click.option("-o", "--output", default="diagram.png")
def main(input, output):
    docker_service = DockerService()
    plantuml_service = PlantumlService()

    docker_service.check_install()
    if not docker_service.is_running():
        docker_service.start_server()
    docker_service.wait_until_ready(45)

    try:
        plantuml_service.render_diagram(input, output)
    except Exception as e:
        logging.error(f"Error: {e}")
