"""Find specimen collection evidence in the transcription reports."""

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import sys
from tempfile import NamedTemporaryFile
from textwrap import wrap


REPORT_NAME = re.compile(
    r"(?:.+_transcriptions_|E[0-9]+_.+_)(?P<stamp>[0-9]{8}_[0-9]{4})(?:_(?P<sequence>[0-9]+))?\.txt",
    re.IGNORECASE,
)
BANNERS = re.compile(
    r"^(?:={22}(?:CM[0-9]+(?: \(MISSING\))?|[^=\n]+?\.jpe?g)={2,}\n)+",
    re.IGNORECASE | re.MULTILINE,
)
HEADER = re.compile(r"^ID: ([^\n]+)\nSTATUS: (OK|REVIEW)(?: \(reused\))?\n")
SEPARATOR = "\n" + "=" * 50 + "\n"
FOOTER = re.compile(
    r"\n{3}(?:SAVED RESULT USAGE [^\n]*\n)?TOKENS: [^\n]*\nAVERAGE/CALL[^\n]*\nRUN: [^\n]*\n*\Z"
)
IDENTIFICATION = re.compile(
    r"\b(?:identification|identified|identifies|identif(?:y|ying)|seen|observed|present|"
    r"flushed|showed|at hand|in sight|identity|measurements?|dimensions|size of)\b", re.IGNORECASE,
)
LIST_CONTINUATION = re.compile(r"^\s+(?:is|are|was|were|had|has|have|in|on|near)\b", re.I)
UNCERTAIN = re.compile(r"[\[\]?]|\b(?:perhaps|probably|possibly|uncertain|likely|may have)\b", re.I)
S_NUMBER = r"(?<![\w-])S[ -]?[0-9]{3,}(?:[A-Z]\b|\b)"
BARE_REFERENCE = re.compile(
    rf"^(?:(?:\b(?:ink|stamp(?:ed)?|pencil|label|marginal|margin|reference)\b[^:\n]*|"
    rf"(?:annotations?\s*:\s*)?(?:ref(?:erence)?\.?|specimen)):\s*)?"
    rf"""["'\[]?({S_NUMBER})[."'\]?\s]*$""", re.I,
)
EXCLUDED_REFERENCE_FIELD = re.compile(
    r"\b(?:set (?:mark|no|number)|a\.?\s*o\.?\s*u\.?|catalog(?:ue)?|egg (?:no|number))\b", re.I,
)
REFERENCE_LOCATION = re.compile(r"\b(?:above|below|beside|next to|under)\s+(?:the\s+)?[\"“]?"
                                r"(?:nests?|birds?|skins?)\b", re.I)
SPECIMEN_REFERENCE = re.compile(
    rf"(?P<s>{S_NUMBER})|\b(?:(?:reference|ref\.?|skins?|birds?|nests?|specimen|catalogue)"
    r"\s*[:#]?\s*(?:[♂♀]\s*)?(?:no\.?|number|#)\s*[:#]?\s*)"
    r"((?:[A-Z][A-Z0-9]{0,2}[ -]?)?[0-9]+[A-Z]?(?:[-/][0-9A-Z]+)*)\b"
    r"|\b(?:skins?|birds?|nests?)\s*:\s*([0-9]{3,}[A-Z]?(?:[-/][0-9A-Z]+)*)\b"
    r"|\bskins?\s+([0-9]{3,}[A-Z]?(?:[-/][0-9A-Z]+)*)\b", re.I,
)
ACTION = r"collect(?:ed)?|tak(?:en|e)|took|sav(?:ed|e)|preserv(?:ed|e)|secur(?:ed|e)"
PAST_ACTION = r"collected|taken|took|saved|preserved|secured"
ACTIVE_ACTION = r"(?<!\bwas )(?<!\bwere )(?<!\bbeen )(?<!\bbe )(?<!\bis )(?<!\bare )"
ACTIVE_ACTION += r"(?:collected|took|saved|preserved|secured)"
SHOT = re.compile(
    r"\bshot\s*(?:the\s+)?(?:[♂♀]|\b(?:male|female)\b)|(?:[♂♀]|\b(?:male|female))\s+shot\b",
    re.I,
)
LEVEL = {"Collection wording": 0, "Quoted annotation": 1, "Specimen list": 2,
         "Specimen reference": 3, "Needs review": 4, "Identifier only": 5}
BIRD_SKIN_SHEET = "Birds and Skins"
PUBLIC_SLIP_URL = "https://ericlaslo.com/eggs/"


def specimen_patterns(specimen):
    return (
        re.compile(
            rf"\b(?:{specimen})(?:\s*[:–—-]\s*|\s+)"
            rf"(?:(?:was|were|also|itself|too|likewise)\s+){{0,4}}(?:{PAST_ACTION})\b"
            rf"|\b{ACTIVE_ACTION}\s+(?:(?:the|a|this|that|both|one|two|an|also)\s+){{0,3}}"
            rf"(?:{specimen})\b", re.I,
        ),
        re.compile(
            rf"\beggs?\b\s*(?:[0-9]+\s*)?(?:and\b|&|\+)\s*(?:the\s+)?(?:{specimen})\b"
            rf"|\b(?:{specimen})\b\s*(?:and\b|&|\+)\s*(?:the\s+)?(?:eggs?\b|[0-9]+\b(?:\s+eggs?\b)?)",
            re.I,
        ),
        re.compile(
            rf"\b(?:no|without)\s+(?:the\s+)?(?:{specimen})\b"
            rf"|\b(?:{specimen})\s+(?:(?:was|were|had|been|did|could)\s+)*"
            rf"(?:not|never|wasn't|weren't)\s+(?:been\s+)?(?:{ACTION})\b"
            rf"|\b(?:not|never|didn't)\s+(?:{ACTION})\s+(?:the\s+)?(?:{specimen})\b",
            re.I,
        ),
        re.compile(rf"\b(?:{specimen})\b", re.I),
    )


RULES = {
    "Nest": specimen_patterns(r"nests?"),
    "Bird": specimen_patterns(r"(?:adult\s+)?birds?|adult\s+(?:male|female)"),
    "Skin": specimen_patterns(r"skins?"),
}
WITH_EGGS = re.compile(
    rf"\b(?:{PAST_ACTION})\s+(?:(?:along|together)\s+)?with\s+(?:the\s+)?eggs?\b", re.I,
)
ANNOTATIONS = re.compile(r"^\s*annotations\s*:", re.I)
SOURCE_QUOTE = re.compile(r'"([^"\n]+)"|“([^”\n]+)”')
TRANSCRIPTION_NOTES = re.compile(r"^\s*transcription notes\s*:", re.I)
SIDE = re.compile(
    r"^\s*(?:[-=]+\s*)?(?:side\s+[AB]|(?:front|back)(?: of slip)?)\s*(?::\s*|[-=]*\s*)$",
    re.I,
)
CONTINUATION = re.compile(
    r"\b(?:nest|bird|skin|was|were|and)\s*$|(?:[+&])\s*$", re.I,
)


@dataclass(frozen=True)
class Candidate:
    family: str
    enums: str
    slip: str
    specimen: str
    kind: str
    reference: str
    evidence: str
    report: Path
    line: int


def read_cards(report):
    source = FOOTER.sub("\n\n\n", report.read_text(encoding="utf-8-sig"))
    banners = list(BANNERS.finditer(source))
    line = 1
    last = 0
    for index, banner in enumerate(banners):
        end = banners[index + 1].start() if index + 1 < len(banners) else len(source)
        block = source[banner.end():end]
        header = HEADER.match(block)
        head, separator, body = block.partition(SEPARATOR)
        if not (header and separator and body.endswith("\n\n\n") and body.strip()):
            continue
        if body.startswith("ERROR: "):
            continue
        line += source.count("\n", last, banner.end())
        last = banner.end()
        enums = ", ".join("E" + number for number in re.findall(r"(?m)^={22}CM([0-9]+)=", banner[0]))
        yield header[1].strip(), enums, line + (head + separator).count("\n"), body


def classify(text, in_annotations):
    """Yield specimen type, evidence type and any reference tied to the wording."""
    stripped = " ".join(ANNOTATIONS.sub("", text).split())
    if in_annotations and (quotes := SOURCE_QUOTE.findall(stripped)):
        # Collection labels in annotations can be inferred. Search the quoted wording itself.
        seen = set()
        for plain, curly in quotes:
            for specimen, kind, reference in classify(plain or curly, False):
                if kind not in ("Needs review", "Identifier only"):
                    kind = "Quoted annotation"
                hit = specimen, kind, reference
                if hit not in seen:
                    seen.add(hit)
                    yield hit
        return

    bare = BARE_REFERENCE.fullmatch(stripped)
    if bare and not EXCLUDED_REFERENCE_FIELD.search(stripped):
        yield "Possible specimen", "Identifier only", bare[1]
        return
    identification = IDENTIFICATION.search(stripped)
    uncertain = UNCERTAIN.search(stripped)
    with_eggs = WITH_EGGS.search(stripped)
    preceding_words = stripped[:with_eggs.start()] if with_eggs else ""
    mentions = {
        specimen: list(mention.finditer(stripped))
        for specimen, (_, _, _, mention) in RULES.items()
    }
    # "Nest in a willow. Collected with the eggs" attaches to the preceding specimen.
    nearest = max(
        ((match.start(), specimen) for specimen, matches in mentions.items()
         for match in matches if match.end() <= len(preceding_words)),
        default=(-1, ""),
    )[1]
    references = ""
    if (sum(bool(matches) for matches in mentions.values()) <= 1
            and not EXCLUDED_REFERENCE_FIELD.search(stripped)
            and not REFERENCE_LOCATION.search(stripped)):
        references = ", ".join(dict.fromkeys(
            next(group for group in match.groups() if group is not None)
            for match in SPECIMEN_REFERENCE.finditer(stripped)
        ))
    for specimen, (direct, joined, negative, _) in RULES.items():
        if negative.search(stripped):
            continue
        if direct.search(stripped) or (nearest == specimen and not identification):
            if in_annotations:
                continue
            kind = "Collection wording"
        elif not identification and any(
            not LIST_CONTINUATION.match(stripped[match.end():]) for match in joined.finditer(stripped)
        ):
            kind = "Specimen list"
        elif references and mentions[specimen]:
            kind = "Specimen reference"
        elif specimen == "Bird" and SHOT.search(stripped):
            if in_annotations:
                continue
            kind = "Needs review"
        else:
            continue
        yield specimen, "Needs review" if uncertain else kind, references


def read_evidence(body, first_line):
    lines = body.splitlines()
    annotations = notes = False
    joined_line = -1
    for index, raw in enumerate(lines):
        if index == joined_line:
            continue
        text = raw.strip()
        if SIDE.match(text):
            annotations = notes = False
        if ANNOTATIONS.match(text):
            annotations, notes = True, False
        if TRANSCRIPTION_NOTES.match(text):
            annotations, notes = False, True
        if notes or not text:
            continue
        matches = list(classify(text, annotations))
        if not matches and index + 1 < len(lines) and CONTINUATION.search(text):
            # Only join plausible wraps so adjacent form fields do not supply evidence.
            following = lines[index + 1].strip()
            if following and not re.match(r"^[\w ]{1,40}:", following):
                combined = text + " " + following
                matches = list(classify(combined, annotations))
                if matches:
                    text += "\n" + following
                    joined_line = index + 1
        for specimen, kind, reference in matches:
            yield specimen, kind, reference, text, first_line + index


def scan(root):
    reports = []
    for family in root.iterdir():
        if family.is_dir():
            for path in family.iterdir():
                if (name := REPORT_NAME.fullmatch(path.name)) and path.is_file():
                    reports.append((name["stamp"], int(name["sequence"] or 1), path))
    if not reports:
        raise ValueError(f"No dated transcription reports found below {root}")

    candidates = {}
    cards = set()
    for _, _, report in sorted(reports, reverse=True):
        for slip, enums, line, text in read_cards(report):
            card = report.parent.name, slip.casefold()
            cards.add(card)
            for specimen, kind, reference, evidence, location in read_evidence(text, line):
                normalized = " ".join(evidence.casefold().split()).rstrip(".")
                key = card, specimen, normalized
                candidates.setdefault(key, Candidate(
                    report.parent.name, enums, slip, specimen, kind, reference, evidence, report, location
                ))
    if not cards:
        raise ValueError(f"No complete transcription blocks found in {len(reports)} reports")
    ordered = sorted(candidates.values(), key=lambda row: (
        LEVEL[row.kind], row.family.casefold(), row.slip.casefold(), row.specimen, row.line,
    ))
    return ordered, len(cards), len(reports)


def write_workbook(destination, candidates):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise ValueError("Install the optional Excel exporter with python -m pip install openpyxl.") from exc

    book = Workbook()
    nests = book.active
    nests.title = "Nests"
    birds_and_skins = book.create_sheet(BIRD_SKIN_SHEET)
    columns = [
        ("E-number(s)", 18), ("Associated specimen", 21), ("Evidence type", 21),
        ("Evidence from transcription", 76), ("Specimen reference", 21), ("Family", 23),
        ("Slip ID", 37), ("Saved report", 43), ("Line", 8), ("Review", 21),
    ]
    for sheet in (nests, birds_and_skins):
        sheet.append([heading for heading, _ in columns])
        sheet.sheet_view.showGridLines = False
        sheet.row_dimensions[1].height = 24
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="234A52")
            cell.alignment = Alignment(vertical="center")
        for column, (_, width) in enumerate(columns, 1):
            sheet.column_dimensions[get_column_letter(column)].width = width
        sheet.freeze_panes = "B2"
    for item in candidates:
        sheet = nests if item.specimen == "Nest" else birds_and_skins
        sheet.append([item.enums, item.specimen, item.kind, item.evidence, item.reference,
                      item.family, item.slip, item.report.name, item.line])
        row = sheet[sheet.max_row]
        for cell in row[:8]:
            # A verbatim line can look like a formula. Keep every source string as text.
            cell.data_type = "s"
            cell.alignment = Alignment(vertical="top", wrap_text=True)
        if item.enums:
            first_enum = item.enums.split(", ", 1)[0]
            row[0].hyperlink = PUBLIC_SLIP_URL + first_enum
            row[0].style = "Hyperlink"
            row[0].alignment = Alignment(vertical="top", wrap_text=True)
        row[8].alignment = Alignment(vertical="top")
        height = max(
            sum(max(1, len(wrap(line, width - 5))) for line in str(cell.value).split("\n"))
            for cell, (_, width) in zip(row[:8], columns)
        )
        sheet.row_dimensions[sheet.max_row].height = min(409, 15 * height + 3)
    for sheet in (nests, birds_and_skins):
        sheet.auto_filter.ref = f"A1:J{sheet.max_row}"

    with NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        book.save(temporary)
        if os.name == "nt":
            temporary.rename(destination)
        else:
            os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("family_root", type=Path)
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args()
    destination = args.workbook.absolute()
    try:
        if destination.suffix.lower() != ".xlsx":
            raise ValueError("OutputFile must end in .xlsx")
        if destination.exists():
            raise FileExistsError(f"Workbook already exists: {destination}")
        rows, cards, reports = scan(args.family_root.absolute())
        write_workbook(destination, rows)
    except (OSError, ValueError) as exc:
        print(f"Specimen search failed: {exc}", file=sys.stderr)
        return 1

    nest_count = sum(row.specimen == "Nest" for row in rows)
    print(f"Checked {cards:,} distinct slips in {reports:,} saved reports.")
    print(f"Evidence rows: {nest_count:,} in Nests and {len(rows) - nest_count:,} in {BIRD_SKIN_SHEET}.")
    print(f"Saved {destination}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
