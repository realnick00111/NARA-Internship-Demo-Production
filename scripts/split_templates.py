"""Split index.html into app shell + screen partials."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "templates" / "index.html"
SCREENS_DIR = ROOT / "templates" / "screens"
PARTIALS_DIR = ROOT / "templates" / "partials"

NAV_BY_SCREEN = {
    "agency-dashboard": "dashboard",
    "assessment-list": "assessments",
    "new-assessment": "assessments",
    "facility-identification": "assessments",
    "assessment-progress": "assessments",
    "ch-structural-entry": "assessments",
    "pqi-findings-entry": "assessments",
    "pqi3-sample": "assessments",
    "pqi6-8-hierarchy": "assessments",
    "pqi9-10-timed": "assessments",
    "validation-summary": "assessments",
    "calculation-review": "assessments",
    "result-summary": "assessments",
    "detailed-explanation": "assessments",
    "draft-management": "drafts",
    "regulation-library": "regulation-library",
    "model-administration": "scoring-models",
    "import-review": "regulation-library",
    "audit-history": "assessments",
}

STANDALONE = {"login-tenant", "export-preview"}


def extract_main_content(body: str) -> str:
    """Pull inner main content from a shelled screen body."""
    m = re.search(r"<main class=\"main\">(.*?)<div class=\"prototype-stamp\">", body, re.S)
    if not m:
        raise ValueError("Could not extract main content")
    return m.group(1).strip()


def main() -> None:
    html = INDEX.read_text(encoding="utf-8")

    head_match = re.search(r"^(.*?)</style></head><body>", html, re.S)
    tail_match = re.search(r"(<script>.*?</script></body></html>)$", html, re.S)
    viewer_match = re.search(
        r"(<div class=\"viewer-controls\".*?</div>)", html, re.S
    )

    if not head_match or not tail_match or not viewer_match:
        raise SystemExit("Failed to parse index.html structure")

    head = head_match.group(1)
    viewer = viewer_match.group(1)
    tail = tail_match.group(1)

    matches = list(re.finditer(r'<section class="screen" id="([^"]+)">', html))
    sections = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else html.find("<script>", start)
        body = html[start:end].rstrip()
        if body.endswith("</section>"):
            body = body[: -len("</section>")].rstrip()
        sections.append((m.group(1), body))

    SCREENS_DIR.mkdir(parents=True, exist_ok=True)
    PARTIALS_DIR.mkdir(parents=True, exist_ok=True)

    for screen_id, body in sections:
        out = SCREENS_DIR / f"{screen_id}.html"
        if screen_id in STANDALONE:
            content = body.strip()
        else:
            content = extract_main_content(body)
        out.write_text(content + "\n", encoding="utf-8")
        print(f"Wrote {out.name} ({len(content)} chars)")

    # Save head/style/viewer fragments for index rebuild
    (PARTIALS_DIR / "_head.html").write_text(head + "</style></head>", encoding="utf-8")
    (PARTIALS_DIR / "_viewer.html").write_text(viewer, encoding="utf-8")
    (PARTIALS_DIR / "_tail.html").write_text(tail, encoding="utf-8")

    print(f"Processed {len(sections)} screens")


if __name__ == "__main__":
    main()
