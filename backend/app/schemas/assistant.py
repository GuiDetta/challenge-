from typing import Literal

from pydantic import BaseModel, Field


class AssistantMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AssistantChatRequest(BaseModel):
    owner_id: str = Field(min_length=1)
    message: str = Field(min_length=1, max_length=4000)
    history: list[AssistantMessage] = Field(default_factory=list, max_length=20)


class AssistantChatResponse(BaseModel):
    role: Literal["assistant"] = "assistant"
    content: str
    system_alerts: list[str] = Field(default_factory=list)
    provider: Literal["openai", "local"]
