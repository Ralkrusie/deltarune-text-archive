/* Interface-only localization. Dialogue strings, source and search data stay untouched. */
(function(root){
'use strict';
const languages={'zh-CN':'简体中文','zh-TW':'繁體中文',en:'English',ja:'日本語',ko:'한국어',es:'Español',fr:'Français',de:'Deutsch',pt:'Português',wingdings:'Wingdings'};
const properNames=new Set(['好人汉化组','DELTARUNE','GitHub','JetBrains Mono NL','Wingdings']);
const rows=[
['结构','Structure','結構','構造','구조','Estructura','Structure','Struktur','Estrutura'],
['源码顺序','Source order','原始碼順序','ソース順','소스 순서','Orden del código','Ordre du code','Quelltextreihenfolge','Ordem do código'],
['文件开头','Start of file','檔案開頭','ファイルの先頭','파일 시작','Inicio del archivo','Début du fichier','Dateianfang','Início do arquivo'],
['支持','Support','支持','支援','후원','Apoyar','Soutenir','Unterstützen','Apoiar'],
['关于','About','關於','概要','소개','Acerca de','À propos','Über','Sobre'],
['设置','Settings','設定','設定','설정','Ajustes','Paramètres','Einstellungen','Configurações'],
['台词库','Text Archive','台詞庫','テキスト集','텍스트 아카이브','Archivo de textos','Archives de textes','Textarchiv','Arquivo de textos'],
['游戏','Game','遊戲','ゲーム','게임','Juego','Jeu','Spiel','Jogo'],
['第 1—5 章','Chapters 1–5','第 1—5 章','チャプター1–5','챕터 1–5','Capítulos 1–5','Chapitres 1–5','Kapitel 1–5','Capítulos 1–5'],
['汉化','Chinese patch','漢化','中国語パッチ','중국어 패치','Parche chino','Patch chinois','Chinesischer Patch','Tradução chinesa'],
['好人汉化组','好人汉化组','好人汉化组','好人汉化组','好人汉化组','好人汉化组','好人汉化组','好人汉化组','好人汉化组'],
['GitHub 仓库','GitHub','GitHub 儲存庫','GitHub','GitHub','GitHub','GitHub','GitHub','GitHub'],
['联系作者','Contact','聯絡作者','作者に連絡','제작자 연락','Contacto','Contact','Kontakt','Contato'],
['搜索','Search','搜尋','検索','검색','Buscar','Rechercher','Suchen','Pesquisar'],
['搜索台词或 key','Search text or key','搜尋台詞或 key','テキスト・keyを検索','대사 또는 key 검색','Buscar texto o key','Rechercher un texte ou une clé','Text oder Key suchen','Pesquisar texto ou key'],
['区分大小写','Match case','區分大小寫','大文字と小文字を区別','대소문자 구분','Distinguir mayúsculas','Respecter la casse','Groß-/Kleinschreibung','Diferenciar maiúsculas'],
['整词匹配','Whole words','全字匹配','単語全体','단어 단위','Palabras completas','Mots entiers','Ganze Wörter','Palavras inteiras'],
['高亮匹配','Highlight','醒目標示','強調表示','강조 표시','Resaltar','Surligner','Hervorheben','Destacar'],
['正则表达式','Regex','正規表示式','正規表現','정규 표현식','Expresión regular','Expression régulière','Regulärer Ausdruck','Expressão regular'],
['章节（多选）','Chapters (multiple)','章節（多選）','チャプター（複数可）','챕터 (다중 선택)','Capítulos (varios)','Chapitres (multiples)','Kapitel (Mehrfachauswahl)','Capítulos (múltiplos)'],
['全部','All','全部','すべて','전체','Todos','Tous','Alle','Todos'],
['显示语言','Text languages','顯示語言','表示言語','표시 언어','Idiomas del texto','Langues du texte','Textsprachen','Idiomas do texto'],
['中文人名译法','Chinese character names','中文人名譯法','中国語の人名表記','중국어 이름 표기','Nombres en chino','Noms en chinois','Chinesische Namen','Nomes em chinês'],
['人名不译','Original names','人名不譯','原名','원래 이름','Nombres originales','Noms originaux','Originalnamen','Nomes originais'],
['仅译招揽','Recruits only','僅譯招攬','勧誘キャラのみ','영입 캐릭터만','Solo reclutas','Recrues seulement','Nur Rekruten','Só recrutas'],
['人名翻译','Translated names','人名翻譯','翻訳名','번역된 이름','Nombres traducidos','Noms traduits','Übersetzte Namen','Nomes traduzidos'],
['智能','Smart','智慧','自動','자동','Automático','Automatique','Automatisch','Automático'],
['显示','View','顯示','表示','보기','Vista','Affichage','Ansicht','Visualização'],
['简洁','Plain','簡潔','簡易','간결','Simple','Simple','Einfach','Simples'],
['源码','Source','原始碼','ソース','원문 코드','Fuente','Source','Quelltext','Fonte'],
['还原','Recreation','還原','再現','재현','Recreación','Reconstitution','Nachbildung','Recriação'],
['排列','Layout','排列','配置','배치','Diseño','Disposition','Anordnung','Disposição'],
['横排','Horizontal','橫排','横並び','가로','Horizontal','Horizontal','Horizontal','Horizontal'],
['纵排','Vertical','直排','縦並び','세로','Vertical','Vertical','Vertikal','Vertical'],
['上一页','Previous','上一頁','前へ','이전','Anterior','Précédent','Zurück','Anterior'],
['下一页','Next','下一頁','次へ','다음','Siguiente','Suivant','Weiter','Próxima'],
['跳转','Go','跳轉','移動','이동','Ir','Aller','Los','Ir'],
['查看上下文','Context','查看上下文','前後の文脈','문맥 보기','Contexto','Contexte','Kontext','Contexto'],
['复制 key','Copy key','複製 key','keyをコピー','key 복사','Copiar key','Copier la clé','Key kopieren','Copiar key'],
['复制本条','Copy entry','複製本條','項目をコピー','항목 복사','Copiar entrada','Copier l’entrée','Eintrag kopieren','Copiar entrada'],
['wiki 源码','Wiki source','Wiki 原始碼','Wiki ソース','Wiki 소스','Fuente Wiki','Source Wiki','Wiki-Quelltext','Fonte Wiki'],
['关闭','Close','關閉','閉じる','닫기','Cerrar','Fermer','Schließen','Fechar'],
['灵魂交互','SOUL interaction','靈魂互動','ソウル操作','영혼 조작','Interacción del ALMA','Interaction de l’ÂME','SEELEN-Interaktion','Interação da ALMA'],
['紧凑模式','Compact mode','緊湊模式','コンパクト表示','간결한 배치','Modo compacto','Mode compact','Kompaktmodus','Modo compacto'],
['结构开头','Start of context','結構開頭','文脈の先頭','문맥 시작','Inicio del contexto','Début du contexte','Kontextanfang','Início do contexto'],
['重新加载','Reload','重新載入','再読み込み','다시 불러오기','Recargar','Recharger','Neu laden','Recarregar'],
['取消检索','Cancel search','取消搜尋','検索を中止','검색 취소','Cancelar búsqueda','Annuler la recherche','Suche abbrechen','Cancelar pesquisa'],
['当前台词','Current entry','目前台詞','現在のテキスト','현재 대사','Entrada actual','Entrée actuelle','Aktueller Eintrag','Entrada atual'],
['选择','Choice','選擇','選択','선택','Elección','Choix','Auswahl','Escolha'],
['首次选择','First choice','首次選擇','初回の選択','첫 선택','Primera elección','Premier choix','Erste Auswahl','Primeira escolha'],
['再次选择','Repeated choice','再次選擇','再選択','재선택','Elección repetida','Choix répété','Erneute Auswahl','Escolha repetida'],
['正在加载…','Loading…','載入中…','読み込み中…','불러오는 중…','Cargando…','Chargement…','Laden…','Carregando…'],
['正在加载文本…','Loading text…','正在載入文字…','テキスト読み込み中…','텍스트 불러오는 중…','Cargando texto…','Chargement des textes…','Texte werden geladen…','Carregando textos…'],
['已复制','Copied','已複製','コピーしました','복사됨','Copiado','Copié','Kopiert','Copiado'],
['复制失败','Copy failed','複製失敗','コピー失敗','복사 실패','Error al copiar','Échec de la copie','Kopieren fehlgeschlagen','Falha ao copiar'],
['没有找到这句台词','No matching text','找不到這句台詞','一致するテキストなし','일치하는 대사 없음','No hay coincidencias','Aucun résultat','Keine Treffer','Nenhum resultado'],
['试试更短的词语，或扩大章节范围。','Try fewer words or more chapters.','試試較短的詞語，或擴大章節範圍。','短い語句や別のチャプターで検索してください。','더 짧은 검색어나 다른 챕터를 선택하세요.','Prueba menos palabras o más capítulos.','Essayez moins de mots ou plus de chapitres.','Weniger Wörter oder mehr Kapitel versuchen.','Tente menos palavras ou mais capítulos.'],
['重置检索条件','Reset filters','重設搜尋條件','条件をリセット','검색 조건 초기화','Restablecer filtros','Réinitialiser les filtres','Filter zurücksetzen','Redefinir filtros']
];
const order=['zh-CN','en','zh-TW','ja','ko','es','fr','de','pt'],dict={};
for(const lang of order)dict[lang]={};
for(const row of rows)order.forEach((lang,i)=>dict[lang][row[0]]=row[i]);
const extra={
'跳到台词':'Skip to text','界面语言':'Interface language','项目与作者':'Project and author','检索与显示设置':'Search and display settings','搜索选项':'Search options','章节、语言与显示设置':'Chapters, languages and display','显示模式':'Display mode','语言排列':'Language layout','结果分页':'Result pages','跳转页码':'Go to page','页码':'Page','输入页码，按 Enter 跳转':'Enter a page number and press Enter','台词操作':'Entry actions','关闭上下文':'Close context','关闭关于':'Close About','关闭设置':'Close settings','召回灵魂':'Recall SOUL',
'正在准备台词数据…':'Preparing text data…','数据已就绪，正在检索…':'Data ready. Searching…','正在加载文件…':'Loading file…','加载未完成':'Loading incomplete','检索未完成':'Search incomplete','数据加载未完成':'Data loading incomplete','暂无源码定位':'Source location unavailable','暂无此语言文本':'Text unavailable in this language','空字符串':'Empty string','仅含控制串 · 切换源码查看':'Control codes only · switch to Source',
'至少保留一个章节':'Select at least one chapter.','至少保留一种语言':'Select at least one text language.','复制失败，请选中文本后手动复制':'Copy failed. Select the text and copy it manually.','相同译文只显示一次':'Identical translations are shown once.','只显示所选中文版本':'Only the selected Chinese variant is shown.','保留原文角色名':'Keep original character names','翻译可招揽角色的人名':'Translate recruitable characters’ names','使用人名翻译版本':'Use translated character names','原文相同只显示一次，不同版本分别标注':'Show identical variants once and label differences.','宽度不足时自动纵排，变宽后恢复横排':'Stack on narrow screens; return to columns when space permits.','搜索始终覆盖英文、日文和全部中文译法':'Search always includes English, Japanese and every Chinese variant.',
'正则表达式，如 ^(YES|NO)$':'Regex, e.g. ^(YES|NO)$','以连续的字母、数字、下划线为词；中文和日文不做自动分词':'Words consist of letters, digits and underscores. Chinese and Japanese are not automatically segmented.','直接输入表达式，不加 / 分隔符，例如 ^(YES|NO)$':'Enter a pattern without / delimiters, e.g. ^(YES|NO)$',
'拖动空白处平移 · 滚动条左右移动 · 右下角调整大小':'Drag empty space to pan · scroll horizontally · resize from the bottom-right corner',
'方向键/左键拖拽：移动\nZ：交互/功能\nX/Shift/左键点击：切换颜色\n右键点击：回到顶部':'Arrow keys / drag: move\nZ: interact / ability\nX / Shift / click: change color\nRight-click: back to top',
'DELTARUNE 文本查阅工具 · 非官方项目':'DELTARUNE text archive · unofficial project','中文文本：好人汉化组':'Chinese translation: 好人汉化组','版本待核对':'Version unverified','日期待核对':'Date unverified',
'当前导出中没有已核对的源码位置，不代表游戏中不存在。':'No verified location in this export; this does not mean the text is absent from the game.','按当前语言、模式和中文译法复制：key + 全部可见版本':'Copy the key and all visible variants using the current text settings.',
'文本未能加载，切换模式后可重试。':'Text could not be loaded. Switch modes to retry.','检索已取消，可以修改条件后重新搜索。':'Search cancelled. Change the filters and search again.','检索模块未能启动，请点击重新加载。':'The search module could not start. Please reload.','检索模块未能启动，请重新加载页面后重试。':'The search module could not start. Reload the page and retry.',
'台词数据加载超过 2 分钟，已停止。请检查网络后重新加载，或先选择单个章节。':'Loading stopped after two minutes. Check your connection, reload, or select a single chapter.','正则检索耗时过长，已停止。请简化表达式或缩小章节范围。':'Regex search timed out. Simplify the pattern or select fewer chapters.','检索耗时过长，已停止。请缩小章节范围后重试。':'Search timed out. Select fewer chapters and retry.',
'上下文数据未能加载':'Context data could not be loaded.','上下文与当前文本版本不一致，请重新构建':'Context and text versions do not match. Rebuild the site.','章节文本未能加载':'Chapter text could not be loaded.','上下文文件路径无效':'Invalid context file path.','上下文索引版本不一致':'Context index version mismatch.','上下文文件版本或身份不一致':'Context file identity or version mismatch.','上下文引用的台词缺失':'A referenced context entry is missing.',
'当前章节源码中未找到这条文本的引用，暂时无法定位上下文。':'No reference was found in this chapter’s source, so context is unavailable.','这个文件尚未生成上下文。':'Context has not been generated for this file.','源码文件':'Source file','上下文源码文件':'Context source file','源码引用未收录于当前文本库':'Source reference not included in the current text archive','源码原串与当前文本库不同；正文显示文本库版本':'Source text differs; the archive version is shown.','关闭后可重试；未用源码行序代替缺失上下文。':'Close and retry. Missing context has not been replaced with source-line order.',
'请通过本地预览启动':'Open through the local preview','已有 8800 预览服务？打开页面':'Preview running on port 8800? Open it','你正在直接打开 HTML。请双击项目根目录的 preview.cmd，或运行 python -m tools.site.serve --open。浏览器会通过本机 HTTP 地址加载文本，无需联网。':'You opened the HTML file directly. Run preview.cmd or python -m tools.site.serve --open to load the site through local HTTP. No internet connection is required.'
};
Object.assign(dict.en,extra);
// Frequently updated status labels use the selected language as well.
const statusRows=[
['正在准备台词数据…','Preparing text data…','正在準備台詞資料…','テキストを準備中…','대사 데이터 준비 중…','Preparando textos…','Préparation des textes…','Textdaten werden vorbereitet…','Preparando textos…'],
['数据已就绪，正在检索…','Data ready. Searching…','資料已就緒，正在搜尋…','検索中…','검색 중…','Buscando…','Recherche…','Suche läuft…','Pesquisando…'],
['暂无此语言文本','Text unavailable in this language','暫無此語言文字','この言語のテキストなし','이 언어의 텍스트 없음','Texto no disponible en este idioma','Texte indisponible dans cette langue','Text in dieser Sprache nicht verfügbar','Texto indisponível neste idioma'],
['空字符串','Empty string','空字串','空の文字列','빈 문자열','Cadena vacía','Chaîne vide','Leere Zeichenfolge','Texto vazio'],
['仅含控制串 · 切换源码查看','Control codes only · switch to Source','僅含控制碼 · 切換原始碼查看','制御コードのみ · ソースで表示','제어 코드만 있음 · 원문 코드로 보기','Solo códigos · ver Fuente','Codes seuls · voir Source','Nur Steuercodes · Quelltext ansehen','Só códigos · ver Fonte'],
['界面语言','Interface language','介面語言','表示言語','인터페이스 언어','Idioma de la interfaz','Langue de l’interface','Oberflächensprache','Idioma da interface']
];
for(const row of statusRows)order.forEach((lang,i)=>dict[lang][row[0]]=row[i]);
function normalize(value){if(languages[value])return value;value=String(value||'').toLowerCase();if(value.startsWith('zh'))return /tw|hk|hant/.test(value)?'zh-TW':'zh-CN';return languages[value.split('-')[0]]?value.split('-')[0]:'en';}
let locale='zh-CN';
function translate(text,lang=locale){
 if(properNames.has(text.trim()))return text;
 if(lang==='wingdings')lang='en';
 if(lang==='zh-CN')return text;
 const key=text.trim(),match=dict[lang]?.[key]??dict.en[key];
 if(match!==undefined)return text.replace(key,match);
 // Dynamic UI values only; never run this over dialogue or source nodes.
 const rules=[[/^第 (\d) 章（可多选）$/,'Chapter $1 (multiple selection)'],[/^正在加载台词数据（(\d+)\/(\d+) 章完成）…$/,'Loading text ($1/$2 chapters)…'],[/^命中 ([\d,]+) 条章节记录 · 跨章去重后 ([\d,]+) 组$/,'$1 chapter records · $2 groups across chapters'],[/^源码 (\d+) 处$/,'$1 source locations'],[/^选项 (\d+)$/,'Option $1'],[/^wiki 源码 · L(\d+)$/,'Wiki source · L$1'],[/^文本文件加载失败（HTTP (\d+)）$/,'Text download failed (HTTP $1)']];
 for(const [pattern,value] of rules)if(pattern.test(text))return text.replace(pattern,value);
 if(text==='共 '||text==='找到 ')return ({'zh-TW':'共 ',ja:'検索結果：',ko:'검색 결과: ',es:'Resultados: ',fr:'Résultats : ',de:'Gefunden: ',pt:'Resultados: '})[lang]||'Found ';
 if(text===' 条章节记录')return ({'zh-TW':' 條章節記錄',ja:' 件',ko:'개 항목',es:' registros',fr:' entrées',de:' Einträge',pt:' registros'})[lang]||' chapter records';
 return text;
}
root.DialogueI18n={translate,normalize,languages};
if(typeof document==='undefined')return;
try{locale=normalize(localStorage.getItem('dialogue-ui-language')||navigator.language);}catch{locale=normalize(navigator.language);}
const select=document.getElementById('ui-language');
for(const [value,label] of Object.entries(languages)){const option=document.createElement('option');option.value=value;option.textContent=label;select.append(option);}select.value=locale;
const about=document.getElementById('about-dialog'),originalAbout=[...about.querySelectorAll(':scope > p')];
const englishAbout=[
'This is an early test version. Features and the UI may change substantially.',
'Browse and compare English, Japanese and Chinese text from DELTARUNE Chapters 1–5.',
'Plain mode is for reading. Source mode preserves control codes such as colors and pauses. Recreation mode is still under development and currently shows a placeholder.',
'Choose multiple chapters, text languages and Chinese name variants. Search covers every language, including languages that are not currently displayed.',
'Identical English text across chapters is grouped. The earliest matching selected chapter supplies the displayed text. A label such as “Ch1-4?” means the text appears in those chapters’ code, not necessarily in normal gameplay. The question mark indicates that reachability is unconfirmed.',
'Context shows nearby dialogue, choices and conditions. This is experimental: branch connections may be incorrect. Check against the game.',
'The archive may contain unused text. Some images, names and values are represented by placeholders. Speaker and portrait information is not yet integrated.',
'Wiki source links are based on the source used by this project. The Wiki may use a different version or line numbering.',
'This is an unofficial project. Game text belongs to its respective rights holders. Chinese translation: 好人汉化组. Source mode uses JetBrains Mono NL; system fonts supply Chinese and Japanese glyphs.'
].map(text=>{const p=document.createElement('p');p.lang='en';p.textContent=text;return p;});
// Keep attribution links available in both versions without duplicating IDs.
for(const link of originalAbout.at(-1).querySelectorAll('a')){const copy=link.cloneNode(true);copy.textContent=translate(copy.textContent,'en');englishAbout.at(-1).append(' ',copy);}
const originals=new WeakMap();
function blocked(node){const p=node.nodeType===3?node.parentElement:node;return !p||p.closest('script,style,code,textarea,#ui-language,#about-dialog > p,.restore-caption,.context-condition')||!!(p.closest('.text')&&!p.closest('.text.missing'));}
function update(node,attr){
 const current=attr?node.getAttribute(attr):node.nodeValue;if(!current)return;
 let record=originals.get(node);if(!record){record={};originals.set(node,record);}
 const key=attr||'text',previous=record[key],source=previous&&current===previous.rendered?previous.source:current;
 const rendered=translate(source);record[key]={source,rendered};
 if(!attr&&source.trim())node.parentElement.classList.toggle('wingdings-ui',locale==='wingdings'&&!properNames.has(source.trim()));
 if(current!==rendered){if(attr)node.setAttribute(attr,rendered);else node.nodeValue=rendered;}
}
function visit(node){
 if(blocked(node))return;
 if(node.nodeType===3){update(node);return;}
 if(node.nodeType!==1)return;
 for(const attr of ['title','aria-label','placeholder'])if(node.hasAttribute(attr))update(node,attr);
 for(const child of node.childNodes)visit(child);
}
function apply(){
 document.documentElement.lang=locale==='wingdings'?'en':locale;document.documentElement.dataset.uiLanguage=locale;document.title='DELTARUNE · '+translate('台词库');
 for(const p of about.querySelectorAll(':scope > p'))p.remove();
 about.append(...(locale.startsWith('zh')?originalAbout:englishAbout));
 // About keeps its English text underneath the Wingdings font; other language options stay legible.
 visit(document.body);
 window.dispatchEvent(new CustomEvent('dialogue-ui-language-change',{detail:{locale}}));
}
const observer=new MutationObserver(records=>{observer.disconnect();for(const r of records){if(r.type==='childList')for(const n of r.addedNodes)visit(n);else visit(r.target);}observe();});
function observe(){observer.observe(document.body,{subtree:true,childList:true,characterData:true,attributes:true,attributeFilter:['title','aria-label','placeholder']});}
select.addEventListener('change',()=>{locale=select.value;try{localStorage.setItem('dialogue-ui-language',locale);}catch{}observer.disconnect();apply();observe();});
apply();observe();
})(typeof window==='undefined'?globalThis:window);
