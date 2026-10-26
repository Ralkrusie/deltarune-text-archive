'use strict';
const assert = require('node:assert/strict');
const T = require('../../web/text.js');
let checks = 0;
function check(name, test) { test(); checks++; console.log('ok - ' + name); }
check('source text and raw copy remain distinct', () => {
 const raw = '\\E1* 甲\n乙\t/%';
 const v = T.format(raw, 1);
 assert.equal(v.raw, raw);
 assert.equal(v.source, '\\E1* 甲\\n乙\\t/%');
 assert.equal(v.plain, '* 甲\n乙    ');
});
check('escape takes precedence over controls', () => {
 assert.equal(T.format('100`% `& `# `~1 `\\E1', 2).plain, '100% & # ~1 \\E1');
});
check('parameter and image placeholders never disappear', () => {
 const v = T.format('~1 \\O0 \\I2 \\m1', 3);
 assert.equal(v.plain, '〔参数 ~1〕 〔艺术字 0〕 〔图标 2〕 〔行内头像 1〕');
 assert.equal(v.issues.length, 4);
});
check('unknown controls preserve adjacent text', () => {
 const v = T.format('\\U* One baseball!/%', 2);
 assert.equal(v.plain, '\\U* One baseball!');
 assert.equal(v.issues[0].kind, 'unknown-sequence');
 assert.equal(T.format('\\E', 1).plain, '\\E');
});
check('chapter-specific commands cannot silently cross chapters', () => {
 assert.equal(T.format('\\O0', 1).plain, '\\O0');
 assert.equal(T.format('\\O0', 3).plain, '〔艺术字 0〕');
 assert.equal(T.format('\\V1* test', 4).plain, '\\V1* test');
 assert.equal(T.format('\\V1* test', 5).plain, '* test');
});
check('choice, empty, missing and control-only are different', () => {
 assert.equal(T.format('\\C4 ', 1).plain, '〔选择指令 \\C4〕 ');
 assert.equal(T.format('', 1).state, 'empty');
 assert.equal(T.format(null, 1).state, 'missing');
 assert.equal(T.format('\\E1/%', 1).state, 'control-only');
});
check('literal menu punctuation is kept', () => {
 assert.equal(T.format('HP/AT 100%', 2).plain, 'HP/AT 100%');
 assert.equal(T.format('https://example.invalid', 2).plain, 'https://example.invalid');
});
check('tokens cover entire raw text and search handles linebreaks', () => {
 const raw = '`😀\\cR* 甲&乙^1/%';
 const v = T.format(raw, 2);
 assert.equal(v.tokens.map(t => t.raw).join(''), raw);
 assert.equal(T.searchText(raw, 2), '😀* 甲 乙');
 assert.equal(T.format('<script>alert(1)</script>', 2).plain, '<script>alert(1)</script>');
});
check('package decoder preserves null, empty and variants', () => {
 const c = {chapter: 1, languages: ['en', 'ja', 'zh_default'], strings: ['', '甲']};
 assert.deepEqual(T.decodeRow(c, ['key', 0, null, 1]), {chapter: 1, key: 'key', en: '', ja: null, zh_default: '甲'});
});
check('hanging markers preserve offsets, unmarked text and paragraph boundaries', () => {
 const plain = '* First\n  next 😀\n＊ 日本語\n　 続き\n\nYES\n  No marker';
 const lines = T.readingLines(plain);
 assert.equal(lines.map(l => plain.slice(l.start, l.end)).join('\n'), plain);
 assert.deepEqual(lines.map(l => l.hanging), [true,true,true,true,false,false,false]);
 assert.deepEqual(lines.filter(l => l.markerStart !== null).map(l => plain[l.markerStart]), ['*','＊']);
 assert.equal(plain.slice(lines[1].bodyStart, lines[1].end), 'next 😀');
 assert.equal(plain.slice(lines[3].bodyStart, lines[3].end), '続き');
 assert.equal(plain.slice(lines[6].bodyStart, lines[6].end), '  No marker');
 const interior = T.readingLines('A * B')[0];
 assert.equal(interior.hanging, false);
 assert.equal(interior.markerStart, null);
 const noSpace = T.readingLines('*你好\n继续')[1];
 assert.equal(noSpace.bodyStart, noSpace.start);
 assert.equal(noSpace.hanging, true);
});
console.log(`${checks} text display checks passed`);
