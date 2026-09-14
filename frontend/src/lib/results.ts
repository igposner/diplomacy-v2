export interface OrderResult {
  power: string; order: string; english: string; outcomes: string[]; ok: boolean;
}

/** What the engine reports about the phase that just resolved. The board draws
    the failures; there is deliberately no written report in the sidebar. */
export interface PhaseResult {
  phase: string;
  centerChanges: Record<string, string>;
  dislodged: Record<string, string[]>;
  orders: OrderResult[];
}
