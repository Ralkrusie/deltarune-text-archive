"""Validate bounded draw evidence and canonicalize configurations, not animation phase."""
import json
import math
from pathlib import Path
from .store import canonical

SPEC = json.loads(Path(__file__).with_name('text-style-sites.json').read_text(encoding='utf-8'))


def validate_styles(header, detail):
    styles = detail.get('text_styles')
    if styles is None:
        if header.get('text_style_schema') == 1:
            raise ValueError('Missing instrumented text styles')
        return
    if (header.get('text_style_schema') != 1 or header.get('text_style_source_sha256') != SPEC['source_sha256']
            or styles.get('schema') != 1 or styles.get('scope') != 'ch2_obj_writer_text_calls'):
        raise ValueError('Unbound text style renderer')
    for name, cap in [('states', 128), ('spans', 8192), ('changes', 512), ('samples', 256)]:
        if not isinstance(styles.get(name), list) or len(styles[name]) > cap:
            raise ValueError('Unbounded text styles: ' + name)
    if type(styles.get('overflow')) is not bool or (styles['overflow'] and not detail['overflow']):
        raise ValueError('Invalid style overflow status')
    def number(n):
        return type(n) in (int, float) and math.isfinite(n)
    def integer(n, low, high):
        return number(n) and int(n) == n and low <= n <= high
    states = styles['states']
    for s in states:
        if not integer(s.get('site'), 1, 19) or not integer(s.get('layer'), 0, 6):
            raise ValueError('Invalid draw site/layer')
        site = s['site']
        if site != 19 and s['layer'] != 0:
            raise ValueError('Unexpected text layer')
        if 'trail_updates_observed' in s and (type(s['trail_updates_observed']) is not bool or (site != 19 and s['trail_updates_observed'])):
            raise ValueError('Invalid trail update observation')
        if not isinstance(s.get('font_name'), str) or not integer(s.get('font_id'), -1, 100000):
            raise ValueError('Invalid font')
        if not isinstance(s.get('colors_bgr'), list) or len(s['colors_bgr']) != 4 or not all(integer(c, 0, 0xffffff) for c in s['colors_bgr']):
            raise ValueError('Invalid draw colors')
        if not all(number(s.get(k)) for k in ('scale_x', 'scale_y', 'rotation', 'call_alpha', 'global_alpha', 'gain', 'shake', 'orbit_divisor')):
            raise ValueError('Invalid style parameters')
        motion = ('random_xy' if s['shake'] != 0 else 'none') if site <= 5 else 'none' if site <= 14 else 'orbit' if site <= 18 else 'drifting_trail'
        alpha = 'constant' if site <= 5 or 15 <= site <= 18 else 'gain' if site == 6 else 'glow_axial' if site <= 10 else 'glow_diagonal' if site <= 14 else 'trail_fade'
        if s.get('motion') != motion or s.get('alpha_model') != alpha or (site > 5 and s['shake'] != 0):
            raise ValueError('Unsupported motion/alpha recipe')
        divisor = {15:4, 16:5, 17:7, 18:9}.get(site, 0)
        if s['orbit_divisor'] != divisor:
            raise ValueError('Invalid orbit recipe')
    def state_id(n):
        return integer(n, 0, len(states) - 1)
    limit = min(8192, len(detail['formatted_text']))
    for span in styles['spans']:
        if (not state_id(span.get('state_index')) or not integer(span.get('start_index'), 1, limit)
                or not integer(span.get('end_index'), span['start_index'] + 1, limit + 1)):
            raise ValueError('Invalid text style span')
    for change in styles['changes']:
        if not integer(change.get('formatted_index'), 1, limit) or not all(state_id(change.get(k)) for k in ('from_state','to_state')):
            raise ValueError('Invalid style change')
        before, after = (states[int(change[k])] for k in ('from_state', 'to_state'))
        if (before['site'], before['layer']) != (after['site'], after['layer']):
            raise ValueError('Cross-layer style change')
    counts = {}
    for sample in styles['samples']:
        if (not state_id(sample.get('state_index')) or not integer(sample.get('formatted_index'), 1, limit)
                or not all(number(sample.get(k)) for k in ('draw','offset_x','offset_y','alpha','phase'))):
            raise ValueError('Invalid style sample')
        index = sample['state_index']
        counts[index] = counts.get(index, 0) + 1
        if counts[index] > 2:
            raise ValueError('Unbounded per-state samples')


def style_body(header, detail):
    if not detail or 'text_styles' not in detail:
        return {}
    styles = detail['text_styles']
    unique = sorted({canonical(s) for s in styles['states']})
    remap = {i: unique.index(canonical(s)) for i, s in enumerate(styles['states'])}
    spans = sorted({canonical(dict(s, state_index=remap[s['state_index']])) for s in styles['spans']})
    # Change order is semantic. Draw numbers and phase samples are raw-event diagnostics.
    changes = [dict(s, from_state=remap[s['from_state']], to_state=remap[s['to_state']]) for s in styles['changes']]
    return {'text_styles': {'schema':1, 'scope':styles['scope'], 'source_sha256':header['text_style_source_sha256'],
        'states':[json.loads(s) for s in unique], 'spans':[json.loads(s) for s in spans],
        'changes':changes, 'overflow':styles['overflow']}}


def styles_summary(body):
    if 'text_styles' not in body:
        return '颜色／运动：旧记录未采集。'
    styles = body['text_styles']
    if not styles['states']:
        return '颜色／运动：未观察到文字绘制，不能判断无效果。'
    colors = sorted({f'#{int(c)&255:02X}{(int(c)>>8)&255:02X}{(int(c)>>16)&255:02X}'
                     for s in styles['states'] for c in s['colors_bgr']})
    labels = {'none':'位置固定', 'random_xy':'随机抖动', 'orbit':'环绕运动', 'drifting_trail':'漂移拖影'}
    effects = sorted({labels[s['motion']] for s in styles['states']})
    if any(s['site']==19 and not s.get('trail_updates_observed',False) for s in styles['states']):
        effects.append('拖影偏移更新未观察到（有 n==1 条件）')
    if any(s['alpha_model'].startswith('glow_') for s in styles['states']): effects.append('透明度脉动发光')
    return f"实际绘制颜色：{'、'.join(colors)}；效果：{'、'.join(effects)}；{len(styles['states'])} 种层配置、{len(styles['changes'])} 次参数变化。" + ('达到采集上限，部分记录。' if styles['overflow'] else '')
