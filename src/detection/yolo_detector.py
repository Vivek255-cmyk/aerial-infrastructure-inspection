"""YOLO-based object detection for infrastructure defects with CV fallback."""

from pathlib import Path

import cv2
import numpy as np
import yaml

from config.settings import Settings
from src.detection.cv_detector import CVDefectDetector


class YOLODetector:
    """Detect infrastructure defects using Ultralytics YOLO with computer vision fallback."""

    INFRASTRUCTURE_CLASSES = {
        "crack", "major crack", "corrosion", "corrosion/rust", "rust",
        "spalling", "water/moisture damage", "surface damage",
        "paint/plaster deterioration", "paint/coating deterioration",
        "concrete damage", "missing_component", "structural_deformation"
    }

    def __init__(self, model_path: str | None = None, confidence: float | None = None):
        settings = Settings()
        self.model_path = model_path or settings.YOLO_MODEL_PATH
        self.confidence = confidence or settings.CONFIDENCE_THRESHOLD
        self.model = None
        self.cv_detector = CVDefectDetector()
        self._load_model()

    def _load_model(self) -> None:
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
        except Exception:
            self.model = None

    def detect(self, image: np.ndarray | str | Path, asset_type: str = "building_wall") -> list[dict]:
        """Run detection on an image and return structured results."""
        if isinstance(image, (str, Path)):
            image = cv2.imread(str(image))
            if image is None:
                raise FileNotFoundError(f"Could not load image: {image}")

        detections = []

        if self.model is not None:
            try:
                results = self.model(image, conf=self.confidence, verbose=False)
                for result in results:
                    boxes = result.boxes
                    if boxes is None:
                        continue

                    for box in boxes:
                        x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                        conf = float(box.conf[0])
                        cls_id = int(box.cls[0])
                        class_name = str(result.names[cls_id]).lower()

                        if class_name in self.INFRASTRUCTURE_CLASSES:
                            detections.append({
                                "class": class_name.title(),
                                "confidence": round(conf, 4),
                                "bbox": [x1, y1, x2, y2],
                                "severity": self._estimate_severity(class_name, conf, x2 - x1, y2 - y1),
                            })
            except Exception:
                pass

        # If YOLO returned 0 defect detections, use CVDefectDetector
        if not detections:
            cv_dets = self.cv_detector.detect_defects(image, asset_type=asset_type)
            detections.extend(cv_dets)

        return detections

    def detect_batch(self, images: list[np.ndarray], asset_type: str = "building_wall") -> list[list[dict]]:
        return [self.detect(img, asset_type=asset_type) for img in images]

    def train(
        self,
        data_yaml: str | Path,
        epochs: int = 100,
        imgsz: int = 640,
        batch: int = 16,
        project: str | Path = "runs/detect",
        name: str = "infrastructure",
    ):
        """Fine-tune YOLO on a validated YOLO-format infrastructure dataset."""
        dataset_path = Path(data_yaml).resolve()
        if not dataset_path.exists():
            raise FileNotFoundError(f"Dataset configuration not found: {dataset_path}")

        with dataset_path.open("r", encoding="utf-8") as stream:
            config = yaml.safe_load(stream) or {}

        required = {"path", "train", "val", "names"}
        missing = required.difference(config)
        if missing:
            raise ValueError(f"Dataset configuration is missing: {', '.join(sorted(missing))}")

        dataset_root = Path(config["path"])
        if not dataset_root.is_absolute():
            dataset_root = (dataset_path.parent / dataset_root).resolve()

        for split in ("train", "val"):
            split_path = Path(config[split])
            if not split_path.is_absolute():
                split_path = dataset_root / split_path
            if not split_path.exists():
                raise FileNotFoundError(f"{split} images directory not found: {split_path}")

        names = config["names"]
        class_count = len(names) if isinstance(names, (list, dict)) else 0
        if class_count != 8:
            raise ValueError(f"Expected 8 defect classes, found {class_count}")
        if epochs < 1 or imgsz < 32 or batch == 0:
            raise ValueError("epochs and imgsz must be positive, and batch cannot be zero")

        from ultralytics import YOLO

        model = YOLO(self.model_path)
        return model.train(
            data=str(dataset_path),
            epochs=epochs,
            imgsz=imgsz,
            batch=batch,
            project=str(project),
            name=name,
            pretrained=True,
        )

    @staticmethod
    def _estimate_severity(
        class_name: str, confidence: float, width: int, height: int
    ) -> str:
        """Estimate defect severity based on class, confidence, and size."""
        area = width * height
        high_severity_classes = {"structural_deformation", "missing_component", "crack", "major crack"}

        if class_name in high_severity_classes and confidence > 0.7 and area > 5000:
            return "critical"
        if confidence > 0.6 and area > 2000:
            return "high"
        if confidence > 0.4:
            return "medium"
        return "low"
