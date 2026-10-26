'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs');
const A=require('../web/actions.js'),T=require('../web/text.js');
const ch=JSON.parse(fs.readFileSync('dist/data/ch1.json','utf8'));
const row=T.decodeRow(ch,ch.rows.find(r=>r[0]==='obj_alphysalley_event_slash_Step_0_gml_25_0'));
const state={lang:['en','ja','zh'],zh:'smart',mode:'source'};
const copied=A.copyEntry(row,state);
assert(copied.startsWith(row.key+'\n\nEN: '));assert(copied.includes('\n\nJA: '));
assert(copied.includes('ZH [人名不译·仅译招揽]: '));assert(copied.includes('ZH [人名翻译]: '));
assert(copied.includes('\\n'));assert(!copied.includes('·.')); // Space markers never enter copied text.
assert.equal(A.copyEntry({...row,zh_default:'甲\n  乙'}, {lang:['zh'],zh:'default',mode:'source'}),row.key+'\n\n甲\\n  乙');
assert.equal(A.copyValue('甲\n  乙',1,'plain'),'甲 乙');
assert.equal(A.copyValue(null,1,'source'),'〔缺少此语言文本〕');assert.equal(A.copyValue('',1,'source'),'〔空字符串〕');
assert(A.copyValue('\\I2',1,'plain').includes('图标 2'));
assert.equal(A.sourceURL(1,'gml_Object_DEVICE_CHOICE_Create_0.gml',20),'https://code.deltarune.wiki/ch1/gml_object_device_choice_create_0#L20');
assert.equal(A.sourceURL(1,'../../evil.gml',20),null);
const choice=T.decodeRow(ch,ch.rows.find(r=>r[0]==='DEVICE_CHOICE_slash_Create_0_gml_22_0'));
assert.equal(choice.sources[0].line,20); // key says 22; the actual code location is 20.
console.log('Copy checks passed: key, language/variant selection, visible escapes, plain folds, missing/empty, image placeholders; verified source line differs from key suffix.');
