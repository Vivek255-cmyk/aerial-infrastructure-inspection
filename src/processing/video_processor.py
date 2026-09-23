"""OpenCV-based video processing for drone footage analysis."""

from pathlib import Path

import cv2
import numpy as np

from src.processing.image_processor import ImageProcessor


class VideoProcessor:
    """Extract and process frames from aerial inspection videos."""

    def __init__(self, frame_interval: int = 30):
        self.frame_interval = frame_interval
        self.image_processor = ImageProcessor()

    def extract_frames(
        self, video_path: str | Path, output_dir: str | Path | None = None
    ) -> list[np.ndarray]:
        """Extract frames at regular intervals from video."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise FileNotFoundError(f"Could not open video: {video_path}")

        frames = []
        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % self.frame_interval == 0:
                processed = self.image_processor.enhance(frame)
                frames.append(processed)

                if output_dir:
                    out_path = Path(output_dir) / f"frame_{frame_count:06d}.jpg"
                    self.image_processor.save(processed, out_path)

            frame_count += 1

        cap.release()
        return frames

    def process_video(
        self,
        video_path: str | Path,
        detector,
        output_path: str | Path | None = None,
    ) -> list[dict]:
        """Run defect detection on every Nth frame of a video."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise FileNotFoundError(f"Could not open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        writer = None
        if output_path:
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

        all_detections = []
        frame_count = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_count % self.frame_interval == 0:
                detections = detector.detect(frame)
                annotated = self.image_processor.draw_annotations(frame, detections)

                for det in detections:
                    det["frame_number"] = frame_count
                    det["timestamp_sec"] = frame_count / fps
                    all_detections.append(det)

                if writer:
                    writer.write(annotated)
            elif writer:
                writer.write(frame)

            frame_count += 1

        cap.release()
        if writer:
            writer.release()

        return all_detections

    @staticmethod
    def get_video_info(video_path: str | Path) -> dict:
        cap = cv2.VideoCapture(str(video_path))
        info = {
            "fps": cap.get(cv2.CAP_PROP_FPS),
            "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
            "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "duration_sec": 0,
        }
        if info["fps"] > 0:
            info["duration_sec"] = info["frame_count"] / info["fps"]
        cap.release()
        return info
