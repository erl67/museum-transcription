/** Read-only pilot. Install as a separate Apps Script project; see README.md. */
const TRANSCRIPTION_VIEWER = Object.freeze({
  // Family root already used by Egg_Scan_Linker.gs.
  ROOT_FOLDER_ID: '1rnIKpQg83jHh85Qr_TQqJ-ayEs0Q65HJ',
  // Optional override; otherwise locate the CSV in the sibling Transcription folder.
  CATALOGUE_FILE_ID: '',
  CATALOGUE_FOLDER_NAME: 'Transcription',
  CATALOGUE_FILE_NAME: 'EggSlipReorganizationProject_FULL.xlsx - Full List.csv',
  MAX_CATALOGUE_BYTES: 10 * 1024 * 1024,
  MAX_REPORT_BYTES: 10 * 1024 * 1024,
  MAX_REPORTS_READ: 40,
  MAX_FILES_LISTED: 5000,
  MAX_LOOKUP_MS: 45000
});

function doGet(e) {
  const params = (e && e.parameter) || {};
  const page = HtmlService.createTemplateFromFile('Viewer');
  page.query = {
    e: String(params.e || '').slice(0, 80),
    family: String(params.family || '').slice(0, 200),
    species: String(params.species || '').slice(0, 200)
  };
  page.appUrl = ScriptApp.getService().getUrl();
  page.result = null;
  if (page.query.e || page.query.family || page.query.species) {
    try {
      page.result = lookupTranscription_(page.query);
    } catch (error) {
      page.result = { error: error.viewerMessage ||
        'The reports could not be read. Check your Google account has access to the Family folder and its reports, then try again.' };
    }
  }
  return page.evaluate().setTitle('Egg-slip transcription')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function viewerError_(message) {
  const error = new Error(message);
  error.viewerMessage = message;
  return error;
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

/** Use the same CSV as the transcription program, not a second copied catalogue. */
function readCatalogue_(root, checkTime) {
  let file;
  if (TRANSCRIPTION_VIEWER.CATALOGUE_FILE_ID) {
    file = DriveApp.getFileById(TRANSCRIPTION_VIEWER.CATALOGUE_FILE_ID);
  } else {
    const candidates = new Map();
    const parents = root.getParents();
    while (parents.hasNext()) {
      checkTime();
      const folders = parents.next().getFoldersByName(TRANSCRIPTION_VIEWER.CATALOGUE_FOLDER_NAME);
      while (folders.hasNext()) {
        checkTime();
        const files = folders.next().getFilesByName(TRANSCRIPTION_VIEWER.CATALOGUE_FILE_NAME);
        while (files.hasNext()) {
          checkTime();
          const found = files.next();
          candidates.set(found.getId(), found);
        }
      }
    }
    if (candidates.size !== 1) {
      throw viewerError_(candidates.size ?
        'More than one catalogue CSV was found. The catalogue location needs to be checked before searching by E-number.' :
        'The catalogue CSV was not found or is not accessible. Check catalogue access, or use a spreadsheet link that includes family and species.');
    }
    file = candidates.values().next().value;
  }
  checkTime();
  if (file.getSize() > TRANSCRIPTION_VIEWER.MAX_CATALOGUE_BYTES) {
    throw viewerError_('The catalogue exceeds the viewer size limit. The E-number search could not be completed.');
  }
  const text = file.getBlob().getDataAsString('UTF-8').replace(/^\uFEFF/, '');
  checkTime();
  try {
    return Utilities.parseCsv(text);
  } catch (error) {
    throw viewerError_('The catalogue CSV could not be read. Check its export format, or use a spreadsheet link with family and species.');
  }
}

function routeFromCatalogue_(query, rows) {
  const header = (rows[0] || []).map(value => String(value).trim());
  const fields = ['catalogNumber', 'Family', 'Scientific Name'];
  const columns = fields.map(name => header.indexOf(name));
  if (fields.some((name, i) => columns[i] < 0 || header.lastIndexOf(name) !== columns[i])) {
    throw viewerError_('The catalogue needs one column each named catalogNumber, Family, and Scientific Name.');
  }
  const routes = new Map();
  for (const row of rows.slice(1)) {
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

function lookupTranscription_(rawQuery) {
  let query = normalizeQuery_(rawQuery);
  const started = Date.now();
  const checkTime = () => {
    if (Date.now() - started > TRANSCRIPTION_VIEWER.MAX_LOOKUP_MS) {
      throw viewerError_('The search time limit was reached. The search is incomplete; please try again.');
    }
  };
  const root = DriveApp.getFolderById(TRANSCRIPTION_VIEWER.ROOT_FOLDER_ID);
  if (!query.family || !query.species) {
    query = routeFromCatalogue_(query, readCatalogue_(root, checkTime));
    checkTime();
  }
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
  const files = matches[0].getFiles();
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
  return selectLatestRecord_(candidates, query, file => {
    checkTime();
    if (file.getSize() > TRANSCRIPTION_VIEWER.MAX_REPORT_BYTES) {
      throw viewerError_('A report exceeds the pilot viewer size limit. The search is incomplete.');
    }
    return file.getBlob().getDataAsString('UTF-8');
  }, checkTime);
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
      throw viewerError_('The pilot report limit was reached. The search is incomplete; older reports have not all been checked.');
    }
    const records = parseReport_(readText(candidate.file), query.digits);
    if (records.length) {
      return { query: query, records: records, reportDate: candidate.info.date,
        sourceUrl: 'https://drive.google.com/file/d/' + encodeURIComponent(candidate.file.getId()) + '/view' };
    }
  }
  return { query: query, records: [], message: 'No transcription available in the species reports yet. ' +
    'Use this same link again after a report has been created and synced to Drive.' };
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
        review: '', needsReview: false, text: block.lines.join('\n').trimEnd() };
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
      review: remaining.join('    |    '), needsReview: needsReview, text: bodyText };
  });
}
