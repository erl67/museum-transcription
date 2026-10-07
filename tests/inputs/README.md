# Representative test inputs

The curated set currently contains 11 physical cards / 19 images (verified by read-only discovery on 7 October 2026). Put selected cards directly in this folder as JPG/JPEG files. Multiple species are welcome; preserve original filenames and include all available sides of each selected card. Subfolders are not searched. A two-sided card is two images but one request before retries.

The set includes a shared E8556/E8557/E8558 slip and a three-sided E10001 card, as well as front-only cards and pairs. Do not fabricate museum examples or copy the full collection here. Review publication rights before explicitly adding selected images to Git.

The master CSV stays local and read-only. Test mode matches complete E-numbers from filenames, independently of production species folders. Uncatalogued scans need the documented naming pattern.

Preview with `python transcribe.py tests --dry-run` before an authorized live check. Launch the program and type **tests** to make fresh requests using the selected profile, currently Gemini 3.5 Flash-Lite. Live checks are optional; offline regression tests do not spend quota. This folder is the default input, and `../outputs/` is the default report folder. Both defaults follow the script directory, independent of Family or the working directory. Explicit path overrides remain available. The known wollweberi/ultramarina mismatch does not prevent E-number matching; source names are retained.

See [testing](../../docs/testing.md) for selection, optional fresh checks, the reviewed baseline, and the distinct optional three-image offline fixture; see [filename rules](../../docs/filename_rules.md) for naming.
