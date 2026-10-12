"""Durable, single-computer egg-slip campaigns. Importing this module sends nothing.

The SQLite database and artifact spool belong on a local, unsynchronized disk.
Provider execution, grouping, prompts, validation and report blocks remain owned
by transcribe.py. All commands except `run` are strictly offline.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import math
import os
from pathlib import Path
import platform
import sqlite3
import sys
from types import SimpleNamespace
import uuid

import egg_slip_prompt
import token_usage
import transcribe as t

SCHEMA = 1
SUCCESS = {"completed", "review"}
EXIT = {"complete": 0, "quota": 10, "paused": 11, "service": 12,
        "attention": 20, "unavailable": 21, "running": 0}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def code_identity():
    root = Path(__file__).resolve().parent
    return {name: digest((root / name).read_bytes()) for name in
            ("campaign.py", "transcribe.py", "egg_slip_prompt.py", "token_usage.py")}


def require_local(path):
    """Reject common synchronized/network locations; custom sync must be excluded by operator."""
    resolved = path.resolve()
    if any(part.casefold() in {"my drive", "google drive", "googledrive", "dropbox", "onedrive"}
           or part.casefold().startswith("onedrive -") for part in resolved.parts):
        raise ValueError(f"State/quota must be outside synchronized folders: {path}")
    if os.name == "nt":
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(str(resolved.anchor)) != 3:
            raise ValueError(f"State/quota requires a fixed local disk: {path}")


class Config:
    def __init__(self, path):
        self.path = Path(path).resolve()
        data = json.loads(self.path.read_text(encoding="utf-8-sig"))
        required = {"base_dir", "csv", "output_dir", "state_dir", "quota_file", "worker_host"}
        optional = {"fallback_dir", "output_policy", "env_file", "model", "rpd", "rpm",
                    "retry_days", "status_file", "log_file", "extra_species"}
        if required - data.keys() or data.keys() - required - optional:
            raise ValueError("Configuration has missing or unknown fields: " +
                             str(sorted((required - data.keys()) | (data.keys() - required - optional))))
        for name in required - {"worker_host"} | {"fallback_dir", "env_file", "status_file", "log_file"}:
            value = data.get(name)
            if value:
                path = Path(value).expanduser()
                if not path.is_absolute():
                    raise ValueError(f"{name} must be an absolute path")
                setattr(self, name, path.resolve())
            else:
                setattr(self, name, None)
        self.worker_host = data["worker_host"]
        self.output_policy = data.get("output_policy", "stop")
        if self.output_policy not in {"stop", "fallback"}:
            raise ValueError("output_policy must be stop or fallback")
        if self.output_policy == "fallback" and not self.fallback_dir:
            raise ValueError("fallback policy requires fallback_dir")
        self.retry_days = data.get("retry_days", 3)
        if type(self.retry_days) is not int or not 1 <= self.retry_days <= 30:
            raise ValueError("retry_days must be an integer from 1 to 30")
        self.extra_species = data.get("extra_species", {})
        for species, family in self.extra_species.items():
            if t.species_name(species) != species:
                raise ValueError("extra_species keys must use Genus_species names")
            t.safe_component(family)
        require_local(self.state_dir)
        require_local(self.quota_file)
        if self.fallback_dir:
            require_local(self.fallback_dir)
        if self.state_dir == self.output_dir or self.state_dir.is_relative_to(self.base_dir):
            raise ValueError("Campaign state must be separate from collection/output")
        args = ["--csv", str(self.csv), "--base-dir", str(self.base_dir),
                "--quota-file", str(self.quota_file), "--model", data.get("model", t.MODEL)]
        for key in ("rpd", "rpm", "env_file"):
            if data.get(key) is not None:
                args.extend(["--" + key.replace("_", "-"), str(data[key])])
        self.args = t.parse_args(args)
        if self.args.rpd is None:
            raise ValueError("Unattended campaigns require a finite daily cap")
        self.log_file = self.log_file or self.state_dir / "campaign.log"
        self.db_path = self.state_dir / "campaign.sqlite3"
        self.pause_path = self.state_dir / "PAUSED"


@contextmanager
def worker_lock(config):
    """OS-released SQLite write lock, shared by campaigns using this quota path.

    Unlike a PID/mtime lease it cannot expire while a slow worker is alive, and
    works across Windows logon sessions. A leftover file is harmless.
    """
    path = config.quota_file.with_name(config.quota_file.name + ".worker.sqlite3")
    conn = sqlite3.connect(path, timeout=0)
    try:
        try:
            conn.execute("BEGIN EXCLUSIVE")
        except sqlite3.OperationalError as exc:
            raise RuntimeError("Another campaign worker holds the quota execution lock") from exc
        yield
    finally:
        conn.close()


class Store:
    def __init__(self, path, create=False):
        if not create and not path.is_file():
            raise ValueError("Campaign is not initialized; run init first")
        self.conn = sqlite3.connect(path, timeout=5)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA synchronous=FULL")
        if create:
            self.conn.executescript("""
                CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE cards (id TEXT PRIMARY KEY, family TEXT, species TEXT,
                    card TEXT, fingerprint TEXT, request_key TEXT, state TEXT,
                    result TEXT, active INTEGER, failures INTEGER DEFAULT 0,
                    retry_after TEXT, refresh INTEGER DEFAULT 0);
                CREATE TABLE history (seq INTEGER PRIMARY KEY, card_id TEXT,
                    fingerprint TEXT, result TEXT, saved_at TEXT);
                CREATE TABLE attempts (seq INTEGER PRIMARY KEY, card_id TEXT,
                    day TEXT, state TEXT, usage TEXT);
                CREATE TABLE publications (id TEXT PRIMARY KEY, family TEXT,
                    species TEXT, report TEXT, journal TEXT, report_hash TEXT,
                    state TEXT, destination TEXT, fallback_destination TEXT);
            """)
            self.set("schema", SCHEMA)
            self.set("campaign_id", uuid.uuid4().hex)
        if self.get("schema") != SCHEMA:
            self.conn.close()
            raise ValueError("Unsupported campaign schema; preserve database and migrate deliberately")

    def close(self):
        self.conn.close()

    def get(self, key, default=None):
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return json.loads(row[0]) if row else default

    def set(self, key, value):
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO meta VALUES (?,?)", (key, encode(value)))

    def rows(self):
        return self.conn.execute("SELECT * FROM cards ORDER BY family,species,id").fetchall()

    def save_result(self, row, result, state, day, retry_days):
        failures = row["failures"] + int(state == "retryable")
        if state == "retryable" and failures >= retry_days:
            state = "permanent"
        retry_after = (datetime.fromisoformat(day).date() + timedelta(days=1)).isoformat()
        with self.conn:
            self.conn.execute("INSERT INTO history(card_id,fingerprint,result,saved_at) VALUES (?,?,?,?)",
                              (row["id"], row["fingerprint"], encode(result), stamp()))
            self.conn.execute("UPDATE cards SET result=?,state=?,failures=?,retry_after=?,refresh=0 WHERE id=?",
                              (encode(result), state, failures, retry_after, row["id"]))


class CampaignQuota:
    """Wrap the existing quota reservation, never implement another counter."""
    def __init__(self, quota, store, config):
        self.quota, self.store, self.config = quota, store, config
        self.card_id = None

    def update(self, *, exhaust=False):
        if not self.quota.path.is_file():
            raise RuntimeError("Quota history disappeared; refusing to reset attempt accounting")
        if exhaust:
            return self.quota.update(exhaust=True)
        if self.config.pause_path.exists():
            raise t.QuotaReached("Campaign paused by operator before next API attempt")
        # Intent precedes quota IO; a crash between the two is charged conservatively on recovery.
        with self.store.conn:
            cur = self.store.conn.execute("INSERT INTO attempts(card_id,day,state) VALUES (?,?, 'intent')",
                                          (self.card_id, self.quota.day()))
        seq = cur.lastrowid
        try:
            count = self.quota.update()
        except t.QuotaReached:
            with self.store.conn:
                self.store.conn.execute("UPDATE attempts SET state='not_sent' WHERE seq=?", (seq,))
            raise
        with self.store.conn:
            self.store.conn.execute("UPDATE attempts SET state='reserved' WHERE seq=?", (seq,))
        return count

    def recover(self):
        for attempt in self.store.conn.execute("SELECT * FROM attempts WHERE state='intent'").fetchall():
            if attempt["day"] == self.quota.day():
                try:
                    self.quota.update()  # May double-charge an ambiguous reservation; never undercharge.
                except t.QuotaReached:
                    pass
            with self.store.conn:
                self.store.conn.execute("UPDATE attempts SET state='uncertain' WHERE seq=?", (attempt["seq"],))
        for row in self.store.rows():
            if row["state"] == "in_progress":
                last = self.store.conn.execute("SELECT max(day) FROM attempts WHERE card_id=?", (row["id"],)).fetchone()[0]
                self.store.save_result(row, {"status": "paused", "text": "", "error":
                    "Interrupted request: outcome unknown; reserved attempts remain charged."},
                    "retryable", last or self.quota.day(), self.config.retry_days)


def card_data(card, base):
    return dict(base_id=card.base_id, enums=card.enums, sections=card.sections,
                paths=[str(p.relative_to(base)) for p in card.paths], warnings=card.warnings)


def restore_card(data, base):
    return t.Card(data["base_id"], tuple(data["enums"]),
                  tuple(base / p for p in data["paths"]), tuple(data["sections"]), data["warnings"])


def prepare(card, db, args, base):
    prompt = egg_slip_prompt.build_prompt(card, db, not args.no_csv_hints)
    raw = [digest(p.read_bytes()) for p in card.paths]
    key, contents = t.prepare_card(card, prompt, args)
    if raw != [digest(p.read_bytes()) for p in card.paths]:
        raise OSError("Source changed while preparing request")
    identity = dict(card=card_data(card, base), raw_sha256=raw, request_key=key,
                    catalogue=[db.by_enum.get(e, []) for e in card.enums])
    return digest(encode(identity).encode()), key, contents, prompt


def validated(entry, card, key):
    if (entry.get("key") != key or entry.get("cache_version") != t.CACHE_VERSION
            or entry.get("status") not in {"ok", "review"}
            or not isinstance(entry.get("warnings"), list)
            or not all(isinstance(w, str) for w in entry.get("warnings", []))
            or not isinstance(entry.get("text"), str) or not entry["text"].strip()):
        return None
    response = SimpleNamespace(candidates=[SimpleNamespace(finish_reason="STOP",
        content=SimpleNamespace(parts=[SimpleNamespace(text=entry["text"], thought=False)]))],
        prompt_feedback=None, usage_metadata=None)
    try:
        text, warnings, _ = t.validate_response(response, card)
    except t.ResponseProblem:
        return None
    # Never discard substantive source/failed text or original non-derived warnings.
    if text != entry["text"]:
        return None
    warnings = list(dict.fromkeys([*entry["warnings"], *warnings]))
    return {**entry, "warnings": warnings, "status": "review" if warnings else "ok"}


def old_checkpoint(path, card, key):
    """Read only: no Journal context (which would append/repair historical bytes)."""
    if not path.exists():
        return None
    latest = None
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            try:
                entry = json.loads(line)
                if isinstance(entry, dict) and entry.get("key") == key:
                    latest = entry
            except (ValueError, UnicodeError):
                continue
    if latest:
        return validated(latest, card, key)
    return None


def checkpoint_for(config, item):
    card = restore_card(item["card"], config.base_dir)
    for root in dict.fromkeys([config.output_dir, config.base_dir]):
        try:
            entry = old_checkpoint(root / item["family"] /
                f"{item['species']}_transcriptions_cache.jsonl", card, item["request_key"])
        except OSError:
            if root == config.output_dir and config.output_policy == "fallback":
                continue
            raise
        if entry:
            return {**entry, "campaign_result_id": entry.get("campaign_result_id") or
                    "import-" + digest(encode(entry).encode("utf-8"))}
    return None


def inventory(config):
    if not config.base_dir.is_dir() or not config.csv.is_file():
        raise OSError("Collection root or catalogue is unavailable; no work is inferred missing")
    db = t.load_database(config.csv)
    targets, _ = t.select_targets(db, f"2-{max(db.by_row, default=2)}")
    catalogue_species = set(targets)
    # Include species folders containing only uncatalogued material. Traverse only
    # the two established layouts, then let the existing resolver check ambiguity.
    for family in config.base_dir.iterdir():
        if not family.is_dir():
            continue
        for candidate in [*family.glob("*/JPEG"), *family.glob("*/*/JPEG")]:
            species = candidate.parent.name
            try:
                species = t.species_name(species)
                t.safe_component(family.name)
            except ValueError:
                continue
            if species not in catalogue_species:
                db.families.setdefault(species, set()).add(family.name)
                targets[species] = set()
    for species, family in config.extra_species.items():
        if species in db.families and db.families[species] != {family}:
            raise ValueError(f"extra_species conflicts with CSV: {species}")
        db.families.setdefault(species, {family})
        targets.setdefault(species, set())
    items, missing, issues = [], [], []
    for species in sorted(targets, key=t.natural_key):
        try:
            family, folder = t.resolve_folders(config.base_dir, db, species)
            # Species scope includes numbered scans absent from CSV and explicit uncatalogued cards.
            cards, problems, _ = t.discover_cards(folder, None, include_uncatalogued=True)
            issues.extend(f"{species}: {p}" for p in problems)
            for enum in sorted(t.missing_catalogue_numbers(folder, db, species, None), key=t.natural_key):
                missing.append(dict(family=family.name, species=species, enum=enum,
                                    rows=len(db.by_enum[enum]), block=t.missing_output_block(enum, db.by_enum[enum])))
            for card in cards:
                fingerprint, key, _, _ = prepare(card, db, config.args, config.base_dir)
                identifier = "/".join((family.name, species, card.base_id)).casefold()
                items.append(dict(id=identifier, family=family.name, species=species,
                                  card=card_data(card, config.base_dir), fingerprint=fingerprint, request_key=key))
        except (OSError, ValueError) as exc:
            issues.append(f"{species}: {exc}")
    return db, items, missing, issues


def scan(config, store, found=None):
    db, items, missing, issues = found or inventory(config)
    # A disconnected/malformed tree must not deactivate formerly known cards.
    store.set("discovery_issues", issues)
    if issues:
        raise ValueError("Discovery requires attention: " + " | ".join(issues[:20]))
    with store.conn:
        prior = {row["id"]: row for row in store.rows()}
        current_ids = {item["id"] for item in items}
        disappeared_species = {(r["family"], r["species"]) for identifier, r in prior.items()
                               if identifier not in current_ids}
        store.conn.execute("UPDATE cards SET active=0")
        for item in items:
            row = store.conn.execute("SELECT * FROM cards WHERE id=?", (item["id"],)).fetchone()
            state, result = "pending", None
            if row:
                state, result = row["state"], row["result"]
                if row["fingerprint"] != item["fingerprint"]:
                    state = "stale"
                elif state in SUCCESS:
                    checked = validated(json.loads(result), restore_card(item["card"], config.base_dir), item["request_key"])
                    if checked is None:
                        state = "stale"
                    else:
                        result = encode(checked)
                        state = "review" if checked["status"] == "review" else "completed"
                # A manual checkpoint may have arrived since queue creation. Explicit
                # refresh deliberately bypasses it; normal pending work can reuse it.
                if state == "pending" and not row["refresh"]:
                    checkpoint = checkpoint_for(config, item)
                    if checkpoint:
                        result = encode(checkpoint)
                        state = "review" if checkpoint["status"] == "review" else "completed"
                        store.conn.execute("INSERT INTO history(card_id,fingerprint,result,saved_at) VALUES (?,?,?,?)",
                            (item["id"], item["fingerprint"], result, stamp()))
                store.conn.execute("UPDATE cards SET family=?,species=?,card=?,fingerprint=?,request_key=?,state=?,result=?,active=1 WHERE id=?",
                    (item["family"], item["species"], encode(item["card"]), item["fingerprint"], item["request_key"], state, result, item["id"]))
            else:
                card = restore_card(item["card"], config.base_dir)
                checkpoint = checkpoint_for(config, item)
                if checkpoint:
                    result = encode(checkpoint)
                    state = "review" if checkpoint["status"] == "review" else "completed"
                elif (item["family"], item["species"]) in disappeared_species:
                    state = "stale"  # Possible rename/regrouping; never silently repeat it.
                store.conn.execute("INSERT INTO cards(id,family,species,card,fingerprint,request_key,state,result,active) VALUES (?,?,?,?,?,?,?,?,1)",
                    (item["id"], item["family"], item["species"], encode(item["card"]), item["fingerprint"], item["request_key"], state, result))
                if result:
                    store.conn.execute("INSERT INTO history(card_id,fingerprint,result,saved_at) VALUES (?,?,?,?)",
                        (item["id"], item["fingerprint"], result, stamp()))
        store.conn.execute("UPDATE cards SET state='stale' WHERE active=0")
    store.set("missing", missing)
    store.set("last_scan", stamp())
    return db


def probe(folder):
    if not folder.is_dir():
        raise OSError(f"Output directory unavailable: {folder}")
    path = folder / (".campaign-probe-" + uuid.uuid4().hex + ".tmp")
    try:
        with path.open("xb") as stream:
            stream.write(b"probe")
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        path.unlink(missing_ok=True)


def output_available(config, families):
    try:
        probe(config.output_dir)
        for family in families:
            probe(config.output_dir / family)
        return True
    except OSError:
        if config.output_policy == "stop":
            raise
        config.fallback_dir.mkdir(parents=True, exist_ok=True)
        probe(config.fallback_dir)
        return False


def build_publications(config, store):
    """Create immutable local snapshots using the established renderer and filenames."""
    groups = {}
    for row in store.rows():
        if row["active"] and row["result"] and row["state"] != "stale":
            groups.setdefault((row["family"], row["species"]), []).append(row)
    missing = store.get("missing", [])
    for item in missing:
        groups.setdefault((item["family"], item["species"]), [])
    for (family, species), rows in groups.items():
        entries, journal = [], []
        for row in rows:
            card = restore_card(json.loads(row["card"]), config.base_dir)
            result = json.loads(row["result"])
            key = (not bool(card.enums), tuple(int(e[1:]) for e in card.enums), t.natural_key(card.base_id))
            entries.append((key, t.output_block(card, result)))
            journal.append(result)
        for item in missing:
            if (item["family"], item["species"]) == (family, species):
                entries.append(((False, (int(item["enum"][1:]),), t.natural_key(item["enum"])), item["block"]))
        text = "".join(block for _, block in sorted(entries, key=lambda pair: pair[0]))
        calls = [call for result in journal for call in result.get("call_usage", [])]
        # Same footer text, explicitly scoped to the saved results in this snapshot.
        text += ("SAVED RESULT USAGE (includes recorded retries; not new spending this run):\n"
                 + token_usage.tokens_line(token_usage.aggregate(calls)) + "\n"
                 + token_usage.averages(calls) + "\n" + token_usage.summary(calls) + "\n")
        fingerprint = digest(text.encode("utf-8"))
        pub_id = digest(encode([family, species, fingerprint]).encode())
        if store.conn.execute("SELECT 1 FROM publications WHERE id=?", (pub_id,)).fetchone():
            continue
        folder = config.state_dir / "artifacts" / family
        folder.mkdir(parents=True, exist_ok=True)
        path, stream = t.open_output_report(folder, f"{species}_transcriptions")
        with stream:
            t.durable_write(stream, text)
        # Publication ledger is committed only after the complete local artifact is fsynced.
        with store.conn:
            store.conn.execute("INSERT INTO publications VALUES (?,?,?,?,?,?,?,?,?)",
                (pub_id, family, species, str(path), encode(journal), fingerprint, "local", None, None))


def copy_report(source, target, expected):
    if digest(source.read_bytes()) != expected:
        raise RuntimeError(f"Local artifact changed: {source}; retained for investigation")
    if target.exists():
        if digest(target.read_bytes()) != expected:
            raise RuntimeError(f"Report conflict: {target}; neither copy was overwritten")
        return
    # A complete temp is hard-linked exclusively into place: atomic visibility, no overwrite.
    temp = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temp.open("xb") as out:
            out.write(source.read_bytes())
            out.flush()
            os.fsync(out.fileno())
        try:
            os.link(temp, target)
        except FileExistsError:
            if digest(target.read_bytes()) != expected:
                raise RuntimeError(f"Report conflict: {target}")
        except OSError:
            # Some Drive providers do not support hard links. Exclusive creation still
            # protects other reports; an interrupted partial is retained as a conflict.
            with target.open("xb") as out:
                out.write(temp.read_bytes())
                out.flush()
                os.fsync(out.fileno())
        if digest(target.read_bytes()) != expected:
            raise OSError(f"Read-back verification failed: {target}")
    finally:
        temp.unlink(missing_ok=True)


def publish(config, store, drive):
    root = config.output_dir if drive else config.fallback_dir
    if drive:
        for pub in store.conn.execute("SELECT * FROM publications WHERE state='drive_local'").fetchall():
            destination = Path(pub["destination"])
            if destination.exists():
                if digest(destination.read_bytes()) != pub["report_hash"]:
                    raise RuntimeError(f"Published report changed: {destination}; preserved for review")
            else:
                with store.conn:
                    store.conn.execute("UPDATE publications SET state='local' WHERE id=?", (pub["id"],))
    for pub in store.conn.execute("SELECT * FROM publications WHERE state != 'drive_local' ORDER BY rowid").fetchall():
        folder = root / pub["family"]
        if not drive:
            folder.mkdir(parents=True, exist_ok=True)
        probe(folder)
        journal_path = folder / f"{pub['species']}_transcriptions_cache.jsonl"
        with t.species_lock(folder / f"{pub['species']}_transcriptions.lock"):
            results = json.loads(pub["journal"])
            saved = set()
            if results and journal_path.exists():
                with journal_path.open(encoding="utf-8") as history:
                    for line in history:
                        try:
                            entry = json.loads(line)
                            if isinstance(entry, dict) and isinstance(entry.get("campaign_result_id"), str):
                                saved.add(entry["campaign_result_id"])
                        except (ValueError, UnicodeError):
                            continue
            if results:
                with t.Journal(journal_path) as journal:
                    for result in results:
                        identifier = result.get("campaign_result_id")
                        if identifier and identifier not in saved:
                            journal.append(result)
                            saved.add(identifier)
            source = Path(pub["report"])
            destination = pub["destination"] if drive else pub["fallback_destination"]
            if not destination:
                # Reserve a collision-free name in DB before any copy; restarts reuse it.
                target = folder / source.name
                index = 2
                while target.exists() and digest(target.read_bytes()) != pub["report_hash"]:
                    target = folder / f"{source.stem}_{index}.txt"
                    index += 1
                destination = str(target)
                column = "destination" if drive else "fallback_destination"
                with store.conn:
                    store.conn.execute(f"UPDATE publications SET {column}=? WHERE id=?", (destination, pub["id"]))
            copy_report(source, Path(destination), pub["report_hash"])
        with store.conn:
            store.conn.execute("UPDATE publications SET state=? WHERE id=?",
                               ("drive_local" if drive else "fallback", pub["id"]))


def status(config, store):
    rows = store.rows()
    counts = {}
    for row in rows:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    quota = t.DailyQuota(config.args)
    # Status never initializes, reserves, resets or repairs quota state.
    state = quota._read() if quota.path.exists() else None
    entry = state["models"].get(quota.key, {}) if state else {}
    used = entry.get("attempts", 0) if entry.get("date") == quota.day() else 0
    exhausted = entry.get("exhausted", False) and entry.get("date") == quota.day()
    attempts = store.conn.execute("SELECT * FROM attempts WHERE state != 'not_sent'").fetchall()
    calls = [json.loads(a["usage"]) if a["usage"] else {"usage": {}, "cost_usd": None} for a in attempts]
    completed = sum(counts.get(s, 0) for s in SUCCESS)
    remaining = sum(counts.get(s, 0) for s in ("pending", "retryable", "in_progress"))
    fresh_completed = store.get("fresh_completed", 0)
    ratio = max(1, len(attempts) / fresh_completed) if fresh_completed else None
    pubs = [dict(row) for row in store.conn.execute(
        "SELECT report,state,destination,fallback_destination FROM publications ORDER BY rowid")]
    return dict(campaign_status="paused" if config.pause_path.exists() else store.get("status", "ready"),
        total_physical_cards=sum(r["active"] for r in rows),
        total_source_images=sum(len(json.loads(r["card"])["paths"]) for r in rows if r["active"]),
        completed_cards=completed, remaining_cards=remaining, review_required=counts.get("review", 0),
        failed_cards=counts.get("retryable", 0) + counts.get("permanent", 0), states=counts,
        missing_source_catalogue_entries=sum(m["rows"] for m in store.get("missing", [])),
        attempts_used_today=used if state is not None else None,
        remaining_daily_attempts=(0 if exhausted else max(0, config.args.rpd - used)) if state is not None else None,
        quota_day=quota.day(), quota_timezone=quota.timezone, campaign_api_attempts=len(attempts),
        uncertain_attempts=sum(a["state"] in {"intent", "reserved", "uncertain"} for a in attempts),
        token_usage=token_usage.aggregate(calls), estimated_cost=token_usage.cost_text(calls),
        current_or_last=store.get("current"), last_successful_run=store.get("last_successful_run"),
        last_error=store.get("last_error"), discovery_issues=store.get("discovery_issues", []),
        worker_host=store.get("worker_host"), runtime_matches_approved=store.get("approved_code") == code_identity(),
        estimated_remaining_days=math.ceil(remaining * ratio / config.args.rpd) if ratio is not None else None,
        minimum_remaining_days=math.ceil(remaining / config.args.rpd),
        estimate_excludes_stale_and_permanent=True, outputs=pubs,
        cards_requiring_attention=[dict(id=r["id"], state=r["state"], active=bool(r["active"]),
                                       error=json.loads(r["result"]).get("error") if r["result"] else None)
                                  for r in rows if r["state"] in {"stale", "retryable", "permanent"}],
        remote_upload_verified=False, updated_at=stamp())


def export_status(config, store):
    value = status(config, store)
    path = config.status_file or config.state_dir / "status.json"
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as out:
        t.durable_write(out, json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    os.replace(temp, path)
    return value


def initialize(config, quota_source=None):
    config.state_dir.mkdir(parents=True, exist_ok=True)
    config.quota_file.parent.mkdir(parents=True, exist_ok=True)
    if config.db_path.exists():
        raise ValueError("Campaign already exists; initialization never resets progress")
    if quota_source:
        source = Path(quota_source).resolve()
        if config.quota_file.exists():
            raise ValueError("Quota destination already exists; use it in place, never overwrite")
        source_args = SimpleNamespace(**vars(config.args))
        source_args.quota_file = str(source)
        with t.species_lock(source.with_name(source.name + ".lock")):
            if not source.is_file():
                raise ValueError("Quota source must exist")
            t.DailyQuota(source_args)._read()
            with config.quota_file.open("xb") as out:
                out.write(source.read_bytes())
                out.flush()
                os.fsync(out.fileno())
    if not config.quota_file.is_file():
        raise ValueError("Existing quota history is required; specify --quota-source after stopping other writers")
    t.DailyQuota(config.args)._read()
    with worker_lock(config):
        store = Store(config.db_path, create=True)
        try:
            store.set("approved_code", code_identity())
            store.set("locations", {k: str(getattr(config, k)) for k in ("base_dir", "csv", "output_dir", "quota_file", "fallback_dir")})
            store.set("worker_host", config.worker_host)
            store.set("status", "ready")
        finally:
            store.close()


def check_binding(config, store):
    locations = {k: str(getattr(config, k)) for k in ("base_dir", "csv", "output_dir", "quota_file", "fallback_dir")}
    if locations != store.get("locations") or config.worker_host != store.get("worker_host"):
        raise ValueError("Campaign locations/host changed; restore configuration before continuing")


def run_worker(config, store, engine=None):
    check_binding(config, store)
    if platform.node().casefold() != config.worker_host.casefold():
        raise ValueError("This is not the designated production computer")
    if store.get("approved_code") != code_identity():
        raise ValueError("Code changed: review/test this revision, then use accept-code before running")
    if config.pause_path.exists():
        return EXIT["paused"]
    if not config.quota_file.is_file():
        raise ValueError("Quota history is missing; refusing to start a fresh counter")
    quota = CampaignQuota(t.DailyQuota(config.args), store, config)
    quota.recover()
    # Inventory validates all routing and images before a single request.
    db = scan(config, store)
    families = {row["family"] for row in store.rows() if row["active"]}
    families.update(m["family"] for m in store.get("missing", []))
    drive = output_available(config, families)
    build_publications(config, store)
    publish(config, store, drive)
    engine = engine or t.Transcriber(config.args)
    engine.quota = quota
    stop = "complete"
    store.set("status", "running")
    try:
        for row in store.rows():
            if not row["active"] or row["state"] not in {"pending", "retryable"}:
                continue
            if row["state"] == "retryable" and row["retry_after"] and row["retry_after"] > quota.quota.day():
                stop = "service"
                continue
            if config.pause_path.exists():
                stop = "paused"
                break
            if store.get("approved_code") != code_identity():
                raise ValueError("Runtime files changed during worker execution; stop and review update")
            # Check quota before credential lookup, image transmission or opening the SDK.
            entry = quota.quota._read()["models"].get(quota.quota.key, {})
            if entry.get("date") == quota.quota.day() and (entry.get("exhausted") or entry["attempts"] >= config.args.rpd):
                stop = "quota"
                break
            if not config.base_dir.is_dir() or not config.csv.is_file():
                raise OSError("Source storage disappeared")
            drive = output_available(config, {row["family"]})
            card = restore_card(json.loads(row["card"]), config.base_dir)
            # Reload current catalogue for every request: Drive can change between cards.
            with redirect_stdout(io.StringIO()):
                current_db = t.load_database(config.csv)
            current_cards, issues, _ = t.discover_cards(card.paths[0].parent, None, include_uncatalogued=True)
            current_card = next((item for item in current_cards if item.base_id.casefold() == card.base_id.casefold()), None)
            if issues or current_card is None or encode(card_data(current_card, config.base_dir)) != row["card"]:
                with store.conn:
                    store.conn.execute("UPDATE cards SET state='stale' WHERE id=?", (row["id"],))
                stop = "attention"
                continue
            fingerprint, key, contents, prompt = prepare(card, current_db, config.args, config.base_dir)
            if fingerprint != row["fingerprint"]:
                with store.conn:
                    store.conn.execute("UPDATE cards SET state='stale' WHERE id=?", (row["id"],))
                stop = "attention"
                continue
            store.set("current", dict(family=row["family"], species=row["species"], card=card.base_id))
            with store.conn:
                store.conn.execute("UPDATE cards SET state='in_progress' WHERE id=?", (row["id"],))
            quota.card_id = row["id"]
            start_seq = store.conn.execute("SELECT coalesce(max(seq),0) FROM attempts").fetchone()[0]
            result = engine.transcribe(card, contents)
            result = {**result, "request_metadata": t.request_metadata(prompt, config.args, key),
                "provider": config.args.provider, "model": config.args.model, "key": key,
                "cache_version": t.CACHE_VERSION, "base_id": card.base_id,
                "catalog_numbers": list(card.enums), "files": [str(p) for p in card.paths],
                "saved_at": stamp(), "campaign_result_id": uuid.uuid4().hex}
            stop_kind = result.get("stop_kind")
            if result["status"] in {"ok", "review"}:
                state = "completed" if result["status"] == "ok" else "review"
            elif stop_kind in {"service", "daily"}:
                state = "pending" if stop_kind == "daily" else "retryable"
            else:
                state = "permanent"
            store.save_result(row, result, state, quota.quota.day(), config.retry_days)
            print(f"{stamp()} {row['id']}: {result['status'].upper()}")
            if result.get("error"):
                print("  " + result["error"])
            if result.get("stop_reason"):
                print("  " + result["stop_reason"])
                store.set("last_stop_reason", result["stop_reason"])
            with store.conn:
                records = store.conn.execute("SELECT seq FROM attempts WHERE seq>? AND state='reserved' ORDER BY seq", (start_seq,)).fetchall()
                for attempt, call in zip(records, result.get("call_usage", [])):
                    store.conn.execute("UPDATE attempts SET state='returned',usage=? WHERE seq=?", (encode(call), attempt["seq"]))
            if state in SUCCESS:
                store.set("fresh_completed", store.get("fresh_completed", 0) + 1)
            # Each response is already committed locally. Publish a species snapshot
            # at the end of this invocation, or recover it at the next startup.
            export_status(config, store)
            if result.get("fatal"):
                stop = "paused" if config.pause_path.exists() else {
                    "daily": "quota", "service": "service"}.get(stop_kind, "attention")
                if stop == "attention":
                    config.pause_path.write_text(result.get("stop_reason", "Fatal failure"), encoding="utf-8")
                break
        if any(r["state"] in {"stale", "permanent"} for r in store.rows()) and stop == "complete":
            stop = "attention"
        build_publications(config, store)
        try:
            publish(config, store, drive)
        except OSError:
            if config.output_policy != "fallback":
                raise
            publish(config, store, False)
        store.set("status", stop)
        if stop in {"complete", "quota"}:
            store.set("last_successful_run", stamp())
        store.set("last_error", store.get("last_stop_reason") if stop in {"service", "attention"} else None)
        print(f"{stamp()} Campaign stopped: {stop}")
        export_status(config, store)
        return EXIT[stop]
    finally:
        engine.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Machine-local JSON configuration")
    parser.add_argument("command", choices=["init", "dry-run", "scan", "run", "status", "pause", "resume",
                                            "retry", "refresh", "reconcile", "accept-code"])
    parser.add_argument("--quota-source", help="init only: copy existing history without overwrite")
    parser.add_argument("--card", help="Exact card ID from status/database; retry/refresh only")
    args = parser.parse_args(argv)
    config, store = None, None
    try:
        config = Config(args.config)
        if args.command == "dry-run":
            _, items, missing, issues = inventory(config)
            print(json.dumps(dict(physical_cards=len(items), source_images=sum(len(i["card"]["paths"]) for i in items),
                missing_source_catalogue_entries=sum(m["rows"] for m in missing), issues=issues,
                cards=[{"id": i["id"], "images": i["card"]["paths"]} for i in items]), indent=2))
            return 20 if issues else 0
        if args.command == "init":
            initialize(config, args.quota_source)
            print("Initialized offline; no schedule enabled. Run scan and inspect status.")
            return 0
        if args.command == "pause":
            if not config.db_path.is_file():
                raise ValueError("Initialize before pausing")
            config.pause_path.write_text("Paused by operator\n", encoding="utf-8")
            print("Pause requested; any current request may finish and will be checkpointed.")
            return 0
        if args.command == "status":
            store = Store(config.db_path)
            print(json.dumps(status(config, store), indent=2, ensure_ascii=False))
            return 0
        with worker_lock(config):
            store = Store(config.db_path)
            check_binding(config, store)
            if args.command == "resume":
                config.pause_path.unlink(missing_ok=True)
            elif args.command == "accept-code":
                store.set("approved_code", code_identity())
                print("Approved current runtime files; next scan still checks fingerprints and validation.")
            elif args.command == "scan":
                scan(config, store)
            elif args.command in {"retry", "refresh"}:
                if not args.card:
                    raise ValueError("Select exactly one --card ID; routine continuation never refreshes successes")
                row = store.conn.execute("SELECT * FROM cards WHERE id=?", (args.card,)).fetchone()
                permitted = {"retryable", "permanent"} if args.command == "retry" else SUCCESS | {"stale"}
                if not row or row["state"] not in permitted or not row["active"]:
                    raise ValueError("Card is absent or ineligible; scan and inspect its state first")
                with store.conn:
                    store.conn.execute("UPDATE cards SET state='pending',result=NULL,failures=0,retry_after=NULL,refresh=1 WHERE id=?", (args.card,))
            elif args.command == "reconcile":
                families = {r["family"] for r in store.rows() if r["active"]}
                if not output_available(config, families):
                    raise OSError("Drive unavailable; reconciliation postponed")
                build_publications(config, store)
                publish(config, store, True)
            elif args.command == "run":
                config.log_file.parent.mkdir(parents=True, exist_ok=True)
                with config.log_file.open("a", encoding="utf-8", buffering=1) as log, redirect_stdout(log):
                    print(f"\n{stamp()} Campaign worker starting on {platform.node()}")
                    return run_worker(config, store)
            export_status(config, store)
        return 0
    except KeyboardInterrupt:
        if store and args.command not in {"dry-run", "status"}:
            store.set("status", "interrupted")
        return 130
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"Campaign stopped: {exc}", file=sys.stderr)
        if store and args.command not in {"dry-run", "status"}:
            try:
                store.set("status", "unavailable" if isinstance(exc, OSError) else "attention")
                store.set("last_error", str(exc))
                export_status(config, store)
            except (OSError, ValueError, RuntimeError, sqlite3.Error):
                pass
        if config and args.command not in {"dry-run", "status"} and config.log_file.parent.is_dir():
            try:
                with config.log_file.open("a", encoding="utf-8") as log:
                    t.durable_write(log, f"{stamp()} STOPPED: {exc}\n")
            except OSError:
                pass
        return 21 if isinstance(exc, OSError) else 20
    finally:
        if store:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
