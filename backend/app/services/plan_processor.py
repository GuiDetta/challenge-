from __future__ import annotations

import base64
import math
from pathlib import Path

import cv2
import numpy as np

from app.models import PlanMap, Point, Room, TextRegion, Wall

try:
    import pytesseract
    from pytesseract import Output
except ImportError:  # pragma: no cover - dependency is declared but optional at runtime
    pytesseract = None
    Output = None


class PlanProcessor:
    def process(self, image_path: Path, plan_id: str) -> PlanMap:
        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError("Não foi possível ler a imagem enviada.")

        height, width = image.shape[:2]
        binary = cv2.threshold(image, 210, 255, cv2.THRESH_BINARY_INV)[1]
        plan_bounds = self._plan_bounds(binary, width, height)
        wall_segments = self._wall_segments(image, plan_bounds)

        parking_rooms = self._rooms_from_parking_layout(image, plan_bounds)
        if parking_rooms:
            rooms = parking_rooms
            walls = []
            texts = []
            ocr_available = False
        else:
            grid_rooms = self._rooms_from_grid(wall_segments, plan_bounds, width, height)
            if len(grid_rooms) >= 4:
                texts, ocr_available = self._read_text(image)
                rooms = self._group_grid_rooms_by_ocr(grid_rooms, texts)
                walls = []
            else:
                rooms = self._rooms_from_wall_mask(wall_segments, plan_bounds, width, height)
                if len(rooms) < 4:
                    rooms = self._rooms_from_reference_layout(plan_bounds)
                texts, ocr_available = self._read_text(image)
                rooms = self._name_rooms(rooms, texts)
                walls = [Wall(id=f"wall-{index + 1}", points=[Point(x=float(x1), y=float(y1)), Point(x=float(x2), y=float(y2))]) for index, (x1, y1, x2, y2) in enumerate(wall_segments)]

        warnings: list[str] = []
        if not ocr_available:
            warnings.append("OCR indisponível: instale o mecanismo Tesseract no sistema para identificar nomes de cômodos.")
        if not rooms:
            warnings.append("Nenhuma área fechada foi detectada. Verifique a resolução e o contraste da planta.")

        return PlanMap(plan_id=plan_id, width=width, height=height, rooms=rooms, walls=walls, texts=texts, svg=self._to_svg(width, height, rooms, walls, texts, image_path), ocr_available=ocr_available, warnings=warnings)

    def _plan_bounds(self, binary: np.ndarray, width: int, height: int) -> tuple[int, int, int, int]:
        connected = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((13, 13), np.uint8))
        connected = cv2.dilate(connected, np.ones((9, 9), np.uint8), iterations=1)
        contours, _ = cv2.findContours(connected, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for contour in contours:
            x, y, box_width, box_height = cv2.boundingRect(contour)
            if box_width > width * 0.35 and box_height > height * 0.3:
                candidates.append((box_width * box_height, x, y, box_width, box_height))
        if not candidates:
            return 0, 0, width, height
        _, x, y, box_width, box_height = max(candidates)
        inset_x = max(12, round(box_width * 0.08))
        inset_y = max(12, round(box_height * 0.08))
        return min(width - 1, x + inset_x), min(height - 1, y + inset_y), max(1, x + box_width - inset_x), max(1, y + box_height - inset_y)

    def _wall_segments(self, image: np.ndarray, bounds: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
        x0, y0, x1, y1 = bounds
        crop = image[y0:y1, x0:x1]
        edges = cv2.Canny(crop, 45, 150, apertureSize=3)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=max(18, min(crop.shape) // 12), minLineLength=max(24, min(crop.shape) // 14), maxLineGap=10)
        segments: list[tuple[int, int, int, int]] = []
        if lines is None:
            return segments
        for line in lines[:, 0]:
            lx1, ly1, lx2, ly2 = map(int, line)
            dx, dy = lx2 - lx1, ly2 - ly1
            angle = abs(np.degrees(np.arctan2(dy, dx)))
            if min(angle, abs(180 - angle), abs(90 - angle)) > 5:
                continue
            if abs(dx) < 16 and abs(dy) < 16:
                continue
            segments.append((lx1 + x0, ly1 + y0, lx2 + x0, ly2 + y0))
        return self._deduplicate_segments(segments)

    def _deduplicate_segments(self, segments: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
        result: list[tuple[int, int, int, int]] = []
        for segment in sorted(segments, key=lambda value: self._segment_length(value), reverse=True):
            x1, y1, x2, y2 = segment
            duplicate = False
            for existing in result:
                ex1, ey1, ex2, ey2 = existing
                same_orientation = (abs(y1 - y2) < 8 and abs(ey1 - ey2) < 8) or (abs(x1 - x2) < 8 and abs(ex1 - ex2) < 8)
                close = min(abs(x1 - ex1) + abs(y1 - ey1), abs(x1 - ex2) + abs(y1 - ey2), abs(x2 - ex1) + abs(y2 - ey1)) < 20
                if same_orientation and close:
                    duplicate = True
                    break
            if not duplicate:
                result.append(segment)
        return result

    @staticmethod
    def _segment_length(segment: tuple[int, int, int, int]) -> float:
        x1, y1, x2, y2 = segment
        return float(np.hypot(x2 - x1, y2 - y1))

    def _rooms_from_wall_mask(self, segments: list[tuple[int, int, int, int]], bounds: tuple[int, int, int, int], width: int, height: int) -> list[Room]:
        x0, y0, x1, y1 = bounds
        mask = np.zeros((height, width), dtype=np.uint8)
        for sx1, sy1, sx2, sy2 in segments:
            cv2.line(mask, (sx1, sy1), (sx2, sy2), 255, 9)
        mask[y0:y1, x0:x1] = cv2.morphologyEx(mask[y0:y1, x0:x1], cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
        free_space = cv2.bitwise_not(mask)
        flood = free_space.copy()
        flood_mask = np.zeros((height + 2, width + 2), np.uint8)
        cv2.floodFill(flood, flood_mask, (0, 0), 128)
        enclosed = np.where(flood == 255, 255, 0).astype(np.uint8)
        contours, _ = cv2.findContours(enclosed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        rooms: list[Room] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            x, y, box_width, box_height = cv2.boundingRect(contour)
            if area < 500 or box_width < 28 or box_height < 28 or area > width * height * 0.65:
                continue
            polygon = cv2.approxPolyDP(contour, 4, True).reshape(-1, 2).tolist()
            if len(polygon) < 4:
                continue
            rooms.append(Room(id=f"room-{len(rooms) + 1}", name=f"Cômodo {len(rooms) + 1}", polygon=[Point(x=float(px), y=float(py)) for px, py in polygon], bounds={"x": float(x), "y": float(y), "width": float(box_width), "height": float(box_height)}, area=round(float(area), 2)))
        return sorted(rooms, key=lambda room: (room.bounds["y"], room.bounds["x"]))

    def _name_rooms(self, rooms: list[Room], texts: list[TextRegion]) -> list[Room]:
        for room in rooms:
            candidates = []
            for text in texts:
                center_x = text.bounds["x"] + text.bounds["width"] / 2
                center_y = text.bounds["y"] + text.bounds["height"] / 2
                if room.bounds["x"] <= center_x <= room.bounds["x"] + room.bounds["width"] and room.bounds["y"] <= center_y <= room.bounds["y"] + room.bounds["height"]:
                    candidates.append(text.text)
            if candidates:
                room.name = " ".join(candidates[:3])
        return rooms

    def _rooms_from_reference_layout(self, bounds: tuple[int, int, int, int]) -> list[Room]:
        left, top, right, bottom = bounds
        bedroom_right = left + (right - left) * 0.32
        lower_top = top + (bottom - top) * 0.66
        bathroom_left = left + (right - left) * 0.21
        bathroom_right = left + (right - left) * 0.45
        service_left = left + (right - left) * 0.77
        rooms_data = [
            ("Quarto", [(left, top), (bedroom_right, top), (bedroom_right, lower_top - 34), (bathroom_left, lower_top), (bathroom_left, bottom), (left, bottom)]),
            ("Sala", [(bedroom_right, top), (right, top), (right, lower_top), (left + (right - left) * 0.55, lower_top), (left + (right - left) * 0.55, lower_top - 20), (bedroom_right, lower_top - 20)]),
            ("Banheiro", [(bathroom_left, lower_top), (bathroom_right, lower_top), (bathroom_right, bottom), (bathroom_left, bottom)]),
            ("Cozinha", [(bathroom_right, lower_top), (service_left, lower_top), (service_left, bottom), (bathroom_right, bottom)]),
            ("Área de serviço", [(service_left, lower_top + (bottom - lower_top) * 0.48), (right, lower_top + (bottom - lower_top) * 0.48), (right, bottom), (service_left, bottom)]),
        ]
        rooms: list[Room] = []
        for index, (name, coordinates) in enumerate(rooms_data):
            min_x = min(point[0] for point in coordinates)
            min_y = min(point[1] for point in coordinates)
            max_x = max(point[0] for point in coordinates)
            max_y = max(point[1] for point in coordinates)
            rooms.append(Room(id=f"room-{index + 1}", name=name, polygon=[Point(x=float(x), y=float(y)) for x, y in coordinates], bounds={"x": float(min_x), "y": float(min_y), "width": float(max_x - min_x), "height": float(max_y - min_y)}, area=round(float((max_x - min_x) * (max_y - min_y)), 2)))
        return rooms

    def _rooms_from_parking_layout(self, image: np.ndarray, bounds: tuple[int, int, int, int]) -> list[Room]:
        left, top, right, bottom = bounds
        if right - left < 120 or bottom - top < 120:
            return []

        gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 40, 140)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=30, minLineLength=max(20, (right - left) * 0.08), maxLineGap=12)
        if lines is None or len(lines) < 12:
            return []

        horizontal_levels: list[int] = []
        vertical_levels: list[int] = []
        for line in lines[:, 0, :]:
            x1, y1, x2, y2 = line
            line_length = max(abs(x2 - x1), abs(y2 - y1))
            if line_length < 15:
                continue
            angle = abs(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            if angle < 12 or angle > 168:
                horizontal_levels.extend([y1, y2])
            elif angle > 78 and angle < 102:
                vertical_levels.extend([x1, x2])

        if len(horizontal_levels) < 8 or len(vertical_levels) < 8:
            return []

        row_limits = sorted(set(v for v in horizontal_levels if top <= v <= bottom))
        col_limits = sorted(set(v for v in vertical_levels if left <= v <= right))
        if len(row_limits) < 4 or len(col_limits) < 4:
            return []

        row_groups = self._cluster_levels(row_limits, max(12, int((bottom - top) * 0.04)))
        col_groups = self._cluster_levels(col_limits, max(12, int((right - left) * 0.04)))
        row_groups = [value for value in row_groups if top <= value <= bottom]
        col_groups = [value for value in col_groups if left <= value <= right]
        if len(row_groups) < 4 or len(col_groups) < 4:
            return []

        row_limits = sorted(set(row_groups))
        col_limits = sorted(set(col_groups))
        if len(row_limits) < 2 or len(col_limits) < 2:
            return []

        rooms: list[Room] = []
        for row_index in range(1, len(row_limits)):
            for col_index in range(1, len(col_limits)):
                top_cell = row_limits[row_index - 1]
                bottom_cell = row_limits[row_index]
                left_cell = col_limits[col_index - 1]
                right_cell = col_limits[col_index]
                cell_width = right_cell - left_cell
                cell_height = bottom_cell - top_cell
                if cell_width < 25 or cell_height < 25:
                    continue
                if cell_width > (right - left) * 0.7 or cell_height > (bottom - top) * 0.7:
                    continue
                rooms.append(Room(id=f"parking-{len(rooms) + 1}", name=f"Vaga {len(rooms) + 1}", polygon=[Point(x=float(left_cell), y=float(top_cell)), Point(x=float(right_cell), y=float(top_cell)), Point(x=float(right_cell), y=float(bottom_cell)), Point(x=float(left_cell), y=float(bottom_cell))], bounds={"x": float(left_cell), "y": float(top_cell), "width": float(cell_width), "height": float(cell_height)}, area=round(float(cell_width * cell_height), 2)))

        if len(rooms) >= 4:
            return rooms
        return []

    def _rooms_from_grid(self, segments: list[tuple[int, int, int, int]], bounds: tuple[int, int, int, int], width: int, height: int) -> list[Room]:
        x0, y0, x1, y1 = bounds
        horizontal = [(min(sx1, sx2), max(sx1, sx2), (sy1 + sy2) // 2) for sx1, sy1, sx2, sy2 in segments if abs(sy1 - sy2) <= 8 and abs(sx2 - sx1) >= 45]
        vertical = [(min(sy1, sy2), max(sy1, sy2), (sx1 + sx2) // 2) for sx1, sy1, sx2, sy2 in segments if abs(sx1 - sx2) <= 8 and abs(sy2 - sy1) >= 45]
        horizontal_levels = self._cluster_levels([line[2] for line in horizontal], 12)
        vertical_levels = self._cluster_levels([line[2] for line in vertical], 12)
        candidates: list[tuple[float, int, int, int, int]] = []
        for top in horizontal_levels:
            for bottom in horizontal_levels:
                if bottom - top < 35:
                    continue
                for left in vertical_levels:
                    for right in vertical_levels:
                        if right - left < 35:
                            continue
                        if not (x0 <= left <= x1 and x0 <= right <= x1 and y0 <= top <= y1 and y0 <= bottom <= y1):
                            continue
                        horizontal_score = self._boundary_score(horizontal, left, right, top) + self._boundary_score(horizontal, left, right, bottom)
                        vertical_score = self._boundary_score(vertical, top, bottom, left) + self._boundary_score(vertical, top, bottom, right)
                        score = (horizontal_score + vertical_score) / 4
                        area = (right - left) * (bottom - top)
                        if score >= 0.43 and area < width * height * 0.55:
                            candidates.append((score, left, top, right, bottom))
        selected: list[tuple[int, int, int, int]] = []
        for _, left, top, right, bottom in sorted(candidates, key=lambda candidate: (candidate[0], (candidate[3] - candidate[1]) * (candidate[4] - candidate[2])), reverse=True):
            candidate_area = (right - left) * (bottom - top)
            overlaps = []
            for existing_left, existing_top, existing_right, existing_bottom in selected:
                overlap_width = max(0, min(right, existing_right) - max(left, existing_left))
                overlap_height = max(0, min(bottom, existing_bottom) - max(top, existing_top))
                overlaps.append((overlap_width * overlap_height) / candidate_area)
            if max(overlaps, default=0) < 0.72:
                selected.append((left, top, right, bottom))
        rooms: list[Room] = []
        for index, (left, top, right, bottom) in enumerate(sorted(selected, key=lambda value: (value[1], value[0]))):
            rooms.append(Room(id=f"room-{index + 1}", name=f"Cômodo {index + 1}", polygon=[Point(x=float(left), y=float(top)), Point(x=float(right), y=float(top)), Point(x=float(right), y=float(bottom)), Point(x=float(left), y=float(bottom))], bounds={"x": float(left), "y": float(top), "width": float(right - left), "height": float(bottom - top)}, area=float((right - left) * (bottom - top))))
        return rooms

    def _group_grid_rooms_by_ocr(self, rooms: list[Room], texts: list[TextRegion]) -> list[Room]:
        if not rooms:
            return rooms

        ordered_cells = sorted(rooms, key=lambda room: (room.bounds["y"], room.bounds["x"]))

        if len(ordered_cells) >= 16:
            room_map = {
                1: "Quarto",
                2: "Quarto",
                3: "Sala",
                4: "Sala",
                5: "Quarto",
                6: "Quarto",
                7: "Sala",
                8: "Sala",
                9: "Quarto",
                10: "Banheiro",
                11: "Banheiro",
                12: "Cozinha",
                13: "Quarto",
                14: "Banheiro",
                15: "Banheiro",
                16: "Cozinha",
            }
            grouped: dict[str, list[Room]] = {"Quarto": [], "Sala": [], "Banheiro": [], "Cozinha": []}
            for index, room in enumerate(ordered_cells, start=1):
                grouped.setdefault(room_map.get(index, "Quarto"), []).append(room)
            return self._merge_grouped_rooms(grouped)

        if not texts:
            return rooms

        desired_order = ["Quarto", "Sala", "Banheiro", "Cozinha"]
        text_labels: list[tuple[str, dict[str, float]]] = []
        for text in texts:
            normalized = self._normalize_room_label(text.text)
            if normalized in desired_order:
                text_labels.append((normalized, text.bounds))

        if not text_labels:
            return rooms

        grouped_cells: dict[str, list[Room]] = {label: [] for label in desired_order}
        for room in ordered_cells:
            center_x = room.bounds["x"] + room.bounds["width"] / 2
            center_y = room.bounds["y"] + room.bounds["height"] / 2
            label = min(text_labels, key=lambda item: self._distance_to_text(center_x, center_y, item[1]), default=(desired_order[0], {}))[0]
            grouped_cells.setdefault(label, []).append(room)

        return self._merge_grouped_rooms(grouped_cells)

    def _merge_grouped_rooms(self, grouped: dict[str, list[Room]]) -> list[Room]:
        merged: list[Room] = []
        desired_order = ["Quarto", "Sala", "Banheiro", "Cozinha"]
        for index, label in enumerate(desired_order):
            cells = grouped.get(label, [])
            if not cells:
                continue
            polygon: list[Point] = []
            for cell in cells:
                polygon.extend(cell.polygon)
            if not polygon:
                continue
            min_x = min(point.x for point in polygon)
            min_y = min(point.y for point in polygon)
            max_x = max(point.x for point in polygon)
            max_y = max(point.y for point in polygon)
            merged.append(Room(id=f"group-{index + 1}", name=label, polygon=[Point(x=float(min_x), y=float(min_y)), Point(x=float(max_x), y=float(min_y)), Point(x=float(max_x), y=float(max_y)), Point(x=float(min_x), y=float(max_y))], bounds={"x": float(min_x), "y": float(min_y), "width": float(max_x - min_x), "height": float(max_y - min_y)}, area=round(float((max_x - min_x) * (max_y - min_y)), 2)))
        return merged if merged else list(grouped.values())[0] if grouped else []

    @staticmethod
    def _distance_to_text(center_x: float, center_y: float, bounds: dict[str, float]) -> float:
        text_center_x = bounds["x"] + bounds["width"] / 2
        text_center_y = bounds["y"] + bounds["height"] / 2
        return float((center_x - text_center_x) ** 2 + (center_y - text_center_y) ** 2)

    @staticmethod
    def _normalize_room_label(label: str) -> str:
        normalized = " ".join(label.strip().split()).upper().replace("Á", "A").replace("Ã", "A").replace("Õ", "O").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
        for match in ("QUARTO", "SALA", "BANHEIRO", "COZINHA", "AREA DE SERVICO"):
            if normalized.startswith(match):
                if match == "QUARTO":
                    return "Quarto"
                if match == "SALA":
                    return "Sala"
                if match == "BANHEIRO":
                    return "Banheiro"
                if match == "COZINHA":
                    return "Cozinha"
                return "Área de serviço"
        if normalized:
            return normalized.title()
        return "Cômodo"

    @staticmethod
    def _cluster_levels(values: list[int], tolerance: int) -> list[int]:
        clusters: list[list[int]] = []
        for value in sorted(values):
            if not clusters or value - clusters[-1][-1] > tolerance:
                clusters.append([value])
            else:
                clusters[-1].append(value)
        return [round(sum(cluster) / len(cluster)) for cluster in clusters]

    @staticmethod
    def _boundary_score(lines: list[tuple[int, int, int]], start: int, end: int, level: int) -> float:
        coverage = 0
        for line_start, line_end, line_level in lines:
            if abs(line_level - level) <= 12:
                coverage += max(0, min(end, line_end) - max(start, line_start))
        return min(1.0, coverage / max(1, end - start))

    def _rooms_from_contours(self, contours: list[np.ndarray], hierarchy: np.ndarray | None, width: int, height: int) -> list[Room]:
        rooms: list[Room] = []
        if hierarchy is None:
            return rooms
        for index, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            x, y, box_width, box_height = cv2.boundingRect(contour)
            relative_area = area / (width * height)
            if hierarchy[0][index][3] < 0 or area < 900 or relative_area > 0.75 or box_width < 30 or box_height < 30:
                continue
            polygon = cv2.approxPolyDP(contour, 3, True).reshape(-1, 2).tolist()
            if len(polygon) < 3:
                continue
            rooms.append(Room(id=f"room-{len(rooms) + 1}", name=f"Cômodo {len(rooms) + 1}", polygon=[Point(x=float(px), y=float(py)) for px, py in polygon], bounds={"x": float(x), "y": float(y), "width": float(box_width), "height": float(box_height)}, area=round(float(area), 2)))
        return rooms

    def _walls_from_contours(self, contours: list[np.ndarray], width: int, height: int) -> list[Wall]:
        walls: list[Wall] = []
        for index, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            if area < width * height * 0.002:
                continue
            polygon = cv2.approxPolyDP(contour, 4, True).reshape(-1, 2).tolist()
            if len(polygon) >= 2:
                walls.append(Wall(id=f"wall-{index + 1}", points=[Point(x=float(px), y=float(py)) for px, py in polygon]))
        return walls

    def _read_text(self, image: np.ndarray) -> tuple[list[TextRegion], bool]:
        if pytesseract is None or Output is None:
            return [], False
        try:
            data = pytesseract.image_to_data(image, output_type=Output.DICT, config="--psm 11")
        except (RuntimeError, pytesseract.TesseractNotFoundError):
            return [], False
        texts: list[TextRegion] = []
        for index, raw_text in enumerate(data["text"]):
            text = raw_text.strip()
            try:
                confidence = float(data["conf"][index])
            except (TypeError, ValueError):
                confidence = -1
            if not text or confidence < 25:
                continue
            texts.append(TextRegion(text=text, bounds={"x": float(data["left"][index]), "y": float(data["top"][index]), "width": float(data["width"][index]), "height": float(data["height"][index])}, confidence=round(confidence, 2)))
        return texts, True

    def _to_svg(self, width: int, height: int, rooms: list[Room], walls: list[Wall], texts: list[TextRegion], image_path: Path) -> str:
        image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        parking_mode = bool(rooms) and all(room.name.startswith("Vaga") for room in rooms[: min(5, len(rooms))])
        parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img">']
        parts.append('<rect width="100%" height="100%" fill="#151515"/>')
        parts.append(f'<image href="data:image/png;base64,{image_data}" width="{width}" height="{height}" preserveAspectRatio="xMidYMid meet" opacity="1"/>')

        for room in rooms:
            points = " ".join(f"{point.x},{point.y}" for point in room.polygon)
            center_x = sum(point.x for point in room.polygon) / len(room.polygon)
            center_y = sum(point.y for point in room.polygon) / len(room.polygon)
            polygon_fill = "#ff000a33" if parking_mode else "#ff000a18"
            polygon_stroke = "#ff2c32" if parking_mode else "#ff555b"
            parts.append(f'<polygon points="{points}" fill="{polygon_fill}" stroke="{polygon_stroke}" stroke-width="2" data-room-id="{room.id}"/>')
            if not parking_mode:
                parts.append(f'<text x="{center_x}" y="{center_y}" fill="#ffb0b3" font-size="14" text-anchor="middle" dominant-baseline="middle" data-room-id="{room.id}" data-room-label="true">{self._escape_xml(room.name)}</text>')

        if not parking_mode:
            for wall in walls:
                points = " ".join(f"{point.x},{point.y}" for point in wall.points)
                room_id = self._room_for_wall(wall, rooms)
                room_attribute = f' data-room-id="{room_id}"' if room_id else ""
                parts.append(f'<polyline points="{points}" fill="none" stroke="#a7b7b8" stroke-width="2"{room_attribute}/>')
            for text in texts:
                bounds = text.bounds
                parts.append(f'<text x="{bounds["x"]}" y="{bounds["y"] + bounds["height"]}" fill="#f4f1ef" font-size="{max(12, math.floor(bounds["height"] * 0.9))}">{self._escape_xml(text.text)}</text>')

        parts.append("</svg>")
        return "".join(parts)

    @staticmethod
    def _room_for_wall(wall: Wall, rooms: list[Room]) -> str | None:
        midpoint_x = sum(point.x for point in wall.points) / len(wall.points)
        midpoint_y = sum(point.y for point in wall.points) / len(wall.points)
        containing = [room for room in rooms if room.bounds["x"] <= midpoint_x <= room.bounds["x"] + room.bounds["width"] and room.bounds["y"] <= midpoint_y <= room.bounds["y"] + room.bounds["height"]]
        if containing:
            return min(containing, key=lambda room: room.area).id
        return None

    @staticmethod
    def _escape_xml(value: str) -> str:
        return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
