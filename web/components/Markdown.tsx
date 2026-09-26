import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/** Model text and about.md. No math plugin on purpose: "$120 plus $7.50" stays dollars, not LaTeX
    (the bug the Streamlit page had until the re-test). */
export function Markdown({ children, dark }: { children: string; dark?: boolean }) {
  return (
    <div className={dark ? "prose-dark" : "prose-ink"}>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
    </div>
  );
}
