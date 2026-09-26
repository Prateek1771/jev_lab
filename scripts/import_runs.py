"""Copy dataset runs saved by the real-test scripts (one NN.json per project, plus an optional NN.rerun.json whose
rows replace the originals) into runs/NN/, where the web UI's History tab reads them.

Usage: uv run python scripts/import_runs.py <folder> <date YYYY-MM-DD> <label>
e.g.   uv run python scripts/import_runs.py path/to/real 2026-09-25 first-real"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(folder: Path, date: str, label: str) -> None:
    for src in sorted(folder.glob("[0-9][0-9].json")):
        nn = src.stem
        rows = {r["idx"]: r for r in json.loads(src.read_text(encoding="utf-8"))}
        rerun = folder / f"{nn}.rerun.json"
        if rerun.exists():
            rows |= {r["idx"]: r for r in json.loads(rerun.read_text(encoding="utf-8"))}
        out = ROOT / "runs" / nn / f"{date}_000000_{label}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps([rows[i] for i in sorted(rows)], indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{nn}: {len(rows)} rows -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2], sys.argv[3])
