"""CLI tool to run a full simulated drone inspection pipeline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.drone.flight_controller import FlightController, FlightPlan
from src.detection.yolo_detector import YOLODetector
from src.models.predictive_maintenance import PredictiveMaintenanceEngine
from config.settings import Settings


def main():
    settings = Settings()
    print("Starting simulated aerial inspection...\n")

    # 1. Plan flight
    plan = FlightPlan.from_grid(
        center_lat=28.6139, center_lon=77.2090,
        width_m=200, height_m=200, altitude_m=50,
    )
    print(f"Flight plan: {len(plan.waypoints)} waypoints")

    # 2. Execute flight
    controller = FlightController(simulation=settings.DRONE_SIMULATION_MODE)
    controller.connect()
    controller.arm_and_takeoff(50)
    captures = controller.execute_plan(plan)
    print(f"Captured {len(captures)} images")

    # 3. Detect defects (on any available test images)
    detector = YOLODetector()
    all_defects = []
    raw_dir = settings.DATA_DIR / "raw"

    for capture in captures:
        img_path = Path(capture["image_path"])
        if img_path.exists():
            detections = detector.detect(str(img_path))
            for det in detections:
                det["asset_id"] = 1
                det["detected_at"] = capture["timestamp"]
            all_defects.extend(detections)

    print(f"Total defects detected: {len(all_defects)}")

    # 4. Predictive maintenance
    if all_defects:
        engine = PredictiveMaintenanceEngine()
        predictions = engine.predict_risk(all_defects)
        print("\nMaintenance predictions:")
        for p in predictions:
            print(f"  Asset #{p['asset_id']}: {p['risk_level']} — {p['recommended_action']}")

    controller.return_to_launch()
    print("\nInspection complete.")


if __name__ == "__main__":
    main()
