"use client";

import { useRouter } from "next/navigation";
import { CostAccuracyScatter, Legend, type ScatterPoint } from "./charts";
import { HEX } from "@/lib/format";

export function OverviewChart({ points }: { points: ScatterPoint[] }) {
  const router = useRouter();
  return (
    <>
      <Legend
        items={[
          { color: HEX.magenta, label: "Jev", shape: "diamond" },
          { color: HEX.teal, label: "LLM baseline", shape: "circle" },
          { color: HEX.orange, label: "Frontier / review", shape: "circle" },
          { color: HEX.sage, label: "No model (rules, regex, lists)", shape: "circle" },
        ]}
      />
      <CostAccuracyScatter points={points} onPick={(p) => router.push(`/p/${p.project}`)} />
    </>
  );
}
