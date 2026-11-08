"""Offline integration checks for the PowerShell report search; no collection access."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import transcribe as t


POWERSHELL = shutil.which('powershell.exe') or shutil.which('pwsh')
SCRIPT = Path(__file__).parent / 'scripts' / 'find-failed-transcriptions.ps1'


@unittest.skipUnless(POWERSHELL, 'PowerShell is required for the report-search checks')
class FailedReportsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.family = self.root / 'Family' / 'Example family [1]'
        self.family.mkdir(parents=True)
        self.output = self.root / 'Status-Failed.txt'

    def block(self, identity, status='failed', error='HTTP 503: offline fixture', text=''):
        card = t.Card(identity, (), (Path(identity + '.jpg'),), ('FRONT',))
        return t.output_block(card, dict(status=status, error=error, text=text))

    def report(self, name, text):
        path = self.family / name
        path.write_text(text, encoding='utf-8')
        return path

    def run_script(self, root=None):
        return subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                               '-File', str(SCRIPT), '-FamilyRoot', str(root or self.root / 'Family'),
                               '-OutputFile', str(self.output)], capture_output=True, text=True, timeout=30)

    def test_latest_per_card_includes_partial_and_individual_runs_preserves_sources(self):
        old = self.report('Bird_one_transcriptions_20261106_2359.txt',
                          ''.join(self.block(f'Bird_one_E{n}') for n in (12, 13, 14, 15, 16)))
        self.report('Bird_one_transcriptions_20261107_0900_2.txt', self.block('Bird_one_E13', error='older failure'))
        selected = self.report('Bird_one_transcriptions_20261107_0900_10.txt',
                               self.block('Bird_one_E001_E23') + self.block('Bird_one_Uncatalogued01', error='Local error: bad JPEG') +
                               self.block('Bird_one_E13', status='ok', error='', text='STATUS: FAILED\nERROR: source wording') +
                               self.block('Bird_one_E14', status='review (reused)', error='') +
                               self.block('Bird_one_E15', status='paused', error='Daily cap'))
        os.utime(old, (2000000000, 2000000000))
        os.utime(selected, (1000000000, 1000000000))
        self.report('E12_g35fl_Bird_one_20261108_0900.txt', self.block('Bird_one_E12', status='ok', error=''))
        self.report('test_20261108_0900_g35fl_t1.0.txt', self.block('TEST_E12'))
        self.report('Bird_two_transcriptions_20261106_0900.txt', self.block('OMITTED_E50'))
        self.report('Bird_two_transcriptions_20261107_0900.txt', '')
        before = {p: p.read_bytes() for p in self.family.iterdir()}
        for _ in range(2):
            result = self.run_script()
            self.assertEqual(result.returncode, 0, result.stderr)
        summary = self.output.read_text(encoding='utf-8-sig')
        self.assertIn('4 failed card(s); checked 8 card(s) across 6 saved reports.', summary)
        self.assertIn('ID: Bird_one_E001_E23', summary)
        self.assertIn('ERROR: HTTP 503: offline fixture', summary)
        self.assertIn('ID: Bird_one_Uncatalogued01', summary)
        self.assertIn('ERROR: Local error: bad JPEG', summary)
        self.assertIn('ID: Bird_one_E16', summary)
        self.assertIn('ID: OMITTED_E50', summary)
        self.assertEqual(summary.count('Report: '), 5)
        self.assertIn('ID: Bird_one_E12\nSTATUS: OK\nNOTE: Special fresh check', summary)
        self.assertIn('RUN: python transcribe.py E12 --force', summary)
        for excluded in ('ID: Bird_one_E13', 'ID: Bird_one_E14', 'ID: Bird_one_E15',
                         'TEST_E12', 'older failure', 'source wording', 'Daily cap', 'Failed cards: 0'):
            self.assertNotIn(excluded, summary)
        self.assertEqual(before, {p: p.read_bytes() for p in self.family.iterdir()})

    def test_newer_individual_failure_replaces_success_and_progress_is_reported(self):
        self.report('Bird_one_transcriptions_20261107_0900.txt', self.block('Bird_one_E007', status='ok', error=''))
        self.report('E007_Bird_one_20261107_1000.txt', self.block('Bird_one_E007', error='HTTP 503: latest failure'))
        events = self.root / 'progress.txt'
        def quote(value):
            return "'" + str(value).replace("'", "''") + "'"
        command = (
            'function Write-Progress { param($Activity, $Status, $PercentComplete, [switch]$Completed) '
            'Add-Content -LiteralPath ' + quote(events) + ' -Value "$Activity|$Status|$Completed" }; '
            '& ' + quote(SCRIPT) + ' -FamilyRoot ' + quote(self.root / 'Family') + ' -OutputFile ' + quote(self.output))
        result = subprocess.run([POWERSHELL, '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
                                 '-Command', command], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = self.output.read_text(encoding='utf-8-sig')
        self.assertIn('1 failed card(s); checked 1 card(s) across 2 saved reports.', summary)
        self.assertIn('ERROR: HTTP 503: latest failure', summary)
        self.assertIn('RUN: python transcribe.py E007 --force', summary)
        self.assertEqual(summary.count('ID: Bird_one_E007'), 1)
        progress = events.read_text()
        self.assertIn('Checking latest card results|1/2:', progress)
        self.assertIn('Checking latest card results|2/2:', progress)
        self.assertIn('Checking latest card results||True', progress)
        self.assertIn('Finding saved transcription reports||True', progress)

    def test_later_success_produces_compact_zero_failure_report(self):
        self.report('Bird_one_transcriptions_20261107_0900.txt', self.block('Bird_one_E1'))
        self.report('Bird_one_transcriptions_20261107_1000.txt', self.block('Bird_one_E1', status='ok', error=''))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = self.output.read_text(encoding='utf-8-sig')
        self.assertIn('0 failed card(s); checked 1 card(s) across 2 saved reports.', summary)
        self.assertNotIn('Report:', summary)
        self.assertNotIn('ID:', summary)
        self.assertLessEqual(len(summary.splitlines()), 4)

    def test_special_checks_all_statuses_flagged_until_later_normal_result(self):
        for number, status in enumerate(('ok', 'review', 'failed', 'paused'), 1):
            identity = f'Bird_one_E00{number}'
            self.report(f'E00{number}_g38f_Bird_one_20261107_0900.txt',
                        self.block(identity, status=status, error='HTTP 503: fixture' if status == 'failed' else ''))
        shared = 'Bird_one_E005_E006'
        self.report('E006_g35fl_Bird_one_20261107_0900.txt', self.block(shared, status='review', error=''))
        self.report('Bird_one_transcriptions_20261107_1000.txt', self.block(shared, status='ok', error=''))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = self.output.read_text(encoding='utf-8-sig')
        self.assertIn('1 failed card(s); checked 5 card(s) across 6 saved reports.', summary)
        self.assertIn('4 latest special-check result(s)', summary)
        for number in range(1, 5):
            self.assertIn(f'RUN: python transcribe.py E00{number} --force', summary)
            self.assertEqual(summary.count(f'ID: Bird_one_E00{number}'), 1)
        self.assertNotIn(shared, summary)
        self.assertNotIn('RUN: python transcribe.py E006', summary)
        self.assertEqual(summary.count('NOTE: Special fresh check'), 4)

    def test_missing_error_and_legacy_suffix_with_crlf(self):
        report = self.report('Bird_one_transcriptions_20261107_0900_3.5flash_t1.0.txt', '')
        report.write_bytes(self.block('Bird_one_E07', error='').replace('\n', '\r\n').encode('utf-8-sig'))
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('No ERROR line recorded', self.output.read_text(encoding='utf-8-sig'))

    def test_no_reports_or_missing_root_does_not_replace_previous_summary(self):
        self.output.write_text('previous summary', encoding='utf-8')
        for root in (self.root / 'Family', self.root / 'absent'):
            result = self.run_script(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.output.read_text(), 'previous summary')

    def test_unrecognized_report_filename_is_an_error(self):
        self.report('Bird_one_transcriptions_undated.txt', self.block('E1'))
        result = self.run_script()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unrecognized report filename', result.stderr)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
