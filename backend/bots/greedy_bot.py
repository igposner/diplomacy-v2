import random
from .base_bot import BaseBot


class GreedyBot(BaseBot):
    async def decide_orders(self, game, message_history: list = None) -> list[str]:
        phase = str(game.phase)
        # Phase format: "SPRING 1901 MOVEMENT" / "FALL 1901 RETREATS" / "WINTER 1901 ADJUSTMENTS"
        if 'ADJUSTMENT' in phase:
            phase_type = 'A'
        elif 'RETREAT' in phase:
            phase_type = 'R'
        else:
            phase_type = 'M'

        orderable_locs = game.get_orderable_locations(self.power_name)
        if not orderable_locs:
            return []

        all_possible = game.get_all_possible_orders()

        if phase_type in ('R', 'A'):
            return self._random_orders(orderable_locs, all_possible)
        return self._movement_orders(game, orderable_locs, all_possible)

    # ------------------------------------------------------------------
    def _random_orders(self, orderable_locs, all_possible) -> list[str]:
        orders = []
        for loc in orderable_locs:
            possible = all_possible.get(loc, [])
            if possible:
                orders.append(random.choice(possible))
        return orders

    def _movement_orders(self, game, orderable_locs, all_possible) -> list[str]:
        owned = set(game.powers[self.power_name].centers)
        all_scs = set(game.map.scs)
        unowned_scs = all_scs - owned

        orders = []
        for loc in orderable_locs:
            possible = all_possible.get(loc, [])
            if not possible:
                continue

            sc_moves = [o for o in possible if self._targets_unowned_sc(o, unowned_scs)]
            if sc_moves:
                orders.append(random.choice(sc_moves))
                continue

            move_orders = [o for o in possible if self._is_move(o)]
            hold_orders = [o for o in possible if o.endswith(' H')]

            if move_orders and random.random() < 0.6:
                orders.append(random.choice(move_orders))
            elif hold_orders:
                orders.append(random.choice(hold_orders))
            else:
                orders.append(possible[0])

        return orders

    # ------------------------------------------------------------------
    @staticmethod
    def _is_move(order: str) -> bool:
        if ' - ' not in order:
            return False
        pre = order.split(' - ', 1)[0]
        tokens = pre.split()
        return len(tokens) == 2 and tokens[0] in ('A', 'F')

    @staticmethod
    def _targets_unowned_sc(order: str, unowned_scs: set) -> bool:
        if ' - ' not in order:
            return False
        pre = order.split(' - ', 1)[0]
        tokens = pre.split()
        if not (len(tokens) == 2 and tokens[0] in ('A', 'F')):
            return False  # support/convoy, not a simple move
        dest = order.split(' - ', 1)[1].strip().split()[0]
        dest = dest.split('/')[0].upper()
        return dest in unowned_scs
