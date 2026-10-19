"""Offline campaign acceptance tests; all model calls use the existing fake client."""
import contextlib
from datetime import datetime, timezone, timedelta
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import tempfile
import threading
import unittest
from unittest.mock import patch

from PIL import Image
import campaign as c
import transcribe as t
import test_transcribe as fixtures


class CampaignTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.family = self.root / "Family" / "Birds"
        self.jpeg = self.family / "Test_bird" / "JPEG"
        self.jpeg.mkdir(parents=True)
        self.csv = self.root / "catalogue.csv"
        self.csv.write_text("catalogNumber,Scientific Name,Family,Collector\n"
                            "E01,Test bird,Birds,Person\nE2,Test bird,Birds,Person\n"
                            "E3,Test bird,Birds,Person\nE9,Test bird,Birds,Person\n", encoding="utf-8")
        self.image("Test_bird_E01(A).jpg")
        self.image("Test_bird_E01(B).jpg", "blue")
        self.image("Test_bird_E2_E3.jpg")
        self.image("Test_bird_Uncatalogued1.jpg")
        self.quota = self.root / "quota.json"
        self.quota.write_text('{"version":1,"models":{}}', encoding="utf-8")
        self.config_path = self.root / "campaign.local.json"
        self.config_data = dict(base_dir=str(self.root / "Family"), csv=str(self.csv),
            output_dir=str(self.root / "Family"), state_dir=str(self.root / "state"),
            quota_file=str(self.quota), worker_host=platform.node(), rpd=2)
        self.config = self.configure()
        c.initialize(self.config)
        self.store = c.Store(self.config.db_path)
        self.addCleanup(self.store.close)
        self.day = datetime(2026, 10, 12, 12, tzinfo=timezone.utc)
        self.addCleanup(patch.stopall)
        patch.object(t.DailyQuota, "day", lambda quota: self.day.date().isoformat()).start()
        self.output = io.StringIO()
        ctx = contextlib.redirect_stdout(self.output)
        ctx.__enter__()
        self.addCleanup(ctx.__exit__, None, None, None)

    def configure(self, **values):
        self.config_data.update(values)
        self.config_path.write_text(json.dumps(self.config_data), encoding="utf-8")
        return c.Config(self.config_path)

    def image(self, name, color="red"):
        path = self.jpeg / name
        with Image.new("RGB", (20, 20), color) as image:
            image.save(path)
        return path

    def engine(self, outcomes=()):
        clock = fixtures.Clock()
        client = fixtures.FakeClient(outcomes, clock)
        return t.Transcriber(self.config.args, client, clock.time, clock.sleep), client

    def run_worker(self, outcomes=()):
        engine, client = self.engine(outcomes)
        with c.worker_lock(self.config):
            code = c.run_worker(self.config, self.store, engine)
        return code, client

    def advance(self, days=1):
        self.day += timedelta(days=days)

    def counts(self):
        return c.status(self.config, self.store)

    def test_multiday_dedup_shared_sides_uncatalogued_and_missing(self):
        code, client = self.run_worker()
        self.assertEqual(code, 10)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(self.counts()["total_physical_cards"], 3)
        self.assertEqual(self.counts()["total_source_images"], 4)
        self.assertEqual(self.counts()["missing_source_catalogue_entries"], 1)
        self.assertEqual(self.run_worker()[1].calls, [])
        self.advance(25)
        code, client = self.run_worker()
        self.assertEqual(code, 0)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(self.counts()["campaign_api_attempts"], 3)
        self.assertEqual(self.counts()["completed_cards"], 3)
        self.assertEqual(self.run_worker()[1].calls, [])
        report = Path(self.counts()["outputs"][-1]["destination"]).read_text(encoding="utf-8")
        self.assertLess(report.index("CM9 (MISSING)"), report.index("Uncatalogued1"))
        self.assertIn("CM2", report)
        self.assertIn("CM3", report)

    def test_exact_cap_includes_format_and_service_retries(self):
        code, client = self.run_worker([fixtures.FakeAPIError(503)])
        self.assertEqual(code, 10)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(self.counts()["attempts_used_today"], 2)
        self.assertEqual(self.counts()["completed_cards"], 1)

    def test_format_retry_and_daily_pause_preserve_failed_response(self):
        self.config.args.rpd = 1
        partial = "Name: partial response without required sections"
        code, client = self.run_worker([fixtures.response(partial)])
        self.assertEqual(code, 10)
        self.assertEqual(len(client.calls), 1)
        result = json.loads(next(r for r in self.store.rows() if r["result"])["result"])
        self.assertEqual(result["text"], partial)
        self.advance()
        self.assertEqual(len(self.run_worker()[1].calls), 1)

    def test_crashed_request_charged_and_bounded_until_next_day(self):
        engine, client = self.engine([KeyboardInterrupt()])
        with self.assertRaises(KeyboardInterrupt):
            c.run_worker(self.config, self.store, engine)
        self.assertEqual(self.counts()["attempts_used_today"], 1)
        self.assertEqual(self.store.rows()[0]["state"], "in_progress")
        self.run_worker()
        self.assertEqual(self.store.rows()[0]["state"], "retryable")
        self.advance()
        self.run_worker()
        self.assertEqual(self.store.rows()[0]["state"], "completed")
        self.assertGreaterEqual(self.counts()["campaign_api_attempts"], 4)

    def test_intent_crash_conservatively_reserves_even_if_already_charged(self):
        c.scan(self.config, self.store)
        row = self.store.rows()[0]
        quota = t.DailyQuota(self.config.args)
        quota.update()
        with self.store.conn:
            self.store.conn.execute("INSERT INTO attempts(card_id,day,state) VALUES (?,?,'intent')", (row["id"], quota.day()))
        c.CampaignQuota(quota, self.store, self.config).recover()
        self.assertEqual(self.counts()["attempts_used_today"], 2)
        self.assertEqual(self.counts()["uncertain_attempts"], 1)
        self.assertEqual(self.run_worker()[1].calls, [])

    def test_intent_from_yesterday_does_not_spend_today(self):
        with self.store.conn:
            self.store.conn.execute("INSERT INTO attempts(card_id,day,state) VALUES ('x','2026-10-11','intent')")
        c.CampaignQuota(t.DailyQuota(self.config.args), self.store, self.config).recover()
        self.assertEqual(self.counts()["attempts_used_today"], 0)

    def test_existing_checkpoint_over_48_hours_imported_without_rewrite(self):
        db, items, _, _, _ = c.inventory(self.config, verify=True)
        item = items[0]
        card = c.restore_card(item["card"], self.config.base_dir)
        entry = dict(key=item["request_key"], cache_version=t.CACHE_VERSION, status="ok",
            text=fixtures.transcript(card.sections), warnings=[], saved_at="2020-01-01T00:00:00+00:00")
        path = self.family / "Test_bird_transcriptions_cache.jsonl"
        path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        before = path.read_bytes()
        c.scan(self.config, self.store, verify=True)
        self.assertEqual(self.store.rows()[0]["state"], "completed")
        self.assertEqual(path.read_bytes(), before)
        with t.Journal(path) as journal:
            self.assertIsNone(journal.reusable(item["request_key"]))
        self.assertEqual(len(self.run_worker()[1].calls), 2)

    def test_report_file_is_not_completion_evidence(self):
        (self.family / "Test_bird_transcriptions_20200101_0000.txt").write_text("STATUS: OK")
        c.scan(self.config, self.store)
        self.assertTrue(all(r["state"] == "pending" for r in self.store.rows()))

    def test_prompt_and_source_changes_are_stale_until_explicit_refresh(self):
        self.run_worker()
        self.image("Test_bird_E01(A).jpg", "green")
        c.scan(self.config, self.store)
        self.assertEqual(self.store.rows()[0]["state"], "stale")
        with patch.object(c.egg_slip_prompt, "BASE_PROMPT", c.egg_slip_prompt.BASE_PROMPT + "\nChanged"):
            c.scan(self.config, self.store)
        self.assertEqual(self.store.rows()[1]["state"], "stale")
        c.scan(self.config, self.store)
        self.assertEqual(self.store.rows()[1]["state"], "stale")
        self.assertEqual(c.main(["--config", str(self.config_path), "refresh", "--card", self.store.rows()[0]["id"]]), 0)
        self.assertEqual(self.store.rows()[0]["state"], "pending")
        self.assertGreaterEqual(self.store.conn.execute("SELECT count(*) FROM history").fetchone()[0], 2)

    def test_catalogue_change_stales_matching_card(self):
        self.run_worker()
        self.csv.write_text(self.csv.read_text().replace("E01,Test bird,Birds,Person", "E01,Test bird,Birds,Changed"))
        c.scan(self.config, self.store)
        self.assertEqual(self.store.rows()[0]["state"], "stale")
        self.assertEqual(self.store.rows()[1]["state"], "completed")

    def test_disconnected_source_is_not_reported_missing(self):
        c.scan(self.config, self.store)
        self.jpeg.rename(self.jpeg.with_name("offline"))
        with self.assertRaises(ValueError):
            self.run_worker()
        self.assertTrue(all(r["active"] for r in self.store.rows()))
        self.assertEqual(self.counts()["campaign_api_attempts"], 0)

    def test_rejected_side_group_remains_error_not_csv_missing(self):
        self.image("Test_bird_E01.jpg")
        _, _, missing, issues, _ = c.inventory(self.config)
        self.assertTrue(issues)
        self.assertNotIn("E01", [m["enum"] for m in missing])
        with self.assertRaises(ValueError):
            self.run_worker()

    def configure_output(self, policy):
        output = self.root / "DriveOutput"
        output.mkdir()
        (output / "Birds").mkdir()
        self.config = self.configure(output_dir=str(output), output_policy=policy,
                                     fallback_dir=str(self.root / "fallback"))
        self.store.set("locations", {k: str(getattr(self.config, k)) for k in ("base_dir", "csv", "output_dir", "quota_file", "fallback_dir")})
        return output

    def test_disconnected_output_stop_policy_sends_nothing(self):
        output = self.configure_output("stop")
        output.rename(output.with_name("offline"))
        with self.assertRaises(OSError):
            self.run_worker()
        self.assertEqual(self.counts()["campaign_api_attempts"], 0)

    def test_fallback_reconciliation_idempotent_without_requests_or_overwrites(self):
        output = self.configure_output("fallback")
        offline = output.with_name("offline")
        output.rename(offline)
        self.run_worker()
        self.assertTrue(all(p["state"] == "fallback" for p in self.counts()["outputs"]))
        self.assertEqual(self.counts()["completed_cards"], 2)
        offline.rename(output)
        cli = ["--config", str(self.config_path), "reconcile"]
        self.assertEqual(c.main(cli), 0)
        snapshot = {p: p.read_bytes() for p in output.rglob("*") if p.is_file()}
        self.assertEqual(c.main(cli), 0)
        self.assertEqual(snapshot, {p: p.read_bytes() for p in output.rglob("*") if p.is_file()})
        self.assertTrue(all(p["state"] == "drive_local" for p in self.counts()["outputs"]))
        self.assertFalse(self.counts()["remote_upload_verified"])

    def test_failed_report_publication_recovers_saved_result_without_request(self):
        with patch.object(c, "publish", side_effect=[None, OSError("offline")]):
            with self.assertRaises(OSError):
                self.run_worker()
        self.assertEqual(self.store.rows()[0]["state"], "completed")
        self.run_worker()
        self.assertEqual(self.counts()["completed_cards"], 2)
        self.assertEqual(self.counts()["campaign_api_attempts"], 2)

    def test_report_copy_conflict_retains_both_bytes(self):
        src, dst = self.root / "src.txt", self.root / "dst.txt"
        src.write_bytes(b"original")
        dst.write_bytes(b"existing museum report")
        with self.assertRaises(RuntimeError):
            c.copy_report(src, dst, c.digest(b"original"))
        self.assertEqual(dst.read_bytes(), b"existing museum report")
        self.assertEqual(src.read_bytes(), b"original")

    def test_duplicate_workers_block_and_stale_lock_file_recovers(self):
        path = self.quota.with_name(self.quota.name + ".worker.sqlite3")
        with c.worker_lock(self.config):
            with self.assertRaises(RuntimeError):
                with c.worker_lock(self.config):
                    pass
        self.assertTrue(path.exists())
        with c.worker_lock(self.config):
            pass

    def test_code_change_requires_acceptance_then_preserves_completed(self):
        self.run_worker()
        changed = {**c.code_identity(), "transcribe.py": "new-tested-build"}
        with patch.object(c, "code_identity", return_value=changed):
            with self.assertRaisesRegex(ValueError, "Code changed"):
                self.run_worker()
            self.assertEqual(c.main(["--config", str(self.config_path), "accept-code"]), 0)
            self.assertEqual(self.run_worker()[1].calls, [])
            self.advance()
            self.assertEqual(len(self.run_worker()[1].calls), 1)

    def test_pause_resume_and_wrong_machine(self):
        self.assertEqual(c.main(["--config", str(self.config_path), "pause"]), 0)
        self.assertEqual(self.run_worker()[0], 11)
        self.assertEqual(c.main(["--config", str(self.config_path), "resume"]), 0)
        with patch.object(c.platform, "node", return_value="another-computer"):
            with self.assertRaisesRegex(ValueError, "designated"):
                self.run_worker()

    def test_pause_between_format_attempts_preserves_partial_text(self):
        partial = "Name: incomplete but retained"
        engine, client = self.engine([fixtures.response(partial)])
        engine.sleep = lambda delay: self.config.pause_path.write_text("operator pause")
        code = c.run_worker(self.config, self.store, engine)
        self.assertEqual(code, 11)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(json.loads(self.store.rows()[0]["result"])["text"], partial)

    def test_auth_failure_pauses_until_intervention(self):
        code, client = self.run_worker([fixtures.FakeAPIError(401)])
        self.assertEqual(code, 20)
        self.assertEqual(len(client.calls), 1)
        self.assertTrue(self.config.pause_path.exists())
        self.advance()
        self.assertEqual(self.run_worker()[1].calls, [])

    def test_service_outage_is_bounded_across_days(self):
        self.config.args.rpd = 500
        for day in range(self.config.retry_days):
            code, client = self.run_worker([fixtures.FakeAPIError(503)] * self.config.args.attempts)
            self.assertEqual(code, 12)
            self.assertEqual(len(client.calls), self.config.args.attempts)
            if day < self.config.retry_days - 1:
                self.assertEqual(self.store.rows()[0]["state"], "retryable")
            self.advance()
        self.assertEqual(self.store.rows()[0]["state"], "permanent")

    def test_status_offline_read_only_including_quota(self):
        self.run_worker()
        before = self.quota.read_bytes()
        snapshot = self.config.db_path.read_bytes()
        with patch.object(t.Transcriber, "ensure_client", side_effect=AssertionError("no service")):
            status = self.counts()
            self.assertEqual(c.main(["--config", str(self.config_path), "status"]), 0)
        self.assertEqual(self.quota.read_bytes(), before)
        self.assertEqual(self.config.db_path.read_bytes(), snapshot)
        self.assertEqual(status["estimated_remaining_days"], 1)

    def test_failed_status_and_dry_run_remain_read_only(self):
        self.quota.write_text("damaged quota")
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(c.main(["--config", str(self.config_path), "status"]), 20)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.csv.unlink()
        before = {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(c.main(["--config", str(self.config_path), "dry-run"]), 21)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*") if p.is_file()})

    def test_sources_untouched_and_dry_run_creates_nothing(self):
        before = {p: p.read_bytes() for p in self.jpeg.iterdir()}
        before[self.csv] = self.csv.read_bytes()
        all_before = {p for p in self.root.rglob("*")}
        self.assertEqual(c.main(["--config", str(self.config_path), "dry-run"]), 0)
        self.assertEqual(all_before, {p for p in self.root.rglob("*")})
        self.run_worker()
        for path, data in before.items():
            self.assertEqual(path.read_bytes(), data)

    def test_genus_layout_and_uncatalogued_only_species(self):
        genus = self.family / "Test"
        genus.mkdir()
        self.jpeg.parent.rename(genus / "Test_bird")
        extra = self.family / "Other_bird" / "JPEG"
        extra.mkdir(parents=True)
        with Image.new("RGB", (20, 20)) as image:
            image.save(extra / "Other_bird_Uncatalogued.jpg")
        _, items, _, issues, _ = c.inventory(self.config)
        self.assertEqual(issues, [])
        self.assertEqual(len(items), 4)

    def test_missing_quota_refuses_reset(self):
        self.quota.unlink()
        with self.assertRaisesRegex(ValueError, "Quota history"):
            self.run_worker()
        self.assertFalse(self.quota.exists())

    def test_quota_deleted_between_attempts_stops_before_transmission(self):
        quota = c.CampaignQuota(t.DailyQuota(self.config.args), self.store, self.config)
        self.quota.unlink()
        with self.assertRaisesRegex(RuntimeError, "disappeared"):
            quota.update()
        self.assertFalse(self.quota.exists())

    def test_rename_is_stale_and_never_silently_retranscribed(self):
        self.run_worker()
        source = self.jpeg / "Test_bird_E2_E3.jpg"
        source.rename(self.jpeg / "Renamed_bird_E2_E3.jpg")
        c.scan(self.config, self.store)
        related = [r for r in self.store.rows() if "e2_e3" in r["id"]]
        self.assertEqual(len(related), 2)
        self.assertTrue(all(r["state"] == "stale" for r in related))

    def test_manual_checkpoint_arriving_after_scan_is_imported(self):
        c.scan(self.config, self.store)
        item = self.store.rows()[0]
        card = c.restore_card(json.loads(item["card"]), self.config.base_dir)
        key = c.prepare(card, t.load_database(self.csv), self.config.args, self.config.base_dir)[1]
        entry = dict(key=key, cache_version=t.CACHE_VERSION, status="ok",
                     text=fixtures.transcript(card.sections), warnings=[])
        path = self.family / "Test_bird_transcriptions_cache.jsonl"
        path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        self.run_worker()
        self.assertEqual(self.counts()["completed_cards"], 3)
        self.assertEqual(self.counts()["campaign_api_attempts"], 2)

    def test_missing_published_report_restored_offline(self):
        self.run_worker()
        report = Path(self.counts()["outputs"][-1]["destination"])
        original = report.read_bytes()
        report.unlink()
        self.assertEqual(c.main(["--config", str(self.config_path), "reconcile"]), 0)
        self.assertEqual(report.read_bytes(), original)
        self.assertEqual(self.counts()["campaign_api_attempts"], 2)

    def test_new_side_added_between_inventory_and_request_is_stale(self):
        engine, client = self.engine()
        original_probe = c.output_available
        calls = 0
        def changed(config, families):
            nonlocal calls
            calls += 1
            if calls == 2:
                self.image("Test_bird_E01(C).jpg")
            return original_probe(config, families)
        with patch.object(c, "output_available", side_effect=changed):
            c.run_worker(self.config, self.store, engine)
        self.assertEqual(self.store.rows()[0]["state"], "stale")
        self.assertEqual(len(client.calls), 2)

    def test_cross_process_lock_released_when_process_terminated(self):
        import subprocess
        import sys
        script = ("import campaign as c,sys; "
                  "config=c.Config(sys.argv[1]); "
                  "lock=c.worker_lock(config); lock.__enter__(); "
                  "print('locked',flush=True); sys.stdin.read()")
        child = subprocess.Popen([sys.executable, "-u", "-c", script, str(self.config_path)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(child.stdout.readline().strip(), "locked")
            with self.assertRaises(RuntimeError):
                with c.worker_lock(self.config):
                    pass
            child.terminate()
            child.wait(timeout=10)
            with c.worker_lock(self.config):
                pass
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)
            for stream in (child.stdin, child.stdout, child.stderr):
                stream.close()

    def test_quota_migration_preserves_all_profiles_and_never_overwrites(self):
        source = self.root / "old-quota.json"
        original = {"version": 1, "models": {"gemini/gemini-3.5-flash-lite": {
            "date": "2026-10-12", "attempts": 149, "exhausted": False}}}
        source.write_text(json.dumps(original))
        config = self.configure(state_dir=str(self.root / "second-state"), quota_file=str(self.root / "second-quota.json"))
        c.initialize(config, source)
        self.assertEqual(config.quota_file.read_bytes(), source.read_bytes())
        with self.assertRaises(ValueError):
            c.initialize(config, source)
        self.assertEqual(config.quota_file.read_bytes(), source.read_bytes())

    @contextlib.contextmanager
    def no_image_reads(self):
        read = Path.read_bytes
        open_file = Path.open
        def guarded(path):
            if path.suffix.lower() in {".jpg", ".jpeg"}:
                raise AssertionError(f"Metadata check read image bytes: {path}")
            return read(path)
        def guarded_open(path, *args, **kwargs):
            if path.suffix.lower() in {".jpg", ".jpeg"}:
                raise AssertionError(f"Metadata check opened an image: {path}")
            return open_file(path, *args, **kwargs)
        with patch.object(Path, "read_bytes", guarded), patch.object(Path, "open", guarded_open), patch.object(t, "prepare_image_bytes",
                side_effect=AssertionError("Metadata check decoded an image")):
            yield

    def test_metadata_scan_and_dry_run_never_read_or_decode_images(self):
        with self.no_image_reads():
            c.scan(self.config, self.store)
            self.assertEqual(c.main(["--config", str(self.config_path), "dry-run"]), 0)
        self.assertTrue(all(row["fingerprint"] is None and row["request_key"] is None for row in self.store.rows()))
        self.assertEqual(self.store.get("scan_mode"), "metadata")
        self.assertIn("[1/1] Test_bird", self.output.getvalue())
        self.assertIn("3 cards / 4 images checked", self.output.getvalue())
        self.assertIn("Queue saved:", self.output.getvalue())

    def test_completed_campaign_continuation_does_not_reread_images(self):
        self.run_worker()
        self.advance()
        self.run_worker()
        with self.no_image_reads():
            c.scan(self.config, self.store)
            self.assertEqual(self.run_worker()[1].calls, [])
        self.assertEqual(self.counts()["completed_cards"], 3)

    def test_worker_only_reads_selected_card_once_even_with_service_retry(self):
        self.config.args.rpd = 2
        read = Path.read_bytes
        paths = []
        def counted(path):
            if path.suffix.lower() == ".jpg":
                paths.append(path.name)
            return read(path)
        with patch.object(Path, "read_bytes", counted):
            code, client = self.run_worker([fixtures.FakeAPIError(503)])
        self.assertEqual(code, 10)
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(paths, ["Test_bird_E01(A).jpg", "Test_bird_E01(B).jpg"])
        self.assertEqual(self.counts()["content_fingerprinted_cards"], 1)

    def test_metadata_changes_mark_stale_without_image_reads(self):
        self.run_worker()
        path = self.jpeg / "Test_bird_E01(A).jpg"
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
        with self.no_image_reads():
            c.scan(self.config, self.store)
        self.assertEqual(self.store.rows()[0]["state"], "stale")
        self.assertEqual(self.store.rows()[1]["state"], "completed")

    def test_metadata_identity_survives_virtual_drive_identifiers_changing(self):
        self.config = self.configure(source_identity="metadata")
        self.run_worker()
        stats = c.source_stats
        def remounted(card):
            return [{**s, "device": s["device"] + 1, "inode": s["inode"] + 1000}
                    for s in stats(card)]
        with patch.object(c, "source_stats", side_effect=remounted), self.no_image_reads():
            c.scan(self.config, self.store)
            self.assertEqual(self.run_worker()[1].calls, [])
        self.assertEqual(self.counts()["completed_cards"], 2)
        self.advance()
        with patch.object(c, "source_stats", side_effect=remounted):
            self.assertEqual(len(self.run_worker()[1].calls), 1)
        self.assertEqual(self.counts()["completed_cards"], 3)

    def test_default_identity_still_detects_filesystem_replacements(self):
        self.run_worker()
        stats = c.source_stats
        with patch.object(c, "source_stats", side_effect=lambda card:
                          [{**s, "inode": s["inode"] + 1} for s in stats(card)]), self.no_image_reads():
            c.scan(self.config, self.store)
        self.assertTrue(all(row["state"] == "stale" for row in self.store.rows()))

    def test_metadata_identity_still_detects_changed_modification_times(self):
        self.config = self.configure(source_identity="metadata")
        self.run_worker()
        path = self.jpeg / "Test_bird_E01(A).jpg"
        stat = path.stat()
        os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
        with self.no_image_reads():
            c.scan(self.config, self.store)
        self.assertEqual(self.store.rows()[0]["state"], "stale")
        self.assertEqual(self.store.rows()[1]["state"], "completed")

    def test_invalid_source_identity_policy_is_rejected(self):
        for value in ("guess", None, [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "source_identity"):
                self.configure(source_identity=value)

    def test_verify_saved_recovers_results_and_unattempted_queue_without_full_audit(self):
        self.run_worker()
        quota = self.quota.read_bytes()
        history = self.store.conn.execute("SELECT * FROM history").fetchall()
        original = [r["result"] for r in self.store.rows()]
        self.config = self.configure(source_identity="metadata")
        c.scan(self.config, self.store)
        self.assertTrue(all(row["state"] == "stale" for row in self.store.rows()))
        self.config.pause_path.write_text("maintenance")
        read = Path.read_bytes
        opened = []
        def counted(path):
            if path.suffix.lower() == ".jpg":
                opened.append(path.name)
            return read(path)
        with patch.object(Path, "read_bytes", counted):
            self.assertEqual(c.main(["--config", str(self.config_path), "verify-saved"]), 0)
        self.assertEqual(opened, ["Test_bird_E01(A).jpg", "Test_bird_E01(B).jpg", "Test_bird_E2_E3.jpg"])
        self.assertEqual(self.counts()["states"], {"completed": 2, "pending": 1})
        self.assertEqual(original, [r["result"] for r in self.store.rows()])
        self.assertEqual(self.quota.read_bytes(), quota)
        self.assertEqual(history, self.store.conn.execute("SELECT * FROM history").fetchall())
        self.assertEqual(self.counts()["campaign_status"], "paused")
        self.assertEqual(self.counts()["scan_mode"], "saved_content")
        self.assertTrue(self.counts()["last_saved_verification"])
        self.config.pause_path.unlink()
        self.assertEqual(self.counts()["campaign_status"], "ready")
        self.assertEqual(self.run_worker()[1].calls, [])
        self.advance()
        self.assertEqual(len(self.run_worker()[1].calls), 1)

    def test_verify_saved_rejects_changed_source_content(self):
        self.run_worker()
        path = self.jpeg / "Test_bird_E01(A).jpg"
        path.write_bytes(path.read_bytes() + b"changed source")
        c.scan(self.config, self.store, verify_saved=True)
        self.assertEqual(self.store.rows()[0]["state"], "stale")
        self.assertEqual(self.store.rows()[1]["state"], "completed")
        self.assertEqual(self.counts()["campaign_api_attempts"], 2)

    def test_verify_saved_rejects_changed_prompt_and_catalogue(self):
        self.run_worker()
        build = c.egg_slip_prompt.build_prompt
        with patch.object(c.egg_slip_prompt, "build_prompt", side_effect=lambda *a: build(*a) + "policy change"):
            c.scan(self.config, self.store, verify_saved=True)
        self.assertTrue(all(row["state"] == "stale" for row in self.store.rows() if row["result"]))
        self.csv.write_text(self.csv.read_text().replace("Person", "Another collector"))
        c.scan(self.config, self.store, verify_saved=True)
        self.assertTrue(all(row["state"] == "stale" for row in self.store.rows() if row["result"]))

    def test_verify_saved_does_not_requeue_renamed_or_unknown_attempted_cards(self):
        c.scan(self.config, self.store)
        pending = self.store.rows()[1]
        with self.store.conn:
            self.store.conn.execute("UPDATE cards SET state='stale' WHERE id=?", (pending["id"],))
            self.store.conn.execute("INSERT INTO attempts(card_id,day,state) VALUES (?,?,'reserved')",
                                    (pending["id"], self.day.date().isoformat()))
        source = self.jpeg / "Test_bird_Uncatalogued1.jpg"
        source.rename(source.with_name("Test_bird_Uncatalogued2.jpg"))
        c.scan(self.config, self.store)
        with self.no_image_reads():
            c.scan(self.config, self.store, verify_saved=True)
        self.assertEqual(self.store.conn.execute("SELECT state FROM cards WHERE id=?", (pending["id"],)).fetchone()[0], "stale")
        renamed = next(r for r in self.store.rows() if "uncatalogued2" in r["id"])
        self.assertEqual(renamed["state"], "stale")

    def test_verify_saved_preserves_interrupted_attempt_and_next_day_gate(self):
        engine, client = self.engine([KeyboardInterrupt()])
        with self.assertRaises(KeyboardInterrupt):
            c.run_worker(self.config, self.store, engine)
        c.CampaignQuota(t.DailyQuota(self.config.args), self.store, self.config).recover()
        before = dict(self.store.rows()[0])
        quota = self.quota.read_bytes()
        with self.store.conn:
            self.store.conn.execute("UPDATE cards SET state='stale'")
        c.scan(self.config, self.store, verify_saved=True)
        recovered = dict(self.store.rows()[0])
        self.assertEqual(recovered["state"], "retryable")
        for field in ("result", "retry_after", "failures"):
            self.assertEqual(before[field], recovered[field])
        self.assertEqual(quota, self.quota.read_bytes())
        self.assertEqual(self.counts()["uncertain_attempts"], 1)

    def test_windows_idle_sleep_protection_restores_previous_state_on_failure(self):
        with patch.object(c.sys, "platform", "win32"), patch.object(c, "_execution_state", return_value=0x80000000) as state:
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                with c.keep_awake():
                    raise RuntimeError("interrupted")
        self.assertEqual([call.args[0] for call in state.call_args_list], [0x80000001, 0x80000000])

    def test_verify_saved_does_not_bypass_exhausted_retry_limits(self):
        self.run_worker()
        row = self.store.rows()[0]
        quota = self.quota.read_bytes()
        for result in ({"status": "failed", "stop_kind": "service", "error": None, "text": ""},
                       {"status": "paused", "error": "Interrupted request: outcome unknown", "text": ""}):
            with self.subTest(result=result):
                self.config = self.configure(source_identity="filesystem")
                with self.store.conn:
                    self.store.conn.execute("UPDATE cards SET state='stale',result=?,failures=? WHERE id=?",
                                            (json.dumps(result), self.config.retry_days, row["id"]))
                self.config = self.configure(source_identity="metadata")
                c.scan(self.config, self.store, verify_saved=True)
                recovered = self.store.conn.execute("SELECT * FROM cards WHERE id=?", (row["id"],)).fetchone()
                self.assertEqual(recovered["state"], "permanent")
                self.assertEqual(recovered["failures"], self.config.retry_days)
                self.assertEqual(self.quota.read_bytes(), quota)

    def test_windows_idle_sleep_protection_failure_stops_before_work(self):
        with patch.object(c.sys, "platform", "win32"), patch.object(c, "_execution_state", return_value=0):
            with self.assertRaisesRegex(OSError, "idle sleep"):
                with c.keep_awake():
                    self.fail("A worker must not run without the required idle-sleep protection")

    def test_idle_sleep_protection_is_noop_on_other_platforms(self):
        with patch.object(c.sys, "platform", "linux"), patch.object(c, "_execution_state") as state:
            with c.keep_awake():
                pass
        state.assert_not_called()

    def test_scheduled_entrypoint_uses_and_releases_idle_sleep_protection(self):
        with patch.object(c.sys, "platform", "win32"), patch.object(c, "_execution_state", return_value=0x80000000) as state:
            with patch.object(c, "run_worker", side_effect=ValueError("offline startup failure")):
                self.assertEqual(c.main(["--config", str(self.config_path), "run"]), 20)
        self.assertEqual([call.args[0] for call in state.call_args_list], [0x80000001, 0x80000000])

    def test_full_verification_detects_content_change_with_preserved_metadata(self):
        path = self.jpeg / "Test_bird_E01(A).jpg"
        original = path.read_bytes() + b"original1234"
        path.write_bytes(original)
        self.run_worker()
        before = path.stat()
        path.write_bytes(original[:-12] + b"modified1234")
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
        with self.no_image_reads():
            c.scan(self.config, self.store)
        self.assertEqual(self.store.rows()[0]["state"], "completed")
        c.scan(self.config, self.store, verify=True)
        self.assertEqual(self.store.rows()[0]["state"], "stale")
        self.assertEqual(self.counts()["campaign_api_attempts"], 2)
        self.assertEqual(self.store.get("scan_mode"), "full_content")
        self.assertTrue(self.store.get("last_full_verification"))

    def test_prepared_request_and_legacy_content_fingerprints_are_identical(self):
        db = t.load_database(self.csv)
        card = t.discover_cards(self.jpeg, None)[0][0]
        for model in ("gemini-3.5-flash-lite", "gpt-5.6-luna"):
            args = t.parse_args(["--model", model])
            for max_edge in (0, 10):
                args.max_edge = max_edge
                prompt = c.egg_slip_prompt.build_prompt(card, db, True)
                key, contents = t.prepare_card(card, prompt, args)
                identity = dict(card=c.card_data(card, self.config.base_dir),
                    raw_sha256=[c.digest(p.read_bytes()) for p in card.paths], request_key=key,
                    catalogue=[db.by_enum.get(e, []) for e in card.enums])
                legacy = c.digest(c.encode(identity).encode("utf-8"))
                fingerprint, actual_key, actual_contents, actual_prompt = c.prepare(card, db, args, self.config.base_dir)
                self.assertEqual((actual_key, actual_contents, actual_prompt), (key, contents, prompt))
                self.assertEqual(fingerprint, legacy)

    def test_source_change_during_preparation_prevents_api_attempt(self):
        original = t.prepare_image_bytes
        path = self.jpeg / "Test_bird_E01(A).jpg"
        def changed(data, max_edge):
            stat = path.stat()
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
            return original(data, max_edge)
        engine, client = self.engine()
        with patch.object(t, "prepare_image_bytes", side_effect=changed):
            with self.assertRaisesRegex(OSError, "Source changed"):
                c.run_worker(self.config, self.store, engine)
        self.assertEqual(client.calls, [])
        self.assertEqual(self.counts()["campaign_api_attempts"], 0)

    def test_full_verification_reads_each_image_once_without_requests(self):
        read = Path.read_bytes
        paths = []
        def counted(path):
            if path.suffix.lower() == ".jpg":
                paths.append(path.name)
            return read(path)
        with patch.object(Path, "read_bytes", counted):
            self.assertEqual(c.main(["--config", str(self.config_path), "verify"]), 0)
        self.assertEqual(len(paths), 4)
        self.assertEqual(len(set(paths)), 4)
        self.assertEqual(self.counts()["campaign_api_attempts"], 0)

    def test_invalid_image_is_deferred_until_selected_and_spends_no_quota(self):
        (self.jpeg / "Test_bird_E01(A).jpg").write_bytes(b"not a readable jpeg")
        with self.no_image_reads():
            c.scan(self.config, self.store)
        engine, client = self.engine()
        with self.assertRaises(OSError):
            c.run_worker(self.config, self.store, engine)
        self.assertEqual(client.calls, [])
        self.assertEqual(self.counts()["campaign_api_attempts"], 0)

    def test_explicit_refresh_bypasses_old_checkpoint_after_fast_scan(self):
        self.run_worker()
        identifier = self.store.rows()[0]["id"]
        self.assertEqual(c.main(["--config", str(self.config_path), "refresh", "--card", identifier]), 0)
        self.advance()
        _, client = self.run_worker()
        self.assertEqual(len(client.calls), 2)  # Explicit refresh plus remaining uncatalogued card.

    def test_schema_upgrade_preserves_results_and_requires_legacy_verification(self):
        self.run_worker()
        history = self.store.conn.execute("SELECT * FROM history").fetchall()
        results = [r["result"] for r in self.store.rows()]
        with self.store.conn:
            self.store.conn.execute("ALTER TABLE cards DROP COLUMN signature")
        self.store.set("schema", 1)
        before = self.config.db_path.read_bytes()
        readonly = c.Store(self.config.db_path, migrate=False)
        try:
            c.status(self.config, readonly)
            self.assertEqual(readonly.get("schema"), 1)
        finally:
            readonly.close()
        self.assertEqual(before, self.config.db_path.read_bytes())
        self.store.close()
        self.store = c.Store(self.config.db_path)
        self.addCleanup(self.store.close)
        self.assertEqual(self.store.get("schema"), c.SCHEMA)
        self.assertEqual(results, [r["result"] for r in self.store.rows()])
        with self.no_image_reads():
            c.scan(self.config, self.store)
        self.assertTrue(all(r["state"] == "stale" for r in self.store.rows() if r["result"]))
        c.scan(self.config, self.store, verify=True)
        self.assertEqual(self.counts()["completed_cards"], 2)
        self.assertEqual(len(history), self.store.conn.execute("SELECT count(*) FROM history").fetchone()[0])
        self.assertEqual(self.counts()["campaign_api_attempts"], 2)

    def test_failed_schema_migration_rolls_back_column_and_version_together(self):
        with self.store.conn:
            self.store.conn.execute("ALTER TABLE cards DROP COLUMN signature")
        self.store.set("schema", 1)
        connect = c.sqlite3.connect
        def fail_version_write(*args, **kwargs):
            conn = connect(*args, **kwargs)
            conn.set_authorizer(lambda action, table, *unused: c.sqlite3.SQLITE_DENY
                if action == c.sqlite3.SQLITE_UPDATE and table == "meta" else c.sqlite3.SQLITE_OK)
            return conn
        with patch.object(c.sqlite3, "connect", side_effect=fail_version_write):
            with self.assertRaises(c.sqlite3.DatabaseError):
                c.Store(self.config.db_path)
        self.assertEqual(self.store.get("schema"), 1)
        columns = [row[1] for row in self.store.conn.execute("PRAGMA table_info(cards)")]
        self.assertNotIn("signature", columns)

    def add_unavailable_species(self):
        with self.csv.open("a", encoding="utf-8") as out:
            out.write("E10,Test absent,Birds,Person\nE10,Test absent,Birds,Person\n")
        (self.family / "Test_absent").mkdir()

    def acknowledge_unavailable_species(self):
        self.config = self.configure(skip_missing_species={"Test_absent": "Collection staff confirmed no scans available."})

    def test_unacknowledged_missing_scan_directory_still_blocks_campaign(self):
        self.add_unavailable_species()
        with self.assertRaisesRegex(ValueError, "Discovery requires attention"):
            self.run_worker()
        self.assertEqual(self.counts()["campaign_api_attempts"], 0)

    def test_acknowledged_missing_species_allows_available_cards_and_is_reported(self):
        self.add_unavailable_species()
        self.acknowledge_unavailable_species()
        with self.no_image_reads():
            c.scan(self.config, self.store)
        status = self.counts()
        self.assertEqual(status["campaign_status"], "ready")
        self.assertEqual(status["discovery_issues"], [])
        self.assertEqual(status["total_physical_cards"], 3)
        self.assertEqual(status["skipped_missing_species"][0]["species"], "Test_absent")
        self.assertEqual(status["skipped_species_catalogue_rows"], 2)
        self.assertEqual(status["missing_source_catalogue_entries"], 1)
        self.config.args.rpd = 500
        code, client = self.run_worker()
        self.assertEqual(code, 0)
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(self.counts()["completed_cards"], 3)
        report = Path(self.counts()["outputs"][-1]["destination"]).read_text(encoding="utf-8")
        self.assertNotIn("CM10", report)
        self.assertIn("CM9 (MISSING)", report)
        self.assertFalse((self.family / "Test_absent" / "JPEG").exists())

    def test_acknowledgement_does_not_hide_ambiguous_directories(self):
        genus = self.family / "Test" / "Test_bird" / "JPEG"
        genus.mkdir(parents=True)
        self.config = self.configure(skip_missing_species={"Test_bird": "No scans expected."})
        with self.assertRaisesRegex(ValueError, "found 2"):
            self.run_worker()
        self.assertEqual(self.counts()["skipped_missing_species"], [])
        self.assertEqual(self.counts()["campaign_api_attempts"], 0)

    def test_acknowledgement_does_not_hide_invalid_existing_scans(self):
        self.config = self.configure(skip_missing_species={"Test_bird": "No scans expected."})
        self.image("unrecognized.jpg")
        with self.assertRaisesRegex(ValueError, "Unrecognized JPEG filename"):
            self.run_worker()
        self.assertEqual(self.counts()["skipped_missing_species"], [])

    def test_acknowledged_species_is_included_when_scans_become_available(self):
        self.add_unavailable_species()
        self.acknowledge_unavailable_species()
        c.scan(self.config, self.store)
        folder = self.family / "Test_absent" / "JPEG"
        folder.mkdir()
        with Image.new("RGB", (20, 20)) as image:
            image.save(folder / "Test_absent_E10.jpg")
        c.scan(self.config, self.store)
        self.assertEqual(self.counts()["skipped_missing_species"], [])
        self.assertEqual(self.counts()["total_physical_cards"], 4)

    def test_acknowledgement_does_not_hide_storage_access_errors(self):
        self.add_unavailable_species()
        self.acknowledge_unavailable_species()
        resolve = t.resolve_folders
        def denied(root, db, species):
            if species == "Test_absent":
                raise PermissionError("Source folder is inaccessible")
            return resolve(root, db, species)
        with patch.object(t, "resolve_folders", side_effect=denied):
            with self.assertRaisesRegex(ValueError, "inaccessible"):
                self.run_worker()
        self.assertEqual(self.counts()["skipped_missing_species"], [])

    def test_acknowledgement_does_not_hide_missing_family_or_drive(self):
        self.add_unavailable_species()
        self.acknowledge_unavailable_species()
        self.family.rename(self.family.with_name("Birds_offline"))
        with self.assertRaisesRegex(ValueError, "Family directory not found"):
            self.run_worker()
        self.config.base_dir.rename(self.config.base_dir.with_name("Family_offline"))
        with self.assertRaises(OSError):
            self.run_worker()

    def test_unknown_missing_species_remains_an_error_with_other_acknowledgements(self):
        c.scan(self.config, self.store)
        self.add_unavailable_species()
        self.acknowledge_unavailable_species()
        with self.csv.open("a", encoding="utf-8") as out:
            out.write("E11,Other absent,Birds,Person\n")
        with self.assertRaisesRegex(ValueError, "Other_absent"):
            self.run_worker()
        self.assertEqual(self.counts()["total_physical_cards"], 3)
        self.assertEqual(len(self.counts()["skipped_missing_species"]), 1)

    def test_missing_species_configuration_requires_exact_names_and_reasons(self):
        for value in (["Test_absent"], {"Test_absent": ""}, {"Test absent": "No scans"}, {"*": "Skip all"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.configure(skip_missing_species=value)

    def test_successful_scan_clears_previous_discovery_failure(self):
        self.add_unavailable_species()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(c.main(["--config", str(self.config_path), "scan"]), 20)
        self.assertEqual(self.counts()["campaign_status"], "attention")
        self.acknowledge_unavailable_species()
        self.assertEqual(c.main(["--config", str(self.config_path), "scan"]), 0)
        self.assertEqual(self.counts()["campaign_status"], "ready")
        self.assertIsNone(self.counts()["last_error"])


if __name__ == "__main__":
    unittest.main()
