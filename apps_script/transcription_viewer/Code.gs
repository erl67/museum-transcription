/** Read-only transcription viewer. Install as a separate Apps Script project; see README.md. */
const TRANSCRIPTION_VIEWER = Object.freeze({
  // Master workbook supplied by the maintainer; its Drive permissions gate viewer access.
  WORKBOOK_FILE_ID: '1P-sWhtIlRHcbh4D5rV0p0sv-MF_Th1lc',
  // Family root already used by Egg_Scan_Linker.gs.
  ROOT_FOLDER_ID: '1rnIKpQg83jHh85Qr_TQqJ-ayEs0Q65HJ',
  // Optional direct CSV ID avoids parent-folder discovery for shared readers.
  CATALOGUE_FILE_ID: '1AOoNhjdyvNHZUxf11WwM1VMPuzdDOA8I',
  CATALOGUE_FOLDER_NAME: 'Transcription',
  CATALOGUE_FILE_NAME: 'EggSlipReorganizationProject_FULL.xlsx - Full List.csv',
  MAX_CATALOGUE_BYTES: 10 * 1024 * 1024,
  MAX_REPORT_BYTES: 10 * 1024 * 1024,
  MAX_REPORTS_READ: 40,
  MAX_FILES_LISTED: 5000,
  MAX_LOOKUP_MS: 45000,
  MAX_IMAGE_BYTES: 12 * 1024 * 1024,
  MAX_TOTAL_IMAGE_BYTES: 24 * 1024 * 1024,
  MAX_IMAGES: 40,
  CATALOGUE_CACHE_SECONDS: 900,
  CATALOGUE_CACHE_BUCKETS: 64,
  SCAN_PLAN_SECONDS: 600,
  // At most 3 UTF-8 bytes per UTF-16 code unit, safely below CacheService's 100 KB/value.
  CACHE_MAX_CHARS: 24000
});

function viewerTiming_(operation) {
  const started = Date.now();
  const data = { operation: operation, stagesMs: {}, counts: {} };
  return {
    measure(name, work) {
      const before = Date.now();
      try { return work(); }
      finally { data.stagesMs[name] = (data.stagesMs[name] || 0) + Date.now() - before; }
    },
    count(name, value) { data.counts[name] = value; },
    elapsed(name, before) { data.stagesMs[name] = Date.now() - before; },
    snapshot() { return { operation: operation, totalMs: Date.now() - started,
      stagesMs: Object.assign({}, data.stagesMs), counts: Object.assign({}, data.counts) }; },
    finish() {
      data.totalMs = Date.now() - started;
      console.info('Viewer timing ' + JSON.stringify(data));
      return data;
    }
  };
}

function measured_(timing, stage, work) {
  return timing ? timing.measure(stage, work) : work();
}

function userCache_() {
  try { return CacheService.getUserCache(); } catch (error) { return null; }
}

function cachedJson_(cache, key) {
  try { return cache ? JSON.parse(cache.get(key)) : null; } catch (error) { return null; }
}

function cacheJson_(cache, key, value, seconds) {
  try {
    const text = JSON.stringify(value);
    if (!cache || text.length > TRANSCRIPTION_VIEWER.CACHE_MAX_CHARS) return false;
    cache.put(key, text, seconds);
    return true;
  } catch (error) { return false; }
}

function digest_(text) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, text, Utilities.Charset.UTF_8)
    .map(byte => ('0' + (byte & 255).toString(16)).slice(-2)).join('');
}

function fileVersion_(file) {
  return file.getLastUpdated().getTime() + ':' + file.getSize();
}

function doGet(e) {
  const timing = viewerTiming_('text');
  const params = (e && e.parameter) || {};
  const page = HtmlService.createTemplateFromFile('Viewer');
  page.query = {
    e: String(params.e || '').slice(0, 80),
    family: String(params.family || '').slice(0, 200),
    species: String(params.species || '').slice(0, 200)
  };
  page.appUrl = ScriptApp.getService().getUrl();
  page.result = null;
  try {
    timing.measure('access', requireWorkbookAccess_);
    if (page.query.e || page.query.family || page.query.species) {
      page.result = lookupTranscription_(page.query, timing);
    }
  } catch (error) {
    page.result = { error: error.viewerMessage ||
      'The reports could not be read. Check your Google account has access to the Family folder and its reports, then try again.' };
  }
  const title = page.result && !page.result.error ?
    page.result.query.e + ' Egg Slip Record' : 'Egg Slip Record Search';
  if (page.result && !page.result.error) page.result.timings = timing.snapshot();
  const output = timing.measure('template', () => page.evaluate().setTitle(title)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1'));
  timing.finish();
  return output;
}

function viewerError_(message) {
  const error = new Error(message);
  error.viewerMessage = message;
  return error;
}

// Deploy as USER_ACCESSING so this check uses the reader's actual workbook permissions.
function requireWorkbookAccess_() {
  const id = TRANSCRIPTION_VIEWER.WORKBOOK_FILE_ID;
  if (!id || !/^[A-Za-z0-9_-]{10,}$/.test(id)) {
    throw viewerError_('The master spreadsheet has not been configured for the viewer. Contact the collection maintainer.');
  }
  try {
    // Force a Drive read; this respects direct, inherited and Google Group access.
    DriveApp.getFileById(id).getName();
  } catch (error) {
    throw viewerError_('Sign in with a Google account that has access to the master Excel file. If you already have access, authorize the viewer and try again.');
  }
}

function normalizeQuery_(query) {
  const match = /^(?:E|CM)?([0-9]+)$/i.exec(String(query.e || '').trim());
  if (!match) throw viewerError_('Enter one complete E-number, such as E4268.');
  const family = String(query.family || '').trim();
  const scientificName = String(query.species || '').trim();
  let species = '';
  if (scientificName) {
    const words = scientificName.replace(/_/g, ' ').split(/\s+/);
    if (words.length < 2) throw viewerError_('Enter a complete scientific name, or leave it unspecified.');
    // Same routing rule as transcribe.species_name: first two words, sp. -> sp.
    const genus = words[0].charAt(0).toUpperCase() + words[0].slice(1).toLowerCase();
    species = genus + '_' + words[1].toLowerCase().replace(/\.+$/, '');
  }
  if ([family, species].some(value => /[<>:"/\\|?*\x00-\x1f]/.test(value) ||
      /[. ]$/.test(value) || value === '.' || value === '..') || species.endsWith('_')) {
    throw viewerError_('The Family or Scientific Name is not a valid report location.');
  }
  return { e: 'E' + match[1], digits: match[1], family: family, species: species };
}

/** Read the exported lookup CSV; the workbook remains the access gate. */
function readCatalogue_(root, checkTime, digits, timing) {
  let file;
  try {
    const findStarted = Date.now();
    if (TRANSCRIPTION_VIEWER.CATALOGUE_FILE_ID) {
      file = DriveApp.getFileById(TRANSCRIPTION_VIEWER.CATALOGUE_FILE_ID);
    } else {
      const candidates = new Map();
      const addFiles = folder => {
        const files = folder.getFilesByName(TRANSCRIPTION_VIEWER.CATALOGUE_FILE_NAME);
        while (files.hasNext()) {
          checkTime();
          const found = files.next();
          candidates.set(found.getId(), found);
        }
      };
      const parents = root.getParents();
      while (parents.hasNext()) {
        checkTime();
        const parent = parents.next();
        addFiles(parent);
        const folders = parent.getFoldersByName(TRANSCRIPTION_VIEWER.CATALOGUE_FOLDER_NAME);
        while (folders.hasNext()) { checkTime(); addFiles(folders.next()); }
      }
      if (candidates.size !== 1) {
        throw viewerError_(candidates.size ?
          'More than one catalogue CSV was found. Set CATALOGUE_FILE_ID to the intended export.' :
          'The catalogue CSV was not found or is not accessible. Check CSV sharing and CATALOGUE_FILE_ID.');
      }
      file = candidates.values().next().value;
    }
    if (timing) timing.elapsed('catalogueFile', findStarted);
    checkTime();
    if (!/\.csv$/i.test(file.getName()) || /^application\/vnd\.google-apps\./.test(file.getMimeType())) {
      throw viewerError_('The lookup catalogue must be a UTF-8 CSV file. Check CATALOGUE_FILE_ID.');
    }
    if (file.getSize() > TRANSCRIPTION_VIEWER.MAX_CATALOGUE_BYTES) {
      throw viewerError_('The catalogue CSV exceeds the viewer size limit. The E-number search could not be completed.');
    }
    const cache = digits === undefined ? null : userCache_();
    const version = cache ? fileVersion_(file) : '';
    const prefix = cache ? 'catalogue-v1:' + digest_(file.getId() + ':' + version) + ':' : '';
    const bucket = digits === undefined ? 0 : catalogueBucket_(digits);
    const cached = measured_(timing, 'catalogueCacheRead', () => cachedJson_(cache, prefix + bucket));
    if (cached && Array.isArray(cached.rows) && cached.rows.every(row =>
        Array.isArray(row) && row.length === 3 && row.every(value => typeof value === 'string'))) {
      if (timing) timing.count('catalogueCacheHit', true);
      checkTime();
      return [['catalogNumber', 'Family', 'Scientific Name']].concat(cached.rows);
    }
    if (timing) timing.count('catalogueCacheHit', false);
    const text = measured_(timing, 'catalogueDownload', () => file.getBlob().getDataAsString('UTF-8')).replace(/^\uFEFF/, '');
    if (/[\u0000\uFFFD]/.test(text)) throw new Error('Invalid UTF-8 export');
    checkTime();
    const rows = measured_(timing, 'catalogueParse', () => Utilities.parseCsv(text));
    checkTime();
    if (cache) {
      const buckets = catalogueBuckets_(rows);
      if (fileVersion_(file) !== version) throw viewerError_('The catalogue CSV changed during the search. Please try again.');
      measured_(timing, 'catalogueCacheWrite', () => {
        const values = {};
        buckets.forEach((rows, index) => {
          const value = JSON.stringify({ rows: rows });
          if (value.length <= TRANSCRIPTION_VIEWER.CACHE_MAX_CHARS) values[prefix + index] = value;
        });
        try { cache.putAll(values, TRANSCRIPTION_VIEWER.CATALOGUE_CACHE_SECONDS); } catch (error) { /* Cache is optional. */ }
      });
    }
    return rows;
  } catch (error) {
    if (error.viewerMessage) throw error;
    throw viewerError_('The catalogue CSV could not be read. Check its sharing and UTF-8 export format.');
  }
}

function catalogueBucket_(digits) {
  let value = 0;
  for (const digit of digits) value = (value * 31 + digit.charCodeAt(0)) % TRANSCRIPTION_VIEWER.CATALOGUE_CACHE_BUCKETS;
  return value;
}

function catalogueBuckets_(rows) {
  rows = rows.filter(row => row.some(value => String(value).trim()));
  const header = (rows[0] || []).map(value => String(value).trim());
  const fields = ['catalogNumber', 'Family', 'Scientific Name'];
  const columns = fields.map(name => header.indexOf(name));
  if (fields.some((name, i) => columns[i] < 0 || header.lastIndexOf(name) !== columns[i])) {
    throw viewerError_('The catalogue needs one column each named catalogNumber, Family, and Scientific Name.');
  }
  const buckets = Array.from({ length: TRANSCRIPTION_VIEWER.CATALOGUE_CACHE_BUCKETS }, () => []);
  for (const row of rows.slice(1)) {
    if (row.length > header.length) throw viewerError_('The catalogue CSV has a row with extra columns. Check its export format.');
    const number = /^E?([0-9]+)$/i.exec(String(row[columns[0]] || '').trim());
    if (number) buckets[catalogueBucket_(number[1])].push(columns.map(column => String(row[column] || '')));
  }
  return buckets;
}

function routeFromCatalogue_(query, rows) {
  rows = rows.filter(row => row.some(value => String(value).trim()));
  const header = (rows[0] || []).map(value => String(value).trim());
  const fields = ['catalogNumber', 'Family', 'Scientific Name'];
  const columns = fields.map(name => header.indexOf(name));
  if (fields.some((name, i) => columns[i] < 0 || header.lastIndexOf(name) !== columns[i])) {
    throw viewerError_('The catalogue needs one column each named catalogNumber, Family, and Scientific Name.');
  }
  const routes = new Map();
  for (const row of rows.slice(1)) {
    if (row.length > header.length) throw viewerError_('The catalogue CSV has a row with extra columns. Check its export format.');
    const number = /^E?([0-9]+)$/i.exec(String(row[columns[0]] || '').trim());
    if (!number || number[1] !== query.digits) continue;
    let route;
    try {
      route = normalizeQuery_({ e: query.e, family: row[columns[1]], species: row[columns[2]] });
    } catch (error) {
      throw viewerError_('The catalogue has an invalid family or scientific name for ' + query.e + '. Check the catalogue row.');
    }
    if (!route.family || !route.species) {
      throw viewerError_('The catalogue is missing the family or scientific name for ' + query.e + '. Check the catalogue row.');
    }
    routes.set(route.family.toLowerCase() + '\n' + route.species.toLowerCase(), route);
  }
  if (!routes.size) {
    throw viewerError_(query.e + ' was not found in the catalogue CSV. Check the number or refresh the catalogue export.');
  }
  if (routes.size !== 1) {
    throw viewerError_('The catalogue lists conflicting families or species for ' + query.e + '. Check the duplicate catalogue rows.');
  }
  const route = routes.values().next().value;
  if ((query.family && query.family.toLowerCase() !== route.family.toLowerCase()) ||
      (query.species && query.species.toLowerCase() !== route.species.toLowerCase())) {
    throw viewerError_('The supplied family or species does not match the catalogue for ' + query.e + '. Search using only the E-number.');
  }
  return route;
}

function lookupTranscription_(rawQuery, timing) {
  let query = normalizeQuery_(rawQuery);
  const started = Date.now();
  const checkTime = () => {
    if (Date.now() - started > TRANSCRIPTION_VIEWER.MAX_LOOKUP_MS) {
      throw viewerError_('The search time limit was reached. The search is incomplete; please try again.');
    }
  };
  const root = DriveApp.getFolderById(TRANSCRIPTION_VIEWER.ROOT_FOLDER_ID);
  if (!query.family || !query.species) {
    query = measured_(timing, 'catalogue', () => routeFromCatalogue_(query, readCatalogue_(root, checkTime, query.digits, timing)));
    checkTime();
  }
  const family = measured_(timing, 'familyFolder', () => familyFolder_(root, query, checkTime));
  const listStarted = Date.now();
  const files = family.getFiles();
  const candidates = [];
  let listed = 0;
  while (files.hasNext()) {
    checkTime();
    if (++listed > TRANSCRIPTION_VIEWER.MAX_FILES_LISTED) {
      throw viewerError_('The folder listing limit was reached. The search is incomplete.');
    }
    const file = files.next();
    const info = reportName_(file.getName(), query.species);
    if (info) candidates.push({ file: file, info: info });
  }
  if (timing) { timing.count('filesListed', listed); timing.elapsed('reportListing', listStarted); }
  let reportsRead = 0;
  const result = measured_(timing, 'reports', () => selectLatestRecord_(candidates, query, file => {
    checkTime();
    if (file.getSize() > TRANSCRIPTION_VIEWER.MAX_REPORT_BYTES) {
      throw viewerError_('A report exceeds the viewer size limit. The search is incomplete.');
    }
    reportsRead++;
    return measured_(timing, 'reportDownload', () => file.getBlob().getDataAsString('UTF-8'));
  }, checkTime));
  if (timing) timing.count('reportsRead', reportsRead);
  result.imageRequest = { query: result.query, reportId: result.reportId || '',
    manifest: imageManifest_(result.records) };
  return result;
}

function familyFolder_(root, query, checkTime) {
  const folders = root.getFolders();
  const matches = [];
  while (folders.hasNext()) {
    checkTime();
    const folder = folders.next();
    if (folder.getName().trim().toLowerCase() === query.family.toLowerCase()) matches.push(folder);
  }
  if (matches.length !== 1) {
    throw viewerError_(matches.length ? 'More than one matching family folder was found. The folder needs to be checked.' :
      'The family folder was not found or is not accessible. Check the Family value and your Drive access.');
  }
  return matches[0];
}

function reportName_(name, species) {
  // Normal species reports only; journals, individual checks and test runs are excluded.
  const prefix = species.toLowerCase() + '_transcriptions_';
  if (!name.toLowerCase().startsWith(prefix)) return null;
  const match = /^(\d{8})_(\d{4})(?:_(\d+))?\.txt$/i.exec(name.slice(prefix.length));
  if (!match) return null;
  const day = match[1], time = match[2], counter = match[3] ? Number(match[3]) : 1;
  const date = new Date(Date.UTC(+day.slice(0, 4), +day.slice(4, 6) - 1, +day.slice(6, 8),
    +time.slice(0, 2), +time.slice(2, 4)));
  const expected = day.slice(0, 4) + '-' + day.slice(4, 6) + '-' + day.slice(6, 8) +
    'T' + time.slice(0, 2) + ':' + time.slice(2, 4);
  if (!Number.isSafeInteger(counter) || counter < (match[3] ? 2 : 1) ||
      !Number.isFinite(date.getTime()) || date.toISOString().slice(0, 16) !== expected) return null;
  return { stamp: day + time, counter: counter, date: expected.replace('T', ' ') };
}

function selectLatestRecord_(candidates, query, readText, checkTime) {
  candidates.sort((a, b) => b.info.stamp.localeCompare(a.info.stamp) || b.info.counter - a.info.counter);
  let read = 0;
  for (let i = 0; i < candidates.length; i++) {
    if (checkTime) checkTime();
    const candidate = candidates[i];
    const next = candidates[i + 1];
    if (next && candidate.info.stamp === next.info.stamp && candidate.info.counter === next.info.counter) {
      throw viewerError_('Duplicate report timestamps were found. The reports need to be checked before choosing a latest version.');
    }
    if (++read > TRANSCRIPTION_VIEWER.MAX_REPORTS_READ) {
      throw viewerError_('The viewer report limit was reached. The search is incomplete; older reports have not all been checked.');
    }
    const records = parseReport_(readText(candidate.file), query.digits);
    if (records.length) {
      return { query: query, records: records, reportDate: candidate.info.date, reportId: candidate.file.getId(),
        sourceUrl: 'https://drive.google.com/file/d/' + encodeURIComponent(candidate.file.getId()) + '/view' };
    }
  }
  return { query: query, records: [], message: 'No transcription available in the species reports yet. ' +
    'Available source scans will load below. Use this link again after a report has synced to Drive.' };
}

function reportBanner_(line) {
  const match = /^={22}(.+?)={2,}$/.exec(line);
  if (!match) return null;
  const cm = /^CM([0-9]+)( \(MISSING\))?$/.exec(match[1]);
  if (cm) return { digits: cm[1], missing: Boolean(cm[2]) };
  // Filename banners terminate the previous numbered record, too.
  if (/\.jpe?g$/i.test(match[1])) return { digits: null, missing: false };
  return null;
}

function parseReport_(text, wantedDigits) {
  // Strip only a recognized terminal run footer, never matching words inside a card.
  text = String(text).replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n');
  text = text.replace(/\n{3}TOKENS: [^\n]*\nAVERAGE\/CALL[^\n]*\nRUN: [^\n]*\n*$/, '\n\n\n');
  const lines = text.split('\n');
  const blocks = [];
  let current = null;
  for (let i = 0; i < lines.length; i++) {
    const banner = reportBanner_(lines[i]);
    if (!banner) {
      if (current) current.lines.push(lines[i]);
      continue;
    }
    // Consecutive CM banners describe one shared physical card and one body.
    if (current && !current.missing && !banner.missing && current.lines.length === 0) {
      if (banner.digits !== null) current.digits.push(banner.digits);
    } else {
      current = { digits: banner.digits === null ? [] : [banner.digits], missing: banner.missing, lines: [] };
      blocks.push(current);
    }
  }
  return blocks.filter(block => block.digits.includes(wantedDigits)).map(block => {
    if (block.missing) {
      return { numbers: block.digits.map(x => 'E' + x), status: 'MISSING', reused: false,
        review: '', needsReview: false, files: [], images: [], imageMessage: '', text: block.lines.join('\n').trimEnd() };
    }
    const separator = block.lines.indexOf('='.repeat(50));
    const header = block.lines.slice(0, separator);
    const statusLine = header.find(line => /^STATUS: /.test(line));
    const status = statusLine && /^STATUS: (OK|REVIEW|FAILED|PAUSED)( \(reused\))?$/.exec(statusLine);
    if (separator < 0 || !/^ID: .+/.test(header[0] || '') || !status) {
      throw viewerError_('The newest matching record has an incomplete or unrecognized header. Check its report before using an older reading.');
    }
    let body = block.lines.slice(separator + 1);
    if ((status[1] === 'FAILED' || status[1] === 'PAUSED') && /^ERROR:/.test(body[0] || '')) {
      const saved = body.indexOf('SAVED RESPONSE (see error above):');
      // Omit service/debug errors, preserve every line of any retained response.
      body = saved < 0 ? [] : body.slice(saved + 1);
    }
    const bodyText = body.join('\n').trimEnd();
    if ((status[1] === 'OK' || status[1] === 'REVIEW') &&
        (!bodyText.trim() || !block.lines.slice(-2).every(line => line === ''))) {
      throw viewerError_('The newest matching record is empty or incomplete. Its report may still be syncing; try again shortly.');
    }
    const reasons = (header.find(line => /^REVIEW: /.test(line)) || '')
      .replace(/^REVIEW: /, '').split(/\s*\|\s*/).map(reason => reason.trim()).filter(Boolean);
    const remaining = reasons.filter(reason =>
      !/^(?:Notes present|Transcription notes are present)\.?$/i.test(reason));
    // Suppress only a known notes-only flag; preserve unexplained REVIEW statuses.
    const needsReview = status[1] === 'REVIEW' && (remaining.length > 0 || reasons.length === 0);
    return { numbers: block.digits.map(x => 'E' + x), status: status[1], reused: Boolean(status[2]),
      review: remaining.join('    |    '), needsReview: needsReview,
      files: (header.find(line => /^FILES: /.test(line)) || '').replace(/^FILES: /, '')
        .split(/;\s*/).map(name => name.trim()).filter(Boolean),
      images: [], imageMessage: '', text: bodyText };
  });
}

/** Locate only the supported species/JPEG layouts; never search unrelated scans. */
function scanChildFolder_(parent, name, checkTime, memo) {
  memo = memo || new Map();
  if (!memo.has(parent)) {
    const folders = parent.getFolders();
    const children = [];
    while (folders.hasNext()) {
      checkTime();
      if (children.length >= TRANSCRIPTION_VIEWER.MAX_FILES_LISTED) throw viewerError_('The folder listing limit was reached. The search is incomplete.');
      const folder = folders.next();
      children.push({ folder: folder, name: folder.getName().toLowerCase() });
    }
    memo.set(parent, children);
  }
  const found = [];
  for (const child of memo.get(parent)) {
    checkTime();
    if (child.name === name.toLowerCase()) found.push(child.folder);
  }
  if (found.length > 1) throw viewerError_('More than one scan folder matches this record. No images were selected.');
  return found[0] || null;
}

function sourceJpegFolder_(family, species, checkTime, path) {
  const memo = new Map();
  const direct = scanChildFolder_(family, species, checkTime, memo);
  const genus = scanChildFolder_(family, species.split('_')[0], checkTime, memo);
  const nested = genus ? scanChildFolder_(genus, species, checkTime, memo) : null;
  const candidates = new Map();
  for (const folder of [direct, nested]) {
    if (!folder) continue;
    const jpeg = scanChildFolder_(folder, 'JPEG', checkTime, memo);
    if (jpeg) candidates.set(jpeg.getId(), { jpeg: jpeg,
      folders: folder === direct ? [family, folder, jpeg] : [family, genus, folder, jpeg] });
  }
  if (candidates.size !== 1) {
    throw viewerError_(candidates.size ?
      'More than one JPEG folder matches this record. No images were selected.' :
      'The source JPEG folder was not found or is not accessible.');
  }
  const chosen = candidates.values().next().value;
  if (path) chosen.folders.forEach((folder, index) => path.push({ id: folder.getId(), name: folder.getName(),
    parentId: index ? chosen.folders[index - 1].getId() : TRANSCRIPTION_VIEWER.ROOT_FOLDER_ID }));
  return chosen.jpeg;
}

function sourceScanSide_(name) {
  const match = /(?:^|_)E\d+(?:_E\d+)*(?:\((FRONT|BACK|[A-Z]|\d+)\)|[_-]([A-Z]|\d+)-?)?(?:_exchanged)?\.jpe?g$/i.exec(name);
  if (!match) return null;
  const token = (match[1] || match[2] || 'FRONT').toUpperCase();
  if (token === 'FRONT') return 1;
  if (token === 'BACK') return 2;
  if (/^[A-Z]$/.test(token)) return token.charCodeAt(0) - 64;
  const number = Number(token);
  return Number.isSafeInteger(number) && number >= 1 ? number : null;
}

function imageManifest_(records) {
  return JSON.stringify(records.map(record => [record.numbers, record.status, record.files]));
}

/** Public RPC: always authorize again, and never trust client-supplied filenames. */
function loadSourceScans(request) {
  const timing = viewerTiming_('scanPlan');
  let response;
  try {
    timing.measure('access', requireWorkbookAccess_);
    const plan = prepareScanPlan_(request, scanDeadline_(), timing);
    const cache = userCache_();
    const token = cache ? Utilities.getUuid() : '';
    const saved = measured_(timing, 'planCacheWrite', () => cacheJson_(cache, 'scan-plan-v1:' + token,
      plan, TRANSCRIPTION_VIEWER.SCAN_PLAN_SECONDS));
    response = { scanOnly: plan.scanOnly, message: plan.message, galleries: plan.galleries,
      token: saved ? token : '', fingerprint: plan.fingerprint };
  } catch (error) {
    response = { error: error.viewerMessage || 'Source scans could not be loaded. Check your Drive access and reload the page to try again.' };
  }
  response.timings = timing.finish();
  return response;
}

function scanDeadline_() {
  const started = Date.now();
  return () => {
    if (Date.now() - started > TRANSCRIPTION_VIEWER.MAX_LOOKUP_MS) {
      throw viewerError_('The scan search time limit was reached. Reload the page to try again.');
    }
  };
}

function imageSourceKey_(request) {
  const query = normalizeQuery_(request && request.query || {});
  return JSON.stringify([query.e, query.family, query.species, String(request.reportId || ''), String(request.manifest || '')]);
}

/** Server-only plan: file metadata and routing, never report text or JPEG bytes. */
function prepareScanPlan_(request, checkTime, timing) {
  const query = normalizeQuery_(request && request.query || {});
  if (!query.family || !query.species) throw viewerError_('Reload the page before loading scans.');
  const root = DriveApp.getFolderById(TRANSCRIPTION_VIEWER.ROOT_FOLDER_ID);
  const family = measured_(timing, 'familyFolder', () => familyFolder_(root, query, checkTime));
  const plan = { sourceKey: imageSourceKey_(request), path: [], report: null };
  let records = [];
  if (request.reportId) {
    const file = DriveApp.getFileById(String(request.reportId));
    const version = fileVersion_(file);
    const parents = file.getParents();
    let inFamily = false;
    while (parents.hasNext()) {
      checkTime();
      if (parents.next().getId() === family.getId()) inFamily = true;
    }
    if (!inFamily || !reportName_(file.getName(), query.species)) {
      throw viewerError_('The displayed report is no longer in its expected folder. Reload the page.');
    }
    if (file.getSize() > TRANSCRIPTION_VIEWER.MAX_REPORT_BYTES) {
      throw viewerError_('The displayed report exceeds the viewer size limit.');
    }
    records = measured_(timing, 'reportValidation', () => parseReport_(file.getBlob().getDataAsString('UTF-8'), query.digits));
    checkTime();
    if (!records.length || imageManifest_(records) !== request.manifest || fileVersion_(file) !== version) {
      throw viewerError_('The displayed report has changed. Reload the page before viewing its scans.');
    }
    plan.report = { id: file.getId(), name: file.getName(), version: version, familyId: family.getId() };
  }
  const scanOnly = !records.length || records.every(record => record.status === 'MISSING');
  let message = '';
  let jpeg;
  if (scanOnly) {
    jpeg = measured_(timing, 'scanFolders', () => sourceJpegFolder_(family, query.species, checkTime, plan.path));
    const discovered = measured_(timing, 'scanDiscovery', () => discoverSourceScans_(jpeg, query, checkTime));
    records = discovered.records;
    message = discovered.message;
  }
  const result = { query: query, records: records };
  measured_(timing, 'imageMetadata', () => attachSourceImages_(result, family, checkTime, jpeg, plan));
  plan.scanOnly = scanOnly;
  plan.message = message;
  plan.galleries = records.filter(record => record.status !== 'MISSING').map(record => ({
      numbers: record.numbers, images: record.images, message: record.imageMessage
    }));
  plan.fingerprint = digest_(JSON.stringify([plan.sourceKey, plan.path, plan.report, plan.galleries]));
  if (timing) timing.count('images', plan.galleries.reduce((sum, gallery) => sum + gallery.images.length, 0));
  return plan;
}

function hasParent_(item, parentId) {
  const parents = item.getParents();
  while (parents.hasNext()) if (parents.next().getId() === parentId) return true;
  return false;
}

/** Recheck actual Drive access/metadata; a cached plan never grants access. */
function validateScanPlan_(plan, checkTime) {
  if (plan.report) {
    const file = DriveApp.getFileById(plan.report.id);
    if (file.getName() !== plan.report.name || fileVersion_(file) !== plan.report.version ||
        !hasParent_(file, plan.report.familyId)) {
      throw viewerError_('The displayed report has changed or moved. Reload the page before viewing its scans.');
    }
  }
  let jpeg;
  for (const step of plan.path) {
    checkTime();
    jpeg = DriveApp.getFolderById(step.id);
    if (jpeg.getName() !== step.name || !hasParent_(jpeg, step.parentId)) {
      throw viewerError_('The source scan folder has changed or moved. Reload the page.');
    }
  }
  return jpeg;
}

/** One full JPEG per response. The browser limits concurrent calls and fixes display order. */
function loadSourceImage(request) {
  const timing = viewerTiming_('image');
  let response;
  try {
    timing.measure('access', requireWorkbookAccess_);
    const checkTime = scanDeadline_();
    if (!request || !Number.isInteger(request.index) || request.index < 0 ||
        request.index >= TRANSCRIPTION_VIEWER.MAX_FILES_LISTED || typeof request.fingerprint !== 'string') {
      throw viewerError_('Reload the page before loading scans.');
    }
    const key = imageSourceKey_(request.sourceRequest);
    let plan = /^[a-f0-9-]{36}$/i.test(request.token || '') ?
      measured_(timing, 'planCacheRead', () => cachedJson_(userCache_(), 'scan-plan-v1:' + request.token)) : null;
    if (!plan || plan.sourceKey !== key || plan.fingerprint !== request.fingerprint) {
      timing.count('planCacheHit', false);
      plan = prepareScanPlan_(request.sourceRequest, checkTime, timing);
      if (plan.fingerprint !== request.fingerprint) throw viewerError_('The source scans have changed. Reload the page.');
    } else timing.count('planCacheHit', true);
    const scans = plan.galleries.reduce((all, gallery) => all.concat(gallery.images), []);
    const scan = scans[request.index];
    if (!scan || !scan.fileId || scan.message) throw viewerError_('This scan is unavailable. Use its original link or reload the page.');
    const jpeg = measured_(timing, 'sourceValidation', () => validateScanPlan_(plan, checkTime));
    const files = jpeg.getFilesByName(scan.name);
    if (!files.hasNext()) throw viewerError_('This source JPG was not found or is not accessible.');
    const file = files.next();
    if (files.hasNext()) throw viewerError_('More than one source JPG has this filename. No image was selected.');
    if (file.getId() !== scan.fileId || fileVersion_(file) !== scan.version || file.getSize() !== scan.size) {
      throw viewerError_('This source scan has changed. Reload the page before viewing it.');
    }
    const base64 = readFullJpeg_(file, scan.size, checkTime, timing);
    if (fileVersion_(file) !== scan.version) throw viewerError_('This source scan changed while loading. Reload the page.');
    response = { base64: base64 };
  } catch (error) {
    response = { error: error.viewerMessage || 'This source scan could not be loaded. Try again or open the original JPG.' };
  }
  response.timings = timing.finish();
  return response;
}

/** Used only without a transcription: exact numbers and complete physical-card groups. */
function discoverSourceScans_(jpeg, query, checkTime) {
  const files = jpeg.getFiles();
  const groups = new Map();
  const issues = [];
  let listed = 0, selected = 0;
  while (files.hasNext()) {
    checkTime();
    if (++listed > TRANSCRIPTION_VIEWER.MAX_FILES_LISTED) {
      throw viewerError_('The scan folder listing limit was reached. The search is incomplete.');
    }
    const name = files.next().getName();
    if (!/\.jpe?g$/i.test(name)) continue;
    const numbers = Array.from(name.matchAll(/(?:^|_)E([0-9]+)(?=[^0-9]|$)/gi), match => match[1]);
    if (!numbers.includes(query.digits)) continue;
    if (++selected > TRANSCRIPTION_VIEWER.MAX_IMAGES) {
      throw viewerError_('Too many matching scans were found. The scan search is incomplete.');
    }
    const match = /^(.+?_E\d+(?:_E\d+)*)(?:\(([A-Z0-9]+)\)|[_-]([A-Z]|\d+)-?)?(?:_exchanged)?\.jpe?g$/i.exec(name);
    if (!match || /[/\\\x00-\x1f]/.test(name)) {
      issues.push('A matching scan has an unrecognized filename: ' + name);
      continue;
    }
    const key = match[1].toLowerCase();
    if (!groups.has(key)) groups.set(key, { base: match[1], items: [] });
    groups.get(key).items.push({ name: name, side: sourceScanSide_(name) });
  }
  const records = Array.from(groups.values()).sort((a, b) =>
    a.base.localeCompare(b.base, undefined, { numeric: true, sensitivity: 'base' })).map(group => {
    group.items.sort((a, b) => a.side - b.side || a.name.localeCompare(b.name));
    const sides = group.items.map(item => item.side);
    const invalid = sides.includes(null) || new Set(sides).size !== sides.length;
    const warnings = [];
    if (invalid) warnings.push('Ambiguous or invalid side labels for ' + group.base + '. No images from this card were selected.');
    else {
      if (sides[0] !== 1) warnings.push('Front image is missing; supplied images are labelled as backs.');
      if (sides.some((side, i) => i && side - sides[i - 1] > 1)) warnings.push('Gap in side labels; an image may be missing.');
    }
    return { numbers: Array.from(group.base.matchAll(/_E(\d+)(?=_|$)/gi), match => 'E' + match[1]),
      status: 'SCANS', files: invalid ? [] : group.items.map(item => item.name),
      images: [], imageMessage: warnings.join(' ') };
  });
  return { records: records, message: issues.join('\n') || (records.length ? '' :
    'No matching source JPGs were found in the accessible species folder.') };
}

/** Read only report-listed or independently discovered filenames in the resolved folder. */
function attachSourceImages_(result, family, checkTime, jpeg, plan) {
  const records = result.records.filter(record => record.status !== 'MISSING');
  if (!records.length) return;
  try {
    if (!jpeg) jpeg = sourceJpegFolder_(family, result.query.species, checkTime, plan && plan.path);
  } catch (error) {
    for (const record of records) record.imageMessage = error.viewerMessage ||
      'Source scans could not be loaded. Check your access to the JPEG folder.';
    return;
  }
  let totalBytes = 0;
  let imageCount = 0;
  for (const record of records) {
    if (!record.files.length) {
      if (!record.imageMessage) record.imageMessage = 'Source filenames are not listed in this report.';
      continue;
    }
    let backCount = 0;
    for (const name of record.files) {
      const side = sourceScanSide_(name);
      const label = side === 1 ? 'Front' : side > 1 ?
        'Back' + (++backCount > 1 ? ' ' + backCount : '') : 'Scan ' + (record.images.length + 1);
      const scan = { name: name, label: label, url: '', base64: '', message: '' };
      record.images.push(scan);
      if (/[/\\\x00-\x1f]/.test(name) || !/\.jpe?g$/i.test(name)) {
        scan.message = 'The source filename is not a JPEG filename.';
        continue;
      }
      try {
        checkTime();
        const files = jpeg.getFilesByName(name);
        if (!files.hasNext()) {
          scan.message = 'This source JPG was not found or is not accessible.';
          continue;
        }
        const file = files.next();
        if (files.hasNext()) {
          scan.message = 'More than one source JPG has this filename. No image was selected.';
          continue;
        }
        scan.url = 'https://drive.google.com/file/d/' + encodeURIComponent(file.getId()) + '/view';
        const size = file.getSize();
        if (++imageCount > TRANSCRIPTION_VIEWER.MAX_IMAGES ||
            totalBytes + size > TRANSCRIPTION_VIEWER.MAX_TOTAL_IMAGE_BYTES) {
          scan.message = 'The image display limit was reached. Open the original JPG below.';
          continue;
        }
        if (size > TRANSCRIPTION_VIEWER.MAX_IMAGE_BYTES) {
          scan.message = 'This scan is too large to display here. Open the original JPG below.';
          continue;
        }
        if (plan) {
          scan.fileId = file.getId();
          scan.size = size;
          scan.version = fileVersion_(file);
        } else {
          scan.base64 = readFullJpeg_(file, size, checkTime);
        }
        totalBytes += size;
      } catch (error) {
        scan.message = error.viewerMessage || 'This source scan could not be loaded. Try again or open the original JPG below.';
      }
    }
  }
}

function readFullJpeg_(file, expectedSize, checkTime, timing) {
  const bytes = measured_(timing, 'imageDownload', () => file.getBlob().getBytes());
  checkTime();
  if (bytes.length !== expectedSize || bytes.length > TRANSCRIPTION_VIEWER.MAX_IMAGE_BYTES) {
    throw viewerError_('This scan has changed size or is too large to display here. Open the original JPG below.');
  }
  if (bytes.length < 3 || (bytes[0] & 255) !== 255 || (bytes[1] & 255) !== 216 || (bytes[2] & 255) !== 255) {
    throw viewerError_('This file could not be displayed as a JPEG. Open the original below.');
  }
  if (timing) timing.count('imageBytes', bytes.length);
  return measured_(timing, 'imageEncode', () => Utilities.base64Encode(bytes));
}
