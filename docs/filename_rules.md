# Input, catalogue, and filename rules

These are **egg-slip domain conventions**, not requirements of a general transcription engine. The current implementation is in `Database`, `load_database`, `select_targets`, `resolve_folders`, `Card`, and `discover_cards` in [transcribe.py](../transcribe.py). The source files are read-only.

## Catalogue input

The program reads a CSV export, not a workbook or a live Google Sheet. It uses `csv.DictReader` with `utf-8-sig`, accepting UTF-8 with or without a BOM. Required headers, after surrounding whitespace is stripped:

| Header | Purpose |
| --- | --- |
| `catalogNumber` | Exact E-number lookup; values are stripped and uppercased. |
| `Scientific Name` | Derive `Genus_species` from the first two words. Underscores can substitute for spaces. |
| `Family` | Resolve the family directory. |

Optional hint columns are `Collector`, `locality`, `county`, `stateProvince`, and `country`, plus `Scientific Name`. Names/case must match; columns such as `CatalogNumberText` from other project exports are **not** aliases for `catalogNumber`. Unrelated columns are retained in the loaded rows but not sent as hints.

Data rows are numbered from 2, with row 1 treated as the header. These are parsed CSV records, not raw text line numbers when quoted values contain newlines. Blank catalogue numbers remain in the row map but do not become selected records. Missing/duplicate headers and rows with extra columns are rejected. Duplicate catalogue numbers are retained as lists, with a warning, not overwritten. Exact-number routing rejects conflicting scientific-name species; family routing rejects missing or conflicting families.

No leading-zero normalization occurs: `E001` and `E1` are different catalogue identifiers. The CSV does not decide what is actually written on a scan. `--no-csv-hints` suppresses reading hints, not the CSV load or normal folder routing.

## Production directories

`BASE_FAMILY_DIR` / `--base-dir` selects the directory named `Family` in the existing installation. Two layouts are supported:

```text
Family/<family>/<Genus_species>/JPEG/<scan>.jpg
Family/<family>/<Genus>/<Genus_species>/JPEG/<scan>.jpg
```

Directory lookup is case-insensitive, including `JPEG`. Both matching layouts present at once, or two case variants of one directory on a case-sensitive filesystem, are ambiguous and rejected. The code does not recursively search arbitrary paths or read originals/TIFF subfolders. Only direct `.jpg` and `.jpeg` files in the resolved JPEG directory are discovered; extension matching is case-insensitive. Other formats are ignored.

The defaults are machine-specific Windows paths under `G:\My Drive\Egg Slip Scanning`. They are retained for compatibility, not a portable project-root convention. CLI path overrides work independently of VS Code's launch directory. Normal reports/journals go in the family directory, even when the scans are nested under a genus directory.

## Target syntax and scope

| Target | Selected material |
| --- | --- |
| `Accipiter_cooperii` or `"Accipiter cooperii"` | Every recognized group in that species JPEG folder, including uncatalogued groups. Family mapping still requires CSV data. |
| `E4268` | Exact number, case-insensitive; it must exist in the CSV to route to its species. |
| `E4268*` | Same selection, fresh console output; `*` is a mode suffix, not a glob. |
| `2-1000` | Inclusive spreadsheet-style row range; first row must be at least 2. Select corresponding E-numbers, plus uncatalogued groups in every visited species folder. |
| `tests` (or `test`) | Every recognized group in the one test input directory, regardless of species. Case-insensitive with surrounding whitespace ignored. |

Invalid targets, descending ranges, species/range targets with `*`, and path strings used as species names are rejected. `--console-only` is available for normal species/range selections; `test --console-only` is rejected. There is no E-number numeric range or general wildcard search.

In normal species mode, a numbered filename absent from the CSV is still transcribed without matching hints; the special missing-CSV review warning is currently added only in test mode. A species consisting solely of uncatalogued records cannot route without a CSV family mapping; use the mixed test folder for such material until a requested routing enhancement exists.

## Filename grammar

The following names illustrate accepted patterns, not bundled sample files:

| Example | Meaning |
| --- | --- |
| `Accipiter_cooperii_E15.jpg` | One front-only card. |
| `Accipiter_cooperii_E4268(A).jpg`, `...(B).jpg` | Front/back images of one physical card. |
| `Uria_aalge_E186_E187_E188(A).jpg` | A shared physical slip referencing several records. |
| `Accipiter_cooperii_E3024(A)_exchanged.jpg` | Optional `_exchanged` tag follows the side suffix. |
| `Accipiter_cooperii_E4314_exchanged.jpg` | Tagged front-only image. |
| `Falco_mexicanus_Uncatalogued01(A).jpg`, `...(B).jpg` | Uncatalogued physical card with two sides. |

Numbered names have a prefix followed by `_E` and digits, optionally followed by more `_E<digits>` tokens, an optional side suffix, optional `_exchanged`, and `.jpg`/`.jpeg`. Uncatalogued names instead have `_Uncatalogued` or `_Uncataloged`, case-insensitive, with optional digits and an optional underscore/space/hyphen before those digits. An unnumbered `_Uncatalogued.jpg` is valid too.

Supported side forms include `(A)`, `(B)`, `(1)`, `(2)`, `_A`, `-A`, `-A-`, and their numeric equivalents. Parenthesized `(FRONT)` and `(BACK)` are also recognized. Other multi-letter side tokens are rejected. Numeric sides start at 1; letters A–Z map to 1–26. `_exchanged` is a tag, not a side or separate record. No arbitrary suffix such as `_typo`, `_edited`, or `_rescan` is supported.

Recognized groups use the case-folded complete base filename, with side suffix and `_exchanged` removed. Species prefixes are not used to validate the CSV scientific name; metadata lookup uses the E-number. Two differently prefixed base IDs with the same E-number remain separate groups. Filenames are references, not visible card text and not proof of catalogue correctness.

## Physical-card grouping and ordering

1. Match any complete E-number in the group, never a substring (`E18` does not select `E187`). Select a shared slip once, even if multiple requested numbers match it.
2. Sort sides numerically. Unlettered, A, and 1 all mean front. A single unlettered image or lone A is valid front-only input and does not imply a missing back.
3. Duplicate side numbers invalidate the whole group. An unlettered front plus `(A)`, or tagged plus untagged copies of the same side, is ambiguous; report it without sending the group. Do not rename automatically.
4. A lone B stays a back with a missing-front warning. Gaps between supplied side numbers produce review warnings. Additional supplied sides are labelled `BACK OF SLIP`, `BACK OF SLIP 2`, etc., in supplied order; numbering is not the raw suffix value.
5. Sort numbered groups by the tuple of numeric catalogue values in filename order, with natural base-name order as the tie-breaker. Sort uncatalogued groups afterward by natural filename order. Leading zeros remain in identifiers and output even though numeric values participate in sorting.

Malformed JPEG names are reported as `FILE CHECK`, not silently treated as uncatalogued. These checks examine the whole scanned directory, including malformed names outside an exact-number selection. Requested E-numbers with no valid matching group are reported as `MISSING`. Recognized cards can still run, but discovery issues make the overall exit status nonzero.

## Mixed-species test directory

The default is `tests/inputs` beside `transcribe.py`, with no `JPEG` subdirectory or recursive species folders. Explicit `--test-input-dir` overrides it. All cards still use the same filename/side parser. No production family/species directories are required, but the configured CSV is still loaded first. Missing catalogue records are transcribed with a review warning; no unrelated hints are supplied. Uncatalogued groups use filenames in their banners and no invented CM/E number.

See [testing](testing.md) for the representative set and [transcription rules](transcription_rules.md) for output. The eventual backend should receive ordered record images and metadata from a domain adapter; it should not need to understand any of the E-number, species, or A/B conventions above.
