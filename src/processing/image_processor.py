"""OpenCV-based image preprocessing for aerial inspection."""

from pathlib import Path

import cv2
import numpy as np


class ImageProcessor:
    """Preprocess drone-captured images for defect detection."""

    def __init__(self, target_size: tuple[int, int] = (640, 640)):
        self.target_size = target_size

    def load(self, path: str | Path) -> np.ndarray:
        image = cv2.imread(str(path))
        if image is None:
            raise FileNotFoundError(f"Could not load image: {path}")
        return image

    def resize(self, image: np.ndarray) -> np.ndarray:
        return cv2.resize(image, self.target_size, interpolation=cv2.INTER_AREA)

    def enhance(self, image: np.ndarray) -> np.ndarray:
        """Apply CLAHE contrast enhancement for better defect visibility."""
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l_channel, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_channel = clahe.apply(l_channel)
        enhanced = cv2.merge([l_channel, a, b])
        return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)

    def denoise(self, image: np.ndarray) -> np.ndarray:
        return cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)

    def extract_edges(self, image: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        return cv2.Canny(blurred, 50, 150)

    def validate_quality(self, image: np.ndarray) -> tuple[bool, str]:
        """Check whether image quality is suitable for reliable inspection."""
        from src.detection.cv_detector import CVDefectDetector
        detector = CVDefectDetector()
        return detector.check_quality(image)

    def preprocess(self, path: str | Path) -> np.ndarray:
        """Full preprocessing pipeline: load → enhance → denoise → resize."""
        image = self.load(path)
        image = self.enhance(image)
        image = self.denoise(image)
        return self.resize(image)

    def save(self, image: np.ndarray, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), image)

    def draw_annotations(
        self,
        image: np.ndarray,
        detections: list[dict],
        color_map: dict[str, tuple] | None = None,
    ) -> np.ndarray:
        """Draw bounding boxes, semi-transparent highlight masks, and labels on image."""
        annotated = image.copy()
        overlay = image.copy()

        severity_colors = {
            "low": (0, 255, 128),        # Green-cyan
            "medium": (0, 215, 255),      # Yellow-gold (BGR)
            "high": (0, 128, 255),        # Orange (BGR)
            "critical": (0, 0, 255),      # Red (BGR)
        }

        for det in detections:
            x1, y1, x2, y2 = det["bbox"]
            label = det.get("class", "Defect")
            severity = det.get("severity", "medium").lower()
            conf = det.get("confidence", 0.0)

            color = (color_map or {}).get(label) or severity_colors.get(severity, (0, 0, 255))

            # Translucent mask overlay over bounding region
            cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)

            # Solid bounding box frame
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)

            # Label badge
            text = f"{label} ({severity.upper()}) {int(conf * 100)}%"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 2
            text_size = cv2.getTextSize(text, font, font_scale, thickness)[0]

            label_bg_y1 = max(0, y1 - text_size[1] - 10)
            label_bg_y2 = y1
            cv2.rectangle(annotated, (x1, label_bg_y1), (x1 + text_size[0] + 12, label_bg_y2), color, -1)
            cv2.putText(
                annotated,
                text,
                (x1 + 6, y1 - 4),
                font,
                font_scale,
                (255, 255, 255),
                thickness,
                lineType=cv2.LINE_AA,
            )

        # Blend semi-transparent highlight mask (25% opacity)
        cv2.addWeighted(overlay, 0.25, annotated, 0.75, 0, annotated)
        return annotated
