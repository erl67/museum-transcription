// Offline generator and shipped-catalogue checks. Requires Python's standard library only.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { test } = require('node:test');
const { spawnSync } = require('node:child_process');
const code = fs.readFileSync(path.join(__dirname, 'Code.gs'), 'utf8');
const shipped = fs.readFileSync(path.join(__dirname, 'Catalogue.gs'), 'utf8');
const header = ['catalogNumber', 'Family', 'Scientific Name'];

function generate(csv) {
  const run = spawnSync('python', ['-X', 'utf8', '-c',
    'import sys; from build_catalogue import build_catalogue; print(build_catalogue(sys.stdin.buffer.read()), end="")'],
    { cwd: __dirname, input: csv, encoding: 'utf8', maxBuffer: 2 * 1024 * 1024 });
  if (run.error) throw run.error;
  if (run.status) throw new Error(run.stderr);
  return run.stdout;
}

function load(source) {
  const forbidden = new Proxy({}, { get() { assert.fail('Bundled routing must not call external services'); } });
  const ctx = vm.createContext({ DriveApp: forbidden, CacheService: forbidden, UrlFetchApp: forbidden });
  // Both file orders must work in Apps Script: there are no cross-file initialization calls.
  vm.runInContext(code + '\n' + source, ctx);
  return ctx;
}
const plain = value => JSON.parse(JSON.stringify(value));

test('shipped catalogue has every numbered row, valid routes and consistent browsing/navigation', () => {
  const ctx = load(shipped);
  const rows = ctx.readCatalogue_(() => {});
  assert.equal(rows.length - 1, 10174);
  assert.equal(vm.runInContext('VIEWER_CATALOGUE.locations.length', ctx), 1226);
  const sequence = ctx.navigationSequence_(rows, () => {});
  assert.equal(sequence.length, 10174);
  const byNumber = new Map(sequence.map(route => [route.digits, route]));
  for (const row of rows.slice(1)) {
    const query = ctx.normalizeQuery_({ e: row[0] });
    const route = ctx.routeFromCatalogue_(query, ctx.readCatalogue_(() => {}, query.digits));
    assert.deepEqual(plain(route), plain(byNumber.get(query.digits)));
  }
  const browse = ctx.browseCatalogue_({ view: 'families' }, 'https://example.test');
  assert.equal(browse.families.length, 133);
  assert.ok(Buffer.byteLength(shipped) < 200000);
});

test('generator projects reordered headers, quoted UTF-8 data and duplicate rows without losing zeros', () => {
  const csv = '\uFEFFNotes, Scientific Name ,catalogNumber,Family\r\n' +
    '"historical, note\nsecond line",Génus spéciès,E001,"Family, A"\r\n' +
    'private,Génus spéciès,1,"Family, A"\r\n' +
    'private,Génus spéciès,001,"Family, A"\r\n' +
    'private,Other species,Uncatalogued,Other\r\n';
  const source = generate(csv), ctx = load(source);
  assert.deepEqual(plain(ctx.readCatalogue_(() => {})), [header,
    ['E001', 'Family, A', 'Génus spéciès'], ['E1', 'Family, A', 'Génus spéciès'],
    ['E001', 'Family, A', 'Génus spéciès']]);
  assert.equal(vm.runInContext('VIEWER_CATALOGUE.locations.length', ctx), 1);
  assert.doesNotMatch(source, /private|historical|Uncatalogued/);
  assert.equal(ctx.readCatalogue_(() => {}, '001').length, 3);
  assert.equal(ctx.readCatalogue_(() => {}, '1').length, 2);
  assert.equal(ctx.readCatalogue_(() => {}, '00').length, 1);
});

test('changing scan flags, transcription flags or other unused columns leaves the bundle identical', () => {
  const csv = header.join(',') + ',Scan Link,Transcribed,Notes\nE001,Family,Genus species,none,no,old\n';
  assert.equal(generate(csv), generate(csv.replace('none,no,old', 'scan.jpg,yes,new')));
  assert.equal(generate(csv), generate(csv));
});

test('generator rejects broken exports instead of publishing a partial catalogue', () => {
  for (const csv of ['', 'Family,Scientific Name\nFamily,Genus species',
    'catalogNumber,Family,Scientific Name,Family\nE1,Family,Genus species,Family',
    header.join(',') + '\nE1,Family,Genus species,extra',
    header.join(',') + '\nE1,Family,"unterminated',
    header.join(',') + '\nE1,Family,Genus\u0000species',
    header.join(',') + '\nE1,Family,Genus\uFFFDspecies',
    header.join(',') + '\nUncatalogued,Family,Genus species']) {
    assert.throws(() => generate(csv), /ValueError|_csv.Error/);
  }
  assert.throws(() => generate(Buffer.from([0xff, 0xfe])), /UnicodeDecodeError/);
});

test('compaction retains conflicting and incomplete routes for explicit viewer errors', () => {
  const ctx = load(generate(header.join(',') + '\nE001,Family,Genus species\n' +
    'E001,Other,Genus species\nE2,,Genus species\nE3,Family,Genus\n'));
  assert.equal(ctx.readCatalogue_(() => {}).length, 5);
  for (const [number, error] of [['001', /conflicting/], ['2', /missing the family/], ['3', /invalid family/]]) {
    assert.throws(() => ctx.routeFromCatalogue_(ctx.normalizeQuery_({ e: number }),
      ctx.readCatalogue_(() => {}, number)), error);
  }
});
