from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile

from app.repositories import Database
from app.schemas import Device, DeviceCreate, PlanMap
from app.services.plan_processor import PlanProcessor
from app.storage import LocalStore


class PlanService:
    ALLOWED_TYPES = {"image/png", "image/jpeg", "image/webp", "image/bmp"}

    def __init__(self, database: Database, store: LocalStore, processor: PlanProcessor) -> None:
        self.database = database
        self.store = store
        self.processor = processor

    async def upload(self, file: UploadFile, owner_id: str | None) -> PlanMap:
        if file.content_type not in self.ALLOWED_TYPES:
            raise HTTPException(status_code=415, detail="Envie uma planta em PNG, JPEG, WEBP ou BMP.")
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="O arquivo enviado está vazio.")
        plan_id = str(uuid4())
        image_path = self.store.save_image(plan_id, content)
        try:
            image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            if image is None:
                raise ValueError("Arquivo de imagem inválido.")
            plan = self.processor.process(image_path, plan_id)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        payload = plan.model_dump()
        room_id_map = {room["id"]: f"{plan_id}-{room['id']}" for room in payload["rooms"]}
        for room in payload["rooms"]:
            room["id"] = room_id_map[room["id"]]
        for previous_id, global_id in room_id_map.items():
            payload["svg"] = payload["svg"].replace(f'data-room-id="{previous_id}"', f'data-room-id="{global_id}"')
        self.database.save_plan(payload, file.filename or "planta", owner_id)
        self.store.save_plan(plan_id, {**payload, "devices": []})
        return PlanMap(**payload)

    def get_or_404(self, plan_id: str, owner_id: str | None = None) -> dict:
        plan = self.database.get_plan(plan_id, owner_id)
        if plan is None and owner_id is None:
            plan = self.store.get_plan(plan_id)
        if plan is None:
            raise HTTPException(status_code=404, detail="Planta não encontrada.")
        return plan

    def add_device(self, plan_id: str, device_input: DeviceCreate) -> Device:
        plan = self.get_or_404(plan_id)
        if device_input.x > plan["width"] or device_input.y > plan["height"]:
            raise HTTPException(status_code=422, detail="A posição do dispositivo está fora dos limites da planta.")
        device = Device(id=str(uuid4()), plan_id=plan_id, **device_input.model_dump())
        self.database.add_device(plan_id, {**device.model_dump(), "device_type": device_input.device_type})
        return device

    def delete_device(self, plan_id: str, device_id: str) -> None:
        self.get_or_404(plan_id)
        device = self.database.get_device(device_id)
        if device is None or device["plan_id"] != plan_id:
            raise HTTPException(status_code=404, detail="Dispositivo não encontrado.")
        self.database.delete_device(device_id)
