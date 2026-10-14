# On-demand transcription viewer — pilot

A spreadsheet link opens this viewer and searches the saved species reports **at click time**. The link needs only an E-number. Existing links with family and scientific name still work and skip the catalogue lookup. No transcription text is written into the spreadsheet, a hidden sheet, script properties, or a persistent cache. No transcription service is called.

A link can be created before that record has been transcribed. It displays “No transcription available” until a matching report is visible in Drive. Opening the same link later searches again. An already-open page does not update by itself; use **Find transcription** to search again.

## Update fonts and review display

Replace **Code.gs** and **Viewer.html** in your Apps Script project, save, then update the existing deployment via **Deploy → Manage deployments → Edit → New version → Deploy**. Keep the existing deployment URL.

Headings, controls, and transcription text use Arial/Helvetica with a sans-serif fallback. The viewer ignores standalone `Notes present` and `Transcription notes are present.` review reasons. If notes presence was the only reason for a saved `REVIEW` status, the viewer displays its normal structural-check message without the review warning. Notes remain visible in the transcription body. Other review reasons, unexplained `REVIEW` statuses, and failed/paused/catalogue-only states retain their warnings. The viewer preserves the original report status and saved text.

## Update an existing deployment for E-number-only search

Replace **Code.gs** and **Viewer.html** in your existing Apps Script project with the updated files here. The manifest and read-only scope have not changed. Save, then use **Deploy → Manage deployments → Edit (pencil) → Version: New version → Deploy**. Keep the existing deployment URL and spreadsheet links.

The form now contains only an E-number field. Even when opened from an older link containing family/species, submitting another E-number looks up its location afresh, without carrying over the old record's family/species.

For E-number-only searches, the viewer reads the same catalogue CSV used by the Python transcription program. It automatically looks for:

```text
Egg Slip Scanning/
  Family/                         (configured ROOT_FOLDER_ID)
  Transcription/
    EggSlipReorganizationProject_FULL.xlsx - Full List.csv
```

The CSV must be synced to Drive and readable by the signed-in user. If it is elsewhere, or the reader cannot browse the common parent folder, set `CATALOGUE_FILE_ID` near the top of **Code.gs** to the CSV's Drive file ID. Leave it blank for automatic discovery. Do not put the spreadsheet ID there; this setting requires the exported CSV file.

The viewer reads the catalogue on each E-number-only search and uses `catalogNumber`, `Family`, and `Scientific Name` to select the reports. It does not save a second catalogue or transcription text. Conflicting duplicate catalogue rows or missing/inaccessible catalogue files produce explicit errors. Existing links supplying both family and species still work without catalogue access.

After updating the deployment, test **E382** in the form; it should resolve to **Hirundinidae / Progne subis**. Then change the number to one in another family to confirm the previous location does not carry over.

## Install the private pilot

Keep this as a **separate Apps Script project** from the existing Egg Scan Linker. No change to that script or to the master workbook is required to test the viewer.

1. Open [Google Apps Script](https://script.google.com/) with the Google account that can read the collection reports. Create a new project named **Egg Transcription Viewer — Pilot**.
2. Replace its default `Code.gs` contents with [Code.gs](Code.gs).
3. Add an **HTML** file named **Viewer** and paste [Viewer.html](Viewer.html) into it.
4. In **Project Settings**, enable **Show “appsscript.json” manifest file in editor**. Replace its contents with [appsscript.json](appsscript.json). The only requested OAuth scope is read-only Drive access. No advanced Drive service is needed.
5. Check `TRANSCRIPTION_VIEWER.ROOT_FOLDER_ID` in `Code.gs`. It is prefilled with the Family root ID from the supplied Egg Scan Linker. It must identify the Family root containing the family directories, not a species or JPEG folder.
6. Save, then choose **Deploy → New deployment → Web app**. For this initial private test, set **Execute as: User accessing the web app** and **Who has access: Only myself**. Authorize read-only Drive access when Google asks. Account or administrator policy may restrict available deployment options.
7. Copy the deployed URL ending in **/exec**. Open it and enter a record’s E-number. Family and species are found in the catalogue CSV described above. The viewer must be deployed and opened through its URL; running `doGet` in the editor does not open the viewer.

Do not upload the test file or this README to Apps Script. There are only three installation files.

The local checks do not verify Google authorization, deployment options, Drive sync, or Apps Script template rendering in your account. Confirm those in this private pilot before sharing links with other staff.

## Try links in a few rows

The local master CSV currently has **Family in C**, **Scientific Name in G**, and **catalogNumber in N**. Confirm those headers in the sheet you choose: column positions can change after copying or inserting columns.

In a new, unused cell on row 2 of the native Google Sheet, use:

```text
=HYPERLINK("PASTE_DEPLOYED_EXEC_URL_HERE?e="&ENCODEURL(N2)&"&family="&ENCODEURL(C2)&"&species="&ENCODEURL(G2),"View transcription")
```

Replace only `PASTE_DEPLOYED_EXEC_URL_HERE` with the complete deployment URL. Keep `?e=` and the rest of the formula. Adapt the row number/columns if needed. Fill just two or three test rows first. These formulas construct links; they do not search Drive or read a report until clicked.

The URL itself also works as an ordinary hyperlink in the Excel master. If copying a formula/link between the native Sheet and the Excel file does not preserve it, construct the URL in the native Sheet using:

```text
="PASTE_DEPLOYED_EXEC_URL_HERE?e="&ENCODEURL(N2)&"&family="&ENCODEURL(C2)&"&species="&ENCODEURL(G2)
```

Use that resulting URL as the target of an ordinary hyperlink in the Excel file. The viewer runs separately from Excel.

Preserve E-numbers as text when leading zeros are meaningful. The viewer distinguishes E001 from E1, but cannot restore zeros already lost by the spreadsheet.

E-number-only links are also supported:

```text
=HYPERLINK("PASTE_DEPLOYED_EXEC_URL_HERE?e="&ENCODEURL(N2),"View transcription")
```

The longer existing formula remains faster because it supplies the report location directly. E-number-only links use the latest synced CSV export for that location, not live edits to the Excel master.

## Pilot checks

- Open a row known to have a saved **species report**. Compare the complete displayed text with that report, including backs, annotations and uncertainties.
- Open a row without a matching report. It should say no transcription is available. If the family folder is missing or inaccessible, it should instead explain that the search could not be completed.
- When an ordinary authorized transcription run later creates a report and Drive finishes syncing it, open the **same link** again. No regeneration of links is needed. Do not make a paid transcription request solely to verify this viewer.
- Check a shared slip, a record with review notes, and a catalogue-only `(MISSING)` entry if available.
- Check the final numbered card of a report: technical header fields and the report usage footer should be absent from the viewer.
- A newer species report might cover a different row range. The viewer searches backward until it finds the requested E-number.

## What the pilot reads and displays

- Resolves omitted family/species from the catalogue CSV, then searches **directly inside the matching family directory**, where the current Python application saves reports. The form submits only the E-number; existing full links bypass this lookup.
- Reads only `Species_transcriptions_YYYYMMDD_HHMM.txt` and collision variants such as `..._2.txt`. It excludes journals, mixed-species test reports, and individual `!` / `@` reports in this first pilot.
- Orders by the timestamp in the filename, then the numeric collision counter. Drive modification time is not used. Duplicate filenames/timestamps produce an explicit ambiguity error.
- Matches complete CM catalogue banners, preserves leading zeros, and returns all matching blocks from that report. Consecutive shared-slip banners retain their complete common body. Duplicate catalogue-only rows remain separate.
- Omits the technical header (model, build, prompt, hashes, settings, token/cost accounting) as a unit. It does not globally delete matching words from the historical transcription.
- Preserves card fields, annotations, all supplied backs, uncertainty, and transcription notes. Review reasons remain visible except standalone notes-presence flags, which no longer cause a review warning by themselves.
- Labels `OK` as structural acceptance, not human verification. A newer `FAILED`, `PAUSED`, `MISSING`, or malformed matching record does not silently become an older successful reading. Available failed response text remains visible, with service/debug error text omitted.
- Shows **report date**, not a claimed date of fresh transcription. Reused readings are identified.
- Uses Google's escaped HTML printing for all text and links. The **Open source report** link opens the original unfiltered report, which still contains its technical metadata.

Catalogue CSV reads are limited to 10 MiB. This pilot reads at most 40 candidate reports, lists at most 5,000 files in one family directory, accepts reports up to 10 MiB, and checks a 45-second elapsed-time budget between Drive operations. These are explicit limits in `Code.gs`; reaching one reports an **incomplete search**, never a false “not available.” A single slow Drive call can still exceed the elapsed-time budget.

No persistent transcription cache or index is used. Drive indexing/sync delays can affect when a new report becomes visible. Report timestamps are the report writer's local wall time, so clock/time-zone changes on the writing computer affect their ordering.

## Share after testing

For staff access, retain **Execute as: User accessing the web app** and choose an appropriate signed-in audience permitted by the institution's Google account policy. Each reader needs access to the report folders and, for E-number-only searches, the catalogue CSV; they must authorize the viewer. Do not switch to “execute as me” merely to bypass another user's missing file access.

For later code changes, update the existing deployment via **Deploy → Manage deployments → Edit → New version**, retaining its /exec URL so spreadsheet links remain valid. Creating a separate deployment produces a different URL.

## Offline verification

From the repository root:

```text
node --test apps_script/transcription_viewer/test_viewer.cjs
python -m unittest -v test_transcribe.py
```

The viewer tests use synthetic Drive objects and replay the card blocks in an existing tracked sample report. They make no network requests. The Python suite remains the regression suite for the existing transcription application.

Implementation references: [web app deployment and execution identity](https://developers.google.com/apps-script/guides/web), [escaped template printing](https://developers.google.com/apps-script/guides/html/templates), [read-only Drive file access](https://developers.google.com/apps-script/reference/drive/file).
