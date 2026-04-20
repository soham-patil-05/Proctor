"""Tkinter GUI entrypoint for Lab Guardian local monitoring client."""

import asyncio
import socket
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import simpledialog
from tkinter import ttk
from urllib.parse import urlparse

import requests

from . import config, db, dispatcher


class MonitorRuntime:
    def __init__(self):
        self.thread = None
        self.loop = None
        self.stop_event = None
        self.running = False

    def start(self, session_id: str, roll_no: str, lab_no: str):
        if self.running:
            return

        def _runner():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.stop_event = asyncio.Event()
            self.running = True
            try:
                self.loop.run_until_complete(dispatcher.run(session_id, roll_no, lab_no, self.stop_event))
            finally:
                self.running = False
                self.loop.close()

        self.thread = threading.Thread(target=_runner, daemon=True)
        self.thread.start()

    def stop(self):
        if not self.running or self.loop is None or self.stop_event is None:
            return
        self.loop.call_soon_threadsafe(self.stop_event.set)
        if self.thread is not None:
            self.thread.join(timeout=5)


class LabGuardianGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('Lab Guardian')
        self.root.geometry('1080x720')

        db.init_db()

        self.runtime = MonitorRuntime()
        self.active_session = None

        self.status_var = tk.StringVar(value='Ready')

        self.roll_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.session_var = tk.StringVar()
        self.lab_var = tk.StringVar()

        self._build_layout()
        self.root.protocol('WM_DELETE_WINDOW', self.on_close)

    def _build_layout(self):
        self.container = ttk.Frame(self.root, padding=12)
        self.container.pack(fill=tk.BOTH, expand=True)

        self.start_frame = ttk.Frame(self.container)
        self.session_frame = ttk.Frame(self.container)

        self._build_start_screen()
        self._build_session_screen()
        self.show_start()

    def _build_start_screen(self):
        frm = self.start_frame

        ttk.Label(frm, text='Lab Guardian', font=('Segoe UI', 20, 'bold')).pack(anchor='w', pady=(0, 12))

        grid = ttk.Frame(frm)
        grid.pack(anchor='w', fill=tk.X)

        ttk.Label(grid, text='Roll No.').grid(row=0, column=0, sticky='w', pady=6)
        ttk.Entry(grid, textvariable=self.roll_var, width=36).grid(row=0, column=1, sticky='w', pady=6)

        ttk.Label(grid, text='Name').grid(row=1, column=0, sticky='w', pady=6)
        ttk.Entry(grid, textvariable=self.name_var, width=36).grid(row=1, column=1, sticky='w', pady=6)

        ttk.Label(grid, text='Session ID').grid(row=2, column=0, sticky='w', pady=6)
        ttk.Entry(grid, textvariable=self.session_var, width=36).grid(row=2, column=1, sticky='w', pady=6)

        ttk.Label(grid, text='Lab No.').grid(row=3, column=0, sticky='w', pady=6)
        self.lab_combo = ttk.Combobox(grid, values=config.LAB_LIST, textvariable=self.lab_var, state='readonly', width=33)
        self.lab_combo.grid(row=3, column=1, sticky='w', pady=6)

        actions = ttk.Frame(frm)
        actions.pack(anchor='w', pady=14)

        self.start_btn = ttk.Button(actions, text='Start', command=self.on_start)
        self.start_btn.grid(row=0, column=0, padx=(0, 10))

        self.export_btn = ttk.Button(actions, text='Export Data', command=self.on_export)
        self.export_btn.grid(row=0, column=1)

        ttk.Label(frm, textvariable=self.status_var).pack(anchor='w', pady=(8, 0))

    def _build_session_screen(self):
        frm = self.session_frame

        self.header_var = tk.StringVar(value='')
        header = ttk.Frame(frm)
        header.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(header, textvariable=self.header_var, font=('Segoe UI', 14, 'bold')).pack(side=tk.LEFT)
        ttk.Button(header, text='End Session', command=self.on_end_session).pack(side=tk.RIGHT)

        self.notebook = ttk.Notebook(frm)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tabs = {}
        for name in ['Processes', 'Devices', 'Network', 'Domain Activity', 'Terminal Events', 'Browser History']:
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=name)
            txt = tk.Text(tab, wrap=tk.WORD)
            txt.pack(fill=tk.BOTH, expand=True)
            txt.configure(state=tk.DISABLED)
            self.tabs[name] = txt

    def set_loading(self, loading: bool):
        state = tk.DISABLED if loading else tk.NORMAL
        self.start_btn.configure(state=state)
        self.export_btn.configure(state=state)
        self.status_var.set('Syncing...' if loading else 'Ready')

    def show_start(self):
        self.session_frame.pack_forget()
        self.start_frame.pack(fill=tk.BOTH, expand=True)

    def show_session(self):
        self.start_frame.pack_forget()
        self.session_frame.pack(fill=tk.BOTH, expand=True)

    def on_start(self):
        roll_no = self.roll_var.get().strip()
        name = self.name_var.get().strip()
        session_id = self.session_var.get().strip()
        lab_no = self.lab_var.get().strip()

        if not roll_no or not name or not session_id or not lab_no:
            messagebox.showerror('Validation Error', 'Roll No., Name, Session ID, and Lab No. are required.')
            return

        db.start_session(session_id, roll_no, name, lab_no)
        self.runtime.start(session_id, roll_no, lab_no)

        self.active_session = {
            'rollNo': roll_no,
            'name': name,
            'sessionId': session_id,
            'labNo': lab_no,
        }
        self.header_var.set(f"{name} ({roll_no}) - Session {session_id} [{lab_no}]")

        self.show_session()
        self.refresh_session_view()

    def on_end_session(self):
        if not self.active_session:
            return

        password = simpledialog.askstring('End Session', 'Enter password to end session:', show='*')
        if password != '80085':
            messagebox.showerror('Error', 'Incorrect password')
            return

        self.runtime.stop()
        db.end_session(self.active_session['sessionId'], self.active_session['rollNo'])
        self.active_session = None
        self.show_start()

    def _can_reach_backend(self) -> bool:
        parsed = urlparse(config.API_BASE_URL)
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port or (443 if parsed.scheme == 'https' else 80)
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            return False

    def on_export(self):
        roll_no = self.roll_var.get().strip()
        session_id = self.session_var.get().strip()
        if not roll_no or not session_id:
            messagebox.showerror('Validation Error', 'Roll No. and Session ID are required for export.')
            return

        if not self._can_reach_backend():
            messagebox.showwarning('Connectivity', 'No LAN available, try again later.')
            return

        self.set_loading(True)
        try:
            payload, id_map = db.get_unsynced_export_payload(session_id, roll_no)
            if all(len(v) == 0 for v in id_map.values()):
                messagebox.showinfo('Export', 'No unsynced records found.')
                return

            response = requests.post(
                f"{config.API_BASE_URL}/api/telemetry/ingest",
                json=payload,
                timeout=20,
            )
            if response.ok:
                db.mark_synced(id_map)
                messagebox.showinfo('Export', 'Export completed successfully.')
            else:
                msg = response.text or 'Export failed'
                messagebox.showerror('Export Error', msg)
        except Exception as exc:
            messagebox.showerror('Export Error', str(exc))
        finally:
            self.set_loading(False)

    def _set_tab_text(self, tab_name: str, content: str):
        widget = self.tabs[tab_name]
        widget.configure(state=tk.NORMAL)
        widget.delete('1.0', tk.END)
        widget.insert('1.0', content)
        widget.configure(state=tk.DISABLED)

    def refresh_session_view(self):
        if not self.active_session:
            return

        payload = db.get_latest_session_payload(
            self.active_session['sessionId'],
            self.active_session['rollNo'],
        )

        self._set_tab_text('Processes', '\n'.join([str(x) for x in payload.get('processes', [])]) or 'No data')
        self._set_tab_text('Devices', str(payload.get('devices', {'usb': [], 'external': []})))
        self._set_tab_text('Network', str(payload.get('network')))
        self._set_tab_text('Domain Activity', '\n'.join([str(x) for x in payload.get('domainActivity', [])]) or 'No data')
        self._set_tab_text('Terminal Events', '\n'.join([str(x) for x in payload.get('terminalEvents', [])]) or 'No data')
        self._set_tab_text('Browser History', '\n'.join([str(x) for x in payload.get('browserHistory', [])]) or 'No data')

        self.root.after(max(1000, int(config.SNAPSHOT_INTERVAL * 1000)), self.refresh_session_view)

    def on_close(self):
        if self.runtime.running:
            messagebox.showwarning('Session Active', 'Cannot close while a session is active.')
            return
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    app = LabGuardianGUI()
    app.run()


if __name__ == '__main__':
    main()
