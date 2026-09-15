"use client";

import { useMemo, useState } from "react";
import { BORDER_INK, FILL, LABEL_INK, PARCHMENT_DARK, TOKEN, type Power } from "@/lib/map";

export interface Press { sender: string; to: string; text: string; phase: string; at: string;
                         kind?: "text" | "commitment" }

const POWERS: Power[] = ["AUSTRIA", "ENGLAND", "FRANCE", "GERMANY", "ITALY", "RUSSIA", "TURKEY"];

export default function PressPanel({
  me, messages, onSend, agents = false,
}: { me: Power; messages: Press[]; onSend: (to: string, text: string) => Promise<void>;
     agents?: boolean }) {
  const others = POWERS.filter((p) => p !== me);
  const [channel, setChannel] = useState<string>("GLOBAL");
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);

  const shown = useMemo(
    () => messages.filter((m) =>
      channel === "GLOBAL"
        ? m.to === "GLOBAL"
        : (m.sender === channel && m.to === me) || (m.sender === me && m.to === channel)),
    [messages, channel, me]
  );

  const send = async () => {
    const text = draft.trim();
    if (!text) return;
    setSending(true);
    try { await onSend(channel, text); setDraft(""); } finally { setSending(false); }
  };

  const chip = (id: string, label: string, colour?: string) => {
    const on = channel === id;
    const unread = messages.filter((m) =>
      id === "GLOBAL" ? m.to === "GLOBAL" : m.sender === id && m.to === me).length;
    return (
      <button key={id} onClick={() => setChannel(id)}
              style={{ display: "flex", alignItems: "center", gap: 5, padding: "4px 7px",
                       borderRadius: 2, cursor: "pointer",
                       border: `1.5px solid ${on ? BORDER_INK : PARCHMENT_DARK}`,
                       background: on ? "#fdfaf2" : "transparent" }}>
        <span style={{ width: 8, height: 8, borderRadius: 1,
                       background: colour ?? "#7a6c50", flex: "none" }} />
        <span style={{ font: "600 9.5px 'EB Garamond', serif", letterSpacing: 1,
                       textTransform: "uppercase", color: LABEL_INK }}>{label}</span>
        {unread > 0 && (
          <span style={{ font: "600 9px 'IBM Plex Mono', monospace", color: "#fdfaf2",
                         background: "#8a6414", borderRadius: 6, padding: "0 4px" }}>{unread}</span>
        )}
      </button>
    );
  };

  return (
    <section style={{ display: "flex", flexDirection: "column", minHeight: 0, flex: "1 1 auto" }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 8, padding: "0 0 8px" }}>
        <h2 style={{ margin: 0, font: "italic 600 19px 'EB Garamond', Georgia, serif", color: LABEL_INK }}>
          Press
        </h2>
        <span style={{ font: "500 9px 'IBM Plex Mono', monospace", letterSpacing: 1.2,
                       textTransform: "uppercase", color: "#7a6c50" }}>
          private to you and the recipient
        </span>

      </header>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 4, paddingBottom: 8 }}>
        {chip("GLOBAL", "All")}
        {others.map((p) => chip(p, p.slice(0, 3), FILL[p]))}
      </div>

      <div style={{ flex: "1 1 auto", minHeight: 80, overflowY: "auto", display: "flex",
                    flexDirection: "column", gap: 8, padding: "6px 2px" }}>
        {shown.length === 0 && (
          <p style={{ font: "italic 14px 'EB Garamond', serif", color: "#7a6c50", margin: 0 }}>
            {agents ? "Nothing here yet. Nobody has to write; you can start."
                    : "Nothing here yet. These opponents are scripted bots and do not answer."}
          </p>
        )}
        {shown.map((m, i) => {
          const mine = m.sender === me;
          if (m.kind === "commitment") {
            return (
              <div key={i} style={{ alignSelf: mine ? "flex-end" : "flex-start", maxWidth: "88%",
                                    borderLeft: `3px solid ${TOKEN[m.sender as Power] ?? LABEL_INK}`,
                                    padding: "3px 0 3px 9px" }}>
                <span style={{ font: "600 9px 'IBM Plex Mono', monospace", letterSpacing: 1.2,
                               textTransform: "uppercase", color: "#7a6c50" }}>
                  Commitment · {m.phase.split(" ").slice(0, 2).join(" ").toLowerCase()}
                </span>
                <p style={{ margin: "1px 0 0", font: "italic 15px 'EB Garamond', Georgia, serif",
                            lineHeight: 1.4, color: LABEL_INK }}>
                  {m.text}
                </p>
              </div>
            );
          }
          return (
            <div key={i} style={{ alignSelf: mine ? "flex-end" : "flex-start", maxWidth: "88%" }}>
              <div style={{ display: "flex", gap: 6, alignItems: "baseline",
                            justifyContent: mine ? "flex-end" : "flex-start" }}>
                <span style={{ font: "600 10px 'EB Garamond', serif", letterSpacing: 0.8,
                               textTransform: "uppercase", color: TOKEN[m.sender as Power] ?? LABEL_INK }}>
                  {mine ? "You" : m.sender.slice(0, 3)}
                </span>
                <span style={{ font: "500 8.5px 'IBM Plex Mono', monospace", color: "#8d7f62" }}>
                  {m.phase.split(" ").slice(0, 2).join(" ").toLowerCase()}
                </span>
              </div>
              <p style={{ margin: "2px 0 0", font: "15px 'EB Garamond', Georgia, serif",
                          lineHeight: 1.45, color: LABEL_INK, background: mine ? "#fdfaf2" : "#ece1c6",
                          border: `1px solid ${PARCHMENT_DARK}`, borderRadius: 3, padding: "6px 9px" }}>
                {m.text}
              </p>
            </div>
          );
        })}
      </div>

      <div style={{ display: "flex", gap: 6, paddingTop: 8 }}>
        <textarea
          id="press-draft"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder={channel === "GLOBAL" ? "Write to every power…" : `Write to ${channel.toLowerCase()}…`}
          rows={2}
          style={{ flex: 1, minWidth: 0, resize: "none", font: "15px 'EB Garamond', Georgia, serif",
                   color: LABEL_INK, background: "#fdfaf2", border: `1px solid ${PARCHMENT_DARK}`,
                   borderRadius: 2, padding: "6px 8px" }} />
        <button onClick={send} disabled={sending || !draft.trim()}
                style={{ font: "600 10px 'EB Garamond', serif", letterSpacing: 1.3,
                         textTransform: "uppercase", padding: "0 12px", borderRadius: 2,
                         border: `1.5px solid ${BORDER_INK}`, background: "#8a6414", color: "#fdfaf2",
                         cursor: draft.trim() ? "pointer" : "not-allowed",
                         opacity: draft.trim() ? 1 : 0.5 }}>
          Send
        </button>
      </div>
    </section>
  );
}
