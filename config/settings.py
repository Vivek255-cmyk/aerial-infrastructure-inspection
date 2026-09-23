import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    """Application configuration loaded from environment variables."""

    # Flask
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key")
    FLASK_ENV: str = os.getenv("FLASK_ENV", "development")
    FLASK_DEBUG: bool = os.getenv("FLASK_DEBUG", "0") == "1"
    FLASK_HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
    FLASK_PORT: int = int(os.getenv("PORT", os.getenv("FLASK_PORT", "5000")))

    # Paths
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    MODELS_DIR: Path = BASE_DIR / "models" / "weights"
    REPORTS_DIR: Path = BASE_DIR / "reports"

    # MySQL
    MYSQL_HOST: str = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER: str = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "aerial_inspection")

    @property
    def MYSQL_URI(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    @property
    def DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        db_path = self.BASE_DIR / "data" / "inspection.db"
        return f"sqlite:///{db_path.as_posix()}"

    # MongoDB
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DATABASE: str = os.getenv("MONGO_DATABASE", "aerial_inspection")

    # YOLO
    YOLO_MODEL_PATH: str = os.getenv(
        "YOLO_MODEL_PATH", str(MODELS_DIR / "yolov8n.pt")
    )
    CONFIDENCE_THRESHOLD: float = float(os.getenv("CONFIDENCE_THRESHOLD", "0.5"))

    # Drone
    DRONE_CONNECTION_STRING: str = os.getenv(
        "DRONE_CONNECTION_STRING", "serial:///dev/ttyUSB0:57600"
    )
    DRONE_SIMULATION_MODE: bool = os.getenv("DRONE_SIMULATION_MODE", "true") == "true"

    # Defect classes for infrastructure inspection
    DEFECT_CLASSES: list[str] = [
        "crack",
        "corrosion",
        "spalling",
        "vegetation_overgrowth",
        "insulator_damage",
        "rust",
        "missing_component",
        "structural_deformation",
    ]
