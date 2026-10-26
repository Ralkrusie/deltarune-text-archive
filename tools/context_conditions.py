"""Local source-bound conditional containment shared by the context pipeline.

This module does not load legacy project code or claim an execution graph.
The historical C1 build entry point lives in legacy_context_conditions.py.
"""
import hashlib
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def backend(legacy=None):
    # Optional argument retained only for historical C1/C2 entry-point compatibility.
    # It never modifies sys.path or loads code from that directory.
    from context_parser import font_flow, gml_dialogue, attribution_schema
    from context_parser.calls import _calls
    return font_flow, gml_dialogue, attribution_schema, _calls


def analyze(source, chapter, path, source_hash, texts, api, excluded=()):
    flow,gml,schema,calls=api
    refs=[]
    for c in calls(source):
        spec=gml.FUNCTIONS.get(c['call'])
        if not spec or spec[1] is None or not c['args']:continue
        key=gml.as_string_literal(c['args'][-1])
        if key is None or not gml.KEY_RE.fullmatch(key):continue
        en=gml.as_string_literal(c['args'][spec[0]]) if spec[0] is not None else None
        table=texts.get(key,{})
        refs.append(dict(occurrence_id=schema.occurrence_id(chapter,'canonical',path,source_hash,key,c['offset'],c['call']),
            key=key,offset=c['offset'],line=source.count('\n',0,c['offset'])+1,call=c['call'],
            source_english=en,texts={k:table.get(k) for k in ('en','ja','zh_default')},
            text_binding='missing_key' if not table else 'source_literal_differs' if en is not None and en!=table.get('en') else 'matched',
            excluded_by=[r['review_id'] for r in excluded if r['start']<=c['offset']<r['end']],
            guards=[],node_id=None,usage='reference_only_not_proven_display'))
    errors=[]
    try:nodes=flow.parse(source)
    except (ValueError,IndexError,RecursionError) as e:
        nodes=[];errors.append(dict(reason='parse_error',detail=str(e)))
    tree=[]
    def visit(n,guards):
        nid=f'n{n.start}'
        item=dict(id=nid,kind=n.kind,start=n.start,end=n.end,line=source.count('\n',0,n.start)+1,
                  expression=n.text,refs=[],children=[],other=[])
        if n.kind=='if':
            item['semantic_kind']='raw_condition_meaning_unreviewed'
            item['children']=[visit(c,guards+[dict(node_id=nid,expression=n.text,branch='then')]) for c in n.children]
            item['other']=[visit(c,guards+[dict(node_id=nid,expression=n.text,branch='else')]) for c in n.other]
        elif n.kind=='switch':
            item['semantic_kind']='switch_control_flow_unresolved'
            # Case containment alone is not a guard: earlier cases can fall through.
            item['children']=[visit(c,guards) for c in n.children]
            errors.append(dict(node_id=nid,reason='switch_fallthrough_not_solved'))
        elif n.kind in ('while','for','repeat','with','function'):
            item['children']=[visit(c,guards) for c in n.children]
            item['scope_status']='execution_or_entry_not_solved'
            errors.append(dict(node_id=nid,reason=n.kind+'_scope_not_executed'))
        else:
            item['children']=[visit(c,guards) for c in n.children]
            item['other']=[visit(c,guards) for c in n.other]
        # Attach only to the deepest enclosing syntax node; identical keys stay distinct.
        occupied=[(c.start,c.end) for c in n.children+n.other]
        for ref in refs:
            if n.start<=ref['offset']<n.end and not any(a<=ref['offset']<b for a,b in occupied):
                ref.update(node_id=nid,guards=guards)
                item['refs'].append(ref['occurrence_id'])
        if n.kind=='stmt':
            assignment=flow.assignments(n.text)
            item['assignment']=list(assignment) if assignment else None
            item['calls']=[dict(call=c['call'],arguments=c['args'],offset=c['offset']) for c in calls(n.text,n.start)]
            item['terminal']=n.text.strip().split(';')[0] if n.text.strip() in ('break;','return;','exit;') else None
        return item
    tree=[visit(n,[]) for n in nodes]
    if any(r['node_id'] is None for r in refs):errors.append(dict(reason='unattached_references_retained'))
    return dict(schema='context-conditions-1',chapter=chapter,path=path,source_sha256=source_hash,
        relationship='lexical_conditional_containment',execution_order='unproven',
        blocks=tree,references=refs,diagnostics=errors,edges=[],
        limitations=['Conditions are evaluated at their source locations, not necessarily on entry.',
            'Sibling if statements are independent and can overwrite the same message slot.',
            'Reference construction does not prove display; state progression, choice mapping, joins and callees are unresolved.'])


def render(bundle):
    refs={r['occurrence_id']:r for r in bundle['references']}
    def gap(n):
        return n.get('terminal') or (not n['refs'] and any(c['call'] in ('msgset','msgnext','scr_text','c_msgset','c_msgnext') for c in n.get('calls',[])))
    def node(n):
        descendants=n['children']+n['other']
        interesting=bool(n['refs']) or gap(n) or any(hasrefs(c) for c in descendants)
        if not interesting:return ''
        label=(('满足：' if n['kind']=='if' else n['kind']+'：')+n['expression']) if n['kind']!='block' else '局部块'
        if n['kind']=='stmt':label='文本引用／写入（尚未证明最终显示）'
        if gap(n):label='退出／动态或共享消息调用：保留原句，未展开'
        body='<section><p><code>'+html.escape(label)+'</code> · L'+str(n['line'])+'</p>'
        if n['kind']=='stmt':body+='<details><summary>原始语句</summary><pre>'+html.escape(n['expression'])+'</pre></details>'
        for rid in n['refs']:
            r=refs[rid]
            body+='<article><small>'+html.escape(r['key'])+'</small><pre>'+html.escape(r['texts']['en'] or r['source_english'] or '〔英文缺失〕')+'</pre><pre>'+html.escape(r['texts']['zh_default'] if r['texts']['zh_default'] is not None else '〔中文缺失〕')+'</pre>'
            if r['excluded_by']:body+='<strong>已有不可达审阅：'+html.escape(', '.join(r['excluded_by']))+'</strong>'
            if r['text_binding']!='matched':body+='<strong>语言表绑定：'+html.escape(r['text_binding'])+'</strong>'
            body+='</article>'
        body+=''.join(node(c) for c in n['children'])
        if n['other'] and any(hasrefs(c) for c in n['other']):
            body+='<p><b>否则：不满足 '+html.escape(n['expression'])+'</b></p>'+''.join(node(c) for c in n['other'])
        return body+'</section>'
    def hasrefs(n):return bool(n['refs']) or gap(n) or any(hasrefs(c) for c in n['children']+n['other'])
    return '<h2>CH'+str(bundle['chapter'])+' · '+html.escape(Path(bundle['path']).name)+'</h2><p>以下顶层块分别审阅，块间没有对话连线；显示顺序仅为源码位置。</p>'+''.join(node(n) for n in bundle['blocks'])
