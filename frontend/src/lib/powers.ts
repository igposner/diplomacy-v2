import { MAP, type Power } from "@/lib/map";

export const POWERS: Power[] = [
  "AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY",
];

/** Where each power sits on the rose, roughly by geography, clockwise from north. */
export const BEARING: Record<Power, number> = {
  GERMANY: 0, RUSSIA: 51.4, TURKEY: 102.9, AUSTRIA: 154.3,
  ITALY: 205.7, FRANCE: 257.1, ENGLAND: 308.6,
};

/** One line on what it is like to hold the seat. */
export const CHARACTER: Record<Power, string> = {
  AUSTRIA: "Three fronts, no natural friends, and a very long memory. The hardest chair at the table.",
  ENGLAND: "An island, a fleet, and no obligation to anyone's quarrel until it suits you.",
  FRANCE: "Good borders and better prospects, which is why you are everyone's second choice of victim.",
  GERMANY: "The centre of the board. You can strike anywhere, and be struck from anywhere.",
  ITALY: "Underestimated, patient, and unusually good at choosing the moment.",
  RUSSIA: "More ground to hold than anyone. Think in years rather than turns.",
  TURKEY: "The safest corner on the board. Build slowly and strike when the rest are spent.",
};

export const homes = (p: Power): string[] => MAP.homes[p] ?? [];
