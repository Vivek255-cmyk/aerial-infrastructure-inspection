"""Flask REST API for the aerial inspection monitoring system."""

import os
import socket
import uuid
from datetime import datetime
from pathlib import Path

import cv2
from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

from config.settings import Settings
from src.database.models import init_db
from src.database.repository import InspectionRepository
from src.models.predictive_maintenance import PredictiveMaintenanceEngine
from src.processing.image_processor import ImageProcessor


def create_app() -> Flask:
    settings = Settings()

    app = Flask(
        __name__,
        template_folder=str(settings.BASE_DIR / "frontend" / "templates"),
        static_folder=str(settings.BASE_DIR / "frontend" / "static"),
    )
    app.config["SECRET_KEY"] = settings.SECRET_KEY
    app.config["SQLALCHEMY_DATABASE_URI"] = settings.DATABASE_URI
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UPLOAD_FOLDER"] = str(settings.DATA_DIR / "raw")
    app.config["PROCESSED_FOLDER"] = str(settings.DATA_DIR / "processed")

    CORS(app)
    init_db(app)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["PROCESSED_FOLDER"], exist_ok=True)

    with app.app_context():
        InspectionRepository.seed_default_assets()

    # Lazy-loaded detector to avoid slow startup
    _detector = {"instance": None}

    def get_detector():
        if _detector["instance"] is None:
            from src.detection.yolo_detector import YOLODetector
            _detector["instance"] = YOLODetector()
        return _detector["instance"]

    # ── Static Processed Images Route ──
    @app.route("/processed/<filename>")
    def serve_processed_image(filename):
        return send_from_directory(app.config["PROCESSED_FOLDER"], filename)

    # ── Dashboard Routes ──

    @app.route("/")
    def dashboard():
        return render_template("index.html")

    @app.route("/inspections")
    def inspections_page():
        return render_template("inspections.html")

    @app.route("/camera")
    def camera_page():
        return render_template("camera.html")

    # ── API Routes ──

    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "version": "0.2.0"})

    @app.route("/api/network")
    def network_info():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                host = sock.getsockname()[0]
        except OSError:
            host = "127.0.0.1"
        return jsonify({"host": host, "port": settings.FLASK_PORT})

    @app.route("/api/assets", methods=["GET"])
    def list_assets():
        assets = InspectionRepository.get_assets()
        return jsonify([a.to_dict() for a in assets])

    @app.route("/api/assets", methods=["POST"])
    def create_asset():
        data = request.get_json(silent=True) or {}
        try:
            asset = InspectionRepository.create_asset(
                name=data["name"],
                asset_type=data.get("asset_type", "building_wall"),
                lat=data.get("latitude", 0),
                lon=data.get("longitude", 0),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(asset.to_dict()), 201

    @app.route("/api/inspect", methods=["POST"])
    def run_inspection():
        """Run full inspection pipeline: quality check → detect → score → recommend → save."""
        if "image" not in request.files:
            return jsonify({"error": "No image provided"}), 400

        file = request.files["image"]
        asset_id = int(request.form.get("asset_id", 1))
        source = request.form.get("source", "upload")

        asset = InspectionRepository.get_asset(asset_id)
        if not asset:
            asset = InspectionRepository.create_asset(
                name=f"Asset #{asset_id}", asset_type="building_wall"
            )

        raw_name = secure_filename(file.filename or "capture.jpg")
        if not raw_name:
            raw_name = "capture.jpg"
        stem = Path(raw_name).stem
        ext = Path(raw_name).suffix or ".jpg"
        filename = f"{stem}_{datetime.utcnow():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}{ext}"
        save_path = Path(app.config["UPLOAD_FOLDER"]) / filename
        file.save(str(save_path))

        processor = ImageProcessor()
        raw_image = processor.load(save_path)

        # 1. Quality Validation
        is_valid_quality, quality_msg = processor.validate_quality(raw_image)
        source_ids = {"mobile": "mobile-cam", "webcam": "webcam", "upload": "upload"}
        inspection = InspectionRepository.create_inspection(
            asset_id, drone_id=source_ids.get(source, source)
        )

        if not is_valid_quality:
            InspectionRepository.complete_inspection(
                inspection_id=inspection.id,
                defect_count=0,
                image_count=1,
                condition_score=100,
                quality_status="insufficient",
                quality_message=quality_msg,
            )
            return jsonify({
                "inspection_id": inspection.id,
                "asset_id": asset.id,
                "asset_name": asset.name,
                "asset_type": asset.asset_type,
                "quality_status": "insufficient",
                "message": quality_msg,
                "defects_found": 0,
                "detections": [],
                "condition_score": 100,
                "maintenance_priority": "N/A",
                "recommended_maintenance": "Re-upload a clearer image.",
                "next_inspection_days": 0,
                "trend": "N/A",
            })

        # 2. Defect Detection Pipeline
        processed_image = processor.preprocess(save_path)
        detector = get_detector()
        detections = detector.detect(processed_image, asset_type=asset.asset_type)

        # Save individual defects
        for det in detections:
            InspectionRepository.save_defect(
                inspection.id, asset_id, det, str(save_path)
            )

        # 3. Previous History & Trend Calculation
        prev_scores = InspectionRepository.get_previous_scores(asset_id)

        # 4. Condition Score & Maintenance Rules
        pm_engine = PredictiveMaintenanceEngine()
        condition_score = pm_engine.calculate_condition_score(detections, previous_scores=prev_scores)
        trend = pm_engine.calculate_trend(condition_score, previous_scores=prev_scores)

        dominant_defect = detections[0]["class"] if detections else "None"
        dominant_severity = detections[0]["severity"] if detections else "low"
        confidence_pct = int(round((detections[0]["confidence"] * 100))) if detections else 100

        maintenance_priority = pm_engine.get_maintenance_priority(dominant_severity, trend=trend)
        next_inspection_days = pm_engine.get_next_inspection_days(dominant_severity)
        rec_maintenance = pm_engine.get_maintenance_recommendation(
            dominant_defect, dominant_severity, asset_type=asset.asset_type
        ) if detections else "No visible defect detected. Continue routine monitoring."

        # 5. Save Annotated Image
        annotated = processor.draw_annotations(processed_image, detections)
        annotated_filename = f"annotated_{filename}"
        annotated_path = Path(app.config["PROCESSED_FOLDER"]) / annotated_filename
        processor.save(annotated, annotated_path)

        InspectionRepository.complete_inspection(
            inspection_id=inspection.id,
            defect_count=len(detections),
            image_count=1,
            condition_score=condition_score,
            maintenance_priority=maintenance_priority,
            recommended_maintenance=rec_maintenance,
            next_inspection_days=next_inspection_days,
            trend=trend,
            quality_status="ok",
            quality_message="Quality acceptable",
        )

        return jsonify({
            "inspection_id": inspection.id,
            "asset_id": asset.id,
            "asset_name": asset.name,
            "asset_type": asset.asset_type,
            "quality_status": "ok",
            "defects_found": len(detections),
            "detections": detections,
            "defect_type": dominant_defect,
            "severity": dominant_severity.title(),
            "confidence": confidence_pct,
            "condition_score": condition_score,
            "maintenance_priority": maintenance_priority,
            "recommended_maintenance": rec_maintenance,
            "next_inspection_days": next_inspection_days,
            "trend": trend,
            "annotated_image_url": f"/processed/{annotated_filename}",
        })

    @app.route("/api/detect", methods=["POST"])
    def detect_only():
        """Detect defects in an uploaded image without saving to DB."""
        if "image" not in request.files:
            return jsonify({"error": "No image provided"}), 400

        file = request.files["image"]
        asset_type = request.form.get("asset_type", "building_wall")
        save_path = Path(app.config["UPLOAD_FOLDER"]) / file.filename
        file.save(str(save_path))

        detector = get_detector()
        detections = detector.detect(str(save_path), asset_type=asset_type)
        return jsonify({"detections": detections, "count": len(detections)})

    @app.route("/api/inspections", methods=["GET"])
    def list_inspections():
        inspections = InspectionRepository.get_recent_inspections()
        return jsonify([i.to_dict() for i in inspections])

    @app.route("/api/defects/<int:asset_id>", methods=["GET"])
    def get_defects(asset_id):
        defects = InspectionRepository.get_defects_by_asset(asset_id)
        return jsonify([d.to_dict() for d in defects])

    @app.route("/api/summary", methods=["GET"])
    def defect_summary():
        return jsonify(InspectionRepository.get_defect_summary())

    @app.route("/api/predict", methods=["GET"])
    def predict_maintenance():
        records = InspectionRepository.get_all_defect_records()
        engine = PredictiveMaintenanceEngine()
        predictions = engine.predict_risk(records)
        return jsonify(predictions)

    @app.route("/api/drone/telemetry", methods=["GET"])
    def drone_telemetry():
        from src.drone.flight_controller import FlightController
        s = Settings()
        controller = FlightController(simulation=s.DRONE_SIMULATION_MODE)
        controller.connect()
        return jsonify(controller.get_telemetry())

    return app
