"""Lexical calls without attribution inference dependencies."""
import re
from .font_flow import TOKEN
from .gml_dialogue import split_args

def _calls(text, base=0):
    """Lexical call positions, excluding comments and quoted lookalikes."""
    tokens = [t for t in TOKEN.finditer(text)
              if not t.group().startswith(("//", "/*"))]
    for i, token in enumerate(tokens[:-1]):
        if not re.fullmatch(r"[A-Za-z_$][\w$]*", token.group()) or tokens[i + 1].group() != "(":
            continue
        args, end, ok = split_args(text, tokens[i + 1].start())
        if ok:
            yield {"call": token.group(), "args": args, "offset": base + token.start(),
                   "end": base + end + 1}
