"""Build results/video_review/GX010021_phase1_20261027/index_v2.html.

Reuses the embedded review JSON from the existing index.html so the v2 page
works from file:// with no server and no fetch. The old index.html is kept
untouched.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "video_review" / "GX010021_phase1_20261027"
TEMPLATE = ROOT / "tools" / "workbench_v2_template.html"
TARGET = OUT / "index_v2.html"


def main() -> None:
    old_html = (OUT / "index.html").read_text(encoding="utf-8")
    m = re.search(
        r'<script id="data" type="application/json">(.*?)</script>',
        old_html, re.S)
    if not m:
        raise SystemExit("embedded data block not found in index.html")
    data = json.loads(m.group(1))  # validate JSON before embedding
    template = TEMPLATE.read_text(encoding="utf-8")
    if "__REVIEW_DATA__" not in template:
        raise SystemExit("template placeholder missing")
    html = template.replace("__REVIEW_DATA__", json.dumps(data, ensure_ascii=False))
    TARGET.write_text(html, encoding="utf-8")
    print(f"wrote {TARGET} ({TARGET.stat().st_size} bytes, "
          f"{len(data['tasks'])} tasks / {len(data['timeline'])} timeline / "
          f"{len(data['evidence'])} evidence entries)")


if __name__ == "__main__":
    main()
