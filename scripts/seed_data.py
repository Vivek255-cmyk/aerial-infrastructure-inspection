"""Seed the database with sample infrastructure assets."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api.app import create_app
from src.database.repository import InspectionRepository


SAMPLE_ASSETS = [
    {"name": "Bridge Span B-42", "asset_type": "bridge", "latitude": 28.6200, "longitude": 77.2150},
    {"name": "Bridge Span B-48", "asset_type": "bridge", "latitude": 28.6225, "longitude": 77.2185},
    {"name": "Building Wall West Wing", "asset_type": "building_wall", "latitude": 28.6100, "longitude": 77.2000},
    {"name": "Building Wall East Facade", "asset_type": "building_wall", "latitude": 28.6125, "longitude": 77.2035},
    {"name": "Tower North Mast", "asset_type": "tower", "latitude": 28.6139, "longitude": 77.2090},
    {"name": "Tower South Mast", "asset_type": "tower", "latitude": 28.6180, "longitude": 77.2120},
]


def main():
    app = create_app()
    with app.app_context():
        existing = InspectionRepository.get_assets()
        existing_names = {asset.name.lower() for asset in existing}
        created = 0

        for asset in SAMPLE_ASSETS:
            if asset["name"].lower() in existing_names:
                print(f"  Already exists: {asset['name']}")
                continue

            InspectionRepository.create_asset(
                name=asset["name"],
                asset_type=asset["asset_type"],
                lat=asset["latitude"],
                lon=asset["longitude"],
            )
            existing_names.add(asset["name"].lower())
            created += 1
            print(f"  Created: {asset['name']}")

        print(f"\nSeeded {created} new asset(s) successfully.")
        print(f"Total assets in database: {len(InspectionRepository.get_assets())}")


if __name__ == "__main__":
    main()
