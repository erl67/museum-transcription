/** Read-only transcription viewer. Install as a separate Apps Script project; see README.md. */
const TRANSCRIPTION_VIEWER = Object.freeze({
  // Master workbook supplied by the maintainer; its Drive permissions gate viewer access.
  WORKBOOK_FILE_ID: '1P-sWhtIlRHcbh4D5rV0p0sv-MF_Th1lc',
  // Family root already used by Egg_Scan_Linker.gs.
  ROOT_FOLDER_ID: '1rnIKpQg83jHh85Qr_TQqJ-ayEs0Q65HJ',
  // Tab name in the saved Excel workbook; the browser gid is not an XLSX worksheet ID.
  CATALOGUE_SHEET_NAME: 'Full List',
  MAX_CATALOGUE_BYTES: 25 * 1024 * 1024,
  MAX_CATALOGUE_XML_BYTES: 80 * 1024 * 1024,
  MAX_REPORT_BYTES: 10 * 1024 * 1024,
  MAX_REPORTS_READ: 40,
  MAX_FILES_LISTED: 5000,
  MAX_LOOKUP_MS: 45000,
  MAX_IMAGE_BYTES: 12 * 1024 * 1024,
  MAX_TOTAL_IMAGE_BYTES: 24 * 1024 * 1024,
  MAX_IMAGES: 40
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
  try {
    requireWorkbookAccess_();
    if (page.query.e || page.query.family || page.query.species) {
      page.result = lookupTranscription_(page.query);
    }
  } catch (error) {
    page.result = { error: error.viewerMessage ||
      'The reports could not be read. Check your Google account has access to the Family folder and its reports, then try again.' };
  }
  return page.evaluate().setTitle('Egg-slip transcription')
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
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

/** Read the saved master Excel workbook directly; never convert it or fall back to a CSV. */
function readCatalogue_(query, checkTime) {
  checkTime();
  const file = DriveApp.getFileById(TRANSCRIPTION_VIEWER.WORKBOOK_FILE_ID);
  if (file.getMimeType() !== 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet') {
    throw viewerError_('The catalogue must be the master Excel (.xlsx) file. Check WORKBOOK_FILE_ID; a shortcut or a converted Google Sheet is a different file.');
  }
  if (file.getSize() > TRANSCRIPTION_VIEWER.MAX_CATALOGUE_BYTES) {
    throw viewerError_('The master workbook exceeds the viewer size limit. The E-number search could not be completed.');
  }
  try {
    const blob = file.getBlob().setContentType('application/zip');
    const parts = new Map();
    for (const part of Utilities.unzip(blob)) {
      checkTime();
      const name = part.getName();
      if (parts.has(name)) throw new Error('Duplicate workbook part');
      parts.set(name, part);
    }
    let xmlBytes = 0;
    const xml = name => {
      checkTime();
      if (!parts.has(name)) throw new Error('Missing workbook part');
      const bytes = parts.get(name).getBytes();
      xmlBytes += bytes.length;
      if (xmlBytes > TRANSCRIPTION_VIEWER.MAX_CATALOGUE_XML_BYTES) {
        throw viewerError_('The expanded workbook data exceeds the viewer size limit. The E-number search is incomplete.');
      }
      const text = parts.get(name).getDataAsString('UTF-8');
      // The catalogue needs no document types, external entities or external relationships.
      if (/<!DOCTYPE|<!ENTITY/i.test(text)) throw new Error('Unsupported XML declarations');
      const root = XmlService.parse(text).getRootElement();
      checkTime();
      return root;
    };
    return catalogueFromXlsx_(query, xml, checkTime);
  } catch (error) {
    if (error.viewerMessage) throw error;
    throw viewerError_('The master Excel workbook could not be read. Check that it is a saved, unencrypted .xlsx file and that the catalogue tab is configured correctly.');
  }
}

function xlsxAttribute_(element, name) {
  const value = element && element.getAttribute(name);
  return value ? value.getValue() : '';
}

function xlsxChildren_(element, name) {
  return element ? element.getChildren(name, element.getNamespace()) : [];
}

function xlsxChild_(element, name) {
  return element ? element.getChild(name, element.getNamespace()) : null;
}

// Exclude phonetic guides and formatting metadata from rich text.
function xlsxText_(element) {
  return element ? element.getChildren().map(child => child.getName() === 't' ? child.getText() :
    child.getName() === 'r' ? xlsxText_(child) : '').join('') : '';
}

/** A deliberately small reader for the three catalogue columns, not a calculation engine. */
function catalogueFromXlsx_(query, xml, checkTime) {
  const workbook = xml('xl/workbook.xml');
  const sheets = xlsxChildren_(xlsxChild_(workbook, 'sheets'), 'sheet')
    .filter(sheet => xlsxAttribute_(sheet, 'name') === TRANSCRIPTION_VIEWER.CATALOGUE_SHEET_NAME);
  if (sheets.length !== 1) {
    throw viewerError_('The master workbook needs one catalogue tab named "' +
      TRANSCRIPTION_VIEWER.CATALOGUE_SHEET_NAME + '". Check CATALOGUE_SHEET_NAME in Code.gs.');
  }
  const id = sheets[0].getAttributes().find(attribute => attribute.getName() === 'id');
  const relationships = xml('xl/_rels/workbook.xml.rels');
  const links = xlsxChildren_(relationships, 'Relationship');
  // Use workbook relationships, not the browser gid or a guessed sheet1.xml path.
  const partName = relationship => {
    if (!relationship || xlsxAttribute_(relationship, 'TargetMode') === 'External') {
      throw new Error('Invalid workbook relationship');
    }
    const target = xlsxAttribute_(relationship, 'Target');
    const segments = (target.startsWith('/') ? target.slice(1) : 'xl/' + target).split('/');
    const resolved = [];
    for (const segment of segments) {
      if (segment === '..') {
        if (!resolved.length) throw new Error('Invalid workbook path');
        resolved.pop();
      } else if (segment && segment !== '.') resolved.push(segment);
    }
    return resolved.join('/');
  };
  const sheetLinks = links.filter(link => id && xlsxAttribute_(link, 'Id') === id.getValue() &&
    /\/worksheet$/.test(xlsxAttribute_(link, 'Type')));
  if (sheetLinks.length !== 1) throw new Error('Missing worksheet relationship');
  const optionalPart = type => {
    const matches = links.filter(link => xlsxAttribute_(link, 'Type').endsWith('/' + type));
    if (matches.length > 1) throw new Error('Ambiguous workbook relationship');
    return matches.length ? xml(partName(matches[0])) : null;
  };
  const shared = xlsxChildren_(optionalPart('sharedStrings'), 'si').map(item => xlsxText_(item));
  const styles = optionalPart('styles');
  const formats = new Map(xlsxChildren_(xlsxChild_(styles, 'numFmts'), 'numFmt')
    .map(format => [xlsxAttribute_(format, 'numFmtId'), xlsxAttribute_(format, 'formatCode')]));
  const cellStyles = xlsxChildren_(xlsxChild_(styles, 'cellXfs'), 'xf');
  const cellValue = (cell, numberColumn = false) => {
    if (!cell) return '';
    const type = xlsxAttribute_(cell, 't');
    const value = xlsxChild_(cell, 'v');
    if (xlsxChild_(cell, 'f') && !value) {
      throw viewerError_('A catalogue formula has no saved result. Recalculate and save the master workbook, then try again.');
    }
    if (type === 'inlineStr') return xlsxText_(xlsxChild_(cell, 'is'));
    const text = value ? value.getText() : '';
    if (type === 's') {
      if (!/^\d+$/.test(text) || Number(text) >= shared.length) throw new Error('Invalid shared string');
      return shared[Number(text)];
    }
    if (type === 'str') return text;
    if (type && type !== 'n') {
      throw viewerError_('A catalogue lookup cell contains an error or unsupported value. Check catalogNumber, Family and Scientific Name in the master workbook.');
    }
    if (!numberColumn || !text) return text;
    const number = Number(text);
    if (!Number.isSafeInteger(number) || number < 0) throw new Error('Invalid catalogue number');
    const styleIndex = xlsxAttribute_(cell, 's') || '0';
    if (!/^\d+$/.test(styleIndex) || (Number(styleIndex) && !cellStyles[Number(styleIndex)])) {
      throw new Error('Invalid cell style');
    }
    const formatId = xlsxAttribute_(cellStyles[Number(styleIndex)], 'numFmtId') || '0';
    if (formatId === '0' || formatId === '49') return String(number);
    const format = formats.get(formatId) || '';
    const match = /^(?:(E)|"E"|\\E)?(0+)$/i.exec(format);
    if (!match) {
      throw viewerError_('A catalogue number uses an unsupported number format. Store E-numbers as text to preserve their exact digits and leading zeros.');
    }
    return (/E/i.test(format) ? 'E' : '') + String(number).padStart(match[2].length, '0');
  };
  const sheet = xml(partName(sheetLinks[0]));
  const rows = xlsxChildren_(xlsxChild_(sheet, 'sheetData'), 'row');
  const first = rows.findIndex(row => xlsxChildren_(row, 'c').some(cell => cellValue(cell).trim()));
  const headerCells = first < 0 ? [] : xlsxChildren_(rows[first], 'c');
  const fields = ['catalogNumber', 'Family', 'Scientific Name'];
  const columns = fields.map(field => {
    const matches = headerCells.filter(cell => cellValue(cell).trim() === field);
    if (matches.length !== 1) {
      throw viewerError_('The catalogue needs one column each named catalogNumber, Family, and Scientific Name in its first nonempty row.');
    }
    const address = /^([A-Z]+)[1-9]\d*$/.exec(xlsxAttribute_(matches[0], 'r'));
    if (!address) throw new Error('Invalid column address');
    return address[1];
  });
  const result = [fields];
  for (const row of rows.slice(first + 1)) {
    checkTime();
    const cells = new Map();
    for (const cell of xlsxChildren_(row, 'c')) {
      const address = /^([A-Z]+)[1-9]\d*$/.exec(xlsxAttribute_(cell, 'r'));
      if (!address || !columns.includes(address[1])) continue;
      if (cells.has(address[1])) throw new Error('Duplicate lookup cell');
      cells.set(address[1], cell);
    }
    const number = cellValue(cells.get(columns[0]), true);
    const match = /^E?([0-9]+)$/i.exec(number.trim());
    if (!match || match[1] !== query.digits) continue;
    result.push([number, cellValue(cells.get(columns[1])), cellValue(cells.get(columns[2]))]);
  }
  return result;
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
    throw viewerError_(query.e + ' was not found in the master catalogue. Check the number and the saved workbook.');
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
    query = routeFromCatalogue_(query, readCatalogue_(query, checkTime));
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
  const result = selectLatestRecord_(candidates, query, file => {
    checkTime();
    if (file.getSize() > TRANSCRIPTION_VIEWER.MAX_REPORT_BYTES) {
      throw viewerError_('A report exceeds the viewer size limit. The search is incomplete.');
    }
    return file.getBlob().getDataAsString('UTF-8');
  }, checkTime);
  if (result.records.length) attachSourceImages_(result, matches[0], checkTime);
  return result;
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
function scanChildFolder_(parent, name, checkTime) {
  const folders = parent.getFolders();
  const found = [];
  while (folders.hasNext()) {
    checkTime();
    const folder = folders.next();
    if (folder.getName().toLowerCase() === name.toLowerCase()) found.push(folder);
  }
  if (found.length > 1) throw viewerError_('More than one scan folder matches this record. No images were selected.');
  return found[0] || null;
}

function sourceJpegFolder_(family, species, checkTime) {
  const direct = scanChildFolder_(family, species, checkTime);
  const genus = scanChildFolder_(family, species.split('_')[0], checkTime);
  const nested = genus ? scanChildFolder_(genus, species, checkTime) : null;
  const candidates = new Map();
  for (const folder of [direct, nested]) {
    if (!folder) continue;
    const jpeg = scanChildFolder_(folder, 'JPEG', checkTime);
    if (jpeg) candidates.set(jpeg.getId(), jpeg);
  }
  if (candidates.size !== 1) {
    throw viewerError_(candidates.size ?
      'More than one JPEG folder matches this record. No images were selected.' :
      'The source JPEG folder was not found or is not accessible.');
  }
  return candidates.values().next().value;
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

/** Images are transient, authenticated reads of the exact FILES listed in the report. */
function attachSourceImages_(result, family, checkTime) {
  const records = result.records.filter(record => record.status !== 'MISSING');
  if (!records.length) return;
  let jpeg;
  try {
    jpeg = sourceJpegFolder_(family, result.query.species, checkTime);
  } catch (error) {
    for (const record of records) record.imageMessage = error.viewerMessage ||
      'Source scans could not be loaded. Check your access to the JPEG folder.';
    return;
  }
  let totalBytes = 0;
  let imageCount = 0;
  for (const record of records) {
    if (!record.files.length) record.imageMessage = 'Source filenames are not listed in this report.';
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
        if (++imageCount > TRANSCRIPTION_VIEWER.MAX_IMAGES ||
            totalBytes + file.getSize() > TRANSCRIPTION_VIEWER.MAX_TOTAL_IMAGE_BYTES) {
          scan.message = 'The image display limit was reached. Open the original JPG below.';
          continue;
        }
        if (file.getSize() > TRANSCRIPTION_VIEWER.MAX_IMAGE_BYTES) {
          scan.message = 'This scan is too large to display here. Open the original JPG below.';
          continue;
        }
        const bytes = file.getBlob().getBytes();
        checkTime();
        if (bytes.length > TRANSCRIPTION_VIEWER.MAX_IMAGE_BYTES ||
            totalBytes + bytes.length > TRANSCRIPTION_VIEWER.MAX_TOTAL_IMAGE_BYTES) {
          scan.message = 'This scan is too large to display here. Open the original JPG below.';
          continue;
        }
        if (bytes.length < 3 || (bytes[0] & 255) !== 255 ||
            (bytes[1] & 255) !== 216 || (bytes[2] & 255) !== 255) {
          scan.message = 'This file could not be displayed as a JPEG. Open the original below.';
          continue;
        }
        scan.base64 = Utilities.base64Encode(bytes);
        totalBytes += bytes.length;
      } catch (error) {
        scan.message = 'This source scan could not be loaded. Try again or open the original JPG below.';
      }
    }
  }
}
