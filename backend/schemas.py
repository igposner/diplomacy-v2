from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    diplomacy_version: str


# Stubs — to be expanded in later steps
class OrderRequest(BaseModel):
    pass


class GameState(BaseModel):
    pass
