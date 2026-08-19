import json
from pathlib import Path
from typing import Any


class LocalStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.plans = root / "plans"
        self.plans.mkdir(parents=True, exist_ok=True)

    def save_plan(self, plan_id: str, payload: dict[str, Any]) -> None:
        (self.plans / f"{plan_id}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_plan(self, plan_id: str) -> dict[str, Any] | None:
        path = self.plans / f"{plan_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_image(self, plan_id: str, content: bytes) -> Path:
        path = self.plans / f"{plan_id}.png"
        path.write_bytes(content)
        return path
