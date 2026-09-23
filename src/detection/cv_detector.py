"""Computer Vision-based inspection and defect detector for infrastructure images."""

import cv2
import numpy as np


class CVDefectDetector:
    """Computer vision engine for quality check, crack detection, corrosion, and defect analysis."""

    def __init__(self, blur_threshold: float = 60.0, dark_threshold: float = 25.0, bright_threshold: float = 235.0):
        self.blur_threshold = blur_threshold
        self.dark_threshold = dark_threshold
        self.bright_threshold = bright_threshold

    def check_quality(self, image: np.ndarray) -> tuple[bool, str]:
        """Validate if image quality is sufficient for reliable inspection."""
        if image is None or image.size == 0:
            return False, "Image quality is insufficient for reliable inspection. Please upload a clearer infrastructure image."

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        mean_brightness = np.mean(gray)

        if laplacian_var < self.blur_threshold:
            return False, "Image quality is insufficient for reliable inspection. Image appears too blurry. Please upload a clearer infrastructure image."

        if mean_brightness < self.dark_threshold:
            return False, "Image quality is insufficient for reliable inspection. Image is too dark. Please upload a clearer infrastructure image."

        if mean_brightness > self.bright_threshold:
            return False, "Image quality is insufficient for reliable inspection. Image is overexposed. Please upload a clearer infrastructure image."

        return True, "Quality acceptable"

    def detect_defects(self, image: np.ndarray, asset_type: str = "building_wall") -> list[dict]:
        """Analyze image using CV algorithms tailored for specified asset type."""
        if image is None or image.size == 0:
            return []

        h, w = image.shape[:2]
        img_area = h * w
        img_diag = np.sqrt(h**2 + w**2)
        detections = []

        # 1. Crack Detection
        crack_dets = self._detect_cracks(image, h, w, img_diag, asset_type)
        detections.extend(crack_dets)

        # 2. Corrosion / Rust Detection (Bridge Span & Tower/Mast)
        if asset_type in {"bridge_span", "tower_mast", "bridge", "tower"}:
            corrosion_dets = self._detect_corrosion(image, h, w, img_area)
            detections.extend(corrosion_dets)

        # 3. Water / Moisture Damage & Surface Damage (Building Wall)
        if asset_type in {"building_wall", "building"}:
            moisture_dets = self._detect_moisture_or_surface_damage(image, h, w, img_area)
            detections.extend(moisture_dets)

        # Non-maximum suppression / grouping overlapping bounding boxes
        return self._filter_overlapping(detections)

    def _detect_cracks(self, image: np.ndarray, h: int, w: int, img_diag: float, asset_type: str) -> list[dict]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image.copy()
        
        # Contrast Enhancement using CLAHE
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)

        # Bilateral filter to smooth noise while preserving crack edges
        filtered = cv2.bilateralFilter(enhanced, 7, 75, 75)

        # Adaptive thresholding + Canny edge detection
        adaptive = cv2.adaptiveThreshold(
            filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 3
        )
        edges = cv2.Canny(filtered, 30, 100)

        # Combine adaptive binary & edge map
        combined = cv2.bitwise_or(adaptive, edges)

        # Morphological operations to connect crack segments along linear directions
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(combined, kernel, iterations=1)
        closed = cv2.morphologyEx(dilated, cv2.MORPH_CLOSE, kernel, iterations=2)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        crack_boxes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            arc_len = cv2.arcLength(cnt, False)

            # Filter small noise artifacts
            if arc_len < 35 or area < 20:
                continue

            x, y, bw, bh = cv2.boundingRect(cnt)
            aspect_ratio = float(bw) / bh if bh > 0 else 0
            rect_len = max(bw, bh)
            diag_len = np.sqrt(bw**2 + bh**2)

            # Cracks are typically elongated (high arc length relative to area or high aspect ratio)
            solidity = area / (bw * bh) if (bw * bh) > 0 else 1.0

            if (arc_len > 40 and solidity < 0.55) or (rect_len > 30 and (aspect_ratio > 1.8 or aspect_ratio < 0.55)):
                crack_boxes.append({
                    "bbox": [x, y, x + bw, y + bh],
                    "arc_len": arc_len,
                    "diag_len": diag_len,
                    "rect_len": rect_len,
                    "area": area,
                    "contour": cnt,
                })

        if not crack_boxes:
            return []

        # Merge nearby crack boxes into main crack region(s)
        merged_boxes = self._merge_crack_boxes(crack_boxes, h, w)

        detections = []
        for item in merged_boxes:
            x1, y1, x2, y2 = item["bbox"]
            bw, bh = x2 - x1, y2 - y1
            rect_len = max(bw, bh)
            diag_len = np.sqrt(bw**2 + bh**2)
            rel_len = diag_len / img_diag

            # Classify as Crack or Major Crack
            is_major = rel_len > 0.28 or rect_len > (max(h, w) * 0.35)
            defect_class = "Major Crack" if is_major and asset_type in {"building_wall", "building"} else "Crack"

            # Estimate Severity
            if rel_len > 0.35 or rect_len > (max(h, w) * 0.4):
                severity = "critical"
            elif rel_len > 0.20 or rect_len > (max(h, w) * 0.25):
                severity = "high"
            elif rel_len > 0.10 or rect_len > (max(h, w) * 0.12):
                severity = "medium"
            else:
                severity = "low"

            # Confidence calculation based on length and contrast signal
            confidence = min(0.72 + (rel_len * 0.5), 0.96)

            detections.append({
                "class": defect_class,
                "confidence": round(float(confidence), 2),
                "bbox": [x1, y1, x2, y2],
                "severity": severity,
                "area_ratio": round(float((bw * bh) / (h * w)), 4),
            })

        return detections

    def _merge_crack_boxes(self, boxes: list[dict], h: int, w: int) -> list[dict]:
        """Merge nearby/intersecting bounding boxes of crack segments."""
        if not boxes:
            return []

        # Expand boxes slightly to group continuous crack lines
        expanded = []
        margin = int(max(h, w) * 0.05)
        for b in boxes:
            x1, y1, x2, y2 = b["bbox"]
            expanded.append([
                max(0, x1 - margin),
                max(0, y1 - margin),
                min(w, x2 + margin),
                min(h, y2 + margin),
                b,
            ])

        # Cluster overlapping expanded boxes
        used = [False] * len(expanded)
        clusters = []

        for i in range(len(expanded)):
            if used[i]:
                continue
            cluster = [expanded[i][4]]
            used[i] = True

            cur_x1, cur_y1, cur_x2, cur_y2 = expanded[i][:4]

            for j in range(i + 1, len(expanded)):
                if used[j]:
                    continue
                nx1, ny1, nx2, ny2 = expanded[j][:4]
                # Check overlap
                if not (cur_x2 < nx1 or cur_x1 > nx2 or cur_y2 < ny1 or cur_y1 > ny2):
                    used[j] = True
                    cluster.append(expanded[j][4])
                    cur_x1 = min(cur_x1, nx1)
                    cur_y1 = min(cur_y1, ny1)
                    cur_x2 = max(cur_x2, nx2)
                    cur_y2 = max(cur_y2, ny2)

            # Combined bounding box from original unexpanded coordinates
            min_x = min(b["bbox"][0] for b in cluster)
            min_y = min(b["bbox"][1] for b in cluster)
            max_x = max(b["bbox"][2] for b in cluster)
            max_y = max(b["bbox"][3] for b in cluster)

            clusters.append({"bbox": [min_x, min_y, max_x, max_y]})

        return clusters

    def _detect_corrosion(self, image: np.ndarray, h: int, w: int, img_area: int) -> list[dict]:
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        # Rust / Corrosion tone range in HSV
        lower_rust = np.array([5, 60, 50])
        upper_rust = np.array([25, 255, 240])

        mask = cv2.inRange(hsv, lower_rust, upper_rust)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        dets = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > (img_area * 0.015):
                x, y, bw, bh = cv2.boundingRect(cnt)
                area_ratio = area / img_area
                severity = "critical" if area_ratio > 0.1 else ("high" if area_ratio > 0.05 else ("medium" if area_ratio > 0.02 else "low"))
                confidence = round(min(0.70 + (area_ratio * 1.5), 0.94), 2)
                dets.append({
                    "class": "Corrosion/Rust",
                    "confidence": confidence,
                    "bbox": [x, y, x + bw, y + bh],
                    "severity": severity,
                    "area_ratio": round(area_ratio, 4),
                })

        return dets

    def _detect_moisture_or_surface_damage(self, image: np.ndarray, h: int, w: int, img_area: int) -> list[dict]:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        # Detect very dark/wet damp patches on concrete/plaster
        _, dark_thresh = cv2.threshold(gray, 55, 255, cv2.THRESH_BINARY_INV)

        contours, _ = cv2.findContours(dark_thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        dets = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > (img_area * 0.04):
                x, y, bw, bh = cv2.boundingRect(cnt)
                area_ratio = area / img_area
                severity = "high" if area_ratio > 0.12 else "medium"
                dets.append({
                    "class": "Water/Moisture Damage",
                    "confidence": round(min(0.68 + (area_ratio * 1.2), 0.90), 2),
                    "bbox": [x, y, x + bw, y + bh],
                    "severity": severity,
                    "area_ratio": round(area_ratio, 4),
                })
        return dets

    def _filter_overlapping(self, detections: list[dict]) -> list[dict]:
        if not detections:
            return []
        # Sort by confidence descending
        sorted_dets = sorted(detections, key=lambda d: d["confidence"], reverse=True)
        filtered = []

        for d in sorted_dets:
            x1, y1, x2, y2 = d["bbox"]
            box_area = (x2 - x1) * (y2 - y1)
            if box_area <= 0:
                continue

            overlap = False
            for existing in filtered:
                ex1, ey1, ex2, ey2 = existing["bbox"]
                ix1 = max(x1, ex1)
                iy1 = max(y1, ey1)
                ix2 = min(x2, ex2)
                iy2 = min(y2, ey2)
                inter_w = max(0, ix2 - ix1)
                inter_h = max(0, iy2 - iy1)
                inter_area = inter_w * inter_h

                if inter_area / box_area > 0.5:
                    overlap = True
                    break

            if not overlap:
                filtered.append(d)

        return filtered
