"""CLI tool to run defect detection on a single image."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.detection.yolo_detector import YOLODetector
from src.processing.image_processor import ImageProcessor


def main():
    parser = argparse.ArgumentParser(description="Detect infrastructure defects in an image")
    parser.add_argument("image", help="Path to the image file")
    parser.add_argument("--output", "-o", help="Path to save annotated image")
    parser.add_argument("--confidence", "-c", type=float, default=0.5, help="Confidence threshold")
    args = parser.parse_args()

    print(f"Processing: {args.image}")
    processor = ImageProcessor()
    detector = YOLODetector(confidence=args.confidence)

    image = processor.preprocess(args.image)
    detections = detector.detect(image)

    print(f"\nFound {len(detections)} defect(s):")
    for i, det in enumerate(detections, 1):
        print(f"  {i}. {det['class']} — confidence: {det['confidence']:.2%}, severity: {det['severity']}")

    if args.output:
        annotated = processor.draw_annotations(image, detections)
        processor.save(annotated, args.output)
        print(f"\nAnnotated image saved to: {args.output}")


if __name__ == "__main__":
    main()
