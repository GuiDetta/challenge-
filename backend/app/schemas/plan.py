from pydantic import BaseModel, Field


class Point(BaseModel):
    x: float
    y: float


class Room(BaseModel):
    id: str
    name: str
    polygon: list[Point]
    bounds: dict[str, float]
    area: float


class Wall(BaseModel):
    id: str
    points: list[Point]


class TextRegion(BaseModel):
    text: str
    bounds: dict[str, float]
    confidence: float | None = None


class PlanMap(BaseModel):
    plan_id: str
    owner_id: str | None = None
    width: int
    height: int
    rooms: list[Room]
    walls: list[Wall]
    texts: list[TextRegion]
    svg: str
    ocr_available: bool
    warnings: list[str] = Field(default_factory=list)
