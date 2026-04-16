import asyncio
import json
import logging

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from .base_bot import BaseBot
from .greedy_bot import GreedyBot
from .prompts import PERSONAS

logger = logging.getLogger(__name__)


class GeminiAgent(BaseBot):
    def __init__(self, power_name: str, api_key: str):
        super().__init__(power_name)
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel("gemini-2.5-flash-lite")
        self._fallback = GreedyBot(power_name)
        self._persona = PERSONAS.get(power_name, "You are a Diplomacy player.")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def decide_orders(self, game, message_history: list = None) -> list[str]:
        try:
            return await self._gemini_decide(game, message_history or [])
        except Exception as exc:
            logger.error("GeminiAgent.decide_orders failed (%s) — GreedyBot fallback", exc)
            return await self._fallback.decide_orders(game)

    async def respond_to_message(self, text: str, game, message_history: list) -> str:
        try:
            return await self._gemini_respond(text, game, message_history)
        except Exception as exc:
            logger.error("GeminiAgent.respond_to_message failed (%s)", exc)
            return "(Diplomatic communications have been temporarily interrupted.)"

    # ------------------------------------------------------------------
    # Internal: Gemini calls
    # ------------------------------------------------------------------

    async def _gemini_decide(self, game, message_history: list) -> list[str]:
        orderable_locs = game.get_orderable_locations(self.power_name)
        if not orderable_locs:
            return []

        all_possible = game.get_all_possible_orders()
        valid_set = {o for loc in orderable_locs for o in all_possible.get(loc, [])}

        prompt = self._order_prompt(game, message_history, orderable_locs, all_possible)
        raw = await self._call(prompt, json_mode=True)

        try:
            parsed = json.loads(raw)
            orders = parsed.get("orders", [])
            reasoning = parsed.get("reasoning", "")
            logger.info("[%s] Gemini reasoning: %s", self.power_name, reasoning)
        except (json.JSONDecodeError, AttributeError) as exc:
            raise ValueError(f"Gemini returned non-JSON: {exc}") from exc

        invalid = [o for o in orders if o not in valid_set]
        if invalid:
            raise ValueError(f"Gemini returned invalid orders: {invalid}")

        return orders

    async def _gemini_respond(self, text: str, game, message_history: list) -> str:
        prompt = self._chat_prompt(text, game, message_history)
        return await self._call(prompt, json_mode=False)

    async def _call(self, prompt: str, json_mode: bool) -> str:
        if json_mode:
            gen_config = GenerationConfig(
                response_mime_type="application/json",
                max_output_tokens=512,
            )
        else:
            gen_config = GenerationConfig(max_output_tokens=600)
        for attempt in range(2):
            try:
                response = await self._model.generate_content_async(
                    prompt, generation_config=gen_config
                )
                return response.text
            except Exception as exc:
                if attempt == 0:
                    logger.warning("Gemini API error (attempt 1): %s — retrying in 2s", exc)
                    await asyncio.sleep(2)
                else:
                    raise

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _order_prompt(self, game, message_history, orderable_locs, all_possible) -> str:
        phase = str(game.phase)
        board = self._board_summary(game)
        legal = "\n".join(
            f"  {loc}: {', '.join(all_possible.get(loc, []))}"
            for loc in orderable_locs
        )
        history = self._fmt_history(message_history)

        return (
            f"You are playing Diplomacy as {self.power_name}.\n\n"
            f"{self._persona}\n\n"
            f"=== Board State (Phase: {phase}) ===\n{board}\n\n"
            f"=== Your Legal Orders ===\n{legal}\n\n"
            f"=== Recent Conversation with the Human Player ===\n"
            f"{history or '(No messages yet)'}\n\n"
            f"=== Instructions ===\n"
            f"Choose your orders verbatim from the legal options above. Every orderable location "
            f"must have exactly one order. Return a JSON object with exactly two fields:\n"
            f'{{"orders": ["order1", "order2", ...], "reasoning": "brief strategy note"}}'
        )

    def _chat_prompt(self, text: str, game, message_history: list) -> str:
        phase = str(game.phase)
        board = self._brief_board(game)
        prior = self._fmt_history(message_history[:-1])

        return (
            f"You are playing Diplomacy as {self.power_name}.\n\n"
            f"{self._persona}\n\n"
            f"=== Current Situation (Phase: {phase}) ===\n{board}\n\n"
            f"=== Conversation So Far ===\n{prior or '(Start of conversation)'}\n\n"
            f"=== The human player says ===\n\"{text}\"\n\n"
            f"=== Instructions ===\n"
            f"Respond in character as {self.power_name}. Be concise (under 150 words), "
            f"strategic, and stay in character. Do not acknowledge being an AI."
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _board_summary(game) -> str:
        lines = []
        for name, power in sorted(game.powers.items()):
            units = ", ".join(sorted(power.units)) or "none"
            centers = ", ".join(sorted(power.centers)) or "none"
            lines.append(f"  {name:8s}: units=[{units}]  centers=[{centers}]")
        return "\n".join(lines)

    @staticmethod
    def _brief_board(game) -> str:
        lines = []
        for name, power in sorted(game.powers.items()):
            lines.append(f"  {name:8s}: {len(power.centers)} centers, {len(power.units)} units")
        return "\n".join(lines)

    @staticmethod
    def _fmt_history(history: list) -> str:
        return "\n".join(
            f"  [{e['phase']}] {e['from']}: {e['text']}"
            for e in history
        )
