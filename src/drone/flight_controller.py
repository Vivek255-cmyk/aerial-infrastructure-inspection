"""Drone flight planning and control interface."""

import json
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class FlightStatus(Enum):
    IDLE = "idle"
    ARMED = "armed"
    TAKEOFF = "takeoff"
    IN_FLIGHT = "in_flight"
    INSPECTING = "inspecting"
    RETURNING = "returning"
    LANDED = "landed"
    ERROR = "error"


@dataclass
class Waypoint:
    latitude: float
    longitude: float
    altitude_m: float
    action: str = "capture"  # capture, hover, pan
    heading_deg: float = 0.0


@dataclass
class FlightPlan:
    name: str
    waypoints: list[Waypoint] = field(default_factory=list)
    speed_mps: float = 5.0
    overlap_percent: float = 70.0
    gimbal_pitch: float = -90.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "waypoints": [
                {
                    "lat": wp.latitude,
                    "lon": wp.longitude,
                    "alt": wp.altitude_m,
                    "action": wp.action,
                    "heading": wp.heading_deg,
                }
                for wp in self.waypoints
            ],
            "speed_mps": self.speed_mps,
            "overlap_percent": self.overlap_percent,
        }

    @classmethod
    def from_grid(
        cls,
        center_lat: float,
        center_lon: float,
        width_m: float,
        height_m: float,
        altitude_m: float = 50.0,
        line_spacing_m: float = 20.0,
    ) -> "FlightPlan":
        """Generate a lawn-mower survey pattern over a rectangular area."""
        waypoints = []
        lat_offset = height_m / 111_000
        lon_offset = width_m / (111_000 * math.cos(math.radians(center_lat)))

        num_lines = max(int(height_m / line_spacing_m), 1)
        step = lat_offset / num_lines

        for i in range(num_lines + 1):
            lat = center_lat - height_m / 2 / 111_000 + i * step
            if i % 2 == 0:
                waypoints.append(Waypoint(lat, center_lon - lon_offset / 2, altitude_m))
                waypoints.append(Waypoint(lat, center_lon + lon_offset / 2, altitude_m))
            else:
                waypoints.append(Waypoint(lat, center_lon + lon_offset / 2, altitude_m))
                waypoints.append(Waypoint(lat, center_lon - lon_offset / 2, altitude_m))

        return cls(name="grid_survey", waypoints=waypoints, overlap_percent=70.0)


class FlightController:
    """Interface for drone flight control (supports simulation mode)."""

    def __init__(self, connection_string: str = "", simulation: bool = True):
        self.connection_string = connection_string
        self.simulation = simulation
        self.status = FlightStatus.IDLE
        self.current_plan: FlightPlan | None = None
        self.telemetry: dict = {}
        self._vehicle = None

    def connect(self) -> bool:
        if self.simulation:
            self.status = FlightStatus.IDLE
            self.telemetry = {
                "battery_percent": 100,
                "altitude_m": 0,
                "speed_mps": 0,
                "gps_fix": 3,
                "satellites": 12,
            }
            return True

        try:
            from dronekit import connect
            self._vehicle = connect(self.connection_string, wait_ready=True, timeout=30)
            self.status = FlightStatus.IDLE
            return True
        except ImportError:
            raise ImportError(
                "dronekit is required for real drone control. "
                "Install with: pip install dronekit, or enable simulation mode."
            )
        except Exception as e:
            self.status = FlightStatus.ERROR
            raise ConnectionError(f"Failed to connect to drone: {e}")

    def arm_and_takeoff(self, target_altitude_m: float) -> None:
        if self.simulation:
            self.status = FlightStatus.TAKEOFF
            self.telemetry["altitude_m"] = target_altitude_m
            self.status = FlightStatus.IN_FLIGHT
            return

        if self._vehicle is None:
            raise RuntimeError("Not connected to drone")

        self._vehicle.mode = "GUIDED"
        self._vehicle.armed = True
        while not self._vehicle.armed:
            pass
        self._vehicle.simple_takeoff(target_altitude_m)

    def execute_plan(self, plan: FlightPlan) -> list[dict]:
        """Execute a flight plan and return captured image metadata."""
        self.current_plan = plan
        self.status = FlightStatus.INSPECTING
        captures = []

        for i, wp in enumerate(plan.waypoints):
            if self.simulation:
                capture = {
                    "waypoint_index": i,
                    "latitude": wp.latitude,
                    "longitude": wp.longitude,
                    "altitude_m": wp.altitude_m,
                    "timestamp": datetime.now().isoformat(),
                    "image_path": f"data/raw/capture_{datetime.now():%Y%m%d_%H%M%S}_{i:03d}.jpg",
                    "action": wp.action,
                }
                captures.append(capture)
                self.telemetry.update({
                    "altitude_m": wp.altitude_m,
                    "latitude": wp.latitude,
                    "longitude": wp.longitude,
                })
            else:
                self._goto_waypoint(wp)
                if wp.action == "capture":
                    captures.append(self._capture_image(i, wp))

        self.status = FlightStatus.RETURNING
        return captures

    def return_to_launch(self) -> None:
        self.status = FlightStatus.RETURNING
        if not self.simulation and self._vehicle:
            self._vehicle.mode = "RTL"
        self.status = FlightStatus.LANDED

    def get_telemetry(self) -> dict:
        if not self.simulation and self._vehicle:
            self.telemetry = {
                "battery_percent": self._vehicle.battery.level,
                "altitude_m": self._vehicle.location.global_relative_frame.alt,
                "speed_mps": self._vehicle.groundspeed,
                "latitude": self._vehicle.location.global_frame.lat,
                "longitude": self._vehicle.location.global_frame.lon,
            }
        return {**self.telemetry, "status": self.status.value}

    def _goto_waypoint(self, wp: Waypoint) -> None:
        if self._vehicle is None:
            return
        from dronekit import LocationGlobalRelative
        target = LocationGlobalRelative(wp.latitude, wp.longitude, wp.altitude_m)
        self._vehicle.simple_goto(target)

    def _capture_image(self, index: int, wp: Waypoint) -> dict:
        return {
            "waypoint_index": index,
            "latitude": wp.latitude,
            "longitude": wp.longitude,
            "altitude_m": wp.altitude_m,
            "timestamp": datetime.now().isoformat(),
            "image_path": f"data/raw/capture_{datetime.now():%Y%m%d_%H%M%S}_{index:03d}.jpg",
            "action": wp.action,
        }

    def save_plan(self, plan: FlightPlan, path: str) -> None:
        with open(path, "w") as f:
            json.dump(plan.to_dict(), f, indent=2)

    def disconnect(self) -> None:
        if self._vehicle:
            self._vehicle.close()
            self._vehicle = None
        self.status = FlightStatus.IDLE
