"""PDF -> raw chunks for puzzlebook35 baseline.

Deterministic: same PDF + same code -> same chunks.jsonl byte-for-byte.
No timestamps in chunk records, no randomness.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

PAGE_FROM = 12
PAGE_TO = 38
SOURCE_TAG = "whiteside_puzzlebook_2025_ru"

PART_HEADERS: dict[str, list[str]] = {
    "От издательства": ["От издательства"],
    "Приступая к работе": ["Приступая к работе"],
    "Введение": ["Приступая к работе", "Введение"],
    "Подготовка среды": ["Приступая к работе", "Подготовка среды"],
    "Нотация O большое": ["Приступая к работе", "Нотация O большое"],
    "И еще несколько предварительных замечаний": [
        "Приступая к работе",
        "И еще несколько предварительных замечаний",
    ],
    "Серьезные задачи": ["Серьезные задачи"],
}

SUBSECTION_PARENT: dict[str, str] = {
    "Отзывы и пожелания": "От издательства",
    "Список опечаток": "От издательства",
    "Нарушение авторских прав": "От издательства",
    "Установка Python": "Подготовка среды",
    "Редактор кода": "Подготовка среды",
    "Внешние библиотеки Python": "Подготовка среды",
    "Git (факультативно)": "Подготовка среды",
    "Примеры": "Нотация O большое",
}

RUNNING_HEADER_NAMES = (
    "От издательства",
    "Приступая к работе",
    "Введение",
    "Подготовка среды",
    "Нотация O большое",
    "И еще несколько предварительных замечаний",
    "Серьезные задачи",
    "Шуточные задачи",
    "Содержание",
)
RUNNING_HEADER_RE = re.compile(
    r"^\s*(?:" + "|".join(re.escape(n) for n in RUNNING_HEADER_NAMES) + r")\s+\d+\s*$"
)
RUNNING_HEADER_NUMFIRST_RE = re.compile(
    r"^\s*\d+\s+(?:" + "|".join(re.escape(n) for n in RUNNING_HEADER_NAMES) + r")\s*$"
)

TASK_RE = re.compile(r"^\s{2,}Задача\s+(\d+(?:\.\d+)?)\s*(\([^)]*\))?\s*$")
PART_HEADER_INDENT_RE = re.compile(r"^\s{2,}(\S.*\S|\S)\s*$")

MULTILINE_PART_TITLES: dict[tuple[str, ...], str] = {
    ("И еще несколько", "предварительных", "замечаний"): "И еще несколько предварительных замечаний",
}


@dataclass
class Chunk:
    chunk_id: str
    source: str
    page: int
    section_path: list[str]
    type: str
    content: str
    char_count: int
    extraction_method: str
    extraction_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source": self.source,
            "page": self.page,
            "section_path": self.section_path,
            "type": self.type,
            "content": self.content,
            "char_count": self.char_count,
            "extraction_method": self.extraction_method,
            "extraction_warnings": self.extraction_warnings,
        }


def run_pdftotext(pdf_path: Path, page: int) -> str:
    """Extract one page using pdftotext -layout. Fail loud on empty output."""
    proc = subprocess.run(
        [
            "pdftotext",
            "-layout",
            "-f", str(page),
            "-l", str(page),
            str(pdf_path),
            "-",
        ],
        capture_output=True,
        check=True,
    )
    text = proc.stdout.decode("utf-8")
    return text


def extract_pages(pdf_path: Path, page_from: int, page_to: int) -> list[tuple[int, list[str]]]:
    """Return list of (page_number, list_of_lines_after_running_header_strip)."""
    out: list[tuple[int, list[str]]] = []
    for p in range(page_from, page_to + 1):
        raw = run_pdftotext(pdf_path, p)
        if not raw.strip():
            out.append((p, []))
            continue
        lines = raw.split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
        cleaned = [
            ln for ln in lines
            if not RUNNING_HEADER_RE.match(ln) and not RUNNING_HEADER_NUMFIRST_RE.match(ln)
        ]
        out.append((p, cleaned))
    return out


def is_part_header(line: str) -> str | None:
    """Return the canonical part-header string if line is a known part header."""
    if not line.startswith(" "):
        return None
    stripped = line.strip()
    if stripped in PART_HEADERS:
        return stripped
    return None


def is_subsection_header(line: str, current_part: str | None) -> str | None:
    """Return subsection name if line is a known subsection header for current part."""
    if line.startswith(" "):
        return None
    stripped = line.strip()
    if stripped in SUBSECTION_PARENT and SUBSECTION_PARENT[stripped] == current_part:
        return stripped
    return None


def detect_multiline_part_title(lines: list[str], idx: int) -> tuple[str, int] | None:
    """If lines[idx:idx+k] form a multi-line part title, return (canonical, k)."""
    for parts, canonical in MULTILINE_PART_TITLES.items():
        if idx + len(parts) > len(lines):
            continue
        ok = True
        for i, expected in enumerate(parts):
            ln = lines[idx + i]
            if not ln.startswith(" "):
                ok = False
                break
            if ln.strip() != expected:
                ok = False
                break
        if ok:
            return canonical, len(parts)
    return None


def classify_type(content: str) -> str:
    """Classify chunk as prose|code|mixed by code-line ratio heuristic."""
    lines = [ln for ln in content.split("\n") if ln.strip()]
    if not lines:
        return "prose"
    code_markers = (
        re.compile(r"^\s*(def|class|import|from|for|if|elif|else|while|return|print|with|try|except)\b"),
        re.compile(r"^\s*[a-zA-Z_][a-zA-Z0-9_]*\s*\("),
        re.compile(r"^\s{4,}\S"),
    )
    code_count = 0
    for ln in lines:
        if any(rx.match(ln) for rx in code_markers):
            code_count += 1
    ratio = code_count / len(lines)
    if ratio >= 0.7:
        return "code"
    if ratio >= 0.25:
        return "mixed"
    return "prose"


def chunk_pages(pages: list[tuple[int, list[str]]]) -> list[Chunk]:
    """Walk page-stripped lines, emit chunks at part/subsection/task boundaries."""
    flat: list[tuple[int, str]] = []
    for page_no, lines in pages:
        for ln in lines:
            flat.append((page_no, ln))

    chunks: list[Chunk] = []
    current_section_path: list[str] = []
    current_part: str | None = None
    current_lines: list[str] = []
    current_page: int | None = None
    chunk_counter = 0
    warnings_for_current: list[str] = []

    def emit() -> None:
        nonlocal current_lines, current_page, chunk_counter, warnings_for_current
        content = "\n".join(current_lines).strip("\n")
        if content.strip() == "":
            current_lines = []
            current_page = None
            warnings_for_current = []
            return
        chunk_counter += 1
        cid = f"pb_raw_{chunk_counter:02d}"
        ch = Chunk(
            chunk_id=cid,
            source=SOURCE_TAG,
            page=current_page if current_page is not None else -1,
            section_path=list(current_section_path),
            type=classify_type(content),
            content=content,
            char_count=len(content),
            extraction_method="pdftotext-layout",
            extraction_warnings=list(warnings_for_current),
        )
        chunks.append(ch)
        current_lines = []
        current_page = None
        warnings_for_current = []

    i = 0
    while i < len(flat):
        page_no, line = flat[i]

        ml = detect_multiline_part_title([f for _, f in flat], i)
        if ml is not None:
            canonical, k = ml
            emit()
            current_part = canonical
            current_section_path = list(PART_HEADERS[canonical])
            current_page = page_no
            i += k
            continue

        ph = is_part_header(line)
        if ph is not None:
            emit()
            current_part = ph
            current_section_path = list(PART_HEADERS[ph])
            current_page = page_no
            i += 1
            continue

        sub = is_subsection_header(line, current_part)
        if sub is not None:
            emit()
            current_section_path = list(PART_HEADERS[current_part]) + [sub]
            current_page = page_no
            i += 1
            continue

        tm = TASK_RE.match(line)
        if tm is not None and current_part == "Серьезные задачи":
            emit()
            task_label = "Задача " + tm.group(1)
            if tm.group(2):
                task_label += " " + tm.group(2)
            current_section_path = list(PART_HEADERS["Серьезные задачи"]) + [task_label]
            current_page = page_no
            i += 1
            continue

        if current_page is None:
            current_page = page_no
        current_lines.append(line)
        i += 1

    emit()
    return chunks


def write_chunks_jsonl(chunks: Iterable[Chunk], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for ch in chunks:
            f.write(json.dumps(ch.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")
