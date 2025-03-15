import subprocess
import logging
import time


class DockerService:
    """Service to manage Docker operations for PlantUML server."""

    def check_install(self) -> None:
        """Check if Docker is installed."""
        try:
            subprocess.run(["docker", "--version"], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            logging.error("Docker is not installed or not found in PATH.")
            raise

    def start_server(self) -> None:
        """Start the PlantUML server in a Docker container."""
        try:
            subprocess.run(
                [
                    "docker",
                    "run",
                    "-d",
                    "-p",
                    "8080:8080",
                    "--name",
                    "plantuml-server",
                    "plantuml/plantuml-server",
                ],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to start Docker container: {e}")
        except Exception as e:
            logging.error(f"Unexpected error: {e}")

    def is_running(self) -> bool:
        """Check if the PlantUML server is running."""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    "name=plantuml-server",
                    "--filter",
                    "status=running",
                    "--format",
                    "{{.Names}}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return "plantuml-server" in result.stdout
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to check Docker container status: {e}")
            return False

    def wait_until_ready(self, timeout: int = 30) -> None:
        """Wait until the PlantUML server is ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(1)
            if self.is_running():
                return
        logging.error("Timeout waiting for the PlantUML server to start.")
        raise TimeoutError("PlantUML server did not start within the timeout period.")
