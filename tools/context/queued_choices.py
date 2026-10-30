"""Bounded, same-event queued menus. Unknown transitions stay independent.

Plans refer to original AST nodes; projection never copies a source occurrence
to multiple answer arms. A new menu is a boundary for the previous answer.
"""
from collections import defaultdict
from dataclasses import replace
from decimal import Decimal
import copy
import re

from .queued_protocol import QueuedProtocol


NUMBER = r'-?\d+(?:\.\d+)?'
WRITE = r'(?:=(?!=)|\+=|-=|\*=|/=|\+\+|--)'


def number(text):
    return Decimal(text) if re.fullmatch(NUMBER, text.strip()) else None


def state(node):
    if node.kind != 'if':
        return None
    values = [number(m[1]) for part in re.split(r'\s*&&\s*', node.text)
              if (m := re.fullmatch(r'con\s*==\s*(' + NUMBER + ')', part))]
    return values[0] if len(values) == 1 else None


class QueuedChoices:
    allow_empty_arms = False
    review_response_assignments = True
    def __init__(self, analyzer, name, excluded=()):
        self.a = analyzer
        self.name = name
        self.data = analyzer.file(name)
        self.source = self.data['source']
        self.protocol = QueuedProtocol(analyzer, name)
        self.excluded = set(excluded)
        self.plans = {}
        self.consumed = set()
        self.omit = set()
        self.audit = []
        self.candidates = {}
        self.failed = {}
        self.active = set()
        self.stages = defaultdict(list)
        self.writes = defaultdict(list)
        self.unknown_writes = False
        self.claimed = {}
        self.prefix_reviews = {}
        self.response_reviews = {}
        self.setup_wrappers = {}
        self.routes = None

    def line(self, offset):
        return self.source.count('\n', 0, offset) + 1

    def tokens(self, text):
        return [t.group() for t in self.a.flow.TOKEN.finditer(text)
                if not t.group().startswith(('//', '/*'))]

    def prompt(self, n):
        if n.kind != 'stmt':
            return None
        calls = list(self.a.calls(n.text))
        if not calls or calls[0]['offset'] != 0:
            return None
        c = calls[0]
        if (c['call'] not in ('c_msgset','c_msgnext') and c['call'] not in self.a.gml.FUNCTIONS
            or not c['call'].startswith(('c_msgset', 'c_msgnext'))
            or c['end'] != len(n.text.strip().rstrip(';').strip())):
            return None
        at = 1 if 'set' in c['call'] else 0
        if len(c['args']) <= at:
            return None
        literal = self.a.gml.as_string_literal(c['args'][at])
        controls = re.findall(r'\\C([2-4])(?!\d)', literal or '')
        return int(controls[0]) if len(controls) == 1 else None

    def inventory_writes(self):
        clean = ' '.join(t for t in self.tokens(self.source) if not t.startswith(('"', "'")))
        if re.search(r'\b(?:var|static|globalvar)\b[^;]*\b(?:con|customcon)\b', clean):
            # The queue writes instance.customcon. A local of the same name
            # makes the response guard read a different value in this event.
            self.unknown_writes = True
        tokens = list(self.a.flow.TOKEN.finditer(self.source))
        tokens = [t for t in tokens if not t.group().startswith(('//', '/*'))]
        for i, token in enumerate(tokens[:-1]):
            if token.group() != 'con':
                continue
            if i and tokens[i - 1].group() in ('var', 'static', 'globalvar', '++', '--'):
                self.unknown_writes = True
            operator = tokens[i + 1].group()
            # TOKEN keeps arithmetic updates together but splits bitwise,
            # remainder and shift assignments (e.g. "<<", "="). All updates
            # compete with the literal producer even outside the menu block.
            if (operator in ('%', '&', '|', '^', '<<', '>>') and i + 2 < len(tokens)
                and tokens[i + 2].group() == '='):
                self.unknown_writes = True
                continue
            if (operator == '?' and i + 3 < len(tokens)
                and [t.group() for t in tokens[i + 2:i + 4]] == ['?', '=']):
                self.unknown_writes = True
                continue
            if operator not in ('=', '+=', '-=', '*=', '/=', '++', '--'):
                continue
            rest = tokens[i + 2:]
            sign = ''
            if rest and rest[0].group() == '-':
                sign = '-'; rest = rest[1:]
            value = number(sign + rest[0].group()) if rest else None
            if operator != '=' or value is None or len(rest) < 2 or rest[1].group() != ';':
                self.unknown_writes = True
            else:
                # Qualified writes are counted as competition, never as our
                # producer. Decimal('1.10') and Decimal('1.1') are the same state.
                self.writes[value].append(token.start())
        for c in self.data['calls']:
            if any(self.a.gml.as_string_literal(arg) == 'con' for arg in c['args']):
                self.unknown_writes = True

    def discover(self, nodes, root, path=(), before=(), guards=()):
        flat = []
        for n in self.a.flat(nodes):
            setup = self.protocol.menu_setup(n)
            if setup:
                flat.extend(setup)
                self.setup_wrappers[setup[0].start] = n
            else:
                flat.append(n)
        for index, n in enumerate(flat):
            count = self.prompt(n)
            if count:
                self.candidates[n.start] = {'prompt': n, 'count': count, 'scope': flat,
                                            'index': index, 'root': root, 'path': list(path),
                                            'before': list(before), 'guards': list(guards)}
            if n.kind == 'if':
                for arm, body in (('then', n.children), ('else', n.other)):
                    self.discover(body, root, (*path, {'condition': n.text, 'arm': arm,
                                                      'line': self.line(n.start)}), (*before, *flat[:index]), (*guards, n))

    def fail(self, offset, reason):
        self.failed[offset] = reason
        return None

    def safe(self, nodes, skip=()):
        """Remove only whole, independently proven nested menu statements."""
        skip = set(skip)
        def stripped(items):
            return [replace(n, children=stripped(n.children), other=stripped(n.other))
                    for n in items if n.start not in skip]
        return self.protocol.safe(stripped(nodes), allow_state=True)

    def local_prefix(self, nodes, prompt, review=None, last_text=None):
        """Keep local hazards; unknown staging does not veto a menu relation.

        This projects the source's menu/answer structure, not a proof that all
        background objects leave the answer untouched. Unchecked work goes to
        the developer audit only; menu construction and consumption stay checked.
        """
        if review is None:
            review = self.prefix_reviews.setdefault(prompt.start, [])
        if last_text is None:
            last_text = prompt.start
        field = r'(?:global\.(?:choice|choicemsg|msc)|(?:\w+\.)?(?:con|customcon))'
        update = r'(?:=(?!=)|(?:\+|-|\*|/|%|&|\||\^|<<|>>|\?\?)=|\+\+|--)'
        for node in self.a.flat(nodes):
            if self.protocol.safe([node], allow_state=True, _last_text=last_text):
                continue
            reason = self.protocol.reason
            text = self.source[node.start:node.end]
            if self.protocol.staging_callback(node):
                review.append({'line': self.line(node.start), 'statement': text,
                               'previous_reason': reason, 'scope': 'local_callback_body'})
                continue
            tokens = self.tokens(text)
            clean = ''.join('""' if t.startswith(('"', "'")) else t for t in tokens)
            if (re.search(r'(?<![\w.])'+field+r'(?:\[[^\]]*\])?'+update, clean)
                    or re.search(r'(?:\+\+|--)'+field+r'\b', clean)):
                return self.protocol.fail('explicit_prefix_state_or_answer_write')
            if any(t in ('exit', 'return', 'break', 'continue') for t in tokens):
                return self.protocol.fail('prefix_control_transfer')
            if reason in ('queue_termination_before_text', 'queue_pause_before_text'):
                return False
            for call in self.a.calls(text):
                literals = [self.a.gml.as_string_literal(arg) for arg in call['args']]
                if call['call'] in ('c_customfunc', 'c_delay_customfunc') or 'customfunc' in literals:
                    return self.protocol.fail('explicit_prefix_callback')
                if any(s in {'choice', 'choicemsg', 'msc', 'con', 'customcon'} for s in literals):
                    return self.protocol.fail('explicit_prefix_state_argument')
                if any(re.search(r'\\C[1-4]', s or '') for s in literals):
                    return self.protocol.fail('new_choice_prompt')
            review.append({'line': self.line(node.start), 'statement': text,
                           'previous_reason': reason})
        return True

    def response_safe(self, nodes, skip, target):
        """Keep the response's branches even when ancillary assignments are opaque.

        Menu/answer writes, callbacks, transfers and unsupported calls still
        block a relation. An unchecked local/object assignment is evidence for
        review, not a claim about the helper's complete runtime effects.
        """
        if self.safe(nodes, skip):
            return True
        if not self.review_response_assignments:
            return False
        last_text = max((r['offset'] for n in nodes for r in self.a.within(self.name,n)), default=-1)
        review = self.response_reviews.setdefault(target.start, [])
        def visit(items):
            for n in self.a.flat(items):
                if n.start in skip:
                    continue
                if n.kind == 'if':
                    if not self.protocol.safe([replace(n, children=[], other=[])], True, last_text):
                        return False
                    if not visit(n.children) or not visit(n.other):
                        return False
                    continue
                if self.protocol.safe([n], True, last_text):
                    continue
                reason = self.protocol.reason
                if self.protocol.staging_callback(n):
                    review.append({'line': self.line(n.start), 'statement': self.source[n.start:n.end],
                                   'previous_reason': reason, 'scope': 'local_callback_body'})
                    continue
                # The construction/consumption protocol is already bound.
                # Unrelated assignments should not discard the whole answer.
                assignment = re.fullmatch(r'(?:var\s+)?(\w+(?:\.\w+)?)\s*=(?!=)\s*([\s\S]+);', n.text) if n.kind=='stmt' else None
                if not assignment or assignment[1].split('.')[0] in ('global','self','other'):
                    return False
                if 'function' in self.tokens(assignment[2]):
                    return self.protocol.fail('deferred_response_assignment')
                calls = list(self.a.calls(assignment[2]))
                if any(c['call'].startswith(('c_', 'd_', 'room_', 'game_'))
                       or c['call'] in ('scr_text', 'scr_readychoicer', 'script_execute', 'instance_destroy') for c in calls):
                    return self.protocol.fail('response_assignment_control_call')
                if not self.local_prefix([n], target, review, last_text):
                    return False
            return True
        return visit(nodes)

    def response(self, target, options, nested):
        flat = self.a.flat(target.children)
        skip = {n.start for plan in nested for n in plan['menu_nodes']}
        mapped = {}; roots = []; response_nodes = []
        def chain(n):
            match = re.fullmatch(r'global\.choice\s*==\s*(\d+)', n.text)
            if not match or int(match[1]) not in options:
                return False
            index = int(match[1])
            if index in mapped:
                # A later answer check may only arrange already-vetted actions.
                if self.a.within(self.name, n) or any(n.start <= p['prompt'].start < n.end for p in nested):
                    return False
                return not n.other
            mapped[index] = n.children
            response_nodes.append(n)
            other = self.a.flat(n.other)
            if len(other) == 1 and other[0].kind == 'if':
                return chain(other[0])
            if other:
                remaining = set(options) - set(mapped)
                if len(remaining) != 1:
                    return False
                mapped[remaining.pop()] = other
            return True
        for index, n in enumerate(flat):
            if n.kind != 'if':
                continue
            if not re.search(r'\bglobal\s*\.\s*choice\b', n.text):
                continue
            if not chain(n):
                return None, 'unmapped_or_repeated_textual_answer'
            roots.append(index)
        if not roots or (set(mapped) != set(options) and not self.allow_empty_arms):
            return None, 'incomplete_answer_arms'
        for i in options:
            mapped.setdefault(i, [])
        first = roots[0]
        last = roots[-1]
        prefix, tail = flat[:first], flat[last + 1:]
        if not self.response_safe(flat[:last + 1], skip, target):
            return None, 'unsafe_response:' + str(self.protocol.reason)
        detached_tail = False
        if not self.response_safe(tail, skip, target):
            # A common suffix does not decide the preceding menu's answer.
            # Keep opaque work as an independent source block, without a proven
            # join/continuation. Never move a later answer use or new menu here.
            text=' '.join(self.source[n.start:n.end] for n in tail)
            clean=''.join(t for t in self.tokens(text) if not t.startswith(('"',"'")))
            if (not self.review_response_assignments
                    or re.search(r'global\.(?:choice|choicemsg|msc)\b',clean)
                    or any(n.start<=p['prompt'].start<n.end for n in tail for p in nested)):
                return None, 'unsafe_response:' + str(self.protocol.reason)
            if any(re.search(r'\\C[1-4]',self.a.gml.as_string_literal(arg) or '')
                   for c in self.a.calls(text) for arg in c['args']):
                return None, 'new_menu_in_common_tail'
            detached_tail = True
            self.response_reviews.setdefault(target.start,[]).append({
                'line': self.line(tail[0].start), 'statement': text,
                'previous_reason': self.protocol.reason, 'scope': 'unexpanded_common_tail'})
        for n in flat[first:last + 1]:
            if n not in response_nodes and self.a.within(self.name, n):
                return None, 'interleaved_common_text'
        if any(n.start <= p['prompt'].start < n.end for n in prefix for p in nested):
            return None, 'new_menu_before_old_answer'
        # Preserve ordinary common-tail conditions, including their text.
        return {'mapped': mapped, 'prefix': prefix, 'tail': tail,
                'detached_tail': detached_tail}, None

    def plan_one(self, offset):
        if offset in self.plans:
            return self.plans[offset]
        if offset in self.failed:
            return None
        if offset in self.active:
            return self.fail(offset, 'cyclic_menu_chain')
        self.active.add(offset)
        try:
            return self._plan_one(offset)
        finally:
            self.active.remove(offset)

    def _plan_one(self, offset):
        candidate = self.candidates[offset]
        nodes = candidate['scope']; at = candidate['index']; prompt = candidate['prompt']
        if candidate['root'].start in self.excluded:
            return self.fail(offset, 'existing_relation_scope')
        if not self.protocol.prompt(prompt):
            return self.fail(offset, 'unverified_prompt_call')
        guards = [replace(n, children=[], other=[]) for n in [candidate['root'], *candidate['guards']]]
        if not self.protocol.safe(guards, allow_state=True):
            return self.fail(offset, 'opaque_menu_condition')
        resets = [i for i, n in enumerate(nodes[:at]) if n.kind == 'stmt'
                  and self.tokens(n.text) == ['global', '.', 'choice', '=', '-', '1', ';']]
        if not resets:
            return self.fail(offset, 'no_direct_answer_reset')
        begin = resets[-1]
        if begin == 0 or self.tokens(nodes[begin - 1].text) != ['global', '.', 'msc', '=', '-', '99', ';']:
            return self.fail(offset, 'unverified_local_message_entry')
        prefix = candidate['before'] + nodes[:begin - 1]
        if not self.local_prefix(prefix, prompt):
            return self.fail(offset, 'unsafe_queued_prefix:' + str(self.protocol.reason))
        segment = nodes[begin - 1:]
        if any(self.prompt(n) for n in nodes[begin:at]) or any(self.prompt(n) for n in nodes[at + 1:]):
            return self.fail(offset, 'multiple_menus_in_scope')
        options = self.a.options(self.name, nodes[begin:at], candidate['count'])
        if len(options) != candidate['count']:
            return self.fail(offset, 'dynamic_or_missing_options')
        if not self.protocol.labels(nodes[begin:at]):
            return self.fail(offset, 'unverified_label_getter')
        if any(self.a.within(self.name, n) for n in nodes[at + 1:]):
            return self.fail(offset, 'text_after_prompt')
        makers = [n for n in nodes[at + 1:] if self.protocol.maker(n)]
        waits = [n for n in nodes[at + 1:] if n.kind == 'stmt'
                 and self.tokens(n.text) == ['c_waitcustom', '(', ')', ';']]
        if len(makers) != 1 or len(waits) != 1 or makers[0].end > waits[0].start:
            return self.fail(offset, 'unverified_dialogue_creation_or_wait')
        assignments = [(n, number(m[1])) for n in nodes if n.kind == 'stmt'
                       and (m := re.fullmatch(r'con\s*=\s*(' + NUMBER + r')\s*;', n.text))]
        if len(assignments) != 1:
            return self.fail(offset, 'non_unique_direct_target')
        write, value = assignments[0]
        if self.unknown_writes or len(self.writes[value]) != 1 or self.writes[value][0] != write.start:
            return self.fail(offset, 'competing_or_dynamic_state_write')
        targets = self.stages[value]
        if len(targets) != 1:
            return self.fail(offset, 'non_unique_response_state')
        target = targets[0]
        if target.start <= candidate['root'].start or target.start < nodes[-1].end or target.start in self.excluded:
            return self.fail(offset, 'non_forward_or_existing_response')
        parts = [''.join(self.tokens(p)) for p in re.split(r'\s*&&\s*', target.text)]
        expected = {'customcon==1', 'global.choice!=-1'}
        state_parts = [p for p in parts if re.fullmatch(r'con=='+NUMBER, p)]
        gate = None
        if target.other or len(state_parts) != 1 or set(parts) != expected | set(state_parts):
            from .queued_gate import timed_gate
            gate = timed_gate(self, target, nodes, options)
            if not gate:
                return self.fail(offset, 'unsupported_response_guard')
            target = gate['target']
        if value in self.claimed and self.claimed[value] != offset:
            return self.fail(offset, 'response_already_claimed')
        # The segment's protocol statements are checked above. Everything else
        # must be effect-safe, including expressions used to produce labels.
        protocol_nodes = {nodes[begin - 1].start, nodes[begin].start, prompt.start,
                          makers[0].start, waits[0].start}
        protocol_nodes.update(n.start for n in nodes[begin:at]
                              if re.match(r'global\.choicemsg(?:\[|\s*=)', n.text))
        if gate:
            protocol_nodes.add(gate['initializer'].start)
        # Pure conditions with verified display commands are ordinary setup.
        # Keep the menu/reset/maker themselves direct; conditional rewrites and
        # opaque calls still fail the same recursive effect check below.
        if not self.safe(segment, protocol_nodes):
            return self.fail(offset, 'unsafe_menu_segment:' + str(self.protocol.reason))
        nested = []
        for child_offset in sorted(self.candidates):
            if any(n.start <= child_offset < n.end for n in target.children):
                child = self.plan_one(child_offset)
                if child:
                    nested.append(child)
        response, reason = self.response(target, options, nested)
        if response is None:
            return self.fail(offset, reason)
        plan = {**candidate, **response, 'options': options, 'target': target,
                'state': format(value.normalize(), 'f'), 'menu_nodes': segment,
                'write_line': self.line(write.start)}
        wrapper = self.setup_wrappers.get(nodes[begin - 1].start)
        if wrapper:
            plan['menu_nodes'] = [*segment, wrapper]
            plan['queued_setup_line'] = self.line(wrapper.start)
        if gate:
            plan['auto_answer'] = gate['auto_answer']
            self.consumed.update(gate['consumed'])
        self.plans[offset] = plan
        self.claimed[value] = offset
        self.consumed.add(target.start)
        self.omit.update(r['occurrence_id'] for r in options.values())
        return plan

    def build(self):
        nodes = self.data['nodes']
        if 'c_waitcustom' not in self.source:
            return self
        for n in nodes:
            value = state(n)
            if value is not None:
                self.stages[value].append(n)
                self.discover(n.children, n)
        all_prompts = {}
        for call in self.data['calls']:
            name = call['call']
            if (name not in ('c_msgset','c_msgnext') and name not in self.a.gml.FUNCTIONS
                or not name.startswith(('c_msgset','c_msgnext'))):
                continue
            at = 1 if 'set' in name else 0
            if len(call['args']) <= at:
                continue
            text = self.a.gml.as_string_literal(call['args'][at]) or ''
            controls = re.findall(r'\\C([2-4])(?!\d)', text)
            if len(controls) == 1:
                all_prompts[call['offset']] = int(controls[0])
        if not all_prompts:
            return self
        self.inventory_writes()
        ready = self.protocol.ready() if self.candidates else False
        for offset in sorted(self.candidates):
            if ready:
                self.plan_one(offset)
            else:
                self.fail(offset, 'unverified_queue_protocol:' + str(self.protocol.reason))
        from .queued_routes import QueuedRoutes
        self.routes = QueuedRoutes(self).build()
        for offset, candidate in sorted(self.candidates.items()):
            plan = self.plans.get(offset)
            record = {'file': self.name, 'prompt_line': self.line(offset), 'option_count': candidate['count'],
                      'status': 'connected' if plan else 'unconnected',
                      'reason': None if plan else self.failed.get(offset, 'unresolved'), 'scope': candidate['path']}
            if plan:
                record.update(target_line=self.line(plan['target'].start), state=plan['state'],
                              option_keys=[r['key'] for r in plan['options'].values()])
                if self.prefix_reviews.get(offset):
                    record['prefix_review'] = self.prefix_reviews[offset]
                    record['relation_scope'] = 'local_menu_response'
                if self.response_reviews.get(plan['target'].start):
                    record['response_review'] = self.response_reviews[plan['target'].start]
                    record['relation_scope'] = 'local_menu_response'
                for field in ('queued_setup_line', 'auto_answer'):
                    if field in plan:
                        record[field] = plan[field]
                self.a.evidence.append({'rule': 'queued_local_choice', **record,
                                        'state_write_line': plan['write_line'],
                                        'helpers': sorted(self.protocol.helpers)})
            self.audit.append(record)
        for offset, count in sorted(all_prompts.items()):
            if offset not in self.candidates:
                self.audit.append({'file': self.name, 'prompt_line': self.line(offset),
                    'option_count': count, 'status': 'unconnected',
                    'reason': 'delayed_or_unsupported_scope', 'scope': []})
        self.audit.sort(key=lambda r:r['prompt_line'])
        return self

    def render(self, offset):
        plan = self.plans[offset]
        project = lambda nodes: self.a.project(self.name, nodes, self.omit, choice_scope=True)
        choice = {'type': 'choice', 'title': '玩家选择', 'branches': [
            {'option': copy.deepcopy(ref), 'body': {'type': 'sequence', 'children': project(plan['mapped'][i])}}
            for i, ref in sorted(plan['options'].items())]}
        if plan.get('auto_answer'):
            choice['auto_answer'] = plan['auto_answer']
        prefix = project(plan['prefix'])
        if prefix:
            choice['prefix'] = {'type': 'sequence', 'children': prefix}
        tail = project(plan['tail'])
        if tail and plan.get('detached_tail'):
            tail=[{'type':'block','label':'L'+str(self.line(plan['tail'][0].start)), 'children':tail}]
        elif tail and tail[0]['type'] == 'message' and tail[0].get('usage') != 'reference':
            choice['join_next'] = True
        return [choice, *tail]
