// Run from the repository root: node --test apps_script/transcription_viewer/test_viewer.cjs
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { test } = require('node:test');
const code = fs.readFileSync(path.join(__dirname, 'Code.gs'), 'utf8');
function context(extra = {}, source = code) {
  const ctx = vm.createContext(extra);
  vm.runInContext(source, ctx);
  return ctx;
}
const ctx = context();
const bar = '='.repeat(50);
function banner(number, missing = false) {
  const label = 'CM' + number + (missing ? ' (MISSING)' : '');
  return '='.repeat(22) + label + '='.repeat(Math.max(2, 28 - label.length));
}
function block(numbers = ['001'], body = 'Collector: A\nANNOTATIONS:\n[uncertain]\nTRANSCRIPTION NOTES:\nNone.', status = 'REVIEW', reused = false) {
  return numbers.map(n => banner(n)).join('\n') + '\n' + [
    'ID: Genus_species_E' + numbers.join('_E'),
    'STATUS: ' + status + (reused ? ' (reused)' : ''),
    'REVIEW: 1 bracketed passage(s)', 'FILES: source.jpg', 'MODEL: technical-model',
    'BUILD: internal | PROMPT: internal', 'PROMPT SHA256: internal', 'INPUT SHA256: internal',
    'SETTINGS: {"private":"internal"}', 'MODEL VERSION: internal', 'TOKENS: internal',
    bar, body
  ].join('\n') + '\n\n\n';
}
const query = { e: 'E001', digits: '001', family: 'Family', species: 'Genus_species' };
function candidate(suffix, text, id = suffix) {
  return { info: ctx.reportName_('Genus_species_transcriptions_' + suffix + '.txt', query.species),
    file: { text, getId: () => id } };
}
const select = files => ctx.selectLatestRecord_(files, query, f => f.text);
const missing = text => banner('001', true) + '\n' + text + '\n\n\n';

test('normalizes complete identifiers without losing zeros; rejects mixed identifiers', () => {
  for (const value of ['E001', 'cm001', '001']) assert.equal(ctx.normalizeQuery_({ ...query, e: value }).e, 'E001');
  for (const value of ['E1/E2', 'E12x', 'E001*', '', '1.0']) assert.throws(() => ctx.normalizeQuery_({ ...query, e: value }));
  assert.equal(ctx.normalizeQuery_({ ...query, species: 'SERINUS sp. subspecies' }).species, 'Serinus_sp');
  assert.throws(() => ctx.normalizeQuery_({ ...query, family: '../Family' }));
});

test('recognizes only normal species reports with valid dates and collision counters', () => {
  assert.equal(ctx.reportName_('GENUS_SPECIES_transcriptions_20261014_0915_10.txt', query.species).counter, 10);
  for (const name of ['Genus_species_transcriptions_20260230_0915.txt',
    'Genus_species_transcriptions_20261014_2460.txt',
    'Genus_species_transcriptions_20261014_0915_0.txt',
    'Genus_species_transcriptions_cache.jsonl',
    'Other_species_transcriptions_20261014_0915.txt',
    'E001_g35fl_Genus_species_20261014_0915.txt', 'test_20261014_0915.txt']) {
    assert.equal(ctx.reportName_(name, query.species), null, name);
  }
});

test('matches full CM identifiers; never matches prefixes or loses leading zeros', () => {
  const report = block(['1']) + block(['001']) + block(['0010']);
  const records = ctx.parseReport_(report, '001');
  assert.equal(records.length, 1);
  assert.equal(records[0].numbers.join(','), 'E001');
  assert.equal(ctx.parseReport_(report, '00').length, 0);
});

test('shared slip preserves all numbers, sides, notes and exact historical wording', () => {
  const body = 'Date: June 1924\nANNOTATIONS:\n[illegible]\nBACK OF SLIP:\nÜber dem Fluß\nBACK OF SLIP 2:\n[blank]\nTRANSCRIPTION NOTES:\nTorn.';
  const report = block(['001', '002'], body);
  for (const number of ['001', '002']) {
    const record = ctx.parseReport_(report, number)[0];
    assert.equal(record.numbers.join(','), 'E001,E002');
    assert.equal(record.text, body);
  }
});

test('omits technical header but preserves identically named fields in source text', () => {
  const body = 'MODEL: visible historical label\nTOKENS: source wording\nTRANSCRIPTION NOTES:\nNone.';
  const record = ctx.parseReport_(block(['001'], body), '001')[0];
  assert.equal(record.text, body);
  assert.equal(record.review, '1 bracketed passage(s)');
  assert.doesNotMatch(JSON.stringify(record), /internal|technical-model/);
});

test('supports BOM, CRLF and reused statuses', () => {
  const record = ctx.parseReport_('\ufeff' + block(['001'], 'body', 'OK', true).replace(/\n/g, '\r\n'), '001')[0];
  assert.equal(record.status, 'OK');
  assert.equal(record.reused, true);
  assert.equal(record.text, 'body');
});

test('CSV-only blocks remain separate, including duplicate rows and partial dates', () => {
  const records = ctx.parseReport_(missing('Collector: A\ndate collected m/d/y: June 1924') +
    missing('Collector: B'), '001');
  assert.equal(records.length, 2);
  assert.equal(records[0].status, 'MISSING');
  assert.match(records[0].text, /June 1924/);
  assert.equal(records[1].text, 'Collector: B');
});

test('uncatalogued filename banners end preceding numbered records', () => {
  const filenameBanner = '='.repeat(22) + 'Genus_species_Uncatalogued01.jpg' + '==';
  const report = block(['001'], 'numbered body') + filenameBanner + '\nID: other\n' + bar + '\nother body\n\n\n';
  assert.equal(ctx.parseReport_(report, '001')[0].text, 'numbered body');
});

test('strips complete run footer and preserves final card text', () => {
  const footer = 'TOKENS: 10 in\nAVERAGE/CALL (1/1 calls with complete usage): 10 in\nRUN: 1 calls | 10 tokens | $0.00\n';
  assert.equal(ctx.parseReport_(block(['001'], 'last body', 'OK') + footer, '001')[0].text, 'last body');
  assert.equal(ctx.parseReport_(missing('Remarks: Some record') + footer, '001')[0].text, 'Remarks: Some record');
});

test('latest failure or pause is shown, with its retained text and without service details', () => {
  for (const status of ['FAILED', 'PAUSED']) {
    const report = block(['001'], 'ERROR: private service details\nSAVED RESPONSE (see error above):\nPartial [uncertain] text', status);
    const result = select([candidate('20261013_1200', block()), candidate('20261014_1200', report)]);
    assert.equal(result.records[0].status, status);
    assert.equal(result.records[0].text, 'Partial [uncertain] text');
  }
  assert.equal(ctx.parseReport_(block(['001'], 'ERROR: service details', 'FAILED'), '001')[0].text, '');
});

test('does not silently substitute an older reading for a newest CSV-only block', () => {
  const result = select([candidate('20261013_1200', block()), candidate('20261014_1200', missing('Collector: A'))]);
  assert.equal(result.records[0].status, 'MISSING');
});

test('checks older reports when newer reports cover different E-numbers', () => {
  const result = select([candidate('20261013_1200', block(['001'], 'older')),
    candidate('20261014_1200', block(['002'], 'newer unrelated'))]);
  assert.equal(result.records[0].text, 'older');
  assert.equal(result.reportDate, '2026-10-13 12:00');
});

test('orders by filename timestamp and numeric collision counter', () => {
  const result = select([candidate('20261014_1200_2', block(['001'], 'two')),
    candidate('20261014_1200_10', block(['001'], 'ten')),
    candidate('20261013_1200_99', block(['001'], 'older'))]);
  assert.equal(result.records[0].text, 'ten');
});

test('duplicate timestamps are explicit ambiguity, not an arbitrary newest report', () => {
  assert.throws(() => select([candidate('20261014_1200', block(), 'a'),
    candidate('20261014_1200', block(), 'b')]), /Duplicate report/);
});

test('missing today then available later uses exactly the same query without a negative cache', () => {
  assert.equal(select([]).records.length, 0);
  const files = [candidate('20261014_1200', block(['001'], 'now available'))];
  assert.equal(select(files).records[0].text, 'now available');
});

test('malformed or truncated newest match stops, without falling back or exposing headers', () => {
  for (const malformed of [banner('001') + '\nID: unfinished',
    block(['001'], '', 'OK'), block(['001'], 'partial body', 'OK').trimEnd()]) {
    assert.throws(() => select([candidate('20261013_1200', block()),
      candidate('20261014_1200', malformed)]), /incomplete|header|empty/);
  }
});

test('report limit reports an incomplete search instead of a false not-found', () => {
  const files = Array.from({ length: 41 }, (_, i) => candidate('20261014_1200_' + (i + 2), block(['999'])));
  assert.throws(() => select(files), /limit.*incomplete/);
});

function iterator(values) {
  let i = 0;
  return { hasNext: () => i < values.length, next: () => values[i++] };
}
function fakeFile(name, text, size = Buffer.byteLength(text)) {
  return { getName: () => name, getId: () => 'file-id', getSize: () => size,
    getBlob: () => ({ getDataAsString: encoding => { assert.equal(encoding, 'UTF-8'); return text; } }) };
}
function workbookFile(id) {
  assert.equal(id, '1P-sWhtIlRHcbh4D5rV0p0sv-MF_Th1lc');
  return { getName: () => 'Master Excel file' };
}
function fakeDrive(families) {
  return { getFileById: workbookFile, getFolderById: id => {
    assert.equal(id, '1rnIKpQg83jHh85Qr_TQqJ-ayEs0Q65HJ');
    return { getFolders: () => iterator(families) };
  } };
}
const family = files => ({ getName: () => ' FAMILY ', getFiles: () => iterator(files) });

test('Drive lookup is read-only, family-scoped and discovers newly added reports on each click', () => {
  const files = [];
  const local = context({ DriveApp: fakeDrive([family(files)]) });
  assert.equal(local.lookupTranscription_(query).records.length, 0);
  files.push(fakeFile('Genus_species_transcriptions_20261014_1200.txt', block()));
  assert.equal(local.lookupTranscription_(query).records.length, 1);
  files.push(fakeFile('Genus_species_transcriptions_20261015_1200.txt', block(['001'], 'updated')));
  assert.equal(local.lookupTranscription_(query).records[0].text, 'updated');
});

test('folder ambiguity, inaccessible folders and oversized reports are explicit errors', () => {
  assert.throws(() => context({ DriveApp: fakeDrive([]) }).lookupTranscription_(query), /not found or is not accessible/);
  assert.throws(() => context({ DriveApp: fakeDrive([family([]), family([])]) }).lookupTranscription_(query), /More than one/);
  const huge = fakeFile('Genus_species_transcriptions_20261014_1200.txt', block(), 11 * 1024 * 1024);
  assert.throws(() => context({ DriveApp: fakeDrive([family([huge])]) }).lookupTranscription_(query), /size limit/);
});

test('file listing and elapsed-time limits report incomplete searches', () => {
  const file = fakeFile('irrelevant.txt', '');
  const limited = code.replace('MAX_FILES_LISTED: 5000', 'MAX_FILES_LISTED: 1');
  assert.throws(() => context({ DriveApp: fakeDrive([family([file, file])]) }, limited).lookupTranscription_(query), /listing limit/);
  let tick = 0;
  const date = { now: () => (tick++ ? 50000 : 0) };
  assert.throws(() => context({ Date: date, DriveApp: fakeDrive([family([])]) }).lookupTranscription_(query), /time limit/);
});

test('replays tracked saved responses including shared cards without header leakage', () => {
  // Remove the mixed-test-only closing line; preserve the saved card blocks and usage footer.
  const report = fs.readFileSync(path.join(__dirname, '../../tests/outputs/test_20260923_1755_g3.5-f-l_t1.0.txt'), 'utf8')
    .replace(/^(?:TEST FINISHED|TEST STOPPED):[^\r\n]*\r?\n/gm, '');
  const numbers = [...report.matchAll(/^={22}CM(\d+)=/gm)].map(match => match[1]);
  assert.ok(numbers.length >= 11);
  for (const number of numbers) {
    const records = ctx.parseReport_(report, number);
    assert.equal(records.length, 1);
    assert.ok(records[0].text.includes('TRANSCRIPTION NOTES'));
    assert.doesNotMatch(records[0].text, /^(?:BUILD|PROMPT SHA256|INPUT SHA256|SETTINGS|MODEL VERSION|TOKENS):/m);
  }
});

test('template uses escaped printing for source text and URLs; it contains no forced-print scripts', () => {
  const template = fs.readFileSync(path.join(__dirname, 'Viewer.html'), 'utf8');
  assert.ok(template.includes('<?= record.text ?>'));
  assert.ok(template.includes('<?= result.sourceUrl ?>'));
  assert.doesNotMatch(template, /<\?![=]?/);
  assert.doesNotMatch(template, /innerHTML|localStorage|sessionStorage/);
  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, 'appsscript.json'), 'utf8').replace(/^\ufeff/, ''));
  assert.deepEqual(manifest.oauthScopes, ['https://www.googleapis.com/auth/drive.readonly']);
});


test('E-number-only and partial-route queries normalize without inventing missing values', () => {
  const q = ctx.normalizeQuery_({ e: 'E001' });
  assert.equal(q.family, '');
  assert.equal(q.species, '');
  assert.equal(ctx.normalizeQuery_({ e: '001', family: 'Family' }).species, '');
  assert.throws(() => ctx.normalizeQuery_({ e: '001', species: 'Genus' }), /scientific name/);
});

const catalogueHeader = ['catalogNumber', 'Family', 'Scientific Name'];
const catalogueRows = [catalogueHeader, ['E001', 'Family', 'Genus species']];

test('catalogue routing matches complete numbers and reordered trimmed headers', () => {
  const rows = [[' Scientific Name ', 'catalogNumber', 'Family'],
    ['Other species', 'E0010', 'Other'], ['Other species', 'E1', 'Other'],
    ['GENUS species subspecies', 'e001', 'Family']];
  const route = ctx.routeFromCatalogue_(ctx.normalizeQuery_({ e: '001' }), rows);
  assert.equal(route.e, 'E001');
  assert.equal(route.family, 'Family');
  assert.equal(route.species, 'Genus_species');
});

test('duplicate catalogue rows with the same route are retained as one lookup location', () => {
  const route = ctx.routeFromCatalogue_(ctx.normalizeQuery_({ e: 'E001' }),
    [...catalogueRows, ['001', 'FAMILY', 'Genus_species']]);
  assert.equal(route.species, 'Genus_species');
});

test('conflicting, missing and invalid catalogue routes fail explicitly', () => {
  const q = ctx.normalizeQuery_({ e: 'E001' });
  for (const extra of [['E001', 'Other', 'Genus species'], ['E001', 'Family', 'Other species']]) {
    assert.throws(() => ctx.routeFromCatalogue_(q, [...catalogueRows, extra]), /conflicting/);
  }
  assert.throws(() => ctx.routeFromCatalogue_(q, [catalogueHeader]), /not found in the master catalogue/);
  assert.throws(() => ctx.routeFromCatalogue_(q, [catalogueHeader, ['E001', '', 'Genus species']]), /missing the family/);
  assert.throws(() => ctx.routeFromCatalogue_(q, [catalogueHeader, ['E001', 'Family', 'Genus']]), /invalid family or scientific name/);
  assert.throws(() => ctx.routeFromCatalogue_(q, [['catalogNumber', 'Family']]), /one column each/);
  assert.throws(() => ctx.routeFromCatalogue_(q, [[...catalogueHeader, 'Family']]), /one column each/);
});

test('partial hints must agree with the catalogue', () => {
  assert.equal(ctx.routeFromCatalogue_(ctx.normalizeQuery_({ e: '001', family: 'family' }), catalogueRows).species, 'Genus_species');
  assert.throws(() => ctx.routeFromCatalogue_(ctx.normalizeQuery_({ e: '001', family: 'Other' }), catalogueRows), /does not match/);
  assert.throws(() => ctx.routeFromCatalogue_(ctx.normalizeQuery_({ e: '001', species: 'Other species' }), catalogueRows), /does not match/);
});

// Apps Script's ZIP/XML services are adapted with Python's standard library.
// These tests parse real XLSX ZIP bytes and XML; they never contact Google.
const { spawnSync } = require('node:child_process');
function pythonJson(script, payload) {
  const run = spawnSync('python', ['-X', 'utf8', '-c', script], {
    input: JSON.stringify(payload), encoding: 'utf8', maxBuffer: 16 * 1024 * 1024
  });
  if (run.error) throw run.error;
  if (run.status) throw new Error(run.stderr.trim());
  return JSON.parse(run.stdout);
}
const xmlCache = new Map();
function xmlElement(node) {
  const children = node.children.map(xmlElement);
  const attribute = (key, value) => ({ getName: () => key.replace(/^.*\}/, ''), getValue: () => value });
  return {
    getName: () => node.name, getNamespace: () => node.ns,
    getText: () => node.text,
    getChildren: (name, ns) => children.filter(child => !name || child.getName() === name && child.getNamespace() === ns),
    getChild: (name, ns) => children.find(child => child.getName() === name && child.getNamespace() === ns) || null,
    getAttribute: name => Object.hasOwn(node.attributes, name) ? attribute(name, node.attributes[name]) : null,
    getAttributes: () => Object.entries(node.attributes).map(([key, value]) => attribute(key, value))
  };
}
const XmlService = { parse(text) {
  if (!xmlCache.has(text)) xmlCache.set(text, pythonJson(String.raw`
import json, sys, xml.etree.ElementTree as ET
def node(element):
    tag = element.tag
    return dict(name=tag.split("}")[-1], ns=tag[1:].split("}")[0] if tag.startswith("{") else "",
                attributes=element.attrib, text=(element.text or "") + "".join(c.tail or "" for c in element),
                children=[node(child) for child in element])
print(json.dumps(node(ET.fromstring(json.load(sys.stdin)))))
`, text));
  return { getRootElement: () => xmlElement(xmlCache.get(text)) };
} };
function blob(bytes, name = '') {
  return { getName: () => name, getBytes: () => [...bytes], getDataAsString: () => bytes.toString('utf8'),
    setContentType(type) { assert.equal(type, 'application/zip'); return this; } };
}
const zipCache = new Map();
const workbookUtilities = { unzip(source) {
  const base64 = Buffer.from(source.getBytes()).toString('base64');
  if (!zipCache.has(base64)) zipCache.set(base64, pythonJson(String.raw`
import base64, io, json, sys, zipfile
with zipfile.ZipFile(io.BytesIO(base64.b64decode(json.load(sys.stdin)))) as z:
    print(json.dumps([[i.filename, base64.b64encode(z.read(i)).decode()] for i in z.infolist()]))
`, base64));
  return zipCache.get(base64).map(([name, bytes]) => blob(Buffer.from(bytes, 'base64'), name));
} };
const xlsxNS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main';
const relNS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships';
const escapeXml = text => String(text).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const inlineCell = (address, text) => '<c r="' + address + '" t="inlineStr"><is><t>' + escapeXml(text) + '</t></is></c>';
function xlsxParts(rows = catalogueRows) {
  const columns = ['N', 'C', 'G'];
  return {
    'xl/workbook.xml': '<workbook xmlns="' + xlsxNS + '" xmlns:r="' + relNS + '"><sheets>' +
      '<sheet name="Other tab" sheetId="1" r:id="rId1"/><sheet name="Full List" sheetId="8" r:id="rId8"/></sheets></workbook>',
    'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
      '<Relationship Id="rId1" Type="' + relNS + '/worksheet" Target="worksheets/sheet1.xml"/>' +
      '<Relationship Id="rId8" Type="' + relNS + '/worksheet" Target="/xl/worksheets/sheet8.xml"/>' +
      '</Relationships>',
    'xl/worksheets/sheet1.xml': 'This unrelated worksheet must not be parsed',
    'xl/worksheets/sheet8.xml': '<worksheet xmlns="' + xlsxNS + '"><sheetData>' + rows.map((row, i) =>
      '<row r="' + (i + 1) + '">' + row.map((value, j) => inlineCell(columns[j] + (i + 1), value)).join('') + '</row>'
    ).join('') + '</sheetData></worksheet>'
  };
}
function zipParts(parts) {
  return Buffer.from(pythonJson(String.raw`
import base64, io, json, sys, zipfile
out = io.BytesIO()
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for name, text in json.load(sys.stdin).items(): z.writestr(name, text)
print(json.dumps(base64.b64encode(out.getvalue()).decode()))
`, parts), 'base64');
}
function xlsxFile(parts = xlsxParts()) {
  const bytes = zipParts(parts);
  return { getName: () => 'Master.xlsx', getMimeType: () => 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    getSize: () => bytes.length, getBlob: () => blob(bytes) };
}
function catalogueDrive(workbook, reportFiles = []) {
  return { getFileById: id => {
    assert.equal(id, '1P-sWhtIlRHcbh4D5rV0p0sv-MF_Th1lc');
    return workbook;
  }, getFolderById: () => ({ getFolders: () => iterator([family(reportFiles)]) }) };
}
function workbookContext(workbook = xlsxFile(), reports = [], source = code, extra = {}) {
  return context({ DriveApp: catalogueDrive(workbook, reports), XmlService, Utilities: workbookUtilities, ...extra }, source);
}
const readWorkbook = (parts, e = 'E001', source = code) => {
  const local = workbookContext(xlsxFile(parts), [], source);
  return local.readCatalogue_(local.normalizeQuery_({ e }), () => {});
};

test('E-number-only lookup reads the master XLSX and only the routed species reports', () => {
  let reads = 0;
  const workbook = xlsxFile(), getBlob = workbook.getBlob;
  workbook.getBlob = () => { reads++; return getBlob(); };
  const reports = [fakeFile('Genus_species_transcriptions_20261014_1200.txt', block()),
    { getName: () => 'Other_species_transcriptions_20261015_1200.txt',
      getBlob: () => { throw new Error('Unrelated report read'); } }];
  const local = workbookContext(workbook, reports);
  const result = local.lookupTranscription_({ e: 'E001', workbook: 'untrusted-other-id' });
  assert.equal(result.query.family, 'Family');
  assert.equal(result.query.species, 'Genus_species');
  assert.equal(result.records[0].numbers.join(), 'E001');
  assert.equal(reads, 1);
  local.lookupTranscription_(query);
  assert.equal(reads, 1, 'Existing full links bypass catalogue content but doGet still checks workbook access');
});

test('E-number-only search works before reports exist and rereads saved workbook changes', () => {
  let workbook = xlsxFile(), reads = 0;
  const current = { getName: () => workbook.getName(), getMimeType: () => workbook.getMimeType(),
    getSize: () => workbook.getSize(), getBlob: () => { reads++; return workbook.getBlob(); } };
  const local = workbookContext(current);
  assert.equal(local.lookupTranscription_({ e: 'E001' }).records.length, 0);
  assert.throws(() => local.lookupTranscription_({ e: 'E002' }), /not found in the master catalogue/);
  workbook = xlsxFile(xlsxParts([...catalogueRows, ['E002', 'Family', 'Genus species']]));
  assert.equal(local.lookupTranscription_({ e: 'E002' }).records.length, 0);
  assert.equal(reads, 3);
});

test('wrong file type, oversized workbooks and corrupt ZIP/XML fail without CSV fallback', () => {
  const workbook = xlsxFile();
  for (const mime of ['text/csv', 'application/vnd.google-apps.spreadsheet', 'application/vnd.google-apps.shortcut']) {
    assert.throws(() => workbookContext({ ...workbook, getMimeType: () => mime }).lookupTranscription_({ e: 'E001' }), /master Excel/);
  }
  assert.throws(() => workbookContext({ ...workbook, getSize: () => 26 * 1024 * 1024 })
    .lookupTranscription_({ e: 'E001' }), /workbook exceeds/);
  assert.throws(() => workbookContext({ ...workbook, getBlob: () => blob(Buffer.from('not a zip')) })
    .lookupTranscription_({ e: 'E001' }), /could not be read/);
  for (const patch of [{ 'xl/workbook.xml': '<broken' }, { 'xl/workbook.xml': '<!DOCTYPE workbook><workbook/>' },
    { 'xl/_rels/workbook.xml.rels': '<Relationships/>' }]) {
    assert.throws(() => readWorkbook({ ...xlsxParts(), ...patch }), /could not be read/);
  }
});

test('catalogue tab is selected by name and workbook relationship rather than gid or sheet order', () => {
  const parts = xlsxParts();
  assert.equal(readWorkbook(parts)[1].join('|'), 'E001|Family|Genus species');
  const relative = { ...parts, 'xl/_rels/workbook.xml.rels':
    parts['xl/_rels/workbook.xml.rels'].replace('/xl/worksheets/sheet8.xml', './worksheets/sheet8.xml') };
  assert.equal(readWorkbook(relative)[1][0], 'E001');
  assert.throws(() => readWorkbook(parts, 'E001', code.replace("CATALOGUE_SHEET_NAME: 'Full List'", "CATALOGUE_SHEET_NAME: 'Missing'")),
    /one catalogue tab named "Missing"/);
  const external = { ...parts, 'xl/_rels/workbook.xml.rels':
    parts['xl/_rels/workbook.xml.rels'].replace('Target="/xl/worksheets/sheet8.xml"', 'TargetMode="External" Target="https://example.com/remote"') };
  assert.throws(() => readWorkbook(external), /could not be read/);
});

test('XLSX shared strings, rich text, Unicode and sparse reordered columns preserve exact numbers', () => {
  const parts = xlsxParts();
  parts['xl/_rels/workbook.xml.rels'] = parts['xl/_rels/workbook.xml.rels'].replace('</Relationships>',
    '<Relationship Id="rIdShared" Type="' + relNS + '/sharedStrings" Target="sharedStrings.xml"/></Relationships>');
  parts['xl/sharedStrings.xml'] = '<sst xmlns="' + xlsxNS + '"><si><t>E001</t></si>' +
    '<si><r><t>Fam</t></r><r><t>ily</t></r><rPh><t>ignored phonetic guide</t></rPh></si></sst>';
  parts['xl/worksheets/sheet8.xml'] = parts['xl/worksheets/sheet8.xml'].replace(inlineCell('N2', 'E001'), '<c r="N2" t="s"><v>0</v></c>')
    .replace(inlineCell('C2', 'Family'), '<c r="C2" t="s"><v>1</v></c>')
    .replace(inlineCell('G2', 'Genus species'), inlineCell('G2', 'Génus spéciès'))
    .replace('</sheetData>', '<row r="99">' + inlineCell('N99', 'E1') + inlineCell('C99', 'Other') + inlineCell('G99', 'Other species') + '</row></sheetData>');
  assert.equal(readWorkbook(parts)[1].join('|'), 'E001|Family|Génus spéciès');
  const bad = { ...parts, 'xl/worksheets/sheet8.xml': parts['xl/worksheets/sheet8.xml'].replace('<v>0</v>', '<v>999</v>') };
  assert.throws(() => readWorkbook(bad), /could not be read/);
});

test('numeric catalogue cells respect simple leading-zero formats and never guess unsupported formats', () => {
  for (const format of ['000', '&quot;E&quot;000', '\\E000']) {
    const parts = xlsxParts();
    parts['xl/_rels/workbook.xml.rels'] = parts['xl/_rels/workbook.xml.rels'].replace('</Relationships>',
      '<Relationship Id="rIdStyles" Type="' + relNS + '/styles" Target="styles.xml"/></Relationships>');
    parts['xl/styles.xml'] = '<styleSheet xmlns="' + xlsxNS + '"><numFmts><numFmt numFmtId="164" formatCode="' +
      format + '"/></numFmts><cellXfs><xf numFmtId="0"/><xf numFmtId="164"/></cellXfs></styleSheet>';
    parts['xl/worksheets/sheet8.xml'] = parts['xl/worksheets/sheet8.xml'].replace(inlineCell('N2', 'E001'), '<c r="N2" s="1"><v>1</v></c>');
    assert.equal(ctx.routeFromCatalogue_(query, readWorkbook(parts)).e, 'E001');
    const bad = { ...parts, 'xl/styles.xml': parts['xl/styles.xml'].replace(format, '#,##0') };
    assert.throws(() => readWorkbook(bad), /unsupported number format/);
  }
  const parts = xlsxParts();
  parts['xl/worksheets/sheet8.xml'] = parts['xl/worksheets/sheet8.xml'].replace(inlineCell('N2', 'E001'), '<c r="N2"><v>1</v></c>');
  assert.equal(readWorkbook(parts).length, 1, 'Unformatted 1 must not match E001');
  assert.equal(readWorkbook(parts, 'E1')[1][0], '1');
});

test('XLSX lookup reads saved formula results and fails explicitly on missing results or cell errors', () => {
  const parts = xlsxParts();
  parts['xl/worksheets/sheet8.xml'] = parts['xl/worksheets/sheet8.xml'].replace(inlineCell('N2', 'E001'),
    '<c r="N2" t="str"><f>CONCAT("E","001")</f><v>E001</v></c>');
  assert.equal(readWorkbook(parts)[1][0], 'E001');
  const empty = { ...parts, 'xl/worksheets/sheet8.xml': parts['xl/worksheets/sheet8.xml'].replace('<v>E001</v>', '') };
  assert.throws(() => readWorkbook(empty), /formula has no saved result/);
  const error = { ...parts, 'xl/worksheets/sheet8.xml': parts['xl/worksheets/sheet8.xml'].replace('t="str"', 't="e"').replace('<v>E001</v>', '<v>#VALUE!</v>') };
  assert.throws(() => readWorkbook(error), /error or unsupported value/);
});

test('workbook header errors, conflicting routes and missing family/species remain explicit', () => {
  const missing = xlsxParts();
  missing['xl/worksheets/sheet8.xml'] = missing['xl/worksheets/sheet8.xml'].replace('Scientific Name', 'wrong header');
  assert.throws(() => readWorkbook(missing), /one column each/);
  const duplicated = xlsxParts();
  duplicated['xl/worksheets/sheet8.xml'] = duplicated['xl/worksheets/sheet8.xml'].replace('</row>', inlineCell('Z1', 'Family') + '</row>');
  assert.throws(() => readWorkbook(duplicated), /one column each/);
  for (const extra of [['E001', 'Other', 'Other species'], ['E001', '', 'Genus species']]) {
    const local = workbookContext(xlsxFile(xlsxParts([...catalogueRows, extra])));
    assert.throws(() => local.lookupTranscription_({ e: 'E001' }), /conflicting|missing the family/);
  }
  assert.equal(workbookContext(xlsxFile(xlsxParts([...catalogueRows, catalogueRows[1]])))
    .lookupTranscription_({ e: 'E001' }).query.species, 'Genus_species');
});

test('expanded workbook and elapsed-time limits produce incomplete-search errors', () => {
  const local = workbookContext(xlsxFile(), [], code.replace('MAX_CATALOGUE_XML_BYTES: 80 * 1024 * 1024', 'MAX_CATALOGUE_XML_BYTES: 10'));
  assert.throws(() => local.lookupTranscription_({ e: 'E001' }), /expanded workbook data exceeds/);
  let checks = 0;
  assert.throws(() => workbookContext().readCatalogue_(query, () => {
    if (++checks === 5) throw ctx.viewerError_('Search time limit reached');
  }), /Search time limit/);
});



test('blank styled rows are skipped and unrelated cell errors do not block a matching catalogue row', () => {
  const parts = xlsxParts([...catalogueRows, ['E002', 'Other family', 'Other species']]);
  const sheet = parts['xl/worksheets/sheet8.xml'];
  parts['xl/worksheets/sheet8.xml'] = sheet
    .replace(inlineCell('G3', 'Other species'), '<c r="G3" t="e"><v>#VALUE!</v></c>')
    .replace(inlineCell('G2', 'Genus species'), inlineCell('G2', 'Genus species') + '<c r="X2" t="e"><v>#N/A</v></c>')
    .replace(/\br="([A-Z]*)(\d+)"/g, (_, column, row) => 'r="' + column + (Number(row) + 4) + '"')
    .replace('<sheetData>', '<sheetData><row r="1"><c r="A1" s="7"/></row><row r="2">' + inlineCell('A2', ' ') + '</row>');
  assert.equal(readWorkbook(parts)[1].join('|'), 'E001|Family|Genus species');
  assert.throws(() => readWorkbook(parts, 'E002'), /error or unsupported value/);
});

test('form submits only E-number so a new search cannot inherit stale family or species', () => {
  const template = fs.readFileSync(path.join(__dirname, 'Viewer.html'), 'utf8');
  assert.match(template.replace(/<\?[\s\S]*?\?>/g, ""), /name="e"[^>]*required/);
  assert.doesNotMatch(template, /name="(?:family|species)"/);
  assert.ok(template.includes('<?= result.query.family ?>'));
});

test('doGet resolves an E-number-only request and passes the resolved location to the view', () => {
  let template;
  const reports = [fakeFile('Genus_species_transcriptions_20261014_1200.txt', block())];
  const local = context({
    DriveApp: catalogueDrive(xlsxFile(), reports),
    Utilities: workbookUtilities, XmlService,
    ScriptApp: { getService: () => ({ getUrl: () => 'https://script.google.com/example/exec' }) },
    HtmlService: { createTemplateFromFile: name => {
      assert.equal(name, 'Viewer');
      template = { evaluate: () => ({ setTitle() { return this; }, addMetaTag() { return this; } }) };
      return template;
    } }
  });
  local.doGet({ parameter: { e: 'E001' } });
  assert.equal(template.query.e, 'E001');
  assert.equal(template.result.query.species, 'Genus_species');
  assert.equal(template.result.records.length, 1);
});


test('notes alone do not show a review warning, while the notes text remains intact', () => {
  const body = 'Collector: A\nTRANSCRIPTION NOTES:\nGerman text translated into English in parentheses.';
  for (const reason of ['Notes present', 'Notes present.', 'Transcription notes are present.', 'notes present']) {
    const report = block(['001'], body).replace('REVIEW: 1 bracketed passage(s)', 'REVIEW: ' + reason);
    const record = ctx.parseReport_(report, '001')[0];
    assert.equal(record.status, 'REVIEW', 'Original report status remains available');
    assert.equal(record.needsReview, false);
    assert.equal(record.review, '');
    assert.equal(record.text, body);
  }
});

test('other review reasons remain visible when combined with the notes flag', () => {
  for (const reasons of [
    'Notes present    |    2 bracketed passage(s)',
    'Missing side. | Transcription notes are present. | Unexpected section.',
    'Notes present | Notes present | 1 bracketed passage(s)'
  ]) {
    const record = ctx.parseReport_(block().replace('REVIEW: 1 bracketed passage(s)', 'REVIEW: ' + reasons), '001')[0];
    assert.equal(record.needsReview, true);
    assert.doesNotMatch(record.review, /Notes present|Transcription notes are present/i);
    assert.match(record.review, /bracketed|Missing side/);
  }
});

test('unexplained review statuses and failure states are not cleared by the display policy', () => {
  const unexplained = ctx.parseReport_(block().replace('REVIEW: 1 bracketed passage(s)\n', ''), '001')[0];
  assert.equal(unexplained.needsReview, true);
  for (const status of ['FAILED', 'PAUSED']) {
    const record = ctx.parseReport_(block(['001'], 'retained text', status)
      .replace('REVIEW: 1 bracketed passage(s)', 'REVIEW: Notes present'), '001')[0];
    assert.equal(record.status, status);
    assert.equal(record.text, 'retained text');
  }
});

test('a substantive explanation containing the word notes is preserved as a review reason', () => {
  const reason = 'Notes mention conflicting dates.';
  const record = ctx.parseReport_(block().replace('REVIEW: 1 bracketed passage(s)', 'REVIEW: ' + reason), '001')[0];
  assert.equal(record.needsReview, true);
  assert.equal(record.review, reason);
});


const imageContext = () => context({ Utilities: { base64Encode: bytes => Buffer.from(bytes).toString('base64') } });
function scanFolder(name, children = [], namedFiles = {}) {
  return { getName: () => name, getId: () => 'folder-' + name,
    getFolders: () => iterator(children),
    getFilesByName: name => iterator(namedFiles[name] || []) };
}
function jpgFile(id, bytes = [-1, -40, -1, -32]) {
  let reads = 0;
  return { getId: () => id, getSize: () => bytes.length,
    getBlob: () => ({ getBytes: () => { reads++; return bytes; } }),
    reads: () => reads };
}
function galleryResult(filenames, status = 'REVIEW') {
  const report = block(['001'], 'transcribed text\nTRANSCRIPTION NOTES:\nNone.', status)
    .replace('FILES: source.jpg', 'FILES: ' + filenames.join('; '));
  return { query, records: ctx.parseReport_(report, '001') };
}
function directScans(namedFiles) {
  return scanFolder('Family', [scanFolder('Genus_species', [scanFolder('JPEG', [], namedFiles)])]);
}
const scanA = 'Genus_species_E001(A).jpg';
const scanB = 'Genus_species_E001(B).jpg';
const scanC = 'Genus_species_E001(C).jpg';

test('source filenames are taken only from the report header, preserving shared-card order', () => {
  const body = 'FILES: historical source wording\nTRANSCRIPTION NOTES:\nNone.';
  const report = block(['001', '002'], body).replace('FILES: source.jpg', 'FILES: ' + scanA + '; ' + scanB);
  const record = ctx.parseReport_(report, '002')[0];
  assert.equal(record.files.join('|'), scanA + '|' + scanB);
  assert.equal(record.numbers.join('|'), 'E001|E002');
  assert.equal(record.text, body);
});

test('side recognition supports existing letter, numeric, front/back and exchanged conventions', () => {
  const sides = { 'Genus_species_E001.jpg': 1, 'E001.jpeg': 1,
    'Genus_species_E001(A).jpg': 1, 'Genus_species_E001(B).jpg': 2,
    'Genus_species_E001(C).jpg': 3, 'Genus_species_E001(FRONT).jpg': 1,
    'Genus_species_E001(BACK).jpg': 2, 'Genus_species_E001(1).jpg': 1,
    'Genus_species_E001_2.jpg': 2, 'Genus_species_E001-B-.jpg': 2,
    'Genus_species_E001_E002(B)_exchanged.JPEG': 2 };
  for (const [name, side] of Object.entries(sides)) assert.equal(ctx.sourceScanSide_(name), side, name);
  assert.equal(ctx.sourceScanSide_('Genus_species_E001(WRONG).jpg'), null);
  assert.equal(ctx.sourceScanSide_('Genus_species_E001(0).jpg'), null);
});

test('gallery displays front, back and additional backs in the report order using private JPEG bytes', () => {
  const files = { [scanA]: [jpgFile('a')], [scanB]: [jpgFile('b')], [scanC]: [jpgFile('c')] };
  const result = galleryResult([scanA, scanB, scanC]);
  imageContext().attachSourceImages_(result, directScans(files), () => {});
  assert.equal(result.records[0].images.map(scan => scan.label).join('|'), 'Front|Back|Back 2');
  assert.equal(result.records[0].images.map(scan => scan.name).join('|'), [scanA, scanB, scanC].join('|'));
  assert.equal(result.records[0].images[0].base64, '/9j/4A==');
  assert.equal(result.records[0].images[1].url, 'https://drive.google.com/file/d/b/view');
  assert.equal(result.records[0].text, 'transcribed text\nTRANSCRIPTION NOTES:\nNone.');
});

test('lone back is never labelled front and supplied gaps do not invent scans', () => {
  const single = galleryResult([scanB]);
  imageContext().attachSourceImages_(single, directScans({ [scanB]: [jpgFile('b')] }), () => {});
  assert.equal(single.records[0].images[0].label, 'Back');
  const gap = galleryResult([scanA, scanC]);
  imageContext().attachSourceImages_(gap, directScans({ [scanA]: [jpgFile('a')], [scanC]: [jpgFile('c')] }), () => {});
  assert.equal(gap.records[0].images.map(scan => scan.label).join('|'), 'Front|Back');
  assert.equal(gap.records[0].images.length, 2);
});

test('genus-nested folders and case-insensitive directory names are supported', () => {
  const family = scanFolder('Family', [scanFolder('gEnUs', [
    scanFolder('GENUS_SPECIES', [scanFolder('jpeg', [], { [scanA]: [jpgFile('a')] })])])]);
  const result = galleryResult([scanA]);
  imageContext().attachSourceImages_(result, family, () => {});
  assert.equal(result.records[0].images[0].base64, '/9j/4A==');
});

test('shared-slip lookup uses the full report filenames and never prefix-matches another E-number', () => {
  const shared = 'Genus_species_E001_E002(A).jpg';
  const result = galleryResult([shared]);
  let requested = '';
  const jpeg = scanFolder('JPEG');
  jpeg.getFilesByName = name => { requested = name; return iterator([jpgFile('shared')]); };
  const family = scanFolder('Family', [scanFolder('Genus_species', [jpeg])]);
  imageContext().attachSourceImages_(result, family, () => {});
  assert.equal(requested, shared);
  assert.equal(result.records[0].images[0].label, 'Front');
});

test('duplicate JPEG layouts and duplicate matching directories leave transcription available', () => {
  const direct = scanFolder('Genus_species', [scanFolder('JPEG')]);
  const nested = scanFolder('Genus', [scanFolder('Genus_species', [scanFolder('jpeg')])]);
  for (const children of [[direct, nested], [direct, scanFolder('GENUS_SPECIES')]]) {
    const result = galleryResult([scanA]);
    imageContext().attachSourceImages_(result, scanFolder('Family', children), () => {});
    assert.match(result.records[0].imageMessage, /More than one/);
    assert.equal(result.records[0].images.length, 0);
    assert.ok(result.records[0].text.startsWith('transcribed text'));
  }
});

test('missing and ambiguous source files are explained without choosing another image', () => {
  const duplicates = [jpgFile('first'), jpgFile('second')];
  const result = galleryResult([scanA, scanB]);
  imageContext().attachSourceImages_(result, directScans({ [scanB]: duplicates }), () => {});
  assert.match(result.records[0].images[0].message, /not found or is not accessible/);
  assert.match(result.records[0].images[1].message, /More than one/);
  assert.equal(result.records[0].images[1].url, '');
  assert.equal(duplicates[0].reads(), 0);
  assert.ok(result.records[0].text);
});

test('catalogue-only blocks do not search for or invent source scans', () => {
  const result = { query, records: ctx.parseReport_(missing('Collector: A'), '001') };
  imageContext().attachSourceImages_(result, { getFolders: () => { throw new Error('Unexpected scan search'); } }, () => {});
  assert.equal(result.records[0].images.length, 0);
  assert.equal(result.records[0].files.length, 0);
  assert.equal(result.records[0].imageMessage, '');
});

test('legacy reports without FILES metadata retain their text and explain absent image references', () => {
  const result = { query, records: ctx.parseReport_(block().replace('FILES: source.jpg\n', ''), '001') };
  imageContext().attachSourceImages_(result, directScans({}), () => {});
  assert.match(result.records[0].imageMessage, /filenames are not listed/);
  assert.ok(result.records[0].text);
});

test('non-JPEG payloads, invalid filenames and image read failures cannot erase the transcript', () => {
  const bad = jpgFile('bad', [60, 104, 116, 109, 108, 62]);
  const failing = { getId: () => 'failed', getSize: () => 4,
    getBlob: () => { throw new Error('Private Drive exception'); } };
  const result = galleryResult([scanA, scanB, '../outside.jpg', 'script.html']);
  imageContext().attachSourceImages_(result, directScans({ [scanA]: [bad], [scanB]: [failing] }), () => {});
  assert.match(result.records[0].images[0].message, /could not be displayed as a JPEG/);
  assert.match(result.records[0].images[1].message, /could not be loaded/);
  assert.match(result.records[0].images[2].message, /not a JPEG filename/);
  assert.match(result.records[0].images[3].message, /not a JPEG filename/);
  assert.doesNotMatch(JSON.stringify(result), /Private Drive exception/);
  assert.ok(result.records[0].text);
});

test('per-image, total-byte and image-count limits retain original scan links', () => {
  const original = jpgFile('large');
  original.getSize = () => 13 * 1024 * 1024;
  const single = galleryResult([scanA]);
  imageContext().attachSourceImages_(single, directScans({ [scanA]: [original] }), () => {});
  assert.match(single.records[0].images[0].message, /too large/);
  assert.ok(single.records[0].images[0].url);
  assert.equal(original.reads(), 0);
  const source = code.replace('MAX_TOTAL_IMAGE_BYTES: 24 * 1024 * 1024', 'MAX_TOTAL_IMAGE_BYTES: 4');
  const limited = context({ Utilities: { base64Encode: bytes => Buffer.from(bytes).toString('base64') } }, source);
  const pair = galleryResult([scanA, scanB]);
  limited.attachSourceImages_(pair, directScans({ [scanA]: [jpgFile('a')], [scanB]: [jpgFile('b')] }), () => {});
  assert.ok(pair.records[0].images[0].base64);
  assert.match(pair.records[0].images[1].message, /display limit/);
  assert.ok(pair.records[0].images[1].url);
  const countLimited = context({ Utilities: { base64Encode: bytes => Buffer.from(bytes).toString('base64') } },
    code.replace('MAX_IMAGES: 40', 'MAX_IMAGES: 1'));
  const countPair = galleryResult([scanA, scanB]);
  countLimited.attachSourceImages_(countPair, directScans({ [scanA]: [jpgFile('a')], [scanB]: [jpgFile('b')] }), () => {});
  assert.match(countPair.records[0].images[1].message, /display limit/);
});

test('image timeout is nonfatal and does not cause fallback to an older report', () => {
  const result = galleryResult([scanA]);
  imageContext().attachSourceImages_(result, directScans({ [scanA]: [jpgFile('a')] }),
    () => { throw new Error('time limit'); });
  assert.match(result.records[0].imageMessage, /could not be loaded/);
  assert.equal(result.records[0].text, 'transcribed text\nTRANSCRIPTION NOTES:\nNone.');
});

test('lookup integrates images from the selected report only, without changing its status', () => {
  const reports = [fakeFile('Genus_species_transcriptions_20261014_1200.txt',
    block(['001'], 'newest text', 'OK').replace('FILES: source.jpg', 'FILES: ' + scanA))];
  const family = directScans({ [scanA]: [jpgFile('a')] });
  family.getFiles = () => iterator(reports);
  const local = context({ DriveApp: fakeDrive([family]),
    Utilities: { base64Encode: bytes => Buffer.from(bytes).toString('base64') } });
  const result = local.lookupTranscription_(query);
  assert.equal(result.records[0].text, 'newest text');
  assert.equal(result.records[0].status, 'OK');
  assert.equal(result.records[0].images[0].base64, '/9j/4A==');
});


function requestRenderer(drive, source = code) {
  let page;
  const local = context({
    DriveApp: drive,
    ScriptApp: { getService: () => ({ getUrl: () => 'https://script.google.com/example/exec' }) },
    HtmlService: { createTemplateFromFile: () => {
      page = { evaluate: () => ({ setTitle() { return this; }, addMetaTag() { return this; } }) };
      return page;
    } }
  }, source);
  return params => { local.doGet({ parameter: params }); return page; };
}

test('viewer checks the master workbook before returning a record', () => {
  const calls = [];
  const reports = [fakeFile('Genus_species_transcriptions_20261014_1200.txt', block())];
  const drive = fakeDrive([family(reports)]);
  drive.getFileById = id => {
    calls.push('workbook');
    assert.equal(id, '1P-sWhtIlRHcbh4D5rV0p0sv-MF_Th1lc');
    return { getName: () => 'Shared master Excel file' };
  };
  const rootRead = drive.getFolderById;
  drive.getFolderById = id => { calls.push('reports'); return rootRead(id); };
  const page = requestRenderer(drive)(query);
  assert.equal(calls.join('|'), 'workbook|reports');
  assert.equal(page.result.records.length, 1);
});

test('readers without workbook access receive no report or scan data', () => {
  let roots = 0;
  const drive = {
    getFileById: () => ({ getName: () => { throw new Error('Private authorization details'); } }),
    getFolderById: () => { roots++; throw new Error('Should not read reports'); }
  };
  const page = requestRenderer(drive)({ ...query, workbook: 'another-file', email: 'claimed-member@example.com' });
  assert.match(page.result.error, /access to the master Excel file/);
  assert.doesNotMatch(page.result.error, /Private authorization details/);
  assert.equal(page.result.records, undefined);
  assert.equal(roots, 0);
});

test('workbook access is rechecked on every request, including the empty search form', () => {
  let allowed = true, checks = 0;
  const drive = { getFileById: () => ({ getName: () => {
    checks++;
    if (!allowed) throw new Error('Access revoked');
    return 'Master Excel file';
  } }) };
  const request = requestRenderer(drive);
  assert.equal(request({}).result, null);
  allowed = false;
  assert.match(request({}).result.error, /access to the master Excel file/);
  allowed = true;
  assert.equal(request({}).result, null);
  assert.equal(checks, 3);
});

test('an absent or malformed master workbook configuration cannot disable the access check', () => {
  const source = code.replace("WORKBOOK_FILE_ID: '1P-sWhtIlRHcbh4D5rV0p0sv-MF_Th1lc'",
    "WORKBOOK_FILE_ID: ''");
  const page = requestRenderer({ getFileById: () => { throw new Error('Unexpected Drive lookup'); } }, source)(query);
  assert.match(page.result.error, /master spreadsheet has not been configured/);
  assert.equal(page.result.records, undefined);
});

test('workbook membership does not bypass a readers report-folder permissions', () => {
  const drive = { getFileById: workbookFile, getFolderById: () => { throw new Error('Folder access denied'); } };
  const page = requestRenderer(drive)(query);
  assert.match(page.result.error, /Family folder/);
  assert.equal(page.result.records, undefined);
});

test('deployment accepts signed-in accounts and runs with each readers own read-only permissions', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, 'appsscript.json'), 'utf8').replace(/^\ufeff/, ''));
  assert.deepEqual(manifest.webapp, { access: 'ANYONE', executeAs: 'USER_ACCESSING' });
  assert.deepEqual(manifest.oauthScopes, ['https://www.googleapis.com/auth/drive.readonly']);
});

