"use client";

import { useState } from "react";
import type { ProjectDetail } from "@/lib/types";
import { DatasetTab } from "./DatasetTab";
import { DownloadTab } from "./DownloadTab";
import { HistoryTab } from "./HistoryTab";
import { RunTab } from "./RunTab";

const TABS = ["Run", "Dataset", "History", "Download"] as const;

export function ProjectTabs({ project }: { project: ProjectDetail }) {
  const [tab, setTab] = useState<(typeof TABS)[number]>("Run");
  const [saved, setSaved] = useState(0);
  const count = { Run: `${Object.keys(project.examples).length} examples`, Dataset: `${project.rows} labeled`, History: "saved runs", Download: "prompts + data" };
  return (
    <section>
      <div role="tablist" className="flex border-[1.2px] border-ink">
        {TABS.map((t, i) => (
          <button key={t} role="tab" aria-selected={tab === t} type="button" onClick={() => setTab(t)}
            className={`flex flex-1 items-baseline justify-center gap-2 px-2 py-3 text-[15px] font-medium sm:text-[16px] tracking-[0.03em] transition-colors duration-[400ms] ease-house sm:flex-none sm:justify-start sm:px-5 ${i ? "rule-l" : ""} ${tab === t ? "bg-ink text-paper" : "text-ink hover:bg-paper/50"}`}>
            {t}<span className={`hidden font-mono text-[11px] font-normal sm:inline ${tab === t ? "text-page" : "text-gray"}`}>{count[t]}</span>
          </button>
        ))}
        <div className="hidden flex-1 rule-l sm:block" />
      </div>
      <div className="pt-6">
        <div hidden={tab !== "Run"}><RunTab project={project} /></div>
        <div hidden={tab !== "Dataset"}><DatasetTab project={project} onSaved={() => setSaved((n) => n + 1)} /></div>
        {tab === "History" && <HistoryTab nn={project.id} refresh={saved} />}
        {tab === "Download" && <DownloadTab nn={project.id} />}
      </div>
    </section>
  );
}
