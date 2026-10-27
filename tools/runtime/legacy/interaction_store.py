"""Independent interaction evidence DB. Read message logs; never modify message observations."""
import argparse
from collections import Counter
import hashlib
import html
import json
import math
from pathlib import Path
import sqlite3
from .store import canonical, resolve_sources


def read_lines(path):
    rows = []
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
    tail = bool(lines and not lines[-1].endswith('\n'))
    if tail:
        lines.pop()
    for i, line in enumerate(lines):
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            raise ValueError('Corrupt complete interaction event')
    return rows, tail


def integer(value, minimum=0):
    return type(value) in (int, float) and math.isfinite(value) and value >= minimum and int(value) == value


def prepare(log, message_log, sources):
    records, tail = read_lines(log)
    messages, main_tail = read_lines(message_log)
    if not records or not messages:
        raise ValueError('Missing complete header')
    h, mh = records[0], messages[0]
    if h.get('kind') != 'header' or h.get('schema') != 1 or h.get('seq') != 1:
        raise ValueError('Invalid interaction header')
    for k in ('session_id', 'run_id', 'source_manifest', 'collector_sha256', 'mode'):
        if h.get(k) != mh.get(k):
            raise ValueError('Interaction/message provenance mismatch: '+k)
    if h['mode'] not in ('natural_play_pilot', 'mechanism_selftest'):
        raise ValueError('Invalid capture mode')
    inv = json.loads(resolve_sources(sources, h['source_manifest']).read_text(encoding='utf-8'))
    by_source = {s['source_id']: s for s in inv['sources']}
    observations = {r['message_id']: r for r in messages if r['kind']=='observation'}
    interactions, endings, links = {}, set(), {}
    for seq, r in enumerate(records, 1):
        if r.get('seq') != seq or not isinstance(r.get('io_failed'), bool):
            raise ValueError('Invalid interaction event sequence')
        if seq == 1:
            continue
        iid = r.get('interaction_id')
        if not integer(iid):
            raise ValueError('Invalid interaction ID')
        if r.get('kind') == 'interaction':
            if iid != len(interactions)+1 or not integer(r.get('parent_id')) or r.get('parent_id') not in (0, *interactions):
                raise ValueError('Reused interaction or unknown parent')
            s = r.get('snapshot', {})
            if any(not isinstance(s.get(k), str) for k in ('room_name','object','evidence')) or s['evidence']!='configured_instance_at_confirm_dispatch':
                raise ValueError('Invalid object snapshot')
            for k in ('sprite','mask'):
                a = s.get(k, {})
                if not isinstance(a.get('name'), str) or not all(integer(a.get(n), -1 if n in ('id','frame') else 0) for n in ('id','frames','frame')) or not (a['frames']==0 and a['frame']==-1 or 0<=a['frame']<a['frames']):
                    raise ValueError('Invalid sprite snapshot')
            extra=s.get('cafe_draw_inputs')
            if extra is not None:
                if s['object']!='obj_npc_cafe' or extra.get('evidence')!='source_verified_cafe_draw_inputs_at_dispatch' or not all(integer(extra.get(k)) for k in ('seat','mode','recruit_id')):
                    raise ValueError('Invalid cafe draw inputs')
                a=extra.get('sprite',{})
                if not isinstance(a.get('name'),str) or not all(integer(a.get(k),-1 if k in ('id','frame') else 0) for k in ('id','frame','frames')) or not (a['frames']==0 and a['frame']==-1 or 0<=a['frame']<a['frames']):
                    raise ValueError('Invalid cafe sprite inputs')
            if not integer(r.get('target_instance_id')) or any(type(r.get(k)) not in (int,float) or not math.isfinite(r[k]) for k in ('x','y')):
                raise ValueError('Invalid instance coordinates')
            interactions[iid] = r
        elif r.get('kind') == 'dispatch_end':
            if iid not in interactions or iid in endings:
                raise ValueError('Orphan/repeated dispatch end')
            endings.add(iid)
        elif r.get('kind') == 'message_link':
            mid = r.get('message_id')
            if mid not in observations or mid in links or iid and iid not in interactions:
                raise ValueError('Orphan/repeated message link')
            o = observations[mid]
            if any(r.get(k) != o.get(k) for k in ('source_id','writer_id','page')):
                raise ValueError('Cross-message link')
            expected = 'propagated_message_token' if iid else 'no_proven_interaction'
            if r.get('relation') != expected:
                raise ValueError('Invalid relation evidence')
            if o['source_id'] and o['source_id'] not in by_source:
                raise ValueError('Unknown occurrence source')
            links[mid] = r
        else:
            raise ValueError('Unsupported sidecar event')
    summary = dict(interactions=len(interactions), linked_messages=sum(bool(r['interaction_id']) for r in links.values()),
        unlinked_messages=sum(not r['interaction_id'] for r in links.values()),
        missing_links=len(observations.keys()-links.keys()), unclosed_dispatches=len(interactions.keys()-endings),
        tail_incomplete=tail or main_tail, io_failed=any(r['io_failed'] for r in records))
    return h, records, interactions, links, observations, by_source, summary


def import_interactions(db_path, log, message_log, sources, report=None):
    h, records, interactions, links, observations, by_source, summary = prepare(log, message_log, sources)
    sid = h['session_id']
    snapshots = {}
    for iid, r in interactions.items():
        body = canonical({'source_manifest':h['source_manifest'], 'snapshot':r['snapshot']})
        snapshots[iid] = (hashlib.sha256(body.encode()).hexdigest(), body)
    db = sqlite3.connect(db_path)
    try:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and ('meta' not in tables or db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()!=('interaction-sidecar-1',)):
            raise ValueError('Refusing unrelated DB')
        db.executescript('''
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(session_id TEXT PRIMARY KEY,header TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(session_id TEXT,seq INTEGER,raw TEXT NOT NULL,PRIMARY KEY(session_id,seq));
        CREATE TABLE IF NOT EXISTS snapshots(snapshot_id TEXT PRIMARY KEY,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS interactions(session_id TEXT,interaction_id INTEGER,snapshot_id TEXT NOT NULL,raw TEXT NOT NULL,PRIMARY KEY(session_id,interaction_id));
        CREATE TABLE IF NOT EXISTS links(session_id TEXT,message_id INTEGER,interaction_id INTEGER,occurrence_id TEXT,raw TEXT NOT NULL,PRIMARY KEY(session_id,message_id));
        ''')
        added = Counter()
        with db:
            db.execute("INSERT OR IGNORE INTO meta VALUES('schema','interaction-sidecar-1')")
            existing=db.execute('SELECT header FROM sessions WHERE session_id=?',(sid,)).fetchone()
            if existing and existing[0]!=canonical(h):raise ValueError('Session header changed')
            db.execute('INSERT OR IGNORE INTO sessions VALUES(?,?)',(sid,canonical(h)))
            for r in records:
                old=db.execute('SELECT raw FROM events WHERE session_id=? AND seq=?',(sid,r['seq'])).fetchone()
                if old and old[0]!=canonical(r):raise ValueError('Previously imported sidecar event changed')
                added['events']+=db.execute('INSERT OR IGNORE INTO events VALUES(?,?,?)',(sid,r['seq'],canonical(r))).rowcount
            for iid,r in interactions.items():
                key,body=snapshots[iid]
                added['snapshots']+=db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(key,body)).rowcount
                added['interactions']+=db.execute('INSERT OR IGNORE INTO interactions VALUES(?,?,?,?)',(sid,iid,key,canonical(r))).rowcount
            for mid,r in links.items():
                source=by_source.get(r['source_id'])
                added['links']+=db.execute('INSERT OR IGNORE INTO links VALUES(?,?,?,?,?)',(sid,mid,r['interaction_id'],source['occurrence_id'] if source else None,canonical(r))).rowcount
        summary.update(session_id=sid,new=dict(added),unique_snapshots=len({v[0] for v in snapshots.values()}))
    finally:
        db.close()
    if report:
        cards=[]
        for iid,r in interactions.items():
            linked=[(mid,l) for mid,l in links.items() if l['interaction_id']==iid]
            text=''.join('<li><a href="review.html#s'+html.escape(sid,quote=True)+'-m'+str(int(mid))+'">消息 '+str(int(mid))+'</a><pre>'+html.escape(observations[mid]['text'])+'</pre><small>'+html.escape(by_source.get(l['source_id'],{}).get('key','来源未绑定'))+'</small></li>' for mid,l in linked)
            cards.append('<article><h2>交互 '+str(int(iid))+' · '+html.escape(r['snapshot']['object'])+'</h2><p>场景贴图配置：'+html.escape(r['snapshot']['sprite']['name'])+' ['+str(r['snapshot']['sprite']['frame'])+']</p><ul>'+text+'</ul>'+('' if linked else '<p>没有追踪到显示消息；不代表此对象没有响应。</p>')+'<details><summary>对象快照／证据</summary><pre>'+html.escape(json.dumps(r,ensure_ascii=False,indent=2))+'</pre></details></article>')
        report.write_text('<!doctype html><meta charset="utf-8"><title>主动交互独立记录</title><style>body{max-width:1000px;margin:32px auto;font:16px system-ui}article{border-top:1px solid #bbb;padding:16px}pre{white-space:pre-wrap}</style><h1>主动交互独立记录</h1><p>对象是触发来源，不自动认定为说话人；贴图是配置快照，不是实际绘制截图。模式：'+html.escape(h['mode'])+'</p><pre>'+html.escape(json.dumps(summary,ensure_ascii=False,indent=2))+'</pre>'+''.join(cards),encoding='utf-8')
    return summary


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('db','log','messages','sources'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--report',type=Path)
    a=p.parse_args()
    print(json.dumps(import_interactions(a.db,a.log,a.messages,a.sources,a.report),ensure_ascii=False,indent=2))
