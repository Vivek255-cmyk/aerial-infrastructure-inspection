"""Tests for defect detection, image processing, condition scoring, and flight control."""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.processing.image_processor import ImageProcessor
from src.detection.defect_classifier import DefectClassifier
from src.detection.cv_detector import CVDefectDetector
from src.detection.yolo_detector import YOLODetector
from src.models.predictive_maintenance import PredictiveMaintenanceEngine
from src.drone.flight_controller import FlightPlan, FlightController
from src.database.repository import InspectionRepository


class TestImageProcessor:
    def test_enhance_does_not_change_shape(self):
        processor = ImageProcessor()
        image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        enhanced = processor.enhance(image)
        assert enhanced.shape == image.shape

    def test_resize(self):
        processor = ImageProcessor(target_size=(640, 640))
        image = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        resized = processor.resize(image)
        assert resized.shape == (640, 640, 3)

    def test_draw_annotations(self):
        processor = ImageProcessor()
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = [{"class": "Crack", "confidence": 0.85, "severity": "medium", "bbox": [100, 100, 200, 200]}]
        annotated = processor.draw_annotations(image, detections)
        assert annotated.shape == image.shape
        assert not np.array_equal(annotated, image)

    def test_validate_quality(self):
        processor = ImageProcessor()
        blurry_image = np.full((100, 100, 3), 128, dtype=np.uint8)
        is_valid, msg = processor.validate_quality(blurry_image)
        assert is_valid is False
        assert "blurry" in msg.lower() or "insufficient" in msg.lower()


class TestCVDefectDetector:
    def test_quality_check_blurry(self):
        detector = CVDefectDetector()
        solid_img = np.full((200, 200, 3), 100, dtype=np.uint8)
        is_valid, msg = detector.check_quality(solid_img)
        assert is_valid is False

    def test_crack_detection_synthetic(self):
        detector = CVDefectDetector()
        img = np.full((300, 300, 3), 220, dtype=np.uint8)
        # Draw a diagonal crack line across the image
        for i in range(50, 250):
            img[i, i : i + 3] = [20, 20, 20]

        dets = detector.detect_defects(img, asset_type="building_wall")
        assert len(dets) > 0
        assert dets[0]["class"] in ("Crack", "Major Crack")

    def test_plain_wall_does_not_become_major_crack(self):
        detector = CVDefectDetector()
        img = np.full((300, 300, 3), 220, dtype=np.uint8)
        cv2 = pytest.importorskip("cv2")
        for y in range(0, 300, 24):
            cv2.line(img, (0, y), (299, y), (205, 205, 205), 2)

        dets = detector.detect_defects(img, asset_type="building_wall")
        assert all(det["class"] != "Major Crack" for det in dets)
        assert all(det["severity"] != "critical" for det in dets)

    def test_short_crack_is_not_critical(self):
        detector = CVDefectDetector()
        img = np.full((300, 300, 3), 220, dtype=np.uint8)
        cv2 = pytest.importorskip("cv2")
        cv2.line(img, (105, 140), (195, 160), (20, 20, 20), 2)

        dets = detector.detect_defects(img, asset_type="building_wall")
        assert dets
        assert dets[0]["class"] == "Crack"
        assert dets[0]["severity"] in ("low", "medium")


class TestPredictiveMaintenance:
    def test_calculate_condition_score(self):
        engine = PredictiveMaintenanceEngine()
        dets = [{"class": "Crack", "confidence": 0.87, "severity": "medium", "bbox": [10, 10, 50, 50]}]
        score = engine.calculate_condition_score(dets)
        assert 0 <= score <= 100
        assert score < 100

    def test_get_maintenance_recommendation(self):
        engine = PredictiveMaintenanceEngine()
        rec = engine.get_maintenance_recommendation("Crack", "medium", "building_wall")
        assert "crack" in rec.lower()
        assert "repair" in rec.lower() or "seal" in rec.lower()

    def test_empty_records(self):
        engine = PredictiveMaintenanceEngine()
        assert engine.predict_risk([]) == []


class TestAssetTypes:
    def test_supported_assets_normalization(self):
        assert InspectionRepository.normalize_asset_type("Building Wall") == "building_wall"
        assert InspectionRepository.normalize_asset_type("bridge") == "bridge_span"
        assert InspectionRepository.normalize_asset_type("tower") == "tower_mast"


class TestFlightPlan:
    def test_grid_generation(self):
        plan = FlightPlan.from_grid(28.6139, 77.2090, 200, 200, 50)
        assert len(plan.waypoints) > 0
        assert plan.name == "grid_survey"


class TestFlightController:
    def test_simulation_connect(self):
        controller = FlightController(simulation=True)
        assert controller.connect() is True
        assert controller.status.value == "idle"
