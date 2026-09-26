"use client";

import { Children, useRef, useState } from "react";

/** Below `sm`, show `size` children at a time with ‹ › controls instead of a long scroll; from `sm` up, all of them.
    Children stay in the DOM (wrapped in `display: contents`), so desktop layout, links and SEO are unchanged.
    `inline` puts the arrows at both ends of a flex row (the index strip); otherwise a pager row sits underneath. */
export function MobilePager({ children, size, start = 0, inline = false, className = "", noun = "items" }: {
  children: React.ReactNode; size: number; start?: number; inline?: boolean; className?: string; noun?: string;
}) {
  const items = Children.toArray(children);
  const pages = Math.ceil(items.length / size);
  const [page, setPage] = useState(Math.min(Math.floor(start / size), pages - 1));
  const top = useRef<HTMLDivElement>(null);
  const go = (d: number) => {
    setPage((p) => Math.max(0, Math.min(pages - 1, p + d)));
    top.current?.scrollIntoView({ block: "start" }); // the pager sits under the list; start the new page at its top
  };
  const body = items.map((c, i) => (
    <div key={i} className={Math.floor(i / size) === page ? "contents" : "contents max-sm:hidden"}>{c}</div>
  ));
  const arrow = "flex items-center justify-center font-mono text-ink transition-colors duration-200 hover:bg-magenta disabled:text-ink/25 disabled:hover:bg-transparent sm:hidden";

  if (inline)
    return (
      <div className={className}>
        <button type="button" aria-label={`Previous ${noun}`} disabled={page === 0} onClick={() => go(-1)} className={`${arrow} w-10 shrink-0 text-[18px]`}>‹</button>
        {body}
        <button type="button" aria-label={`Next ${noun}`} disabled={page === pages - 1} onClick={() => go(1)} className={`${arrow} w-10 shrink-0 rule-l text-[18px]`}>›</button>
      </div>
    );

  const from = page * size + 1, to = Math.min(items.length, (page + 1) * size);
  return (
    <>
      <div ref={top} className={`scroll-mt-16 ${className}`}>{body}</div>
      {pages > 1 && (
        <div className="mt-4 flex items-stretch border-[1.2px] border-ink sm:hidden" role="navigation" aria-label={`${noun} pages`}>
          <button type="button" disabled={page === 0} onClick={() => go(-1)} className={`${arrow} px-4 py-2.5 text-[13px]`}>‹ prev</button>
          <span className="flex flex-1 items-center justify-center rule-l font-mono text-[12px] text-ink">{from}–{to} of {items.length}</span>
          <button type="button" disabled={page === pages - 1} onClick={() => go(1)} className={`${arrow} rule-l px-4 py-2.5 text-[13px]`}>next ›</button>
        </div>
      )}
    </>
  );
}
