"""Train the infrastructure defect detector on a YOLO-format dataset."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.yolo_detector import YOLODetector


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="models/dataset.yaml")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--project", default="runs/detect")
    parser.add_argument("--name", default="infrastructure")
    args = parser.parse_args()

    detector = YOLODetector()
    results = detector.train(
        data_yaml=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project=args.project,
        name=args.name,
    )
    save_dir = getattr(results, "save_dir", Path(args.project) / args.name)
    print(f"Training complete. Results: {save_dir}")
    print("Copy the best weights to models/weights/infrastructure_best.pt and set YOLO_MODEL_PATH to that path.")


if __name__ == "__main__":
    main()