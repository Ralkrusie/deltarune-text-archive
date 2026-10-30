"""A literal timed answer gate between a queued menu and its response state."""
import re
from dataclasses import replace

from .queued_choices import NUMBER, number


def timed_gate(q, gate, producer, options):
    compact = q.protocol.compact
    parts = {compact(p) for p in gate.text.split('&&')}
    if (gate.other or len(parts) != 2 or 'customcon==1' not in parts
            or not any(re.fullmatch(r'con=='+NUMBER, p) for p in parts)):
        return None
    nodes = q.a.flat(gate.children)
    if len(nodes) != 3:
        return None
    tick, timeout, answered = nodes
    timer = re.fullmatch(r'(\w+)\+\+;', compact(tick.text)) if tick.kind == 'stmt' else None
    if not timer or timer[1] in ('con', 'customcon'):
        return None
    timer = timer[1]
    if (timeout.kind != 'if' or timeout.other
            or not re.fullmatch(re.escape(timer)+r'>=\d+', compact(timeout.text))):
        return None
    force = q.a.flat(timeout.children)
    selected = re.fullmatch(r'global\.choice=(\d+);', compact(force[0].text)) if len(force) == 1 else None
    if not selected or int(selected[1]) not in options:
        return None
    if answered.kind != 'if' or answered.other or compact(answered.text) != 'global.choice!=-1':
        return None
    ack = q.a.flat(answered.children)
    transitions = [(n, number(m[1])) for n in ack if n.kind == 'stmt'
                   and (m := re.fullmatch(r'con\s*=\s*('+NUMBER+r')\s*;', n.text))]
    if len(transitions) != 1:
        return None
    write, value = transitions[0]
    targets = q.stages[value]
    if q.writes[value] != [write.start] or len(targets) != 1:
        return None
    target = targets[0]
    if (target.start < gate.end or target.start in q.excluded or target.start in q.consumed
            or target.other or not re.fullmatch(r'con\s*==\s*'+NUMBER, target.text)):
        return None
    initializers = [n for n in producer if n.kind == 'stmt' and compact(n.text) == timer+'=0;']
    if len(initializers) != 1:
        return None
    cleanup = [n for n in ack if compact(n.text) != timer+'=0;'
               and not (n.kind == 'with' and n.text == 'obj_choicer_neo'
                        and [compact(c.text) for c in q.a.flat(n.children)] == ['instance_destroy();'])]
    if not q.protocol.safe(cleanup, allow_state=True):
        return None
    if not any(compact(n.text) == 'c_waitcustom_end();' for n in cleanup):
        return None
    return {'target': replace(gate, end=target.end, children=target.children),
            'consumed': [gate.start, target.start], 'initializer': initializers[0],
            'auto_answer': {'condition': timeout.text, 'option': int(selected[1])}}
