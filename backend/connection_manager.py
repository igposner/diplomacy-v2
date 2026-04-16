import logging
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, game_id: str) -> None:
        await websocket.accept()
        if game_id in self._connections:
            logger.warning("Replacing existing connection for game %s", game_id)
        self._connections[game_id] = websocket

    def disconnect(self, game_id: str) -> None:
        self._connections.pop(game_id, None)

    async def send_to(self, websocket: WebSocket, message: dict) -> None:
        await websocket.send_json(message)

    async def broadcast_state(self, game_id: str, state: dict) -> None:
        ws = self._connections.get(game_id)
        if ws:
            await ws.send_json({"type": "state", "data": state})
