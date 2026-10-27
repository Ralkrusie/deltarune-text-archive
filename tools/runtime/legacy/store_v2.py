"""Append-only event ingestion; page attributes may arrive after the page entry."""
import json
from pathlib import Path
import re
import sqlite3
from .store import canonical, digest
from .style_store import validate_styles, style_body
from .smallface_store import validate_smallfaces, smallface_body


def normalized_detail(header, entry, detail):
    """Recover only the audited rev7 choice-page empty-cursor defect; raw events stay intact."""
    if detail is None:return None
    limit=len(detail['formatted_text'])+1
    spans=detail['identity_spans']
    if not any(s['end_index']>limit for s in spans):return detail
    if (header.get('collector_sha256')!='43550d6cd64703156efa926151323af214e663bff0c003d88235fbe9a36d0699'
        or not re.fullmatch(r'\s*\\C2\s*',entry['text'])
        or detail['formatted_text']!=entry['text']
        or any(not 1<=s['start_index']<s['end_index']<=limit+2 for s in spans)):
        return detail  # Normal validation below still rejects unrelated out-of-range data.
    repaired=[]
    for s in spans:
        end=min(s['end_index'],limit)
        if s['start_index']<end:repaired.append(dict(s,end_index=end))
    return {**detail,'identity_spans':repaired,'normalization':'rev7_choice_empty_cursor_clipped',
            'telemetry':{**detail['telemetry'],'glyphs_consumed':bool(repaired)}}


def page_body(header, inventory, entry, detail):
    detail=normalized_detail(header,entry,detail)
    sources={s['source_id']:s for s in inventory['sources']}
    source=sources.get(entry['source_id'])
    states=[] if detail is None else detail['identity_states']
    # Canonical ordering makes different traversal order alone immaterial.
    unique=sorted({canonical(s) for s in states})
    state_map={i:unique.index(canonical(s)) for i,s in enumerate(states)}
    canonical_states=[json.loads(s) for s in unique]
    spans=[] if detail is None else [dict(s,state_index=state_map[s['state_index']]) for s in detail['identity_spans']]
    # Preserve the raw draw argument in events; equivalent wrapped frames share a variant.
    assets=[] if detail is None else [json.loads(s) for s in sorted({canonical(
        {k:v for k,v in a.items() if k!='requested_subimage'}) for a in detail['assets']})]
    faces=inventory.get('face_entities',{})
    candidates=sorted({faces[str(int(s['face_code']))] for s in canonical_states if str(int(s['face_code'])) in faces})
    control_only=bool(re.fullmatch(r'(?:\\[A-Za-z][A-Za-z0-9]\s*)+%',entry['text']) or re.fullmatch(r'\s*\\C2\s*',entry['text']))
    if control_only:candidates=[]
    return {'schema':2,'manifest':header['source_manifest'],'mode':header['mode'],
        'collector_sha256':header.get('collector_sha256','unversioned-development'),
        **({'input_policy':header['input_policy']} if 'input_policy' in header else {}),
        **({'normalization':detail['normalization']} if detail and 'normalization' in detail else {}),
        'test_modifications':header['test_modifications'],
        'occurrence_id':source['occurrence_id'] if source else None,
        'binding':'propagated_source_tag' if source else 'unmatched',
        'room':entry['room_name'],'language':entry['language'],'channel':entry['channel'],'text':entry['text'],
        'identity':{'status':'control_only' if control_only else 'face_code_evidence' if candidates else 'unknown',
                    'candidates':candidates,'states':canonical_states,'spans':spans,
                    'no_face_is_not_narrator':True},
        'formatted_text':None if detail is None else detail['formatted_text'],
        'index_space':'formatted_mystring_1based','assets':assets,
        **style_body(header,detail),
        **smallface_body(header,inventory,detail),
        'coverage':{'page_closed':detail is not None,'overflow':False if detail is None else detail['overflow'],
                    'glyphs_consumed':False if detail is None else detail['telemetry']['glyphs_consumed'],
                    'portrait':'observed_draws' if any(a['role']=='portrait' for a in assets) else 'not_observed',
                    'color':('observed_draws' if detail['text_styles']['states'] else 'not_observed') if detail and 'text_styles' in detail else 'not_instrumented',
                    'motion':('observed_draws' if detail['text_styles']['states'] else 'not_observed') if detail and 'text_styles' in detail else 'not_instrumented',
                    'smallface':('child_observations' if detail['smallfaces'] else 'not_observed') if detail and 'smallfaces' in detail else 'not_instrumented'},
        'partial':True}


def import_v2(database:Path,records,inventory,tail_incomplete):
    header=records[0]
    if (header.get('schema')!=2 or header.get('kind')!='header' or header.get('mode') not in ('natural_play_pilot','mechanism_selftest')
        or not re.fullmatch('[a-f0-9]{32}',header.get('session_id',''))
        or header.get('test_modifications')!=inventory.get('test_modifications')):
        raise ValueError('Invalid v2 header / modification binding')
    sources={s['source_id']:s for s in inventory['sources']}
    entries={};details={}
    for seq,r in enumerate(records[1:],1):
        if r.get('seq')!=seq or type(r.get('seq')) not in (int,float): raise ValueError('Invalid event sequence')
        mid=r.get('message_id')
        if type(mid) not in (int,float) or int(mid)!=mid or mid<=0: raise ValueError('Invalid message ID')
        if r.get('kind')=='observation':
            if mid in entries or mid!=len(entries)+1: raise ValueError('Reused / missing message ID')
            if r.get('source_id')!=0 and r.get('source_id') not in sources: raise ValueError('Unknown source ID')
            if r.get('stage')!='page_enter' or r.get('language')!='en' or r.get('channel')!='obj_writer': raise ValueError('Unsupported entry')
            if any(not isinstance(r.get(k),str) for k in ('text','room_name')): raise ValueError('Missing text/context')
            entries[mid]=r
        elif r.get('kind')=='attributes':
            if mid not in entries or mid in details: raise ValueError('Orphan/repeated attributes')
            if any(r.get(k)!=entries[mid].get(k) for k in ('page','writer_id')): raise ValueError('Cross-message attributes')
            if r.get('index_space')!='formatted_mystring_1based' or not isinstance(r.get('formatted_text'),str): raise ValueError('Invalid offsets')
            if any(not isinstance(r.get(k),list) for k in ('identity_states','identity_spans','assets')): raise ValueError('Invalid attribute lists')
            if len(r['identity_states'])>64 or len(r['assets'])>256: raise ValueError('Unbounded attributes')
            for state in r['identity_states']:
                if any(type(state.get(k)) not in (int,float) for k in ('face_code','expression','typer')): raise ValueError('Invalid identity signal')
            checked=normalized_detail(header,entries[mid],r)
            for span in r['identity_spans']:
                if not 0<=span['state_index']<len(r['identity_states']):raise ValueError('Invalid identity state index')
            for span in checked['identity_spans']:
                if not 0<=span['state_index']<len(r['identity_states']) or not 1<=span['start_index']<span['end_index']<=len(r['formatted_text'])+1: raise ValueError('Invalid identity span')
            for asset in r['assets']:
                if asset.get('role') not in ('portrait','inline') or not isinstance(asset.get('sprite_name'),str): raise ValueError('Invalid sprite reference')
            if not isinstance(r.get('telemetry'),dict) or type(r.get('overflow')) is not bool: raise ValueError('Missing capture status')
            validate_styles(header,r)
            validate_smallfaces(header,entries[mid],r,sources)
            details[mid]=r
        else: raise ValueError('Unknown v2 record kind')
    database.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(database)
    try:
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and ('meta' not in tables or db.execute("SELECT value FROM meta WHERE key='schema'").fetchone()!=('capture-attributes-2',)):
            raise ValueError('Refusing non-v2 database')
        db.executescript('''CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(session_id TEXT PRIMARY KEY,header TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(session_id TEXT,seq INTEGER,raw TEXT NOT NULL,PRIMARY KEY(session_id,seq));
        CREATE TABLE IF NOT EXISTS variants(variant_id TEXT PRIMARY KEY,body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS observations(session_id TEXT,message_id INTEGER,variant_id TEXT,telemetry TEXT,PRIMARY KEY(session_id,message_id));''')
        sid=header['session_id'];new_events=new_obs=new_variants=updated=0
        with db:
            db.execute("INSERT OR IGNORE INTO meta VALUES ('schema','capture-attributes-2')")
            old=db.execute('SELECT header FROM sessions WHERE session_id=?',(sid,)).fetchone()
            if old and old[0]!=canonical(header):raise ValueError('Header altered')
            db.execute('INSERT OR IGNORE INTO sessions VALUES (?,?)',(sid,canonical(header)))
            for r in records[1:]:
                old=db.execute('SELECT raw FROM events WHERE session_id=? AND seq=?',(sid,r['seq'])).fetchone()
                if old and old[0]!=canonical(r): raise ValueError('Prior event altered')
                new_events+=db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?)',(sid,r['seq'],canonical(r))).rowcount
            # A shorter replay cannot erase attributes already stored.
            persisted=[json.loads(r[0]) for r in db.execute('SELECT raw FROM events WHERE session_id=? ORDER BY seq',(sid,))]
            all_entries={r['message_id']:r for r in persisted if r['kind']=='observation'}
            all_details={r['message_id']:r for r in persisted if r['kind']=='attributes'}
            for mid,entry in all_entries.items():
                detail=all_details.get(mid);body=page_body(header,inventory,entry,detail);vid=digest(body)
                new_variants+=db.execute('INSERT OR IGNORE INTO variants VALUES (?,?)',(vid,canonical(body))).rowcount
                old=db.execute('SELECT variant_id FROM observations WHERE session_id=? AND message_id=?',(sid,mid)).fetchone()
                new_obs+=old is None;updated+=bool(old and old[0]!=vid)
                telemetry={} if detail is None else {'reason':detail['reason'],**detail['telemetry']}
                db.execute('INSERT OR REPLACE INTO observations VALUES (?,?,?,?)',(sid,mid,vid,canonical(telemetry)))
        return {'schema':2,'session_id':sid,'events':len(entries),'raw_events':len(records)-1,
                'new_events':new_events,'new_observations':new_obs,'new_variants':new_variants,'updated_observations':updated,
                'unmatched':sum(not r['source_id'] for r in entries.values()),'unclosed_pages':len(entries)-len(details),
                'tail_incomplete':tail_incomplete,'capture_complete':False}
    finally: db.close()
