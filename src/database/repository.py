"""Data access layer for inspections, assets, and defects."""

from datetime import datetime
from src.database.models import Asset, Defect, Inspection, db


class InspectionRepository:
    """CRUD operations for inspection data."""

    SUPPORTED_ASSET_TYPES = {"building_wall", "bridge_span", "tower_mast"}
    ASSET_TYPE_ALIASES = {
        "building": "building_wall",
        "building_wall": "building_wall",
        "building_walls": "building_wall",
        "bridge": "bridge_span",
        "bridge_span": "bridge_span",
        "tower": "tower_mast",
        "tower_mast": "tower_mast",
        "transmission_tower": "tower_mast",
    }

    @staticmethod
    def normalize_asset_type(asset_type: str) -> str:
        if asset_type is None or str(asset_type).strip() == "":
            return "building_wall"

        normalized = str(asset_type).strip().lower().replace("-", "_").replace(" ", "_")
        normalized = InspectionRepository.ASSET_TYPE_ALIASES.get(normalized, normalized)

        if normalized not in InspectionRepository.SUPPORTED_ASSET_TYPES:
            return "building_wall"
        return normalized

    @staticmethod
    def seed_default_assets() -> None:
        """Ensure standard demo assets exist for IDs 1, 2, and 3."""
        defaults = [
            {"id": 1, "name": "Building Wall", "asset_type": "building_wall", "lat": 37.7749, "lon": -122.4194},
            {"id": 2, "name": "Bridge Span", "asset_type": "bridge_span", "lat": 37.8080, "lon": -122.4777},
            {"id": 3, "name": "Tower/Mast", "asset_type": "tower_mast", "lat": 37.7833, "lon": -122.4167},
        ]

        for item in defaults:
            existing = Asset.query.get(item["id"])
            if not existing:
                asset = Asset(
                    id=item["id"],
                    name=item["name"],
                    asset_type=item["asset_type"],
                    latitude=item["lat"],
                    longitude=item["lon"],
                )
                db.session.add(asset)
        db.session.commit()

    @staticmethod
    def create_asset(name: str, asset_type: str, lat: float = 0.0, lon: float = 0.0) -> Asset:
        asset_type = InspectionRepository.normalize_asset_type(asset_type)
        asset = Asset(name=name, asset_type=asset_type, latitude=lat, longitude=lon)
        db.session.add(asset)
        db.session.commit()
        return asset

    @staticmethod
    def get_assets() -> list[Asset]:
        InspectionRepository.seed_default_assets()
        return Asset.query.all()

    @staticmethod
    def get_asset(asset_id: int) -> Asset | None:
        InspectionRepository.seed_default_assets()
        asset = Asset.query.get(asset_id)
        if not asset and asset_id in {1, 2, 3}:
            InspectionRepository.seed_default_assets()
            asset = Asset.query.get(asset_id)
        return asset

    @staticmethod
    def create_inspection(asset_id: int, drone_id: str = "upload") -> Inspection:
        InspectionRepository.seed_default_assets()
        inspection = Inspection(asset_id=asset_id, drone_id=drone_id, status="in_progress")
        db.session.add(inspection)
        db.session.commit()
        return inspection

    @staticmethod
    def get_previous_scores(asset_id: int, limit: int = 5) -> list[int]:
        """Fetch past completed inspection condition scores for an asset ID."""
        inspections = (
            Inspection.query.filter(
                Inspection.asset_id == asset_id,
                Inspection.status == "completed",
                Inspection.quality_status == "ok",
            )
            .order_by(Inspection.completed_at.desc())
            .limit(limit)
            .all()
        )
        return [i.condition_score for i in inspections if i.condition_score is not None]

    @staticmethod
    def complete_inspection(
        inspection_id: int,
        defect_count: int,
        image_count: int,
        condition_score: int = 100,
        maintenance_priority: str = "Routine",
        recommended_maintenance: str = "",
        next_inspection_days: int = 90,
        trend: str = "Stable",
        quality_status: str = "ok",
        quality_message: str = "",
    ) -> Inspection:
        inspection = Inspection.query.get(inspection_id)
        if inspection:
            inspection.status = "completed"
            inspection.defect_count = defect_count
            inspection.image_count = image_count
            inspection.condition_score = condition_score
            inspection.maintenance_priority = maintenance_priority
            inspection.recommended_maintenance = recommended_maintenance
            inspection.next_inspection_days = next_inspection_days
            inspection.trend = trend
            inspection.quality_status = quality_status
            inspection.quality_message = quality_message
            inspection.completed_at = datetime.utcnow()

            # Update asset last inspection timestamp
            asset = Asset.query.get(inspection.asset_id)
            if asset:
                asset.last_inspection = datetime.utcnow()

            db.session.commit()
        return inspection

    @staticmethod
    def save_defect(
        inspection_id: int,
        asset_id: int,
        detection: dict,
        image_path: str = "",
        lat: float | None = None,
        lon: float | None = None,
    ) -> Defect:
        bbox = detection.get("bbox", [0, 0, 0, 0])
        defect = Defect(
            inspection_id=inspection_id,
            asset_id=asset_id,
            defect_class=detection["class"],
            confidence=float(detection["confidence"]),
            severity=detection.get("severity", "low"),
            bbox_x1=bbox[0], bbox_y1=bbox[1],
            bbox_x2=bbox[2], bbox_y2=bbox[3],
            image_path=image_path,
            latitude=lat, longitude=lon,
        )
        db.session.add(defect)
        db.session.commit()
        return defect

    @staticmethod
    def get_defects_by_asset(asset_id: int) -> list[Defect]:
        return Defect.query.filter_by(asset_id=asset_id).order_by(Defect.detected_at.desc()).all()

    @staticmethod
    def get_recent_inspections(limit: int = 20) -> list[Inspection]:
        return Inspection.query.order_by(Inspection.started_at.desc()).limit(limit).all()

    @staticmethod
    def get_defect_summary() -> dict:
        from sqlalchemy import func
        results = (
            db.session.query(Defect.defect_class, Defect.severity, func.count(Defect.id))
            .group_by(Defect.defect_class, Defect.severity)
            .all()
        )
        summary = {}
        for cls, sev, count in results:
            if cls not in summary:
                summary[cls] = {}
            summary[cls][sev] = count
        return summary

    @staticmethod
    def get_all_defect_records() -> list[dict]:
        defects = Defect.query.all()
        return [
            {
                "asset_id": d.asset_id,
                "asset_type": d.asset.asset_type if d.asset else None,
                "class": d.defect_class,
                "confidence": d.confidence,
                "severity": d.severity,
                "detected_at": d.detected_at,
            }
            for d in defects
        ]
