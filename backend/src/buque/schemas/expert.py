from datetime import datetime

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    snapshot_id: int
    sku: str | None = None
    warehouse: str | None = None
    seed: str | None = None


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)


class AdoptExplanationRequest(BaseModel):
    message_id: int


class ExplanationDraftOut(BaseModel):
    sku: str | None = None
    warehouse: str | None = None
    primary_explanation: str
    secondary_explanation: str | None = None
    tertiary_explanation: str | None = None
    explanation_tags: list[str] = []
    key_evidence: list[str] = []
    suggested_action: str
    responsible_role: str | None = None
    action_deadline: str | None = None
    require_human_confirm: bool = True
    confidence_note: str | None = None


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    explanation_draft: ExplanationDraftOut | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionOut(BaseModel):
    id: int
    snapshot_id: int
    sku: str | None = None
    warehouse: str | None = None
    title: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionDetailOut(ChatSessionOut):
    messages: list[ChatMessageOut]


class AdoptExplanationOut(BaseModel):
    snapshot_id: int
    sku: str
    primary_explanation: str
    suggested_action: str
