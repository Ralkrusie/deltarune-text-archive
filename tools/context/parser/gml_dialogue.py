"""Locate dialogue calls, keys and literal values in GML source."""
import os

import re

import sys

from collections import defaultdict

KEY_RE = re.compile(r'^.+_slash_.+_gml_\d+_\d+(?:_[a-z]+)?$')

FUNCTIONS = {
    'stringsetloc':    (0, -1),
    'stringsetsubloc': (0, -1),
    'stringset':       (0, None),
    'msgsetloc':       (1, -1),
    'msgsetsubloc':    (1, -1),
    'msgnextloc':      (0, -1),
    'msgnextsubloc':   (0, -1),
    'c_msgsetloc':     (1, -1),
    'c_msgsetsubloc':  (1, -1),
    'c_msgnextloc':    (0, -1),
    'c_msgnextsubloc': (0, -1),
    # ch1 专用：直接以本地化 key 取文本（英文在外部 lang 文件，代码里没有默认值）
    'scr_84_get_lang_string': (None, -1),
}

SPEAKER_FUNCS = ('c_speaker', 'scr_speaker', 'c_facenext', 'c_msgface')

EVENT_RE = re.compile(
    r'\b(' + '|'.join(re.escape(f) for f in (list(FUNCTIONS) + list(SPEAKER_FUNCS)))
    + r'|scr_\w*face\w*)\s*\(')

def decode_gml_string(s):
    """把 GML 字符串**内容**（已去掉外层引号）解码为运行时真实字符。

    ``\\\\`` → ``\\`` ／ ``\\n`` → 换行 ／ ``\\t`` → Tab ／ ``\\"`` → ``"``

    其余 ``\\X`` 原样保留：对话控制符 ``\\M3`` 在源码里写作 ``\\\\M3``，
    已由第一条规则还原为 ``\\M3``，不会走到末尾分支。
    """
    out = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == '\\' and i + 1 < n:
            nxt = s[i + 1]
            if nxt == '\\':
                out.append('\\')
            elif nxt == 'n':
                out.append('\n')
            elif nxt == 't':
                out.append('\t')
            elif nxt == '"':
                out.append('"')
            elif nxt == "'":
                out.append("'")
            elif nxt == 'r':
                out.append('\r')
            else:
                out.append(c)
                out.append(nxt)
            i += 2
            continue
        out.append(c)
        i += 1
    return ''.join(out)

def split_args(text, start):
    """从 ``text[start]``（必须是 ``(``）开始切分实参。

    返回 ``(args, end_index, ok)``；``args`` 为**原始文本**（未去引号、未去空白）。
    跟踪双引号状态与 ``()``/``[]`` 深度，因此参数内的逗号、嵌套调用、字符串都正确。
    """
    if start >= len(text) or text[start] != '(':
        return [], start, False
    args = []
    depth = 0
    i = start
    cur = start + 1
    in_str = False
    while i < len(text):
        c = text[i]
        if in_str:
            if c == '\\':
                i += 2
                continue
            if c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            i += 1
            continue
        if c == '(' or c == '[':
            depth += 1
            i += 1
            continue
        if c == ')' or c == ']':
            depth -= 1
            if depth == 0:
                args.append(text[cur:i])
                return args, i, True
            i += 1
            continue
        if c == ',' and depth == 1:
            args.append(text[cur:i])
            cur = i + 1
            i += 1
            continue
        i += 1
    return args, len(text), False

def as_string_literal(arg):
    """若参数是**单个字符串字面量**则返回其解码内容，否则 ``None``。

    ``"a" + "b"`` 这类表达式不返回（避免把拼接结果误当文本）。
    """
    a = arg.strip()
    if len(a) < 2 or a[0] != '"' or a[-1] != '"':
        return None
    body = a[1:-1]
    i = 0
    while i < len(body):
        if body[i] == '\\':
            i += 2
            continue
        if body[i] == '"':
            return None
        i += 1
    return decode_gml_string(body)

def line_of(text, pos):
    """返回 ``pos`` 所在的 1-based 行号。"""
    return text.count('\n', 0, pos) + 1

def scan_file(path, filename=None):
    """扫描单个 GML 文件，返回**消息调用**记录列表。

    记录字段：``key`` / ``english`` / ``call`` / ``file`` / ``line`` /
    ``has_key``（该函数是否本就带 key）/ ``key_ok``（key 是否形如本地化 key）/
    ``raw_key``（未通过校验的原始末参文本，便于诊断）。
    """
    filename = filename or os.path.basename(path)
    text = open(path, encoding='utf-8', errors='replace').read()
    records = []
    for ev in iter_events(text):
        if not ev['is_message']:
            continue
        name = ev['name']
        args = ev['args']
        eng_idx, key_idx = FUNCTIONS[name]
        if eng_idx is None:
            # 纯键引用（ch1 的 `scr_84_get_lang_string`）：代码里没有英文默认值，
            # 不属于脚本一的提取目标 —— 出处/说话人由脚本三处理
            continue
        english = as_string_literal(args[eng_idx]) if eng_idx < len(args) else None

        if key_idx is None:
            records.append({'key': None, 'english': english, 'call': name,
                            'file': filename, 'line': ev['line'],
                            'has_key': False, 'key_ok': False, 'raw_key': None})
            continue

        raw = args[-1] if (key_idx == -1 and args) else None
        key = as_string_literal(raw) if raw is not None else None
        key_ok = bool(key and KEY_RE.match(key))
        records.append({'key': key if key_ok else None, 'english': english,
                        'call': name, 'file': filename, 'line': ev['line'],
                        'has_key': True, 'key_ok': key_ok, 'raw_key': key})
    return records

def _lhs_of(text, pos):
    """取调用点之前**同一行**的赋值左值（如 ``global.msg[0]`` / ``armornametemp``）。

    用于判断这条文本写进了哪个容器（对话 / 选项 / 数据），见 `classify_container`。
    取不到（如调用作为参数传递）返回 ``None``。
    """
    line_start = text.rfind('\n', 0, pos) + 1
    seg = text[line_start:pos]
    if '=' not in seg:
        return None
    left = seg.rsplit('=', 1)[0].strip()
    if not left or not re.match(r'^[\w\.\[\]"\'\s]*$', left):
        return None
    return left or None

def iter_events(text):
    """按**文本出现顺序**产出对话相关调用 —— 供「顺序状态机」使用（脚本三）。

    覆盖：11 种消息函数 + `c_speaker`/`c_facenext`/`c_msgface` + `scr_*face`。
    每项含 ``name`` / ``args``（原始实参文本）/ ``pos`` / ``line`` / ``is_message`` / ``lhs``。
    函数定义行（``function stringsetloc(...)``）会被跳过。
    """
    for m in EVENT_RE.finditer(text):
        name = m.group(1)
        head = text[max(0, m.start() - 9):m.start()]
        if head.endswith('function '):
            continue
        args, _end, ok = split_args(text, m.end() - 1)
        if not ok:
            continue
        yield {
            'name': name,
            'args': args,
            'pos': m.start(),
            'line': line_of(text, m.start()),
            'is_message': name in FUNCTIONS,
            'lhs': _lhs_of(text, m.start()),
        }
