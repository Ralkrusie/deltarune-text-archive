"""Follow literal same-file states after an already bound queued answer.

Unique successors are nested; shared successors stay at one source landing.
This is a projection of explicit state writes, not execution of scene effects.
"""
import re

from .queued_choices import NUMBER, number


class QueuedRoutes:
    def __init__(self, queue):
        self.q = queue
        self.edges = {}
        self.inline = set()
        self.anchors = {}

    def build(self):
        q = self.q
        if q.unknown_writes:
            return self
        pending = [body for p in q.plans.values()
                   for body in [*p['mapped'].values(), *([] if p.get('detached_tail') else [p['tail']])]]
        visited = set()
        while pending:
            nodes = q.a.flat(pending.pop())
            writes = [(n, number(m[1])) for n in nodes if n.kind == 'stmt'
                      and (m := re.fullmatch(r'con\s*=\s*('+NUMBER+r')\s*;', n.text))]
            if len(writes) != 1:
                continue
            write, value = writes[0]
            if nodes[-1].start != write.start:
                continue
            if write.start in visited:
                continue
            visited.add(write.start)
            # A conditional/deferred competing write is not a final literal exit.
            all_writes = {at for positions in q.writes.values() for at in positions
                          if any(n.start <= at < n.end for n in nodes)}
            if all_writes != {write.start} or any(n.kind=='stmt' and re.match(r'(?:exit|return|break|continue)\b', n.text)
                                                 for n in q.a.flow.walk(nodes)):
                continue
            targets = q.stages[value]
            if len(targets) != 1:
                continue
            target = targets[0]
            if (target.start < write.end or target.start in q.excluded or target.start in q.consumed
                    or target.other or not re.fullmatch(r'con\s*==\s*'+NUMBER, target.text)
                    or not q.a.within(q.name,target)):
                continue
            self.edges[write.start] = target
            pending.append(target.children)
        for at, target in self.edges.items():
            value = number(re.fullmatch(r'con\s*==\s*('+NUMBER+r')', target.text)[1])
            if q.writes[value] == [at]:
                self.inline.add(target.start)
            else:
                self.anchors[target.start] = 'state-'+str(q.line(target.start))
            q.a.evidence.append({'rule': 'queued_state_continuation', 'file': q.name,
                                 'write_line': q.line(at), 'target_line': q.line(target.start),
                                 'state': str(value), 'shared': target.start not in self.inline,
                                 'scope': 'literal_same_file_state'})
        q.consumed.update(self.inline)
        return self

    def render(self, at):
        target = self.edges[at]
        if target.start in self.inline:
            return self.q.a.project(self.q.name, target.children, self.q.omit, choice_scope=True)
        return [{'type': 'jump', 'target': self.anchors[target.start],
                 'label': '接续 L'+str(self.q.line(target.start)), 'condition': target.text}]
