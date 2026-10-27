# Egg Slip Record Search

Spreadsheet links open this viewer and retrieve the latest available species report at click time. The form accepts an E-number alone and reads its family/species from the catalogue CSV export in Drive; existing links with family and scientific name still work. The page shows record text first, then displays full-resolution scans as each finishes loading. If no transcription exists, it finds available scans by the complete E-number and keeps each physical card’s sides together.

No transcription text is stored in the spreadsheet, hidden sheets, script properties, or a persistent cache. The viewer reads existing Drive files and makes no transcription-service requests. A link can be created before a record has been transcribed; opening it again after a report has synced searches afresh.

## Open Egg Slip Record Search

[Open Egg Slip Record Search at cmbirds.org/eggs](https://cmbirds.org/eggs).

Use **https://cmbirds.org/eggs** as the canonical link for opening, sharing and bookmarking **Egg Slip Record Search**. Readers do not need to open the spreadsheet first. The page heading is **Egg-slip transcription / scan viewer**, with the instruction **Enter an E-number to view the available transcription and card scans.** The E-number field is blank, with no example placeholder. Enter up to five digits with or without the E prefix (for example, **E10215** or **10215**) and choose **Find record**. The field allows at most six characters and validates the optional E followed by one to five digits. After a search, the field is empty and ready for another number.

The browser tab is titled **Egg Slip Record Search** on the initial search page and when a search returns an error. A successful lookup uses the normalized E-number, for example **E4268 Egg Slip Record**. That title also applies when only scans or catalogue information are available. Leading zeros remain part of the title, so E001 is shown as **E001 Egg Slip Record**.

A footer below the transcription and source scans links to this project's GitHub source, gives the maintainer's contact address, and states that the website is independently created and maintained, is not owned, operated, sponsored, or endorsed by the museums, and does not represent official museum communications or institutional positions. The content area is at least one viewport tall, followed by extra spacing, keeping the footer below the initial view even while scans are loading or on a short search/error page.

Viewer.html is Apps Script template source. Opening the local HTML file directly previews the layout but does not run the search, evaluate template expressions, or load Drive scans. Use [cmbirds.org/eggs](https://cmbirds.org/eggs) for the working viewer. Paste the HTML source into the Apps Script HTML file named **Viewer**, and the JavaScript source into **Code.gs**.

## Browse records

**Previous** and **Next** appear at the upper right beside the heading. Open a record first to enable them. Navigation follows alphabetical family, then alphabetical scientific name, then E-number in numerical order within that species. CSV row order and Drive listing order do not determine neighbours: E2 → E10 → E100 is the correct progression. At the end of a species, Next opens the lowest-numbered record in the next species; Previous reverses that order, including family transitions.

Every numbered catalogue entry is included, whether it has a completed transcription, a catalogue-only skeleton, scans without a report, or no available files yet. An unfinished entry keeps its E-number and family/species visible, with the existing transcription and scan availability messages. Navigation does not invent a transcription or create a missing-card block. Identical duplicate catalogue numbers at the same location give one navigation position, while their report blocks remain intact. Significant zeros are preserved: E001 and E1 remain distinct entries. Shared-slip numbers can each lead to the same shared card.

The buttons make ordinary page requests and work without client-side navigation scripts. Neighbour lookup runs only when a button is clicked, reusing the existing CSV routing cache in one batch when all entries are available. A missing or invalid bucket causes a fresh CSV read. The selected destination uses the normal, fresh report lookup and progressive scan loader. Ordinary searches do no extra adjacent-record work.

Navigation stops at the first/last catalogue record without wrapping. Attempting to go beyond an end leaves the current record visible, shows an endpoint message and disables that direction. Catalogue conflicts, incomplete routing, report problems or bounded-search failures produce explicit navigation messages while retaining the current record when it can still be read. A direct-location record absent from the catalogue can still be viewed, but needs a catalogue route before Previous/Next can place it in the sequence. The public stop switch and request budget are checked before any navigation lookup.

## Public access and publication boundary

Deploy with **Execute as: Me** and **Who has access: Anyone**, including visitors who are not signed in. The supplied manifest uses **USER_DEPLOYING** and **ANYONE_ANONYMOUS**. The deploying account authorizes read-only Drive access; visitors do not need workbook or Drive permissions. This replaces the former workbook-membership check, which cannot authenticate a visitor when the app runs as its deployer. See [Google's deployment settings](https://developers.google.com/apps-script/manifest/web-app-api-executable).

**The configured Family root is the publication boundary.** Matching species reports and JPEGs beneath it are available through the viewer, even if Drive labels them Restricted. Future matching files added there become available automatically. The catalogue exposes E-numbers and family/species routes; the raw CSV is not returned. Direct-location links may reach numbered records absent from the CSV, so the CSV is not a publication allowlist. Keep material that must remain private outside this root. No separate record-approval system is implied.

The maintainer chose to publish all existing record states: OK, REVIEW, FAILED, PAUSED, catalogue-only MISSING blocks, and scans without transcriptions. Retained failed/paused responses remain explicitly incomplete or unaccepted; structural OK still does not mean human verification. Existing report parsing and uncertainty are preserved.

Only the deploying account needs access to the Family root and catalogue CSV. Keep Drive sharing restricted if desired: the app serves the selected text and image bytes itself. Original report/JPG links continue to use Drive's own permissions and may ask visitors to sign in. Do not make the entire Drive folder public merely to enable these links. A separate deploying account with access only to the publication folder and CSV gives stronger isolation; the read-only OAuth scope limits modification but can read other files that account can access. Folder and file checks in this app restrict what it serves.

Install this viewer in its own project with only Code.gs, Viewer.html and appsscript.json. Do not combine it with the spreadsheet linker or other scripts with public write/admin functions. Keep project-editor access limited to maintainers. Workspace administrator policies may prevent anonymous deployment; the local files do not override those policies or update an existing deployment automatically.

## Emergency stop and request limits

In Apps Script **Project Settings → Script properties**, set **VIEWER_PUBLIC_DISABLED** to the exact value **true** to stop new page, scan-list and image requests without a new deployment. Remove the property or set it to **false** to reopen. Already delivered content cannot be recalled, and requests already past the check may finish. For a full shutdown, archive the deployment in **Manage deployments**.

Code.gs sets shared limits of **120 requests per UTC minute**, **3,000 requests per UTC day**, and **2 GiB of reserved JPEG bytes per UTC day**. These are configurable application limits, not Google's quota values or per-visitor allowances. Each page (including the empty form), scan-list call and individual image call consumes one request, including malformed requests and retries. Scan bytes are reserved immediately before download; failed downloads retain their reservation. Text searches remain usable after only the image-byte budget is exhausted.

Counters live in the fixed **VIEWER_PUBLIC_BUDGET_V1** script property. A script-wide lock makes reservations atomic across visitors and deployments of this project. Cache eviction and client-supplied identities do not reset counters. Corrupt/unavailable property storage or lock failures stop requests before Drive reads. Do not edit or delete counters routinely; after inspecting corrupt state, a maintainer can remove that property to initialize fresh counters, which deliberately resets the budget. Never put these controls in user properties or a per-browser cookie.

These controls limit admitted Drive work; they cannot prevent an attacker from invoking the app, using up the shared budget, or consuming Apps Script execution/property quotas with rejected requests. This is not denial-of-service protection or a guarantee of availability. Monitor **Executions** and adjust limits for observed use. See Google's [service quotas](https://developers.google.com/apps-script/guides/services/quotas), [script locks](https://developers.google.com/apps-script/reference/lock/lock-service), and [script properties](https://developers.google.com/apps-script/reference/properties/properties-service).

## Install or update the viewer

Use a separate Apps Script project from the Egg Scan Linker.

1. Open [Google Apps Script](https://script.google.com/) with the maintaining account. For a new project, name it **Egg Slip Record Search**.
2. Replace **Code.gs** with [Code.gs](Code.gs).
3. Add or replace the HTML file named **Viewer** using [Viewer.html](Viewer.html).
4. In **Project Settings**, enable **Show appsscript.json manifest file in editor** and replace it with [appsscript.json](appsscript.json). **Update all three files for this public-access revision.** The manifest changes execution identity/audience and retains only read-only Drive access.
5. Confirm ROOT_FOLDER_ID and CATALOGUE_FILE_ID near the top of Code.gs, and the public request/download limits. ROOT_FOLDER_ID identifies the Family root, not a species or JPEG folder. Confirm this is the material intended for publication. CATALOGUE_FILE_ID is prefilled with the maintainer's supplied CSV ID; update it if the CSV is replaced by a new Drive file. WORKBOOK_FILE_ID is no longer used.
6. For an existing deployment, save and choose **Deploy → Manage deployments → Edit (pencil) → Version: New version → Deploy**. Check the execution identity and audience settings described above. Keep the existing deployment URL so spreadsheet links stay valid.
7. For a first deployment, choose **Deploy → New deployment → Web app**, use the settings above, and copy the resulting URL ending in **/exec**.

Saving source alone does not update a versioned /exec deployment. The execution URL is used for deployment checks and direct record links; the canonical public access link remains [cmbirds.org/eggs](https://cmbirds.org/eggs). If the deployment URL changes, update the target behind the canonical link and check that it opens the current viewer. Do not upload this README or the test file as Apps Script source. Running doGet in the editor does not open the viewer.

## CSV lookup and direct viewer links

The master Excel workbook remains the authoritative catalogue. E-number lookup reads its **UTF-8 CSV export**, avoiding XLSX download, unzip, and XML parsing. The viewer does not open the workbook. The existing export is:

~~~text
G:\My Drive\Egg Slip Scanning\EggSlipReorganizationProject_FULL.xlsx - Full List.csv
~~~

Apps Script uses the corresponding Drive file, not the Windows drive letter. With CATALOGUE_FILE_ID blank, it searches for the exact configured filename beside the Family root and inside its sibling `Transcription` folder. It deduplicates the same file ID and rejects multiple different matching files. It does not choose an arbitrary export.

Configuration in Code.gs:

- ROOT_FOLDER_ID: the existing **Family** folder containing species reports and JPEG directories.
- CATALOGUE_FILE_ID: **1AOoNhjdyvNHZUxf11WwM1VMPuzdDOA8I**, the maintainer's supplied [CSV file](https://drive.google.com/file/d/1AOoNhjdyvNHZUxf11WwM1VMPuzdDOA8I/view). This avoids CSV discovery on each search and avoids needing to grant the deploying account access to the CSV's parent folder. Use the CSV's ID, not either workbook or a converted Google Sheet. Replacing a file with a new Drive file requires updating this ID. Leaving it blank retains automatic discovery.
- CATALOGUE_FILE_NAME: **EggSlipReorganizationProject_FULL.xlsx - Full List.csv**.
- CATALOGUE_FOLDER_NAME: **Transcription**, the additional sibling location supported for existing installations.

The CSV needs exactly one column each named **catalogNumber**, **Family**, and **Scientific Name**. Columns may move and surrounding header whitespace is ignored. The full existing export works; a separate compact export containing only these columns also works if explicitly configured. Duplicate rows agreeing on family/species work; conflicting or incomplete matches, extra columns beyond the header, unreadable exports, and ambiguous locations produce explicit errors. UTF-8 with or without a BOM, quoted commas, and quoted line breaks are supported.

Refresh the export after catalogue changes. Saving the Excel workbook alone does not refresh the CSV. Every E-number search checks the CSV's current access, type, size and modification time. The first search downloads/parses the export and temporarily caches only catalogNumber, Family and Scientific Name. Subsequent searches can reuse those lookup rows for up to 15 minutes. A changed file ID, size or modification time immediately selects a new cache identity. A missing/evicted cache entry or cache-service failure falls back to reading the CSV. No access decision, transcription text or image bytes are cached. UserCache is retained as an optimization, not visitor isolation or authorization; executing as the deployer means visitors must be treated as sharing execution resources.

The lookup is divided into 64 independent cache entries; each is conservatively limited to 24,000 UTF-16 code units, below Google's 100 KB per-entry limit. Oversized entries simply use the uncached path. Duplicate rows and their conflicts are preserved; malformed headers or extra columns anywhere in the export prevent a cache from being populated. E-numbers retain their complete digits: `E001` and `E1` are different. The viewer cannot recover zeros lost during export and does not create, replace or synchronize the CSV. Python continues to use its configured local CSV unchanged.

To share the viewer independently of the spreadsheet, use [cmbirds.org/eggs](https://cmbirds.org/eggs). Readers enter an E-number in the form. For direct record links, the deployment URL ending in **/exec?e=E4268** opens that record. The formulas below retain execution URLs for these record-specific requests; use the canonical link for general viewer access. Both are public after deploying the new version with the settings above.

The known catalogue columns are **Family in C**, **Scientific Name in G**, and **catalogNumber in N**. Confirm these headers if columns have moved. On row 2, a direct-location link is:

~~~text
=HYPERLINK("PASTE_DEPLOYED_EXEC_URL_HERE?e="&ENCODEURL(N2)&"&family="&ENCODEURL(C2)&"&species="&ENCODEURL(G2),"View transcription")
~~~

An E-number-only link is also supported:

~~~text
=HYPERLINK("PASTE_DEPLOYED_EXEC_URL_HERE?e="&ENCODEURL(N2),"View transcription")
~~~

Replace only PASTE_DEPLOYED_EXEC_URL_HERE with the complete deployment URL. Keep the **?e=** delimiter. Adapt row references and fill down as needed. The longer link uses the supplied family/species without reading CSV contents; use E-number-only links to pick up refreshed CSV corrections. Neither link type requires visitors to have workbook access.

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
- Temporarily caches the server-derived scan plan for up to 10 minutes. It contains folder/file metadata and record/file references, never report bodies or image bytes. Individual image requests still check the public stop switch/budget, report metadata, folder names/parents, exact filename uniqueness and image identity/size/modification time under the deployer's Drive permissions. The configured publication-root ID is part of the source key, so changing roots invalidates old plans. A cache miss rebuilds and compares the plan before reading bytes. Changed sources require a reload rather than substituting other scans. Folder choices are pinned for the displayed gallery; a new search checks directory ambiguity afresh. Within discovery, the direct-species and genus searches share one family-subfolder listing.
- Uses the existing full-resolution JPGs, with no thumbnails, resizing, public image host, new OAuth scope or sharing changes. Progressive loading improves time to the first available image; it does not reduce total image bytes, and additional per-image requests can affect total completion time.
- Keeps transcription visible if scans are missing, ambiguous, unreadable, or too large. Catalogue-only blocks may now have a separate gallery of current scans found by E-number.
- Uses escaped HTML printing for text and links. Opening the original source report shows its unfiltered technical metadata.

## Limits and verification

The viewer reads at most **40 candidate reports**, lists at most **5,000 family-directory files**, accepts CSV exports and reports up to **10 MiB** each, and checks a separate **45-second** elapsed-time budget for text lookup, scan discovery and each image request between Drive operations. Reaching a report-search limit produces an explicit incomplete-search message. One slow Drive operation can itself exceed the elapsed-time budget. Scan-folder traversal limits each child-folder listing to **5,000 folders**. Scan-only discovery lists at most **5,000 files** and accepts at most **40 matching JPEGs**; limit errors explicitly report an incomplete search. Missing, inaccessible, or ambiguous directories do not become “no scans found.”

Source images are limited to **12 MiB each**, **24 MiB total planned image bytes per page**, and **40 images**. The plan reserves each eligible file's full size before downloads start; an image whose actual byte length or version changes is rejected. Failed reservations are not reassigned to other images during the page load. When a file is found but cannot be embedded, its original Drive link remains available. Image failures do not replace the selected transcription.

## Measure loading times after deployment

Server logs contain `Viewer timing` JSON for `text`, `scanPlan` and `image` executions. Inspect them in Apps Script's **Executions** view. Text stages include access, CSV file discovery, CSV download/parsing/cache reads/writes, family lookup, report listing/download/selection and template rendering. Button requests additionally include `navigation` and `navigationCatalogue` stages. Counts include catalogue-cache hits, files listed and reports read. Image stages include scan-plan cache hits, source validation, JPEG download/encoding and original byte count. Nested stage durations overlap; do not add them together. No catalogue values, report text, image content, filenames, IDs or account identifiers are included in timing logs.

The browser developer console also logs `Viewer text timing`, `Viewer scan discovery`, `Viewer image timing`, `Viewer first image displayed` and `Viewer image requests finished`. Browser scan elapsed times start when the page's script runs, after the text response arrives. Per-image elapsed times include the RPC round trip; the first-image measurement includes JPEG decoding/display readiness. The text timing copied into the page precedes template rendering; the server's final text log includes it. These figures do not include all of Google's navigation, authorization or startup overhead, so also measure **Find record → visible text** with a stopwatch.

Compare an initial E-number-only search with several different E-numbers in the same account shortly afterwards. A warm cache should show `catalogueCacheHit: true` and no CSV download/parse stage. Record time to text, first full image and all images separately, using the same representative cards and network. Verify a refreshed export invalidates the cache and a new report still appears on the next search. The offline tests verify removed reads and progressive behavior; they cannot establish a five-second production lookup or a specific speedup.

Drive sync delays affect new reports and scans. Filename timestamps use the report writer's local wall time, so clock/time-zone changes on that computer affect ordering.

Open [cmbirds.org/eggs](https://cmbirds.org/eggs) in a signed-out/incognito browser and confirm it reaches the current viewer. Check the versioned **/exec** app for deployment diagnostics. Confirm E-number searches, direct-location links and Previous/Next work without authorization. Confirm text appears before scans. Test a record without a report, a shared slip, a lone back, a catalogue-only block, REVIEW and FAILED/PAUSED text, and missing/ambiguous scan folders. Original Drive links may correctly refuse anonymous access while embedded scans work. Verify image retry leaves text intact. Set VIEWER_PUBLIC_DISABLED=true and confirm both fresh pages and pending/retried image requests stop; restore it afterwards. Inspect counters in Script properties. After the next intended catalogue correction, refresh the CSV and confirm a fresh search sees it. No paid transcription request is needed for these checks.

From the local repository root, run:

~~~text
node --test apps_script/transcription_viewer/test_viewer.cjs
python -m unittest -v test_transcribe.py
~~~

The viewer tests use synthetic Drive objects, CSV fixtures parsed through Python’s standard library, script-property/lock mocks, a deferred browser-RPC/DOM adapter, and existing local saved responses. Node.js and Python are required; no third-party test package is needed. They make no network requests. Security coverage includes all endpoint guards, shared limits, UTC rollover, lock/storage failure, byte reservations, root changes, arbitrary report IDs, input bounds, malicious captions and link schemes. Earlier local browser checks cover layout and progressive loading. Anonymous Google access, deployment settings, native template rendering and actual service quotas still need checking in the deployed account.

CSV parsing uses [Apps Script CSV support](https://developers.google.com/apps-script/reference/utilities/utilities#parseCsv(String)). Deferred image loading uses [HTML service asynchronous communication](https://developers.google.com/apps-script/guides/html/communication). Reducing initial Drive reads follows [Google’s performance guidance](https://developers.google.com/apps-script/guides/support/best-practices); no live speed measurement is claimed.

Implementation references: [deployment versions](https://developers.google.com/apps-script/concepts/deployments), [escaped template printing](https://developers.google.com/apps-script/guides/html/templates), [Drive file access](https://developers.google.com/apps-script/reference/drive/file).
