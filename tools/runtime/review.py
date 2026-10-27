"""Build a local, searchable two-track review workspace from verified submission ZIPs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess

from .bundles import receive_bundle, _read_bundle, _inventory
from .interpret import interpret, VERSION
from .kit import sha, _plain, _new_output


def build(bundles, sources, library, out, code_root=None, game=None, cli=None, characters=None):
    out=_new_output(out,library,*bundles)
    dataset=dict(schema=1,interpretation=VERSION,sessions=[],rows=[],characters=[])
    frames=set();packages=set();verified={}
    for bundle in bundles:
        result=receive_bundle(bundle,sources,library)
        manifest,files=_read_bundle(bundle)
        for seg in manifest['segments']:
            sid=seg['session_id'];_,inv=_inventory(sources,seg['source_manifest']);packages.add(inv['package_sha256'])
            by_source={s['source_id']:s for s in inv['sources']}
            db=sqlite3.connect(Path(library)/'received'/manifest['bundle_id']/sid/'messages.sqlite')
            bodies={mid:(vid,json.loads(body),json.loads(telemetry)) for mid,vid,body,telemetry in db.execute('SELECT o.message_id,o.variant_id,v.body,o.telemetry FROM observations o JOIN variants v USING(variant_id)')};db.close()
            streams={kind:[json.loads(l) for l in files[name].splitlines()] for kind,name in seg['files'].items()}
            observations={r['message_id']:r for r in streams['capture'] if r['kind']=='observation'}
            ix={r['interaction_id']:r for r in streams.get('interactions',[]) if r['kind']=='interaction'}
            ixlinks={r['message_id']:r for r in streams.get('interactions',[]) if r['kind']=='message_link'}
            choices={r['choice_id']:dict(r) for r in streams.get('choices',[]) if r['kind']=='choice_open'}
            for r in streams.get('choices',[]):
                if r['kind']=='choice_confirm':choices[r['choice_id']]['selected_slot']=r['selected_slot']
            clinks={r['message_id']:r for r in streams.get('choices',[]) if r['kind']=='message_link'}
            segment_summary=next(s for s in result['summary']['segment_summaries'] if s['session_id']==sid)
            summary=dict(segment_summary['counts'], interactions=len(ix), choices=len(choices))
            dataset['sessions'].append(dict(id=sid,run=manifest['run_id'],mode=seg['mode'],summary=summary,bundle=manifest['bundle_id']))
            for mid,(vid,body,telemetry) in bodies.items():
                src=by_source.get(observations[mid]['source_id']);snippet=None
                if src and code_root:
                    p=Path(code_root)/Path(src['path']).name
                    if p.name not in verified:
                        if sha(p)!=src['sha256']:raise ValueError('Source changed: '+p.name)
                        verified[p.name]=src['sha256']
                    lines=p.read_text(encoding='utf-8').splitlines();n=src['line']
                    snippet='\n'.join(f'{i+1}: {lines[i]}' for i in range(max(0,n-5),min(len(lines),n+12)))
                interaction=ix.get(ixlinks.get(mid,{}).get('interaction_id'))
                parents=[c for c in choices.values() if c['parent_message_id']==mid]
                after=choices.get(clinks.get(mid,{}).get('choice_id'))
                row=dict(id=sid+':'+str(mid),session=sid,message=mid,partition=seg['partition_id'],variant=vid,
                         body=body,source=src,snippet=snippet,view=interpret(body),interaction=interaction,
                         choices=parents,after_choice=after,telemetry=telemetry)
                dataset['rows'].append(row)
                for a in body.get('assets',[]):frames.add((a['sprite_name'],int(a['subimage'])))
                for sf in body.get('smallfaces',[]):
                    for a in sf['sprites']:frames.add((a['sprite_name'],int(a['subimage'])))
                if interaction:
                    snap=interaction['snapshot'];a=snap['sprite']
                    if a['id']>=0:frames.add((a['name'],int(a['frame'])))
                    if snap.get('cafe_draw_inputs'):
                        a=snap['cafe_draw_inputs']['sprite']
                        if a['id']>=0:frames.add((a['name'],int(a['frame'])))
    if len({s['id'] for s in dataset['sessions']})!=len(dataset['sessions']):raise ValueError('Choose one current bundle per session')
    if characters:
        data=json.loads(Path(characters).read_text(encoding='utf-8'))
        dataset['characters']=[{k:c[k] for k in ('id','en','zh')} for c in data['characters']]
    out.mkdir(parents=True)
    if game:
        game=_plain(game).resolve(strict=True)
        if packages!={sha(game)} or not cli:raise ValueError('Exact bound game and CLI required for frame export')
        request=dict(output=str(out/'assets'),frames=[dict(name=n,frame=f) for n,f in sorted(frames)])
        if any(not re.fullmatch(r'spr_\w+',n) or f<0 for n,f in frames):raise ValueError('Invalid frame')
        (out/'asset-request.json').write_text(json.dumps(request),encoding='utf-8')
        with (out/'assets.log').open('wb') as log:
            subprocess.run([str(cli),'load',str(game),'-s',str(Path(__file__).with_name('export_review_assets.csx'))],
                env=dict(os.environ,DR_REVIEW_ASSETS=str(out/'asset-request.json')),stdout=log,stderr=subprocess.STDOUT,check=True)
        dataset['assets']={n+'_'+str(f)+'.png':sha(out/'assets'/f'{n}_{f}.png') for n,f in sorted(frames)}
    else:dataset['assets']={}
    dataset['source_files_verified']=len(verified)
    (out/'data.js').write_text('window.REVIEW_DATA='+json.dumps(dataset,ensure_ascii=False).replace('<','\\u003c')+';\n',encoding='utf-8')
    for name in ('index.html','review.css','review.js'):
        shutil.copy2(Path(__file__).with_name('review_web')/name,out/name)
    return dict(out=str(out),sessions=len(dataset['sessions']),rows=len(dataset['rows']),frames=len(dataset['assets']),source_files_verified=len(verified))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,action='append',required=True)
    for name in ('sources','library','out'):p.add_argument('--'+name,type=Path,required=True)
    for name in ('code-root','game','cli','characters'):p.add_argument('--'+name,type=Path)
    a=p.parse_args();print(json.dumps(build(a.bundle,a.sources,a.library,a.out,a.code_root,a.game,a.cli,a.characters),indent=2))
