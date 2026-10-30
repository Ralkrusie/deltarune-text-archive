"""Compare context catalogs and write a local review of every changed file."""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
from urllib.parse import urlencode

from .context_data import references
from .summarize_context import summarize


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def menus(node, parents=()):
    if node['type'] == 'choice':
        identity = tuple(b['option']['occurrence_id'] for b in node['branches'])
        yield identity, node, parents
        parents = (*parents, identity)
    for child in node.get('children', []):
        yield from menus(child, parents)
    if node.get('prefix'):
        yield from menus(node['prefix'], parents)
    for branch in node.get('branches', []):
        yield from menus(branch['body'], parents)


def compare(before, after):
    a, b = summarize(before), summarize(after)
    proof_a, proof_b = read(before/'evidence.json'), read(after/'evidence.json')
    if a['text_manifest_sha256'] != b['text_manifest_sha256']:
        raise ValueError('Compare catalogs bound to the same text input')
    changed = []
    for ch in range(1, 6):
        old = {r['file']: r for r in read(before/f'index-ch{ch}.json')['files']}
        new = {r['file']: r for r in read(after/f'index-ch{ch}.json')['files']}
        if old.keys() != new.keys():
            raise ValueError('Source file inventory changed')
        for name in old:
            raw_a, raw_b = (before/old[name]['path']).read_bytes(), (after/new[name]['path']).read_bytes()
            if raw_a == raw_b:
                continue
            sa, sb = json.loads(raw_a)['scenes'][0], json.loads(raw_b)['scenes'][0]
            # Option slots become option cards rather than generic references.
            # Display usage may change; source identity and text binding may not.
            inventory = lambda s: Counter(json.dumps({k:v for k,v in r.items() if k not in ('usage','entry_guards')}, sort_keys=True)
                                          for r in references(s['body']))
            if inventory(sa) != inventory(sb):
                raise ValueError('Reference identity/content changed: '+name)
            def guards(n, inherited=()):
                active=tuple(sorted(set(inherited)|{json.dumps(g,sort_keys=True) for g in n.get('entry_guards',[])}))
                if n['type']=='message':yield n['occurrence_id'],active
                for c in n.get('children',[]):yield from guards(c,active)
                if n.get('prefix'):yield from guards(n['prefix'],active)
                for branch in n.get('branches',[]):
                    if branch.get('option'):yield from guards(branch['option'],active)
                    yield from guards(branch['body'],active)
            if Counter(guards(sa['body'])) != Counter(guards(sb['body'])):
                raise ValueError('Source entry conditions changed: '+name)
            ma = {k: (n, p) for k, n, p in menus(sa['body'])}
            mb = {k: (n, p) for k, n, p in menus(sb['body'])}
            changes = []
            for identity in sorted(ma.keys() | mb.keys()):
                na, pa = ma.get(identity, (None, ()))
                nb, pb = mb.get(identity, (None, ()))
                if na == nb and pa == pb:
                    continue
                kind = 'added' if na is None else 'removed' if nb is None else 'modified' if na != nb else 'moved'
                keys = [branch['option']['key'] for branch in (nb or na)['branches']]
                current = next((r for r in proof_b['queued_menus'] if r['chapter']==ch
                                and r['file']==name and r.get('option_keys')==keys), None)
                prior = next((r for r in proof_a['queued_menus'] if r['chapter']==ch and r['file']==name
                              and (r.get('option_keys')==keys or current and r['prompt_line']==current['prompt_line'])), None)
                changes.append({'kind': kind, 'keys': keys, 'before': na, 'after': nb,
                                'parent_choices_before': pa, 'parent_choices_after': pb,
                                'audit_before': prior, 'audit_after': current})
            changes.sort(key=lambda r: (r['after'] or r['before'])['branches'][0]['option']['source']['line'])
            changed.append({'chapter': ch, 'file': name, 'before': sa, 'after': sb, 'menus': changes})
    routes=lambda proof:{json.dumps(r,sort_keys=True):r for r in proof['rules'] if r['rule']=='queued_state_continuation'}
    routes_a,routes_b=routes(proof_a),routes(proof_b)
    candidates=lambda proof:{(r['chapter'],r['file'],r['prompt_line']):r for r in proof['queued_menus']}
    candidates_a,candidates_b=candidates(proof_a),candidates(proof_b)
    queued=[{'chapter':k[0], 'file':k[1], 'prompt_line':k[2],
             'before':candidates_a.get(k), 'after':candidates_b.get(k)}
            for k in sorted(candidates_a.keys() | candidates_b.keys())]
    return {'before': {'totals': a['totals'], 'choices': a['choices']},
            'after': {'totals': b['totals'], 'choices': b['choices']},
            'reference_inventory_preserved': True, 'changed_files': changed,
            'queued_candidates': queued,
            'state_continuations': {'added':[routes_b[k] for k in sorted(routes_b.keys()-routes_a.keys())],
                                    'removed':[routes_a[k] for k in sorted(routes_a.keys()-routes_b.keys())]},
            'menu_changes': dict(Counter(r['kind'] for f in changed for r in f['menus']))}


STYLE = '''body{font:17px/1.65 system-ui,sans-serif;background:#111;color:#eee;max-width:1200px;margin:35px auto;padding:0 24px}
a{color:#9ed3ff}h1{font-size:26px}h2{font-size:21px}h3{font-size:18px}small,summary,.note{color:#bbb}
article,section.menu{border:1px solid #555;padding:16px;margin:16px 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit}
code{overflow-wrap:anywhere;font-size:13px}details{margin:14px 0}summary{cursor:pointer}.choice{border-left:3px solid #99bde4;padding:0 16px;margin:20px 0}
table{border-collapse:collapse;width:100%;font-size:14px}td,th{border:1px solid #555;padding:8px;text-align:left;overflow-wrap:anywhere}td:first-child{max-width:350px}
.branches{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.branch .branches{grid-template-columns:1fr}.branch{min-width:0}
.block{border-top:1px solid #555;margin-top:28px}.condition{background:#242424;padding:8px}
@media(max-width:750px){.branches{grid-template-columns:1fr}}'''


def write_review(result, texts, out, site):
    tables = {ch: {r['key']: r for r in read(texts/f'trilingual_chapter{ch}.json')['lines']} for ch in range(1, 6)}
    escape = html.escape
    formatter = (Path(__file__).resolve().parents[2]/'web/text.js').read_text(encoding='utf-8')
    script = '<script>'+formatter.replace('</script', '<\\/script')+'''</script><script>
for(const e of document.querySelectorAll('pre[data-chapter]'))e.textContent=DialogueText.format(e.textContent,Number(e.dataset.chapter)).plain??e.textContent;
</script>'''

    def page(title, body):
        return '<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+escape(title)+'</title><style>'+STYLE+'</style><body><h1>'+escape(title)+'</h1>'+body+script+'</body></html>'

    def ref(r, ch):
        row = tables[ch].get(r['key'], {})
        text = '<small>中文</small><pre data-chapter="'+str(ch)+'">'+escape(row.get('zh_default') or '（无中文）')+'</pre>'
        text += '<details><summary>英文／日文原文</summary>' + ''.join('<pre>'+escape(row.get(lang) or '')+'</pre>' for lang in ('en', 'ja'))+'</details>'
        return '<article>'+text+'<code>'+escape(r['key'])+'</code><div class="note">L'+str(r['source']['line'])+' · '+escape(r['source']['file'])+'</div></article>'

    def node(n, ch):
        if n['type']=='message':
            return ref(n, ch)
        if n['type']=='jump':
            return '<p><a href="'+jump_base+'#'+escape(n['target'],quote=True)+'">'+escape(n['label'])+'</a></p>'
        if n.get('branches'):
            parts = []
            for branch in n['branches']:
                label = ref(branch['option'], ch) if branch.get('option') else '<p class="condition">'+escape(branch.get('label', ''))+'</p>'
                parts.append('<div class="branch">'+label+node(branch['body'], ch)+'</div>')
            prefix = node(n['prefix'], ch) if n.get('prefix') else ''
            automatic = n.get('auto_answer')
            notice = '<p>'+escape(automatic['condition'])+' → 选项 '+str(automatic['option']+1)+'</p>' if automatic else ''
            return '<div class="choice"><h3>'+('玩家选择' if n['type']=='choice' else '条件')+'</h3>'+notice+prefix+'<div class="branches">'+''.join(parts)+'</div></div>'
        anchor = ' id="'+escape(n['anchor'],quote=True)+'"' if n.get('anchor') else ''
        return '<div'+anchor+' class="'+('block' if n['type']=='block' else '')+'">'+escape(n.get('label', ''))+''.join(node(c, ch) for c in n.get('children', []))+'</div>'

    changes = result['menu_changes']
    parts = ['<p>选择关系：'+str(result['before']['choices']['menus'])+' → '+str(result['after']['choices']['menus'])+
             '。变化文件 '+str(len(result['changed_files']))+' 个；新增 '+str(changes.get('added',0))+' 题，移除 '+str(changes.get('removed',0))+
             ' 题，原题内容变化 '+str(changes.get('modified',0))+' 题，原题所属父选择变化 '+str(changes.get('moved',0))+' 题。</p>',
             '<p>源码引用与原文保持。下方列出全部新增／修改／移动关系；完整文件前后版另列。此页是开发审查材料。</p>']
    number = 0
    for index, item in enumerate(result['changed_files'], 1):
        ch = item['chapter']
        parts.append('<h2>CH'+str(ch)+' · '+escape(item['file'])+'</h2>')
        for version in ('before', 'after'):
            name = f'file-{index}-{version}.html'
            jump_base = ''
            (out/name).write_text(page(item['file']+' · '+version, '<a href="index.html">返回清单</a>'+node(item[version]['body'], ch)), encoding='utf-8')
            parts.append('<a href="'+name+'">'+('修改前完整文件' if version=='before' else '修改后完整文件')+'</a>　')
        routes=result.get('state_continuations',{})
        for change, label in (('added','新增状态续接'),('removed','移除状态续接')):
            rows=[r for r in routes.get(change,[]) if r['chapter']==ch and r['file']==item['file']]
            if rows:
                parts.append('<h3>'+label+'</h3><ul>')
                for r in sorted(rows,key=lambda r:r['write_line']):
                    parts.append('<li>L'+str(r['write_line'])+' → L'+str(r['target_line'])+
                                 ' · con = '+escape(r['state'])+' · '+('共享落点' if r['shared'] else '并入当前分支')+'</li>')
                parts.append('</ul>')
        jump_base = f'file-{index}-after.html'
        for change in item['menus']:
            number += 1
            kind = {'added':'新增连接', 'removed':'移除连接', 'modified':'关系内容变化', 'moved':'已有追问放回父选择内'}[change['kind']]
            query = urlencode({'q':change['keys'][0], 'ch':ch, 'lang':'zh', 'mode':'plain', 'zh':'default'})
            parts.append(f'<section class="menu" id="change-{number}"><h3>{number}. {kind}</h3><a href="'+escape(site+'/?'+query)+'" target="_blank">在本地网页查看</a>')
            prior, current = change['audit_before'] or {}, change['audit_after'] or {}
            parts.append('<p class="note">之前：'+escape(prior.get('reason') or prior.get('status') or '见完整文件')+'；现在：'+escape(current.get('status') or kind)+'</p>')
            if change['kind']=='moved':
                parts.append('<p>这道追问原有的选项和回答内容保持；本次补上其外层选择关系。</p>')
            parts.append(node(change['after'] or change['before'], ch))
            for field,label in (('prefix_review','前置附属工作与局部回调'),('response_review','回答中的附属工作与局部回调')):
                if not current.get(field):continue
                parts.append('<details><summary>'+label+'（'+str(len(current[field]))+' 处）</summary>')
                for entry in current[field]:
                    parts.append('<p>L'+str(entry['line'])+' · '+escape(entry['previous_reason'] or '')+'</p><pre>'+escape(entry['statement'])+'</pre>')
                    if entry.get('scope')=='local_callback_body':
                        parts.append('<p class="note">已检查这段回调中的赋值和调用；创建对象的后台事件未展开。</p>')
                    if entry.get('scope')=='unexpanded_common_tail':
                        parts.append('<p class="note">公共后段保持独立源码块；未证明其中动画、退出或后续状态的执行关系。</p>')
                parts.append('</details>')
            parts.append('</section>')
    candidates=result.get('queued_candidates',[])
    parts.append('<h2>全部队列菜单候选（'+str(len(candidates))+' 处）</h2>'
                 '<p>包含本轮没有变化的候选；停止原因是当前检查遇到的第一处障碍，修掉它后仍可能遇到下一处。'
                 '这是已发现的显式队列菜单范围，不是全部游戏选择题。</p>')
    status=lambda r: '未登记' if r is None else '已连接' if r['status']=='connected' else '已有关系覆盖' if r.get('reason')=='existing_relation_scope' else r.get('reason') or r['status']
    reasons=Counter(status(r['after']) for r in candidates)
    parts.append('<ul>'+''.join('<li>'+escape(reason)+'：'+str(count)+'</li>' for reason,count in reasons.most_common())+'</ul>')
    parts.append('<table><thead><tr><th>文件与提示位置</th><th>之前</th><th>现在</th></tr></thead><tbody>')
    for row in candidates:
        parts.append('<tr><td>CH'+str(row['chapter'])+' · <code>'+escape(row['file'])+'</code> · L'+str(row['prompt_line'])+'</td><td>'+
                     escape(status(row['before']))+'</td><td>'+escape(status(row['after']))+'</td></tr>')
    parts.append('</tbody></table>')
    (out/'index.html').write_text(page('上下文改动审查', ''.join(parts)), encoding='utf-8')


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('before', 'after', 'texts', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--site', default='http://127.0.0.1:8800')
    args = parser.parse_args()
    out = args.out.resolve()
    if any(out==p.resolve() or out.is_relative_to(p.resolve()) or p.resolve().is_relative_to(out) for p in (args.before,args.after,args.texts)):
        raise ValueError('Review output must be separate from inputs')
    result = compare(args.before, args.after)
    out.mkdir(parents=True, exist_ok=True)
    (out/'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    write_review(result, args.texts, out, args.site.rstrip('/'))
    print(json.dumps({'changed_files':len(result['changed_files']), 'menus':result['menu_changes']}, ensure_ascii=False))
