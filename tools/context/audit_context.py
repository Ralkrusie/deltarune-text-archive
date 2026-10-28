"""Developer-only registry of choice signals and text-related source conditions.

Discovery does not depend on successful projection. A registered source condition
is lexical containment, not a proven gameplay difference or an execution edge.
Nothing in this module writes a context package or a website file.
"""
import argparse
from bisect import bisect_left
from collections import Counter, defaultdict
import json
from pathlib import Path
import re

from .context_conditions import ROOT, backend, digest
from .context_files import Analyzer
from .context_data import catalog_payload, references
from .context_paths import paths
from .build_context_all import Sources
from .shared_cases import SharedCases

CONTROL = re.compile(r'\\C([1-4])(?!\d)')
MESSAGE = re.compile(r'(?:c_)?msg(?:set|next)(?:sub)?(?:loc)?$')
TEXT_CALLS = {'scr_text', 'c_msc', 'd_make', 'scr_readychoicer'}
ANSWER = re.compile(r'\bglobal\.choice\b')
SIGNAL = re.compile(r'global\s*\.\s*(?:choice|choicemsg|msg)\b|obj_choicer\w*|\\\\?C[1-4]|\b(?:c_)?msg(?:set|next)\w*\s*\(|\b(?:scr_text|c_msc)\s*\(')


def compact(flow, text):
    return ''.join(t.group() for t in flow.TOKEN.finditer(text)
                   if not t.group().startswith(('//', '/*')))


def walk_ui(node):
    yield node
    for child in node.get('children', []): yield from walk_ui(child)
    if 'prefix' in node: yield from walk_ui(node['prefix'])
    for branch in node.get('branches', []):
        if 'option' in branch: yield branch['option']
        yield from walk_ui(branch['body'])


def identity(chapter, name, offset, kind):
    # Position ID remains comparable for a fixed export. Every record separately
    # binds its source hash; this is not a cross-version semantic identity.
    return 'audit:' + digest(f'{chapter}/{name}/{offset}/{kind}'.encode())[:24]


def condition_category(expression):
    if ANSWER.search(expression): return 'choice_answer'
    if re.search(r'\bglobal\.flag\b|\bscr_flag_get\s*\(', expression): return 'flag'
    if re.search(r'\bscr_sideb_active\s*\(', expression): return 'sideb'
    if re.search(r'\bglobal\.', expression): return 'global_state'
    if re.search(r'\b(?:con|customcon|myinteract|talk_con)\b', expression): return 'flow_state'
    return 'other_expression'


class FileRegistry:
    def __init__(self, analyzer, name, scene=None, diagnostics=None):
        self.a, self.name = analyzer, name
        self.data = analyzer.file(name)
        self.source, self.refs = self.data['source'], self.data['refs']
        self.nodes = list(analyzer.flow.walk(self.data['nodes']))
        self.scene = scene
        self.ui = list(walk_ui(scene['body'])) if scene else []
        self.rows, self.paths, self.scopes = [], {}, {}
        self.diagnostics = diagnostics or {}
        self.newlines = [m.start() for m in re.finditer('\n', self.source)]
        self.ui_choices = [n for n in self.ui if n['type'] == 'choice']
        self.choice_options = [{r['option']['occurrence_id'] for r in n['branches']} for n in self.ui_choices]
        self.ui_conditions = defaultdict(list)
        self.ui_guards = defaultdict(list)
        self.reply_choices = []
        for n in self.ui:
            ids = None
            if n['type'] == 'condition':
                expression = compact(analyzer.flow, n['branches'][0]['label'])
                ids = {r['occurrence_id'] for r in references(n)}
                self.ui_conditions[expression].append((n, ids))
            if n.get('raw_guard'):
                ids = ids or {r['occurrence_id'] for r in references(n)}
                self.ui_guards[compact(analyzer.flow, n['raw_guard'])].append(ids)
        for n in self.ui_choices:
            self.reply_choices.append({r['occurrence_id'] for b in n['branches'] for r in references(b['body'])})
        def visit(nodes, ancestors=(), scopes=()):
            flat = analyzer.flat(nodes)
            for index, n in enumerate(flat):
                self.paths[n.start] = list(ancestors)
                self.scopes[n.start] = [*scopes, (flat, index)]
                visit(n.children, (*ancestors, (n, 'then')), (*scopes, (flat, index)))
                visit(n.other, (*ancestors, (n, 'else')), (*scopes, (flat, index)))
        visit(self.data['nodes'])

    def line(self, offset): return bisect_left(self.newlines, offset) + 1

    def refs_in(self, start, end):
        offsets = self.data['offsets']
        return self.refs[bisect_left(offsets, start):bisect_left(offsets, end)]

    def sample(self, refs):
        return {'count': len(refs), 'identity_sha256': digest('\n'.join(r['occurrence_id'] for r in refs).encode()),
                'samples': [dict(occurrence_id=r['occurrence_id'], key=r['key'], line=r['source']['line'],
                    english=(r.get('source_english') if 'binding' in r else self.a.tables.get(r['key'], {}).get('en')),
                    chinese=self.a.tables.get(r['key'], {}).get('zh_default'), binding=r.get('binding','matched')) for r in refs[:1]]}

    def row(self, kind, start, end, expression, node=None):
        ancestors = self.paths.get(node.start, []) if node else []
        return dict(id=identity(self.a.chapter, self.name, start, kind), kind=kind,
            chapter=self.a.chapter, file=self.name, source_sha256=self.data['hash'],
            source={'offset': start, 'end': end, 'line': self.line(start), 'end_line': self.line(max(start, end-1))},
            expression=expression, scope=[{'kind': n.kind, 'expression': n.text, 'arm': arm,
                'line': self.line(n.start)} for n, arm in ancestors if n.kind != 'block'],
            texts=self.sample(self.refs_in(start, end)))

    def owner(self, offset):
        return min((n for n in self.nodes if n.start <= offset < n.end),
                   key=lambda n: n.end-n.start, default=None)

    def option_candidates(self, node, count):
        if node is None or count not in (2, 3, 4): return {}
        if self.name == 'gml_GlobalScript_scr_text.gml':
            cases = [n for n, _ in self.paths.get(node.start, []) if n.kind == 'case']
            if cases:
                # Shared tables use localized single-space padding, while the
                # direct-menu resolver only accepts its own empty-slot protocol.
                found = SharedCases(self.a, self.name).options(cases[-1], count)
                if found and all(r['offset'] < node.end for r in found.values()): return found
        for flat, index in reversed(self.scopes.get(node.start, [])):
            prefix = flat[:index]
            resets = [i for i, n in enumerate(prefix) if n.kind == 'stmt'
                      and compact(self.a.flow, n.text) == 'global.choice=-1;']
            result = self.a.options(self.name, prefix[resets[-1]:] if resets else prefix, count)
            if len(result) == count: return result
        return {}

    def choice(self, start, end, text, family, call=None):
        node = self.owner(start)
        markers = [int(m[1]) for m in CONTROL.finditer(text)]
        count = markers[0] if len(markers) == 1 else None
        r = self.row('choice', start, end, text, node)
        r.update(family=family, controls=markers, option_count=count, discovery='literal_control',
                 status='unconnected', reasons=[], rule_diagnostics=[], projection_matches=[])
        if call: r['call'] = call
        options = self.option_candidates(node, count)
        r['option_candidates'] = [dict(slot=i, key=v['key'], occurrence_id=v['occurrence_id'],
            line=v['source']['line'],english=self.sample([v])['samples'][0]['english'],
            chinese=self.a.tables.get(v['key'],{}).get('zh_default')) for i, v in sorted(options.items())]
        ids = {v['occurrence_id'] for v in options.values()}
        if ids:
            r['projection_matches'] = [i for i, values in enumerate(self.choice_options) if values == ids]
        if count == 1: r['reasons'].append('inline_choice_not_supported')
        elif count is None: r['reasons'].append('multiple_controls_in_one_text')
        elif len(options) != count: r['reasons'].append('fixed_option_binding_not_found')
        line = self.line(node.start if node else start)
        for label in ('queued_menus', 'direct_menus'):
            for d in self.diagnostics.get(label, []):
                if d['prompt_line'] == line:
                    r['rule_diagnostics'].append({'rule': label, 'status': d['status'], 'reason': d['reason']})
                    if d.get('reason'): r['reasons'].append(d['reason'])
        if family == 'shared_script':
            cases = [n for n, _ in self.paths.get(node.start, []) if n.kind == 'case'] if node else []
            if cases and cases[-1].text.isdigit():
                value = int(cases[-1].text); r['shared_case'] = value
                reason = self.diagnostics.get('shared_rejections', {}).get(value)
                if reason:
                    r['rule_diagnostics'].append({'rule':'shared_case_choice','status':'unconnected','reason':reason})
                    r['reasons'].append(reason)
                # Record independent observations beyond the first blocker. They
                # describe syntax and do not claim that a proposed fix is safe.
                planner = SharedCases(self.a, self.name)
                r['observations'] = []
                for prompt, _, _, after in planner.prompts(cases[-1].children):
                    if not prompt.start <= start < prompt.end: continue
                    suffix = [planner.message(n) for n in after if planner.message(n) is not None]
                    if suffix and all(not s.strip() for s in suffix):
                        r['observations'].append('whitespace_message_slots_after_prompt')
                siblings = [n for n in self.nodes if n.kind == 'case' and n.text == str(value+1)]
                if len(siblings) == 1 and planner.prompts(siblings[0].children):
                    r['observations'].append('next_case_contains_choice_prompt')
        if len(r['projection_matches']) == 1:
            r.update(status='linked', reasons=['exact_option_occurrences_in_context_choice'])
        elif r['projection_matches']:
            r['reasons'].append('multiple_projection_sites')
        if not r['reasons']: r['reasons'] = ['no_matching_relation_rule']
        r['reasons'] = list(dict.fromkeys(r['reasons']))
        self.rows.append(r)

    def discover_choices(self):
        covered = []
        for c in self.data['calls']:
            spec = self.a.gml.FUNCTIONS.get(c['call'])
            text = None
            if spec:
                if spec[0] is not None and len(c['args']) > spec[0]:
                    text = self.a.gml.as_string_literal(c['args'][spec[0]])
                elif spec[0] is None and c['args']:
                    key = self.a.gml.as_string_literal(c['args'][spec[1]])
                    text = self.a.tables.get(key, {}).get('en')
            elif MESSAGE.fullmatch(c['call']):
                at = 1 if 'set' in c['call'] else 0
                if len(c['args']) > at: text = self.a.gml.as_string_literal(c['args'][at])
            if text and CONTROL.search(text):
                family = ('shared_script' if self.name == 'gml_GlobalScript_scr_text.gml' else
                          'queued_message' if c['call'].startswith('c_msg') else
                          'direct_message' if c['call'].startswith('msg') else 'localized_reference')
                self.choice(c['offset'], c['end'], text, family, c['call'])
                covered.append((c['offset'], c['end']))
        # Independent token pass also sees plain buffer literals, concatenations,
        # opaque callbacks, and strings outside the recognized message helpers.
        for token in self.a.flow.TOKEN.finditer(self.source):
            if any(lo <= token.start() < hi for lo, hi in covered): continue
            text = self.a.gml.as_string_literal(token.group())
            if text and CONTROL.search(text):
                node = self.owner(token.start())
                literal_assignment = bool(node and node.kind == 'stmt' and re.fullmatch(
                    r'global\.msg\[\d+\]\s*=\s*'+re.escape(token.group())+r'\s*;', node.text))
                family = ('shared_script' if literal_assignment and self.name == 'gml_GlobalScript_scr_text.gml'
                          else 'buffer_literal' if literal_assignment else 'unbound_control_literal')
                self.choice(token.start(), token.end(), text, family)
                if not literal_assignment:
                    self.rows[-1].update(status='uncertain', reasons=['control_literal_display_not_proven'])

    def relevant_calls(self, start, end):
        return [dict(call=c['call'], line=self.line(c['offset']), args=c['args'])
                for c in self.data['calls'] if start <= c['offset'] < end
                and (MESSAGE.fullmatch(c['call']) or c['call'] in TEXT_CALLS)]

    def discover_conditions(self):
        represented = {n.start for n in self.nodes if n.kind in ('if', 'switch')}
        for n in self.nodes:
            if n.kind not in ('if', 'switch'): continue
            refs = self.refs_in(n.start, n.end)
            calls = self.relevant_calls(n.start, n.end)
            clean = compact(self.a.flow, n.text)
            guard_proofs = [p for p in self.diagnostics.get('rules', []) if p['rule'] == 'passed_exit_guard'
                            and p['source']['line'] == self.line(n.start)]
            if not (refs or calls or ANSWER.search(clean) or guard_proofs): continue
            r = self.row('condition', n.start, n.end, n.text, n)
            r.update(syntax=n.kind, category=condition_category(clean), meaning='unreviewed',
                     execution='unproven', status='unresolved', reasons=[])
            branches = [('then', n.children), ('else', n.other)] if n.kind == 'if' else [(x.text, x.children) for x in n.children]
            r['branches'] = []
            ids = {x['occurrence_id'] for x in refs}
            for label, body in branches:
                lo, hi = (body[0].start, body[-1].end) if body else (n.end, n.end)
                r['branches'].append(dict(label=label, source={'offset':lo,'end':hi}, texts=self.sample(self.refs_in(lo, hi))))
            nonempty = sum(b['texts']['count'] > 0 for b in r['branches'])
            r['text_shape'] = 'multiple_text_arms' if nonempty > 1 else 'single_text_arm' if nonempty else 'no_localized_text'
            if n.kind == 'switch':
                r['reasons'] = ['switch_cases_not_execution_edges']
                if self.name == 'gml_GlobalScript_scr_text.gml': r['category'] = 'shared_dispatch'
            elif guard_proofs:
                r.update(status='represented_guard', reasons=['source_exit_guard_recorded'], evidence=guard_proofs)
            elif ids:
                matches = [(node, values) for node, values in self.ui_conditions.get(clean, []) if ids <= values]
                if matches:
                    r.update(status='represented', reasons=['lexical_condition_in_context'])
                    if any(node.get('revisit') for node, _ in matches):
                        r.update(status='represented_revisit', reasons=['local_flag_revisit_rule'])
                elif any(ids <= values for values in self.ui_guards.get(clean, [])):
                    r.update(status='represented_guard', reasons=['block_guard_in_context'])
                elif ANSWER.search(clean) and any(ids <= values for values in self.reply_choices):
                    r.update(status='represented_in_choice', reasons=['answer_text_inside_linked_choice'])
            if not r['reasons']:
                r['reasons'] = ['indirect_message_calls_not_expanded' if calls and not refs else
                                'no_localized_reply_text' if not refs else 'no_exact_condition_projection']
            r['text_calls'] = calls[:6]
            r['text_call_count'] = len(calls)
            self.rows.append(r)
        # Report conditional syntax hidden in anonymous-function statements or
        # parser failures rather than silently counting the file as covered.
        for t in self.a.flow.TOKEN.finditer(self.source):
            if t.group() not in ('if', 'switch', '?') or t.start() in represented: continue
            node = self.owner(t.start())
            if not self.refs and not SIGNAL.search(self.source): continue
            if node and not (self.a.within(self.name,node) or self.relevant_calls(node.start,node.end)
                             or ANSWER.search(compact(self.a.flow,node.text))):
                continue
            r = self.row('condition_gap', t.start(), node.end if node else t.end(),
                         (node.text[:600] if node else t.group()), node)
            r.update(status='unresolved', reasons=['ternary_not_projected' if t.group()=='?' else
                'parse_failure' if self.data['parse_error'] else 'conditional_in_opaque_scope'],
                meaning='unreviewed', execution='unproven', association='candidate_only')
            self.rows.append(r)

    def discover_signals(self):
        for n in self.nodes:
            if n.kind != 'stmt': continue
            clean = compact(self.a.flow, n.text)
            signal = None
            if re.search(r'global\.choicemsg(?:\[.*?\])?(?:=|\+=)', clean): signal='option_storage_write'
            elif ANSWER.search(clean) and not re.search(r'global\.choice=-?\d+;', clean): signal='answer_read_or_transfer'
            elif any(c['call'].startswith('instance_create') and any(re.fullmatch(r'obj_choicer\w*',arg.strip()) for arg in c['args'])
                     for c in self.a.calls(n.text)): signal='chooser_creation'
            elif any(MESSAGE.fullmatch(c['call']) and
                     self.a.gml.as_string_literal(c['args'][1 if 'set' in c['call'] else 0]) is None
                     for c in self.a.calls(n.text) if len(c['args']) > (1 if 'set' in c['call'] else 0)):
                signal='dynamic_message_argument'
            if signal:
                r=self.row('signal',n.start,n.end,n.text[:800],n)
                r.update(signal=signal,status='candidate_only',reasons=['supporting_signal_not_a_menu_count'])
                self.rows.append(r)

    def build(self):
        self.discover_choices(); self.discover_conditions(); self.discover_signals()
        # Ambiguous reuse of a label set cannot silently make two prompts green.
        claims=Counter(i for r in self.rows if r['kind']=='choice' for i in r['projection_matches'])
        for r in self.rows:
            if r['kind']=='choice' and r['status']=='linked' and any(claims[i]>1 for i in r['projection_matches']):
                r.update(status='uncertain',reasons=['multiple_prompts_claim_same_projection'])
        choices=[r for r in self.rows if r['kind']=='choice']
        for r in self.rows:
            if r['kind']!='condition':continue
            r['contained_choice_ids']=[c['id'] for c in choices if r['source']['offset']<=c['source']['offset']<r['source']['end']]
        # Expose unmatched successful projections as an audit-discovery gap.
        for i,n in enumerate(self.ui_choices):
            if claims[i]:continue
            options=[b['option'] for b in n['branches']]
            external={o['source']['file'] for o in options if o['source']['file']!=self.name}
            callbacks=[p for p in self.diagnostics.get('rules',[]) if p['rule']=='queued_choice_callback'
                       and external=={p['script']}]
            if len(callbacks)==1 and len(external)==1 and all(o['source']['file'] in external for o in options):
                proof=callbacks[0]
                r=self.row('choice_call',proof['offset'],proof['offset']+1,'c_msc('+str(proof['case'])+')')
                r.update(status='linked_at_callsite',reasons=['verified_shared_callback'],evidence=proof,
                    option_occurrences=[o['occurrence_id'] for o in options],origin_file=proof['script'],projection_index=i)
                self.rows.append(r)
                continue
            r=self.row('projection_gap',0,len(self.source),'unmapped context choice',None)
            r['id']=identity(self.a.chapter,self.name,i,'projection_gap')
            r.update(status='needs_audit_mapping',reasons=['context_choice_without_unique_source_prompt'],
                     location_precision='file_only',projection_index=i,
                     options=[dict(key=x['key'],occurrence_id=x['occurrence_id'],source=x['source']) for x in options])
            self.rows.append(r)
        owners=defaultdict(list)
        for r in self.rows:
            if r['kind']=='choice':
                for index in r['projection_matches']:owners[index].append(r['id'])
            elif r['kind']=='choice_call':owners[r['projection_index']].append(r['id'])
        for r in self.rows:
            if r['kind']!='condition':continue
            ids={x['occurrence_id'] for x in self.refs_in(r['source']['offset'],r['source']['end'])}
            r['text_contained_in_choice_ids']=list(dict.fromkeys(rid for index,reply in enumerate(self.reply_choices)
                if ids and ids<=reply for rid in owners[index]))
        return sorted(self.rows,key=lambda r:(r['source']['offset'],r['kind']))


def reconcile_calls(rows):
    """Link imported labels back to their actual source prompt, without merging uses."""
    calls=[r for r in rows if r['kind']=='choice_call']
    for c in calls:
        matches=[r for r in rows if r['kind']=='choice' and r['chapter']==c['chapter'] and r['file']==c['origin_file']
                 and {o['occurrence_id'] for o in r['option_candidates']}==set(c['option_occurrences'])]
        c['source_prompt_ids']=[r['id'] for r in matches]
        if len(matches)==1:
            r=matches[0];r.setdefault('callsite_ids',[]).append(c['id'])
            if r['status']=='unconnected':
                r.update(status='linked_at_callsite',reasons=['verified_callback_at_recorded_callsite_only'])


def summarize(rows, file_count, source_proof, context_hash, manifest_hash):
    groups=defaultdict(Counter); reasons=defaultdict(Counter); families=Counter(); categories=Counter();shapes=Counter()
    chapters=defaultdict(lambda:defaultdict(Counter))
    for r in rows:
        groups[r['kind']][r['status']]+=1
        chapters[r['chapter']][r['kind']][r['status']]+=1
        for reason in r.get('reasons',[]):reasons[r['kind']][reason]+=1
        if r['kind']=='choice':families[r['family']]+=1
        if r['kind']=='condition':categories[r['category']]+=1;shapes[r['text_shape']]+=1
    return dict(schema=1,kind='developer-context-audit',scanned_files=file_count,records=len(rows),
        scope='Known choice signals and text-related lexical conditions; not gameplay coverage or semantic accuracy.',
        context_sha256=context_hash,text_manifest_sha256=manifest_hash,
        sources_sha256=digest(json.dumps(source_proof,sort_keys=True).encode()),
        statuses={k:dict(v) for k,v in groups.items()},reasons={k:dict(v) for k,v in reasons.items()},
        choice_families=dict(families),condition_categories=dict(categories),condition_text_shapes=dict(shapes),
        chapters={ch:{k:dict(v) for k,v in kinds.items()} for ch,kinds in chapters.items()})


def compare(previous, current):
    old={r['id']:r for r in previous};new={r['id']:r for r in current}
    fields=('status','reasons','observations','option_candidates','callsite_ids','contained_choice_ids',
            'text_contained_in_choice_ids','expression')
    changed=[]
    for rid in sorted(old.keys() & new.keys()):
        before,after=old[rid],new[rid]
        differences=[f for f in fields if before.get(f)!=after.get(f)]
        rebound=before['source_sha256']!=after['source_sha256']
        if differences or rebound:
            changed.append(dict(id=rid,fields=differences,source_changed=rebound,
                                before_status=before['status'],after_status=after['status'],
                                before_reasons=before.get('reasons',[]),after_reasons=after.get('reasons',[])))
    return dict(mode='comparison',added=sorted(new.keys()-old.keys()),removed=sorted(old.keys()-new.keys()),
                changed=changed,note='Disappearing records are not automatically resolved; changed sources require rechecking.')


def report(summary, rows):
    kinds={'choice':'选择提示','condition':'文本相关条件','signal':'辅助信号','condition_gap':'条件语法缺口',
           'projection_gap':'登记映射缺口','choice_call':'共享选择调用位置','file_gap':'文件解析缺口'}
    statuses={'linked':'已连接','linked_at_callsite':'已在特定调用处连接','unconnected':'尚未连接','uncertain':'是否构成菜单尚不确定',
              'represented':'已保留源码条件','represented_guard':'已保留前置／块条件','represented_in_choice':'已纳入选择回答',
              'represented_revisit':'已标明首次／再次','unresolved':'待分析','candidate_only':'仅辅助线索',
              'needs_audit_mapping':'需要补登记映射'}
    out=['# 上下文开发审计','', f'扫描 {summary["scanned_files"]:,} 个 GML，登记 {summary["records"]:,} 条不同类型记录。', '',
         '选择入口与条件判断来自源码扫描，连接状态与现有上下文对账。此清单不进入网站。', '',
         '“已展示条件”只表示源码条件在产物中保留；不证明触发条件的剧情含义、可达性或完整执行顺序。', '',
         '| 登记类型 | 状态 | 数量 |','|---|---|---:|']
    for kind, counts in summary['statuses'].items():
        for status,count in counts.items():out.append(f'| {kinds.get(kind,kind)} | {statuses.get(status,status)} | {count:,} |')
    out+=['','## 未连接选择的阻断原因','', '| 原因 | 数量 |','|---|---:|']
    for reason,count in summary['reasons'].get('choice',{}).items():
        if reason not in ('exact_option_occurrences_in_context_choice','verified_callback_at_recorded_callsite_only'):out.append(f'| `{reason}` | {count} |')
    out+=['','原因可以并列，原因数量不能相加当作菜单总数。signal、condition_gap 和 projection_gap 单列，不混入选择题分母。', '',
          '## 每类原因的源码样本','']
    seen=set()
    for r in rows:
        if r['kind'] not in ('choice','condition_gap','projection_gap'):continue
        if r['status'] in ('linked','linked_at_callsite'):continue
        for reason in r.get('reasons',[]):
            group=(r['kind'],reason)
            if group in seen:continue
            seen.add(group)
            out.append(f'- `{reason}`：CH{r["chapter"]} `{r["file"]}` L{r["source"]["line"]}；`{r["id"]}`。')
    out+=['','## 读取与边界','',
          '- 完整登记见 `registry.jsonl`，每行一条；`sources.json` 绑定全部 GML，`summary.json` 保存计数和产物摘要。',
          '- `changes.json` 保存与 --previous 指定清单的新增、移除、状态／原因变化和源码变更；首次生成为基线，不把消失记录视为修复。',
          '- 每条有源码范围、父作用域、状态、原因；每个范围提供首条文本样本，count 与 identity_sha256 对应范围内全部本地化引用。',
          '- 同 key 的不同引用、章节副本分别登记；位置 ID 仅适用于当前导出格式，文件变化须重跑并核对。',
          '- 字面量控制串、第一章语言表控制串、选项写入、答案读取和动态消息参数均参与扫描；弱信号不等于一次菜单。',
          '- 条件范围包含本地化引用、已知消息调用、答案判断和已记录的提前退出检查。无这些信号的全局间接影响不在分母内。',
          '- switch 分块不证明无穿透；匿名函数／三元表达式／解析失败单列缺口。任意动态拼接和自定义菜单仍可能需要新增发现器。',
          '- 本批只登记，没有改变分析规则、连接关系或网站显示。','']
    return '\n'.join(out)


def build(code, texts, context, out, previous=None):
    code,texts,out=paths(code,texts,out)
    context=Path(context).resolve(strict=True)
    for source in (context,ROOT/'dist',ROOT/'web'):
        if out==source or out.is_relative_to(source) or source.is_relative_to(out):
            raise ValueError('Audit output must be separate from context and website directories')
    previous_rows=None
    if previous is not None:
        previous=Path(previous).resolve(strict=True)
        if previous==out or previous.is_relative_to(out) or out.is_relative_to(previous):
            raise ValueError('Previous audit must be a separate snapshot')
        previous_rows=[json.loads(s) for s in (previous/'registry.jsonl').read_text(encoding='utf-8').splitlines()]
    manifest=(texts/'manifest.json').read_bytes()
    tables={ch:{r['key']:r for r in json.loads((texts/f'trilingual_chapter{ch}.json').read_text(encoding='utf-8'))['lines']} for ch in range(1,6)}
    catalog_payload(context,manifest,tables)
    proof=json.loads((context/'evidence.json').read_text(encoding='utf-8'))
    if proof['contexts_sha256']!=digest((context/'contexts.json').read_bytes()):raise ValueError('Stale context evidence')
    # Validate every input, including helpers and files without localized text.
    sources_proof={f'ch{ch}/'+p.name:digest(p.read_bytes()) for ch in range(1,6) for p in sorted((code/f'ch{ch}').glob('*.gml'))}
    if sources_proof!=proof['sources']:raise ValueError('GML snapshot differs from context build; rebuild context first')
    rows=[];api=backend();file_count=0
    for ch in range(1,6):
        sources=Sources(code/f'ch{ch}');a=Analyzer(sources,ch,tables[ch],api,sources.hashes,strict_bindings=False)
        index=json.loads((context/f'index-ch{ch}.json').read_text(encoding='utf-8'))
        files={m['file']:m for m in index['files']}
        rules=defaultdict(list)
        for r in proof['rules']:
            if r['chapter']==ch:rules[r['file']].append(r)
        for name in sources:
            source=sources[name];file_count+=1
            if name not in files and not SIGNAL.search(source):sources.loaded.pop(name,None);continue
            data=a.file(name);scene=None
            if name in files:
                scene=json.loads((context/files[name]['path']).read_text(encoding='utf-8'))['scenes'][0]
            # Re-run relation diagnostics in memory. Never write generated data.
            fresh=a.analyze(name)
            if scene is not None and fresh!=scene:raise ValueError('Analyzer and context differ: '+name+'; rebuild context first')
            diagnostics={'rules':rules[name],'queued_menus':a.queue_audit,'direct_menus':a.direct_audit,
                         'shared_rejections':dict(a.shared_rejections)}
            registry=FileRegistry(a,name,scene,diagnostics)
            rows.extend(registry.build())
            if data['parse_error']:
                r=registry.row('file_gap',0,len(source),'')
                r.update(status='unresolved',reasons=['parse_failure'],detail=data['parse_error']);rows.append(r)
            if name!='gml_GlobalScript_scr_text.gml':a.cache.pop(name,None)
            sources.loaded.pop(name,None)
        print(f'CH{ch}: {len(rows):,} cumulative audit records',flush=True)
    reconcile_calls(rows)
    if len({r['id'] for r in rows})!=len(rows):raise ValueError('Duplicate audit identities')
    summary=summarize(rows,file_count,sources_proof,digest((context/'contexts.json').read_bytes()),digest(manifest))
    summary['audit_tool_sha256']=digest(Path(__file__).read_bytes())
    changes=compare(previous_rows,rows) if previous_rows is not None else {'mode':'initial_baseline'}
    summary['changes']={k:len(v) for k,v in changes.items() if isinstance(v,list)}
    out.mkdir(parents=True,exist_ok=True)
    with (out/'registry.jsonl').open('w',encoding='utf-8',newline='\n') as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
    for name,value in [('summary.json',summary),('sources.json',sources_proof),('changes.json',changes)]:
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'review.md').write_text(report(summary,rows),encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--code',type=Path,required=True)
    p.add_argument('--texts',type=Path,default=ROOT/'build/texts')
    p.add_argument('--context',type=Path,default=ROOT/'local/context-all')
    p.add_argument('--out',type=Path,default=ROOT/'build/context-audit')
    p.add_argument('--previous',type=Path,help='Optional separate audit snapshot to compare')
    args=p.parse_args();build(args.code,args.texts,args.context,args.out,args.previous)
