#!/usr/bin/env python3
"""Split standardized novel TXT files into chapter-level Markdown files for RAG."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


CHAPTER_PATTERN = re.compile(r"^第[0-9一二三四五六七八九十百千零〇]+章(?:\s+.*)?$")
PART_PATTERN = re.compile(r"^第[0-9一二三四五六七八九十百千零〇]+部(?:\s+.*)?$")
BOOK_FILE_PATTERN = re.compile(
    r"^(?P<book_order>[^：:]+)[：:]\[(?P<year>\d{4})\]《(?P<title_cn>[^》]+)》\((?P<title_en>[^)]*)\)$"
)
INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*]+')
SPACES_PATTERN = re.compile(r"\s+")


@dataclass
class Chapter:
    heading: str
    part_heading: str
    text: str
    chapter_index: int


def _clean_heading(line: str) -> str:
    return line.replace("\ufeff", "").strip().strip("\u3000").strip()


def _normalize_text(raw_lines: List[str]) -> str:
    normalized: List[str] = []
    previous_blank = False

    for raw in raw_lines:
        line = raw.replace("\ufeff", "").replace("\r", "")
        line = line.replace("\u3000", " ").strip()
        if not line:
            if normalized and not previous_blank:
                normalized.append("")
            previous_blank = True
            continue
        normalized.append(line)
        previous_blank = False

    while normalized and not normalized[-1]:
        normalized.pop()
    return "\n".join(normalized)


def _safe_name(name: str, *, fallback: str) -> str:
    cleaned = INVALID_FILENAME_CHARS.sub("_", name)
    cleaned = SPACES_PATTERN.sub("_", cleaned).strip("._ ")
    return cleaned or fallback


def _parse_book_metadata(path: Path, book_title_line: str) -> Dict[str, str]:
    base = path.stem
    match = BOOK_FILE_PATTERN.match(base)
    if not match:
        return {
            "book_order": "",
            "book_title_cn": "",
            "book_title_en": "",
            "year": "",
            "book_display_title": book_title_line,
        }
    return {
        "book_order": match.group("book_order"),
        "book_title_cn": match.group("title_cn"),
        "book_title_en": match.group("title_en"),
        "year": match.group("year"),
        "book_display_title": book_title_line,
    }


def _split_book(path: Path) -> Dict[str, object]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    lines = raw.splitlines()

    non_empty = [_clean_heading(line) for line in lines if _clean_heading(line)]
    book_title_line = non_empty[0] if non_empty else path.stem
    metadata = _parse_book_metadata(path, book_title_line)

    preface_lines: List[str] = []
    chapters_raw: List[Dict[str, object]] = []
    current: Optional[Dict[str, object]] = None
    current_part = ""

    for raw_line in lines:
        heading = _clean_heading(raw_line)
        if not heading:
            if current is not None:
                current["raw_lines"].append(raw_line)
            else:
                preface_lines.append(raw_line)
            continue

        if PART_PATTERN.fullmatch(heading):
            current_part = heading
            continue

        if CHAPTER_PATTERN.fullmatch(heading):
            if current is not None:
                chapters_raw.append(current)
            current = {
                "heading": heading,
                "part_heading": current_part,
                "raw_lines": [],
            }
            continue

        if current is not None:
            current["raw_lines"].append(raw_line)
        else:
            preface_lines.append(raw_line)

    if current is not None:
        chapters_raw.append(current)

    chapters: List[Chapter] = []
    preface_text = _normalize_text(preface_lines)
    if preface_text:
        chapters.append(
            Chapter(
                heading="前置内容",
                part_heading="",
                text=preface_text,
                chapter_index=1,
            )
        )

    for index, item in enumerate(chapters_raw, start=len(chapters) + 1):
        text = _normalize_text(item["raw_lines"])  # type: ignore[index]
        if not text:
            continue
        chapters.append(
            Chapter(
                heading=str(item["heading"]),  # type: ignore[index]
                part_heading=str(item["part_heading"]),  # type: ignore[index]
                text=text,
                chapter_index=index,
            )
        )

    return {
        "source_file": str(path.as_posix()),
        "series_dir": path.parent.name,
        "book_file_stem": path.stem,
        "book_metadata": metadata,
        "chapters": chapters,
    }


def _render_chapter_markdown(book: Dict[str, object], chapter: Chapter) -> str:
    metadata = book["book_metadata"]  # type: ignore[index]
    source_file = book["source_file"]  # type: ignore[index]

    part_heading = chapter.part_heading
    heading_line = chapter.heading
    book_title = str(metadata.get("book_display_title", ""))  # type: ignore[union-attr]
    title_cn = str(metadata.get("book_title_cn", ""))  # type: ignore[union-attr]
    title_en = str(metadata.get("book_title_en", ""))  # type: ignore[union-attr]
    year = str(metadata.get("year", ""))  # type: ignore[union-attr]

    meta_lines = [
        "---",
        f'source_file: {json.dumps(source_file, ensure_ascii=False)}',
        f'chapter_index: {chapter.chapter_index}',
        f'chapter_heading: {json.dumps(heading_line, ensure_ascii=False)}',
        f'part_heading: {json.dumps(part_heading, ensure_ascii=False)}',
        f'book_title: {json.dumps(book_title, ensure_ascii=False)}',
        f'book_title_cn: {json.dumps(title_cn, ensure_ascii=False)}',
        f'book_title_en: {json.dumps(title_en, ensure_ascii=False)}',
        f'publish_year: {json.dumps(year, ensure_ascii=False)}',
        "---",
        "",
        f"# {book_title or 'Untitled Book'}",
    ]
    if part_heading:
        meta_lines.append(f"## {part_heading}")
    meta_lines.append(f"### {heading_line}")
    meta_lines.extend(["", chapter.text.strip(), ""])
    return "\n".join(meta_lines)


def split_novels(input_dir: Path, output_dir: Path, clean_output: bool) -> Dict[str, object]:
    if clean_output and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    all_books = sorted(input_dir.rglob("*.txt"))
    manifest_books: List[Dict[str, object]] = []

    for path in all_books:
        parsed = _split_book(path)
        chapters: List[Chapter] = parsed["chapters"]  # type: ignore[index]
        series_dir = _safe_name(str(parsed["series_dir"]), fallback="series")
        book_dir_name = _safe_name(str(parsed["book_file_stem"]), fallback="book")
        book_output_dir = output_dir / series_dir / book_dir_name
        book_output_dir.mkdir(parents=True, exist_ok=True)

        chapter_items: List[Dict[str, object]] = []
        for chapter in chapters:
            chapter_name = _safe_name(chapter.heading, fallback=f"chapter_{chapter.chapter_index:03d}")
            output_name = f"{chapter.chapter_index:03d}_{chapter_name}.md"
            output_path = book_output_dir / output_name
            output_path.write_text(_render_chapter_markdown(parsed, chapter), encoding="utf-8")

            chapter_items.append(
                {
                    "chapter_index": chapter.chapter_index,
                    "chapter_heading": chapter.heading,
                    "part_heading": chapter.part_heading,
                    "char_count": len(chapter.text),
                    "output_file": str(output_path.as_posix()),
                }
            )

        manifest_books.append(
            {
                "source_file": parsed["source_file"],
                "series_dir": parsed["series_dir"],
                "book_file_stem": parsed["book_file_stem"],
                "book_metadata": parsed["book_metadata"],
                "chapter_count": len(chapter_items),
                "chapters": chapter_items,
            }
        )

    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input_dir": str(input_dir.as_posix()),
        "output_dir": str(output_dir.as_posix()),
        "book_count": len(manifest_books),
        "books": manifest_books,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Traverse data/novel and split novels into chapter-level Markdown files."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/novel"),
        help="Source directory containing original novel TXT files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/novel_rag"),
        help="Output directory for chapter-level Markdown files and manifest.",
    )
    parser.add_argument(
        "--clean-output",
        action="store_true",
        help="Delete the output directory before writing new files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    manifest = split_novels(
        input_dir=input_dir,
        output_dir=output_dir,
        clean_output=bool(args.clean_output),
    )
    print(
        f"Split completed: {manifest['book_count']} books -> "
        f"{manifest['output_dir']} (manifest: {manifest['output_dir']}/manifest.json)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
