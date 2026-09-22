"""Offline regression tests. Run: python -m unittest -v test_transcribe.py

No real API calls. The optional SDK test uses httpx.MockTransport and a dummy key.
Set EGG_SLIP_SAMPLE_DIR to the supplied JPG directory to include the real scans.
"""

import contextlib
import asyncio
import csv
from datetime import datetime, timezone
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


PASTED_E15 = '''==================================================
ID: Accipiter_Cooperii_E15
============================

COLLECTION OF CARNEGIE MUSEUM, PITTSBURGH, PENNA.
Name: Accipiter cooperi
Locality: -
Date: -
Incubation: - Identification: -
Nest: -
One egg badly chipped and cracked
" " cracked
Fragment sent to R. Kahring, Inst. für Paläontologie, Berlin
9 May 1994
Set No.: - Collector: Frederic S. Webster
A.O.U. No.: 333
Set Mark: 333a FSW
No. of Eggs: 3
ANNOTATIONS:
(top left) 15
(bottom right) form A291 [3-14-32-1m]
TRANSCRIPTION NOTES:'''


class APIKeyTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.scripts = self.root / "Egg Slip Scanning" / "scripts"
        self.scripts.mkdir(parents=True)
        self.other = self.root / "Program Files" / "Microsoft VS Code"
        self.other.mkdir(parents=True)
        self.args = t.parse_args(["E15", "--csv", str(self.scripts.parent / "master.csv"),
                                  "--base-dir", str(self.scripts.parent / "Family")])
        contexts = contextlib.ExitStack()
        self.addCleanup(contexts.close)
        contexts.enter_context(patch.dict(os.environ, {}, clear=True))
        contexts.enter_context(patch.object(t, "__file__", str(self.scripts / "transcribe.py")))
        contexts.enter_context(patch.object(Path, "cwd", return_value=self.other))
        self.output = contexts.enter_context(contextlib.redirect_stdout(io.StringIO()))

    def test_dotenv_beside_script_from_unrelated_vscode_directory(self):
        (self.scripts / ".env").write_text("GEMINI_API_KEY=offline-script-token\n", encoding="utf-8")
        self.assertEqual(t.load_api_key(self.args), "offline-script-token")
        self.assertIn(str(self.scripts / ".env"), self.output.getvalue())
        self.assertNotIn("offline-script-token", self.output.getvalue())

    def test_dotenv_in_project_root(self):
        (self.scripts.parent / ".env").write_text("GOOGLE_API_KEY=offline-root-token\n", encoding="utf-8")
        self.assertEqual(t.load_api_key(self.args), "offline-root-token")

    def test_dotenv_precedes_stale_environment_key(self):
        (self.scripts / ".env").write_text("GEMINI_API_KEY=offline-file-token", encoding="utf-8")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-stale-token"}):
            self.assertEqual(t.load_api_key(self.args), "offline-file-token")

    def test_environment_fallback_and_blank_gemini_uses_google(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "  ", "GOOGLE_API_KEY": " offline-process-token "}):
            self.assertEqual(t.load_api_key(self.args), "offline-process-token")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "offline-gemini-token", "GOOGLE_API_KEY": "offline-google-token"}):
            self.assertEqual(t.load_api_key(self.args), "offline-gemini-token")

    def test_quotes_comments_export_bom_and_windows_encodings(self):
        path = self.scripts / ".env"
        for encoding in ("utf-8", "utf-8-sig", "utf-16"):
            for value in ('"offline-dummy-token" # comment', "'offline-dummy-token'", "offline-dummy-token # comment"):
                with self.subTest(encoding=encoding, value=value):
                    path.write_text("# setup\nIGNORED=anything\nexport GEMINI_API_KEY = " + value + "\n", encoding=encoding)
                    self.assertEqual(t.load_api_key(self.args), "offline-dummy-token")
        self.assertNotIn("offline-dummy-token", self.output.getvalue())

    def test_script_dotenv_precedes_project_and_current_directory(self):
        for parent, token in ((self.other, "offline-cwd"), (self.scripts.parent, "offline-root"),
                              (self.scripts, "offline-script")):
            (parent / ".env").write_text("GEMINI_API_KEY=" + token, encoding="utf-8")
        self.assertEqual(t.load_api_key(self.args), "offline-script")

    def test_explicit_dotenv_and_missing_path(self):
        explicit = self.root / "config.env"
        explicit.write_text("GEMINI_API_KEY=offline-explicit-token", encoding="utf-8")
        (self.scripts / ".env").write_text("GEMINI_API_KEY=offline-default-token", encoding="utf-8")
        self.args.env_file = str(explicit)
        self.assertEqual(t.load_api_key(self.args), "offline-explicit-token")
        explicit.unlink()
        with self.assertRaisesRegex(ValueError, "--env-file"):
            t.load_api_key(self.args)

    def test_malformed_quote_error_never_contains_key(self):
        (self.scripts / ".env").write_text('GEMINI_API_KEY="offline-private-token', encoding="utf-8")
        with self.assertRaises(ValueError) as caught:
            t.load_api_key(self.args)
        self.assertNotIn("offline-private-token", str(caught.exception) + self.output.getvalue())

    def test_missing_or_empty_key_gives_setup_hint(self):
        self.assertEqual(t.load_api_key(self.args), "")
        self.assertIn(".env.txt", self.output.getvalue())
        (self.scripts / ".env").write_text('GEMINI_API_KEY=""\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no usable API key"):
            t.load_api_key(self.args)

    def test_api_key_assignment_and_bare_google_key(self):
        path = self.scripts / ".env"
        for content, expected in (("API_KEY=offline-assignment", "offline-assignment"),
                                  ("AQ.offline-dummy-token-for-testing", "AQ.offline-dummy-token-for-testing")):
            with self.subTest(form=content.split("=", 1)[0]):
                path.write_text(content, encoding="utf-8")
                self.assertEqual(t.load_api_key(self.args), expected)
                self.assertNotIn(expected, self.output.getvalue())

    def test_windows_hidden_txt_extension_has_specific_error(self):
        (self.scripts / ".env.txt").write_text("GEMINI_API_KEY=offline-hidden-extension", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, r"Rename the file to \.env") as caught:
            t.load_api_key(self.args)
        self.assertNotIn("offline-hidden-extension", str(caught.exception))

    def test_check_config_shows_version_and_script_without_reading_csv(self):
        (self.scripts / ".env").write_text("GEMINI_API_KEY=offline-config-token", encoding="utf-8")
        with patch.object(t, "load_database") as database, patch.object(t, "Transcriber") as transcriber:
            self.assertEqual(t.main(["--check-config"]), 0)
            database.assert_not_called()
            transcriber.assert_not_called()
        output = self.output.getvalue()
        self.assertIn(t.SCRIPT_VERSION, output)
        self.assertIn(str(self.scripts / "transcribe.py"), output)
        self.assertIn("No API request was sent", output)
        self.assertNotIn("offline-config-token", output)

    def test_missing_key_stops_without_manual_prompt(self):
        try:
            from google import genai
        except ImportError:
            self.skipTest("Install google-genai for client initialization verification")
        with patch.object(genai, "Client") as constructor, patch.object(t.getpass, "getpass") as prompt:
            with self.assertRaisesRegex(RuntimeError, "No API key loaded"):
                t.Transcriber(self.args).ensure_client()
            constructor.assert_not_called()
            prompt.assert_not_called()

    def test_unusable_dotenv_is_fatal_instead_of_repeating_for_every_card(self):
        try:
            from google import genai
        except ImportError:
            self.skipTest("Install google-genai for client initialization verification")
        (self.scripts / ".env").write_text("WRONG_NAME=offline-invalid-format", encoding="utf-8")
        with patch.object(genai, "Client") as constructor, patch.object(t.getpass, "getpass") as prompt:
            with self.assertRaisesRegex(RuntimeError, "API key setup error"):
                t.Transcriber(self.args).ensure_client()
            constructor.assert_not_called()
            prompt.assert_not_called()

    def test_ensure_client_uses_dotenv_without_prompting(self):
        try:
            from google import genai
        except ImportError:
            self.skipTest("Install google-genai for client initialization verification")
        (self.scripts / ".env").write_text("GEMINI_API_KEY=offline-init-token", encoding="utf-8")
        with patch.object(genai, "Client") as constructor, patch.object(t.getpass, "getpass") as prompt:
            engine = t.Transcriber(self.args)
            engine.ensure_client()
            engine.ensure_client()
            constructor.assert_called_once()
            self.assertEqual(constructor.call_args.kwargs["api_key"], "offline-init-token")
            self.assertFalse(constructor.call_args.kwargs["vertexai"])
            prompt.assert_not_called()

    def test_actual_sdk_uses_developer_endpoint_and_key_header_despite_environment(self):
        try:
            from google import genai
            import httpx
        except ImportError:
            self.skipTest("Install google-genai for the SDK transport test")
        (self.scripts / ".env").write_text("GEMINI_API_KEY=offline-header-token", encoding="utf-8")
        captured = []

        def handler(request):
            captured.append(request)
            return httpx.Response(200, json={"name": "models/" + t.MODEL})

        sync_http = httpx.Client(transport=httpx.MockTransport(handler))
        async_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        self.addCleanup(sync_http.close)
        self.addCleanup(lambda: asyncio.run(async_http.aclose()))
        real_client = genai.Client

        def factory(**kwargs):
            kwargs["http_options"].update(httpx_client=sync_http, httpx_async_client=async_http)
            return real_client(**kwargs)

        with patch.dict(os.environ, {"GOOGLE_GENAI_USE_VERTEXAI": "true", "GOOGLE_GENAI_USE_ENTERPRISE": "true",
                                     "GOOGLE_GEMINI_BASE_URL": "https://wrong.invalid"}), \
                patch.object(genai, "Client", side_effect=factory):
            engine = t.Transcriber(self.args)
            self.addCleanup(engine.close)
            engine.ensure_client()
            engine.client.models.get(model=t.MODEL)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].url.host, "generativelanguage.googleapis.com")
        self.assertEqual(captured[0].headers["x-goog-api-key"], "offline-header-token")
        self.assertNotIn("authorization", captured[0].headers)

    def test_provider_selects_only_its_own_key_from_shared_dotenv(self):
        (self.scripts / ".env").write_text(
            "GEMINI_API_KEY=offline-google\nAPI_KEY=offline-legacy\nOPENAI_API_KEY=offline-openai\n")
        self.assertEqual(t.load_api_key(self.args), "offline-google")
        self.args.provider = "openai"
        self.assertEqual(t.load_api_key(self.args), "offline-openai")
        self.assertNotIn("offline-openai", self.output.getvalue())

    def test_openai_never_uses_generic_or_google_key(self):
        (self.scripts / ".env").write_text("GEMINI_API_KEY=offline-google\nAPI_KEY=offline-legacy\n")
        self.args.provider = "openai"
        self.assertEqual(t.load_api_key(self.args), "")
        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-openai-env"}):
            self.assertEqual(t.load_api_key(self.args), "offline-openai-env")


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


def openai_response(text, status="completed", reason=None):
    return NS(status=status, model="offline-openai-fixture", incomplete_details=NS(reason=reason),
              output=[NS(type="reasoning", summary=[NS(text="private thought fixture")]),
                      NS(type="message", content=[NS(type="output_text", text=text)])],
              usage=NS(input_tokens=100, output_tokens=60, total_tokens=160,
                       output_tokens_details=NS(reasoning_tokens=20)))


class FakeOpenAIClient:
    def __init__(self, outcomes):
        self.responses = self
        self.outcomes = list(outcomes)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    def close(self):
        pass


class ProfileAndQuotaTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.args = t.parse_args(["--quota-file", str(self.root / "usage.json")])

    def test_one_selector_applies_all_gemini_profile_defaults(self):
        expected = {"gemini-3.5-flash-lite": (15, 500, 180, 5),
                    "gemini-3.6-flash": (5, 20, 300, 3), "gemini-3.8-flash": (5, 20, 300, 3)}
        for model, values in expected.items():
            with self.subTest(model=model), patch.object(t, "MODEL", model):
                args = t.parse_args([])
                self.assertEqual((args.rpm, args.rpd, args.timeout, args.attempts), values)
                self.assertEqual(args.provider, "gemini")
                self.assertEqual(args.temperature, 0.1)
                self.assertNotIn("thinking_config", t.generation_config(args))
        args = t.parse_args(["--model", "gemini-3.8-flash"])
        self.assertEqual((args.rpm, args.rpd), (5, 20))

    def test_explicit_overrides_and_new_profile_keep_own_provider_settings(self):
        model = "another-vision-model"
        profile = t.ModelProfile("openai", 2, 11, temperature=None, reasoning_effort="low", quota_timezone="UTC")
        with patch.dict(t.MODEL_PROFILES, {model: profile}):
            args = t.parse_args(["--model", model, "--rpm", "1", "--rpd", "7", "--timeout", "90"])
        self.assertEqual((args.provider, args.rpm, args.rpd, args.timeout), ("openai", 1, 7, 90))
        config = t.generation_config(args)
        self.assertEqual(config["reasoning"], {"effort": "low"})
        self.assertNotIn("temperature", config)
        self.assertNotIn("response_mime_type", config)
        self.assertIsNone(t.parse_args(["--rpd", "0"]).rpd)

    def test_unknown_model_and_incompatible_options_fail_locally(self):
        for options in (["--model", "unconfigured-model"], ["--rpd", "-1"], ["--rpm", "0"],
                        ["--model", "gemini-3.8-flash", "--thinking-level", "minimal"],
                        ["--reasoning-effort", "low"], ["--image-detail", "original"],
                        ["--model", "gpt-5.6-luna", "--thinking-level", "low"]):
            with self.subTest(options=options), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    t.parse_args(options)
        config = t.generation_config(t.parse_args(["--model", "gemini-3.8-flash", "--thinking-level", "low"]))
        self.assertEqual(config["thinking_config"], {"thinking_level": "LOW"})

    def test_list_models_needs_no_key_or_dataset_and_writes_nothing(self):
        with patch.object(t, "load_api_key") as key, patch.object(t, "run") as run, \
                contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(t.main(["--list-models"]), 0)
        key.assert_not_called()
        run.assert_not_called()
        self.assertIn("gemini-3.8-flash: gemini; 5 RPM; 20 local RPD", output.getvalue())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_daily_count_survives_restart_and_is_separate_for_each_model(self):
        self.args.rpd = 2
        quota = t.DailyQuota(self.args)
        self.assertEqual(quota.update(), 1)
        self.assertEqual(t.DailyQuota(self.args).update(), 2)
        with self.assertRaises(t.QuotaReached):
            t.DailyQuota(self.args).update()
        self.args.model = "gemini-3.8-flash"
        self.assertEqual(t.DailyQuota(self.args).update(), 1)
        self.args.provider = "openai"
        self.assertEqual(t.DailyQuota(self.args).update(), 1)
        state = json.loads(Path(self.args.quota_file).read_text())
        self.assertEqual(len(state["models"]), 3)

    def test_pacific_reset_uses_midnight_with_summer_and_winter_offsets(self):
        self.args.rpd = 1
        for month, reset_hour in ((9, 7), (1, 8)):
            with self.subTest(month=month):
                self.args.quota_file = str(self.root / f"{month}.json")
                now = datetime(2026, month, 21, reset_hour - 1, 59, 59, tzinfo=timezone.utc)
                quota = t.DailyQuota(self.args, now=lambda: now)
                self.assertEqual(quota.update(), 1)
                with self.assertRaises(t.QuotaReached):
                    quota.update()
                now = datetime(2026, month, 21, reset_hour, tzinfo=timezone.utc)
                self.assertEqual(quota.update(), 1)

    def test_provider_daily_stop_persists_until_reset(self):
        now = datetime(2026, 9, 21, 18, tzinfo=timezone.utc)
        quota = t.DailyQuota(self.args, now=lambda: now)
        quota.update()
        quota.update(exhaust=True)
        with self.assertRaises(t.QuotaReached):
            t.DailyQuota(self.args, now=lambda: now).update()
        now = datetime(2026, 9, 22, 7, tzinfo=timezone.utc)
        self.assertEqual(quota.update(), 1)

    def test_damaged_counter_is_preserved_not_reset(self):
        path = Path(self.args.quota_file)
        for data in ('{broken', '{"version":99,"models":{}}',
                     '{"version":1,"models":{"x":{"date":"2026-09-21","attempts":-1,"exhausted":false}}}'):
            with self.subTest(data=data):
                path.write_text(data)
                with self.assertRaisesRegex(RuntimeError, "damaged"):
                    t.DailyQuota(self.args).update()
                self.assertEqual(path.read_text(), data)


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
        self.args = t.parse_args(["Accipiter_gentilis", "--csv", str(self.csv), "--base-dir", str(self.root / "Family"),
                                  "--quota-file", str(self.root / "usage.json")])
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

    def use_profile(self, model, *options):
        self.args = t.parse_args(["Accipiter_gentilis", "--model", model, "--csv", str(self.csv),
                                  "--base-dir", str(self.root / "Family"),
                                  "--quota-file", str(self.root / "usage.json"), *options])

    def snapshot(self, include_usage=True):
        return {str(path.relative_to(self.root)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in self.root.rglob("*") if path.is_file()
                and (include_usage or not path.name.startswith("usage.json"))}

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

    def test_uncatalogued_examples_pair_and_sort_after_numbered_cards(self):
        for number in (10, 2, 1):
            for side in ("B", "A"):
                self.card_image(f"Falco_mexicanus_Uncatalogued{number:02}({side}).jpg")
        cards, issues, missing = t.discover_cards(self.folder, None)
        self.assertEqual(issues, [])
        self.assertEqual(missing, set())
        self.assertEqual([c.enums for c in cards[:2]], [("E4268",), ("E4927",)])
        unnumbered = cards[2:]
        self.assertEqual([c.base_id for c in unnumbered],
                         [f"Falco_mexicanus_Uncatalogued{n:02}" for n in (1, 2, 10)])
        for card in unnumbered:
            self.assertEqual(card.enums, ())
            self.assertEqual(card.sections, ("FRONT", "BACK OF SLIP"))
            self.assertTrue(card.paths[0].name.endswith("(A).jpg"))
            prompt = t.build_prompt(card, self.db(), True)
            self.assertNotIn("CATALOGUE REFERENCE HINTS", prompt)
            self.assertNotIn("Reference Collector", prompt)
            block = t.output_block(card, {"status": "ok", "text": transcript(card.sections)})
            banners = [line for line in block.splitlines() if line.startswith("=") and line.strip("=")]
            self.assertEqual([line.strip("=") for line in banners], [p.name for p in card.paths])
            self.assertNotIn("CM", "\n".join(banners))
            self.assertTrue(block.endswith("\n\n\n"))

    def test_uncatalogued_spelling_variants_and_front_only(self):
        for name in ("Accipiter_gentilis_Uncatalogued.jpg",
                     "Accipiter_gentilis_Uncataloged_02(A).JPEG",
                     "Accipiter_gentilis_Uncataloged_02(B).JPEG",
                     "Accipiter_gentilis_UNCATALOGUED03-A-.jpg",
                     "Accipiter_gentilis_UNCATALOGUED03-B-.jpg"):
            self.card_image(name)
        cards, issues, _ = t.discover_cards(self.folder, None)
        self.assertEqual(issues, [])
        uncatalogued = [card for card in cards if not card.enums]
        self.assertEqual(len(uncatalogued), 3)
        self.assertEqual(sorted(len(c.paths) for c in uncatalogued), [1, 2, 2])
        single = next(card for card in uncatalogued if len(card.paths) == 1)
        self.assertEqual(single.sections, ("FRONT",))
        self.assertEqual(single.warnings, [])

    def test_uncatalogued_duplicate_sides_rejected_and_back_only_warned(self):
        for name in ("Falco_mexicanus_Uncatalogued01.jpg",
                     "Falco_mexicanus_Uncatalogued01(A).jpg",
                     "Falco_mexicanus_Uncatalogued02(B).jpg"):
            self.card_image(name)
        cards, issues, _ = t.discover_cards(self.folder, None)
        uncatalogued = [card for card in cards if not card.enums]
        self.assertEqual(len(uncatalogued), 1)
        self.assertTrue(any("duplicate side" in item for item in issues))
        self.assertEqual(uncatalogued[0].sections, ("BACK OF SLIP",))
        self.assertTrue(any("Front image is missing" in w for w in uncatalogued[0].warnings))

    def test_reported_exchanged_filenames_are_paired_and_discovered(self):
        for name in ("Accipiter_Cooperii_E3024(B)_exchanged.jpg",
                     "Accipiter_Cooperii_E3024(A)_exchanged.jpg",
                     "Accipiter_Cooperii_E4314_exchanged.jpg"):
            self.card_image(name)
        cards, issues, missing = t.discover_cards(self.folder, {"E3024", "E4314"})
        self.assertEqual([card.base_id for card in cards], ["Accipiter_Cooperii_E3024", "Accipiter_Cooperii_E4314"])
        self.assertEqual([card.sections for card in cards], [("FRONT", "BACK OF SLIP"), ("FRONT",)])
        self.assertEqual(issues, [])
        self.assertEqual(missing, set())

    def test_shared_exchanged_card_matches_second_number(self):
        for side in ("B", "A"):
            self.card_image(f"Accipiter_gentilis_E186_E187({side})_EXCHANGED.JPEG")
        card = self.cards({"E187"})[0]
        self.assertEqual(card.enums, ("E186", "E187"))
        self.assertEqual(card.sections, ("FRONT", "BACK OF SLIP"))

    def test_exchanged_tag_cannot_hide_duplicate_front(self):
        self.card_image("Accipiter_gentilis_E4927_exchanged.jpg")
        cards, issues, missing = t.discover_cards(self.folder, {"E4927"})
        self.assertEqual(cards, [])
        self.assertTrue(any("duplicate side" in issue for issue in issues))
        self.assertEqual(missing, {"E4927"})

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
        self.args.temperature = t.MODEL_PROFILES[t.MODEL].temperature
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

    def test_user_pasted_e15_accepts_multiple_location_annotations(self):
        card = t.Card("Accipiter_Cooperii_E15", ("E15",), (Path("Accipiter_Cooperii_E15.jpg"),), ("FRONT",))
        text, _, _ = t.validate_response(response(PASTED_E15), card)
        self.assertEqual(text, PASTED_E15)

    def test_front_only_prompt_explicitly_requires_zero_backs(self):
        card = self.cards({"E4927"})[0]
        prompt = t.build_prompt(card, self.db(), False)
        self.assertIn("1 front image(s), 0 back image(s)", prompt)
        self.assertIn("FRONT ONLY", prompt)

    def test_lone_a_is_front_only_without_missing_back_warning(self):
        self.card_image("Accipiter_gentilis_E187(A).jpg")
        card = self.cards({"E187"})[0]
        self.assertEqual(card.sections, ("FRONT",))
        self.assertEqual(card.warnings, [])
        self.assertIn("FRONT ONLY", t.build_prompt(card, self.db(), False))

    def test_front_only_empty_back_templates_are_removed_without_retry(self):
        card = self.cards({"E4927"})[0]
        for marker in ("", "-", "[blank]", "[No back image provided]", "No back supplied."):
            with self.subTest(marker=marker):
                body = "Name: specimen\nANNOTATIONS:\n(top left) 4927\nBACK OF SLIP:\n" + marker + "\nTRANSCRIPTION NOTES:"
                engine, client, _ = self.engine([response(body)])
                result = engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
                self.assertEqual(result["status"], "review")
                self.assertEqual(len(client.calls), 1)
                self.assertNotIn("BACK OF SLIP", result["text"])
                self.assertIn("(top left) 4927", result["text"])
                self.assertTrue(any("placeholder" in item for item in result["warnings"]))

    def test_unexpected_substantive_back_is_not_silently_discarded(self):
        card = self.cards({"E4927"})[0]
        body = transcript(("BACK OF SLIP",))
        with self.assertRaises(t.ResponseProblem) as caught:
            t.validate_response(response(body), card)
        self.assertIn("TEST FIXTURE BACK", caught.exception.partial)

    def test_annotations_on_front_and_back_preserve_both_sides(self):
        card = self.cards({"E4268"})[0]
        body = ("Name: specimen\nANNOTATIONS:\n(top left) 4268\nBACK OF SLIP:\n"
                "Long back narrative.\nANNOTATIONS:\n(bottom right) marginal text\nTRANSCRIPTION NOTES:")
        engine, client, _ = self.engine([response(body)])
        result = engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["text"], body)
        self.assertEqual(len(client.calls), 1)

    def test_repeated_annotations_on_one_side_are_retained_for_review(self):
        card = self.cards({"E4927"})[0]
        body = "Name: specimen\nANNOTATIONS:\n(top left) 4927\nANNOTATIONS:\n(bottom right) stamp\nTRANSCRIPTION NOTES:"
        text, warnings, _ = t.validate_response(response(body), card)
        self.assertEqual(text, body)
        self.assertTrue(any("2 ANNOTATIONS" in item for item in warnings))

    def test_indented_bold_and_crlf_headers_are_recognized(self):
        card = self.cards({"E4268"})[0]
        body = ("Name: specimen\r\n  **ANNOTATIONS:**\r\n(top left) 4268\r\n"
                "  **BACK OF SLIP:**\r\nNarrative.\r\n  ANNOTATIONS:\r\nStamp\r\n  TRANSCRIPTION NOTES:")
        text, warnings, _ = t.validate_response(response(body), card)
        self.assertEqual(text, body)
        self.assertEqual(warnings, [])

    def test_section_prefixed_back_is_accepted_without_retry(self):
        card = self.cards({"E4268"})[0]
        for heading in ("SECTION: BACK OF SLIP", "SECTION: BACK OF SLIP:",
                        "BACK OF SLIP", "**SECTION: BACK OF SLIP**",
                        "## SECTION: BACK OF SLIP", "**SECTION:** BACK OF SLIP"):
            with self.subTest(heading=heading):
                body = ("COLLECTION OF\nH. W. and C. M. BRANDT\nSpecies: Cooper's Hawk\n"
                        "ANNOTATIONS:\nTop left, stamped in red ink: 4936\n\n"
                        + heading + "\nField Data H.W. and C.M. Brandt\nIncub. 1/2 +\n"
                        "ANNOTATIONS:\nBottom numbers: 4/11/14/20\n\nTRANSCRIPTION NOTES:\nNone")
                engine, client, _ = self.engine([response(body)])
                result = engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
                self.assertEqual(result["status"], "ok")
                self.assertEqual(result["text"], body)
                self.assertEqual(len(client.calls), 1)

    def test_flexible_back_headings_still_reject_missing_empty_duplicate_and_cutoff(self):
        card = self.cards({"E4268"})[0]
        for back in ("", "Data mentions SECTION: BACK OF SLIP in prose.",
                     "BACK OF SLIP has writing on it.",
                     "SECTION: BACK OF SLIP\nANNOTATIONS:\n",
                     "SECTION: BACK OF SLIP\nText\nSECTION: BACK OF SLIP\nMore text"):
            with self.subTest(back=back), self.assertRaises(t.ResponseProblem):
                t.validate_response(response("Front\nANNOTATIONS:\n" + back +
                                             "\nTRANSCRIPTION NOTES:\nNone"), card)
        with self.assertRaisesRegex(t.ResponseProblem, "token limit"):
            t.validate_response(response("Front\nANNOTATIONS:\nSECTION: BACK OF SLIP\n"
                                         "Back text\nTRANSCRIPTION NOTES:\nNone", "MAX_TOKENS"), card)

    def test_numbered_section_back_headings_keep_image_order(self):
        card = t.Card("test", ("E1",), (), ("FRONT", "BACK OF SLIP", "BACK OF SLIP 2"))
        body = ("Front\nANNOTATIONS:\nSECTION: BACK OF SLIP\nFirst back\n"
                "SECTION: BACK OF SLIP 2\nSecond back\nTRANSCRIPTION NOTES:\nNone")
        self.assertEqual(t.validate_response(response(body), card)[0], body)
        wrong_order = body.replace("BACK OF SLIP\n", "BACK OF SLIP 3\n")
        with self.assertRaises(t.ResponseProblem):
            t.validate_response(response(wrong_order), card)

    def test_supplied_blank_back_is_retained(self):
        card = self.cards({"E4268"})[0]
        body = "Name: specimen\nANNOTATIONS:\nBACK OF SLIP:\n[blank]\nTRANSCRIPTION NOTES:"
        text, warnings, _ = t.validate_response(response(body), card)
        self.assertEqual(text, body)
        self.assertEqual(warnings, [])

    def test_empty_notes_markers_do_not_trigger_review_but_real_notes_do(self):
        card = self.cards({"E4927"})[0]
        for notes in ("", "-", "None", "None.", " NONE. ", "N/A", "n/a."):
            with self.subTest(notes=notes):
                body = transcript() + "\n" + notes
                text, warnings, _ = t.validate_response(response(body), card)
                self.assertEqual(text, body.strip())
                self.assertEqual(warnings, [])
        for notes in ("None of the date is legible.", "None. Lower edge is torn.", "Ink obscures part of the locality."):
            with self.subTest(notes=notes):
                _, warnings, _ = t.validate_response(response(transcript() + "\n" + notes), card)
                self.assertIn("Transcription notes are present.", warnings)

    def test_cached_empty_notes_review_is_corrected_without_losing_other_flags(self):
        path = self.root / "old_review_cache.jsonl"
        for other_flags in ([], ["1 bracketed uncertain reading(s)."]):
            with self.subTest(other_flags=other_flags), t.Journal(path) as journal:
                text = transcript() + "\nNone."
                original = {"key": "old", "cache_version": t.CACHE_VERSION, "status": "review",
                            "text": text, "warnings": ["Transcription notes are present.", *other_flags]}
                journal.append(original)
                entry = journal.reusable("old")
                self.assertEqual(entry["warnings"], other_flags)
                self.assertEqual(entry["status"], "review" if other_flags else "ok")
                self.assertEqual(entry["text"], text)
                self.assertIn("Transcription notes are present.", original["warnings"])
        with t.Journal(path) as journal:
            journal.append({**original, "text": transcript() + "\nLower edge is torn."})
            self.assertIn("Transcription notes are present.", journal.reusable("old")["warnings"])

    def test_back_only_response_needs_no_front_annotations(self):
        self.card_image("Accipiter_gentilis_E187(B).jpg")
        card = self.cards({"E187"})[0]
        body = "BACK OF SLIP:\nNarrative on back.\nANNOTATIONS:\n(top right) stamp\nTRANSCRIPTION NOTES:"
        self.assertEqual(t.validate_response(response(body), card)[0], body)

    def test_format_retry_adds_actual_side_instructions_without_mutating_request(self):
        card = self.cards({"E4927"})[0]
        engine, client, _ = self.engine([response(transcript(("BACK OF SLIP",))), response(transcript())])
        _, contents = t.prepare_card(card, "test", self.args)
        original_count = len(contents[0]["parts"])
        result = engine.transcribe(card, contents)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(len(contents[0]["parts"]), original_count)
        correction = client.calls[1]["contents"][0]["parts"][-1]["text"]
        self.assertIn("FORMAT CORRECTION", correction)
        self.assertIn("0 back image(s)", correction)
        self.assertIn("FRONT ONLY", correction)

    def test_thoughts_excluded_and_uncertainty_flagged(self):
        card = self.cards({"E4268"})[0]
        text = transcript(card.sections).replace("TEST FIXTURE ONLY", "[uncertain]")
        actual, warnings, usage = t.validate_response(response(text, thought="SECRET TEST THOUGHT"), card)
        self.assertNotIn("SECRET TEST THOUGHT", actual)
        self.assertIn("1 bracketed", warnings[0])
        self.assertEqual(usage["total_token_count"], 100)

    def test_reported_latex_is_rejected_without_rewriting_the_response(self):
        card = self.cards({"E4927"})[0]
        examples = (
            r'Incubation $\begin{aligned} & 2 \text { egg } 5 \text { days } \\ & 2 \text { " fresh }\end{aligned}$',
            r'Mark $\frac{5}{4}$ [crossed out: $\frac{5}{7}$]',
            r'Nest Diam. $\frac{24}{12}$',
            r'Depth $\frac{1 \frac{1}{2}}{1}$',
            r'Mark: $5/4$', r'Mark: \(5/4\)', r'Mark: \frac{5}{4}',
        )
        for example in examples:
            with self.subTest(example=example):
                body = example + "\nANNOTATIONS:\nTRANSCRIPTION NOTES:"
                with self.assertRaisesRegex(t.ResponseProblem, "LaTeX") as caught:
                    t.validate_response(response(body), card)
                self.assertTrue(caught.exception.retryable)
                self.assertEqual(caught.exception.partial, body)

    def test_plain_fractions_multiline_fields_and_literal_currency_are_retained(self):
        card = self.cards({"E4927"})[0]
        body = ('Incubation: 2 egg 5 days\n2 " fresh\nSet Mark: 5/4\n'
                'Nest: Diameter: Inside: 12 inches; Outside: 24 inches\n'
                'Depth: Inside: 1 inches; Outside: 1 1/2 inches\n'
                'Price: $2 and $3\nSpecies: { Falco mexicanus\nPrairie Falcon\n'
                'ANNOTATIONS:\nTRANSCRIPTION NOTES:')
        actual, warnings, _ = t.validate_response(response(body), card)
        self.assertEqual(actual, body)
        self.assertEqual(warnings, [])

    def test_latex_retry_is_bounded_and_requests_plain_text(self):
        card = self.cards({"E4927"})[0]
        bad = r'Nest Diam. $\frac{24}{12}$' + "\nANNOTATIONS:\nTRANSCRIPTION NOTES:"
        good = 'Nest Diam.: 24/12\nANNOTATIONS:\nTRANSCRIPTION NOTES:'
        _, contents = t.prepare_card(card, "test", self.args)
        for second, expected in ((good, "ok"), (bad, "failed")):
            with self.subTest(expected=expected):
                engine, client, _ = self.engine([response(bad), response(second)])
                result = engine.transcribe(card, contents)
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["text"], second)
                self.assertEqual(len(client.calls), 2)
                correction = client.calls[1]["contents"][0]["parts"][-1]["text"]
                self.assertIn("LaTeX", correction)
                self.assertIn("plain text", correction)
                self.assertEqual(len(contents[0]["parts"]), 3)

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

    def test_batch_appends_uncatalogued_groups_and_reuses_them(self):
        for number in (2, 1):
            for side in ("B", "A"):
                self.card_image(f"Accipiter_gentilis_Uncatalogued{number:02}({side}).jpg")
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(len(client.calls), 4)
        report = next(self.family.glob("*_transcriptions_*.txt")).read_text()
        self.assertLess(report.index("ID: Accipiter_gentilis_E4927"),
                        report.index("ID: Accipiter_gentilis_Uncatalogued01"))
        self.assertLess(report.index("ID: Accipiter_gentilis_Uncatalogued01"),
                        report.index("ID: Accipiter_gentilis_Uncatalogued02"))
        self.assertEqual(report.count("STATUS: OK"), 4)
        self.assertNotIn("FILE CHECK:", report)
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(len(client.calls), 0)
        self.card_image("Accipiter_gentilis_Uncatalogued01(B).jpg", "purple")
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(len(client.calls), 1)

    def test_row_range_includes_uncatalogued_but_single_enum_does_not(self):
        self.card_image("Accipiter_gentilis_Uncatalogued01.jpg")
        self.args.target = "2-2"  # E4268 only, plus this folder's uncatalogued slip.
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(len(client.calls), 2)
        report = next(self.family.glob("*_transcriptions_*.txt")).read_text()
        self.assertIn("ID: Accipiter_gentilis_Uncatalogued01", report)
        self.assertNotIn("ID: Accipiter_gentilis_E4927", report)
        self.args.force = True
        for target in ("E4268", "E4268*"):
            with self.subTest(target=target):
                self.args.target = target
                engine, client, _ = self.engine()
                self.assertEqual(t.run(self.args, engine), 0)
                self.assertEqual(len(client.calls), 1)
                submitted = str(client.calls[0]["contents"])
                self.assertNotIn("IMAGE: Accipiter_gentilis_Uncatalogued", submitted)

    def test_uncatalogued_dry_run_is_read_only_and_reports_no_invented_number(self):
        self.card_image("Accipiter_gentilis_Uncatalogued01.jpg")
        self.args.dry_run = True
        before = self.snapshot()
        engine, client, _ = self.engine()
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            self.assertEqual(t.run(self.args, engine), 0)
        self.assertIn("Uncatalogued (filename header)", captured.getvalue())
        self.assertIn("3 card group(s)", captured.getvalue())
        self.assertEqual(client.calls, [])
        self.assertEqual(self.snapshot(), before)

    def test_force_refreshes_completed_cards(self):
        t.run(self.args, self.engine()[0])
        self.args.force = True
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(len(client.calls), 2)

    def test_console_star_is_fresh_and_does_not_write_even_when_cache_exists(self):
        t.run(self.args, self.engine()[0])
        before = self.snapshot(include_usage=False)
        usage_before = json.loads((self.root / "usage.json").read_text())
        self.args.target = "E4268*"
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(self.snapshot(include_usage=False), before)
        usage_after = json.loads((self.root / "usage.json").read_text())
        key = self.args.provider + "/" + self.args.model
        self.assertEqual(usage_after["models"][key]["attempts"], usage_before["models"][key]["attempts"] + 1)

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

    def test_minute_filenames_preserve_same_minute_outputs(self):
        with patch.object(t, "datetime") as clock:
            clock.now.return_value = datetime(2026, 9, 16, 8, 25, 50, 289529)
            first, handle = t.open_output_report(self.family, "Accipiter_cooperii_transcriptions")
            with handle:
                handle.write("first run")
            second, handle = t.open_output_report(self.family, "Accipiter_cooperii_transcriptions")
            with handle:
                handle.write("second run")
        self.assertEqual(first.name, "Accipiter_cooperii_transcriptions_20260916_0825.txt")
        self.assertEqual(second.name, "Accipiter_cooperii_transcriptions_20260916_0825_2.txt")
        self.assertEqual(first.read_text(), "first run")
        self.assertEqual(second.read_text(), "second run")

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

    def test_low_quota_profile_paces_successes_and_retries(self):
        self.use_profile("gemini-3.8-flash")
        engine, client, clock = self.engine()
        for card in self.cards():
            engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
        self.assertEqual(client.starts, [0, 12.1])
        engine, client, clock = self.engine([FakeAPIError(503)])
        card = self.cards()[0]
        result = engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
        self.assertEqual(result["status"], "ok")
        self.assertGreaterEqual(client.starts[1] - client.starts[0], 15)

    def test_pacing_changes_reuse_cache_and_switching_back_restores_model_results(self):
        self.assertEqual(t.run(self.args, self.engine()[0]), 0)
        self.args.rpm, self.args.rpd, self.args.timeout, self.args.attempts = 1, 600, 400, 1
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(client.calls, [])
        self.use_profile("gemini-3.8-flash")
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(len(client.calls), 2)
        self.use_profile("gemini-3.5-flash-lite")
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(client.calls, [])
        counts = json.loads((self.root / "usage.json").read_text())["models"]
        self.assertEqual(counts["gemini/gemini-3.5-flash-lite"]["attempts"], 2)
        self.assertEqual(counts["gemini/gemini-3.8-flash"]["attempts"], 2)

    def test_daily_cap_pauses_next_card_and_restart_reuses_completed_work(self):
        self.args.rpd = 1
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 1)
        self.assertEqual(len(client.calls), 1)
        report = next(self.family.glob("*_transcriptions_*.txt")).read_text()
        self.assertIn("STATUS: OK", report)
        self.assertIn("STATUS: PAUSED", report)
        self.assertNotIn("STATUS: FAILED", report)
        self.assertIn("MODEL: gemini / gemini-3.5-flash-lite", report)
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 1)
        self.assertEqual(client.calls, [])
        self.args.rpd = 2
        engine, client, _ = self.engine()
        self.assertEqual(t.run(self.args, engine), 0)
        self.assertEqual(len(client.calls), 1)

    def test_format_retry_consumes_daily_budget_and_keeps_saved_response(self):
        self.args.rpd = 1
        card = self.cards()[0]
        partial = "Name: unfinished format fixture"
        engine, client, _ = self.engine([response(partial)])
        result = engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
        self.assertEqual(result["status"], "paused")
        self.assertEqual(result["text"], partial)
        self.assertEqual(result["attempts"], 1)
        self.assertEqual(len(client.calls), 1)

    def test_daily_api_quota_stops_without_retry_and_remains_blocked_on_restart(self):
        error = FakeAPIError(429, {"error": {"details": [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                   "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}]}})
        for label in ("generate_requests_per_model_per_day", "generate_requests_per_day_per_model",
                      "GenerateRequestsPerDayPerProjectPerModel-FreeTier"):
            self.assertEqual(t.quota_error_kind(FakeAPIError(429, {"quotaId": label})), "daily")
        self.assertEqual(t.quota_error_kind(FakeAPIError(429, {"error": {"code": "quota_exceeded"}})), "daily")
        engine, client, clock = self.engine([error])
        card = self.cards()[0]
        contents = t.prepare_card(card, "test", self.args)[1]
        result = engine.transcribe(card, contents)
        self.assertEqual(result["status"], "paused")
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(clock.delays, [])
        engine, client, _ = self.engine()
        self.assertEqual(engine.transcribe(card, contents)["status"], "paused")
        self.assertEqual(client.calls, [])

    def test_long_server_wait_pauses_instead_of_retrying_early(self):
        engine, client, clock = self.engine([FakeAPIError(429, headers={"Retry-After": "3600"})])
        card = self.cards()[0]
        result = engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
        self.assertEqual(result["status"], "paused")
        self.assertIn("3600s", result["stop_reason"])
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(clock.delays, [])

    def test_counter_write_failure_prevents_api_request(self):
        engine, client, _ = self.engine()
        card = self.cards()[0]
        with patch.object(t.DailyQuota, "_write", side_effect=OSError("disk fixture")):
            with self.assertRaisesRegex(RuntimeError, "no API request was sent"):
                engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
        self.assertEqual(client.calls, [])

    def test_openai_keeps_image_order_plain_text_usage_and_completion_checks(self):
        self.use_profile("gpt-5.6-luna")
        card = self.cards({"E4268"})[0]
        text = transcript(card.sections)
        client = FakeOpenAIClient([openai_response(text)])
        clock = Clock()
        engine = t.Transcriber(self.args, client, clock.time, clock.sleep)
        result = engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["text"], text)
        self.assertEqual(result["usage"], {"prompt_token_count": 100, "candidates_token_count": 40,
                                         "thoughts_token_count": 20, "total_token_count": 160})
        payload = client.calls[0]
        self.assertNotIn("temperature", payload)
        self.assertNotIn("thinking_config", payload)
        self.assertFalse(payload["store"])
        parts = payload["input"][0]["content"]
        self.assertIn("SECTION: FRONT", parts[1]["text"])
        self.assertIn("SECTION: BACK OF SLIP", parts[3]["text"])
        for index, image_part in enumerate((parts[2], parts[4])):
            self.assertEqual(image_part["detail"], "original")
            self.assertEqual(t.base64.b64decode(image_part["image_url"].split(",", 1)[1]), card.paths[index].read_bytes())
        for status, reason in (("incomplete", "max_output_tokens"), ("failed", None), (None, None)):
            with self.subTest(status=status), self.assertRaises(t.ResponseProblem) as caught:
                t.normalize_openai_response(openai_response(text, status=status, reason=reason))
            self.assertEqual(caught.exception.partial, text)
        refused = openai_response(text)
        refused.output[1].content.append(NS(type="refusal", refusal="fixture"))
        with self.assertRaisesRegex(t.ResponseProblem, "declined"):
            t.normalize_openai_response(refused)

    def test_openai_format_retry_uses_original_images_and_billing_quota_is_not_retried(self):
        self.use_profile("gpt-5.6-luna")
        card = self.cards()[0]
        client = FakeOpenAIClient([openai_response("bad format"), openai_response(transcript(card.sections))])
        clock = Clock()
        engine = t.Transcriber(self.args, client, clock.time, clock.sleep)
        self.assertEqual(engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])["status"], "ok")
        self.assertIn("FORMAT CORRECTION", client.calls[1]["input"][0]["content"][-1]["text"])
        self.assertEqual(client.calls[0]["input"][0]["content"][2], client.calls[1]["input"][0]["content"][2])
        client = FakeOpenAIClient([FakeAPIError(429, {"error": {"code": "insufficient_quota"}})])
        engine = t.Transcriber(self.args, client, clock.time, clock.sleep)
        result = engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
        self.assertEqual(result["status"], "paused")
        self.assertIn("billing", result["stop_reason"])
        self.assertEqual(len(client.calls), 1)

    def test_actual_openai_sdk_serializes_request_and_counts_its_own_retries_offline(self):
        try:
            import openai
            from openai import _base_client
        except ImportError:
            self.skipTest("Install openai for the SDK transport test")
        # Current SDK uses httpx2; older supported SDKs use httpx.
        http = getattr(_base_client, "httpx2", None) or _base_client.httpx
        self.use_profile("gpt-5.6-luna")
        card = self.cards({"E4268"})[0]
        captured = []

        def handler(request):
            captured.append(request)
            if len(captured) == 1:
                return http.Response(429, headers={"Retry-After": "1"}, json={
                    "error": {"message": "offline rate limit", "type": "rate_limit_error", "code": "rate_limit_exceeded"}})
            return http.Response(200, json={"id": "resp_offline", "object": "response", "created_at": 1,
                "model": "gpt-5.6-luna", "status": "completed", "error": None, "incomplete_details": None,
                "output": [{"type": "message", "id": "msg_offline", "role": "assistant", "status": "completed",
                            "content": [{"type": "output_text", "text": transcript(card.sections), "annotations": []}]}],
                "usage": {"input_tokens": 100, "output_tokens": 60, "total_tokens": 160,
                          "output_tokens_details": {"reasoning_tokens": 20}}})

        http_client = http.Client(transport=http.MockTransport(handler))
        self.addCleanup(http_client.close)
        constructor = openai.OpenAI
        options = []

        def factory(**kwargs):
            options.append(kwargs.copy())
            return constructor(**kwargs, http_client=http_client)

        clock = Clock()
        with patch.object(openai, "OpenAI", side_effect=factory), \
                patch.object(t, "load_api_key", return_value="offline-openai-token"), \
                patch.dict(os.environ, {"OPENAI_BASE_URL": "https://wrong.invalid"}):
            engine = t.Transcriber(self.args, clock=clock.time, sleep=clock.sleep)
            self.addCleanup(engine.close)
            result = engine.transcribe(card, t.prepare_card(card, "test", self.args)[1])
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(captured), 2)
        self.assertEqual(engine.requests, 2)
        self.assertGreaterEqual(clock.now, 60)
        self.assertEqual(options[0]["max_retries"], 0)
        self.assertEqual(options[0]["timeout"], 300)
        self.assertEqual(captured[0].url.host, "api.openai.com")
        self.assertEqual(captured[0].url.path, "/v1/responses")
        self.assertEqual(captured[0].headers["authorization"], "Bearer offline-openai-token")
        body = json.loads(captured[-1].content)
        self.assertEqual(body["model"], "gpt-5.6-luna")
        self.assertNotIn("temperature", body)
        self.assertFalse(body["store"])
        self.assertEqual(len([part for part in body["input"][0]["content"] if part["type"] == "input_image"]), 2)

    def test_supplied_scans_preserve_pixels_and_pair_correctly(self):
        location = os.environ.get("EGG_SLIP_SAMPLE_DIR")
        if not location:
            self.skipTest("Set EGG_SLIP_SAMPLE_DIR to run supplied-scan verification")
        # Later conversations can add other photographs to the attachment folder.
        paths = sorted(Path(location).glob("*Accipiter_gentilis*.jpg"))
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
