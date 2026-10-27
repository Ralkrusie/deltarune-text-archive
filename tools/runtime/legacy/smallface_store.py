"""Bound child-message evidence; runtime instance IDs and phases never define variants."""
import hashlib
import json
import math
from pathlib import Path
from .store import canonical

SPEC_TEXT=Path(__file__).with_name('smallface-spec.json').read_text(encoding='utf-8')
SPEC=json.loads(SPEC_TEXT)
SPEC_SHA=hashlib.sha256(SPEC_TEXT.encode()).hexdigest()


def validate_smallfaces(header, entry, detail, sources):
    if 'smallfaces' not in detail:
        if header.get('smallface_schema')==1:raise ValueError('Missing smallface observations')
        return
    if header.get('smallface_schema')!=1 or header.get('smallface_spec_sha256')!=SPEC_SHA:
        raise ValueError('Unbound smallface mechanism')
    children=detail['smallfaces']
    if not isinstance(children,list) or len(children)>32:raise ValueError('Unbounded smallfaces')
    def number(v):return type(v) in (int,float) and math.isfinite(v)
    def integer(v,lo,hi):return number(v) and int(v)==v and lo<=v<=hi
    for i,c in enumerate(children):
        if c.get('ordinal')!=i or c.get('parent_message_id')!=entry['message_id']:
            raise ValueError('Cross-message child binding')
        if not integer(c.get('anchor_index'),1,len(detail['formatted_text'])) or not integer(c.get('slot'),0,9):
            raise ValueError('Invalid smallface anchor')
        start=int(c['anchor_index'])-1
        if detail['formatted_text'][start:start+3]!='\\f'+str(int(c['slot'])):
            raise ValueError('Smallface does not match consumed control')
        if c.get('source_id')!=0 and (c.get('source_id') not in sources or sources[c['source_id']].get('channel')!='smallface'):
            raise ValueError('Unknown/wrong-channel smallface source')
        if not isinstance(c.get('text'),str) or not (isinstance(c.get('selector'),str) or number(c.get('selector'))):
            raise ValueError('Invalid child content/selector')
        if any(not number(c.get(k)) for k in ('configured_sprite_id','configured_frame','image_speed','initial_x','initial_y','entry_speed','entry_direction','alarm_steps','draw_events')):
            raise ValueError('Invalid child configuration')
        if type(c.get('overflow')) is not bool or (c['overflow'] and not detail['overflow']):raise ValueError('Invalid child overflow')
        for key,limit in [('sprites',128),('text_states',64),('samples',8)]:
            if not isinstance(c.get(key),list) or len(c[key])>limit:raise ValueError('Unbounded child '+key)
        for a in c['sprites']:
            if not isinstance(a.get('sprite_name'),str) or a.get('pass') not in ('gui','world'):
                raise ValueError('Invalid smallface sprite')
            if not integer(a.get('frame_count'),1,100000) or not integer(a.get('subimage'),0,a['frame_count']-1):
                raise ValueError('Invalid child sprite frame')
            if any(not number(a.get(k)) for k in ('sprite_id','scale_x','scale_y','rotation','blend')):raise ValueError('Invalid child sprite transform')
        for s in c['text_states']:
            if (s.get('site') not in (1,2,3) or s.get('pass') not in ('world','gui') or not integer(s.get('color_bgr'),0,0xffffff)
                or any(not isinstance(s.get(k),str) for k in ('text','rendered_text','font_name'))
                or type(s.get('complete_text_drawn')) is not bool):raise ValueError('Invalid child text state')
            if s.get('motion')!=('random_xy_1' if s['site']==3 else 'none'):raise ValueError('Wrong child motion recipe')


def smallface_body(header,inventory,detail):
    if not detail or 'smallfaces' not in detail:return {}
    sources={s['source_id']:s for s in inventory['sources']}
    children=[]
    for child in detail['smallfaces']:
        c={k:v for k,v in child.items() if k not in ('parent_message_id','samples','draw_events')}
        c['sprites']=[json.loads(s) for s in sorted({canonical(s) for s in c['sprites']})]
        c['text_states']=[json.loads(s) for s in sorted({canonical(s) for s in c['text_states']})]
        src=sources.get(c['source_id']);c['occurrence_id']=src['occurrence_id'] if src else None
        c['binding']='propagated_source_tag' if src else 'unmatched'
        c['source_key']=src['key'] if src else None
        candidate=SPEC['selectors'].get(c['selector']) if isinstance(c['selector'],str) else None
        consistent=all(a['sprite_id']==c['configured_sprite_id'] for a in c['sprites'])
        c['identity']={'status':'helper_selector_evidence' if candidate and consistent else 'unknown',
            'candidates':[candidate] if candidate and consistent else [],'not_inherited_from_parent':True}
        c['coverage']={'sprite_drawn':bool(c['sprites']),'text_drawn':bool(c['text_states']),
            'all_observed_text_states_complete':bool(c['text_states']) and all(s['complete_text_drawn'] for s in c['text_states']),
            'text_changed_after_creation':any(s['text']!=c['text'] for s in c['text_states'])}
        children.append(c)
    return {'smallface_spec_sha256':header['smallface_spec_sha256'],'smallfaces':children}


def smallface_summary(body):
    if 'smallfaces' not in body:return 'smallface：旧记录未采集。'
    if not body['smallfaces']:return 'smallface：本页没有记录到附属实例。'
    parts=[]
    for c in body['smallfaces']:
        name=', '.join(c['identity']['candidates']) or '人物未知'
        coverage=c['coverage']
        status='已画出完整文字' if coverage['all_observed_text_states_complete'] else '文字部分显示' if coverage['text_drawn'] else '未观察到文字绘制'
        assets=', '.join(f"{a['sprite_name']}[{int(a['subimage'])}]" for a in c['sprites']) or '未观察到贴图'
        parts.append(f"插话 {int(c['ordinal'])+1} · {name} · {status} · {assets}\n{c['text']}\n来源：{c['source_key'] or '未绑定'}；主句字符位置 {int(c['anchor_index'])}")
    return '\n\n'.join(parts)
