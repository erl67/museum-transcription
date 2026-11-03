# Egg Slip Record Search

Spreadsheet links open this viewer and retrieve the latest available species report at click time. The form accepts an E-number or a scientific species name; **Browse by family** opens an alphabetical family list. Catalogue lookup and browsing use the compact Catalogue.gs file bundled with the app; only reports and scans are read from Drive. Existing record links with family and scientific name still work. Opening a record shows its text first, then displays full-resolution scans as each finishes loading. If no transcription exists, it finds available scans by the complete E-number and keeps each physical card’s sides together.

No transcription text is stored in the spreadsheet, hidden sheets, script properties, or a persistent cache. The viewer reads existing Drive files and makes no transcription-service requests. A link can be created before a record has been transcribed; opening it again after a report has synced searches afresh.

## Open Egg Slip Record Search

[Open Egg Slip Record Search at cmbirds.org/eggs](https://cmbirds.org/eggs).

Use **https://cmbirds.org/eggs** as the canonical link for opening, sharing and bookmarking **Egg Slip Record Search**. Readers do not need to open the spreadsheet first. The page heading is **Egg-slip transcription / scan viewer**, with the instruction **Enter an E-number or species to view card records.** followed by a **Browse by family** link. The search field starts blank, with no example placeholder, and no catalogue lists or results appear until requested. Enter an E-number (for example, **E10215** or **10215**) or a complete scientific name such as **Pipilo erythrophthalmus**, then choose **Search**. The field accepts up to 200 characters. After a search, it is empty and ready for another query.

The browser tab is titled **Egg Slip Record Search** on the initial search page and when a search returns an error. A successful record lookup uses the normalized E-number, for example **E4268 Egg Slip Record**. That title also applies when only scans or catalogue information are available. Leading zeros remain part of the title, so E001 is shown as **E001 Egg Slip Record**. Catalogue pages use **Browse by Family | Egg Slip Records** or the selected species followed by **| Egg Slip Records**.

A footer below the transcription and source scans links to this project's GitHub source, gives the maintainer's contact address, and states that the website is independently created and maintained, is not owned, operated, sponsored, or endorsed by the museums, and does not represent official museum communications or institutional positions. The content area is at least one viewport tall, followed by extra spacing, keeping the footer below the initial view even while scans are loading or on a short search/error page.

Viewer.html is Apps Script template source. Opening the local HTML file directly previews the layout but does not run the search, evaluate template expressions, or load Drive scans. Use [cmbirds.org/eggs](https://cmbirds.org/eggs) for the working viewer. Paste the HTML source into the Apps Script HTML file named **Viewer**, and the JavaScript sources into **Code.gs** and **Catalogue.gs**.

## Browse species and families

A species search returns its catalogue E-numbers in numerical order, each linked to the existing record viewer. Matching ignores case and accepts spaces or underscores. It follows the existing report-routing rule: the first two scientific-name words identify the species, and `sp.` becomes `sp`. This is an exact normalized species match, not a prefix or common-name search. A typed species search includes that species across all listed families; a species link within a family selects that family only.

**Browse by family** shows families alphabetically, initially collapsed. Expanding a family reveals its species alphabetically as ordinary links. Species do not expand in place; clicking one opens its E-number list. Opening an E-number retrieves the current record and scans. Identical duplicate catalogue routes appear once in the list; significant zeros remain distinct. These lists include numbered catalogue entries awaiting scans or transcription and do not claim that files are available. Conflicting or incomplete numbered catalogue rows produce an error rather than a partial list.

Both views use the existing Apps Script project and deployment: `?view=families` opens the family list, and `?view=species&family=FAMILY&species=SCIENTIFIC_NAME` opens a species list (URL-encode the values). The search form submits only `q`; number searches use the existing record lookup, while species searches use the catalogue. Existing `?e=...` record links and spreadsheet formulas remain valid. A new form search never inherits the preceding record's location hints.

Opening the blank page reads no collection folders and does not build the catalogue index. Number searches use a local exact-number index; they do not build family/species lists. Browsing validates and sorts the bundled routing rows and returns only names and number links, without any Drive or catalogue-cache calls. Expanding a family makes no server request. The public stop switch, request budget and 45-second lookup budget remain in effect. Install **Catalogue.gs alongside Code.gs**, retaining Viewer.html and the manifest, and publish a new version of the existing deployment.

## Browse records

**Previous** and **Next** appear at the upper right beside the heading. Open a record first to enable them. Navigation follows alphabetical family, then alphabetical scientific name, then E-number in numerical order within that species. CSV row order and Drive listing order do not determine neighbours: E2 → E10 → E100 is the correct progression. At the end of a species, Next opens the lowest-numbered record in the next species; Previous reverses that order, including family transitions.

Every numbered catalogue entry is included, whether it has a completed transcription, a catalogue-only skeleton, scans without a report, or no available files yet. An unfinished entry keeps its E-number and family/species visible, with the existing transcription and scan availability messages. Navigation does not invent a transcription or create a missing-card block. Identical duplicate catalogue numbers at the same location give one navigation position, while their report blocks remain intact. Significant zeros are preserved: E001 and E1 remain distinct entries. Shared-slip numbers can each lead to the same shared card.

The buttons make ordinary page requests and work without client-side navigation scripts. Neighbour lookup runs only when a button is clicked, using the bundled routing catalogue and the existing alphabetical/numerical sorting rules. No CSV download or cache read is needed. The selected destination uses the normal, fresh report lookup and progressive scan loader. Ordinary searches do no extra adjacent-record work.

Navigation stops at the first/last catalogue record without wrapping. Attempting to go beyond an end leaves the current record visible, shows an endpoint message and disables that direction. Catalogue conflicts, incomplete routing, report problems or bounded-search failures produce explicit navigation messages while retaining the current record when it can still be read. A direct-location record absent from the catalogue can still be viewed, but needs a catalogue route before Previous/Next can place it in the sequence. The public stop switch and request budget are checked before any navigation lookup.

## Public access and publication boundary

Deploy with **Execute as: Me** and **Who has access: Anyone**, including visitors who are not signed in. The supplied manifest uses **USER_DEPLOYING** and **ANYONE_ANONYMOUS**. The deploying account authorizes read-only Drive access; visitors do not need workbook or Drive permissions. This replaces the former workbook-membership check, which cannot authenticate a visitor when the app runs as its deployer. See [Google's deployment settings](https://developers.google.com/apps-script/manifest/web-app-api-executable).

**The configured Family root is the publication boundary.** Matching species reports and JPEGs beneath it are available through the viewer, even if Drive labels them Restricted. Future matching files added there become available automatically. The catalogue exposes E-numbers and family/species routes; the raw CSV is not returned. Direct-location links may reach numbered records absent from the CSV, so the CSV is not a publication allowlist. Keep material that must remain private outside this root. No separate record-approval system is implied.

The maintainer chose to publish all existing record states: OK, REVIEW, FAILED, PAUSED, catalogue-only MISSING blocks, and scans without transcriptions. Retained failed/paused responses remain explicitly incomplete or unaccepted; structural OK still does not mean human verification. Existing report parsing and uncertainty are preserved.

Only the deploying account needs access to the Family root; the viewer no longer needs access to the catalogue CSV. Keep Drive sharing restricted if desired: the app serves the selected text and image bytes itself. Original report/JPG links continue to use Drive's own permissions and may ask visitors to sign in. Do not make the entire Drive folder public merely to enable these links. A separate deploying account with access only to the publication folder gives stronger isolation; the read-only OAuth scope limits modification but can read other files that account can access. Folder and file checks in this app restrict what it serves.

Install this viewer in its own project with only Code.gs, Catalogue.gs, Viewer.html and appsscript.json. Do not combine it with the spreadsheet linker or other scripts with public write/admin functions. Keep project-editor access limited to maintainers. Workspace administrator policies may prevent anonymous deployment; the local files do not override those policies or update an existing deployment automatically.

## Emergency stop and request limits

In Apps Script **Project Settings → Script properties**, set **VIEWER_PUBLIC_DISABLED** to the exact value **true** to stop new page, scan-list and image requests without a new deployment. Remove the property or set it to **false** to reopen. Already delivered content cannot be recalled, and requests already past the check may finish. For a full shutdown, archive the deployment in **Manage deployments**.

Code.gs sets shared limits of **120 requests per UTC minute**, **3,000 requests per UTC day**, and **2 GiB of reserved JPEG bytes per UTC day**. These are configurable application limits, not Google's quota values or per-visitor allowances. Each page (including the empty form), scan-list call and individual image call consumes one request, including malformed requests and retries. Scan bytes are reserved immediately before download; failed downloads retain their reservation. Text searches remain usable after only the image-byte budget is exhausted.

Counters live in the fixed **VIEWER_PUBLIC_BUDGET_V1** script property. A script-wide lock makes reservations atomic across visitors and deployments of this project. Cache eviction and client-supplied identities do not reset counters. Corrupt/unavailable property storage or lock failures stop requests before Drive reads. Do not edit or delete counters routinely; after inspecting corrupt state, a maintainer can remove that property to initialize fresh counters, which deliberately resets the budget. Never put these controls in user properties or a per-browser cookie.

These controls limit admitted Drive work; they cannot prevent an attacker from invoking the app, using up the shared budget, or consuming Apps Script execution/property quotas with rejected requests. This is not denial-of-service protection or a guarantee of availability. Monitor **Executions** and adjust limits for observed use. See Google's [service quotas](https://developers.google.com/apps-script/guides/services/quotas), [script locks](https://developers.google.com/apps-script/reference/lock/lock-service), and [script properties](https://developers.google.com/apps-script/reference/properties/properties-service).

## Install or update the viewer

Use a separate Apps Script project from the Egg Scan Linker.

1. Open [Google Apps Script](https://script.google.com/) with the maintaining account. For a new project, name it **Egg Slip Record Search**.
2. Replace **Code.gs** with [Code.gs](Code.gs).
3. Add a **Script** file named **Catalogue** (the editor adds `.gs`) and paste [Catalogue.gs](Catalogue.gs) into it. This file contains the complete compact catalogue; do not paste it into an HTML file.
4. Keep the existing **Viewer** HTML file and **appsscript.json** for this catalogue-only update. For a new installation, use [Viewer.html](Viewer.html) and [appsscript.json](appsscript.json); enable **Show appsscript.json manifest file in editor** in Project Settings. The manifest uses the public deployment settings above and read-only Drive access.
5. Confirm ROOT_FOLDER_ID and the public request/download limits near the top of Code.gs. The root identifies the Family folder containing the material intended for publication. CATALOGUE_FILE_ID and the CSV cache settings are no longer used.
6. For an existing deployment, save and choose **Deploy → Manage deployments → Edit (pencil) → Version: New version → Deploy**. Keep the existing deployment URL so spreadsheet links stay valid.
7. For a first deployment, choose **Deploy → New deployment → Web app**, use the settings above, and copy the resulting URL ending in **/exec**.

Saving source alone does not update a versioned /exec deployment. The execution URL is used for deployment checks and direct record links; the canonical public access link remains [cmbirds.org/eggs](https://cmbirds.org/eggs). If the deployment URL changes, update the target behind the canonical link and check that it opens the current viewer. Do not upload the generator, README or test files as Apps Script source. Running doGet in the editor does not open the viewer.

## Bundled catalogue and direct viewer links

The master workbook and its UTF-8 CSV export remain the source catalogue for the Python transcription application. The viewer uses a separate, generated [Catalogue.gs](Catalogue.gs) containing only **catalogNumber**, **Family** and **Scientific Name**. Reports, scan availability, collector information, locality and other columns are not copied into this bundle.

The 2 November 2026 bundle contains **10,174 numbered rows**, with **1,226 distinct family/scientific-name pairs** stored once and referenced by number. Its generated UTF-8 file is **180,857 bytes**, compared with the source CSV's **4,770,179 bytes** (about **96% smaller**). Numbers are stored as digit strings, preserving significant zeros. Row order and duplicate rows are preserved; the existing viewer rules still reject conflicting or incomplete routes. Numbered records awaiting scans or transcriptions remain included.

Every search uses the bundled data: there is no catalogue Drive metadata check, download, CSV parse, cache expiry or network fallback. A missing or malformed Catalogue.gs produces a deployment error. The in-memory number index is built lazily during each execution that needs it. Previous/Next and browsing retain the existing local sorting rules. The app does not send the whole catalogue to the browser on the landing page.

**New reports and scans need no catalogue update.** The viewer continues discovering them on Drive whenever a record is opened. Changing Scan Link, Transcribed or other unused CSV columns also needs no update. Only an actual change to an E-number, family or scientific name requires regenerating Catalogue.gs and deploying a new version. Editing the CSV alone no longer changes the viewer's routes.

The generator reads the source without modifying it. From the repository root:

~~~powershell
python apps_script/transcription_viewer/build_catalogue.py "G:\My Drive\Egg Slip Scanning\EggSlipReorganizationProject_FULL.xlsx - Full List.csv"
node --test apps_script/transcription_viewer/test_viewer.cjs apps_script/transcription_viewer/test_catalogue.cjs
~~~

Then replace Catalogue.gs in Apps Script and publish a new version of the existing deployment. Review any unexpected record-count change before deployment; update the shipped-catalogue test counts only after checking the source. The bundled routing data is included in this repository at the maintainer's request. The full source CSV, scans and transcription reports are not added by this generator.

The CSV must have exactly one of each required header; surrounding header whitespace and reordered columns are supported. The generator supports UTF-8/BOM and quoted commas/newlines, rejects malformed exports and extra columns beyond the header, and preserves all numbered routing rows. Its SHA-256 identifies only the compact routing data, so changing unused columns does not change the bundle. It cannot recover leading zeros already lost in the source export. Python's transcription workflow continues reading its configured full CSV unchanged.

To share the viewer independently of the spreadsheet, use [cmbirds.org/eggs](https://cmbirds.org/eggs). Readers can search by E-number or species, or browse families. For direct record links, the deployment URL ending in **/exec?e=E4268** opens that record. The formulas below retain execution URLs for these record-specific requests; use the canonical link for general viewer access. Both are public after deploying the new version with the settings above.

The known catalogue columns are **Family in C**, **Scientific Name in G**, and **catalogNumber in N**. Confirm these headers if columns have moved. On row 2, a direct-location link is:

~~~text
=HYPERLINK("PASTE_DEPLOYED_EXEC_URL_HERE?e="&ENCODEURL(N2)&"&family="&ENCODEURL(C2)&"&species="&ENCODEURL(G2),"View transcription")
~~~

An E-number-only link is also supported:

~~~text
=HYPERLINK("PASTE_DEPLOYED_EXEC_URL_HERE?e="&ENCODEURL(N2),"View transcription")
~~~

Replace only PASTE_DEPLOYED_EXEC_URL_HERE with the complete deployment URL. Keep the **?e=** delimiter. Adapt row references and fill down as needed. The longer link uses the supplied family/species without consulting the bundled catalogue; use E-number-only links to pick up routing corrections after deploying an updated Catalogue.gs. Neither link type requires visitors to have workbook access.

An ordinary hyperlink to the resulting URL also works in the Excel file. If copying formulas between the native Sheet and Excel loses the link, build the URL in the native Sheet and use it as the target of an ordinary hyperlink.

Keep meaningful leading zeros as text: E001 and E1 are different records. Check that exported values retain their zeros; spreadsheet display formatting alone is not a guarantee. Submitting the form sends only its search text, so a new search does not inherit an old record's family/species.

## Transcription and source-scan display

- Reads normal species reports directly in the matching family directory, newest first by filename timestamp and numeric collision counter, until the exact CM number is found. It excludes journals, mixed-species test reports, and individual ! / @ reports.
- Keeps shared-slip numbers and their complete common text together. Duplicate catalogue-only rows remain separate.
- Preserves historical wording, partial dates, annotations, supplied backs, uncertainty, and transcription notes.
- Omits technical report headers and complete terminal usage footers from both ordinary runs and campaign snapshots. Campaign footers include a `SAVED RESULT USAGE (includes recorded retries; not new spending this run):` heading. Source words matching technical field names are not globally deleted.
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

An older viewer could report “The newest matching record is empty or incomplete” for the final card in an otherwise complete campaign report: it did not recognize the campaign's usage heading and treated the footer as card text. Waiting for sync would not resolve that format mismatch; a new ordinary report could hide it by becoming the newest match. Update Code.gs and publish a new deployment version to read those existing campaign reports without retranscribing. The viewer still rejects empty or genuinely incomplete records and does not fall back to older readings to conceal them.

## Limits and verification

The viewer reads at most **40 candidate reports**, lists at most **5,000 family-directory files**, accepts reports up to **10 MiB**, and checks a separate **45-second** elapsed-time budget for text lookup, scan discovery and each image request between Drive operations. Reaching a report-search limit produces an explicit incomplete-search message. One slow Drive operation can itself exceed the elapsed-time budget. Scan-folder traversal limits each child-folder listing to **5,000 folders**. Scan-only discovery lists at most **5,000 files** and accepts at most **40 matching JPEGs**; limit errors explicitly report an incomplete search. Missing, inaccessible, or ambiguous directories do not become “no scans found.”

Source images are limited to **12 MiB each**, **24 MiB total planned image bytes per page**, and **40 images**. The plan reserves each eligible file's full size before downloads start; an image whose actual byte length or version changes is rejected. Failed reservations are not reassigned to other images during the page load. When a file is found but cannot be embedded, its original Drive link remains available. Image failures do not replace the selected transcription.

## Measure loading times after deployment

Server logs contain `Viewer timing` JSON for `text`, `scanPlan` and `image` executions. Inspect them in Apps Script's **Executions** view. Text stages include access, local bundled-catalogue lookup, family lookup, report listing/download/selection and template rendering. Button requests additionally include `navigation` and `navigationCatalogue` stages. Catalogue browsing uses `browseCatalogue` and `browseSequence`; it has no report or image reads. Counts include `catalogueSource: "bundled"`, the bundled row count, files listed and reports read. CSV download/parse/cache stages no longer appear. Image stages include scan-plan cache hits, source validation, JPEG download/encoding and original byte count. Nested stage durations overlap; do not add them together. No catalogue values, report text, image content, filenames, IDs or account identifiers are included in timing logs.

The browser developer console also logs `Viewer text timing`, `Viewer scan discovery`, `Viewer image timing`, `Viewer first image displayed` and `Viewer image requests finished`. Browser scan elapsed times start when the page's script runs, after the text response arrives. Per-image elapsed times include the RPC round trip; the first-image measurement includes JPEG decoding/display readiness. The text timing copied into the page precedes template rendering; the server's final text log includes it. These figures do not include all of Google's navigation, authorization or startup overhead, so also measure **Search → visible text** with a stopwatch.

Compare an initial E-number-only search with several different E-numbers in the same account shortly afterwards. Both initial and subsequent number searches should show `catalogueSource: "bundled"` and no CSV download/parse/cache stage. Record time to text, first full image and all images separately, using the same representative cards and network. Verify a new report still appears on the next search without updating Catalogue.gs. The offline tests verify removed reads and progressive behavior; they cannot establish a five-second production lookup or a specific speedup.

Drive sync delays affect new reports and scans. Filename timestamps use the report writer's local wall time, so clock/time-zone changes on that computer affect ordering.

Open [cmbirds.org/eggs](https://cmbirds.org/eggs) in a signed-out/incognito browser and confirm it reaches the current viewer. Check the versioned **/exec** app for deployment diagnostics. Confirm E-number searches, direct-location links and Previous/Next work without authorization. Confirm text appears before scans. Test a record without a report, a shared slip, a lone back, a catalogue-only block, REVIEW and FAILED/PAUSED text, and missing/ambiguous scan folders. Original Drive links may correctly refuse anonymous access while embedded scans work. Verify image retry leaves text intact. Set VIEWER_PUBLIC_DISABLED=true and confirm both fresh pages and pending/retried image requests stop; restore it afterwards. Inspect counters in Script properties. After an intended routing correction, regenerate Catalogue.gs and deploy a new version before checking it in the viewer. No paid transcription request is needed for these checks.

After deploying the browsing update, confirm the initial page is blank apart from its heading, instructions, navigation and search form. Search a species, check numerical E-number order, then open one record. Open **Browse by family**, expand a family, and confirm species links open a separate number list. Check both desktop and narrow layouts. Repeat a numeric search and inspect its timing log: it should have no `browseCatalogue` or `browseSequence` stage. The offline tests exercise these paths with synthetic catalogue data; deployed response times still require measurement.

From the local repository root, run:

~~~text
node --test apps_script/transcription_viewer/test_viewer.cjs apps_script/transcription_viewer/test_catalogue.cjs
python -m unittest -v test_transcribe.py
~~~

The viewer tests use synthetic Drive objects, bundled catalogue fixtures, generator CSV fixtures parsed through Python’s standard library, script-property/lock mocks, a deferred browser-RPC/DOM adapter, and existing local saved responses. Node.js and Python are required; no third-party test package is needed. They make no network requests. Security coverage includes all endpoint guards, shared limits, UTC rollover, lock/storage failure, byte reservations, root changes, arbitrary report IDs, input bounds, malicious captions and link schemes. Earlier local browser checks cover layout and progressive loading. Anonymous Google access, deployment settings, native template rendering and actual service quotas still need checking in the deployed account.

Catalogue generation uses Python’s standard-library CSV parser offline. Deferred image loading uses [HTML service asynchronous communication](https://developers.google.com/apps-script/guides/html/communication). Reducing initial Drive reads follows [Google’s performance guidance](https://developers.google.com/apps-script/guides/support/best-practices); no live speed measurement is claimed.

Implementation references: [deployment versions](https://developers.google.com/apps-script/concepts/deployments), [escaped template printing](https://developers.google.com/apps-script/guides/html/templates), [Drive file access](https://developers.google.com/apps-script/reference/drive/file).
