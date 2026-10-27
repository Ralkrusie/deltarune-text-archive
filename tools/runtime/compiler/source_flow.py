"""Bounded local value provenance, never a last-string lookup or text match."""
import re
from .syntax import TOKEN, split_args, as_string_literal, occurrence_id


def additions(text, filename, source_hash, first_id):
    tokens = [t for t in TOKEN.finditer(text) if not t.group().startswith(('//', '/*'))]
    edits, rows = [], []
    path = 'data/exported/code/ch2/' + filename

    def bind_leaf(lo, hi, tag):
        value = text[lo:hi].strip()
        match = re.match(r'(stringsetloc|stringsetsubloc)\s*\(', value)
        if not match:
            return None
        args, end, ok = split_args(value, value.index('('))
        key = as_string_literal(args[-1]) if ok and len(args) >= 2 and not value[end+1:].strip() else None
        if key is None:
            return None
        offset = lo + len(text[lo:hi]) - len(text[lo:hi].lstrip())
        sid = first_id + len(rows)
        rows.append(dict(source_id=sid, chapter=2, path=path, sha256=source_hash,
                         offset=offset, line=text.count('\n',0,offset)+1, call=match[1], key=key,
                         occurrence_id=occurrence_id(2,'canonical',path,source_hash,key,offset,match[1])))
        return [(lo,lo,f'cap_local_value({tag}, '),(hi,hi,f', {sid})')]

    # Shared item helper: tag the two actual template branches before suffixing.
    # The wrapper copies its return tag immediately, before any other game call.
    if filename == 'gml_GlobalScript_scr_itemget_anytype_text.gml':
        anchor = 'var itemgetstring = "";'
        if text.count(anchor)!=1 or text.count('return itemgetstring;')!=1:
            raise ValueError('Item template contract changed')
        pos=text.index(anchor)
        edits.append((pos,pos,'var cap_item_tag = {source: 0};\n'))
        for match in re.finditer(r'itemgetstring = (stringsetsubloc\([^\n]+\));',text):
            leaf=bind_leaf(match.start(1),match.end(1),'cap_item_tag')
            if leaf is None: raise ValueError('Unsupported item template')
            edits.extend(leaf)
        if len(rows)!=2: raise ValueError('Expected two item result templates')
        pos=text.index('return itemgetstring;')
        edits.append((pos,pos,'global.cap_item_return_source = cap_item_tag.source;\n'))
        return edits, rows

    # Restrict to a single var declaration, used unchanged within its enclosing block.
    # Any assignment, shadowing or increment in that region leaves the entire use unknown.
    braces=[]; enclosing={}; ends={}
    for i,t in enumerate(tokens):
        enclosing[i]=braces[-1] if braces else -1
        if t.group()=='{':braces.append(i)
        elif t.group()=='}' and braces: ends[braces.pop()]=i
    for i,t in enumerate(tokens[:-4]):
        if t.group()!='var' or not re.fullmatch(r'[A-Za-z_]\w*',tokens[i+1].group()) or tokens[i+2].group()!='=':
            continue
        if i and tokens[i-1].group() not in ('{','}',';',':'):
            continue  # Do not split a single unbraced conditional statement.
        name=tokens[i+1].group(); block_end=ends.get(enclosing[i],len(tokens))
        if any(q.group()=='function' for q in tokens[i+1:block_end]):
            continue  # Nested closures need a separate scope analysis.
        depth=0;j=i+3
        while j<block_end:
            v=tokens[j].group()
            if v==';' and depth==0:break
            depth+=v in ('(','[');depth-=v in (')',']');j+=1
        if j>=block_end:continue
        if any(tokens[q].group()==name and (tokens[q+1].group() in ('=','+=','-=','++','--','*=','/=') or tokens[q-1].group() in ('var','++','--')) for q in range(j+1,block_end-1)):
            continue
        consumers=[]
        for q in range(j+1,block_end-1):
            call=tokens[q].group()
            if call not in ('msgset','msgnext') or tokens[q+1].group()!='(':continue
            args,end,ok=split_args(text,tokens[q+1].start())
            index=1 if call=='msgset' else 0
            if ok and len(args)==index+1 and args[index].strip()==name:
                consumers.append((tokens[q].start(),tokens[q].end(),'cap_local_'+call))
                consumers.append((end,end,', cap_tag_'+str(t.start())))
        if not consumers:continue
        lo,hi=tokens[i+3].start(),tokens[j].start();value=text[lo:hi].strip();tag='cap_tag_'+str(t.start())
        local=[]; old_count=len(rows)
        if value.startswith('scr_itemget_anytype_text('):
            args,end,ok=split_args(value,value.index('('))
            if not ok or value[end+1:].strip() or len(args) not in (2,3):continue
            local=[(lo,lo+len('scr_itemget_anytype_text'),'cap_local_itemget'),(lo+len('scr_itemget_anytype_text('),lo+len('scr_itemget_anytype_text('),tag+', ')]
        else:
            depth=0; question=colon=None
            for q in range(i+3,j):
                v=tokens[q].group()
                if depth==0 and v=='?':question=q
                if depth==0 and v==':':colon=q
                depth+=v in ('(','[');depth-=v in (')',']')
            ranges=[(lo,hi)] if question is None else [(tokens[question+1].start(),tokens[colon].start()),(tokens[colon+1].start(),hi)] if colon else []
            for a,b in ranges:
                leaf=bind_leaf(a,b,tag)
                if leaf is None:local=[];rows[old_count:]=[];break
                local.extend(leaf)
        if local:
            edits.extend([(t.start(),t.start(),f'var {tag} = {{source: 0}};\n'),*local,*consumers])
    return edits,rows
