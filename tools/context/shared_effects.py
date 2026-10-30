"""Bounded effects for sequential shared-script answer tests.

This proves that construction of a response leaves the selected answer intact.
It does not execute dialogue control strings or follow another object's state.
Helper definitions and their dependencies are checked in the current chapter.
"""
import re


PURE_BUILTINS={'string','string_length','string_replace_all','array_length_1d',
               'instance_exists','variable_global_exists','is_undefined',
               'abs','min','max','floor','ceil','round','is_real','chr','string_lower'}
GLOBAL_SCALARS={'fc','fe','typer','gold','msgno'}
GLOBAL_ARRAYS={'msg','flag','writersnd'}


class SharedEffects:
    def __init__(self,analyzer):
        self.a=analyzer;self.reason='';self.used=set();self.cache={};self.checking=set()

    def fail(self,reason):
        self.reason=reason;return False

    def tokens(self,text):
        return [t.group() for t in self.a.flow.TOKEN.finditer(text) if not t.group().startswith(('//','/*'))]

    def compact(self,text):return ''.join(self.tokens(text))

    def function(self,name):
        # A preferred filename alone is insufficient if another script defines
        # the same function. Cache this chapter's definition inventory.
        index=getattr(self.a,'_shared_effect_functions',None)
        if index is None:
            index={}
            for filename in self.a.sources:
                if not filename.startswith('gml_GlobalScript_'):continue
                source=self.a.sources[filename]
                tokens=self.tokens(source)
                for i,t in enumerate(tokens[:-2]):
                    if t=='function' and tokens[i+2]=='(':
                        index.setdefault(tokens[i+1],[]).append(filename)
                if hasattr(self.a.sources,'loaded') and filename not in self.a.cache:
                    self.a.sources.loaded.pop(filename,None)
            self.a._shared_effect_functions=index
        names=index.get(name,[])
        if len(names)!=1:return None
        filename=names[0];data=self.a.file(filename)
        functions=[n for n in data['nodes'] if n.kind=='function' and re.match(re.escape(name)+r'\s*\(',n.text)]
        if len(functions)!=1 or len(data['nodes'])!=1:return None
        return filename,functions[0],data['source']

    def exact(self,fn,expected):
        return self.compact(fn[2][fn[1].start:fn[1].end])==self.compact(expected)

    def helper(self,name):
        if name in self.cache:
            proof=self.cache[name]
            if proof is None:return False
            self.used.update(proof);return True
        if name in self.checking:return False
        fn=self.function(name)
        if not fn:self.cache[name]=None;return False
        previous=self.used;self.used={fn[0]};self.checking.add(name)
        try:ok=self.check_helper(name,fn)
        finally:self.checking.remove(name)
        proof=set(self.used) if ok else None
        self.used=previous;self.cache[name]=proof
        if ok:self.used.update(proof)
        return ok

    def check_helper(self,name,fn):
        templates={
            'scr_anyface_next':('function scr_anyface_next(arg0,arg1){global.msgno++;scr_anyface(arg0,global.msgno,arg1);}',('scr_anyface',)),
            'msgsetsub':('function msgsetsub(){var len=argument_count;var args;for(var i=0;i<len;i++)args[i]=argument[i];var str=substringargs(argument[1],2,args);msgset(argument[0],str);}',('substringargs','msgset')),
            'msgsetsubloc':('function msgsetsubloc(){var len=argument_count;var args;for(var i=0;i<len;i++)args[i]=argument[i];var msg_index=argument[0];var format_string=argument[1];var localized_format_string_id=argument[len-1];if(!is_english())format_string=scr_84_get_lang_string(localized_format_string_id);var str=substringargs(format_string,2,args);msgset(msg_index,str);}',('is_english','scr_84_get_lang_string','substringargs','msgset')),
            'stringset':('function stringset(arg0){return arg0;}',()),
            'is_english':('function is_english(){return !variable_global_exists("lang")||global.lang=="en";}',()),
            'stringsetloc':('function stringsetloc(arg0,arg1){var str=arg0;if(!is_english())str=scr_84_get_lang_string(arg1);return stringset(str);}',('is_english','scr_84_get_lang_string','stringset')),
            'substringargs':('function substringargs(arg0,arg1,arg2){var str=arg0;var offset=arg1;var args=arg2;var sub_id=1;var num_args=array_length_1d(args);var len=(num_args-offset)+1;while(sub_id<len){var sub="~"+string(sub_id);var ndx=(sub_id+offset)-1;str=string_replace_all(str,sub,args[ndx]);sub_id=sub_id+1;}return str;}',()),
            'stringsetsubloc':('function stringsetsubloc(){var len=argument_count;var args;for(var i=0;i<len;i++)args[i]=argument[i];var format_string=argument[0];var localized_format_string_id=argument[len-1];if(!is_english())format_string=scr_84_get_lang_string(localized_format_string_id);var str=substringargs(format_string,1,args);return stringset(str);}',('is_english','scr_84_get_lang_string','substringargs','stringset')),
            # The CH1 substitution helper also writes instance length/pos.
            # Those writes are explicit in this exact template, not hidden purity.
            'scr_84_get_subst_string':('function scr_84_get_subst_string(){var str=argument[0];var sub_id=1;length=string_length(str);pos=0;while(sub_id<argument_count){var sub="~"+string(sub_id);str=string_replace_all(str,sub,argument[sub_id]);sub_id=sub_id+1;}return str;}',()),
            'msgset':('function msgset(arg0,arg1){global.msgno=arg0;global.msg[arg0]=arg1;}',()),
            'msgnext':('function msgnext(arg0){global.msgno++;msgset(global.msgno,arg0);}',('msgset',)),
            'msgsetloc':('function msgsetloc(arg0,arg1,arg2){var msg_index=arg0;var str=arg1;var localized_string_id=arg2;if(!is_english())str=scr_84_get_lang_string(localized_string_id);msgset(msg_index,str);}',('is_english','scr_84_get_lang_string','msgset')),
            'msgnextloc':('function msgnextloc(arg0,arg1){var str=arg0;var localized_string_id=arg1;if(!is_english())str=scr_84_get_lang_string(localized_string_id);msgnext(str);}',('is_english','scr_84_get_lang_string','msgnext')),
            'scr_flag_get':('function scr_flag_get(arg0){return global.flag[arg0];}',()),
        }
        if name=='scr_84_get_lang_string':
            simple='function scr_84_get_lang_string(arg0){return ds_map_find_value(global.lang_map,arg0);}'
            base='function scr_84_get_lang_string(arg0){var lang_string_id=arg0;var str=ds_map_find_value(global.lang_map,lang_string_id);if(is_undefined(str)){if(!ds_map_find_value(global.lang_missing_map,lang_string_id))ds_map_add(global.lang_missing_map,lang_string_id,true);str="--missing-string--";}return str;}'
            log='show_debug_message("ERROR: string id "+lang_string_id+" for language "+global.lang+" is missing");'
            logged=base.replace('ds_map_add(global.lang_missing_map,lang_string_id,true);','{ds_map_add(global.lang_missing_map,lang_string_id,true);'+log+'}')
            return any(self.exact(fn,body) for body in (simple,base,logged,logged.replace('+lang_string_id+','+string(lang_string_id)+')))
        if name in templates:
            body,deps=templates[name]
            return self.exact(fn,body) and all(self.helper(dep) for dep in deps)
        if name=='scr_speaker':
            if self.compact(fn[1].text)!='scr_speaker(arg0)':return False
            return self.safe(fn[1].children,targets={'_speaker','global.fc','global.fe','global.typer'})
        if name=='scr_anyface':
            if self.compact(fn[1].text)!='scr_anyface(arg0,arg1,arg2)':return False
            return self.safe(fn[1].children)
        if re.fullmatch(r'scr_\w*face',name):
            if self.compact(fn[1].text) not in (name+'(arg0)',name+'(arg0,arg1)'):return False
            return self.safe(fn[1].children,targets={'global.msg[arg0]'})
        return False

    def expression(self,text,allow_prompt=False):
        tokens=self.tokens(text)
        if any(t in ('function','new','delete','return','exit','globalvar','var','self','other',
                     '=','+=','-=','*=','/=','++','--',';',':','{','}','@','$','?') for t in tokens):
            return self.fail('effectful_expression')
        # No qualified/method calls, invoked array entries or computed functions.
        for i,t in enumerate(tokens):
            if t=='(' and i and (tokens[i-1] in (')',']') or i>1 and tokens[i-2]=='.'):
                return self.fail('indirect_call')
            literal=self.a.gml.as_string_literal(t)
            if literal is not None and not allow_prompt:
                original=self.a.tables.get(literal,{}).get('en') or literal
                if re.search(r'\\C[1-4]',original):return self.fail('new_choice_prompt')
        for call in self.a.calls(text):
            name=call['call']
            if name in PURE_BUILTINS:continue
            if name not in ('stringset','stringsetloc','stringsetsubloc','scr_84_get_lang_string',
                            'scr_84_get_subst_string','scr_flag_get') or not self.helper(name):
                return self.fail('unproved_expression_call:'+name)
        return True

    def safe(self,nodes,allow_options=False,targets=None):
        for n in self.a.flat(nodes):
            if n.kind=='if':
                if not self.expression(n.text) or not self.safe(n.children,allow_options,targets) or not self.safe(n.other,allow_options,targets):return False
                continue
            if n.kind!='stmt':return self.fail('unsupported_effect_scope:'+n.kind)
            text=n.text.strip()
            assignment=re.fullmatch(r'(?:var\s+)?([\w.]+(?:\[[^\]]+\])?)\s*(=|\+=|-=|\*=|/=)\s*([\s\S]+);',text)
            if assignment:
                lhs,op,rhs=assignment.groups();lhs=self.compact(lhs)
                if targets is not None:
                    allowed=lhs in targets and op=='='
                elif '.' not in lhs and '[' not in lhs:
                    allowed=bool(re.fullmatch(r'\w+',lhs) and lhs not in PURE_BUILTINS|{'global','self','other','argument','argument_count','choice','choicemsg','msc'}
                                 and not lhs.startswith(('scr_','c_','msg','string','arg')))
                else:
                    scalar=re.fullmatch(r'global\.(\w+)',lhs)
                    array=re.fullmatch(r'global\.(\w+)\[(\d+)\]',lhs)
                    allowed=bool(scalar and scalar[1] in GLOBAL_SCALARS or array and array[1] in GLOBAL_ARRAYS|({'choicemsg'} if allow_options else set()))
                if not allowed:return self.fail('unproved_assignment:'+lhs)
                if not self.expression(rhs,allow_prompt=allow_options):return False
                continue
            calls=list(self.a.calls(text));direct=calls[0] if calls else None
            if targets is not None or not direct or direct['offset']!=0 or self.compact(text[direct['end']:])!=';':
                return self.fail('unsupported_effect_statement')
            if any(not self.expression(arg,allow_prompt=allow_options) for arg in direct['args']):return False
            if not self.helper(direct['call']):return self.fail('unproved_call:'+direct['call'])
        return True

    def proof(self):
        return [{'file':name,'sha256':self.a.file(name)['hash']} for name in sorted(self.used)]
