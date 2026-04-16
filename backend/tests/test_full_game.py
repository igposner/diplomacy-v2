"""
End-to-end test: 7 GreedyBots play a full game (FRANCE slot simulated by GreedyBot).
Runs until game over or all of 1910 resolves, then writes tests/game_output.json.
"""
import asyncio
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_manager import GameManager
from bots.greedy_bot import GreedyBot
from diplomacy.utils.export import to_saved_game_format


def _year(phase_str: str) -> int:
    # Phase format: "SPRING 1901 MOVEMENT", "WINTER 1910 ADJUSTMENTS", etc.
    return int(phase_str.split()[1])


async def main():
    manager = GameManager(human_power='FRANCE')
    france_bot = GreedyBot('FRANCE')

    phases_processed = 0

    while not manager.game.is_game_done:
        phase = str(manager.game.phase)
        print(f"  [{phases_processed:>3}] {phase}")

        human_orders = await france_bot.decide_orders(manager.game)
        manager.submit_human_orders(human_orders)
        await manager.advance_phase()
        phases_processed += 1

        if manager.game.is_game_done:
            break

        if _year(str(manager.game.phase)) >= 1911:
            print(f"  Stopping — next phase would be {manager.game.phase} (past 1910).")
            break

    print("\n=== Final Supply Center Counts ===")
    for name, power in sorted(manager.game.powers.items()):
        centers = sorted(power.centers)
        print(f"  {name:8s}: {len(centers):2d}  {centers}")

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'game_output.json')
    saved = to_saved_game_format(manager.game)
    with open(output_path, 'w') as f:
        json.dump(saved, f, indent=2)
    print(f"\nGame saved to {output_path}")
    print("Step 1 complete — no errors.")


if __name__ == '__main__':
    asyncio.run(main())
