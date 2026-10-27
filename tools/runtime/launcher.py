"""Launch a verified portable copy and recover/export only its three capture streams."""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid

CREATE_SUSPENDED = 0x00000004  # Win32 flag; not exported by Python subprocess.


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as src:
        for block in iter(lambda: src.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def under(root, relative):
    plain(root)
    root = Path(root).resolve(strict=True)
    if not isinstance(relative, str) or '\\' in relative or ':' in relative:
        raise ValueError('Invalid relative file name')
    path = root / relative
    if not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('Invalid relative file name')
    for part in [path, *path.parents]:
        if part == root:
            break
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Redirected path is not allowed')
    if not path.resolve().is_relative_to(root):
        raise ValueError('Path escapes installation')
    return path


def plain(path):
    path = Path(path).absolute()
    for p in (path, *path.parents):
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise ValueError('Redirected path is not allowed: ' + str(p))
    return path


def load_install(root, verify=True):
    root = plain(root).resolve(strict=True)
    data = json.loads(under(root, 'capture.json').read_text(encoding='utf-8'))
    if data.get('schema') != 1 or data.get('kind') != 'portable_runtime_capture':
        raise ValueError('Not a portable capture installation')
    if data.get('profile') != 'DELTARUNE_CAPTURE_EN_FULL_D203' or data.get('chapters') != [2]:
        raise ValueError('Unsupported capture profile or chapter')
    if data.get('startup') != 'game/DELTARUNE.exe' or data.get('language') != 'en':
        raise ValueError('Unsupported game entry/language')
    if not isinstance(data.get('outputs'), dict) or data['startup'] not in data['outputs']:
        raise ValueError('Missing game output manifest')
    for name, expected in data['outputs'].items():
        p = under(root, name)
        if verify and (not p.is_file() or sha(p) != expected):
            raise ValueError('Capture game was changed: ' + name)
    if sha(under(root, 'sources.json')) != data.get('source_manifest'):
        raise ValueError('Source inventory changed')
    return data


def save_roots(profile, root=None):
    if root is not None:
        return [under(root, 'saves/' + profile)]
    # Actual per-machine paths, never the original builder's manifest paths.
    roots = [Path(os.environ['LOCALAPPDATA']) / profile,
             Path(os.environ['USERPROFILE']) / 'AppData/Local' / profile]
    return list(dict.fromkeys(plain(p) for p in roots))


def snapshot(root):
    root = Path(root)
    if not root.exists():
        return {}
    if root.is_symlink() or (hasattr(root, 'is_junction') and root.is_junction()):
        raise ValueError('Redirected save folder')
    result = {}
    for p in root.rglob('*'):
        if p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction()):
            raise ValueError('Redirected save file')
        if p.is_file():
            result[p.relative_to(root).as_posix()] = sha(p)
    return result


class Accounting(ctypes.Structure):
    _fields_ = [(n, ctypes.c_int64) for n in ('user', 'kernel', 'period_user', 'period_kernel')] + [
        (n, wintypes.DWORD) for n in ('faults', 'total', 'active', 'terminated')]


class GameJob:
    """Assign the suspended launcher before allowing any chapter child to start."""
    def __init__(self, process):
        self.api = ctypes.WinDLL('kernel32', use_last_error=True)
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.QueryInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p]
        self.api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle or not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            error = ctypes.get_last_error()
            process.kill()
            self.close()
            raise ctypes.WinError(error)
        nt = ctypes.WinDLL('ntdll')
        nt.NtResumeProcess.argtypes = [wintypes.HANDLE]
        nt.NtResumeProcess.restype = wintypes.LONG
        if nt.NtResumeProcess(int(process._handle)) != 0:
            self.api.TerminateJobObject(self.handle, 1)
            self.close()
            raise OSError('Could not resume isolated game')

    def wait(self, timeout=None):
        start = time.monotonic()
        while True:
            info = Accounting()
            if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(info), ctypes.sizeof(info), None):
                raise ctypes.WinError(ctypes.get_last_error())
            if info.active == 0:
                return False, info.total
            if timeout is not None and time.monotonic() - start >= timeout:
                self.api.TerminateJobObject(self.handle, 1)
                return True, info.total
            time.sleep(0.2)

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None

    def terminate(self):
        if self.handle:
            self.api.TerminateJobObject(self.handle, 1)


class ProfileLock:
    def __init__(self, profile, root=None):
        import msvcrt
        path = under(root, '.capture.lock') if root is not None else plain(Path(os.environ['LOCALAPPDATA']) / (profile + '.launcher.lock'))
        self.file = path.open('a+b')
        self.file.seek(0)
        if not self.file.read(1):
            self.file.write(b'0'); self.file.flush()
        self.file.seek(0)
        try:
            msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.file.close()
            raise ValueError('Another capture launcher is already using this isolated profile')

    def close(self):
        self.file.close()


def collect(root, run_id, roots=None, cleanup=True, _locked=False):
    root = plain(root).resolve(strict=True)
    if _locked:
        return _collect(root, run_id, roots, cleanup)
    lock = ProfileLock(load_install(root, verify=False)['profile'], root)
    try:
        return _collect(root, run_id, roots, cleanup)
    finally:
        lock.close()


def _restore_export(root, session, run_id):
    """A verified archive is the recoverable raw record after JSONL cleanup."""
    from .bundles import _read_bundle
    receipt = under(root, 'sessions/' + run_id + '/collection.json')
    if not receipt.exists():
        return
    saved = json.loads(receipt.read_text(encoding='utf-8'))
    name = saved.get('export_name') or Path(saved.get('export_file', '')).name
    if not name or Path(name).name != name:
        raise ValueError('Invalid archived export receipt')
    archive = under(root, 'exports/' + name)
    if saved.get('export_sha256') and sha(archive) != saved['export_sha256']:
        raise ValueError('Archived ZIP changed; JSONL cleanup/recovery stopped')
    manifest, files = _read_bundle(archive)
    if manifest['run_id'] != run_id or manifest['bundle_id'] != saved.get('bundle_id'):
        raise ValueError('Archived ZIP does not match this session')
    for name, raw in files.items():
        dest = under(root, 'sessions/' + run_id + '/' + name)
        if dest.exists():
            current = dest.read_bytes()
            if current.startswith(raw):
                continue
            if not raw.startswith(current):
                raise ValueError('Recovered log conflicts with archived bytes: ' + name)
        dest.write_bytes(raw)


def cleanup_archived(root, run_id, archive, folders):
    """Delete only this run's exact bytes already verified inside its closed ZIP."""
    from .bundles import _read_bundle, NAME
    manifest, files = _read_bundle(archive)
    if manifest['run_id'] != run_id:
        raise ValueError('Cleanup archive run mismatch')
    candidates = []
    for folder in dict.fromkeys(plain(p) for p in folders):
        if not folder.exists():
            continue
        for p in folder.glob('*.jsonl'):
            plain(p)
            match = NAME.fullmatch(p.name)
            if match is None or match.group(2) != run_id:
                continue
            if p.name not in files or p.read_bytes() != files[p.name]:
                return {'deleted_jsonl': 0, 'warnings': ['导出后日志发生变化，保留全部 JSONL，稍后重新导出。']}
            candidates.append(p)
    removed, warnings = 0, []
    for p in candidates:
        try:
            if p.read_bytes() != files[p.name]:
                warnings.append('日志仍在变化，未删除：' + p.name)
                continue
            p.unlink()
            removed += 1
        except OSError:
            warnings.append('JSONL 暂未清理：' + p.name)
    return {'deleted_jsonl': removed, 'warnings': warnings}


def _collect(root, run_id, roots, cleanup):
    """Recover a run without requiring a normal game exit; never copy save files."""
    from .bundles import export_bundle
    root = plain(root).resolve(strict=True)
    meta = load_install(root, verify=False)
    if not re.fullmatch('[a-f0-9]{32}', run_id):
        raise ValueError('Invalid run ID')
    session = under(root, 'sessions/' + run_id)
    session.mkdir(parents=True, exist_ok=True)
    _restore_export(root, session, run_id)
    pattern = re.compile(r'(capture|interactions|choices)_' + run_id + r'_[a-f0-9]{32}\.jsonl')
    folders = list(roots) if roots is not None else save_roots(meta['profile'], root)
    for folder in folders:
        folder = plain(folder)
        for src in folder.glob('*_' + run_id + '_*.jsonl'):
            if not pattern.fullmatch(src.name) or src.is_symlink():
                continue
            dest = under(root, 'sessions/' + run_id + '/' + src.name)
            if dest.exists():
                old, new = dest.read_bytes(), src.read_bytes()
                if new == old:
                    continue
                if not new.startswith(old):
                    raise ValueError('Recovered log conflicts with prior bytes: ' + src.name)
                # A completed earlier snapshot is retained in its immutable ZIP.
            shutil.copy2(src, dest)
    logs = list(session.glob('capture_*.jsonl'))
    if not logs:
        return {'run_id': run_id, 'status': 'no_ch2_capture', 'messages': 0,
                'warnings': ['没有找到第二章记录；其他章节尚未适配。']}
    # Known build provenance, independent of what a participant's log claims.
    for log in logs:
        h = json.loads(log.read_bytes().splitlines()[0])
        for key in ('source_manifest', 'collector_sha256'):
            if h.get(key) != meta.get(key):
                raise ValueError('Log does not belong to this capture build: ' + key)
        if h.get('run_id') != run_id:
            raise ValueError('Log run ID mismatch')
    exports = under(root, 'exports')
    exports.mkdir(exist_ok=True)
    # Recovery can contain more observations than the earlier export; keep both snapshots.
    combined = hashlib.sha256(b''.join(p.read_bytes() for p in sorted(session.glob('*.jsonl')))).hexdigest()[:12]
    output = exports / (run_id + '-' + combined + '.zip')
    from .bundles import _read_bundle
    report = None
    if output.exists():
        manifest, archived = _read_bundle(output)
        current = {p.name: p.read_bytes() for p in session.glob('*.jsonl')}
        if archived != current:
            raise ValueError('Existing ZIP conflicts with this export; originals preserved')
        report = dict(bundle_id=manifest['bundle_id'], run_id=run_id, bytes=output.stat().st_size,
                      summary=manifest['summary'])
    if report is None:
        report = export_bundle(session, root / 'sources.json', output)
    with output.open('r+b') as finished:
        finished.flush(); os.fsync(finished.fileno())
    manifest, archived = _read_bundle(output)
    if manifest['bundle_id'] != report['bundle_id'] or archived != {p.name: p.read_bytes() for p in session.glob('*.jsonl')}:
        raise ValueError('ZIP readback failed; originals preserved')
    report.update(run_id=run_id, export_file=str(output), export_name=output.name,
                  export_sha256=sha(output), status='exported')
    receipt = under(root, 'sessions/' + run_id + '/collection.json')
    receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    if cleanup:
        report['cleanup'] = cleanup_archived(root, run_id, output, [session, *folders])
        report['warnings'] = report['cleanup']['warnings']
        receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def launch(root, smoke=False, mechanism=False, mechanism_pace='choices'):
    if os.name != 'nt':
        raise ValueError('The participant launcher supports Windows only')
    root = plain(root).resolve(strict=True)
    meta = load_install(root)
    if mechanism and not smoke:
        raise ValueError('Mechanism fixtures require bounded smoke mode')
    if meta.get('save_layout') != 'local_appdata_v1':
        raise ValueError('旧采集副本需要先迁入本地存档布局；请使用“迁入已有副本”。')
    save_roots(meta['profile'], root)  # Reject redirected save paths before the game can write.
    under(root, 'saves').mkdir(exist_ok=True)
    lock = ProfileLock(meta['profile'], root)
    proc = job = None
    game_exited = False
    try:
        run = uuid.uuid4().hex
        session = under(root, 'sessions/' + run)
        session.mkdir(parents=True)
        original_roots = list(dict.fromkeys([Path(os.environ['USERPROFILE']) / 'AppData/Local/DELTARUNE',
                                           Path(os.environ['LOCALAPPDATA']) / 'DELTARUNE']))
        before = [snapshot(p) for p in original_roots]
        under(root, 'last-run.json').write_text(json.dumps({'run_id': run, 'state': 'running'}), encoding='utf-8')
        env = dict(os.environ, DR_CAPTURE_SESSION=run, DR_CAPTURE_SMOKE='1' if smoke else '0',
                   DR_CAPTURE_MECHANISM_TEST='1' if mechanism else '0',
                   DR_CAPTURE_TEST_PACE=mechanism_pace if mechanism else '',
                   LOCALAPPDATA=str(under(root, 'saves')))
        command = [str(root / meta['startup'])]
        cwd = root / 'game'
        if mechanism:
            cwd = cwd / 'chapter2_windows'
            command += ['-game', str(cwd / 'data.win'), 'launcher']
        with under(root, 'sessions/' + run + '/runner.log').open('wb') as log:
            proc = subprocess.Popen(command, cwd=cwd, env=env,
                                    stdout=log, stderr=subprocess.STDOUT,
                                    creationflags=CREATE_SUSPENDED)
            job = GameJob(proc)
            timed_out, processes = job.wait(45 if smoke else None)
            proc.wait(timeout=5)
            game_exited = True
        unchanged = before == [snapshot(p) for p in original_roots]
        report = collect(root, run, _locked=True)
        report.update(original_saves_unchanged=unchanged, exit_code=proc.returncode,
                      timed_out=timed_out, process_count=processes, smoke_only=smoke,
                      mode='mechanism_selftest' if mechanism else 'natural_play_pilot')
        if not unchanged:
            report.setdefault('warnings', []).append('原版存档摘要发生变化，请核对是否同时运行了原版游戏。')
        under(root, 'sessions/' + run + '/launch-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        under(root, 'last-run.json').write_text(json.dumps({'run_id': run, 'state': 'exited'}), encoding='utf-8')
        return report
    finally:
        try:
            if job:
                try:
                    if not game_exited:
                        job.terminate()
                        if proc:
                            proc.wait(timeout=5)
                finally:
                    job.close()
            elif proc and proc.poll() is None:
                proc.kill()
        finally:
            lock.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['launch', 'recover', 'check'])
    p.add_argument('--capture', required=True, type=Path)
    p.add_argument('--run')
    p.add_argument('--smoke', action='store_true')
    p.add_argument('--mechanism', action='store_true', help='Run bounded CH2 choice fixtures with --smoke')
    a = p.parse_args()
    if a.action == 'launch':
        result = launch(a.capture, a.smoke, a.mechanism)
    elif a.action == 'check':
        result = load_install(a.capture)
    else:
        run = a.run or json.loads((a.capture / 'last-run.json').read_text(encoding='utf-8'))['run_id']
        result = collect(a.capture, run)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
