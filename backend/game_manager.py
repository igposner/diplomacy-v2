import os
import uuid
from datetime import datetime, timezone

import diplomacy
from dotenv import load_dotenv

from bots.greedy_bot import GreedyBot

load_dotenv()

_ALL_POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']


class GameManager:
    def __init__(self, human_power: str, ai_power: str | None = None):
        self.human_power = human_power.upper()
        self.ai_power = ai_power.upper() if ai_power else None
        self.game = diplomacy.Game()
        self.chat_history: list[dict] = []

        if self.ai_power:
            from bots.gemini_agent import GeminiAgent
            api_key = os.getenv("GEMINI_API_KEY", "")
            self.ai_bot = GeminiAgent(self.ai_power, api_key)
        else:
            self.ai_bot = None

        non_bot_powers = {self.human_power}
        if self.ai_power:
            non_bot_powers.add(self.ai_power)

        self.bots: dict[str, GreedyBot] = {
            name: GreedyBot(name)
            for name in _ALL_POWERS
            if name not in non_bot_powers
        }

    # ------------------------------------------------------------------

    def submit_human_orders(self, orders: list[str]) -> None:
        self.game.set_orders(self.human_power, orders)

    async def advance_phase(self) -> None:
        if self.ai_bot and self.ai_power:
            ai_orders = await self.ai_bot.decide_orders(self.game, self.chat_history)
            self.game.set_orders(self.ai_power, ai_orders)

        for power_name, bot in self.bots.items():
            orders = await bot.decide_orders(self.game)
            self.game.set_orders(power_name, orders)

        self.game.process()

    async def send_message_to_ai(self, text: str) -> str:
        if self.ai_bot is None:
            return "No AI opponent is configured for this game."

        phase = str(self.game.phase)
        now = datetime.now(timezone.utc).isoformat()

        self.chat_history.append(
            {"from": "HUMAN", "text": text, "phase": phase, "timestamp": now}
        )

        reply = await self.ai_bot.respond_to_message(text, self.game, self.chat_history)

        self.chat_history.append(
            {
                "from": "AI",
                "text": reply,
                "phase": phase,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        return reply

    def state_for_frontend(self) -> dict:
        orderable = self.game.get_orderable_locations(self.human_power)
        all_possible = self.game.get_all_possible_orders()
        possible_orders = {loc: all_possible.get(loc, []) for loc in orderable}

        return {
            "phase": str(self.game.phase),
            "powers": {
                name: {
                    "units": list(power.units),
                    "centers": list(power.centers),
                }
                for name, power in self.game.powers.items()
            },
            "done": self.game.is_game_done,
            "orderable": orderable,
            "possible_orders": possible_orders,
            "chat_history": self.chat_history,
        }


# --- Game registry ---

GAMES: dict[str, GameManager] = {}


def create_game(human_power: str, ai_power: str | None = None) -> str:
    game_id = uuid.uuid4().hex[:8]
    GAMES[game_id] = GameManager(human_power, ai_power)
    return game_id


def get_game(game_id: str) -> GameManager | None:
    return GAMES.get(game_id)
