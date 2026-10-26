'use strict';
// Run from the project root. This checks data loss, not full game rendering accuracy.
const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const crypto = require('node:crypto');
const T = require('../../web/text.js');
const root = path.resolve(__dirname, '../..');
const read = file => JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
const hash = data => crypto.createHash('sha256').update(data).digest('hex');
const out = path.join(root, 'build/display-review');
const manifest = read(path.join(root, 'build/site-data/manifest.json'));
const samples = [
 [1, 'obj_alphysalley_event_slash_Step_0_gml_25_0', 'en', '普通对话：移除表情与暂停指令'],
 [1, 'DEVICE_CONTACT_slash_Step_0_gml_729_0', 'en', '动态参数：保留待填位置'],
 [4, 'obj_dummyenemy_slash_Step_0_gml_558_0', 'zh_default', '新版中文：保留换行和图标占位'],
 [3, 'obj_ch3_BTB06_slash_Step_0_gml_211_0', 'en', '艺术字：没有映射时保留占位'],
 [2, 'obj_ch2_cyber01_slash_Step_0_gml_110_0', 'en', '行内头像：不等于 smallface 消息'],
 [1, 'scr_text_slash_scr_text_gml_1023_0', 'en', '选择指令：不推断选项或分支'],
 [2, 'scr_text_slash_scr_text_gml_6605_0', 'zh_default', 'smallface 正文：可阅读，关联关系未接入'],
 [5, 'obj_castle_tutorial_slash_Step_0_gml_294_0', 'zh_default', '广告正文：不推断发言角色'],
 [2, 'DEVICE_CONTACT_slash_Other_10_gml_1_0', 'en', '缺失翻译：保留 null'],
 [2, 'obj_ch2_city07_slash_Step_0_gml_515_0', 'en', '未知控制：保留原片段与相邻星号'],
 [1, 'obj_checkers_enemy_slash_Step_0_gml_82_0', 'zh_default', '转义百分号与动态参数'],
];
const views = [], stats = [], unknowns = {};
let fieldCount = 0;
const started = performance.now();
for (const chapter of manifest.chapters) {
 const dataPath = path.join(root, 'build/site-data', chapter.path);
 const bytes = fs.readFileSync(dataPath);
 assert.equal(hash(bytes), chapter.sha256);
 const packed = read(dataPath);
 const source = read(path.join(root, 'build/texts', `trilingual_chapter${chapter.chapter}.json`));
 assert.equal(packed.rows.length, source.lines.length);
 const totals = {chapter: chapter.chapter, rows: packed.rows.length, fields: 0, states: {}, issues: {}};
 const cache = new Map();
 for (let index = 0; index < packed.rows.length; index++) {
  const row = T.decodeRow(packed, packed.rows[index]), original = source.lines[index];
  assert.equal(row.key, original.key);
  for (const lang of packed.languages) {
   assert.equal(row[lang], original[lang], `${chapter.chapter}/${row.key}/${lang}`);
   const raw = row[lang];
   if (!cache.has(raw)) cache.set(raw, T.format(raw, chapter.chapter));
   const view = cache.get(raw);
   assert.equal(view.raw, raw);
   if (raw !== null) assert.equal(view.tokens.map(t => t.raw).join(''), raw);
   totals.fields++; fieldCount++;
   totals.states[view.state] = (totals.states[view.state] || 0) + 1;
   for (const issue of view.issues) {
    totals.issues[issue.kind] = (totals.issues[issue.kind] || 0) + 1;
    if (issue.kind === 'unknown-sequence') {
     unknowns[issue.raw] ??= {count: 0, example: {chapter: chapter.chapter, key: row.key, lang, raw}};
     unknowns[issue.raw].count++;
    }
   }
   const picked = samples.find(s => s[0] === chapter.chapter && s[1] === row.key && s[2] === lang);
   if (picked) views.push({chapter: chapter.chapter, key: row.key, language: lang, note: picked[3],
                           raw, source: view.source, plain: view.plain, state: view.state, issues: view.issues});
  }
 }
 stats.push(totals);
}
assert.equal(views.length, samples.length);
const sample = key => views.find(v => v.key === key);
assert(sample('DEVICE_CONTACT_slash_Step_0_gml_729_0').plain.includes('〔参数 ~1〕'));
assert(sample('obj_dummyenemy_slash_Step_0_gml_558_0').plain.includes('\n（〔图标 2〕'));
assert(sample('obj_ch3_BTB06_slash_Step_0_gml_211_0').plain.includes('〔艺术字 0〕'));
assert.equal(sample('scr_text_slash_scr_text_gml_1023_0').plain, '〔选择指令 \\C4〕 ');
assert.equal(sample('DEVICE_CONTACT_slash_Other_10_gml_1_0').state, 'missing');
assert(sample('obj_ch2_city07_slash_Step_0_gml_515_0').plain.includes('\\U*'));
assert.equal(sample('scr_text_slash_scr_text_gml_6605_0').plain, sample('scr_text_slash_scr_text_gml_6605_0').raw);
assert(sample('obj_checkers_enemy_slash_Step_0_gml_82_0').plain.includes('〔参数 ~1〕%'));
const elapsedMs = performance.now() - started;
const result = {schema: 1, totalRows: manifest.total_rows, checkedFields: fieldCount,
 rawRoundtrip: true, tokenCoverage: true, realSampleChecks: views.length,
 elapsedMs: Math.round(elapsedMs), nodeVersion: process.version,
 dataBytes: manifest.chapters.reduce((sum, c) => sum + c.bytes, 0),
 moduleSha256: hash(fs.readFileSync(path.join(root, 'web/text.js'))),
 stats, unknowns, samples: views};
fs.mkdirSync(out, {recursive: true});
fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify(result, null, 2) + '\n', 'utf8');
const escape = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const shown = value => value === null ? '〔缺失翻译〕' : value === '' ? '〔空字符串〕' : value;
let html = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>第 2 步文本验收</title><style>body{font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 20px;color:#17242e;background:#f5f7f8}article{background:white;border:1px solid #ccd4da;border-radius:8px;padding:20px;margin:20px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#eff3f5;padding:12px}code{overflow-wrap:anywhere}h2{font-size:19px}.note{color:#516471}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:700px){.pair{display:block}}</style><h1>第 2 步：源码 → 简洁</h1><p>开发验收页，非新网站布局。占位表示尚未接入素材／参数信息；未知片段保留。源码可视化显示换行转义，底层原文完整保存。</p>';
for (const v of views) {
 html += `<article><h2>${escape(v.note)}</h2><p>第 ${v.chapter} 章 · ${escape(v.language)}<br><code>${escape(v.key)}</code></p><div class="pair"><div>源码模式<pre>${escape(shown(v.source))}</pre></div><div>简洁模式<pre>${escape(shown(v.plain))}</pre></div></div><p class="note">${escape(v.issues.map(i => i.kind + ': ' + i.raw).join('；') || v.state)}</p></article>`;
}
html += '</html>';
fs.writeFileSync(path.join(out, 'index.html'), html, 'utf8');
console.log(JSON.stringify({rows: result.totalRows, fields: fieldCount, realSamples: views.length,
 dataMiB: result.dataBytes / 1024**2, elapsedMs: result.elapsedMs, unknowns}, null, 2));
