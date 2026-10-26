"""Website contract for source-bound static context trees."""
from import_texts import sha
import json
import re


def references(node):
    if node['type']=='message':yield node
    for child in node.get('children',[]):yield from references(child)
    for branch in node.get('branches',[]):
        if 'option' in branch:yield branch['option']
        yield from references(branch['body'])


def validate(pack, text_manifest, tables):
    if pack.get('schema')!=1 or pack.get('text_manifest_sha256')!=sha(text_manifest):
        raise ValueError('Context data stale or unsupported; regenerate context pilot')
    ids=set()
    def node(n,ch,depth=0):
        if depth>128:raise ValueError('Context nesting limit exceeded')
        kind=n.get('type')
        if kind=='message':
            missing=n.get('binding')=='missing_key' and n.get('key') not in tables[ch] and 'source_english' in n and (n['source_english'] is None or isinstance(n['source_english'],str))
            if (n.get('key') not in tables[ch] and not missing) or not str(n.get('occurrence_id','')).startswith('occurrence:'):
                raise ValueError('Invalid context reference')
            s=n.get('source',{})
            if not s.get('file','').startswith('gml_') or '/' in s['file'] or '\\' in s['file'] or type(s.get('line')) is not int or s['line']<1:
                raise ValueError('Invalid context source')
        elif kind in ('sequence','block','blocks'):
            for c in n['children']:node(c,ch,depth+1)
        elif kind in ('choice','condition'):
            if len(n['branches'])<2:raise ValueError('Incomplete branch set')
            for b in n['branches']:
                if kind=='choice':node(b['option'],ch,depth+1)
                elif not isinstance(b.get('label'),str):raise ValueError('Missing condition label')
                node(b['body'],ch,depth+1)
        elif kind in ('end','join'):
            if not isinstance(n.get('label'),str):raise ValueError('Missing endpoint label')
        else:raise ValueError('Unknown context node type')
    for scene in pack['scenes']:
        if scene['id'] in ids or scene['chapter'] not in tables:raise ValueError('Duplicate/invalid scene')
        ids.add(scene['id']);node(scene['body'],scene['chapter'])
    return pack


def catalog_payload(folder,text_manifest,tables):
    """Validate every lazily served chunk and its lookup before copying to dist."""
    raw=(folder/'contexts.json').read_bytes();catalog=json.loads(raw)
    evidence=json.loads((folder/'evidence.json').read_text(encoding='utf-8'))
    binding=sha(text_manifest)
    if catalog.get('schema')!=2 or catalog.get('text_manifest_sha256')!=binding or sha(raw)!=evidence['contexts_sha256']:
        raise ValueError('Context catalog stale or corrupt')
    payload={'data/contexts.json':raw}
    def read(meta):
        path=meta['path']
        if not re.fullmatch(r'(?:index-ch[1-5]|files/[0-9a-f]{24})\.json',path):raise ValueError('Unsafe context chunk path')
        raw=(folder/path).read_bytes()
        if sha(raw)!=meta['sha256'] or len(raw)!=meta['bytes']:raise ValueError('Context chunk digest mismatch: '+path)
        if evidence['files'].get(path)!=meta:raise ValueError('Context chunk evidence mismatch')
        payload['data/context/'+path]=raw
        return json.loads(raw)
    if set(catalog['chapters'])!={str(ch) for ch in range(1,6)}:raise ValueError('Incomplete chapter catalog')
    for chapter,meta in catalog['chapters'].items():
        ch=int(chapter);index=read(meta)
        if index.get('chapter')!=ch or index.get('text_manifest_sha256')!=binding:raise ValueError('Context chapter mismatch')
        native={};related={}
        for fid,entry in enumerate(index['files']):
            pack=read({k:entry[k] for k in ('path','sha256','bytes')});validate(pack,text_manifest,tables)
            if len(pack['scenes'])!=1:raise ValueError('Expected one file per chunk')
            scene=pack['scenes'][0]
            if scene['chapter']!=ch or scene['file']!=entry['file'] or scene['id']!=entry['id']:raise ValueError('Context file identity mismatch')
            refs=list(references(scene['body']))
            if sum(r['source']['file']==scene['file'] for r in refs)!=entry['reference_count']:raise ValueError('Context reference count mismatch')
            for key in sorted({r['key'] for r in refs if r['source']['file']==scene['file']}):native.setdefault(key,[]).append(fid)
            for key in sorted({r['key'] for r in refs if r['source']['file']!=scene['file']}):related.setdefault(key,[]).append(fid)
        if index['by_key']!=native or index['related_by_key']!=related:raise ValueError('Context lookup coverage mismatch')
    return payload
