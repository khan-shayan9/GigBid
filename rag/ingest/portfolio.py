"""Load one persona's portfolio folder into evidence items with metadata (B1).

One item per case study, CV section (or a PDF CV), repo file, review and past proposal. Every
item carries persona, type, project, skills, date, client industry and, for proposals, outcome.
`rag/ingest/chunking.py` cuts items into the chunks the index stores.
"""

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from rag.ingest.pdf import pdf_text

EvidenceType = Literal["case_study", "cv", "repo", "review", "proposal"]
Outcome = Literal["won", "replied", "ignored"]

CASE_HEADING = re.compile(r"^## (?P<id>[\w-]+) \| (?P<title>.+)$", re.MULTILINE)
CASE_YEAR = re.compile(r"·\s*(?P<year>\d{4})\s*·")
CASE_CLIENT = re.compile(r"^Client:\s*(?P<client>[^·]+)")
SECTION_HEADING = re.compile(r"^## (?P<title>.+)$", re.MULTILINE)
SKILL_SECTIONS = {"skills", "tools", "stack", "also"}
# CV skill lines carry hedges ("a bit of AWS (S3, EC2)"); these are not part of the skill name.
SKILL_HEDGE = re.compile(r"^(?:a bit of|a little|comfortable with|some|older:)\s+|\s+from .*$",
                         re.IGNORECASE)
NOT_OFFERED = "not my thing"
REPO_SUFFIXES = {".md", ".py", ".ts", ".js", ".sql"}


class EvidenceItem(BaseModel):
    id: str
    type: EvidenceType
    title: str
    source: str  # path inside the persona folder, with a #fragment for one part of a file
    date: str | None = None  # ISO date, or a year when that is all the source gives
    outcome: Outcome | None = None  # past proposals only
    text: str
    persona: str | None = None
    # Case study id for case studies and their reviews, repo folder for repo files, job id for
    # past proposals; None for CV sections.
    project: str | None = None
    skills: list[str] = Field(default=[], description="CV skills named in the text")
    client_industry: str | None = None  # from the case study's "Client:" line


def load_portfolio(persona_dir: Path) -> list[EvidenceItem]:
    persona = persona_dir.name
    cv = _cv_pdf(persona_dir, persona) if (persona_dir / "cv.pdf").exists() \
        else _cv_sections(persona_dir, persona)
    items = [*_case_studies(persona_dir), *cv, *_repo_files(persona_dir, persona),
             *_reviews(persona_dir), *_proposals(persona_dir)]
    return add_metadata(items, persona, skill_terms(cv_skills(persona_dir)[0]))


def add_metadata(items: list[EvidenceItem], persona: str,
                 terms: list[str]) -> list[EvidenceItem]:
    """Set persona and skills on every item; reviews take their case study's client industry."""
    industries = {item.id: item.client_industry for item in items if item.type == "case_study"}
    return [item.model_copy(update={
        "persona": persona, "skills": skills_in(item.text, terms),
        "client_industry": item.client_industry or industries.get(item.project or "")})
        for item in items]


def cv_skills(persona_dir: Path) -> tuple[list[str], str]:
    """Skills listed in the CV's skills-like sections, and its "Not my thing" text."""
    skills: list[str] = []
    not_offered = ""
    if not (persona_dir / "cv.md").exists():
        return skills, not_offered
    for title, body in _sections((persona_dir / "cv.md").read_text(encoding="utf-8")):
        if title.lower() in SKILL_SECTIONS:
            skills += [part.strip(" .") for part in _split_outside_parens(body) if part.strip(" .")]
        elif title.lower() == NOT_OFFERED:
            not_offered = " ".join(body.split())
    return skills, not_offered


def skill_terms(skills: list[str]) -> list[str]:
    """Skill names to look for in text: each CV skill without hedges, plus its bracketed parts."""
    terms = []
    for skill in skills:
        main, _, inner = skill.partition("(")
        terms += [SKILL_HEDGE.sub("", main).strip(),
                  *(part.strip() for part in inner.rstrip(")").split(","))]
    return list(dict.fromkeys(term for term in terms if term))


def skills_in(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms
            if re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text, re.IGNORECASE)]


def _case_studies(persona_dir: Path) -> list[EvidenceItem]:
    text = (persona_dir / "case_studies.md").read_text(encoding="utf-8")
    matches = list(CASE_HEADING.finditer(text))
    items = []
    for match, following in zip(matches, [*matches[1:], None], strict=True):
        body = text[match.end():following.start() if following else len(text)].strip()
        first_line = body.splitlines()[0] if body else ""
        year, client = CASE_YEAR.search(first_line), CASE_CLIENT.match(first_line)
        items.append(EvidenceItem(
            id=match["id"], type="case_study", title=match["title"],
            source=f"case_studies.md#{match['id']}", date=year["year"] if year else None,
            text=body, project=match["id"],
            client_industry=client["client"].strip() if client else None))
    return items


def _cv_sections(persona_dir: Path, persona: str) -> list[EvidenceItem]:
    text = (persona_dir / "cv.md").read_text(encoding="utf-8")
    # "Not my thing" lists work the freelancer refuses; as evidence it would match those jobs.
    return [EvidenceItem(id=f"{persona}-cv-{_slug(title)}", type="cv", title=f"CV: {title}",
                         source=f"cv.md#{_slug(title)}", text=body)
            for title, body in _sections(text) if body and title.lower() != NOT_OFFERED]


def _cv_pdf(persona_dir: Path, persona: str) -> list[EvidenceItem]:
    """A PDF CV as one item; the chunker splits it. Skills still come from cv.md if present."""
    return [EvidenceItem(id=f"{persona}-cv-pdf", type="cv", title="CV (PDF)", source="cv.pdf",
                         text=pdf_text(persona_dir / "cv.pdf"))]


def _repo_files(persona_dir: Path, persona: str) -> list[EvidenceItem]:
    files = sorted(path for path in (persona_dir / "repos").rglob("*")
                   if path.is_file() and path.suffix in REPO_SUFFIXES)
    return [EvidenceItem(
        id=f"{persona}-repo-{_slug(path.parent.name)}-{_slug(path.name)}", type="repo",
        title=f"{path.parent.name}/{path.name}",
        source=path.relative_to(persona_dir).as_posix(), project=path.parent.name,
        text=path.read_text(encoding="utf-8")) for path in files]


def _reviews(persona_dir: Path) -> list[EvidenceItem]:
    return [EvidenceItem(id=row["review_id"], type="review",
                         title=f"Client review of {row['project']} ({row['rating']}/5)",
                         source=f"reviews.jsonl#{row['review_id']}", text=row["text"],
                         project=row["project"])
            for row in _jsonl(persona_dir / "reviews.jsonl")]


def _proposals(persona_dir: Path) -> list[EvidenceItem]:
    return [EvidenceItem(id=row["proposal_id"], type="proposal",
                         title=f"Past proposal for {row['job_id']}",
                         source=f"past_proposals.jsonl#{row['proposal_id']}",
                         date=row["sent_at"][:10], outcome=row["outcome"],
                         text=row["cover_letter"], project=row["job_id"])
            for row in _jsonl(persona_dir / "past_proposals.jsonl")]


def _sections(markdown: str) -> list[tuple[str, str]]:
    """(title, body) for each `## ` section, plus the text before the first one as "Summary"."""
    matches = list(SECTION_HEADING.finditer(markdown))
    intro = markdown[:matches[0].start()] if matches else markdown
    sections = [("Summary", _drop_title_lines(intro))]
    for match, following in zip(matches, [*matches[1:], None], strict=True):
        body = markdown[match.end():following.start() if following else len(markdown)]
        sections.append((match["title"].strip(), body.strip()))
    return sections


def _drop_title_lines(intro: str) -> str:
    """Drop the `# Name` heading and the `source: ...` tag line from a document's opening."""
    return "\n".join(line for line in intro.splitlines()
                     if not line.startswith("# ") and not line.startswith("source:")).strip()


def _split_outside_parens(text: str) -> list[str]:
    # A full stop ends a list item only before a space ("Next.js" stays whole).
    parts, depth, current = [], 0, ""
    for char in re.sub(r"\.(\s|$)", ", ", " ".join(text.split())):
        depth += {"(": 1, ")": -1}.get(char, 0)
        if char == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += char
    return [*parts, current]


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
