"""Canonical legacy occurrence IDs and argument syntax, migrated without outside imports."""

import re
import hashlib
import json

from pathlib import PurePosixPath
SOURCE_KINDS = {"canonical", "zh"}

TOKEN = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'
                   r"'(?:\\.|[^'\\])*'|[A-Za-z_$][\w$]*|"
                   r'\d+(?:\.\d+)?|==|!=|<=|>=|&&|\|\||\+\+|--|\+=|-=|\*=|/=|<<|>>|[^\s]')

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

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()

def _nonempty(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('missing ' + label)

def _hash(value, label):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('invalid SHA-256: ' + label)

def _path(value, label):
    _nonempty(value, label)
    path = PurePosixPath(value)
    if (path.is_absolute() or '\\' in value or ':' in value or
            '..' in path.parts or path.as_posix() != value or value == '.'):
        raise ValueError('path must be normalized project-relative text: ' + label)

def _chapter(chapter):
    if type(chapter) is not int or chapter not in range(1, 6):
        raise ValueError('chapter must be an integer in 1..5')

def occurrence_id(chapter, source_kind, path, sha256, key, offset, call):
    _chapter(chapter)
    if source_kind not in SOURCE_KINDS:
        raise ValueError('invalid source kind')
    _path(path, 'occurrence source')
    _hash(sha256, 'occurrence source')
    if key is not None:
        _nonempty(key, 'localization key')
    if type(offset) is not int or offset < 0:
        raise ValueError('source offset must be a nonnegative integer')
    _nonempty(call, 'registration call')
    return 'occurrence:' + digest([chapter, source_kind, path, sha256, key, offset, call])[:32]
