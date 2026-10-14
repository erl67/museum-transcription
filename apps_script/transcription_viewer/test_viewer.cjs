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
function fakeDrive(families) {
  return { getFolderById: id => {
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
  assert.throws(() => ctx.routeFromCatalogue_(q, [catalogueHeader]), /not found in the catalogue/);
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

function catalogueDrive(csvFiles, reportFiles) {
  return { getFolderById: () => ({
    getFolders: () => iterator([family(reportFiles)]),
    getParents: () => iterator([{
      getFoldersByName: name => {
        assert.equal(name, 'Transcription');
        return iterator([{
          getFilesByName: filename => {
            assert.equal(filename, 'EggSlipReorganizationProject_FULL.xlsx - Full List.csv');
            return iterator(csvFiles);
          }
        }]);
      }
    }])
  }) };
}

test('E-number-only lookup reads the sibling catalogue and then only the routed species reports', () => {
  let parsed = 0;
  const csv = fakeFile('catalogue.csv', '\ufeffcatalogue content');
  const reports = [fakeFile('Genus_species_transcriptions_20261014_1200.txt', block()),
    { getName: () => 'Other_species_transcriptions_20261015_1200.txt',
      getBlob: () => { throw new Error('Unrelated report read'); } }];
  const local = context({ DriveApp: catalogueDrive([csv], reports),
    Utilities: { parseCsv: text => { assert.equal(text, 'catalogue content'); parsed++; return catalogueRows; } } });
  const result = local.lookupTranscription_({ e: 'E001' });
  assert.equal(result.query.family, 'Family');
  assert.equal(result.query.species, 'Genus_species');
  assert.equal(result.records[0].numbers.join(), 'E001');
  assert.equal(parsed, 1);
  local.lookupTranscription_(query);
  assert.equal(parsed, 1, 'Existing full links bypass catalogue access');
});

test('E-number-only search can succeed before a report exists and rereads the catalogue each time', () => {
  const rows = [...catalogueRows];
  let parses = 0;
  const local = context({ DriveApp: catalogueDrive([fakeFile('csv', 'content')], []),
    Utilities: { parseCsv: () => { parses++; return rows; } } });
  assert.equal(local.lookupTranscription_({ e: 'E001' }).records.length, 0);
  assert.throws(() => local.lookupTranscription_({ e: 'E002' }), /not found in the catalogue/);
  rows.push(['E002', 'Family', 'Genus species']);
  assert.equal(local.lookupTranscription_({ e: 'E002' }).records.length, 0);
  assert.equal(parses, 3);
});

test('missing, ambiguous, oversized and malformed catalogue files do not masquerade as absent transcriptions', () => {
  const q = { e: 'E001' };
  assert.throws(() => context({ DriveApp: catalogueDrive([], []) }).lookupTranscription_(q), /catalogue CSV was not found/);
  const first = fakeFile('csv', 'content');
  const second = { ...first, getId: () => 'other-csv-id' };
  assert.throws(() => context({ DriveApp: catalogueDrive([first, second], []) }).lookupTranscription_(q), /More than one catalogue/);
  const huge = fakeFile('csv', 'content', 11 * 1024 * 1024);
  assert.throws(() => context({ DriveApp: catalogueDrive([huge], []) }).lookupTranscription_(q), /catalogue exceeds/);
  const malformed = context({ DriveApp: catalogueDrive([first], []), Utilities: { parseCsv: () => { throw new Error('bad quotes'); } } });
  assert.throws(() => malformed.lookupTranscription_(q), /export format/);
});

test('explicit catalogue file ID supports nonstandard locations with the same read-only lookup', () => {
  const custom = code.replace("CATALOGUE_FILE_ID: ''", "CATALOGUE_FILE_ID: 'catalogue-id'");
  const drive = fakeDrive([family([])]);
  drive.getFileById = id => { assert.equal(id, 'catalogue-id'); return fakeFile('csv', 'content'); };
  const local = context({ DriveApp: drive, Utilities: { parseCsv: () => catalogueRows } }, custom);
  assert.equal(local.lookupTranscription_({ e: '001' }).query.species, 'Genus_species');
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
    DriveApp: catalogueDrive([fakeFile('csv', 'content')], reports),
    Utilities: { parseCsv: () => catalogueRows },
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

