# Aerial Infrastructure Inspection & Predictive Maintenance System

An AI-powered system for automated drone-based infrastructure inspection, defect detection using YOLO, and predictive maintenance scheduling.

## Features

- **Drone Flight Planning** — Automated grid-survey patterns with waypoint generation
- **Image/Video Processing** — OpenCV preprocessing (CLAHE enhancement, denoising, edge detection)
- **Defect Detection** — YOLOv8 object detection for 8 infrastructure defect types
- **Predictive Maintenance** — ML-based failure risk prediction and maintenance scheduling
- **Web Dashboard** — Real-time monitoring, inspection upload, analytics charts
- **REST API** — Full Flask backend with MySQL/MongoDB support
- **Simulation Mode** — Test the full pipeline without a physical drone

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.x |
| Image Processing | OpenCV |
| Object Detection | YOLO (Ultralytics) |
| Deep Learning | PyTorch / TensorFlow |
| Data Analysis | NumPy, Pandas, scikit-learn |
| Backend | Flask |
| Database | MySQL (SQLAlchemy) / MongoDB |
| Frontend | HTML, CSS, JavaScript, Chart.js |
| Experimentation | Jupyter Notebook |
| Version Control | Git / GitHub |

## Project Structure

```
├── config/                  # Application settings
├── src/
│   ├── api/                 # Flask REST API & dashboard routes
│   ├── detection/           # YOLO detector & defect classifier
│   ├── processing/          # OpenCV image & video processors
│   ├── models/              # Predictive maintenance engine
│   ├── drone/               # Flight controller & planning
│   └── database/            # SQLAlchemy models & repository
├── frontend/
│   ├── templates/           # HTML dashboard pages
│   └── static/              # CSS & JavaScript
├── notebooks/               # Jupyter notebooks for experimentation
├── scripts/                 # CLI tools
├── tests/                   # Unit tests
├── data/                    # Raw & processed images
├── models/                  # YOLO weights & dataset config
├── run.py                   # Application entry point
└── requirements.txt
```

## Quick Start

### 1. Prerequisites

- Python 3.10+
- MySQL (optional — SQLite works for development)
- Git

### 2. Setup

```bash
# Clone and enter project
cd "D:\MEGA PROJECT"

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/macOS)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Edit .env with your database credentials
```

### 3. Run the Dashboard

```bash
python run.py
```

Open **http://127.0.0.1:5000** in your browser.

### Hosting Online

The app can be deployed to any Python host that supports a web service. Render is a straightforward option:

1. Push this repository to GitHub.
2. In Render, create a **Web Service** and select the repository.
3. Use Python 3.10 or newer.
4. Set the build command to `pip install -r requirements-core.txt`.
5. Set the start command to `gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 300 run:app`.
6. Add `FLASK_ENV=production`, `FLASK_DEBUG=0`, a long random `SECRET_KEY`, and `DRONE_SIMULATION_MODE=true` as environment variables.

Set `DATABASE_URL` to a managed PostgreSQL or MySQL database for production. The default SQLite database and uploaded files are local to the server and may be lost on redeploys or restarts. The YOLO weights must also be included in the deployment or downloaded during the build; model weight files are currently ignored by Git.

### 4. CLI Tools

```bash
# Detect defects in a single image
python scripts/inspect_image.py path/to/image.jpg -o output/annotated.jpg

# Run full simulated inspection pipeline
python scripts/run_inspection.py
```

### 5. Run Tests

```bash
pytest tests/ -v
```

## Defect Classes

| Class | Description |
|-------|-------------|
| crack | Structural cracks in concrete/metal |
| corrosion | Surface corrosion and degradation |
| spalling | Concrete spalling and surface loss |
| vegetation_overgrowth | Vegetation encroaching on structures |
| insulator_damage | Power line insulator damage |
| rust | Rust formation on metal surfaces |
| missing_component | Missing bolts, plates, or parts |
| structural_deformation | Visible structural deformation |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | System health check |
| GET/POST | `/api/assets` | List/create infrastructure assets |
| POST | `/api/inspect` | Upload image and run inspection |
| POST | `/api/detect` | Detect defects (no DB save) |
| GET | `/api/inspections` | List recent inspections |
| GET | `/api/defects/<asset_id>` | Get defects for an asset |
| GET | `/api/summary` | Defect summary statistics |
| GET | `/api/predict` | Maintenance risk predictions |
| GET | `/api/drone/telemetry` | Drone telemetry data |
| POST | `/api/drone/flight-plan` | Generate grid survey plan |

## Training a Custom YOLO Model

1. Prepare your dataset in YOLO format under `data/dataset/`
2. Update `models/dataset.yaml` with your paths
3. Open `notebooks/02_model_training.ipynb` or run:

```python
from src.detection.yolo_detector import YOLODetector
detector = YOLODetector()
detector.train("models/dataset.yaml", epochs=100)
```

## Database Setup (MySQL)

```sql
CREATE DATABASE aerial_inspection;
```

Tables are auto-created on first run via SQLAlchemy.

## Drone Integration

The system runs in **simulation mode** by default. For real drone control:

1. Install dronekit: `pip install dronekit`
2. Set `DRONE_SIMULATION_MODE=false` in `.env`
3. Configure `DRONE_CONNECTION_STRING` for your flight controller

Supported: DJI (via SDK), ArduPilot/PX4 (via MAVLink/dronekit).

## Development Roadmap

- [ ] Custom YOLO model trained on infrastructure datasets
- [ ] Real-time video stream processing
- [ ] GPS-tagged defect mapping on interactive map
- [ ] Email/SMS alerts for critical defects
- [ ] Multi-drone fleet management
- [ ] PDF inspection report generation
- [ ] Mobile app for field technicians

## License

MIT
