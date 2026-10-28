"""Generate all five chapters, with a chapter lookup and one context chunk per file."""
from collections import Counter
from collections.abc import Mapping
import json
from pathlib import Path
import time
from .context_conditions import ROOT, backend, digest
from .context_files import Analyzer
from .context_paths import paths, parser
from .context_data import references, validate


class Sources(Mapping):
    def __init__(self,folder):
        self.paths={p.name:p for p in sorted(folder.glob('*.gml'))}
        self.loaded={};self.hashes={}
    def __len__(self):return len(self.paths)
    def __iter__(self):return iter(self.paths)
    def __contains__(self,key):return key in self.paths
    def __getitem__(self,key):
        if key not in self.loaded:
            raw=self.paths[key].read_bytes();self.hashes[key]=digest(raw)
            self.loaded[key]=raw.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
        return self.loaded[key]


def encoded(value):
    return (json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode('utf-8')


def fallback(name,ch,refs):
    return {'id':f'ch{ch}/'+name,'chapter':ch,'file':name,'title':name,'reference_count':len(refs),
            'body':{'type':'blocks','children':[{'type':'block','label':'L'+str(r['source']['line']),
                     'unresolved':True,'children':[r]} for r in refs]}}


def build(code, texts=ROOT/'build/texts', out=ROOT/'local/context-all'):
    code,texts,out=paths(code,texts,out)
    began=time.perf_counter();api=backend()
    manifest_bytes=(texts/'manifest.json').read_bytes();binding=digest(manifest_bytes)
    out.mkdir(parents=True,exist_ok=True);(out/'files').mkdir(exist_ok=True)
    inventory={};chapter_paths={};summaries=[];diagnostics=[];rules=[];sources_proof={};missing={};queue_audit=[];direct_audit=[]
    def write(path,data):
        raw=encoded(data);(out/path).write_bytes(raw)
        meta={'path':path,'sha256':digest(raw),'bytes':len(raw)};inventory[path]=meta;return meta
    for ch in range(1,6):
        tables={r['key']:r for r in json.loads((texts/f'trilingual_chapter{ch}.json').read_text(encoding='utf-8'))['lines']}
        sources=Sources(code/f'ch{ch}');analyzer=Analyzer(sources,ch,tables,api,sources.hashes,strict_bindings=False)
        files=[];lookup={};related={};counts=Counter();chapter_rules=Counter()
        for index,name in enumerate(sources):
            source=sources[name]
            if '_gml_' not in source:
                sources.loaded.pop(name,None);continue
            record=analyzer.file(name)
            if not record['refs']:
                analyzer.cache.pop(name,None);sources.loaded.pop(name,None);continue
            try:
                scene=analyzer.analyze(name)
                pack={'schema':1,'text_manifest_sha256':binding,'scenes':[scene]}
                validate(pack,manifest_bytes,{ch:tables})
            except (ValueError,RecursionError,IndexError) as exc:
                diagnostics.append({'chapter':ch,'file':name,'reason':'projection_fallback','detail':str(exc)})
                analyzer.evidence=[]
                scene=fallback(name,ch,record['refs'])
                pack={'schema':1,'text_manifest_sha256':binding,'scenes':[scene]}
                validate(pack,manifest_bytes,{ch:tables})
            native=[r for r in references(scene['body']) if r['source']['file']==name]
            assert Counter(r['occurrence_id'] for r in native)==Counter(r['occurrence_id'] for r in record['refs']),name
            fid=len(files);path='files/'+digest(scene['id'].encode())[:24]+'.json'
            meta=write(path,pack)
            files.append({'file':name,'id':scene['id'],'reference_count':len(native),**meta})
            for key in sorted({r['key'] for r in native}):lookup.setdefault(key,[]).append(fid)
            for key in sorted({r['key'] for r in references(scene['body']) if r['source']['file']!=name}):related.setdefault(key,[]).append(fid)
            counts['references']+=len(native);counts.update(r.get('binding','matched') for r in native)
            chapter_rules.update(e['rule'] for e in analyzer.evidence)
            rules.extend({'chapter':ch,**e} for e in analyzer.evidence)
            queue_audit.extend({'chapter':ch,**e} for e in analyzer.queue_audit)
            direct_audit.extend({'chapter':ch,**e} for e in analyzer.direct_audit)
            diagnostics.extend({'chapter':ch,**e} for e in analyzer.diagnostics)
            # Only shared protocol helpers need persistent parsed trees.
            if name!='gml_GlobalScript_scr_text.gml':analyzer.cache.pop(name,None)
            sources.loaded.pop(name,None)
            if len(files)%100==0:print(f'CH{ch}: {len(files)} files / {counts["references"]} references',flush=True)
        absent=sorted(set(tables)-set(lookup));missing[str(ch)]=absent
        summary={'chapter':ch,'scanned_files':len(sources),'context_files':len(files),'text_records':len(tables),
                 'covered_keys':len(set(tables)&set(lookup)),'no_source_keys':len(absent),
                 'no_source_without_english':sum(tables[k]['en'] is None for k in absent),
                 'links':dict(chapter_rules),**counts}
        summaries.append(summary)
        chapter_paths[str(ch)]=write(f'index-ch{ch}.json',{'schema':2,'chapter':ch,'text_manifest_sha256':binding,
                                          'files':files,'by_key':lookup,'related_by_key':related})
        sources_proof.update({f'ch{ch}/'+name:sha for name,sha in sources.hashes.items()})
        print(json.dumps(summary,ensure_ascii=False),flush=True)
    manifest={'schema':2,'kind':'automatic-context-catalog','text_manifest_sha256':binding,'chapters':chapter_paths}
    raw=encoded(manifest);(out/'contexts.json').write_bytes(raw)
    report={'schema':2,'text_manifest_sha256':binding,'contexts_sha256':digest(raw),'files':inventory,
            'chapters':summaries,'diagnostics':diagnostics,'rules':rules,'sources':sources_proof,
            'missing_keys':missing,'queued_menus':queue_audit,'direct_menus':direct_audit,'total_bytes':sum(v['bytes'] for v in inventory.values())+len(raw),
            'seconds':round(time.perf_counter()-began,2)}
    (out/'evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'total_files':sum(s['context_files'] for s in summaries),'total_bytes':report['total_bytes'],
                      'diagnostics':len(diagnostics),'seconds':report['seconds']},ensure_ascii=False),flush=True)
    return report


if __name__=='__main__':
    a=parser(__doc__,'local/context-all').parse_args()
    build(a.code,a.texts,a.out)
