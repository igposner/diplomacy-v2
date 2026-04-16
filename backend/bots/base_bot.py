from abc import ABC, abstractmethod


class BaseBot(ABC):
    def __init__(self, power_name: str):
        self.power_name = power_name

    @abstractmethod
    async def decide_orders(self, game, message_history: list = None) -> list[str]:
        """Return a list of order strings for this power given the current game state."""
