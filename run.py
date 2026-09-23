"""Entry point for the Aerial Inspection System."""

import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.api.app import create_app
from config.settings import Settings


def get_local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"


app = create_app()

if __name__ == "__main__":
    settings = Settings()
    host = settings.FLASK_HOST
    port = settings.FLASK_PORT
    local_ip = get_local_ip()
    print("=" * 60)
    print("  Aerial Infrastructure Inspection System")
    print("  Predictive Maintenance Dashboard")
    print("=" * 60)
    print(f"  Local: http://127.0.0.1:{port}")
    print(f"  Phone/lan: http://{local_ip}:{port}")
    print(f"  Environment: {settings.FLASK_ENV}")
    print(f"  Drone mode: {'Simulation' if settings.DRONE_SIMULATION_MODE else 'Live'}")
    print("=" * 60)
    app.run(host=host, port=port, debug=settings.FLASK_DEBUG)
