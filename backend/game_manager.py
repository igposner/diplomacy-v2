import uuid
import diplomacy
from bots.greedy_bot import GreedyBot

_ALL_POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']


class GameManager:
    def __init__(self, human_power: str):
        self.human_power = human_power.upper()
        self.game = diplomacy.Game()
        self.bots: dict[str, GreedyBot] = {
            name: GreedyBot(name)
            for name in _ALL_POWERS
            if name != self.human_power
        }

    def submit_human_orders(self, orders: list[str]) -> None:
        self.game.set_orders(self.human_power, orders)

    def advance_phase(self) -> None:
        for power_name, bot in self.bots.items():
            orders = bot.decide_orders(self.game)
            self.game.set_orders(power_name, orders)
        self.game.process()

    def state_for_frontend(self) -> dict:
        orderable = self.game.get_orderable_locations(self.human_power)
        all_possible = self.game.get_all_possible_orders()
        possible_orders = {loc: all_possible.get(loc, []) for loc in orderable}

        return {
            'phase': str(self.game.phase),
            'powers': {
                name: {
                    'units': list(power.units),
                    'centers': list(power.centers),
                }
                for name, power in self.game.powers.items()
            },
            'done': self.game.is_game_done,
            'orderable': orderable,
            'possible_orders': possible_orders,
        }


# --- Game registry ---

GAMES: dict[str, GameManager] = {}


def create_game(human_power: str) -> str:
    game_id = uuid.uuid4().hex[:8]
    GAMES[game_id] = GameManager(human_power)
    return game_id


def get_game(game_id: str) -> GameManager | None:
    return GAMES.get(game_id)
