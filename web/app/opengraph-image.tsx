import { ImageResponse } from "next/og";

export const alt = "Jev Lab: 25 AI decision tests, Jev vs LLMs vs plain code";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// ponytail: one share card for every route; per-project cards if project links get shared a lot
export default function Image() {
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column", justifyContent: "space-between", background: "#abbab9", padding: 72, color: "#1e1e1e" }}>
        <div style={{ display: "flex", fontSize: 28, letterSpacing: 4 }}>UNOFFICIAL TESTS · JEV VIA OPENROUTER</div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ fontSize: 180, fontWeight: 600, lineHeight: 0.9, letterSpacing: -4 }}>Jev Lab</div>
          <div style={{ fontSize: 44, marginTop: 28, maxWidth: 980 }}>25 decisions an AI product makes, each decided by Jev, an LLM, and plain code.</div>
        </div>
        <div style={{ display: "flex", height: 16, background: "#d45bb6" }} />
      </div>
    ),
    size,
  );
}
