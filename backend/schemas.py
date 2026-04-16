from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field


# --- REST schemas ---

class CreateGameRequest(BaseModel):
    human_power: str
    ai_power: str | None = None

class CreateGameResponse(BaseModel):
    game_id: str


# --- WebSocket: client → server ---

class SubmitOrdersMessage(BaseModel):
    type: Literal["submit_orders"]
    orders: list[str]

class AdvancePhaseMessage(BaseModel):
    type: Literal["advance_phase"]

class GetStateMessage(BaseModel):
    type: Literal["get_state"]

class SendMessageMessage(BaseModel):
    type: Literal["send_message"]
    text: str

ClientMessage = Annotated[
    Union[SubmitOrdersMessage, AdvancePhaseMessage, GetStateMessage, SendMessageMessage],
    Field(discriminator="type"),
]


# --- WebSocket: server → client ---

class StateMessage(BaseModel):
    type: Literal["state"] = "state"
    data: dict

class ErrorMessage(BaseModel):
    type: Literal["error"] = "error"
    message: str

class GameOverMessage(BaseModel):
    type: Literal["game_over"] = "game_over"
    winners: list[str]


# --- Legacy stubs ---

class HealthResponse(BaseModel):
    status: str
    diplomacy_version: str
