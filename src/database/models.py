"""SQLAlchemy models for MySQL and SQLite document schemas."""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text

db = SQLAlchemy()


class Asset(db.Model):
    """Infrastructure asset being inspected (Building Wall, Bridge Span, Tower/Mast)."""
    __tablename__ = "assets"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    asset_type = db.Column(db.String(50), nullable=False) # building_wall, bridge_span, tower_mast
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    install_date = db.Column(db.Date)
    last_inspection = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="active")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    inspections = db.relationship("Inspection", backref="asset", lazy=True)
    defects = db.relationship("Defect", backref="asset", lazy=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "asset_type": self.asset_type,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "status": self.status,
            "last_inspection": self.last_inspection.isoformat() if self.last_inspection else None,
        }


class Inspection(db.Model):
    """A single aerial inspection session."""
    __tablename__ = "inspections"

    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False)
    drone_id = db.Column(db.String(100))
    flight_plan = db.Column(db.Text)
    image_count = db.Column(db.Integer, default=0)
    defect_count = db.Column(db.Integer, default=0)
    condition_score = db.Column(db.Integer, default=100)
    maintenance_priority = db.Column(db.String(30), default="Routine")
    recommended_maintenance = db.Column(db.Text)
    next_inspection_days = db.Column(db.Integer, default=90)
    trend = db.Column(db.String(30), default="Stable")
    quality_status = db.Column(db.String(30), default="ok")
    quality_message = db.Column(db.Text)
    status = db.Column(db.String(20), default="pending")
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    defects = db.relationship("Defect", backref="inspection", lazy=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "asset_id": self.asset_id,
            "drone_id": self.drone_id,
            "image_count": self.image_count,
            "defect_count": self.defect_count,
            "condition_score": self.condition_score,
            "maintenance_priority": self.maintenance_priority,
            "recommended_maintenance": self.recommended_maintenance,
            "next_inspection_days": self.next_inspection_days,
            "trend": self.trend,
            "quality_status": self.quality_status,
            "quality_message": self.quality_message,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class Defect(db.Model):
    """An individual defect detected during inspection."""
    __tablename__ = "defects"

    id = db.Column(db.Integer, primary_key=True)
    inspection_id = db.Column(db.Integer, db.ForeignKey("inspections.id"), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey("assets.id"), nullable=False)
    defect_class = db.Column(db.String(50), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    severity = db.Column(db.String(20), default="low")
    bbox_x1 = db.Column(db.Integer)
    bbox_y1 = db.Column(db.Integer)
    bbox_x2 = db.Column(db.Integer)
    bbox_y2 = db.Column(db.Integer)
    image_path = db.Column(db.String(500))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "inspection_id": self.inspection_id,
            "asset_id": self.asset_id,
            "class": self.defect_class,
            "confidence": self.confidence,
            "severity": self.severity,
            "bbox": [self.bbox_x1, self.bbox_y1, self.bbox_x2, self.bbox_y2],
            "image_path": self.image_path,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "detected_at": self.detected_at.isoformat() if self.detected_at else None,
            "resolved": self.resolved,
        }


def init_db(app) -> None:
    db.init_app(app)
    with app.app_context():
        db.create_all()
        _upgrade_existing_schema()


def _upgrade_existing_schema() -> None:
    """Add inspection fields to databases created by older application versions."""
    inspector = inspect(db.engine)
    if "inspections" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("inspections")}
    missing_columns = {
        "condition_score": "INTEGER DEFAULT 100",
        "maintenance_priority": "VARCHAR(30) DEFAULT 'Routine'",
        "recommended_maintenance": "TEXT",
        "next_inspection_days": "INTEGER DEFAULT 90",
        "trend": "VARCHAR(30) DEFAULT 'Stable'",
        "quality_status": "VARCHAR(30) DEFAULT 'ok'",
        "quality_message": "TEXT",
    }

    for column_name, column_definition in missing_columns.items():
        if column_name not in existing_columns:
            db.session.execute(
                text(f"ALTER TABLE inspections ADD COLUMN {column_name} {column_definition}")
            )
    db.session.commit()
