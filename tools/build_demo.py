"""Build a game-text excerpt preview without reading local inputs or the legacy project."""
import argparse
import json
from pathlib import Path
import re
import tempfile

from import_texts import run, sha
from build_site_data import build

ROOT = Path(__file__).resolve().parents[1]
WEB_FILES = (
    'index.html', 'style.css', 'text.js', 'model.js', 'actions.js', 'query.js',
    'app.js', 'context.js', 'search-worker.js',
    'fonts/JetBrainsMonoNL-Regular.ttf', 'fonts/OFL.txt', 'fonts/SOURCE.json',
)


def replace_one(source, pattern, replacement):
    result, count = re.subn(pattern, lambda _: replacement, source, flags=re.DOTALL)
    if count != 1:
        raise ValueError('Demo adapter no longer matches the page; review: ' + pattern)
    return result


def demo_markup(source):
    source = replace_one(source, r'<section id="restore-preview".*?</section>',
                         '<section id="restore-preview" class="restore-preview" hidden><p id="restore-text">还原模式尚在准备中；此示例不包含游戏素材。</p></section>')
    source = replace_one(source, r'<title>.*?</title>',
                         '<title>DELTARUNE Text Archive · 真实台词示例</title>')
    source = replace_one(source, r'<meta name="description"[^>]*>',
                         '<meta name="description" content="Selected game dialogue demonstration.">')
    for name in ('soul-motion.js', 'soul.js'):
        source = replace_one(source, r'<script\b[^>]*src="' + re.escape(name) + r'"[^>]*>\s*</script>', '')
    # Optional soul modules belong only to the full site, including ongoing additions.
    source = re.sub(r'<script\b[^>]*src="soul-[^"/]+\.js"[^>]*>\s*</script>', '', source)
    source = replace_one(source, r'<header\b.*?</header>', '''<header class="masthead demo-masthead">
<h1 class="demo-title">DELTARUNE Text Archive<span>真实台词示例</span></h1>
<div class="release-info"><p>40 条示例 · 五章输入格式</p><p>游戏 v0.0.253 · 汉化 V261024</p><button id="about" class="quiet">关于此示例</button></div>
</header>''')
    source = replace_one(source, r'<footer\b.*?</footer>',
                         '<footer><span>非官方项目 · 真实台词节选</span><span>游戏文本：DELTARUNE · 中文：好人汉化组</span></footer>')
    source = replace_one(source, r'<dialog id="settings-dialog".*?</dialog>', '')
    source = replace_one(source, r'<dialog id="about-dialog".*?</dialog>', '''<dialog id="about-dialog"><div class="dialog-top"><h2>关于此示例</h2><button id="close-about" class="quiet" aria-label="关闭关于">关闭</button></div>
<p>这是台词库的精简示例，选取了第 1–5 章共 40 条真实文本，可体验搜索、三语对照和中文人名译法切换。游戏版本为 v0.0.253（2026-07-31），中文翻译为好人汉化组 V261024。</p>
<p>简洁模式适合直接阅读；源码模式保留颜色、停顿等控制指令，方便核对原文。搜索会查找所有语言，不受显示语言的选择限制。</p>
<p>此示例不包含对话上下文、游戏图片和灵魂互动，“还原”模式尚未完成。部分文本可能不会在正常游玩中出现，图片和动态内容暂以文字标记代替。</p>
<p>这是非官方项目，游戏文本及中文译文属于其相应权利方。源码模式使用 <a href="fonts/OFL.txt" target="_blank" rel="noopener noreferrer">JetBrains Mono NL</a> 字体，中日文字形由系统字体补齐。</p></dialog>''')
    return source


def demo_css(source):
    source = replace_one(source, r"@font-face\s*\{[^}]*font-family:\s*'Game Main ZH'[^}]*\}", '')
    return source + '''
/* Demo-only text branding; no replacement game artwork. */
.demo-masthead { grid-template-columns: minmax(0, 1fr) auto; }
.demo-title { font: 600 clamp(22px, 3vw, 36px)/1.3 system-ui, sans-serif; margin: 0; }
.demo-title span { display: block; color: var(--muted); font-size: 18px; margin-top: 8px; }
@media (max-width: 600px) { .demo-masthead { grid-template-columns: 1fr; gap: 12px; } .demo-masthead .release-info { justify-self: start; text-align: left; } }
'''


def build_demo(root=ROOT):
    root = Path(root).resolve()
    build_dir = root / 'build'
    target = build_dir / 'open-source-demo'
    # Reject linked output directories before creating temporary data or writing files.
    if build_dir.is_symlink() or build_dir.resolve() != build_dir or target.resolve() != target:
        raise ValueError('Demo output must remain inside this project build directory')
    inputs = root / 'examples/input'
    observed = {root/'web'/name: (root/'web'/name).read_bytes() for name in WEB_FILES}
    observed.update({p: p.read_bytes() for p in inputs.glob('ch*/lang_*.json')})
    payload = {name: observed[root/'web'/name] for name in WEB_FILES}
    payload['index.html'] = demo_markup(payload['index.html'].decode('utf-8-sig')).encode('utf-8')
    payload['style.css'] = demo_css(payload['style.css'].decode('utf-8-sig')).encode('utf-8')
    if b'assets/' in payload['index.html'] or b'assets/' in payload['style.css']:
        raise ValueError('Demo still references game assets')
    build_dir.mkdir(exist_ok=True)
    # This owned temporary directory is the only cleanup target; dist is never used.
    with tempfile.TemporaryDirectory(prefix='demo-stage-', dir=build_dir) as temporary:
        stage = Path(temporary)
        if not stage.resolve().is_relative_to(build_dir):
            raise ValueError('Temporary demo directory escaped build')
        imported = run(inputs, stage/'texts')
        build(stage/'texts', stage/'data')
        for path in (stage/'data').iterdir():
            payload['data/'+path.name] = path.read_bytes()
        text_binding = sha((stage/'texts/manifest.json').read_bytes())
        payload['data/contexts.json'] = (json.dumps({
            'schema': 1, 'text_manifest_sha256': text_binding, 'scenes': [],
        }, separators=(',', ':'))+'\n').encode()
    if any(path.read_bytes() != raw for path, raw in observed.items()):
        raise ValueError('Source changed during demo build; retry after the other task finishes')
    report = {
        'kind': 'game-text-excerpts', 'rows': imported['total_rows'],
        'files': {name: sha(raw) for name, raw in sorted(payload.items())},
        'sources': {path.relative_to(root).as_posix(): sha(raw) for path, raw in observed.items()},
    }
    payload['demo-build.json'] = (json.dumps(report, indent=2)+'\n').encode()
    for path in target.rglob('*'):
        if path.is_symlink() or path.resolve() != path:
            raise ValueError('Linked output path in demo directory')
        if path.is_file() and path.relative_to(target).as_posix() not in payload:
            raise ValueError('Unexpected demo file; inspect manually: ' + str(path))
    for name in payload:
        path = target/name
        if path.resolve() != path or (path.exists() and not path.is_file()):
            raise ValueError('Unsafe demo output: ' + str(path))
    for name, raw in payload.items():
        path = target/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    print(f'Demo: {imported["total_rows"]} rows, {len(payload)} files, '
          f'{sum(map(len, payload.values()))/1024:.1f} KiB -> {target}')
    return target


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        build_demo()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SystemExit('Demo build failed: ' + str(exc))
