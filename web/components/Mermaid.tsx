"use client";

import { useEffect, useId, useState } from "react";

let ready: Promise<typeof import("mermaid").default> | null = null;

/** mermaid is ~1 MB and browser-only: load it once, on first use, themed like the instrument panels. */
function load() {
  ready ??= import("mermaid").then(({ default: m }) => {
    m.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme: "base",
      fontFamily: "JetBrains Mono, ui-monospace, monospace",
      themeVariables: {
        background: "#262626",
        primaryColor: "#1e1e1e",
        primaryTextColor: "#e6e6e6",
        primaryBorderColor: "#abbab9",
        lineColor: "#8a8a8a",
        secondaryColor: "#1e1e1e",
        tertiaryColor: "#1e1e1e",
        edgeLabelBackground: "#262626",
        fontSize: "13px",
      },
      flowchart: { curve: "basis", padding: 12, htmlLabels: true, wrappingWidth: 260 },
      themeCSS: ".node rect, .node polygon, .node circle { filter: none !important; }",
    });
    return m;
  });
  return ready;
}

export function Mermaid({ code }: { code: string }) {
  const id = useId().replace(/[^a-zA-Z0-9]/g, "");
  const [svg, setSvg] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    let alive = true;
    load()
      .then((m) => m.render(`m${id}`, code))
      .then(({ svg }) => alive && setSvg(svg))
      .catch((e) => alive && setError(String(e?.message ?? e)));
    return () => {
      alive = false;
    };
  }, [code, id]);

  if (error) return <pre className="font-mono text-[12px] text-red">diagram error: {error}</pre>;
  if (!svg) return <div className="h-40 animate-pulse bg-viz-grid/40" />;
  return <div className="mermaid-box fade-in flex justify-center" dangerouslySetInnerHTML={{ __html: svg }} />;
}
