"""Egg-slip transcription, revised 2026-09-23. Python 3.10+.

Run normally for the original interactive prompt, or use --help for options.
Gemini: python -m pip install --upgrade google-genai Pillow tzdata
OpenAI (optional): python -m pip install --upgrade openai Pillow tzdata
Keys: GEMINI_API_KEY or OPENAI_API_KEY in .env beside this script.
Use --check-config for local key lookup, or --prompt-key to enter a key manually.
The CSV and source photographs are read only. No API calls occur on import.
"""

from __future__ import annotations

import argparse
import base64
import csv
import getpass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import re
import sys
import time
from contextlib import contextmanager, ExitStack
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import Any
from types import SimpleNamespace
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import egg_slip_prompt
import token_usage


# --- 1. Settings: change MODEL to select ALL of that model's settings ---
SCRIPT_VERSION = "2026-09-23.5"
CSV_PATH = r"G:\My Drive\Egg Slip Scanning\EggSlipReorganizationProject_FULL.xlsx - Full List.csv"
BASE_FAMILY_DIR = r"G:\My Drive\Egg Slip Scanning\Family"
MODEL = "gemini-3.5-flash-lite"  # Or "gemini-3.6-flash", "gemini-3.8-flash", etc.

TEST_TEMPERATURE = 1.0  # Test-mode default; independent of normal profiles. None omits it.
# OpenAI choices: gpt-5.6-luna, gpt-5.6-terra, gpt-5.6-sol, gpt-6-astra.
# Astra does not accept temperature; its tests use auto (omitted).
TEST_INPUT_DIR = Path(__file__).resolve().parent / "tests" / "inputs"
TEST_OUTPUT_DIR = Path(__file__).resolve().parent / "tests" / "outputs"


@dataclass(frozen=True)
class ModelProfile:
    provider: str              # "gemini" or "openai"; selects client and API key.
    rpm: float
    rpd: int | None            # Local daily attempt cap; None disables the cap.
    timeout: float = 180       # Seconds per request (not per entire batch).
    attempts: int = 5          # Total attempts per card, including the first.
    temperature: float | None = 1.0  # None = omit for models that do not accept it.
    max_output_tokens: int = 16384
    retry_base: float = 5      # Exponential backoff base, in seconds.
    max_retry_wait: float = 120  # Longer server delays pause the run instead.
    thinking_level: str | None = None  # Gemini: None leaves the model default.
    media_resolution: str | None = None  # Gemini: None, "low", "medium", "high".
    reasoning_effort: str | None = None  # OpenAI: None leaves the model default.
    image_detail: str = "original"      # OpenAI image setting.
    quota_timezone: str = "America/Los_Angeles"
    thinking_levels: tuple[str, ...] = ("minimal", "low", "medium", "high")
    filename_tag: str | None = None  # None uses the full model ID.
    supports_temperature: bool = True
    reasoning_efforts: tuple[str, ...] = ("none", "low", "medium", "high", "xhigh", "max")


# Gemini caps below are YOUR supplied allowances, not universal provider limits.
# Copy an entry to add another model, using its exact API model ID as the key.
# Optional generation settings belong in that entry; unrelated settings are not
# sent to the other provider. No model/provider is ever substituted on failure.
MODEL_PROFILES = {
    "gemini-3.5-flash-lite": ModelProfile("gemini", rpm=15, rpd=500, filename_tag="g3.5-f-l"),
    "gemini-3.6-flash": ModelProfile("gemini", rpm=5, rpd=20, timeout=300,
                                      attempts=3, retry_base=15, filename_tag="g3.6f"),
    "gemini-3.8-flash": ModelProfile("gemini", rpm=5, rpd=20, timeout=300,
                                      attempts=3, retry_base=15,
                                      thinking_levels=("low", "medium", "high"), filename_tag="g3.8f"),
    # OpenAI profiles: these are conservative TEST caps, not your quota.
    # Add OPENAI_API_KEY to .env and install openai before selecting an OpenAI model.
    "gpt-5.6-luna": ModelProfile("openai", rpm=5, rpd=20, timeout=300,
                                  attempts=3, retry_base=15,
                                  quota_timezone="UTC"),
    "gpt-5.6-terra": ModelProfile("openai", rpm=5, rpd=20, timeout=300,
                                   attempts=3, retry_base=15,
                                   quota_timezone="UTC"),
    "gpt-5.6-sol": ModelProfile("openai", rpm=5, rpd=20, timeout=300,
                                 attempts=3, retry_base=15,
                                 quota_timezone="UTC"),
    "gpt-6-astra": ModelProfile("openai", rpm=5, rpd=20, timeout=300,
                                 attempts=3, temperature=None, retry_base=15,
                                 quota_timezone="UTC", supports_temperature=False,
                                 reasoning_efforts=("low", "medium", "high", "xhigh", "max")),
}

# Daily counts cover all targets/restarts using this script and this state file.
# Keep this file when updating the script. No credentials or image data go in it.
REQUEST_USAGE_FILE = Path(__file__).resolve().with_name("transcribe_request_usage.json")
MAX_IMAGE_EDGE = 0            # 0 = original resolution; 2000 restores old cap.
MAX_INLINE_REQUEST_BYTES = 19_000_000  # Leave room below the 20 MB API limit.
CACHE_VERSION = 1
CACHE_MAX_AGE = timedelta(hours=48)


# --- API key lookup: independent of the directory VS Code launches from ---
API_KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
DOTENV_KEY_NAMES = (*API_KEY_NAMES, "API_KEY", "OPENAI_API_KEY")


def dotenv_api_keys(path: Path) -> dict[str, str]:
    """Read only API-key assignments; never execute or expand .env contents."""
    raw = path.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
    try:
        lines = raw.decode(encoding).splitlines()
    except UnicodeError:
        raise ValueError(f"Cannot read {path}; save it as UTF-8 text.") from None
    values = {}
    for number, line in enumerate(lines, start=1):
        match = re.fullmatch(r"[ \t]*(?:export[ \t]+)?(GEMINI_API_KEY|GOOGLE_API_KEY|API_KEY|OPENAI_API_KEY)[ \t]*=[ \t]*(.*)", line)
        if not match:
            continue
        name, value = match.groups()
        value = value.strip()
        if value.startswith(("'", '"')):
            quoted = re.fullmatch(r"(['\"])(.*?)\1[ \t]*(?:#.*)?", value)
            if not quoted:
                # A syntax error must never echo a line containing a key.
                raise ValueError(f"Invalid quoted API key in {path}, line {number}.")
            value = quoted[2].strip()
        else:
            value = re.split(r"[ \t]+#", value, maxsplit=1)[0].strip()
        values[name] = value
    # Also accept a .env containing only a pasted Google key, with no assignment.
    # Named assignments remain preferable and accept any key format.
    noncomments = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    if not values and len(noncomments) == 1:
        token = noncomments[0]
        if token[:1] in {"'", '"'} and token[-1:] == token[:1]:
            token = token[1:-1]
        if re.fullmatch(r"(?:AIza|AQ\.)[A-Za-z0-9_.=-]{16,}", token):
            values["GEMINI_API_KEY"] = token
    return values


def load_api_key(args) -> str:
    """Prefer the intended .env over stale process variables; never print a key."""
    names = (*API_KEY_NAMES, "API_KEY") if args.provider == "gemini" else ("OPENAI_API_KEY",)
    environment_names = API_KEY_NAMES if args.provider == "gemini" else ("OPENAI_API_KEY",)
    key_hint = names[0] + "=your_actual_key"
    if args.env_file:
        paths = [Path(args.env_file).expanduser().resolve()]
        if not paths[0].is_file():
            raise ValueError(f"The --env-file path is not a file: {paths[0]}")
    else:
        script_dir = Path(__file__).resolve().parent
        directories = [script_dir, script_dir.parent,
                       Path(args.csv).expanduser().resolve().parent,
                       Path(args.base_dir).expanduser().resolve().parent, Path.cwd()]
        paths = list(dict.fromkeys(directory / ".env" for directory in directories))
    for path in paths:
        if not path.is_file():
            mistaken_path = path.with_name(path.name + ".txt")
            if mistaken_path.is_file():
                raise ValueError(f"Found {mistaken_path}, but expected {path}. Rename the file to .env, not .env.txt.")
            continue
        values = dotenv_api_keys(path)
        for name in names:
            if values.get(name):
                print(f"API key loaded from {path} ({name}).")
                return values[name]
        # A file with just the other provider's valid key may coexist with this
        # provider's process variable. An explicit empty/wrong file still errors.
        other_names = set(DOTENV_KEY_NAMES) - set(names)
        if not any(name in values for name in names) and any(values.get(name) for name in other_names):
            continue
        raise ValueError(f"Found {path}, but it contains no usable API key for {args.provider}. "
                         f"Use {key_hint} on one line.")
    for name in environment_names:
        key = os.environ.get(name, "").strip()
        if key:
            print(f"API key loaded from environment variable {name}.")
            return key
    print("No API key found. Checked these paths:")
    for path in paths:
        print(f"  {path}")
    print(f"Put {key_hint} in .env beside this script. "
          "The filename must be .env, not .env.txt. Use --env-file for another location.")
    return ""


# --- 2. Egg-slip reading policy lives in egg_slip_prompt.py ---


# --- 3. CSV loading and input routing ---
def natural_key(value: str) -> tuple:
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold())
                 for part in re.split(r"(\d+)", value) if part)


def safe_component(value: str) -> str:
    if (not value or value in {".", ".."} or value.endswith((".", " "))
            or re.search(r'[<>:"/\\|?*\x00-\x1f]', value)):
        raise ValueError(f"Invalid folder component: {value!r}")
    return value


def species_name(value: str) -> str:
    parts = value.replace("_", " ").split()
    if len(parts) < 2:
        raise ValueError(f"Cannot derive a species folder from {value!r}")
    # CSV abbreviations such as "sp." route to Windows-safe folders like "sp".
    # Normalize the routing token only; retain the original scientific name in hints.
    epithet = safe_component(parts[1].lower().rstrip("."))
    return safe_component(f"{parts[0].capitalize()}_{epithet}")


@dataclass
class Database:
    by_enum: dict[str, list[dict]] = field(default_factory=dict)
    by_row: dict[int, dict] = field(default_factory=dict)
    families: dict[str, set[str]] = field(default_factory=dict)


def load_database(path: Path) -> Database:
    db = Database()
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError("The master CSV has no header.")
        reader.fieldnames = [name.strip() for name in reader.fieldnames]
        required = {"catalogNumber", "Scientific Name", "Family"}
        missing = required - set(reader.fieldnames)
        if missing:
            raise ValueError("Missing CSV column(s): " + ", ".join(sorted(missing)))
        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Duplicate CSV column headers; export the sheet again.")
        for number, raw in enumerate(reader, start=2):
            if None in raw:
                raise ValueError(f"CSV row {number} has extra columns; check quoting.")
            row = {key: (value or "").strip() for key, value in raw.items()}
            row["catalogNumber"] = row["catalogNumber"].upper()
            db.by_row[number] = row
            enum = row["catalogNumber"]
            if not enum:
                continue
            db.by_enum.setdefault(enum, []).append(row)
            if row["Scientific Name"] and row["Family"]:
                try:
                    species = species_name(row["Scientific Name"])
                    family = safe_component(row["Family"])
                except ValueError:
                    continue
                db.families.setdefault(species, set()).add(family)
    duplicates = [key for key, rows in db.by_enum.items() if len(rows) > 1]
    print(f"Loaded {len(db.by_enum):,} catalogue numbers from {len(db.by_row):,} CSV rows.")
    if duplicates:
        print(f"WARNING: {len(duplicates)} duplicate catalogue number(s); all records retained.")
    return db


def enum_species(db: Database, enum: str) -> str:
    records = db.by_enum.get(enum)
    if not records:
        raise ValueError(f"{enum} was not found in the master CSV.")
    species = {species_name(row["Scientific Name"]) for row in records}
    if len(species) != 1:
        raise ValueError(f"Conflicting species for {enum} in duplicate CSV rows.")
    return next(iter(species))


def select_targets(db: Database, target: str) -> tuple[dict, bool]:
    target = target.strip()
    console_only = target.endswith("*")
    if console_only:
        target = target[:-1].strip()
    if not target:
        raise ValueError("Enter a species, an E-number, or a CSV row range.")
    enum_match = re.fullmatch(r"E\d+", target, flags=re.I)
    if console_only and not enum_match:
        raise ValueError("The * suffix requires one E-number, for example E4268*.")
    if enum_match:
        enum = target.upper()
        return {enum_species(db, enum): {enum}}, console_only
    row_range = re.fullmatch(r"(\d+)\s*-\s*(\d+)", target)
    if row_range:
        first, last = map(int, row_range.groups())
        if first < 2 or last < first:
            raise ValueError("Use an ascending CSV row range starting at row 2 or later.")
        targets: dict[str, set[str]] = {}
        # Iterate actual CSV rows, not a potentially enormous requested range.
        for number, row in db.by_row.items():
            if first <= number <= last and row["catalogNumber"]:
                enum = row["catalogNumber"]
                if not re.fullmatch(r"E\d+", enum):
                    raise ValueError(f"CSV row {number}: expected an E-number, got {enum!r}.")
                species = enum_species(db, enum)
                targets.setdefault(species, set()).add(enum)
        if not targets:
            raise ValueError("The selected CSV rows contain no catalogue numbers.")
        print(f"Mapped {sum(map(len, targets.values())):,} distinct catalogue numbers.")
        return targets, False
    if re.search(r"[/\\]", target):
        raise ValueError("Enter a species name, not a folder path.")
    return {species_name(target): None}, False


# --- 4. Resolve folders, group numbered/uncatalogued scans, and order sides ---
def child_directory(parent: Path, name: str) -> Path | None:
    safe_component(name)
    if not parent.is_dir():
        return None
    matches = [path for path in parent.iterdir()
               if path.is_dir() and path.name.casefold() == name.casefold()]
    if len(matches) > 1:
        raise ValueError(f"More than one folder matches {name!r} in {parent}")
    return matches[0] if matches else None


def resolve_folders(root: Path, db: Database, species: str) -> tuple[Path, Path]:
    families = db.families.get(species, set())
    distinct = {name.casefold() for name in families}
    if len(distinct) != 1:
        raise ValueError(f"Missing or conflicting Family data for {species}: {sorted(families)}")
    family_dir = child_directory(root, sorted(families)[0])
    if family_dir is None:
        raise ValueError(f"Family directory not found under {root}: {sorted(families)[0]}")
    candidates = []
    # Original layout first; also support Family / Genus / Species / JPEG.
    genus_dir = child_directory(family_dir, species.split("_")[0])
    for parent in [family_dir, genus_dir]:
        if parent is None:
            continue
        species_dir = child_directory(parent, species)
        jpeg_dir = child_directory(species_dir, "JPEG") if species_dir else None
        if jpeg_dir is not None and jpeg_dir not in candidates:
            candidates.append(jpeg_dir)
    if len(candidates) != 1:
        raise ValueError(f"Expected one JPEG folder for {species}; found {len(candidates)} in {family_dir}.")
    return family_dir, candidates[0]


FILENAME_PATTERN = re.compile(
    r"^(?P<base>.+?_E\d+(?:_E\d+)*)"
    r"(?:\((?P<paren>[A-Z0-9]+)\)|[_-](?P<suffix>[A-Z]|\d+)-?)?"
    r"(?:_exchanged)?\.jpe?g$", re.I
)
UNCATALOGUED_PATTERN = re.compile(
    r"^(?P<base>.+?_Uncatalog(?:ued|ed)(?:[_ -]?\d+)?)"
    r"(?:\((?P<paren>[A-Z0-9]+)\)|[_-](?P<suffix>[A-Z]|\d+)-?)?"
    r"(?:_exchanged)?\.jpe?g$", re.I
)


def side_number(side: str) -> int:
    side = side.upper()
    if side in {"", "FRONT"}:
        return 1
    if side == "BACK":
        return 2
    if side.isdigit():
        if int(side) < 1:
            raise ValueError("Side numbering must start at 1, not 0.")
        return int(side)
    if len(side) == 1 and side.isalpha():
        return ord(side) - ord("A") + 1
    raise ValueError(f"Unrecognized side suffix {side!r}; use (A), (B), or (1), (2).")


@dataclass
class Card:
    base_id: str
    enums: tuple[str, ...]
    paths: tuple[Path, ...]
    sections: tuple[str, ...]
    warnings: list[str] = field(default_factory=list)


def discover_cards(folder: Path, allowed: set[str] | None, *,
                   include_uncatalogued: bool | None = None) -> tuple[list[Card], list[str], set[str]]:
    if include_uncatalogued is None:
        include_uncatalogued = allowed is None
    grouped: dict[str, list] = {}
    issues = []
    for path in sorted(folder.iterdir(), key=lambda p: natural_key(p.name)):
        if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg"}:
            continue
        match = FILENAME_PATTERN.fullmatch(path.name)
        uncatalogued = False
        if not match:
            match = UNCATALOGUED_PATTERN.fullmatch(path.name)
            uncatalogued = match is not None
        if not match:
            issues.append(f"Unrecognized JPEG filename: {path.name}")
            continue
        base_id = match["base"]
        enums = () if uncatalogued else tuple(re.findall(r"(?<=_)E\d+(?=_|$)", base_id.upper()))
        if uncatalogued and not include_uncatalogued:
            continue
        if enums and allowed is not None and not allowed.intersection(enums):
            continue
        side = match["paren"] or match["suffix"] or ""
        grouped.setdefault(base_id.casefold(), []).append((base_id, enums, path, side))
    cards = []
    found: set[str] = set()
    for items in grouped.values():
        base_id, enums = items[0][:2]
        try:
            ordered = sorted(items, key=lambda item: (side_number(item[3]), natural_key(item[2].name)))
            sides = [side_number(item[3]) for item in ordered]
            if len(set(sides)) != len(sides):
                raise ValueError("duplicate side labels (including an unlettered front plus A/1)")
        except ValueError as exc:
            issues.append(f"{base_id}: {exc}; rename the ambiguous files before transcribing.")
            continue
        warnings = []
        if sides[0] != 1:
            warnings.append("Front image is missing; supplied images are labelled as backs.")
        if any(b - a > 1 for a, b in zip(sides, sides[1:])):
            warnings.append("Gap in side suffixes; check whether an image is missing.")
        sections = []
        back_count = 0
        for side in sides:
            if side == 1:
                sections.append("FRONT")
            else:
                back_count += 1
                sections.append("BACK OF SLIP" + (f" {back_count}" if back_count > 1 else ""))
        cards.append(Card(base_id, enums, tuple(item[2] for item in ordered), tuple(sections), warnings))
        found.update(enums)
    cards.sort(key=lambda card: (not bool(card.enums), tuple(int(e[1:]) for e in card.enums),
                                 natural_key(card.base_id)))
    return cards, issues, (allowed - found if allowed is not None else set())


# --- 5. Image preparation and exact-input fingerprints for safe reuse ---
def prepare_image(path: Path, max_edge: int) -> bytes:
    from PIL import Image, ImageOps

    raw = path.read_bytes()
    with Image.open(io.BytesIO(raw)) as source:
        source.load()  # Force decoding now so damaged JPEGs fail before an API call.
        resize = bool(max_edge and max(source.size) > max_edge)
        orientation = source.getexif().get(274, 1)
        if source.format == "JPEG" and source.mode in {"RGB", "L"} and orientation == 1 and not resize:
            return raw  # Preserve original JPEG bytes whenever no conversion is needed.
        with ImageOps.exif_transpose(source) as oriented:
            with oriented.convert("RGB") as image:
                if resize:
                    image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=95, subsampling=0)
                return buffer.getvalue()


def generation_config(args) -> dict:
    if args.provider == "openai":
        config = {"max_output_tokens": args.max_output_tokens, "store": False,
                  "text": {"format": {"type": "text"}}}
        if args.temperature is not None:
            config["temperature"] = args.temperature
        if args.reasoning_effort:
            config["reasoning"] = {"effort": args.reasoning_effort}
        return config
    config = {"max_output_tokens": args.max_output_tokens,
              "response_mime_type": "text/plain", "automatic_function_calling": {"disable": True}}
    if args.temperature is not None:
        config["temperature"] = args.temperature
    if args.media_resolution:
        config["media_resolution"] = "MEDIA_RESOLUTION_" + args.media_resolution.upper()
    if args.thinking_level:
        config["thinking_config"] = {"thinking_level": args.thinking_level.upper()}
    return config


def prepare_card(card: Card, prompt: str, args) -> tuple[str, list]:
    config = generation_config(args)
    manifest = {"cache_version": CACHE_VERSION, "model": args.model, "config": config,
                "prompt": prompt, "max_edge": args.max_edge, "images": []}
    # Gemini was the original provider. Keep its manifest identical so changes
    # to pacing alone never invalidate existing successful transcriptions.
    if args.provider != "gemini":
        manifest.update(provider=args.provider, image_detail=args.image_detail)
    parts: list[dict] = [{"text": prompt}]
    request_size = len(prompt.encode("utf-8")) + 4096
    for path, section in zip(card.paths, card.sections):
        data = prepare_image(path, args.max_edge)
        label = f"IMAGE: {path.name}\nSECTION: {section}"
        parts.extend([{"text": label}, {"inline_data": {"mime_type": "image/jpeg", "data": data}}])
        request_size += 4 * ((len(data) + 2) // 3) + len(label.encode("utf-8")) + 256
        manifest["images"].append({"name": path.name, "section": section,
                                   "sha256": hashlib.sha256(data).hexdigest()})
    if request_size > MAX_INLINE_REQUEST_BYTES:
        raise ValueError(f"Images exceed the inline request budget ({request_size / 1e6:.1f} MB). "
                         "Try --max-edge 3000, or a smaller value; original files will not be changed.")
    key = hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    return key, [{"role": "user", "parts": parts}]


def request_metadata(prompt: str, args, key: str) -> dict:
    """Save initial request provenance, never credentials or source hint values."""
    metadata = {
        "script_version": SCRIPT_VERSION,
        "prompt_version": egg_slip_prompt.PROMPT_VERSION,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "input_sha256": key,
        "generation": generation_config(args),
        "max_edge": args.max_edge,
        "csv_hints": not args.no_csv_hints,
    }
    if args.provider == "openai":
        metadata["image_detail"] = args.image_detail
    return metadata


# --- 6. Rate limiting, retry handling, and response completeness checks ---
class RateLimiter:
    def __init__(self, rpm: float, clock=time.monotonic, sleep=time.sleep):
        self.interval = 60.0 / rpm + 0.1
        self.clock, self.sleep = clock, sleep
        self.next_start = 0.0

    def wait(self):
        if self.next_start - self.clock() >= 1:
            print(f"    Request pacing: waiting {self.next_start - self.clock():.1f}s.")
        while self.clock() < self.next_start:
            self.sleep(self.next_start - self.clock())
        self.next_start = self.clock() + self.interval


class QuotaReached(Exception):
    """A normal resumable stop, not a failed transcription or an overnight wait."""


class DailyQuota:
    """Local conservative attempt counts, shared by targets, keys and restarts.

    The provider's project usage can also include other programs. Every attempted
    request is reserved before sending, including retries and interrupted calls.
    A short OS lock plus atomic replacement prevents concurrent counter updates
    from being lost. RPM pacing remains per process; run one batch at a time.
    """
    def __init__(self, args, now=None):
        self.path = Path(args.quota_file).expanduser().resolve()
        self.key = args.provider + "/" + args.model
        self.limit = args.rpd
        self.timezone = args.quota_timezone
        self.now = now or (lambda: datetime.now(timezone.utc))

    def day(self) -> str:
        try:
            zone = ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            raise RuntimeError(f"Daily quota timezone {self.timezone!r} is unavailable. "
                               "Check quota_timezone in the profile; on Windows install timezone data with: "
                               "python -m pip install --upgrade tzdata") from None
        return self.now().astimezone(zone).date().isoformat()

    def _read(self) -> dict:
        if not self.path.exists():
            return {"version": 1, "models": {}}
        try:
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(state, dict) or state.get("version") != 1 or not isinstance(state.get("models"), dict):
                raise ValueError("Invalid counter format")
            for entry in state["models"].values():
                if (not isinstance(entry, dict) or not isinstance(entry.get("date"), str)
                        or type(entry.get("attempts")) is not int or entry["attempts"] < 0
                        or type(entry.get("exhausted")) is not bool):
                    raise ValueError("Invalid daily count")
                datetime.strptime(entry["date"], "%Y-%m-%d")
            return state
        except (ValueError, UnicodeError):
            raise RuntimeError(f"Daily usage file is damaged: {self.path}. "
                               "No request was sent; restore the counter before continuing.") from None

    def _write(self, state: dict):
        temp_path = self.path.with_name(self.path.name + ".tmp")
        try:
            with temp_path.open("w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
        finally:
            temp_path.unlink(missing_ok=True)

    def update(self, *, exhaust=False) -> int:
        with species_lock(self.path.with_name(self.path.name + ".lock")):
            day = self.day()
            state = self._read()
            entry = state["models"].get(self.key)
            if entry is None or entry["date"] != day:
                entry = {"date": day, "attempts": 0, "exhausted": False}
            if exhaust:
                entry["exhausted"] = True
            else:
                if entry["exhausted"] or (self.limit is not None and entry["attempts"] >= self.limit):
                    source = "The API reported a daily quota limit" if entry["exhausted"] else "The local daily attempt cap was reached"
                    raise QuotaReached(f"{source} for {self.key} ({entry['attempts']} local attempt(s) today). "
                                       f"Run the same target after midnight in {self.timezone} to resume. "
                                       "Normal saved cards can be reused; tests start fresh. No overnight wait or extra request was made.")
                entry["attempts"] += 1
            state["models"][self.key] = entry
            self._write(state)
            return entry["attempts"]


def enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").rsplit(".", 1)[-1].upper()


def error_code(exc: Exception) -> int | None:
    for value in (getattr(exc, "code", None), getattr(exc, "status_code", None),
                  getattr(getattr(exc, "response", None), "status_code", None)):
        try:
            return int(value)
        except (TypeError, ValueError):
            pass
    return None


def is_transient(exc: Exception) -> bool:
    code = error_code(exc)
    if code is not None:
        return code in {408, 429, 500, 502, 503, 504}
    if isinstance(exc, (ConnectionError, TimeoutError)):
        return True
    if type(exc).__name__ in {"APIConnectionError", "APITimeoutError"}:
        return True  # OpenAI wraps its httpx transport errors.
    # httpx is a google-genai dependency, but --dry-run and tests need neither.
    try:
        import httpx
        if isinstance(exc, httpx.TransportError):
            return True
    except ImportError:
        pass
    return getattr(exc, "winerror", None) in {10053, 10054, 10060}


def quota_error_kind(exc: Exception, provider: str = "gemini") -> str | None:
    if error_code(exc) != 429:
        return None
    payload = (getattr(exc, "response_json", None) or getattr(exc, "body", None)
               or getattr(exc, "details", None) or {})
    description = json.dumps(payload, default=str).lower() + " " + str(exc).lower()
    if "insufficient_quota" in description or "billing_hard_limit_reached" in description:
        return "billing"
    body = payload.get("error", payload) if isinstance(payload, dict) else {}
    if provider == "gemini" and isinstance(body, dict) and body.get("code") == "quota_exceeded":
        return "daily"
    if re.search(r"per[ _-]?day(?:\b|[ _-]|per)|requests/day|daily[ _-](?:quota|limit)", description):
        return "daily"
    return None


def retry_delay(exc: Exception) -> float:
    """Respect Retry-After and Google's structured RetryInfo when supplied."""
    values = [0.0]
    headers = getattr(getattr(exc, "response", None), "headers", {}) or {}
    after = headers.get("Retry-After") or headers.get("retry-after")
    if after:
        try:
            values.append(float(after))
        except (TypeError, ValueError):
            try:
                values.append((parsedate_to_datetime(after) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
    payload = getattr(exc, "response_json", None) or getattr(exc, "details", None)
    if isinstance(payload, dict):
        body = payload.get("error", payload)
        if isinstance(body, dict):
            for detail in body.get("details", []) or []:
                if not isinstance(detail, dict):
                    continue
                delay = detail.get("retryDelay", detail.get("retry_delay"))
                try:
                    if isinstance(delay, dict):
                        seconds = float(delay.get("seconds", 0)) + float(delay.get("nanos", 0)) / 1e9
                    else:
                        seconds = float(str(delay).removesuffix("s"))
                    values.append(seconds)
                except (TypeError, ValueError):
                    pass
    return max(value for value in values if math.isfinite(value))


class ResponseProblem(Exception):
    def __init__(self, message: str, partial: str = "", retryable: bool = False):
        super().__init__(message)
        self.partial, self.retryable = partial, retryable


SECTION_HEADING = re.compile(
    r"^[ \t]*(?:\#{1,6}[ \t]+)?(?:\*\*)?"
    r"(?:SECTION[ \t]*:[ \t]*(?:\*\*)?[ \t]*)?"
    r"(?P<label>ANNOTATIONS|BACK[ \t]+OF[ \t]+SLIP(?:[ \t]+\d+)?|"
    r"TRANSCRIPTION[ \t]+NOTES)[ \t]*(?:\*\*)?[ \t]*"
    r"(?::[ \t]*(?:\*\*)?|(?=\r?$))", re.M | re.I
)
LATEX_MARKUP = re.compile(
    r"\\(?:begin|end|[dt]?frac|text(?:rm|bf|it)?|mathrm|mathbf|mathit|"
    r"displaystyle|left|right|over|quad|qquad|hbox|mbox|cdot|times)\b"
    r"|\\[()\[\]]|\$\$|\$[^$\r\n]+\$(?![ \t]*\d)"
)


def section_headers(text: str) -> list[tuple[str, int, int]]:
    # Accept standalone headings with or without a colon and the model's
    # optional SECTION: prefix. Prose mentions within a line are not headings.
    return [(re.sub(r"[ \t]+", " ", match["label"]).upper(), match.start(), match.end())
            for match in SECTION_HEADING.finditer(text)]


def notes_have_content(notes: str) -> bool:
    """Treat explicit empty-note markers as empty, preserving the original text."""
    return notes.strip().casefold() not in {"", "-", "none", "none.", "n/a", "n/a."}


# These are format hints for familiar egg-slip labels, not a field schema. Require
# several field starts on a side before warning so narrative backs stay narrative.
FIELD_START = re.compile(
    r"^\s*(?P<label>No\.?\s+of\s+eggs(?:\s+in\s+(?:set|nest))?|"
    r"Set\s+(?:mark|no\.?)|Collected\s+by|Collector|Identity|Identification|"
    r"Incubation|Locality|Species|NAME|Ref\.?\s*No\.?|"
    r"A\.?\s*O\.?\s*U\.?(?:\s*No\.?)?|No\.?|Date|Nest|Remarks)"
    r"(?=\s|:|$)\s*(?P<colon>:)?", re.I
)
MERGED_FIELD_PAIRS = (
    (r"No\.?\s+of\s+eggs(?:\s+in\s+(?:set|nest))?", r"Set\s+mark|Collected\s+by"),
    (r"Set\s+No\.?", r"Collector|Collected\s+by"),
    (r"Identity|Identification", r"Incubation"),
    (r"Incubation", r"Identity|Identification"),
    (r"Date", r"Incubation|Nest"),
    (r"Collected\s+by", r"on"),
    (r"No\.?", r"Species"),
)


def field_format_warnings(text: str) -> list[str]:
    """Conservative, non-destructive hints; cannot validate handwriting or all forms."""
    sides: list[list[tuple[str, re.Match]]] = [[]]
    in_fields = True
    for line in text.splitlines():
        heading = SECTION_HEADING.match(line)
        if heading:
            in_fields = heading["label"].upper().startswith("BACK")
            if in_fields:
                sides.append([])
            continue
        if in_fields and (match := FIELD_START.match(line)):
            sides[-1].append((line, match))
    missing = merged = 0
    for fields in sides:
        if len(fields) < 3:
            continue
        for line, match in fields:
            missing += match["colon"] is None
            for first, second in MERGED_FIELD_PAIRS:
                if (re.fullmatch(first, match["label"], re.I)
                        and re.search(r"\s+(?:" + second + r")(?=\s|:|$)",
                                      line[match.end():], re.I)):
                    merged += 1
                    break
    warnings = []
    if missing:
        warnings.append(f"Format: {missing} field line(s) may be missing a label colon.")
    if merged:
        warnings.append(f"Format: {merged} line(s) may merge separate labelled fields.")
    return warnings


def validate_response(response, card: Card) -> tuple[str, list[str], dict]:
    candidates = getattr(response, "candidates", None) or []
    candidate = candidates[0] if candidates else None
    # Extract only answer text, never model thought parts or function calls.
    content = getattr(candidate, "content", None)
    parts = getattr(content, "parts", None) or []
    text = "".join(getattr(part, "text", "") or "" for part in parts
                   if not getattr(part, "thought", False)).strip()
    finish = enum_value(getattr(candidate, "finish_reason", None))
    block = enum_value(getattr(getattr(response, "prompt_feedback", None), "block_reason", None))
    if block and block != "BLOCK_REASON_UNSPECIFIED":
        raise ResponseProblem(f"Prompt blocked: {block}", text)
    if finish == "MAX_TOKENS":
        raise ResponseProblem("Response hit the output token limit; rerun with a higher --max-output-tokens.", text)
    if finish and finish != "STOP":
        raise ResponseProblem(f"Response did not finish normally: {finish}", text)
    if not text:
        raise ResponseProblem("The API returned no answer text.", retryable=True)
    if not finish:
        raise ResponseProblem("The API supplied no completion reason.", text, retryable=True)
    if LATEX_MARKUP.search(text):
        # Reread the images instead of guessing what a generated equation means.
        # In particular a stacked nest measurement may be a pair, not a fraction.
        raise ResponseProblem(
            "LaTeX/math markup found. Use plain text such as 5/4 or 1 1/2; "
            "keep separate measurements and multiline fields attached to their labels, "
            "with no math wrappers or backslash commands.", text, True)
    warnings = list(card.warnings)
    expected_backs = [section for section in card.sections if section != "FRONT"]
    headers = section_headers(text)
    # Some models emit an empty back template even for front-only input. Removing
    # that template is safe; never drop substantive text under an unexpected back.
    if not expected_backs:
        top_level = [header for header in headers if header[0] != "ANNOTATIONS"]
        empty_back_markers = {"", "-", "none", "n/a", "blank", "not supplied", "not provided",
                              "no back", "no back supplied", "no back provided",
                              "no back image", "no back image supplied", "no back image provided"}
        removals = []
        for index, (label, start, end) in enumerate(top_level):
            if label.startswith("BACK OF SLIP"):
                stop = top_level[index + 1][1] if index + 1 < len(top_level) else len(text)
                body = text[end:stop].strip().casefold().strip("[]. \t\r\n")
                if body in empty_back_markers:
                    removals.append((start, stop))
        if removals:
            for start, stop in reversed(removals):
                text = text[:start] + text[stop:]
            text = text.strip()
            headers = section_headers(text)
            warnings.append("Removed an empty back placeholder; no back image was supplied.")
    notes_headers = [header for header in headers if header[0] == "TRANSCRIPTION NOTES"]
    if len(notes_headers) != 1:
        raise ResponseProblem(f"Expected one final TRANSCRIPTION NOTES: section; got {len(notes_headers)}.", text, True)
    if headers[-1][0] != "TRANSCRIPTION NOTES":
        raise ResponseProblem("TRANSCRIPTION NOTES: must follow all front/back sections.", text, True)
    backs = [header for header in headers if header[0].startswith("BACK OF SLIP")]
    if [header[0] for header in backs] != expected_backs:
        raise ResponseProblem(
            f"Expected {len(expected_backs)} back section(s) for the supplied images; "
            f"got {len(backs)} (headings must match their image labels in order).", text, True)
    first_back_or_notes = backs[0][1] if backs else notes_headers[0][1]
    if ("FRONT" in card.sections and not any(
            label == "ANNOTATIONS" and start < first_back_or_notes for label, start, _ in headers)):
        raise ResponseProblem("The supplied front needs an ANNOTATIONS: section before any back or final notes.", text, True)
    # ANNOTATIONS is a subsection of a side, not a globally unique card section.
    side = "FRONT"
    annotation_counts: dict[str, int] = {}
    for label, _, _ in headers:
        if label.startswith("BACK OF SLIP"):
            side = label
        elif label == "ANNOTATIONS":
            annotation_counts[side] = annotation_counts.get(side, 0) + 1
    for side, count in annotation_counts.items():
        if count > 1:
            warnings.append(f"{side} has {count} ANNOTATIONS headings; text retained for review.")
    for index, (label, _, end) in enumerate(backs):
        stop = backs[index + 1][1] if index + 1 < len(backs) else notes_headers[0][1]
        section_text = SECTION_HEADING.sub("", text[end:stop]).strip()
        if not section_text:
            raise ResponseProblem(f"{label}: is empty; a truly blank supplied back must say [blank].", text, True)
    uncertain = [match for match in re.findall(r"\[([^\]\n]+)\]", text) if match.lower() != "blank"]
    if uncertain:
        warnings.append(f"{len(uncertain)} bracketed passage(s).")
    warnings.extend(field_format_warnings(text))
    if "```" in text:
        warnings.append("Model returned Markdown fences; inspect formatting.")
    notes = text[notes_headers[0][2]:].strip()
    if notes_have_content(notes):
        warnings.append("Transcription notes are present.")
    usage_obj = getattr(response, "usage_metadata", None)
    usage = {key: getattr(usage_obj, key, None) for key in
             ("prompt_token_count", "candidates_token_count", "thoughts_token_count", "total_token_count")}
    return text, warnings, usage


def openai_input(contents: list, detail: str) -> list:
    """Translate the same labelled images/prompt without reordering either side."""
    messages = []
    for message in contents:
        parts = []
        for part in message["parts"]:
            if "text" in part:
                parts.append({"type": "input_text", "text": part["text"]})
            else:
                inline = part["inline_data"]
                encoded = base64.b64encode(inline["data"]).decode("ascii")
                parts.append({"type": "input_image", "detail": detail,
                              "image_url": f"data:{inline['mime_type']};base64,{encoded}"})
        messages.append({"role": message["role"], "content": parts})
    return messages


def normalize_openai_response(response):
    """Give both providers identical completeness/format checks and usage fields."""
    answer_parts, refused = [], False
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", None) != "message":
            continue  # Never include reasoning summaries in the transcription.
        for part in getattr(item, "content", None) or []:
            if getattr(part, "type", None) == "output_text":
                answer_parts.append(getattr(part, "text", "") or "")
            elif getattr(part, "type", None) == "refusal":
                refused = True
    text = "\n".join(answer_parts).strip()
    if refused:
        raise ResponseProblem("OpenAI declined the request.", text)
    status = getattr(response, "status", None)
    if status != "completed":
        reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
        if reason == "max_output_tokens":
            raise ResponseProblem("Response hit the output token limit; rerun with a higher --max-output-tokens.", text)
        raise ResponseProblem(f"OpenAI response did not complete: {status or 'missing status'}"
                              + (f" ({reason})." if reason else "."), text)
    usage = getattr(response, "usage", None)
    output_tokens = getattr(usage, "output_tokens", None)
    thoughts = getattr(getattr(usage, "output_tokens_details", None), "reasoning_tokens", None)
    return SimpleNamespace(
        candidates=[SimpleNamespace(finish_reason="STOP", content=SimpleNamespace(
            parts=[SimpleNamespace(text=text, thought=False)]))],
        usage_metadata=SimpleNamespace(
            prompt_token_count=getattr(usage, "input_tokens", None),
            candidates_token_count=output_tokens - (thoughts or 0) if output_tokens is not None else None,
            thoughts_token_count=thoughts,
            total_token_count=getattr(usage, "total_tokens", None)),
        model_version=getattr(response, "model", None))


class Transcriber:
    def __init__(self, args, client=None, clock=time.monotonic, sleep=time.sleep):
        self.args, self.client = args, client
        self.sleep = sleep
        self.limiter = RateLimiter(args.rpm, clock, sleep)
        self.quota = DailyQuota(args)
        self.requests = 0
        self.call_usage = []
        self.secret = ""

    def ensure_client(self):
        if self.client is not None:
            return
        try:
            if self.args.provider == "gemini":
                from google import genai
            else:
                import openai
        except ImportError as exc:
            package = "google-genai" if self.args.provider == "gemini" else "openai"
            raise RuntimeError(f"Install dependencies: python -m pip install --upgrade {package} Pillow tzdata") from exc
        try:
            self.secret = load_api_key(self.args)
        except (OSError, ValueError) as exc:
            raise RuntimeError(f"API key setup error: {exc}") from exc
        if not self.secret and self.args.prompt_key:
            self.secret = getpass.getpass(f"{self.args.provider.capitalize()} API key (hidden; not saved): ").strip()
        if not self.secret:
            raise RuntimeError("No API key loaded. Correct the .env file shown above, "
                               "or use --prompt-key if you want to enter it manually.")
        try:
            if self.args.provider == "gemini":
                print(f"Gemini Developer API; google-genai {getattr(genai, '__version__', 'unknown version')}.")
                # Keep unrelated SDK backend/base-URL variables from changing this client.
                self.client = genai.Client(vertexai=False, api_key=self.secret, http_options={
                    "base_url": "https://generativelanguage.googleapis.com/",
                    "api_version": "v1beta",
                    "timeout": int(self.args.timeout * 1000),
                    "retry_options": {"attempts": 1},  # Script paces/counts EVERY retry.
                })
            else:
                print(f"OpenAI Responses API; openai {getattr(openai, '__version__', 'unknown version')}.")
                self.client = openai.OpenAI(api_key=self.secret, base_url="https://api.openai.com/v1",
                                            timeout=self.args.timeout, max_retries=0)
        except (TypeError, ValueError) as exc:
            raise RuntimeError(f"Cannot initialize {self.args.provider}; check the SDK installation and settings. "
                               + self.clean_error(exc)) from exc

    def clean_error(self, exc: Exception) -> str:
        text = str(exc)
        if self.secret:
            text = text.replace(self.secret, "[REDACTED]")
        return f"{type(exc).__name__}: {text}"[:2000]

    def transcribe(self, card: Card, contents: list) -> dict:
        start = len(self.call_usage)
        result = self._transcribe(card, contents)
        return {**result, "call_usage": self.call_usage[start:]}

    def request(self, contents):
        # Capture raw usage before normalization or document validation can reject it.
        response = None
        try:
            if self.args.provider == "gemini":
                response = self.client.models.generate_content(
                    model=self.args.model, contents=contents, config=generation_config(self.args))
            else:
                response = self.client.responses.create(
                    model=self.args.model, input=openai_input(contents, self.args.image_detail),
                    **generation_config(self.args))
        finally:
            usage = token_usage.read_usage(response, self.args.provider)
            call = {"usage": usage, "cost_usd": token_usage.estimate(usage, self.args.model),
                    "model": self.args.model, "provider": self.args.provider,
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                    "pricing_checked": "2026-09-23"}
            self.call_usage.append(call)
            print("    " + token_usage.tokens_line(usage) + " |  " + token_usage.cost_text([call]))
        return normalize_openai_response(response) if self.args.provider == "openai" else response

    def _transcribe(self, card: Card, contents: list) -> dict:
        self.ensure_client()
        invalid_responses = 0
        partial = ""
        request_contents = contents
        for attempt in range(1, self.args.attempts + 1):
            self.limiter.wait()
            try:
                daily_count = self.quota.update()
            except QuotaReached as exc:
                return {"status": "paused", "error": str(exc), "text": partial, "fatal": True,
                        "stop_reason": str(exc), "attempts": attempt - 1}
            except (OSError, RuntimeError) as exc:
                raise RuntimeError(f"Could not record daily usage; no API request was sent. {exc}") from exc
            self.requests += 1
            cap = str(self.args.rpd) if self.args.rpd is not None else "uncapped"
            print(f"    API request {attempt}/{self.args.attempts}; local daily use {daily_count}/{cap}; "
                  f"timeout {self.args.timeout:g}s.")
            service_failure = False
            format_retry = False
            try:
                response = self.request(request_contents)
                text, warnings, usage = validate_response(response, card)
                return {"status": "review" if warnings else "ok", "text": text,
                        "warnings": warnings, "usage": usage, "attempts": attempt,
                        "model_version": getattr(response, "model_version", None)}
            except ResponseProblem as exc:
                invalid_responses += 1
                partial = exc.partial or partial
                message = str(exc)
                retry = exc.retryable and invalid_responses < 2
                format_retry = True
                delay = 0.0
                correction = egg_slip_prompt.format_correction(card, message)
                request_contents = [*contents[:-1], {**contents[-1], "parts": [
                    *contents[-1]["parts"], {"text": correction}]}]
            except Exception as exc:
                message = self.clean_error(exc)
                code = error_code(exc)
                quota_kind = quota_error_kind(exc, self.args.provider)
                if quota_kind:
                    if quota_kind == "daily":
                        self.quota.update(exhaust=True)
                        reason = ("The API reported exhausted daily quota. Local counts cannot see requests "
                                  f"from other programs. Resume after midnight in {self.args.quota_timezone}.")
                    else:
                        reason = "The API reported exhausted billing/credit quota. Check billing before resuming."
                    return {"status": "paused", "error": message, "text": partial, "fatal": True,
                            "stop_reason": reason, "attempts": attempt}
                # Authentication/model/config errors affect the entire run.
                if code in {400, 401, 402, 403, 404}:
                    reason = "API authentication/model/configuration error affects the run."
                    if code == 401 and self.args.provider == "gemini":
                        reason = ("Google rejected the loaded credential (HTTP 401). Verify the full key "
                                  "and its Key Type in Google AI Studio. Google's September 2026 migration "
                                  "requires an Auth key; changing local .env lookup cannot repair a rejected key.")
                    elif code == 404:
                        reason = (f"{self.args.provider} returned HTTP 404 for {self.args.model}. Check the model ID "
                                  "and its availability to your project; the model was not changed automatically.")
                    return {"status": "failed", "error": message, "text": partial,
                            "fatal": True, "stop_reason": reason,
                            "attempts": attempt}
                retry = is_transient(exc)
                service_failure = retry
                hint = retry_delay(exc)
                if retry and hint > self.args.max_retry_wait:
                    reason = (f"The server requested a {hint:g}s wait, beyond the {self.args.max_retry_wait:g}s "
                              "retry-wait limit. Resume later; the wait was not shortened.")
                    return {"status": "paused", "error": message, "text": partial, "fatal": True,
                            "stop_reason": reason, "attempts": attempt}
                delay = max(hint, 60.0 if code == 429 else 0.0,
                            min(60.0, self.args.retry_base * 2 ** min(attempt - 1, 10)))
                delay += random.uniform(0, 1)
                delay = min(delay, self.args.max_retry_wait)  # Also bounds jitter.
            if not retry or attempt == self.args.attempts:
                result = {"status": "failed", "error": message, "text": partial, "attempts": attempt}
                if service_failure:
                    result.update(fatal=True, stop_reason="Repeated rate-limit/network/server errors. "
                                  "HTTP 503 means service unavailable; it does not prove a quota limit. "
                                  "Restart the same target to resume after the service or quota recovers.")
                return result
            if format_retry:
                print(f"    Format check: {message}\n"
                      f"    Retrying once with explicit formatting instructions "
                      f"(request {attempt + 1}/{self.args.attempts}; request pacing still applies).")
            else:
                print(f"    Attempt {attempt}/{self.args.attempts}: {message}\n    Retrying after {delay:.1f}s (plus request pacing).")
            self.sleep(delay)
        raise AssertionError("Unreachable retry state")

    def close(self):
        if self.client is not None:
            self.client.close()


# --- 7. Durable per-species progress journal and readable text output ---
@contextmanager
def species_lock(path: Path):
    """Serialize by path. Windows mutexes need no persistent lock file."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.ReleaseMutex.argtypes = (wintypes.HANDLE,)
        kernel32.ReleaseMutex.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        kernel32.CloseHandle.restype = wintypes.BOOL
        identity = str(path.resolve()).casefold().encode("utf-8")
        name = "Local\\egg-slip-" + hashlib.sha256(identity).hexdigest()
        handle = kernel32.CreateMutexW(None, False, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        acquired = False
        try:
            outcome = kernel32.WaitForSingleObject(handle, 0)
            if outcome not in (0, 0x80):  # WAIT_OBJECT_0 or WAIT_ABANDONED
                if outcome == 0x102:  # WAIT_TIMEOUT
                    raise RuntimeError(f"Cannot lock {path.name}; another run may be using it.")
                raise ctypes.WinError(ctypes.get_last_error())
            acquired = True
            # Remove files left by older versions, but never disrupt an open file.
            try:
                path.unlink(missing_ok=True)
            except OSError as exc:
                print(f"WARNING: Could not remove obsolete lock file {path}: {exc}")
            yield
        finally:
            try:
                if acquired:
                    kernel32.ReleaseMutex(handle)
            finally:
                kernel32.CloseHandle(handle)
        return

    # POSIX flock is attached to the inode. Deleting its path would allow a
    # second process to lock a new inode while the first still holds this one.
    with path.open("a+b") as handle:
        import fcntl
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError(f"Cannot lock {path.name}; another run may be using it.") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class Journal:
    def __init__(self, path: Path, now=None):
        self.path = path
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.entries: dict[str, dict] = {}
        self.handle = None

    def __enter__(self):
        self.handle = self.path.open("a+b")
        try:
            self.handle.seek(0)
            corrupt = 0
            last = b""
            for line in self.handle:
                last = line
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    if not isinstance(entry, dict) or not isinstance(entry.get("key"), str):
                        raise ValueError("Invalid journal entry")
                    self.entries[entry["key"]] = entry
                except (ValueError, UnicodeDecodeError):
                    corrupt += 1
            self.handle.seek(0, os.SEEK_END)
            # Preserve damaged bytes, but do not glue the next entry to a partial line.
            if last and not last.endswith(b"\n"):
                self.handle.write(b"\n")
                self.handle.flush()
            if corrupt:
                print(f"WARNING: Ignored {corrupt} damaged journal line(s); affected cards may be retried.")
            return self
        except BaseException:
            self.handle.close()
            raise

    def recent(self, entry: dict) -> bool:
        stamp = entry.get("saved_at")
        if not isinstance(stamp, str):
            return False  # Journal mtime cannot date an individual entry.
        try:
            saved = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if saved.tzinfo is None:
                return False
            age = self.now() - saved.astimezone(timezone.utc)
            return timedelta(0) <= age <= CACHE_MAX_AGE
        except (ValueError, TypeError, OverflowError):
            return False

    def reusable(self, key: str) -> dict | None:
        entry = self.entries.get(key)
        if (entry and self.recent(entry) and entry.get("cache_version") == CACHE_VERSION
                and entry.get("status") in {"ok", "review"}
                and isinstance(entry.get("text"), str) and entry["text"].strip()
                and isinstance(entry.get("warnings"), list)):
            # Older builds flagged the model's "None." as an actual note. Fix
            # that derived status locally without discarding a paid transcription.
            notes_headers = [header for header in section_headers(entry["text"])
                             if header[0] == "TRANSCRIPTION NOTES"]
            if (len(notes_headers) == 1
                    and not notes_have_content(entry["text"][notes_headers[0][2]:])
                    and "Transcription notes are present." in entry["warnings"]):
                warnings = [item for item in entry["warnings"]
                            if item != "Transcription notes are present."]
                entry = {**entry, "warnings": warnings, "status": "review" if warnings else "ok"}
            # New format hints are derived locally, without refreshing paid results.
            warnings = list(entry["warnings"])
            for warning in field_format_warnings(entry["text"]):
                if warning not in warnings:
                    warnings.append(warning)
            if warnings != entry["warnings"]:
                entry = {**entry, "warnings": warnings, "status": "review"}
            return entry
        return None

    def append(self, entry: dict):
        data = (json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        self.handle.write(data)
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.entries[entry["key"]] = entry

    def __exit__(self, *_):
        self.handle.close()


def review_line(warnings):
    reasons = ["Notes present" if item == "Transcription notes are present." else
               item.removesuffix(".").replace("bracketed uncertain reading(s)", "bracketed passage(s)")
               for item in warnings]
    return "REVIEW: " + "    |    ".join(reasons) if reasons else ""


def write_usage_footer(handle, engine, start):
    calls = getattr(engine, "call_usage", [])[start:]
    durable_write(handle, token_usage.tokens_line(token_usage.aggregate(calls)) + "\n"
                  + token_usage.averages(calls) + "\n" + token_usage.summary(calls) + "\n")


def output_block(card: Card, result: dict, cached: bool = False) -> str:
    bar = "=" * 50
    # Fixed left padding aligns CM labels (and their digits) across all records.
    # Shared slips list every CM number on its own banner line, then one body.
    # Uncatalogued pairs use their original filenames, one banner per image.
    lines = []
    labels = ["CM" + enum[1:] for enum in card.enums] or [path.name for path in card.paths]
    for label in labels:
        lines.append("=" * 22 + label + "=" * max(2, 50 - 22 - len(label)))
    lines.extend([f"ID: {card.base_id}", f"STATUS: {result['status'].upper()}" + (" (reused)" if cached else "")])
    review = review_line(result.get("warnings", []))
    if review:
        lines.append(review)
    lines.append("FILES: " + "; ".join(path.name for path in card.paths))
    if result.get("model"):
        lines.append(f"MODEL: {result['model']}")
    metadata = result.get("request_metadata")
    if metadata:
        lines.append(f"BUILD: {metadata['script_version']} | PROMPT: {metadata['prompt_version']}")
        lines.append(f"PROMPT SHA256: {metadata['prompt_sha256']}")
        lines.append(f"INPUT SHA256: {metadata['input_sha256']}")
        settings = {name: metadata[name] for name in
                    ("generation", "max_edge", "csv_hints", "image_detail") if name in metadata}
        lines.append("SETTINGS: " + json.dumps(settings, ensure_ascii=False, sort_keys=True))
        lines.append("MODEL VERSION: " + (result.get("model_version") or "unavailable"))
    calls = result.get("call_usage")
    if calls is not None:
        usage = token_usage.aggregate(calls)
    else:
        old = result.get("usage") or {}
        usage = dict(zip(token_usage.FIELDS, (old.get(key) for key in
                     ("prompt_token_count", "candidates_token_count", "thoughts_token_count", "total_token_count"))))
    cost = token_usage.cost_text(calls) if calls is not None else "unknown"
    lines.append(token_usage.tokens_line(usage) + " |  " + cost)
    lines.append(bar)
    if result.get("error"):
        lines.append("ERROR: " + result["error"])
        if result.get("text"):
            lines.append("SAVED RESPONSE (see error above):")
    lines.append(result.get("text", ""))
    return "\n".join(lines).rstrip("\r\n") + "\n\n\n"  # Two blank lines between slips.


def durable_write(handle, text: str):
    handle.write(text)
    handle.flush()
    os.fsync(handle.fileno())


def open_output_report(folder: Path, stem: str, trailing_tag: str = ""):
    """Use minutes in filenames; a short counter preserves same-minute runs."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    number = 1
    while True:
        suffix = "" if number == 1 else f"_{number}"
        path = folder / f"{stem}_{stamp}{suffix}{trailing_tag}.txt"
        try:
            return path, path.open("x", encoding="utf-8", newline="\n")
        except FileExistsError:
            number += 1


# --- 8. Main processing loop: dry run, console mode, resumable batch mode ---
def configure_test_run(args):
    """Resolve settings after the interactive target, before any API/output work."""
    if args.console_only:
        raise ValueError("tests saves a combined report; --console-only cannot be used with tests.")
    if Path(args.test_input_dir).expanduser().resolve() == Path(args.test_output_dir).expanduser().resolve():
        raise ValueError("Test input and output directories must be different.")
    if not args.temperature_explicit:
        args.temperature = TEST_TEMPERATURE if args.supports_temperature else None
        if not args.supports_temperature and TEST_TEMPERATURE is not None:
            print(f"{args.model} does not support temperature; tests use auto (omitted).")
    if args.temperature is not None and (not math.isfinite(args.temperature) or not 0 <= args.temperature <= 2):
        raise ValueError("Test temperature must be finite and between 0 and 2, or None/auto.")
    print(f"Test temperature: {temperature_tag(args)}; transcription cache disabled.")


def temperature_tag(args) -> str:
    return "auto" if args.temperature is None else str(float(args.temperature))


def run(args, engine=None) -> int:
    db = load_database(Path(args.csv))
    target = args.target if args.target is not None else input(
        "Enter target (e.g., tests, Lagopus_lagopus, E2695, E2695*, or 2-1000): ")
    test_mode = target.strip().casefold() in {"test", "tests"}
    if test_mode:
        configure_test_run(args)
        targets, star_mode = {"tests": None}, False
    else:
        targets, star_mode = select_targets(db, target)
    # Include unnumbered scans in each visited batch folder, but keep a targeted
    # E-number lookup scoped to that card (including the console-only * form).
    include_uncatalogued = re.fullmatch(r"E\d+", target.strip().removesuffix("*").strip(), re.I) is None
    console_only = star_mode or args.console_only
    engine = engine or Transcriber(args)
    totals = {"fresh": 0, "reused": 0, "review": 0, "failed": 0, "paused": 0, "discovery_issues": 0}
    selected = 0
    start = time.monotonic()
    try:
        for species, allowed in targets.items():
            try:
                if test_mode:
                    input_dir = Path(args.test_input_dir).expanduser().resolve()
                    family_dir = Path(args.test_output_dir).expanduser().resolve()
                    if not args.dry_run:
                        input_dir.mkdir(parents=True, exist_ok=True)
                else:
                    family_dir, input_dir = resolve_folders(Path(args.base_dir), db, species)
                cards, issues, missing = discover_cards(
                    input_dir, allowed, include_uncatalogued=include_uncatalogued)
                if test_mode:
                    for card in cards:
                        unmatched = [enum for enum in card.enums if enum not in db.by_enum]
                        if unmatched:
                            card.warnings.append("No CSV record for: " + ", ".join(unmatched) + ".")
            except (OSError, ValueError) as exc:
                print(f"ERROR: {species}: {exc}")
                totals["discovery_issues"] += 1
                continue
            for issue in issues:
                print("FILE CHECK: " + issue)
            if missing:
                print("MISSING: " + ", ".join(sorted(missing, key=natural_key)))
            totals["discovery_issues"] += len(issues) + len(missing)
            selected += len(cards)
            print(f"\n[{species}] {len(cards)} card group(s), {sum(len(card.paths) for card in cards)} image(s).")
            if not cards:
                print(f"No usable target cards in {input_dir}")
                totals["discovery_issues"] += 1
                continue
            if args.dry_run:
                for card in cards:
                    print(f"  {card.base_id} -> {', '.join(card.enums) or 'Uncatalogued (filename header)'}")
                    for path, section in zip(card.paths, card.sections):
                        print(f"    {section}: {path.name}")
                    for warning in card.warnings:
                        print("    REVIEW: " + warning)
                continue
            output_path = None
            # Acquire all output handles before spending any requests for this species.
            with ExitStack() as stack:
                journal = None
                output = None
                if not console_only:
                    if test_mode:
                        family_dir.mkdir(parents=True, exist_ok=True)
                        tag = safe_component(args.filename_tag or args.model)
                        output_path, handle = open_output_report(
                            family_dir, "test", f"_{tag}_t{temperature_tag(args)}")
                    else:
                        stem = f"{species}_transcriptions"
                        stack.enter_context(species_lock(family_dir / f"{stem}.lock"))
                        journal = stack.enter_context(Journal(family_dir / f"{stem}_cache.jsonl"))
                        output_path, handle = open_output_report(family_dir, stem)
                    output = stack.enter_context(handle)
                    stack.callback(write_usage_footer, output, engine, len(getattr(engine, "call_usage", [])))
                    print(f"Output: {output_path}")
                    if test_mode:
                        durable_write(output, f"TEST RUN: {SCRIPT_VERSION}\nMODEL: {args.model}\n"
                                      f"TEMPERATURE: {temperature_tag(args)}\nINPUT: {input_dir}\n"
                                      f"CARDS: {len(cards)}; IMAGES: {sum(len(card.paths) for card in cards)}\n"
                                      "CACHE: disabled; every card receives a fresh request.\n\n\n")
                    for issue in issues:
                        durable_write(output, "FILE CHECK: " + issue + "\n")
                    if missing:
                        durable_write(output, "MISSING: " + ", ".join(sorted(missing, key=natural_key)) + "\n")
                for index, card in enumerate(cards, start=1):
                    print(f"  [{index}/{len(cards)}] {card.base_id} ({len(card.paths)} side(s))")
                    key = None
                    reused = False
                    try:
                        prompt = egg_slip_prompt.build_prompt(card, db, not args.no_csv_hints)
                        key, contents = prepare_card(card, prompt, args)
                        result = journal.reusable(key) if journal and not args.force else None
                        reused = result is not None
                        if result is None:
                            result = engine.transcribe(card, contents)
                            result = {**result, "request_metadata": request_metadata(prompt, args, key)}
                    except (OSError, ValueError) as exc:
                        result = {"status": "failed", "error": f"Local error: {exc}", "text": ""}
                    result = {**result, "provider": args.provider, "model": args.model}
                    if result["status"] in {"failed", "paused"}:
                        totals[result["status"]] += 1
                    else:
                        totals["reused" if reused else "fresh"] += 1
                        if result["status"] == "review":
                            totals["review"] += 1
                    if journal and key and not reused:
                        journal.append({**result, "key": key, "cache_version": CACHE_VERSION,
                                        "base_id": card.base_id, "catalog_numbers": list(card.enums),
                                        "files": [str(path) for path in card.paths], "model": args.model,
                                        "saved_at": datetime.now(timezone.utc).isoformat()})
                    block = output_block(card, result, reused)
                    if output:
                        durable_write(output, block)
                        print("    " + result["status"].upper() + (" (reused; no API call)" if reused else ""))
                        if result.get("error"):
                            print("    " + result["error"])
                        review = review_line(result.get("warnings", []))
                        if review:
                            print("    " + review)
                    else:
                        print(block)
                    print("    " + token_usage.summary(getattr(engine, "call_usage", [])))
                    if result.get("fatal"):
                        if test_mode and output:
                            durable_write(output, "TEST STOPPED: " + result["stop_reason"] + "\n")
                        print("Stopped: " + result["stop_reason"])
                        return 1
                if test_mode and output:
                    durable_write(output, f"TEST FINISHED: {totals['fresh']} new, {totals['review']} review, "
                                  f"{totals['failed']} failed; {totals['discovery_issues']} file issues; "
                                  f"{engine.requests} API attempt(s).\n")
    except KeyboardInterrupt:
        print("\nInterrupted. Completed test output is saved; the next test starts fresh." if test_mode else
              "\nInterrupted. Completed saved cards can be reused by running the same target again.")
        return 130
    finally:
        try:
            engine.close()
        finally:
            if not args.dry_run:
                calls = getattr(engine, "call_usage", [])
                print(token_usage.tokens_line(token_usage.aggregate(calls)))
                print(token_usage.averages(calls))
                print(token_usage.summary(calls))
    if args.dry_run:
        print(f"\nDry run: {selected} card group(s); no API calls or output files.")
    else:
        print(f"\nFinished in {time.monotonic() - start:.1f}s: "
              f"{totals['fresh']} new, {totals['reused']} reused, {totals['review']} needing review, "
              f"{totals['failed']} failed; {engine.requests} API attempt(s).")
    if totals["discovery_issues"]:
        print(f"File/routing issues: {totals['discovery_issues']}; see messages above.")
    return 1 if totals["failed"] or totals["paused"] or totals["discovery_issues"] else 0


# --- 9. Command-line options; original interactive launch still works ---
def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"Egg-slip transcriber {SCRIPT_VERSION}")
    parser.add_argument("target", nargs="?", help="tests, species, E-number, E-number*, or CSV row range")
    parser.add_argument("--csv", default=CSV_PATH, help="Master CSV path")
    parser.add_argument("--base-dir", default=BASE_FAMILY_DIR, help="Root Family directory")
    parser.add_argument("--test-input-dir", default=str(TEST_INPUT_DIR), help="Flat sample JPEG folder; default: tests/inputs beside script")
    parser.add_argument("--test-output-dir", default=str(TEST_OUTPUT_DIR), help="Combined test reports; default: tests/outputs beside script")
    parser.add_argument("--env-file", help="Explicit .env path; otherwise checks script/project folders, then current directory")
    parser.add_argument("--prompt-key", action="store_true", help="Allow manual key entry if no .env or process key is found")
    parser.add_argument("--check-config", action="store_true", help="Show running version/path and check key lookup; no API requests or CSV/image reads")
    parser.add_argument("--model", default=MODEL, help="Model ID in MODEL_PROFILES; selects its provider and defaults")
    parser.add_argument("--list-models", action="store_true", help="List configured profiles; no keys, files or API calls")
    parser.add_argument("--temperature", type=lambda value: None if value.lower() == "auto" else float(value),
                        default=argparse.SUPPRESS, help="Override profile temperature; auto omits it")
    parser.add_argument("--rpm", type=float, default=argparse.SUPPRESS, help="Override profile requests per minute")
    parser.add_argument("--rpd", type=int, default=argparse.SUPPRESS, help="Override local daily attempt cap; 0 disables cap")
    parser.add_argument("--quota-file", default=str(REQUEST_USAGE_FILE), help="Persistent daily request counter path")
    parser.add_argument("--attempts", type=int, default=argparse.SUPPRESS)
    parser.add_argument("--timeout", type=float, default=argparse.SUPPRESS, help="Request timeout in seconds")
    parser.add_argument("--max-retry-wait", type=float, default=argparse.SUPPRESS,
                        help="Pause instead of sleeping longer than this many seconds for a retry")
    parser.add_argument("--max-edge", type=int, default=MAX_IMAGE_EDGE, help="Longest image edge; 0 keeps original pixels")
    parser.add_argument("--max-output-tokens", type=int, default=argparse.SUPPRESS)
    parser.add_argument("--media-resolution", choices=["auto", "low", "medium", "high"],
                        default=argparse.SUPPRESS, help="Gemini only; auto leaves it unset")
    parser.add_argument("--thinking-level", choices=["auto", "minimal", "low", "medium", "high"],
                        default=argparse.SUPPRESS, help="Gemini only; auto uses model default")
    parser.add_argument("--reasoning-effort", choices=["auto", "none", "minimal", "low", "medium", "high", "xhigh", "max"],
                        default=argparse.SUPPRESS, help="OpenAI only; supported values vary by model")
    parser.add_argument("--image-detail", choices=["auto", "low", "high", "original"],
                        default=argparse.SUPPRESS, help="OpenAI only; supported values vary by model")
    parser.add_argument("--no-csv-hints", action="store_true", help="Transcribe without CSV hints or CSV-selected collector guidance")
    parser.add_argument("--force", action="store_true", help="Request fresh transcriptions even when completed results are cached")
    parser.add_argument("--console-only", action="store_true", help="Fresh console output; no reports/cache, daily count still saved")
    parser.add_argument("--dry-run", action="store_true", help="List matched cards and image order; no API calls or files")
    args = parser.parse_args(argv)
    if args.list_models:
        return args
    args.model = args.model.strip()
    profile = MODEL_PROFILES.get(args.model)
    if profile is None:
        parser.error(f"No profile for {args.model!r}. Add its exact model ID, provider, RPM and RPD "
                     "to MODEL_PROFILES in the settings section. Use --list-models to see configured models.")
    explicit = set(vars(args))
    args.temperature_explicit = "temperature" in explicit
    for name, value in vars(profile).items():
        if not hasattr(args, name):
            setattr(args, name, value)
    for name in ("media_resolution", "thinking_level", "reasoning_effort"):
        if getattr(args, name) == "auto":
            setattr(args, name, None)
    if args.rpd == 0:
        args.rpd = None
    for label, value in (("rpm", args.rpm), ("timeout", args.timeout), ("temperature", args.temperature),
                         ("max-retry-wait", args.max_retry_wait), ("retry_base", args.retry_base)):
        if value is not None and not math.isfinite(value):
            parser.error(f"--{label} must be finite.")
    if args.rpm <= 0 or args.timeout <= 0 or args.attempts < 1 or args.max_output_tokens < 1 or args.max_edge < 0:
        parser.error("RPM, timeout, attempts and output tokens must be positive; max-edge must be >= 0.")
    if args.temperature is not None and not 0 <= args.temperature <= 2:
        parser.error("Temperature must be between 0 and 2.")
    if args.rpd is not None and (type(args.rpd) is not int or args.rpd < 1):
        parser.error("RPD must be a positive integer, or 0/None to disable the local cap.")
    if args.retry_base <= 0 or args.max_retry_wait < 60:
        parser.error("retry_base must be positive; --max-retry-wait must be at least 60 seconds.")
    if args.provider not in {"gemini", "openai"}:
        parser.error("ModelProfile.provider must be gemini or openai.")
    if args.provider == "gemini":
        if args.reasoning_effort is not None or "image_detail" in explicit:
            parser.error("--reasoning-effort and --image-detail are OpenAI settings.")
        if args.thinking_level and args.thinking_level not in args.thinking_levels:
            parser.error(f"{args.model} thinking levels: {', '.join(args.thinking_levels)} (or auto).")
    elif args.thinking_level is not None or args.media_resolution is not None:
        parser.error("--thinking-level and --media-resolution are Gemini settings.")
    if not args.supports_temperature and args.temperature is not None:
        parser.error(f"{args.model} does not support temperature; use --temperature auto.")
    if args.provider == "openai" and args.reasoning_effort and args.reasoning_effort not in args.reasoning_efforts:
        parser.error(f"{args.model} reasoning efforts: {', '.join(args.reasoning_efforts)} (or auto).")
    return args


def main(argv=None) -> int:
    # Avoid UnicodeEncodeError in older Windows consoles without changing file encoding.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    try:
        args = parse_args(argv)
        print(f"Egg-slip transcriber {SCRIPT_VERSION}\nScript: {Path(__file__).resolve()}\nPython: {sys.executable}")
        if args.list_models:
            for model, profile in MODEL_PROFILES.items():
                print(f"{model}: {profile.provider}; {profile.rpm:g} RPM; "
                      f"{profile.rpd if profile.rpd is not None else 'uncapped'} local RPD; "
                      f"timeout {profile.timeout:g}s; {profile.attempts} attempts/card")
            return 0
        print(f"Model: {args.model} ({args.provider}); {args.rpm:g} RPM; "
              f"{args.rpd if args.rpd is not None else 'uncapped'} local RPD; "
              f"timeout {args.timeout:g}s; {args.attempts} attempts/card.")
        print(f"Daily usage file: {Path(args.quota_file).expanduser().resolve()}")
        if args.check_config:
            if not load_api_key(args):
                raise RuntimeError("Local key lookup failed; no API request was sent.")
            print("Local key lookup succeeded. No API request was sent; the provider has not validated the key.")
            return 0
        return run(args)
    except KeyboardInterrupt:
        print("\nStopped.")
        return 130
    except (OSError, ValueError, RuntimeError, ImportError, EOFError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
