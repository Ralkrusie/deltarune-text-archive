const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const scope={};vm.runInNewContext(fs.readFileSync('web/i18n.js','utf8'),scope);
const {translate:t,normalize,languages}=scope.DialogueI18n;
assert.equal(normalize('zh-Hant-HK'),'zh-TW');
assert.equal(normalize('en-US'),'en');assert.equal(normalize('xx'),'en');
for(const lang of Object.keys(languages))assert.ok(t('设置',lang));
assert.equal(t('设置','ja'),'設定');assert.equal(t('关于','en'),'About');
assert.equal(t('共 ','en'),'Found ');
assert.equal(t('正在加载台词数据（2/5 章完成）…','en'),'Loading text (2/5 chapters)…');
assert.equal(t('obj_test_slash_Create_0','en'),'obj_test_slash_Create_0');
assert.equal(t('未知内容','en'),'未知内容');
for(const lang of Object.keys(languages)){
 assert.equal(t('好人汉化组',lang),'好人汉化组');
 assert.equal(t('JetBrains Mono NL',lang),'JetBrains Mono NL');
 assert.equal(t('DELTARUNE',lang),'DELTARUNE');
}
assert.equal(normalize('wingdings'),'wingdings');
assert.equal(t('设置','wingdings'),'Settings');
assert.equal(t('中文文本：好人汉化组','en'),'Chinese translation: 好人汉化组');
console.log('Interface locale normalization, labels, fallback and dynamic counts passed.');
