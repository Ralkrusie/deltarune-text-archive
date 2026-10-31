/* Text-only view model. Chapter writer syntax is evidence for reading, not a claim
   about the consumer of every language-table string. No global runtime state. */
(function (root) {
    'use strict';
    const common = new Set(['E', 'F', 'T', 'f', 'c', 'M', 'S', 's', '*', 'C', 'I']);
    const extra = {1: ['a'], 2: ['m'], 3: ['m', 'O'], 4: ['m', 'O'], 5: ['m', 'O', 'V', 'v']};
    const labels = {O: '艺术字', I: '图标', m: '行内头像'};

    function tokenize(raw, chapter) {
        if (typeof raw !== 'string') throw new TypeError('Expected a string');
        if (!extra[chapter]) throw new RangeError('Expected chapter 1..5');
        const known = new Set([...common, ...extra[chapter]]);
        const tokens = [];
        let i = 0;
        function add(kind, size, value) {
            const source = raw.slice(i, i + size);
            tokens.push({kind, raw: source, start: i, end: i + size, value: value === undefined ? source : value});
            i += size;
        }
        while (i < raw.length) {
            const c = raw[i], next = raw[i + 1];
            if (c === '`' && next !== undefined) {
                const literal = String.fromCodePoint(raw.codePointAt(i + 1));
                add('text', 1 + literal.length, literal); continue;
            }
            if (c === '\\') {
                if (known.has(next) && i + 2 < raw.length) {
                    const cmd = next, arg = raw[i + 2];
                    add(labels[cmd] ? 'image' : cmd === 'C' ? 'choice' : 'control', 3, {cmd, arg});
                } else add('unknown', next === undefined ? 1 : 2);
                continue;
            }
            if (c === '~' && /[0-9]/.test(next || '')) {
                const marker = raw.slice(i).match(/^~[0-9]+/)[0];
                add('parameter', marker.length, marker); continue;
            }
            if (c === '^' && /[0-9]/.test(next || '')) { add('control', 2); continue; }
            // Only remove trailing message terminators. Interior punctuation may be menu text.
            if ((c === '/' || c === '%') && /^[/%]+\s*$/.test(raw.slice(i)) &&
                !(c === '%' && /[0-9]/.test(raw[i - 1] || ''))) {
                const marker = raw.slice(i).match(/^[/%]+/)[0];
                add('control', marker.length); continue;
            }
            if (c === '&' || c === '#' || c === '\n' || c === '\r') {
                add('break', c === '\r' && next === '\n' ? 2 : 1, '\n'); continue;
            }
            if (c === '|' || c === '\t') { add('space', 1, c === '\t' ? '    ' : ' '); continue; }
            if (c === '^' || c === '`') { add('unknown', 1); continue; }
            add('text', 1);
        }
        return tokens;
    }

    function sourceText(raw) {
        if (raw === null) return null;
        if (typeof raw !== 'string') throw new TypeError('Expected string or null');
        return raw.replace(/[\u0000-\u001f\u007f]/g, c =>
            ({'\n': '\\n', '\r': '\\r', '\t': '\\t'}[c] || '\\x' + c.charCodeAt(0).toString(16).padStart(2, '0')));
    }

    function format(raw, chapter, artwords = {}) {
        if (raw === null) return {raw: null, source: null, plain: null, state: 'missing', issues: [], tokens: []};
        const tokens = tokenize(raw, chapter), issues = [], artwordRanges = [];
        let plain = '', hasControl = false;
        for (const token of tokens) {
            switch (token.kind) {
                case 'text': case 'space': case 'break': plain += token.value; break;
                case 'control': hasControl = true; break;
                case 'image':
                    if (token.value.cmd === 'O' && typeof artwords[token.value.arg] === 'string') {
                        artwordRanges.push([plain.length, plain.length + artwords[token.value.arg].length]);
                        plain += artwords[token.value.arg]; break;
                    }
                    plain += `〔${labels[token.value.cmd]} ${token.value.arg}〕`;
                    issues.push({kind: 'unresolved-image', raw: token.raw, start: token.start}); break;
                case 'parameter':
                    plain += `〔参数 ${token.raw}〕`;
                    issues.push({kind: 'unresolved-parameter', raw: token.raw, start: token.start}); break;
                case 'choice':
                    plain += `〔选择指令 ${token.raw}〕`; break;
                case 'unknown':
                    plain += token.raw;
                    issues.push({kind: 'unknown-sequence', raw: token.raw, start: token.start}); break;
            }
        }
        const state = raw === '' ? 'empty' : !plain.trim() && hasControl ? 'control-only' : 'text';
        return {raw, source: sourceText(raw), plain, state, issues, tokens, artwordRanges};
    }

    // Layout offsets only: leave plain, source, copy and search representations intact.
    function readingLines(plain) {
        let start = 0, hanging = false;
        return plain.split('\n').map(line => {
            const marker = line.match(/^([ \t\u3000]*)([*＊])([ \t\u3000]*)/);
            if (marker) hanging = true;
            else if (!line.trim()) hanging = false;
            const prefix = marker ? marker[0] : hanging ? line.match(/^[ \t\u3000]*/)[0] : '';
            const result = {start, end: start + line.length, bodyStart: start + prefix.length,
                hanging, markerStart: marker ? start + marker[1].length : null};
            start += line.length + 1;
            return result;
        });
    }

    function searchText(raw, chapter) {
        const view = format(raw, chapter);
        return view.plain === null ? null : view.plain.replace(/\s+/g, ' ').trim().toLowerCase();
    }

    function decodeRow(chapterData, row) {
        const result = {chapter: chapterData.chapter, key: row[0]};
        if (chapterData.artwords?.[row[0]]) result.artwords = chapterData.artwords[row[0]];
        chapterData.languages.forEach((language, index) => {
            result[language] = row[index + 1] === null ? null : chapterData.strings[row[index + 1]];
        });
        if(chapterData.source_files)result.sources=(row[chapterData.languages.length+1]||[]).map(([file,line])=>({file:chapterData.source_files[file],line}));
        return result;
    }

    const api = {tokenize, sourceText, format, readingLines, searchText, decodeRow};
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.DialogueText = api;
}(typeof globalThis !== 'undefined' ? globalThis : this));
