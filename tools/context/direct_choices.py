"""Same-event direct menus, including a second question inside an answer.

Only a literal, unique response state is followed. A common d_make after an
if/else may create the branch's menu; arbitrary later states are not expanded.
"""
import re
from dataclasses import replace

from .queued_choices import QueuedChoices, NUMBER, number, state
from .queued_protocol import QueuedProtocol


class DirectProtocol(QueuedProtocol):
    def prompt(self, statement):
        call = self.direct_call(statement)
        return bool(call and call['call'] in ('msgset', 'msgnext', 'msgsetloc', 'msgnextloc')
                    and all(self.pure(a) for a in call['args'])
                    and self.summary(call['call'], call['args']))

    def speaker(self):
        fn = self.function('scr_speaker')
        if not fn or self.compact(fn[1].text) != 'scr_speaker(arg0)':
            return False
        for n in self.a.flow.walk(fn[1].children):
            if n.kind == 'block':
                continue
            if n.kind == 'if' and self.pure(n.text):
                continue
            m = re.fullmatch(r'(_speaker|global\.(?:typer|fc|fe))\s*=\s*(.*);', n.text)
            if n.kind != 'stmt' or not m or not self.pure(m[2]):
                return False
        return True

    def summary(self, name, args):
        if name == 'msgset':
            return self.exact_function(name, 'function msgset(arg0,arg1){global.msgno=arg0;global.msg[arg0]=arg1;}')
        if name == 'msgnext':
            return (self.exact_function(name, 'function msgnext(arg0){global.msgno++;msgset(global.msgno,arg0);}')
                    and self.summary('msgset', ['0', '"text"']))
        if name in ('msgsetloc', 'msgnextloc'):
            fn = self.function(name)
            return bool(fn and self.localized(name, fn))
        if name == 'scr_speaker':
            return len(args) == 1 and self.speaker()
        if name == 'd_make':
            return not any(a.strip() for a in args) and self.dialogue_factory()
        return super().summary(name, args)

    def creator(self, node):
        if node.kind != 'stmt':
            return None
        text = self.compact(node.text)
        if text == 'd_make();':
            return '' if self.dialogue_factory() else None
        m = re.fullmatch(r'var(\w+)=d_make\(\);', text)
        return m[1] if m and self.dialogue_factory() else None

    def safe(self, nodes, allow_state=False, _last_text=None):
        # Named dialoguer handles only bind within this statement list.
        if _last_text is None:
            _last_text = max((r['offset'] for n in self.a.flat(nodes)
                              for r in self.a.within(self.name, n)), default=-1)
        handles = set()
        for n in self.a.flat(nodes):
            handle = self.creator(n)
            if handle is not None:
                if handle:
                    handles.add(handle)
                continue
            if n.kind == 'stmt':
                field = re.fullmatch(r'(\w+)\.(side|stay|zurasu)\s*=\s*(' + NUMBER + r');', n.text)
                if field and field[1] in handles:
                    continue
                # A literal animation frame/sprite write does not assign an
                # answer or flow state. No dynamic object/field expressions.
                visual = re.fullmatch(r'(\w+)\.(image_speed|image_index|sprite_index)\s*=\s*(' + NUMBER + r'|spr_\w+);', n.text)
                if visual and visual[1] not in ('global', 'self', 'other'):
                    continue
                m = re.match(r'(?:var\s+)?(\w+)\s*=(?!=)', n.text)
                if m:
                    handles.discard(m[1])
            if not super().safe([n], allow_state, _last_text):
                return False
        return True


class DirectChoices(QueuedChoices):
    allow_empty_arms = True
    review_response_assignments = False

    def __init__(self, analyzer, name, excluded=()):
        super().__init__(analyzer, name, excluded)
        self.protocol = DirectProtocol(analyzer, name)

    def prompt(self, n):
        c = self.protocol.direct_call(n) if n.kind == 'stmt' else None
        if not c or c['call'] not in ('msgset', 'msgnext', 'msgsetloc', 'msgnextloc'):
            return None
        at = 1 if 'set' in c['call'] else 0
        text = self.a.gml.as_string_literal(c['args'][at]) if len(c['args']) > at else None
        controls = re.findall(r'\\C([2-4])(?!\d)', text or '')
        return int(controls[0]) if len(controls) == 1 else None

    def discover(self, nodes, root, path=(), before=(), guards=(), following=()):
        flat = self.a.flat(nodes)
        for i, n in enumerate(flat):
            count = self.prompt(n)
            if count:
                self.candidates[n.start] = dict(prompt=n, count=count, scope=flat, index=i,
                    root=root, path=list(path), before=list(before), guards=list(guards), following=list(following))
            if n.kind == 'if':
                for arm, body in (('then', n.children), ('else', n.other)):
                    self.discover(body, root, (*path, dict(condition=n.text, arm=arm, line=self.line(n.start))),
                        (*before, *flat[:i]), (*guards, n), (*flat[i + 1:], *following))

    def _plan_one(self, offset):
        c = self.candidates[offset]
        nodes, at, prompt = c['scope'], c['index'], c['prompt']
        if c['root'].start in self.excluded:
            return self.fail(offset, 'existing_relation_scope')
        if not self.protocol.prompt(prompt):
            return self.fail(offset, 'unverified_direct_prompt')
        guards = [replace(n, children=[], other=[]) for n in [c['root'], *c['guards']]]
        if not self.protocol.safe(guards, True):
            return self.fail(offset, 'opaque_menu_condition')
        resets = [i for i, n in enumerate(nodes[:at]) if n.kind == 'stmt'
                  and self.protocol.compact(n.text) == 'global.choice=-1;']
        if not resets:
            return self.fail(offset, 'no_direct_answer_reset')
        begin = resets[-1]
        if begin == 0 or self.protocol.compact(nodes[begin - 1].text) != 'global.msc=-99;':
            return self.fail(offset, 'unverified_local_message_entry')
        prefix = c['before'] + nodes[:begin - 1]
        if not self.protocol.safe(prefix, True, _last_text=prompt.start):
            return self.fail(offset, 'unsafe_direct_prefix:' + self.protocol.reason)
        options = self.a.options(self.name, nodes[begin:at], c['count'])
        if len(options) != c['count']:
            return self.fail(offset, 'dynamic_or_missing_options')
        if not self.protocol.labels(nodes[begin:at]):
            return self.fail(offset, 'unverified_label_getter')
        if sum(bool(self.prompt(n)) for n in nodes[begin:]) != 1:
            return self.fail(offset, 'multiple_menus_in_scope')
        continuation = nodes[at + 1:] + c['following']
        if any(n.kind != 'stmt' or self.a.within(self.name, n) for n in continuation):
            return self.fail(offset, 'nontrivial_menu_continuation')
        makers = [n for n in continuation if self.protocol.creator(n) is not None]
        if len(makers) != 1 or not self.protocol.safe(continuation, True):
            return self.fail(offset, 'unverified_direct_creation')
        # The last unconditional write on the path may precede the containing
        # if (Berdly) or be inside its arm (bathroom/MichaelBomb).
        path = prefix + nodes[begin - 1:] + c['following']
        writes = [(n, number(m[1])) for n in path if n.kind == 'stmt'
                  and (m := re.fullmatch(r'con\s*=\s*(' + NUMBER + r')\s*;', n.text))]
        if not writes:
            return self.fail(offset, 'no_direct_target_state')
        write, value = writes[-1]
        if any(n.start > write.start and re.match(r'con\s*=(?!=)', n.text)
               for n in self.a.flow.walk(path) if n.kind == 'stmt'):
            return self.fail(offset, 'conditional_target_overwrite')
        if self.unknown_writes or self.writes[value] != [write.start]:
            return self.fail(offset, 'competing_or_dynamic_state_write')
        targets = self.stages[value]
        if len(targets) != 1:
            return self.fail(offset, 'non_unique_response_state')
        target = targets[0]
        parts = [self.protocol.compact(p) for p in re.split(r'\s*&&\s*', target.text)]
        states = [p for p in parts if re.fullmatch(r'con==' + NUMBER, p)]
        if (target.other or len(states) != 1 or len(parts) != 2
            or set(parts) != {'global.choice!=-1', *states}):
            return self.fail(offset, 'unsupported_response_guard')
        if target.start <= max(n.end for n in path) or target.start in self.excluded:
            return self.fail(offset, 'non_forward_or_existing_response')
        if value in self.claimed:
            return self.fail(offset, 'response_already_claimed')
        segment = nodes[begin - 1:]
        skip = {nodes[begin - 1].start, nodes[begin].start, prompt.start}
        skip.update(n.start for n in nodes[begin:at] if re.match(r'global\.choicemsg(?:\[|\s*=)', n.text))
        if not self.safe(segment, skip):
            return self.fail(offset, 'unsafe_direct_segment:' + self.protocol.reason)
        nested = []
        for child_offset in sorted(self.candidates):
            if target.start < child_offset < target.end:
                child = self.plan_one(child_offset)
                if child:
                    nested.append(child)
        response, reason = self.response(target, options, nested)
        if response is None:
            return self.fail(offset, reason)
        plan = {**c, **response, 'options': options, 'target': target, 'state': format(value.normalize(), 'f'),
                'menu_nodes': segment, 'write_line': self.line(write.start)}
        self.plans[offset] = plan
        self.claimed[value] = offset
        self.consumed.add(target.start)
        self.omit.update(r['occurrence_id'] for r in options.values())
        return plan

    def build(self):
        for n in self.data['nodes']:
            value = state(n)
            if value is not None:
                self.stages[value].append(n)
                self.discover(n.children, n)
        if not self.candidates:
            return self
        self.inventory_writes()
        ready = self.protocol.ready()
        for offset in sorted(self.candidates):
            if ready:
                self.plan_one(offset)
            else:
                self.fail(offset, 'unverified_dialogue_protocol')
        for offset, c in sorted(self.candidates.items()):
            p = self.plans.get(offset)
            row = dict(file=self.name, prompt_line=self.line(offset), option_count=c['count'],
                       scope=c['path'], status='connected' if p else 'unconnected', reason=None if p else self.failed[offset])
            if p:
                row.update(target_line=self.line(p['target'].start), state=p['state'],
                           option_keys=[r['key'] for r in p['options'].values()])
                self.a.evidence.append(dict(rule='direct_local_choice', **row,
                    state_write_line=p['write_line'], helpers=sorted(self.protocol.helpers)))
            self.audit.append(row)
        return self
