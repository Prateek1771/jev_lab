import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { Markdown } from "@/components/Markdown";
import { Mermaid } from "@/components/Mermaid";
import { MobilePager } from "@/components/MobilePager";
import { ProjectTabs } from "@/components/project/ProjectTabs";
import { MetaRow, Panel, Pill } from "@/components/ui";
import { getProject, getProjects } from "@/lib/api";

export async function generateMetadata({ params }: PageProps<"/p/[nn]">): Promise<Metadata> {
  const { nn } = await params;
  const project = await getProject(nn).catch(() => null);
  if (!project) return {};
  // first paragraph of the markdown, stripped to plain text, cut near 155 chars for the SERP snippet
  const plain = project.description.split(/\n\s*\n/).find((b) => !b.trim().startsWith("#")) ?? "";
  const text = plain.replace(/[`*_>#\[\]]|\(https?:[^)]*\)/g, "").replace(/\s+/g, " ").trim();
  const description = text.length > 155 ? `${text.slice(0, 152).replace(/\s\S*$/, "")}…` : text;
  return {
    title: project.title,
    description: description || `${project.name}: Jev vs an LLM vs plain code on ${project.rows} labeled rows.`,
    alternates: { canonical: `/p/${nn}` },
  };
}

export default async function ProjectPage({ params }: PageProps<"/p/[nn]">) {
  const { nn } = await params;
  const [all, project] = await Promise.all([getProjects(), getProject(nn).catch(() => null)]);
  if (!project) notFound();
  const i = all.findIndex((p) => p.id === nn);
  const prev = all[i - 1];
  const next = all[i + 1];

  return (
    <div className="fade-in">
      {/* the index strip: every experiment one click away, dashed cells like the nav */}
      {/* ponytail: 6 per page on phones, all 25 from sm up */}
      <MobilePager inline size={6} start={i} noun="experiments" className="-mx-4 flex rule-b sm:-mx-6">
        {all.map((p) => (
          <Link key={p.id} href={`/p/${p.id}`} title={p.name}
            className={`flex h-9 min-w-0 flex-1 items-center justify-center font-pixel text-[20px] transition-colors duration-200 ease-house ${p.id === nn ? "bg-ink text-pink" : "text-ink hover:bg-magenta"} ${p.id !== all[0].id ? "rule-l" : "max-sm:[border-left:var(--rule)]"}`}>
            {p.id}
          </Link>
        ))}
      </MobilePager>

      <header className="pt-10 pb-8">
        <div className="mb-6 flex items-center justify-between gap-4 font-mono text-[12px]">
          {prev ? <Link href={`/p/${prev.id}`} className="u text-ink">← {prev.id}<span className="hidden sm:inline"> {prev.name}</span></Link> : <span />}
          {next ? <Link href={`/p/${next.id}`} className="u text-ink">{next.id}<span className="hidden sm:inline"> {next.name}</span> →</Link> : <span />}
        </div>
        <div className="font-pixel text-[40px] leading-none text-ink/70">{project.id}</div>
        <h1 className="mt-2 font-display text-[clamp(44px,7vw,104px)] leading-[0.85] font-medium tracking-[-0.02em] text-ink">{project.name}</h1>
        <div className="mt-7">
          <MetaRow
            items={[
              { k: "jev primitive", v: <span className="font-mono text-[13px]">{project.primitive}</span> },
              { k: "labels", v: <span className="flex flex-wrap gap-1">{project.labels.map((l) => <Pill key={l}>{l}</Pill>)}</span> },
              { k: "dataset", v: `${project.rows} labeled rows` },
              { k: "tracing", v: project.traced ? "Langfuse" : "one call, not traced" },
            ]}
          />
        </div>
      </header>

      <section className="grid gap-8 pb-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
        <div className="text-[17px] leading-[1.4]">
          <Markdown>{project.description}</Markdown>
        </div>
        <div className="grid gap-4">
          {project.diagrams.map((d) => (
            <Panel key={d.heading} title={d.heading} right={<span className="font-mono text-[10px] tracking-[0.1em]">{d.heading === "With Jev" ? "◐ ▮▮▮ ▦" : "LLM · CODE"}</span>}>
              <Mermaid code={d.mermaid} />
            </Panel>
          ))}
        </div>
      </section>

      <ProjectTabs project={project} />
    </div>
  );
}
