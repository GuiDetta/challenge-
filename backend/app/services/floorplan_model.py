from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class FloorplanCellSample:
    room: str
    cells: list[tuple[int, int]]


class FloorplanSyntheticDataset:
    """Gera um dataset sintético para o padrão 4x4 de plantas residenciais.

    O padrão é o mesmo usado no exemplo do usuário:
    Quarto = 1,2,5,6,9,13
    Sala = 3,4,7,8
    Banheiro = 10,11,14,15
    Cozinha = 12,16
    """

    CELL_LAYOUT = {
        "Quarto": [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0), (3, 0)],
        "Sala": [(0, 2), (0, 3), (1, 2), (1, 3)],
        "Banheiro": [(2, 1), (2, 2), (3, 1), (3, 2)],
        "Cozinha": [(2, 3), (3, 3)],
    }

    def generate(self, samples_per_variant: int = 120) -> list[dict[str, object]]:
        dataset: list[dict[str, object]] = []
        for _ in range(samples_per_variant):
            shift_x = random.uniform(-12, 12)
            shift_y = random.uniform(-10, 10)
            scale = random.uniform(0.92, 1.08)
            for room, cells in self.CELL_LAYOUT.items():
                feature_cells = []
                for row, col in cells:
                    x = (col + 0.5) * 100 * scale + shift_x
                    y = (row + 0.5) * 100 * scale + shift_y
                    feature_cells.append([x, y])
                data = {
                    "room": room,
                    "cells": feature_cells,
                    "grid_size": [4, 4],
                }
                dataset.append(data)
        return dataset


class SimpleRoomModel:
    """Modelo simples de centroides para agrupar células por tipo de cômodo."""

    def __init__(self) -> None:
        self.centroids: dict[str, np.ndarray] = {}

    def fit(self, dataset: list[dict[str, object]]) -> None:
        groups: dict[str, list[np.ndarray]] = {}
        for item in dataset:
            room_name = str(item["room"])
            for cell in item["cells"]:
                groups.setdefault(room_name, []).append(np.asarray(cell, dtype=float))

        for room_name, points in groups.items():
            self.centroids[room_name] = np.mean(np.asarray(points), axis=0)

    def predict_room(self, cell: tuple[float, float]) -> str:
        if not self.centroids:
            return "Quarto"
        point = np.asarray(cell, dtype=float)
        distances = {room: float(np.linalg.norm(point - centroid)) for room, centroid in self.centroids.items()}
        return min(distances, key=distances.get)


def main() -> None:
    dataset = FloorplanSyntheticDataset().generate(samples_per_variant=150)
    model = SimpleRoomModel()
    model.fit(dataset)
    output_path = Path(__file__).resolve().parents[2] / "data" / "floorplan_training_dataset.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dataset[:10], ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dataset sintético gerado em {output_path}")
    print(f"Centroides atuais: {json.dumps({room: centroid.tolist() for room, centroid in model.centroids.items()}, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
