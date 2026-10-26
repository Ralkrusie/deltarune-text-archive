"""Migrate only verified source locations from the old database, without attribution fields."""
import argparse, hashlib, json, sqlite3
from pathlib import Path

def prepare(database, code, texts, out):
    database=Path(database).resolve(strict=True);code=Path(code).resolve(strict=True)
    texts=Path(texts).resolve(strict=True);out=Path(out).resolve()
    out.mkdir(parents=True,exist_ok=True)
    summary=[]; evidence={}
    with sqlite3.connect(database.as_uri()+'?mode=ro',uri=True) as con:
        for ch in range(1,6):
            rows=json.loads((texts/f'trilingual_chapter{ch}.json').read_text(encoding='utf-8'))['lines']
            keys={r['key'] for r in rows}; found={}; cache={}; rejected=[]
            for key,file,line in con.execute('SELECT l.key,o.file,o.line FROM occurrences o JOIN lines l ON l.id=o.line_id WHERE l.chapter=? AND o.chapter=? ORDER BY o.id',(ch,ch)):
                if key not in keys:continue
                if not file or Path(file).name!=file or not file.startswith('gml_') or not file.endswith('.gml'):continue
                path=code/f'ch{ch}'/file
                if file not in cache:
                    raw=path.read_bytes();cache[file]=raw.decode('utf-8-sig').splitlines()
                    evidence[f'ch{ch}/{file}']=hashlib.sha256(raw).hexdigest()
                lines=cache[file]
                if not isinstance(line,int) or line<1 or line>len(lines) or '"'+key+'"' not in lines[line-1]:
                    rejected.append([key,file,line]);continue
                pair=[file,line]
                if pair not in found.setdefault(key,[]):found[key].append(pair)
            files=sorted({f for items in found.values() for f,line in items}); indices={f:i for i,f in enumerate(files)}
            data={'text_manifest_sha256':hashlib.sha256((texts/'manifest.json').read_bytes()).hexdigest(),'schema':1,'chapter':ch,'files':files,'by_key':{key:[[indices[f],line] for f,line in items] for key,items in sorted(found.items())}}
            (out/f'ch{ch}.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
            summary.append({'chapter':ch,'keys':len(found),'locations':sum(map(len,found.values())),'missing':len(keys-found.keys()),'rejected':rejected})
    (out/'provenance.json').write_text(json.dumps({'database':str(database),'code':str(code),'files_sha256':evidence,'summary':summary},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['database','code','texts','out']:p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();prepare(a.database,a.code,a.texts,a.out)
