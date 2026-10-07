# Test reports

This is the default output directory. Live `tests` runs write one combined report here, independent of the Family folder and working directory. Use `--test-output-dir` to select another location. New generated contents are ignored by Git, but several historical reports and two files named manual transcriptions are already tracked alongside this README. Ignore rules do not remove tracked files. Retain earlier runs and preserve their original filenames; a manual label does not by itself certify every reading or complete coverage of the current input set.

An example name is `test_20261007_1425_g3.5-f-l_t1.0.txt`. Same-minute collisions receive a counter before the model/temperature suffix.

Every live test starts fresh and bypasses all transcription journals. Daily request accounting still applies. Gemini 3.5 Flash-Lite is the established production choice; further paid provider comparisons are not required. New reports include request provenance and token/cost totals; older reports retain the information they originally recorded. See [testing](../../docs/testing.md) for how to point the program here, review existing runs against scans, and curate an offline regression baseline without new service requests.
