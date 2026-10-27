"""Independent choice stream. Join only version-bound message IDs and explicit continuations."""
import argparse
from collections import Counter
import hashlib
import html
import json
from pathlib import Path
import sqlite3

from .interaction_store import read_lines, integer, prepare as prepare_interactions
from .store import canonical, resolve_sources


def prepare(log, messages, sources):
    rows,tail=read_lines(log)
    main,main_tail=read_lines(messages)
    if not rows or not main:raise ValueError('Missing complete choice/header')
    h=rows[0]
    if h.get('kind')!='header' or h.get('schema')!=1:raise ValueError('Invalid choice header')
    for key in ('session_id','run_id','source_manifest','collector_sha256','mode'):
        if h.get(key)!=main[0].get(key):raise ValueError('Choice provenance mismatch: '+key)
    if h['mode'] not in ('natural_play_pilot','mechanism_selftest'):raise ValueError('Invalid mode')
    inv=json.loads(resolve_sources(sources,h['source_manifest']).read_text(encoding='utf-8'))
    by_source={r['source_id']:r for r in inv['sources']}
    entries={r['message_id']:r for r in main if r['kind']=='observation'}
    ix=log.with_name(log.name.replace('choices_','interactions_',1))
    interactions=prepare_interactions(ix,messages,sources)[2] if ix!=log and ix.exists() else {}
    choices,links={},{}

    def source(sid):
        if not integer(sid) or sid and (sid not in by_source or by_source[sid].get('channel')!='choice_option'):
            raise ValueError('Invalid choice option source')

    def options(values,count,kind):
        if not isinstance(values,list) or len(values)!=count:raise ValueError('Wrong option count')
        for i,v in enumerate(values):
            if v.get('slot')!=i or not isinstance(v.get('text'),str):raise ValueError('Invalid option')
            source(v.get('source_id'))
            if kind=='old' and (v['source_id'] or v['text'] or v.get('text_status')!='embedded_in_parent_not_split'):
                raise ValueError('Legacy options must not borrow choicemsg')
            if kind=='neo' and v.get('text_status')!='configured_option':raise ValueError('Invalid option status')

    for seq,r in enumerate(rows,1):
        if r.get('seq')!=seq or not isinstance(r.get('io_failed'),bool):raise ValueError('Invalid choice sequence')
        if seq==1:continue
        cid=r.get('choice_id')
        if not integer(cid):raise ValueError('Invalid choice ID')
        kind=r.get('kind')
        if kind=='choice_open':
            if cid!=len(choices)+1:raise ValueError('Repeated choice')
            e=entries.get(r.get('parent_message_id'))
            if e is None or e['writer_id']!=r.get('parent_writer_id'):raise ValueError('Invalid choice parent')
            if r.get('selector_type') not in ('old','neo'):raise ValueError('Invalid selector')
            count=len(r.get('options',[]))
            if count not in (2,3,4) or r['selector_type']=='old' and count!=2:raise ValueError('Invalid choice count')
            options(r['options'],count,r['selector_type'])
            if not integer(r.get('interaction_id')) or r['interaction_id'] and r['interaction_id'] not in interactions:
                raise ValueError('Unknown interaction')
            choices[cid]={'open':r,'draws':[],'confirm':None,'end':None}
        elif kind=='message_link':
            mid=r.get('message_id');e=entries.get(mid)
            if e is None or mid in links:raise ValueError('Invalid/repeated choice message')
            if any(r.get(k)!=e.get(k) for k in ('source_id','writer_id','page')):raise ValueError('Cross-message choice link')
            if cid and (cid not in choices or choices[cid]['confirm'] is None):raise ValueError('Continuation without confirmation')
            if r.get('relation')!=('explicit_choice_continuation' if cid else 'no_proven_choice'):raise ValueError('Invalid choice relation')
            links[mid]=r
        else:
            if cid not in choices:raise ValueError('Unknown choice')
            c=choices[cid];count=len(c['open']['options']);selector=c['open']['selector_type']
            if c['end'] is not None:raise ValueError('Choice changed after end')
            if kind=='choice_draw':
                v=r.get('state',{})
                if selector!='neo' or not integer(v.get('slot')) or v['slot']>=count:raise ValueError('Invalid option draw slot')
                if any(not isinstance(v.get(k),str) for k in ('text','rendered_text','font_name')):raise ValueError('Invalid option draw text')
                if not isinstance(v.get('selected'),bool) or not integer(v.get('font_id'),-1) or not integer(v.get('color_bgr')):raise ValueError('Invalid option style')
                source(v.get('source_id'))
                if len(c['draws'])>=128:raise ValueError('Choice state limit exceeded')
                c['draws'].append(r)
            elif kind=='choice_confirm':
                if c['confirm'] is not None or not integer(r.get('selected_slot')) or r['selected_slot']>=count:raise ValueError('Invalid/repeated confirmation')
                options(r['options'],count,selector)
                if r.get('observed_states')!=len(c['draws']):raise ValueError('Wrong confirmed draw count')
                c['confirm']=r
            elif kind=='choice_end':
                selected=-1 if c['confirm'] is None else c['confirm']['selected_slot']
                if r.get('selected_slot')!=selected or not isinstance(r.get('overflow'),bool):raise ValueError('Invalid choice ending')
                c['end']=r
            else:raise ValueError('Unsupported choice event')
    summary=dict(choices=len(choices),confirmed=sum(c['confirm'] is not None for c in choices.values()),
        linked_messages=sum(bool(r['choice_id']) for r in links.values()),unlinked_messages=sum(not r['choice_id'] for r in links.values()),
        missing_links=len(entries.keys()-links.keys()),unclosed_choices=sum(c['end'] is None for c in choices.values()),
        tail_incomplete=tail or main_tail,io_failed=any(r['io_failed'] for r in rows),
        overflow=sum(bool(c['end'] and c['end']['overflow']) for c in choices.values()))
    return h,rows,choices,links,entries,summary


def import_choices(database,log,messages,sources,report=None):
    h,rows,choices,links,entries,summary=prepare(log,messages,sources)
    db=sqlite3.connect(database)
    added=Counter()
    try:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and ('meta' not in tables or db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()!=('choice-sidecar-1',)):
            raise ValueError('Refusing unrelated DB')
        db.executescript('''CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
        CREATE TABLE IF NOT EXISTS sessions(session_id TEXT PRIMARY KEY,header TEXT);
        CREATE TABLE IF NOT EXISTS events(session_id TEXT,seq INTEGER,raw TEXT,PRIMARY KEY(session_id,seq));
        CREATE TABLE IF NOT EXISTS variants(variant_id TEXT PRIMARY KEY,body TEXT);
        CREATE TABLE IF NOT EXISTS choices(session_id TEXT,choice_id INTEGER,parent_message_id INTEGER,variant_id TEXT,PRIMARY KEY(session_id,choice_id));
        CREATE TABLE IF NOT EXISTS links(session_id TEXT,message_id INTEGER,choice_id INTEGER,raw TEXT,PRIMARY KEY(session_id,message_id));''')
        sid=h['session_id']
        with db:
            db.execute("INSERT OR IGNORE INTO meta VALUES('schema','choice-sidecar-1')")
            old=db.execute('SELECT header FROM sessions WHERE session_id=?',(sid,)).fetchone()
            if old and old[0]!=canonical(h):raise ValueError('Changed choice header')
            db.execute('INSERT OR IGNORE INTO sessions VALUES(?,?)',(sid,canonical(h)))
            for r in rows:
                old=db.execute('SELECT raw FROM events WHERE session_id=? AND seq=?',(sid,r['seq'])).fetchone()
                if old and old[0]!=canonical(r):raise ValueError('Changed choice event')
                added['events']+=db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?)',(sid,r['seq'],canonical(r))).rowcount
            for cid,c in choices.items():
                # Only complete choices get a stable variant; unfinished event history remains retained.
                if c['end'] is None:continue
                body=canonical(dict(source_manifest=h['source_manifest'],collector_sha256=h['collector_sha256'],
                    selector_type=c['open']['selector_type'],options=c['open']['options'],
                    draws=sorted({canonical(r['state']) for r in c['draws']}),
                    confirmed_options=c['confirm']['options'] if c['confirm'] else None,
                    selected=c['end']['selected_slot'],overflow=c['end']['overflow']))
                key=hashlib.sha256(body.encode()).hexdigest()
                added['variants']+=db.execute('INSERT OR IGNORE INTO variants VALUES(?,?)',(key,body)).rowcount
                added['choices']+=db.execute('INSERT OR IGNORE INTO choices VALUES(?,?,?,?)',(sid,cid,c['open']['parent_message_id'],key)).rowcount
            for mid,r in links.items():
                added['links']+=db.execute('INSERT OR IGNORE INTO links VALUES(?,?,?,?)',(sid,mid,r['choice_id'],canonical(r))).rowcount
    finally:db.close()
    summary['new']=dict(added)
    if report:
        cards=[]
        for cid,c in choices.items():
            related=[entries[mid]['text'] for mid,r in links.items() if r['choice_id']==cid]
            cards.append('<article><h2>选择 '+str(int(cid))+' · '+c['open']['selector_type']+'</h2><p>父页：'+html.escape(entries[c['open']['parent_message_id']]['text'])+'</p><p>后续：'+html.escape(' / '.join(related))+'</p><pre>'+html.escape(json.dumps(c,ensure_ascii=False,indent=2))+'</pre></article>')
        report.write_text('<!doctype html><meta charset="utf-8"><title>选择题独立采集</title><style>body{max-width:1050px;margin:30px auto;font:16px system-ui}pre{white-space:pre-wrap}article{border-top:1px solid #ccc}</style><h1>选择题采集</h1><p>模式：'+html.escape(h['mode'])+'。配置与实际绘制分开；旧选择器文字在父页，未拆标签；只证明本次选择，不代表完整分支。</p><pre>'+html.escape(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre>'+''.join(cards),encoding='utf-8')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('db','log','messages','sources'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--report',type=Path)
    a=p.parse_args()
    print(json.dumps(import_choices(a.db,a.log,a.messages,a.sources,a.report),indent=2))
