# Hosted egg-slip reader and workbook links

Google Drive is the working location for the original egg-slip scans and saved transcription reports. The master workbook and its **Full List** CSV export supply the catalogue for transcription. The public reader displays the scans and transcription data mirrored to the website. [Open Egg Slip Record Search](https://ericlaslo.com/birds/egg-reader/).

## How the website loads cards

Readers can search by E-number or scientific name, browse by family, or open a workbook link. The reader starts with a blank search page. When someone requests a record, the site's JavaScript loads `catalogue.json`, then the matching species data and the requested card's JPEGs from the website. Catalogue and record data are published as JSON. The browser loads the mirrored images directly from the site, without a Google Apps Script request for each image. A record can include several physical cards or sides. The page labels catalogue-only information and retained incomplete readings separately from completed transcriptions.

Refresh the website mirror after adding or correcting scans, saved transcriptions, or catalogue routes. A change on Drive becomes visible in the reader once the corresponding website files are published. Before switching workbook links, open a known published E-number and check that the catalogue, transcription and scans load. If the page opens but reports that the data could not be loaded, check that `catalogue.json` and the data and scan files it references are reachable at their published paths.

The original Apps Script viewer is retained for reference and is no longer actively maintained for public display. Its setup, limits and `/exec` URLs apply to the legacy viewer. [Legacy Apps Script viewer guide](../apps_script/transcription_viewer/README.md).

## Update workbook links

On **Full List**, column **O (Scan Link)** opens the original scan in Drive and uses Drive sharing permissions. Column **P (Transcribed)** opens the hosted reader. The source columns are **N (catalogNumber)**, **C (Family)** and **G (Scientific Name)**. Confirm the headers before editing either workbook.

For existing `HYPERLINK` formulas, replace the URL through `/exec`, leaving `?e=`, the row references, and the link label in place. Copy the existing deployment URL from the formula bar so the search matches that workbook. Use `https://ericlaslo.com/birds/egg-reader/` as the replacement. Work only in the **Transcribed** data range so blank cells, other columns and hyperlinks to Drive are preserved.

- **Native Google Sheet.** Open **Edit → Find and replace**. Set **Search** to **Specific range** and enter `'Full List'!P2:P`, or select the data cells in P with the range picker. Enable **Also search within formulas**. Leave regular expressions and whole-cell matching off. Find and replace one link, check it, then replace the remaining matches. [Google Sheets Find and Replace help](https://support.google.com/docs/answer/62754).
- **Excel workbook.** Open the `.xlsx` in desktop Excel for Windows. On **Full List**, select the populated range in column P, press **Ctrl+H**, and set **Within** to **Sheet**. Replace the same URL text in the selected formulas. Check one link before replacing the rest, then save in `.xlsx` format. The formula below uses `ENCODEURL`, which Excel for the web and Excel for Mac do not support. [Excel Find and Replace help](https://support.microsoft.com/en-us/excel/get-started/find-or-replace-text-and-numbers-on-a-worksheet) · [ENCODEURL availability](https://support.microsoft.com/en-us/office/encodeurl-function-07c7fb90-7c60-4bff-8687-fac50fe33d0e).

A row 2 formula in Google Sheets or Excel for Windows looks like this:

```text
=HYPERLINK("https://ericlaslo.com/birds/egg-reader/?e="&ENCODEURL(N2)&"&family="&ENCODEURL(C2)&"&species="&ENCODEURL(G2),"View")
```

If a transcription cell contains an inserted hyperlink instead of a formula, edit its link address or replace that cell with the formula for its row. Preserve leading zeros in the catalogue number. After saving each workbook, open a **Transcribed** link to check the E-number and a **Scan Link** to check the Drive destination. Use a record you know is published in the web mirror.

**Egg Scan Linker** is separate from the legacy public viewer. The inspected `Egg_Scan_Linker.gs` builds the Drive scan index and writes the **Scan Link** column. Editing **Transcribed** formulas is a workbook change. The scan linker can continue generating Drive links as before.
