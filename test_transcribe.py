"""Offline regression tests. Run: python -m unittest -v test_transcribe.py

No real API calls. The optional SDK test uses httpx.MockTransport and a dummy key.
Set EGG_SLIP_SAMPLE_DIR to the supplied JPG directory to include the real scans.
"""

import contextlib
import asyncio
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from PIL import Image
import transcribe as t


def response(text, finish="STOP", thought=None):
    parts = [NS(text=text, thought=False)]
    if thought:
        parts.insert(0, NS(text=thought, thought=True))
    return NS(candidates=[NS(finish_reason=finish, content=NS(parts=parts))],
              prompt_feedback=None, usage_metadata=NS(total_token_count=100), model_version="offline-fixture")


def transcript(sections=()):
    return "Species: TEST FIXTURE ONLY\nANNOTATIONS:\n" + "".join(
        f"{section}: TEST FIXTURE BACK\n" for section in sections if section != "FRONT"
    ) + "TRANSCRIPTION NOTES:"


class Clock:
    def __init__(self):
        self.now = 0.0
        self.delays = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        if seconds < 0:
            raise AssertionError("Negative sleep")
        self.delays.append(seconds)
        self.now += seconds


class FakeAPIError(Exception):
    def __init__(self, code, details=None, headers=None):
        super().__init__(f"HTTP {code}: offline fixture")
        self.code = code
        self.details = details or {}
        self.response = NS(headers=headers or {})


class FakeClient:
    def __init__(self, outcomes=(), clock=None):
        self.models = self
        self.outcomes = list(outcomes)
        self.calls = []
        self.starts = []
        self.clock = clock
        self.closed = False

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.clock:
            self.starts.append(self.clock.time())
        if self.outcomes:
            outcome = self.outcomes.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
            return outcome
        labels = [part["text"].split("SECTION: ")[-1] for part in kwargs["contents"][0]["parts"]
                  if "text" in part and "\nSECTION: " in part["text"]]
        return response(transcript(labels))

    def close(self):
        self.closed = True


class DatasetTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.family = self.root / "Family" / "Accipitridae"
        self.folder = self.family / "Accipiter_gentilis" / "JPEG"
        self.folder.mkdir(parents=True)
        self.csv = self.root / "master.csv"
        self.write_csv(["E4268", "E4927", "E186", "E187", "E001"])
        self.card_image("Accipiter_gentilis_E4268(B).jpg", "blue")
        self.card_image("Accipiter_gentilis_E4268(A).jpg", "red")
        self.card_image("Accipiter_gentilis_E4927.jpg", "green")
        self.args = t.parse_args(["Accipiter_gentilis", "--csv", str(self.csv), "--base-dir", str(self.root / "Family")])
        self.quiet = contextlib.redirect_stdout(io.StringIO())
        self.quiet.__enter__()
        self.addCleanup(self.quiet.__exit__, None, None, None)

    def write_csv(self, enums, extra=None):
        headers = ["catalogNumber", "Scientific Name", "Family", "Collector", "locality"]
        with self.csv.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers)
            writer.writeheader()
            for enum in enums:
                writer.writerow({"catalogNumber": enum, "Scientific Name": "Accipiter gentilis",
                                 "Family": "Accipitridae", "Collector": "Reference Collector",
                                 "locality": "Reference Locality"})
            if extra:
                writer.writerow(extra)

    def card_image(self, name, color="red"):
        path = self.folder / name
        with Image.new("RGB", (64, 40), color) as image:
            image.save(path, "JPEG")
        return path

    def db(self):
        return t.load_database(self.csv)

    def cards(self, allowed=None):
        return t.discover_cards(self.folder, allowed)[0]

    def engine(self, outcomes=()):
        clock = Clock()
        client = FakeClient(outcomes, clock)
        return t.Transcriber(self.args, client=client, clock=clock.time, sleep=clock.sleep), client, clock

    def snapshot(self):
        return {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.root.rglob("*") if path.is_file()}

    def test_front_back_order_is_deterministic(self):
        card = self.cards({"E4268"})[0]
        self.assertEqual([path.name for path in card.paths],
                         ["Accipiter_gentilis_E4268(A).jpg", "Accipiter_gentilis_E4268(B).jpg"])
        self.assertEqual(card.sections, ("FRONT", "BACK OF SLIP"))

    def test_multi_enum_can_be_selected_by_second_number_once(self):
        self.card_image("Accipiter_gentilis_E186_E187.jpg")
        cards, issues, missing = t.discover_cards(self.folder, {"E187", "E186"})
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].enums, ("E186", "E187"))
        self.assertEqual(issues, [])
        self.assertEqual(missing, set())
        self.assertEqual(len(self.cards({"E187"})), 1)
        self.assertEqual(len(self.cards({"E18"})), 0)

    def test_leading_zero_catalogue_number_is_not_rewritten(self):
        self.card_image("Accipiter_gentilis_E001.jpg")
        card = self.cards({"E001"})[0]
        self.assertEqual(card.enums, ("E001",))
        self.assertIn('"catalogNumber": "E001"', t.build_prompt(card, self.db(), True))

    def test_numeric_sides_have_numeric_order_and_gap_warning(self):
        for suffix in (10, 2, 1):
            self.card_image(f"Accipiter_gentilis_E186({suffix}).jpg")
        card = self.cards({"E186"})[0]
        self.assertEqual([path.stem.rsplit("(", 1)[-1] for path in card.paths], ["1)", "2)", "10)"])
        self.assertEqual(card.sections, ("FRONT", "BACK OF SLIP", "BACK OF SLIP 2"))
        self.assertTrue(card.warnings)

    def test_ambiguous_duplicate_front_is_not_submitted(self):
        self.card_image("Accipiter_gentilis_E4268.jpg")
        cards, issues, missing = t.discover_cards(self.folder, {"E4268"})
        self.assertEqual(cards, [])
        self.assertIn("duplicate side", issues[0])
        self.assertEqual(missing, {"E4268"})

    def test_back_only_is_not_labelled_front(self):
        self.card_image("Accipiter_gentilis_E186(B).jpg")
        card = self.cards({"E186"})[0]
        self.assertEqual(card.sections, ("BACK OF SLIP",))
        self.assertIn("Front image is missing", card.warnings[0])

    def test_case_insensitive_jpeg_and_alternate_side_suffixes(self):
        self.card_image("Accipiter_gentilis_E186-B-.JPEG")
        self.card_image("Accipiter_gentilis_E186-A-.JPG")
        self.assertEqual(self.cards({"E186"})[0].sections, ("FRONT", "BACK OF SLIP"))

    def test_bad_filename_is_reported(self):
        self.card_image("Accipiter_gentilis_E187_typo.jpg")
        _, issues, missing = t.discover_cards(self.folder, {"E187"})
        self.assertIn("Unrecognized JPEG filename", issues[0])
        self.assertEqual(missing, {"E187"})

    def test_csv_row_range_uses_sheet_row_numbers(self):
        targets, console = t.select_targets(self.db(), "2-3")
        self.assertEqual(targets, {"Accipiter_gentilis": {"E4268", "E4927"}})
        self.assertFalse(console)

    def test_invalid_targets_do_not_silently_save_batch(self):
        db = self.db()
        for target in ("", "5-2", "1-3", "Accipiter_gentilis*", "../Accipiter_gentilis", "E999"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                t.select_targets(db, target)

    def test_missing_csv_header_fails_before_transcription(self):
        self.csv.write_text("catalogNumber,Family\nE1,Accipitridae\n")
        with self.assertRaisesRegex(ValueError, "Scientific Name"):
            self.db()

    def test_duplicate_records_are_retained_and_conflicts_rejected(self):
        self.write_csv(["E4268"], {"catalogNumber": "E4268", "Scientific Name": "Buteo jamaicensis", "Family": "Accipitridae"})
        db = self.db()
        self.assertEqual(len(db.by_enum["E4268"]), 2)
        with self.assertRaisesRegex(ValueError, "Conflicting species"):
            t.select_targets(db, "E4268")

    def test_nested_genus_layout_and_case_insensitive_paths(self):
        target = self.family / "Accipiter"
        target.mkdir()
        (self.family / "Accipiter_gentilis").rename(target / "accipiter_gentilis")
        family, folder = t.resolve_folders(self.root / "Family", self.db(), "Accipiter_gentilis")
        self.assertEqual(family, self.family)
        self.assertEqual(folder, target / "accipiter_gentilis" / "JPEG")

    def test_two_valid_layouts_are_reported_as_ambiguous(self):
        (self.family / "Accipiter" / "Accipiter_gentilis" / "JPEG").mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, "found 2"):
            t.resolve_folders(self.root / "Family", self.db(), "Accipiter_gentilis")

    def test_prompt_can_omit_catalogue_hints(self):
        card = self.cards({"E4268"})[0]
        self.assertIn("Reference Collector", t.build_prompt(card, self.db(), True))
        self.assertNotIn("Reference Collector", t.build_prompt(card, self.db(), False))
        self.assertNotIn("GROUND TRUTH", t.build_prompt(card, self.db(), True))

    def test_original_jpeg_bytes_preserved_without_resize(self):
        path = self.cards()[0].paths[0]
        self.assertEqual(t.prepare_image(path, 0), path.read_bytes())

    def test_exif_orientation_and_optional_resize(self):
        path = self.folder / "orientation.jpg"
        with Image.new("RGB", (80, 40), "red") as image:
            exif = image.getexif()
            exif[274] = 6
            image.save(path, "JPEG", exif=exif)
        original = path.read_bytes()
        with Image.open(io.BytesIO(t.prepare_image(path, 0))) as image:
            self.assertEqual(image.size, (40, 80))
        with Image.open(io.BytesIO(t.prepare_image(path, 20))) as image:
            self.assertEqual(image.size, (10, 20))
        self.assertEqual(path.read_bytes(), original)

    def test_fingerprint_changes_for_prompt_model_settings_or_pixels(self):
        card = self.cards({"E4268"})[0]
        prompt = t.build_prompt(card, self.db(), True)
        key, _ = t.prepare_card(card, prompt, self.args)
        self.assertEqual(key, t.prepare_card(card, prompt, self.args)[0])
        self.assertNotEqual(key, t.prepare_card(card, prompt + "new", self.args)[0])
        self.args.model = "test-model"
        self.assertNotEqual(key, t.prepare_card(card, prompt, self.args)[0])
        self.args.model = t.MODEL
        self.args.temperature = 1.0
        self.assertNotEqual(key, t.prepare_card(card, prompt, self.args)[0])
        self.args.temperature = t.TEMPERATURE
        self.card_image(card.paths[0].name, "black")
        self.assertNotEqual(key, t.prepare_card(card, prompt, self.args)[0])

    def test_inline_payload_budget_is_checked_before_api(self):
        card = self.cards()[0]
        with patch.object(t, "MAX_INLINE_REQUEST_BYTES", 10), self.assertRaisesRegex(ValueError, "inline request"):
            t.prepare_card(card, "test", self.args)

    def test_cutoff_blocked_empty_and_missing_back_are_not_success(self):
        card = self.cards({"E4268"})[0]
        bad = [response(transcript(card.sections), "MAX_TOKENS"), response(""),
               response(transcript()), response("ANNOTATIONS:\nBACK OF SLIP:\nTRANSCRIPTION NOTES:"),
               response(transcript(card.sections), "SAFETY")]
        for item in bad:
            with self.subTest(item=item), self.assertRaises(t.ResponseProblem):
                t.validate_response(item, card)

    def test_thoughts_excluded_and_uncertainty_flagged(self):
        card = self.cards({"E4268"})[0]
        text = transcript(card.sections).replace("TEST FIXTURE ONLY", "[uncertain]")
        actual, warnings, usage = t.validate_response(response(text, thought="SECRET TEST THOUGHT"), card)
        self.assertNotIn("SECRET TEST THOUGHT", actual)
        self.assertIn("1 bracketed", warnings[0])
        self.assertEqual(usage["total_token_count"], 100)

    def test_server_retry_hint_and_every_attempt_are_paced(self):
        error = FakeAPIError(429, {"error": {"details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "12.5s"}]}})
        engine, client, clock = self.engine([error])
        card = self.cards()[0]
        _, contents = t.prepare_card(card, "test", self.args)
        result = engine.transcribe(card, contents)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(client.calls), 2)
        self.assertGreaterEqual(client.starts[1] - client.starts[0], 12.5)
        self.assertEqual(t.retry_delay(error), 12.5)

    def test_rate_limiter_paces_fast_successes_without_post_call_delay(self):
        engine, client, clock = self.engine()
        for card in self.cards():
            _, contents = t.prepare_card(card, "test", self.args)
            engine.transcribe(card, contents)
        self.assertEqual(client.starts, [0, 4.1])
        self.assertEqual(clock.now, 4.1)

    def test_401_is_fatal_without_retries(self):
        engine, client, _ = self.engine([FakeAPIError(401)])
        card = self.cards()[0]
        result = engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
        self.assertTrue(result["fatal"])
        self.assertEqual(len(client.calls), 1)

    def test_retry_limit_has_no_final_unneeded_backoff(self):
        self.args.attempts = 2
        engine, client, clock = self.engine([FakeAPIError(503), FakeAPIError(503)])
        card = self.cards()[0]
        result = engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(len(clock.delays), 1)
        self.assertTrue(result["fatal"])

    def test_empty_response_gets_one_retry_and_incomplete_result_stays_failed(self):
        engine, client, _ = self.engine([response(""), response("partial")])
        card = self.cards()[0]
        result = engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["text"], "partial")
        self.assertEqual(len(client.calls), 2)

    def test_dry_run_is_read_only_and_makes_no_requests(self):
        before = self.snapshot()
        self.args.dry_run = True
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(client.calls, [])
        self.assertEqual(self.snapshot(), before)

    def test_successful_run_reuses_results_and_changed_image_refreshes_one_card(self):
        engine, client, _ = self.engine()
        source_before = {str(path): path.read_bytes() for path in self.folder.iterdir()}
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(len(client.calls), 2)
        engine2, client2, _ = self.engine()
        self.assertEqual(t.run(self.args, engine2), 0)
        self.assertEqual(len(client2.calls), 0)
        for name, data in source_before.items():
            self.assertEqual(Path(name).read_bytes(), data)
        self.card_image("Accipiter_gentilis_E4927.jpg", "purple")
        engine3, client3, _ = self.engine()
        self.assertEqual(t.run(self.args, engine3), 0)
        self.assertEqual(len(client3.calls), 1)
        self.assertEqual(len(list(self.family.glob("*_transcriptions_*.txt"))), 3)

    def test_force_refreshes_completed_cards(self):
        t.run(self.args, self.engine()[0])
        self.args.force = True
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(len(client.calls), 2)

    def test_console_star_is_fresh_and_does_not_write_even_when_cache_exists(self):
        t.run(self.args, self.engine()[0])
        before = self.snapshot()
        self.args.target = "E4268*"
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(self.snapshot(), before)

    def test_failed_result_is_retried_on_next_run(self):
        self.args.target = "E4927"
        engine, _, _ = self.engine([response("partial", "MAX_TOKENS")])
        self.assertEqual(t.run(self.args, engine), 1)
        engine2, client2, _ = self.engine()
        self.assertEqual(t.run(self.args, engine2), 0)
        self.assertEqual(len(client2.calls), 1)

    def test_authentication_error_stops_the_batch_after_first_card(self):
        engine, client, _ = self.engine([FakeAPIError(403)])
        self.assertEqual(t.run(self.args, engine), 1)
        self.assertEqual(len(client.calls), 1)
        journal = next(self.family.glob("*_cache.jsonl"))
        self.assertEqual(json.loads(journal.read_text())["status"], "failed")

    def test_bad_jpeg_does_not_reach_api(self):
        self.args.target = "E4927"
        (self.folder / "Accipiter_gentilis_E4927.jpg").write_bytes(b"not a jpeg")
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 1)
        self.assertEqual(client.calls, [])

    def test_output_failure_after_checkpoint_does_not_repeat_paid_request(self):
        self.args.target = "E4927"
        engine, client, _ = self.engine()
        with patch.object(t, "durable_write", side_effect=OSError("simulated disk failure")), self.assertRaises(OSError):
            t.run(self.args, engine)
        self.assertEqual(len(client.calls), 1)
        engine2, client2, _ = self.engine()
        self.assertEqual(t.run(self.args, engine2), 0)
        self.assertEqual(client2.calls, [])

    def test_journal_recovers_from_partial_line_and_never_reuses_failure(self):
        path = self.root / "journal.jsonl"
        good = {"key": "good", "cache_version": t.CACHE_VERSION, "status": "ok", "text": "saved text", "warnings": []}
        path.write_bytes((json.dumps(good) + '\n{"key":"broken"').encode())
        with t.Journal(path) as journal:
            self.assertEqual(journal.reusable("good"), good)
            journal.append({**good, "key": "next"})
        with t.Journal(path) as journal:
            self.assertIsNotNone(journal.reusable("good"))
            self.assertIsNotNone(journal.reusable("next"))
            journal.append({**good, "status": "failed"})
            self.assertIsNone(journal.reusable("good"))

    def test_second_species_lock_is_rejected(self):
        if os.name == "nt":
            self.skipTest("Windows lock must be checked on the deployment machine")
        path = self.root / "lock"
        with t.species_lock(path):
            with self.assertRaises(RuntimeError):
                with t.species_lock(path):
                    pass
        with t.species_lock(path):
            pass

    def test_actual_sdk_serializes_images_and_parses_errors_offline(self):
        try:
            from google import genai
            from google.genai import errors
            import httpx
        except ImportError:
            self.skipTest("Install google-genai for the SDK transport test")
        captured = []

        def handler(request):
            payload = json.loads(request.content)
            captured.append(payload)
            if len(captured) == 1:
                return httpx.Response(429, json={"error": {"code": 429, "message": "offline fixture", "status": "RESOURCE_EXHAUSTED",
                                                          "details": [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "7s"}]}})
            return httpx.Response(200, json={"candidates": [{"finishReason": "STOP", "content": {"role": "model", "parts": [
                {"text": transcript(("FRONT", "BACK OF SLIP"))}]}}], "usageMetadata": {"totalTokenCount": 50}})

        clock = Clock()
        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        async_http_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.addCleanup(lambda: asyncio.run(async_http_client.aclose()))
        client = genai.Client(api_key="offline-dummy-key", http_options={
            "httpx_client": http_client, "httpx_async_client": async_http_client,
            "retry_options": {"attempts": 1}, "timeout": 180000})
        self.addCleanup(client.close)
        engine = t.Transcriber(self.args, client=client, clock=clock.time, sleep=clock.sleep)
        card = self.cards({"E4268"})[0]
        _, contents = t.prepare_card(card, t.build_prompt(card, self.db(), True), self.args)
        result = engine.transcribe(card, contents)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(captured), 2)
        parts = captured[-1]["contents"][0]["parts"]
        self.assertEqual(len([part for part in parts if "inlineData" in part]), 2)
        self.assertIn("SECTION: FRONT", parts[1]["text"])
        self.assertIn("SECTION: BACK OF SLIP", parts[3]["text"])
        self.assertEqual(captured[-1]["generationConfig"]["temperature"], 0.1)
        self.assertGreaterEqual(clock.now, 7)
        self.assertEqual(t.retry_delay(errors.APIError(429, {"error": {"details": [{"retryDelay": "9s"}]}})), 9)

    def test_supplied_scans_preserve_pixels_and_pair_correctly(self):
        location = os.environ.get("EGG_SLIP_SAMPLE_DIR")
        if not location:
            self.skipTest("Set EGG_SLIP_SAMPLE_DIR to run supplied-scan verification")
        paths = sorted(Path(location).glob("*.jpg"))
        self.assertEqual(len(paths), 3)
        for path in paths:
            name = path.name
            if name.startswith(("02-", "03-", "04-")):
                name = name[3:]
            name = name.replace("-A-", "(A)").replace("-B-", "(B)")
            (self.folder / name).write_bytes(path.read_bytes())
        cards = self.cards({"E4927", "E4268"})
        self.assertEqual(len(cards), 2)
        self.assertEqual(sum(len(card.paths) for card in cards), 3)
        for card in cards:
            for path in card.paths:
                self.assertEqual(t.prepare_image(path, 0), path.read_bytes())
            key, contents = t.prepare_card(card, t.build_prompt(card, self.db(), True), self.args)
            self.assertEqual(len(key), 64)
            self.assertEqual(len(contents[0]["parts"]), 1 + 2 * len(card.paths))


if __name__ == "__main__":
    unittest.main(verbosity=2)
