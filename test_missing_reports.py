"""Offline checks for the PowerShell catalogue coverage audit."""
import csv
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import transcribe as t


POWERSHELL = shutil.which("powershell.exe") or shutil.which("pwsh")
SCRIPT = Path(__file__).parent / "scripts" / "find-missing-transcriptions.ps1"


@unittest.skipUnless(POWERSHELL, "PowerShell is required for the catalogue audit")
class MissingReportsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.family = self.root / "Family" / "Expected [1]"
        self.family.mkdir(parents=True)
        self.catalogue = self.root / "catalogue.csv"
        self.summary = self.root / "coverage.txt"

    def write_catalogue(self, numbers):
        with self.catalogue.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["catalogNumber", "", "Scientific Name", "Family"])
            writer.writerows((number, "", "Bird sp. subspecies", self.family.name) for number in numbers)

    def block(self, *numbers, status="ok", text="FRONT OF SLIP:\nEggs in Set 4", error=""):
        identity = "Bird_sp_" + "_".join(numbers)
        card = t.Card(identity, numbers, (Path(identity + ".jpg"),), ("FRONT",))
        return t.output_block(card, dict(status=status, text=text, error=error), cached=status == "review")

    def report(self, name, content, family=None):
        path = (family or self.family) / name
        path.write_bytes(content.replace("\n", "\r\n").encode("utf-8-sig"))
        return path

    def run_script(self, output=None):
        return subprocess.run(
            [POWERSHELL, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-File", str(SCRIPT), "-FamilyRoot", str(self.family.parent),
             "-CsvPath", str(self.catalogue), "-OutputFile", str(output or self.summary)],
            capture_output=True, text=True, timeout=30,
        )

    def test_reports_cover_exact_numbers_and_retain_incomplete_evidence(self):
        self.write_catalogue(["E001", "E1", "E2", "E2", "E3", "E4", "E5", "E6", "E7", "E8", "E9", "E10", ""])
        self.report("Bird_sp_transcriptions_20261107_0900.txt",
                    self.block("E001", "E2", status="review") + self.block("E3")
                    + t.missing_output_block("E4", [{"Collector": "Fixture collector"}])
                    + t.missing_output_block("E10", [{}]))
        self.report("Bird_sp_transcriptions_20261107_0901.txt", "")
        self.report("Bird_sp_transcriptions_20261107_0902_2.txt",
                    self.block("E3", status="failed", error="Later failed retry")
                    + self.block("E5", status="failed", error="Older error"))
        latest = self.report("Bird_sp_transcriptions_20261107_0902_10.txt",
                             self.block("E5", status="failed", error="Latest error")
                             + self.block("E6", status="paused", text="", error="Daily cap")
                             + self.block("E7", text="").rstrip("\n"))
        self.report("E8_g35fl_Bird_sp_20261107_0903.txt", self.block("E8"))
        other = self.family.parent / "Wrong"
        other.mkdir()
        self.report("Bird_sp_transcriptions_20261107_0903.txt", self.block("E9"), other)
        self.report("test_20261107_0903_g35fl_t1.0.txt", self.block("E1"))

        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = self.summary.read_text(encoding="utf-8-sig")
        self.assertIn("4 of 11 catalogue E-number/family pairs have a saved transcription", summary)
        self.assertIn("1 CSV-only record(s) omitted", summary)
        self.assertIn("6 to follow up (3 failed, paused, or incomplete; 3", summary)
        self.assertIn("ID: Bird_sp_E1\nE-number: E1\nSTATUS: NO TRANSCRIPTION", summary)
        self.assertNotIn("E-number: E4\n", summary)
        self.assertIn("E-number: E10\nSTATUS: NO TRANSCRIPTION", summary)
        self.assertIn(f"STATUS: FAILED\nERROR: Latest error\nReport: {latest}", summary)
        self.assertIn("STATUS: PAUSED\nERROR: Daily cap", summary)
        self.assertIn("E-number: E7\nSTATUS: INCOMPLETE", summary)
        self.assertIn("E-number: E9\nSTATUS: NO TRANSCRIPTION", summary)
        self.assertNotIn("Older error", summary)
        self.assertNotIn("Later failed retry", summary)

    def test_source_paths_are_rejected_as_output(self):
        self.write_catalogue(["E1"])
        report = self.report("Bird_sp_transcriptions_20261107_0900.txt", self.block("E1"))
        for source in (self.catalogue, report):
            original = source.read_bytes()
            result = self.run_script(output=source)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(source.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
