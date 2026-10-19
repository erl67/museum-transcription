# Egg Slip Record Search

Spreadsheet links open this viewer and retrieve the latest available species report at click time. The form accepts an E-number alone and reads its family/species from the catalogue CSV export in Drive; existing links with family and scientific name still work. The page shows record text first, then displays full-resolution scans as each finishes loading. If no transcription exists, it finds available scans by the complete E-number and keeps each physical card’s sides together.

No transcription text is stored in the spreadsheet, hidden sheets, script properties, or a persistent cache. The viewer reads existing Drive files and makes no transcription-service requests. A link can be created before a record has been transcribed; opening it again after a report has synced searches afresh.

## Open Egg Slip Record Search

[Open Egg Slip Record Search](https://script.google.com/macros/s/AKfycbzisn0ISa_2hwEh_vIaQporGeXxruTwscyAOalTgubqPV9EXvkleFlXyKx8aTezEa6EyA/exec?).

Share or bookmark the deployed web-app URL ending in **/exec** to open **Egg Slip Record Search** directly. Readers do not need to open the spreadsheet first. The page heading is **Egg-slip transcription / scan viewer**, with the instruction **Enter an E-number to view the available transcription and card scans.** The empty E-number field shows **E5350** as an example; it is a placeholder rather than a preselected record. Enter up to five digits with or without the E prefix (for example, **E10215** or **10215**) and choose **Find record**. The field allows at most six characters and validates the optional E followed by one to five digits. After a search, the field is empty and ready for another number.

The browser tab is titled **Egg Slip Record Search** on the initial search page and when a search returns an error. A successful lookup uses the normalized E-number, for example **E4268 Egg Slip Record**. That title also applies when only scans or catalogue information are available. Leading zeros remain part of the title, so E001 is shown as **E001 Egg Slip Record**.

Viewer.html is Apps Script template source. Opening the local HTML file directly previews the layout but does not run the search, evaluate template expressions, or load Drive scans. Use the deployed **/exec** URL for the working viewer. Paste the HTML source into the Apps Script HTML file named **Viewer**, and the JavaScript source into **Code.gs**.

## Access for people who can open the master Excel file

The deployment accepts signed-in Google accounts and runs as **the user accessing the web app**. Before showing a search or reading reports, it checks that account can read the configured master workbook in Drive. Direct permissions, Google Group membership, and inherited access are evaluated by Google Drive. The workbook check runs on every page request and again on every image-loading request, so the application does not maintain a separate user list.

The access check uses the [master Excel workbook](https://docs.google.com/spreadsheets/d/1P-sWhtIlRHcbh4D5rV0p0sv-MF_Th1lc/edit?gid=1539383110), identified by WORKBOOK_FILE_ID. The viewer reads only workbook metadata for this access check; catalogue lookup uses the separate CSV export. Update WORKBOOK_FILE_ID if the master file is replaced.

Workbook sharing does not automatically share separate data folders. To let the same readers use the whole viewer:

1. Keep the master Excel file shared with the intended people or Google Group.
2. Share the **Family root folder**, including its reports and JPEG subfolders, with the same people/group as **Viewer**.
3. Share the **catalogue CSV** with the same people/group as **Viewer**. For automatic discovery, readers also need access to the `Egg Slip Scanning` parent folder; alternatively set CATALOGUE_FILE_ID to the CSV’s Drive file ID to avoid parent-folder discovery.
4. Deploy with **Execute as: User accessing the web app** and **Who has access: Anyone with a Google account**. The manifest represents these settings as USER_ACCESSING and ANYONE.
5. Readers sign in with the account used for the master Excel file and authorize the viewer's read-only Drive access.

The broad signed-in deployment audience lets the app check external collaborators as well as institutional accounts. The workbook check still runs before any report or scan is read. Keep the execution identity set to the accessing user; the check relies on that identity. Institutional Google Workspace policies may limit the audience options or external-account authorization.

These source files do not change Google Drive sharing or copy the workbook's permissions to other files. Apply the matching folder sharing in Drive. Using one Google Group for the workbook, CSV, and Family data makes future membership changes easier to manage. Sharing the Apps Script project's source with every reader is not required.

See [Google's execution-permission documentation](https://developers.google.com/apps-script/guides/web#permissions), [web-app manifest settings](https://developers.google.com/apps-script/manifest/web-app-api-executable), and [Drive file/folder sharing](https://support.google.com/drive/answer/7166529).

## Install or update the viewer

Use a separate Apps Script project from the Egg Scan Linker.

1. Open [Google Apps Script](https://script.google.com/) with the maintaining account. For a new project, name it **Egg Slip Record Search**.
2. Replace **Code.gs** with [Code.gs](Code.gs).
3. Add or replace the HTML file named **Viewer** using [Viewer.html](Viewer.html).
4. In **Project Settings**, enable **Show appsscript.json manifest file in editor** and replace it with [appsscript.json](appsscript.json). New installations need all three source files. This revision changes Code.gs and Viewer.html; an existing manifest matching the supplied file can stay as it is. The OAuth scope remains read-only Drive access.
5. Confirm WORKBOOK_FILE_ID, ROOT_FOLDER_ID, and CATALOGUE_FILE_ID near the top of Code.gs. ROOT_FOLDER_ID identifies the Family root, not a species or JPEG folder. CATALOGUE_FILE_ID is prefilled with the maintainer's supplied CSV ID; update it if the CSV is replaced by a new Drive file.
6. For an existing deployment, save and choose **Deploy → Manage deployments → Edit (pencil) → Version: New version → Deploy**. Check the execution identity and audience settings described above. Keep the existing deployment URL so spreadsheet links stay valid.
7. For a first deployment, choose **Deploy → New deployment → Web app**, use the settings above, and copy the resulting URL ending in **/exec**.

Saving source alone does not update a versioned /exec deployment. Do not upload this README or the test file as Apps Script source. Running doGet in the editor does not open the viewer; use the deployed URL.

## CSV lookup and direct viewer links

The master Excel workbook remains the authoritative catalogue and access gate. E-number lookup now reads its **UTF-8 CSV export**, avoiding XLSX download, unzip, and XML parsing. The existing export is:

~~~text
G:\My Drive\Egg Slip Scanning\EggSlipReorganizationProject_FULL.xlsx - Full List.csv
~~~

Apps Script uses the corresponding Drive file, not the Windows drive letter. With CATALOGUE_FILE_ID blank, it searches for the exact configured filename beside the Family root and inside its sibling `Transcription` folder. It deduplicates the same file ID and rejects multiple different matching files. It does not choose an arbitrary export.

Configuration in Code.gs:

- WORKBOOK_FILE_ID: **1P-sWhtIlRHcbh4D5rV0p0sv-MF_Th1lc**, used for access checks only.
- ROOT_FOLDER_ID: the existing **Family** folder containing species reports and JPEG directories.
- CATALOGUE_FILE_ID: **1AOoNhjdyvNHZUxf11WwM1VMPuzdDOA8I**, the maintainer's supplied [CSV file](https://drive.google.com/file/d/1AOoNhjdyvNHZUxf11WwM1VMPuzdDOA8I/view). This avoids CSV discovery on each search and allows readers to use the shared CSV without browsing its parent folder. Use the CSV's ID, not either workbook or a converted Google Sheet. Replacing a file with a new Drive file requires updating this ID. Leaving it blank retains automatic discovery.
- CATALOGUE_FILE_NAME: **EggSlipReorganizationProject_FULL.xlsx - Full List.csv**.
- CATALOGUE_FOLDER_NAME: **Transcription**, the additional sibling location supported for existing installations.

The CSV needs exactly one column each named **catalogNumber**, **Family**, and **Scientific Name**. Columns may move and surrounding header whitespace is ignored. The full existing export works; a separate compact export containing only these columns also works if explicitly configured. Duplicate rows agreeing on family/species work; conflicting or incomplete matches, extra columns beyond the header, unreadable exports, and ambiguous locations produce explicit errors. UTF-8 with or without a BOM, quoted commas, and quoted line breaks are supported.

Refresh the export after catalogue changes. Saving the Excel workbook alone does not refresh the CSV. Every E-number search checks the CSV's current access, type, size and modification time. The first search downloads/parses the export and temporarily caches only catalogNumber, Family and Scientific Name for that reader. Subsequent searches can reuse those lookup rows for up to 15 minutes. A changed file ID, size or modification time immediately selects a new cache identity. A missing/evicted cache entry or cache-service failure falls back to reading the CSV. No workbook-access decision, transcription text or image bytes are cached.

The lookup is divided into 64 independent cache entries; each is conservatively limited to 24,000 UTF-16 code units, below Google's 100 KB per-entry limit. Oversized entries simply use the uncached path. Duplicate rows and their conflicts are preserved; malformed headers or extra columns anywhere in the export prevent a cache from being populated. E-numbers retain their complete digits: `E001` and `E1` are different. The viewer cannot recover zeros lost during export and does not create, replace or synchronize the CSV. Python continues to use its configured local CSV unchanged.

To share the viewer independently of the spreadsheet, use the deployment URL ending in **/exec**, with no query string. Readers enter an E-number in the form. A direct link ending in **/exec?e=E4268** opens that record. The same sharing and authorization requirements apply.

The known catalogue columns are **Family in C**, **Scientific Name in G**, and **catalogNumber in N**. Confirm these headers if columns have moved. On row 2, a direct-location link is:

~~~text
=HYPERLINK("PASTE_DEPLOYED_EXEC_URL_HERE?e="&ENCODEURL(N2)&"&family="&ENCODEURL(C2)&"&species="&ENCODEURL(G2),"View transcription")
~~~

An E-number-only link is also supported:

~~~text
=HYPERLINK("PASTE_DEPLOYED_EXEC_URL_HERE?e="&ENCODEURL(N2),"View transcription")
~~~

Replace only PASTE_DEPLOYED_EXEC_URL_HERE with the complete deployment URL. Keep the **?e=** delimiter. Adapt row references and fill down as needed. The longer link uses the supplied family/species without reading CSV contents; use E-number-only links to pick up refreshed CSV corrections. Both link types require master-workbook access.

An ordinary hyperlink to the resulting URL also works in the Excel file. If copying formulas between the native Sheet and Excel loses the link, build the URL in the native Sheet and use it as the target of an ordinary hyperlink.

Keep meaningful leading zeros as text: E001 and E1 are different records. Check that exported values retain their zeros; spreadsheet display formatting alone is not a guarantee. Submitting the form sends only its E-number, so a new search does not inherit an old record's family/species.

## Transcription and source-scan display

- Reads normal species reports directly in the matching family directory, newest first by filename timestamp and numeric collision counter, until the exact CM number is found. It excludes journals, mixed-species test reports, and individual ! / @ reports.
- Keeps shared-slip numbers and their complete common text together. Duplicate catalogue-only rows remain separate.
- Preserves historical wording, partial dates, annotations, supplied backs, uncertainty, and transcription notes.
- Omits technical report headers and usage footers. Source words matching technical field names are not globally deleted.
- Notes presence alone does not trigger a review warning. Other reasons and unexplained REVIEW statuses remain flagged. OK means structural acceptance, not human verification.
- A newest matching FAILED, PAUSED, MISSING, or malformed record does not silently become an older successful reading. Available failed response text stays visible; service/debug error details are omitted.
- Shows the report date, not a claimed date of fresh transcription, and identifies reused readings.
- When a transcription exists (including failed/paused attempts), returns only the source JPGs listed in that report’s FILES header. Scan discovery rereads the displayed report by ID, verifies its family/species and checks its record/file manifest. A newer report arriving meanwhile cannot replace its scans. Individual image requests check the pinned report's name, parent, size and modification time; any subsequent report edit or move requires a page reload. Deleted or inaccessible files produce image-load errors. Images show current files at those filenames, not guaranteed archived versions from the report date.
- When no matching report exists, or the matching blocks are all catalogue-only MISSING records, searches the routed species JPEG folder by complete E-number. These current scans are displayed separately and explicitly identified as having no image transcription. Existing catalogue-only text/status remains unchanged. Shared slips match any complete number; leading zeros remain significant; distinct physical cards stay separate. Invalid/duplicate sides are reported without selecting an arbitrary image. Malformed matching names and missing/ambiguous folders are explicit messages, not evidence of absent cards.
- Displays scans in report order as Front, Back, Back 2, and further supplied sides. A lone back remains Back; missing sides are not invented.
- Resolves both Family/family/species/JPEG and Family/family/genus/species/JPEG layouts, with case-insensitive folder matching and exact source-filename matching.
- Returns text and a loading indicator before reading JPG bytes. After page load, `loadSourceScans` returns an ordered gallery and file metadata. The browser reserves each scan's position and calls `loadSourceImage` with at most two downloads active. Each completed full JPEG appears immediately in its original position, even when downloads finish out of order. Captions use plain text and link each original JPG. Retry reloads failed images while retaining successful images and record text.
- Temporarily caches the server-derived scan plan for that reader for up to 10 minutes. It contains folder/file metadata and record/file references, never report bodies or image bytes. Individual image requests still recheck workbook access, report metadata, folder names/parents, exact filename uniqueness and image identity/size/modification time under the accessing user. A cache miss rebuilds and compares the plan before reading bytes. Changed sources require a reload rather than substituting other scans. Folder choices are pinned for the displayed gallery; a new search checks directory ambiguity afresh. Within discovery, the direct-species and genus searches share one family-subfolder listing.
- Uses the existing full-resolution JPGs, with no thumbnails, resizing, public image host, new OAuth scope or sharing changes. Progressive loading improves time to the first available image; it does not reduce total image bytes, and additional per-image requests can affect total completion time.
- Keeps transcription visible if scans are missing, ambiguous, unreadable, or too large. Catalogue-only blocks may now have a separate gallery of current scans found by E-number.
- Uses escaped HTML printing for text and links. Opening the original source report shows its unfiltered technical metadata.

## Limits and verification

The viewer reads at most **40 candidate reports**, lists at most **5,000 family-directory files**, accepts CSV exports and reports up to **10 MiB** each, and checks a separate **45-second** elapsed-time budget for text lookup, scan discovery and each image request between Drive operations. Reaching a report-search limit produces an explicit incomplete-search message. One slow Drive operation can itself exceed the elapsed-time budget. Scan-folder traversal limits each child-folder listing to **5,000 folders**. Scan-only discovery lists at most **5,000 files** and accepts at most **40 matching JPEGs**; limit errors explicitly report an incomplete search. Missing, inaccessible, or ambiguous directories do not become “no scans found.”

Source images are limited to **12 MiB each**, **24 MiB total planned image bytes per page**, and **40 images**. The plan reserves each eligible file's full size before downloads start; an image whose actual byte length or version changes is rejected. Failed reservations are not reassigned to other images during the page load. When a file is found but cannot be embedded, its original Drive link remains available. Image failures do not replace the selected transcription.

## Measure loading times after deployment

Server logs contain `Viewer timing` JSON for `text`, `scanPlan` and `image` executions. Inspect them in Apps Script's **Executions** view. Text stages include access, CSV file discovery, CSV download/parsing/cache reads/writes, family lookup, report listing/download/selection and template rendering. Counts include catalogue-cache hits, files listed and reports read. Image stages include scan-plan cache hits, source validation, JPEG download/encoding and original byte count. Nested stage durations overlap; do not add them together. No catalogue values, report text, image content, filenames, IDs or account identifiers are included in timing logs.

The browser developer console also logs `Viewer text timing`, `Viewer scan discovery`, `Viewer image timing`, `Viewer first image displayed` and `Viewer image requests finished`. Browser scan elapsed times start when the page's script runs, after the text response arrives. Per-image elapsed times include the RPC round trip; the first-image measurement includes JPEG decoding/display readiness. The text timing copied into the page precedes template rendering; the server's final text log includes it. These figures do not include all of Google's navigation, authorization or startup overhead, so also measure **Find record → visible text** with a stopwatch.

Compare an initial E-number-only search with several different E-numbers in the same account shortly afterwards. A warm cache should show `catalogueCacheHit: true` and no CSV download/parse stage. Record time to text, first full image and all images separately, using the same representative cards and network. Verify a refreshed export invalidates the cache and a new report still appears on the next search. The offline tests verify removed reads and progressive behavior; they cannot establish a five-second production lookup or a specific speedup.

Drive sync delays affect new reports and scans. Filename timestamps use the report writer's local wall time, so clock/time-zone changes on that computer affect ordering.

Check the deployed app with a second account that has the workbook, CSV, and Family sharing. Confirm an E-number-only search uses the CSV, and a full-location link works without reading it. Confirm text appears with a loading indicator before scans arrive. Test a record without a report, a shared slip, a lone back, a catalogue-only block whose scans have since arrived, and a missing/ambiguous scan folder. Confirm source links work and image failure/retry leaves text intact. A denied account must receive no report/scan data, including when access is revoked before the image request. After the next intended catalogue correction, refresh the CSV and confirm a fresh search sees it. No paid transcription request is needed for these checks.

From the local repository root, run:

~~~text
node --test apps_script/transcription_viewer/test_viewer.cjs
python -m unittest -v test_transcribe.py
~~~

The viewer tests use synthetic Drive objects, CSV fixtures parsed through Python’s standard library, a deferred browser-RPC/DOM adapter, and existing local saved responses. Node.js and Python are required for these offline tests; no third-party test package is needed. They make no network requests. Local browser checks cover initial text/loading, asynchronous success/failure/retry, centering, mobile layout, and image-error fallback. Real Google authorization, group propagation, sharing, deployment settings, and native template rendering must be checked in the deployed account.

CSV parsing uses [Apps Script CSV support](https://developers.google.com/apps-script/reference/utilities/utilities#parseCsv(String)). Deferred image loading uses [HTML service asynchronous communication](https://developers.google.com/apps-script/guides/html/communication). Reducing initial Drive reads follows [Google’s performance guidance](https://developers.google.com/apps-script/guides/support/best-practices); no live speed measurement is claimed.

Implementation references: [deployment versions](https://developers.google.com/apps-script/concepts/deployments), [escaped template printing](https://developers.google.com/apps-script/guides/html/templates), [Drive file access](https://developers.google.com/apps-script/reference/drive/file).
