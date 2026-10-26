"""Extracted shared helpers; origins and retained symbols: SOURCES.json."""
from __future__ import annotations

from dataclasses import dataclass, field

import re

from .gml_dialogue import as_string_literal, split_args

TOKEN = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|'
                   r"'(?:\\.|[^'\\])*'|[A-Za-z_$][\w$]*|"
                   r'\d+(?:\.\d+)?|==|!=|<=|>=|&&|\|\||\+\+|--|\+=|-=|\*=|/=|<<|>>|[^\s]')

@dataclass
class Node:
    kind: str
    start: int
    end: int
    text: str = ''
    children: list = field(default_factory=list)
    other: list = field(default_factory=list)

class Parser:
    def __init__(self, text):
        self.text = text
        self.tokens = [m for m in TOKEN.finditer(text) if not m.group().startswith(('//', '/*'))]
        self.i = 0

    def peek(self):
        return self.tokens[self.i].group() if self.i < len(self.tokens) else ''

    def pos(self):
        return self.tokens[self.i].start() if self.i < len(self.tokens) else len(self.text)

    def group(self):
        if self.peek() != '(':
            raise ValueError(f'expected parenthesis at {self.pos()}')
        start = self.pos()
        self.i += 1
        depth = 1
        while self.i < len(self.tokens):
            s = self.peek()
            depth += (s == '(') - (s == ')')
            end = self.tokens[self.i].end()
            self.i += 1
            if depth == 0:
                return self.text[start + 1:end - 1]
        raise ValueError(f'unclosed parenthesis at {start}')

    def sequence(self, stop=('}',)):
        out = []
        while self.peek() and self.peek() not in stop:
            previous = self.i
            out.append(self.statement())
            if previous == self.i:
                raise ValueError(f'parser made no progress at {self.pos()}')
        return out

    def statement(self):
        start, word = self.pos(), self.peek()
        self.i += 1
        if word == ';':
            return Node('stmt', start, self.pos(), ';')
        if word == '{':
            children = self.sequence()
            if self.peek() != '}':
                raise ValueError(f'unclosed block at {start}')
            self.i += 1
            return Node('block', start, self.pos(), children=children)
        if word == 'if':
            cond = self.group()
            yes = self.statement()
            no = []
            if self.peek() == 'else':
                self.i += 1
                no = [self.statement()]
            return Node('if', start, self.pos(), cond, [yes], no)
        if word == 'switch':
            expr = self.group()
            if self.peek() != '{':
                raise ValueError(f'expected switch block at {self.pos()}')
            self.i += 1
            cases = []
            while self.peek() and self.peek() != '}':
                cp, label = self.pos(), self.peek()
                if label not in ('case', 'default'):
                    raise ValueError(f'expected case at {cp}')
                self.i += 1
                p = self.pos()
                while self.peek() and self.peek() != ':':
                    self.i += 1
                value = self.text[p:self.pos()].strip() if label == 'case' else 'default'
                self.i += 1
                body = self.sequence(('case', 'default', '}'))
                cases.append(Node('case', cp, self.pos(), value, body))
            if self.peek() != '}':
                raise ValueError(f'unclosed switch at {start}')
            self.i += 1
            return Node('switch', start, self.pos(), expr, cases)
        if word in ('while', 'for', 'repeat', 'with'):
            expr = self.group()
            body = self.statement()
            return Node(word, start, self.pos(), expr, [body])
        if word == 'function':
            name = self.peek()
            self.i += 1
            args = self.group()
            body = self.statement()
            return Node('function', start, self.pos(), name + '(' + args + ')', [body])
        # The first token was already consumed, including a leading parenthesis
        # in (expression).method(). Keep it in the opaque-statement balance.
        depth = int(word in ('(', '['))
        while self.i < len(self.tokens):
            token = self.peek()
            if token == ';' and depth == 0:
                end = self.tokens[self.i].end()
                self.i += 1
                return Node('stmt', start, end, self.text[start:end])
            if token == '}' and depth == 0:
                break
            depth += (token in ('(', '[', '{')) - (token in (')', ']', '}'))
            self.i += 1
        return Node('stmt', start, self.pos(), self.text[start:self.pos()])

def parse(text):
    return Parser(text).sequence(stop=())

def walk(nodes):
    for node in nodes:
        yield node
        yield from walk(node.children)
        yield from walk(node.other)

UNKNOWN = object()

def unparen(s):
    s = s.strip()
    while s.startswith('(') and s.endswith(')'):
        tokens = list(TOKEN.finditer(s))
        depth, closes = 0, None
        for t in tokens:
            depth += (t.group() == '(') - (t.group() == ')')
            if depth == 0:
                closes = t.end()
                break
        if closes != len(s):
            break
        s = s[1:-1].strip()
    return s

def split_top(s, operators):
    depth = 0
    for match in TOKEN.finditer(s):
        t = match.group()
        depth += (t in ('(', '[')) - (t in (')', ']'))
        if depth == 0 and t in operators:
            yield s[:match.start()], t, s[match.end():]

def constant(expr, env):
    """Only evaluate a deliberately small pure subset, never Python eval()."""
    s = unparen(expr)
    if s in env:
        return env[s]
    literal = as_string_literal(s)
    if literal is not None:
        return literal
    if s in ('true', 'false'):
        return s == 'true'
    if re.fullmatch(r'(?:room_|spr_|obj_)\w+', s):
        return s
    if re.fullmatch(r'-?\d+(?:\.\d+)?', s):
        return float(s) if '.' in s else int(s)
    ternary = list(split_top(s, ('?',)))
    if ternary:
        test, _, rest = ternary[0]
        depth = 0
        for a, op, b in split_top(rest, ('?', ':')):
            if op == '?':
                depth += 1
            elif depth:
                depth -= 1
            else:
                cv = constant(test, env)
                if cv is UNKNOWN:
                    av, bv = constant(a, env), constant(b, env)
                    return av if av is not UNKNOWN and av == bv else UNKNOWN
                return constant(a if cv else b, env)
    call = re.match(r'^(string|string_lower|real|chr|langopt)\s*\(', s)
    if call:
        args, end, ok = split_args(s, s.index('('))
        if ok and end == len(s) - 1:
            values = [constant(a, env) for a in args]
            if call[1] == 'langopt' and len(values) == 2:
                language = env.get('global.lang', UNKNOWN)
                if language is UNKNOWN or language is None:
                    return values[0] if values[0] is not UNKNOWN and values[0] == values[1] else UNKNOWN
                return values[1 if language == 'ja' else 0]
            if len(values) == 1 and values[0] is not UNKNOWN:
                try:
                    return {'string': str, 'string_lower': lambda x: str(x).lower(),
                            'real': float, 'chr': chr}[call[1]](values[0])
                except (TypeError, ValueError, KeyError):
                    pass
        return UNKNOWN
    # GML's && and || short circuit even if the other operand is unknown.
    for ops in (('||', 'or'), ('&&', 'and'), ('==', '!=', '>=', '<=', '>', '<'), ('+', '-'), ('*', '/')):
        parts = list(split_top(s, ops))
        if not parts:
            continue
        a, op, b = parts[-1]
        if not a.strip():
            continue
        av, bv = constant(a, env), constant(b, env)
        if op in ('||', 'or'):
            if av is not UNKNOWN and bool(av) or bv is not UNKNOWN and bool(bv):
                return True
        if op in ('&&', 'and'):
            if av is not UNKNOWN and not bool(av) or bv is not UNKNOWN and not bool(bv):
                return False
        if av is UNKNOWN or bv is UNKNOWN:
            return UNKNOWN
        try:
            return {'==': lambda: av == bv, '!=': lambda: av != bv,
                    '>=': lambda: av >= bv, '<=': lambda: av <= bv,
                    '>': lambda: av > bv, '<': lambda: av < bv,
                    '+': lambda: av + bv, '-': lambda: av - bv,
                    '*': lambda: av * bv, '/': lambda: av / bv,
                    '&&': lambda: bool(av and bv), 'and': lambda: bool(av and bv),
                    '||': lambda: bool(av or bv), 'or': lambda: bool(av or bv)}[op]()
        except (TypeError, ValueError, ZeroDivisionError):
            return UNKNOWN
    if s.startswith('!'):
        v = constant(s[1:], env)
        return UNKNOWN if v is UNKNOWN else not bool(v)
    return UNKNOWN

def assignments(text):
    """Simple assignment only; comparison operators cannot match."""
    m = re.match(r'\s*(?:var\s+)?([\w.]+(?:\[[^\]]+\])?)\s*=(?!=)\s*([\s\S]*?);?\s*$', text)
    return (m[1], m[2].rstrip(';').strip()) if m else None
