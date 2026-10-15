# Egg Transcription Viewer

Spreadsheet links open this viewer and retrieve the latest available species report at click time. The form accepts an E-number alone and reads its family/species from the saved master Excel workbook in Drive; existing links with family and scientific name still work. Source scans appear below the transcription, centered and labelled by side.

No transcription text is stored in the spreadsheet, hidden sheets, script properties, or a persistent cache. The viewer reads existing Drive files and makes no transcription-service requests. A link can be created before a record has been transcribed; opening it again after a report has synced searches afresh.

## Access for people who can open the master Excel file

The deployment accepts signed-in Google accounts and runs as **the user accessing the web app**. Before showing a search or reading reports, it checks that account can read the configured master workbook in Drive. Direct permissions, Google Group membership, and inherited access are evaluated by Google Drive. The workbook check runs on every page request, so the application does not maintain a separate user list.

The catalogue and access check use the same [master Excel workbook](https://docs.google.com/spreadsheets/d/1P-sWhtIlRHcbh4D5rV0p0sv-MF_Th1lc/edit?gid=1539383110), identified by WORKBOOK_FILE_ID. No CSV file or common-parent-folder access is needed by the viewer. Update the ID if the master file is replaced.

Workbook sharing does not automatically share separate data folders. To let the same readers use the whole viewer:

1. Keep the master Excel file shared with the intended people or Google Group.
2. Share the **Family root folder**, including its reports and JPEG subfolders, with the same people/group as **Viewer**.
3. Deploy with **Execute as: User accessing the web app** and **Who has access: Anyone with a Google account**. The manifest represents these settings as USER_ACCESSING and ANYONE.
4. Readers sign in with the account used for the master Excel file and authorize the viewer's read-only Drive access.

The broad signed-in deployment audience lets the app check external collaborators as well as institutional accounts. The workbook check still runs before any report or scan is read. Keep the execution identity set to the accessing user; the check relies on that identity. Institutional Google Workspace policies may limit the audience options or external-account authorization.

These source files do not change Google Drive sharing or copy the workbook's permissions to other files. Apply the matching folder sharing in Drive. Using one Google Group for both the workbook and Family data makes future membership changes easier to manage. Sharing the Apps Script project's source with every reader is not required.

See [Google's execution-permission documentation](https://developers.google.com/apps-script/guides/web#permissions), [web-app manifest settings](https://developers.google.com/apps-script/manifest/web-app-api-executable), and [Drive file/folder sharing](https://support.google.com/drive/answer/7166529).

## Install or update the viewer

Use a separate Apps Script project from the Egg Scan Linker.

1. Open [Google Apps Script](https://script.google.com/) with the maintaining account. For a new project, name it **Egg Transcription Viewer**.
2. Replace **Code.gs** with [Code.gs](Code.gs).
3. Add or replace the HTML file named **Viewer** using [Viewer.html](Viewer.html).
4. In **Project Settings**, enable **Show appsscript.json manifest file in editor** and replace it with [appsscript.json](appsscript.json). This update needs all three installation files. The OAuth scope remains read-only Drive access.
5. Confirm WORKBOOK_FILE_ID, ROOT_FOLDER_ID, and CATALOGUE_SHEET_NAME near the top of Code.gs. ROOT_FOLDER_ID identifies the Family root, not a species or JPEG folder.
6. For an existing deployment, save and choose **Deploy → Manage deployments → Edit (pencil) → Version: New version → Deploy**. Check the execution identity and audience settings described above. Keep the existing deployment URL so spreadsheet links stay valid.
7. For a first deployment, choose **Deploy → New deployment → Web app**, use the settings above, and copy the resulting URL ending in **/exec**.

Saving source alone does not update a versioned /exec deployment. Do not upload this README or the test file as Apps Script source. Running doGet in the editor does not open the viewer; use the deployed URL.

## Master catalogue and spreadsheet links

The viewer reads the **saved .xlsx file in Google Drive** directly. It does not need Apps Script to run inside the Excel file, does not convert or copy the workbook, and does not read the exported CSV.

Configuration in Code.gs:

- WORKBOOK_FILE_ID: **1P-sWhtIlRHcbh4D5rV0p0sv-MF_Th1lc** (the supplied master workbook).
- CATALOGUE_SHEET_NAME: **Full List**, taken from the existing export's tab name. Confirm the visible tab has this exact name; update this setting if it was renamed.
- ROOT_FOLDER_ID: the existing **Family** folder containing species reports and JPEG directories.

The selected tab must have exactly one column each named **catalogNumber**, **Family**, and **Scientific Name** in its first nonempty row. Columns may move. Only these values for the requested E-number are used; duplicate rows that agree on family/species work, while conflicting or incomplete matches produce an error. The browser's gid is not used as an Excel worksheet number.

Every E-number-only search reads the saved workbook again. Save online edits before searching; changes still being saved or synced are not yet available. Formula cells use their saved results: the viewer does not recalculate Excel formulas. If a lookup formula has no saved result, recalculate and save the workbook. Shared strings, inline/rich text, and simple numeric zero-padding formats are supported. Store E-numbers as text for unambiguous digits. A shortcut, legacy .xls file, encrypted workbook, or converted native Google Sheet is not this .xlsx source; unsupported types fail explicitly rather than falling back to an old CSV.

**Python follow-up:** the maintainer wants this same online workbook to be the catalogue source for the local transcription program too. That change is deferred to a separate conversation. Python still reads its configured local CSV in this revision; do not remove its export until that migration is implemented.

The known catalogue columns are **Family in C**, **Scientific Name in G**, and **catalogNumber in N**. Confirm these headers if columns have moved. On row 2, a direct-location link is:

~~~text
=HYPERLINK("PASTE_DEPLOYED_EXEC_URL_HERE?e="&ENCODEURL(N2)&"&family="&ENCODEURL(C2)&"&species="&ENCODEURL(G2),"View transcription")
~~~

An E-number-only link is also supported:

~~~text
=HYPERLINK("PASTE_DEPLOYED_EXEC_URL_HERE?e="&ENCODEURL(N2),"View transcription")
~~~

Replace only PASTE_DEPLOYED_EXEC_URL_HERE with the complete deployment URL. Keep the **?e=** delimiter. Adapt row references and fill down as needed. The longer link uses the supplied family/species without reading catalogue contents; use E-number-only links to pick up saved catalogue corrections. Both link types require master-workbook access.

An ordinary hyperlink to the resulting URL also works in the Excel file. If copying formulas between the native Sheet and Excel loses the link, build the URL in the native Sheet and use it as the target of an ordinary hyperlink.

Keep meaningful leading zeros as text: E001 and E1 are different records. Simple 000-style or E-prefixed zero-padding formats are also preserved, but the viewer cannot restore zeros already lost by the spreadsheet. Submitting the form sends only its E-number, so a new search does not inherit an old record's family/species.

## Transcription and source-scan display

- Reads normal species reports directly in the matching family directory, newest first by filename timestamp and numeric collision counter, until the exact CM number is found. It excludes journals, mixed-species test reports, and individual ! / @ reports.
- Keeps shared-slip numbers and their complete common text together. Duplicate catalogue-only rows remain separate.
- Preserves historical wording, partial dates, annotations, supplied backs, uncertainty, and transcription notes.
- Omits technical report headers and usage footers. Source words matching technical field names are not globally deleted.
- Notes presence alone does not trigger a review warning. Other reasons and unexplained REVIEW statuses remain flagged. OK means structural acceptance, not human verification.
- A newest matching FAILED, PAUSED, MISSING, or malformed record does not silently become an older successful reading. Available failed response text stays visible; service/debug error details are omitted.
- Shows the report date, not a claimed date of fresh transcription, and identifies reused readings.
- Returns only the source JPGs listed in that report's FILES header. Newly added scans are not attached to an older transcription. Images show current files at those filenames, not guaranteed archived versions from the report date.
- Displays scans in report order as Front, Back, Back 2, and further supplied sides. A lone back remains Back; missing sides are not invented.
- Resolves both Family/family/species/JPEG and Family/family/genus/species/JPEG layouts, with case-insensitive folder matching and exact source-filename matching.
- Reads image bytes with the accessing user's Drive permissions, embeds them transiently in the returned page, and links to each original Drive JPG. No public image host or public-sharing change is required.
- Keeps transcription visible if scans are missing, ambiguous, unreadable, or too large. Catalogue-only MISSING blocks do not receive a source gallery.
- Uses escaped HTML printing for text and links. Opening the original source report shows its unfiltered technical metadata.

## Limits and verification

The viewer reads at most **40 candidate reports**, lists at most **5,000 family-directory files**, accepts master Excel files up to **25 MiB**, parsed workbook XML parts up to **80 MiB combined**, and reports up to **10 MiB**, and checks a **45-second** elapsed-time budget between Drive operations. Reaching a report-search limit produces an explicit incomplete-search message. One slow Drive operation or workbook unzip/XML operation can itself exceed the elapsed-time budget. Large workbooks can take longer to search because they are read fresh, without a persistent catalogue cache.

Source images are limited to **12 MiB each**, **24 MiB total bytes per page**, and **40 images**. When a file is found but cannot be embedded, its original Drive link remains available. Image failures do not replace the selected transcription.

Drive sync delays affect new reports and scans. Filename timestamps use the report writer's local wall time, so clock/time-zone changes on that computer affect ordering.

Check the deployed app with a second account that has the same Excel and Family sharing. Confirm the catalogue tab is Full List. After the next intended catalogue correction is saved, confirm a fresh E-number-only search sees it. Confirm it can search E382 and another family, display fronts/backs, and open originals. Check a denied account receives an access message without report/scan data. Check notes-only, genuine review, shared-slip, catalogue-only, and unavailable-scan examples. Reopen the same link after an ordinary authorized run later creates a report; no new paid request is needed solely to test the viewer.

From the local repository root, run:

~~~text
node --test apps_script/transcription_viewer/test_viewer.cjs
python -m unittest -v test_transcribe.py
~~~

The viewer tests use synthetic Drive objects, real in-memory XLSX ZIP/XML fixtures parsed through Python's standard library, and existing local saved responses. Node.js and Python are required for these offline tests; no third-party test package is needed. They make no network requests. Local browser checks cover centering, mobile layout and image-error fallback. Real Google authorization, group propagation, sharing, deployment settings, and native template rendering must be checked in the deployed account.

Workbook reading uses [Apps Script ZIP support](https://developers.google.com/apps-script/reference/utilities/utilities#unzip(BlobSource)) and [XML parsing](https://developers.google.com/apps-script/reference/xml-service), following [Microsoft's SpreadsheetML structure](https://learn.microsoft.com/en-us/office/open-xml/spreadsheet/structure-of-a-spreadsheetml-document) and [shared-string rules](https://learn.microsoft.com/en-us/office/open-xml/spreadsheet/working-with-the-shared-string-table).

Implementation references: [deployment versions](https://developers.google.com/apps-script/concepts/deployments), [escaped template printing](https://developers.google.com/apps-script/guides/html/templates), [Drive file access](https://developers.google.com/apps-script/reference/drive/file).
