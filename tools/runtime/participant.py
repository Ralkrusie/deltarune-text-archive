"""Small Windows participant UI; also the frozen executable entry point."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from tools.runtime.kit import install_kit
from tools.runtime.launcher import launch, collect, load_install
from tools.runtime.layout import migrate_capture


def home():
    return Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parents[2]


class Participant:
    def __init__(self, root, kit):
        self.root, self.kit = root, Path(kit)
        self.tasks = queue.Queue()
        self.busy = False
        self.capture_home = home() / 'capture'
        self.capture = tk.StringVar(value=str(self.capture_home) if (self.capture_home / 'capture.json').is_file() else '')
        self.status = tk.StringVar(value='游戏、存档和采集数据统一保存在工具旁的 capture 文件夹。')
        self.last_export = None
        revision = json.loads((self.kit / 'kit.json').read_text(encoding='utf-8'))['revision']
        root.title(f'DELTARUNE 第二章协作采集 · r{revision} 便携版')
        root.geometry('720x520')
        root.minsize(620, 460)
        frame = ttk.Frame(root, padding=20)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='第二章协作采集', font=('Microsoft YaHei UI', 18, 'bold')).pack(anchor='w')
        ttk.Label(frame, text='英文原版 · 独立存档 · 退出后自动导出记录', padding=(0, 5)).pack(anchor='w')
        ttk.Label(frame, text='目前只采第二章。HP 上限 999；Ctrl 连翻关闭；X 快现保留。\n'
                  '需要匹配版本的完整原版游戏；工具会检查版本，并创建完整副本。',
                  justify='left', wraplength=650, padding=(0, 8)).pack(anchor='w')
        self.buttons = []
        bar = ttk.Frame(frame); bar.pack(fill='x', pady=5)
        self.button(bar, '1. 准备新的采集副本', self.install).pack(side='left', padx=(0, 8))
        self.button(bar, '迁入已有采集副本', self.choose).pack(side='left')
        ttk.Label(frame, textvariable=self.capture, wraplength=650).pack(anchor='w', pady=7)
        bar = ttk.Frame(frame); bar.pack(fill='x', pady=5)
        self.button(bar, '2. 开始采集', self.start).pack(side='left', padx=(0, 8))
        self.button(bar, '恢复／导出上次记录', self.recover).pack(side='left', padx=(0, 8))
        self.button(bar, '打开隔离存档', self.open_saves).pack(side='left')
        ttk.Label(frame, textvariable=self.status, wraplength=650, padding=(0, 10)).pack(anchor='w')
        self.output = tk.Text(frame, height=9, wrap='word', state='disabled')
        self.output.pack(fill='both', expand=True)
        self.button(frame, '3. 打开导出文件夹', self.open_exports).pack(anchor='w', pady=(10, 0))
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.after(100, self.poll)

    def button(self, parent, text, command):
        b = ttk.Button(parent, text=text, command=command)
        self.buttons.append(b)
        return b

    def show(self, text):
        self.output.configure(state='normal')
        self.output.delete('1.0', 'end'); self.output.insert('1.0', text)
        self.output.configure(state='disabled')

    def work(self, message, fn, done):
        if self.busy:
            return
        self.busy = True
        self.status.set(message)
        for b in self.buttons:
            b.configure(state='disabled')
        def run():
            try:
                self.tasks.put((done, fn(), None))
            except Exception as error:
                self.tasks.put((done, None, str(error)))
        threading.Thread(target=run, daemon=False).start()

    def poll(self):
        try:
            done, value, error = self.tasks.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            for b in self.buttons:
                b.configure(state='normal')
            if error:
                self.status.set('操作未完成；原有记录仍保留。')
                self.show(error)
                messagebox.showerror('采集工具', error)
            else:
                done(value)
        self.root.after(100, self.poll)

    def install(self):
        if not (self.kit / 'kit.json').is_file():
            messagebox.showerror('缺少补丁', '请把工具与 kit 文件夹一起解压后运行。')
            return
        game = filedialog.askdirectory(title='选择原版游戏目录（包含 DELTARUNE.exe）')
        if not game:
            return
        out = self.capture_home
        def done(_):
            self.capture.set(str(out)); self.status.set('副本已准备好，可以开始采集。')
            self.show('隔离副本：' + str(out) + '\n存档不会自动复制。可以从头玩，或在关闭游戏后，把自己需要的存档文件复制到隔离存档目录。')
        self.work('正在检查版本并复制完整游戏，请稍候……', lambda: install_kit(self.kit, Path(game), out), done)

    def choose(self):
        path = filedialog.askdirectory(title='选择要迁入工具目录的旧采集副本（包含 capture.json）')
        if path:
            def done(_):
                self.capture.set(str(self.capture_home)); self.status.set('采集副本和存档已迁入，旧隔离存档保留。')
            self.work('正在检查并迁入采集副本与存档……', lambda: migrate_capture(Path(path), home()), done)

    def selected(self):
        if not self.capture.get():
            messagebox.showinfo('选择副本', '请先准备或选择采集副本。')
            return None
        return Path(self.capture.get())

    def report(self, result):
        summary = result.get('summary', result)
        self.last_export = result.get('export_file')
        if result.get('status') == 'no_ch2_capture':
            self.status.set('本次没有找到第二章记录。')
        else:
            self.status.set('记录已导出，请把 exports 文件夹中本次 ZIP 发给项目负责人。')
        lines = [f"消息：{summary.get('messages', 0)}　主动交互：{summary.get('interactions', 0)}　选择题：{summary.get('choices', 0)}",
                 f"smallface：{summary.get('smallfaces', 0)}　来源待核对：{summary.get('unmatched', 0)}"]
        warnings = summary.get('warnings', []) + result.get('warnings', [])
        if warnings:
            lines.append('\n需要注意：\n' + '\n'.join(map(str, warnings)))
        lines.append('\n' + str(self.last_export or '未生成记录包'))
        if 'cleanup' in result:
            lines.append(f"\nZIP 已回读校验；本次清理 {result['cleanup']['deleted_jsonl']} 个对应 JSONL。")
        lines.append('\n导出包只含采集记录与版本信息；没有游戏、存档或截图。')
        self.show('\n'.join(lines))

    def start(self):
        path = self.selected()
        if path:
            self.work('正在校验并启动游戏。退出所有章节后会自动整理记录，请保留此窗口。',
                      lambda: launch(path), self.report)

    def recover(self):
        path = self.selected()
        if path:
            def run():
                last = json.loads((path / 'last-run.json').read_text(encoding='utf-8'))
                return collect(path, last['run_id'])
            self.work('正在恢复已写出的记录……', run, self.report)

    def open_exports(self):
        path = self.selected()
        if path:
            out = path / 'exports'
            if out.is_dir():
                os.startfile(out)
            else:
                messagebox.showinfo('暂无导出', '完成一次第二章采集并退出游戏后，这里会生成 ZIP。')

    def open_saves(self):
        path = self.selected()
        if path:
            from tools.runtime.launcher import save_roots
            meta = load_install(path, verify=False)
            candidates = save_roots(meta['profile'], path)
            existing = next((p for p in candidates if p.is_dir()), None)
            if existing is not None:
                os.startfile(existing)
            else:
                messagebox.showinfo('隔离存档', '首次启动游戏后会创建隔离存档目录。\n' + str(candidates[0]))

    def close(self):
        if self.busy:
            messagebox.showinfo('采集中', '请先退出游戏并等待导出完成，再关闭工具。')
        else:
            self.root.destroy()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kit', type=Path)
    p.add_argument('--prepare-game', type=Path, help='Use the same installer as the UI to prepare home()/capture')
    p.add_argument('--check', type=Path, help='Check installation and print JSON without UI')
    p.add_argument('--smoke', type=Path, help='Boot-only verification of a prepared copy without UI')
    p.add_argument('--verify-mechanisms', type=Path, help='Bounded CH2 choice fixtures, no normal play')
    p.add_argument('--mechanism-pace', choices=['choices', 'sources'], default='choices')
    p.add_argument('--report', type=Path, help='Write command verification result for windowed executable')
    a = p.parse_args()
    result = None
    if a.prepare_game:
        result = install_kit(a.kit or home() / 'kit', a.prepare_game, home() / 'capture')
    elif a.check:
        result = load_install(a.check)
    elif a.smoke:
        result = launch(a.smoke, smoke=True)
    elif a.verify_mechanisms:
        result = launch(a.verify_mechanisms, smoke=True, mechanism=True, mechanism_pace=a.mechanism_pace)
    else:
        root = tk.Tk()
        Participant(root, a.kit or home() / 'kit')
        root.mainloop()
    if result is not None:
        if a.report:
            with a.report.open('x', encoding='utf-8') as output:
                json.dump(result, output, ensure_ascii=False, indent=2)
        elif sys.stdout is not None:
            print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
