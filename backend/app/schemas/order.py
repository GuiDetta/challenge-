from typing import Literal

from pydantic import BaseModel, Field


class ChargingOrderCreate(BaseModel):
    user_id: str
    charger_code: str
    energy_kwh: float = Field(gt=0, le=500)
    payment_method: Literal["pix", "paypal", "wallet"]


class ChargingOrderFinish(BaseModel):
    user_id: str
    energy_delivered_kwh: float = Field(ge=0)


class WalletTopUp(BaseModel):
    user_id: str
    amount: Literal[10, 25, 50, 100]
    method: Literal["pix", "card"] = "pix"
