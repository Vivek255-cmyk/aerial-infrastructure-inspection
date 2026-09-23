"""Predictive maintenance engine, condition scoring, and maintenance recommendation rules."""

from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder


class PredictiveMaintenanceEngine:
    """Engine for condition scoring, maintenance recommendations, and historical failure prediction."""

    SEVERITY_SCORES = {"low": 1, "medium": 2, "high": 3, "critical": 4}

    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.label_encoder = LabelEncoder()
        self._is_trained = False

    @staticmethod
    def calculate_condition_score(detections: list[dict], previous_scores: list[int] | None = None) -> int:
        """Calculate a 0–100 condition score based on detected defects, severities, and historical trend."""
        if not detections:
            return 100

        base_score = 100
        severity_deductions = {
            "low": 12,
            "medium": 28,
            "high": 45,
            "critical": 65,
        }

        total_deduction = 0
        for det in detections:
            sev = det.get("severity", "medium").lower()
            conf = det.get("confidence", 0.7)
            ded = severity_deductions.get(sev, 25) * conf
            total_deduction += ded

        score = max(0, min(100, int(round(base_score - total_deduction))))

        # Adjust score slightly if recent history shows continuous degradation
        if previous_scores and len(previous_scores) >= 2:
            if previous_scores[0] < previous_scores[1]: # Decreasing trend
                score = max(0, score - 3)

        return score

    @staticmethod
    def calculate_trend(current_score: int, previous_scores: list[int] | None = None) -> str:
        """Determine asset condition trend (Stable, Deteriorating, Improving)."""
        if not previous_scores:
            return "Stable"

        prev_score = previous_scores[0] # Most recent previous score
        diff = current_score - prev_score

        if diff < -3:
            return "Deteriorating"
        elif diff > 3:
            return "Improving"
        return "Stable"

    @staticmethod
    def get_maintenance_priority(severity: str, trend: str = "Stable") -> str:
        """Determine Maintenance Priority (Routine, Medium, High, Urgent) with trend escalation."""
        sev_map = {
            "low": "Routine",
            "medium": "Medium",
            "high": "High",
            "critical": "Urgent",
        }
        priority = sev_map.get(severity.lower(), "Medium")

        # Escalate priority if condition is continuously deteriorating
        if trend == "Deteriorating":
            escalation = {
                "Routine": "Medium",
                "Medium": "High",
                "High": "Urgent",
                "Urgent": "Urgent",
            }
            priority = escalation.get(priority, priority)

        return priority

    @staticmethod
    def get_next_inspection_days(severity: str) -> int:
        """Suggest next inspection interval in days (7, 30, 60, 90 days)."""
        days_map = {
            "low": 90,
            "medium": 60,
            "high": 30,
            "critical": 7,
        }
        return days_map.get(severity.lower(), 60)

    @staticmethod
    def get_maintenance_recommendation(defect_class: str, severity: str, asset_type: str = "building_wall") -> str:
        """Generate specific maintenance recommendations based on defect type and severity."""
        defect = (defect_class or "crack").strip().lower()
        sev = (severity or "medium").strip().lower()

        # 1. Crack Recommendations
        if "crack" in defect:
            if sev == "low":
                return "Monitor crack, seal minor crack, schedule periodic inspection."
            elif sev == "medium":
                return "Clean and repair/seal crack, inspect surrounding area, schedule follow-up inspection."
            elif sev == "high":
                return "Detailed structural inspection recommended, schedule urgent professional assessment, recommend repair/strengthening assessment."
            elif sev == "critical":
                return "Mark as urgent, recommend immediate professional structural assessment."

        # 2. Corrosion / Rust Recommendations
        if "corrosion" in defect or "rust" in defect:
            return "Remove loose corrosion, clean affected area, apply anti-corrosion treatment, apply protective coating, schedule follow-up inspection."

        # 3. Water / Moisture Damage Recommendations
        if "water" in defect or "moisture" in defect or "damp" in defect:
            return "Check possible leakage/water source, repair leakage/drainage issue, repair damaged surface, reinspect after repair."

        # 4. Surface / Paint / Plaster Deterioration Recommendations
        if "surface" in defect or "paint" in defect or "plaster" in defect or "spalling" in defect:
            return "Remove loose material, prepare surface, repair damaged area, apply protective coating, schedule follow-up inspection."

        # Generic fallback
        return f"Inspect surrounding structure for {defect_class} defects and schedule routine maintenance."

    def build_features(self, defect_records: list[dict]) -> pd.DataFrame:
        """Convert raw defect records into feature vectors for ML."""
        df = pd.DataFrame(defect_records)
        if df.empty:
            return pd.DataFrame()

        df["severity_score"] = df["severity"].map(self.SEVERITY_SCORES).fillna(1)
        df["detection_date"] = pd.to_datetime(df.get("detected_at", datetime.now()))

        features = df.groupby("asset_id").agg(
            total_defects=("class", "count"),
            avg_confidence=("confidence", "mean"),
            max_severity=("severity_score", "max"),
            unique_defect_types=("class", "nunique"),
            days_since_first=("detection_date", lambda x: (datetime.now() - x.min()).days),
            days_since_last=("detection_date", lambda x: (datetime.now() - x.max()).days),
        ).reset_index()

        return features

    def predict_risk(self, defect_records: list[dict]) -> list[dict]:
        """Predict failure risk for each asset based on defect history."""
        features = self.build_features(defect_records)
        if features.empty:
            return []

        predictions = []
        for _, row in features.iterrows():
            asset_id = int(row["asset_id"])
            max_sev_score = row["max_severity"]
            sev_names = {1: "low", 2: "medium", 3: "high", 4: "critical"}
            sev_str = sev_names.get(max_sev_score, "medium")

            risk_level = "critical" if max_sev_score == 4 else ("high" if max_sev_score == 3 else ("medium" if max_sev_score == 2 else "low"))
            recommended = self.get_maintenance_recommendation("Crack", sev_str)

            predictions.append({
                "asset_id": asset_id,
                "risk_level": risk_level,
                "risk_score": round(max_sev_score / 4.0, 2),
                "recommended_action": recommended,
                "maintenance_window": {
                    "recommended_date": (datetime.now() + timedelta(days=self.get_next_inspection_days(sev_str))).strftime("%Y-%m-%d"),
                    "urgency": risk_level,
                },
            })

        return predictions
