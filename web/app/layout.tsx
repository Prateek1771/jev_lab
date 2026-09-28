import type { Metadata } from "next";
import { Inter_Tight, JetBrains_Mono, VT323 } from "next/font/google";
import Link from "next/link";
import { LiveCounter } from "@/components/LiveCounter";
import { Glyph } from "@/components/ui";
import { UiToggle } from "@/components/UiToggle";
import { AUTHOR, SITE_URL } from "@/lib/site";
import "./globals.css";

// Die Grotesk C (commercial) → Inter Tight; LisaTerminal → VT323 (DESIGN.md §4)
const interTight = Inter_Tight({ subsets: ["latin"], weight: ["400", "500", "600"], variable: "--font-inter-tight" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], weight: ["300", "400"], variable: "--font-jetbrains" });
const vt323 = VT323({ subsets: ["latin"], weight: "400", variable: "--font-vt323" });

const DESCRIPTION = "Unofficial tests by Prateek Hitli: 24 decision experiments, Jev (via OpenRouter) against LLM and no-model baselines, measured on real runs. Not affiliated with TypeSafe AI.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "Jev Lab: 24 AI decision tests, Jev vs LLMs vs code", template: "%s · Jev Lab" },
  description: DESCRIPTION,
  authors: [{ name: AUTHOR.name, url: AUTHOR.url }],
  alternates: { canonical: "/" },
  openGraph: { siteName: "Jev Lab", type: "website", locale: "en_US" },
  twitter: { card: "summary_large_image" },
};

const JSON_LD = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  name: "Jev Lab",
  url: SITE_URL,
  description: DESCRIPTION,
  author: { "@type": "Person", name: AUTHOR.name, url: AUTHOR.url },
};

function Nav() {
  const cell = "flex items-center whitespace-nowrap px-2 text-[14px] sm:px-4 sm:text-[15px] font-medium tracking-[0.03em] text-ink transition-colors duration-500 ease-house hover:bg-ink hover:text-paper";
  return (
    <nav className="sticky top-0 z-40 flex h-12 border-b-[1.2px] border-ink bg-page/85 backdrop-blur-[10px]">
      <Link href="/" aria-label="Jev Lab home" className="flex shrink-0 items-center gap-2.5 bg-ink px-2.5 text-paper sm:px-3">
        <Glyph className="h-7 w-7 text-[26px]" />
        <span className="hidden text-[15px] font-medium tracking-[0.06em] lg:inline">JEV LAB</span>
      </Link>
      {/* The links scroll sideways when they don't fit; brand, counter and toggle never shrink or get cut. */}
      <div className="no-scrollbar flex min-w-0 flex-1 overflow-x-auto">
        <Link href="/" className={`${cell} rule-l`}><span className="sm:hidden">Home</span><span className="max-sm:hidden">Overview</span></Link>
        <Link href="/jev" className={`${cell} rule-l`}>What is Jev</Link>
        <Link href="/#projects" className={`${cell} rule-l max-sm:hidden`}>Projects</Link>
        <Link href="/#method" className={`${cell} rule-l hidden lg:flex`}>Method</Link>
        <div className="flex-1 rule-l" />
      </div>
      <LiveCounter />
      <UiToggle />
      <Link href="/p/24" className="hidden shrink-0 items-center bg-ink px-4 xl:flex rule-l text-[15px] font-medium tracking-[0.03em] text-paper transition-colors duration-500 ease-house hover:bg-magenta hover:text-ink">
        Open the harness
      </Link>
    </nav>
  );
}

function Footer() {
  const items: { t: string; href?: string }[] = [
    { t: "Jev typesafe/jev-1.13 via OpenRouter" },
    { t: "Fast google/gemini-3.1-flash-lite" },
    { t: "Frontier anthropic/claude-sonnet-5" },
    { t: `Tests by ${AUTHOR.name} · ${AUTHOR.host}`, href: AUTHOR.url },
  ];
  return (
    <footer className="mt-24">
      {/* Not official: said plainly on every page */}
      <div className="rule-t mx-auto max-w-[1440px] px-4 py-5 sm:px-6">
        <p className="max-w-[900px] text-[14px] leading-[1.45] text-ink-86">
          <b className="font-medium text-ink">Unofficial.</b> Jev Lab is a set of independent tests by{" "}
          <a href={AUTHOR.url} target="_blank" rel="noreferrer" className="u text-ink">{AUTHOR.name} ({AUTHOR.host})</a>,
          not affiliated with or endorsed by TypeSafe AI or Jev. Every run used his own OpenRouter API key, with OpenRouter
          as the provider for the Jev model (<code className="font-mono text-[12.5px]">typesafe/jev-1.13</code>) and for the baseline LLMs.
        </p>
      </div>
      <div className="grid grid-cols-2 gap-px bg-page md:grid-cols-4">
        {items.map(({ t, href }) =>
          href ? (
            <a key={t} href={href} target="_blank" rel="noreferrer" className="bg-ink px-4 py-6 text-center font-mono text-[11px] tracking-[0.06em] text-paper/80 transition-colors duration-200 hover:bg-magenta hover:text-ink">{t}</a>
          ) : (
            <div key={t} className="bg-ink px-4 py-6 text-center font-mono text-[11px] tracking-[0.06em] text-paper/80">{t}</div>
          ),
        )}
      </div>
    </footer>
  );
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${interTight.variable} ${jetbrains.variable} ${vt323.variable}`}>
      <body className="min-h-screen overflow-x-clip">
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }} />
        <Nav />
        <main className="mx-auto max-w-[1440px] px-4 sm:px-6">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
