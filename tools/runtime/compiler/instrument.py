"""Source-bound CH2 pilot transformations. No text-based runtime matching."""
from __future__ import annotations
import hashlib
from pathlib import Path
import re
from .syntax import TOKEN, split_args, as_string_literal, occurrence_id

CALLS = {"msgsetloc": 3, "msgnextloc": 2, "c_msgsetloc": 3, "c_msgnextloc": 2}
SUB_CALLS = {"msgsetsubloc": 3, "msgnextsubloc": 2, "c_msgsetsubloc": 3, "c_msgnextsubloc": 2}


def transform(text: str, filename: str, source_hash: str, start_id: int):
    tokens = [t for t in TOKEN.finditer(text) if not t.group().startswith(("//", "/*"))]
    edits, rows = [], []
    for i, token in enumerate(tokens[:-1]):
        call = token.group()
        if call not in (CALLS | SUB_CALLS) or tokens[i+1].group() != "(":
            continue
        if i and tokens[i-1].group() == "function":
            continue
        args, end, ok = split_args(text, tokens[i+1].start())
        if not ok or (call in CALLS and len(args) != CALLS[call]) or (call in SUB_CALLS and not SUB_CALLS[call] <= len(args) <= 16):
            raise ValueError(f"Unsupported call signature: {filename}:{token.start()}")
        key = as_string_literal(args[-1])
        # Dynamic/shared wrappers remain uninstrumented at their inner call.
        # They still clear any previous slot tag through the write interception.
        if key is None:
            continue
        ident = start_id + len(rows)
        path = f"data/exported/code/ch2/{filename}"
        rows.append({"source_id": ident, "chapter": 2, "path": path,
                     "sha256": source_hash, "offset": token.start(),
                     "line": text.count("\n", 0, token.start())+1, "call": call, "key": key,
                     "occurrence_id": occurrence_id(2, "canonical", path, source_hash, key, token.start(), call)})
        edits += [(token.start(), token.end(), "cap_"+call), (end, end, f", {ident}")]
    # Every ordinary indexed write invalidates earlier provenance, including
    # untagged helpers and +=. Indices must be side-effect-free single values.
    # Smallface helper bodies are separate occurrences; never inherit the parent's source.
    for i, token in enumerate(tokens[:-1]):
        if token.group() != 'scr_smallface' or tokens[i+1].group() != '(' or (i and tokens[i-1].group() == 'function'):
            continue
        args, end, ok = split_args(text, tokens[i+1].start())
        if not ok or len(args) != 6: raise ValueError('Unsupported smallface helper')
        value=args[5].strip(); bound_id=0
        match=re.match(r'(stringsetloc|stringsetsubloc)\s*\(',value)
        if match:
            inner, stop, valid=split_args(value,value.index('('))
            key=as_string_literal(inner[-1]) if valid and len(inner)>=2 and not value[stop+1:].strip() else None
            if key is not None:
                offset=text.rfind(value,token.end(),end)
                if offset < 0:raise ValueError('Cannot locate smallface text expression')
                bound_id=start_id+len(rows);path=f'data/exported/code/ch2/{filename}'
                rows.append({'source_id':bound_id,'chapter':2,'path':path,'sha256':source_hash,
                    'offset':offset,'line':text.count('\n',0,offset)+1,'call':match[1],'key':key,
                    'channel':'smallface','occurrence_id':occurrence_id(2,'canonical',path,source_hash,key,offset,match[1])})
        edits += [(token.start(),token.end(),'cap_smallface'),(end,end,f', {bound_id}')]
    writes = 0
    for i in range(len(tokens)-7):
        local_dialogue = (tokens[i].group() == '_dialogue' and tokens[i+1].group() == '[' and filename in ('gml_GlobalScript_scr_recruit_info.gml','gml_Object_obj_npc_cafe_Other_10.gml'))
        if not local_dialogue and ([t.group() for t in tokens[i:i+2]] != ["global", "."] or tokens[i+2].group() not in ('msg','smstring','choicemsg','battlemsg') or tokens[i+3].group()!='['):
            continue
        field='_dialogue' if local_dialogue else tokens[i+2].group()
        small=field=='smstring'
        choice=field=='choicemsg'
        prefix='cap_dlg_' if local_dialogue else 'cap_btl_' if field=='battlemsg' else 'cap_ch_' if choice else 'cap_sm_' if small else 'cap_'
        index_start = i+2 if local_dialogue else i+4
        j = index_start
        while j < len(tokens) and tokens[j].group() != "]":
            j += 1
        if j+1 >= len(tokens) or tokens[j+1].group() not in {"=", "+="}:
            continue
        index = text[tokens[index_start].start():tokens[j].start()].strip()
        if not re.fullmatch(r"[A-Za-z_]\w*|\d+", index):
            raise ValueError(f"Side-effecting/unsupported message slot {index}")
        k, depth = j+2, 0
        while k < len(tokens):
            value = tokens[k].group()
            if value == ";" and depth == 0:
                break
            depth += value in {"(", "[", "{"}
            depth -= value in {")", "]", "}"}
            k += 1
        if k == len(tokens):
            raise ValueError("Unterminated message assignment")
        begin = tokens[j+2].start()
        # Only whole ternary leaves are bound; concatenation/functions stay unknown.
        # Each branch binds its own slot when evaluated, never an ambient last-source tag.
        if choice and tokens[j+1].group() == '=':
            nest=0;question=colon=None
            for q in range(j+2,k):
                v=tokens[q].group()
                if nest==0 and v=='?': question=q
                if nest==0 and v==':': colon=q
                nest+=v in ('(','[','{');nest-=v in (')',']','}')
            if question is not None and colon is not None and question<colon:
                for lo,hi in ((question+1,colon),(colon+1,k)):
                    a,z=tokens[lo].start(),tokens[hi].start(); sid=0
                    call=tokens[lo].group()
                    if call in ('stringsetloc','stringsetsubloc') and tokens[lo+1].group()=='(':
                        args,stop,ok=split_args(text,tokens[lo+1].start())
                        key=as_string_literal(args[-1]) if ok and len(args)>=2 and not text[stop+1:z].strip() else None
                        if key is not None:
                            sid=start_id+len(rows);path=f'data/exported/code/ch2/{filename}'
                            rows.append(dict(source_id=sid,chapter=2,path=path,sha256=source_hash,offset=a,line=text.count('\n',0,a)+1,call=call,key=key,channel='choice_option',occurrence_id=occurrence_id(2,'canonical',path,source_hash,key,a,call)))
                    edits.extend([(a,a,f'cap_ch_bind_slot({index}, '),(z,z,f', {sid})')])
                writes+=1
                continue
        bound_id = None
        if tokens[j+1].group() == "=" and tokens[j+2].group() in {"stringsetloc", "stringsetsubloc"} and tokens[j+3].group() == "(":
            args, end, ok = split_args(text, tokens[j+3].start())
            if ok and len(args) >= 2 and not text[end+1:tokens[k].start()].strip():
                key = as_string_literal(args[-1])
                if key is not None:
                    bound_id = start_id + len(rows)
                    path = f"data/exported/code/ch2/{filename}"
                    rows.append({"source_id": bound_id, "chapter": 2, "path": path,
                                 "sha256": source_hash, "offset": begin,
                                 "line": text.count("\n", 0, begin)+1, "call": tokens[j+2].group(), "key": key,
                                 "occurrence_id": occurrence_id(2,"canonical",path,source_hash,key,begin,tokens[j+2].group())})
                    if small:rows[-1]['channel']='smallface'
                    if choice:rows[-1]['channel']='choice_option'
        copy=re.fullmatch(r'global\.battlemsg\[([A-Za-z_]\w*|\d+)\]',text[begin:tokens[k].start()].strip()) if field=='msg' and tokens[j+1].group()=='=' else None
        if copy:
            edits += [(begin,begin,f'cap_btl_to_msg({index}, {copy[1]}, '),(tokens[k].start(),tokens[k].start(),')')]
        elif bound_id is None:
            edits += [(begin, begin, f"{prefix}clear_slot({index}, "),
                      (tokens[k].start(), tokens[k].start(), ")")]
        else:
            edits += [(begin, begin, f"{prefix}bind_slot({index}, "),
                      (tokens[k].start(), tokens[k].start(), f", {bound_id})")]
        writes += 1
    from .source_flow import additions
    extra, added = additions(text, filename, source_hash, start_id + len(rows))
    edits.extend(extra)
    rows.extend(added)
    for start, end, value in sorted(edits, reverse=True):
        text = text[:start] + value + text[end:]
    return text, rows, writes


def generate(root: Path, destination: Path, previous=None):
    destination.mkdir()
    rows, patches, writes = [], {}, 0
    for p in sorted(root.glob("*.gml")):
        original = p.read_text(encoding="utf-8")
        transformed, added, count = transform(original, p.name, hashlib.sha256(p.read_bytes()).hexdigest(), len(rows)+1)
        rows.extend(added)
        writes += count
        if transformed != original:
            (destination / p.name).write_text(transformed, encoding="utf-8")
            patches[p.stem] = hashlib.sha256(original.strip().encode()).hexdigest()
    if previous:
        old = {r['occurrence_id']:r['source_id'] for r in previous['sources']}
        next_id = max(old.values()) + 1
        remap = {}
        for row in rows:
            target = old.get(row['occurrence_id'])
            if target is None:
                target, next_id = next_id, next_id + 1
            remap[row['source_id']] = target
            row['source_id'] = target
        for p in destination.glob('*.gml'):
            text = p.read_text(encoding='utf-8')
            edits = []
            for m in re.finditer(r'\bcap_(?:'+'|'.join(CALLS | SUB_CALLS)+r'|bind_slot|sm_bind_slot|ch_bind_slot|dlg_bind_slot|btl_bind_slot|smallface|local_value)\s*\(', text):
                args,end,ok = split_args(text,text.index('(',m.start()))
                if not ok or not args[-1].strip().isdigit():
                    raise ValueError('Invalid injected provenance argument')
                match = re.search(r'\d+\s*$', text[:end])
                old_id=int(args[-1]);edits.append((match.start(),end,str(remap[old_id] if old_id else 0)))
            for start,end,value in sorted(edits,reverse=True): text=text[:start]+value+text[end:]
            p.write_text(text,encoding='utf-8')
    return {"schema": 1, "chapter": 2, "sources": rows, "patches": patches, "invalidated_writes": writes}


def substitution_wrappers():
    """Forward the exact original argument count; the last extra argument is only provenance."""
    result=[]
    for name, minimum in SUB_CALLS.items():
        body=f'function cap_{name}() {{\n switch (argument_count - 1) {{\n'
        for count in range(minimum,17):
            body+=f' case {count}: {name}('+', '.join(f'argument[{i}]' for i in range(count))+'); break;\n'
        body+=' }\n'
        if name.startswith('c_'):
            body+=' if (instance_exists(obj_cutscene_master)) obj_cutscene_master.cap_command[obj_cutscene_master.maximum_command - 2] = argument[argument_count - 1];\n'
        else:
            slot='argument[0]' if name.startswith('msgset') else 'global.msgno'
            body+=f' global.cap_source[{slot}] = argument[argument_count - 1];\n'
        result.append(body+'}\n')
    return '\n'.join(result)
