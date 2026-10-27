"""Versioned review interpretation; immutable legacy observations are never rewritten."""
import re

VERSION = 'review-evidence-1'


def interpret(body):
    control = not re.sub(r'\\[A-Za-z][A-Za-z0-9]|[\s/%]', '', body['text'])
    kind = 'child_container' if control and body.get('smallfaces') else 'control' if control else 'text'
    identity=body.get('identity',{})
    states=identity.get('states',[])
    portrait_codes={a['face_code'] for a in body.get('assets',[]) if a.get('role')=='portrait' and 'face_code' in a}
    # Require every positive identity state to be supported by an actual portrait draw.
    # Mixed/unobserved states remain unknown, rather than selecting a convenient subset.
    codes={s['face_code'] for s in states if s.get('face_code')}
    raw=identity.get('candidates',[])
    backed=bool(raw and codes and codes.issubset(portrait_codes) and kind=='text')
    return dict(version=VERSION,kind=kind,
                identity_status='portrait_supported' if backed else 'not_applicable' if kind!='text' else 'unknown',
                candidates=raw if backed else [],raw_candidates=raw,
                suppressed=bool(raw and not backed and kind=='text'),
                issues=(['source_unknown'] if not body.get('occurrence_id') and kind=='text' else [])+
                       (['unbacked_face_state'] if raw and not backed and kind=='text' else [])+
                       (['partial_page'] if not body.get('coverage',{}).get('page_closed') else []))
