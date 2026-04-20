"""Tkinter GUI entrypoint for Lab Guardian local monitoring client."""

import asyncio
import errno
import json
import os
import socket
import threading
import tkinter as tk
from datetime import datetime
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


class EndSessionDialog(tk.Toplevel):
    def __init__(self, parent, on_confirm):
        super().__init__(parent)
        self.parent = parent
        self.on_confirm = on_confirm
        self.title("End Session")
        self.geometry("320x160")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - 160
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - 80
        self.geometry(f"+{max(x, 0)}+{max(y, 0)}")

        body = ttk.Frame(self, padding=12)
        body.pack(fill=tk.BOTH, expand=True)

        ttk.Label(body, text="Enter password to end this session:").pack(anchor="w", pady=(0, 8))
        self.password_entry = ttk.Entry(body, show="*", width=30)
        self.password_entry.pack(anchor="w")
        self.password_entry.focus_set()

        self.error_var = tk.StringVar(value="")
        ttk.Label(body, textvariable=self.error_var, foreground="#C62828").pack(anchor="w", pady=(6, 0))

        actions = ttk.Frame(body)
        actions.pack(anchor="e", pady=(12, 0))
        ttk.Button(actions, text="Cancel", style="Neutral.TButton", command=self.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(actions, text="Confirm", style="Primary.TButton", command=self._confirm).pack(side=tk.RIGHT)

        self.bind("<Return>", lambda _e: self._confirm())

    def _confirm(self):
        if self.password_entry.get() != "80085":
            self.error_var.set("Incorrect password.")
            self.password_entry.focus_set()
            return
        self.on_confirm()
        self.destroy()


class LabGuardianGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("LabGuardian — Student Monitor")
        self.root.geometry("1100x700")
        self.root.minsize(1100, 700)
        self.root.configure(bg="#FFFFFF")

        self._apply_theme()
        self._try_set_icon()

        conn = db.init_db()
        conn.close()

        self.runtime = MonitorRuntime()
        self.active_session = None

        self.roll_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.session_var = tk.StringVar()
        self.lab_var = tk.StringVar()

        self.start_status_var = tk.StringVar(value="")
        self.status_bar_var = tk.StringVar(value="Ready")
        self.displayed_rowids = {
            "devices": set(),
            "browserHistory": set(),
            "processes": set(),
            "terminalEvents": set(),
        }

        self._build_layout()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def _apply_theme(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure("TFrame", background="#FFFFFF")
        style.configure("TLabel", background="#FFFFFF")

        style.configure("Card.TFrame", background="#FFFFFF")

        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"), foreground="#1A237E")
        style.configure("Subtitle.TLabel", font=("Segoe UI", 10), foreground="#546E7A")
        style.configure("FieldLabel.TLabel", font=("Segoe UI", 9), foreground="#37474F")

        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(24, 8), foreground="#FFFFFF", background="#1565C0")
        style.map("Primary.TButton", background=[("active", "#0D47A1")])

        style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=(20, 6), foreground="#1565C0", background="#FFFFFF", borderwidth=1)
        style.map("Secondary.TButton", background=[("active", "#E3F2FD")])

        style.configure("Danger.TButton", font=("Segoe UI", 10, "bold"), padding=(16, 6), foreground="#FFFFFF", background="#C62828")
        style.map("Danger.TButton", background=[("active", "#B71C1C")])

        style.configure("Neutral.TButton", font=("Segoe UI", 10), padding=(16, 6), foreground="#263238", background="#CFD8DC")
        style.map("Neutral.TButton", background=[("active", "#B0BEC5")])

        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _try_set_icon(self):
        icon_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "icon.png"))
        if os.path.exists(icon_path):
            try:
                self.root.iconphoto(True, tk.PhotoImage(file=icon_path))
            except Exception:
                pass

    def _build_layout(self):
        self.container = ttk.Frame(self.root, style="TFrame")
        self.container.pack(fill=tk.BOTH, expand=True)

        self.start_frame = ttk.Frame(self.container)
        self.session_frame = ttk.Frame(self.container)

        self._build_start_screen()
        self._build_session_screen()
        self.show_start()

    def _build_start_screen(self):
        card = ttk.Frame(self.start_frame, style="Card.TFrame", padding=40)
        card.place(relx=0.5, rely=0.5, anchor="center")

        ttk.Label(card, text="LabGuardian", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(card, text="Student Monitoring System", style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 16))

        fields = [
            ("Roll No.", self.roll_var),
            ("Name", self.name_var),
            ("Session ID", self.session_var),
        ]

        row = 2
        for label, var in fields:
            ttk.Label(card, text=label, style="FieldLabel.TLabel").grid(row=row, column=0, sticky="w", pady=(4, 2))
            ttk.Entry(card, textvariable=var, width=30).grid(row=row + 1, column=0, sticky="w")
            row += 2

        ttk.Label(card, text="Lab No.", style="FieldLabel.TLabel").grid(row=row, column=0, sticky="w", pady=(4, 2))
        self.lab_combo = ttk.Combobox(card, values=config.LAB_LIST, textvariable=self.lab_var, state="readonly", width=28)
        self.lab_combo.grid(row=row + 1, column=0, sticky="w")

        row += 2
        self.start_btn = ttk.Button(card, text="Start", style="Primary.TButton", command=self.on_start)
        self.start_btn.grid(row=row, column=0, sticky="w", pady=(14, 0))

        row += 1
        self.export_btn = ttk.Button(card, text="Export Data", style="Secondary.TButton", command=self.on_export)
        self.export_btn.grid(row=row, column=0, sticky="w", pady=(8, 0))

        row += 1
        self.progress = ttk.Progressbar(card, mode="indeterminate", length=260)
        self.progress.grid(row=row, column=0, sticky="w", pady=(8, 0))
        self.progress.grid_remove()

        row += 1
        self.start_status_label = tk.Label(card, textvariable=self.start_status_var, bg="#FFFFFF", fg="#546E7A", font=("Segoe UI", 9))
        self.start_status_label.grid(row=row, column=0, sticky="w", pady=(8, 0))

    def _tree_with_scroll(self, parent, columns, headings):
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill=tk.BOTH, expand=True)

        tree = ttk.Treeview(wrapper, columns=columns, show="headings")
        for col, heading in zip(columns, headings):
            tree.heading(col, text=heading)
            tree.column(col, anchor="w", width=130)

        scroll = ttk.Scrollbar(wrapper, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)

        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        tree.tag_configure("high", background="#FEF2F2", foreground="#991B1B")
        tree.tag_configure("medium", background="#FFFBEB", foreground="#92400E")
        tree.tag_configure("low", background="#ECFDF5", foreground="#065F46")
        tree.tag_configure("normal", background="#ECFDF5", foreground="#065F46")
        return tree

    def _build_session_screen(self):
        header = tk.Frame(self.session_frame, bg="#1A237E", height=48)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        self.header_left_var = tk.StringVar(value="")
        tk.Label(header, textvariable=self.header_left_var, bg="#1A237E", fg="#FFFFFF", font=("Segoe UI", 11, "bold")).pack(side=tk.LEFT, padx=16)

        end_btn = ttk.Button(header, text="End Session", style="Danger.TButton", command=self.on_end_session)
        end_btn.pack(side=tk.RIGHT, padx=16, pady=8)

        self.notebook = ttk.Notebook(self.session_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        devices_tab = ttk.Frame(self.notebook)
        network_tab = ttk.Frame(self.notebook)
        processes_tab = ttk.Frame(self.notebook)
        terminal_tab = ttk.Frame(self.notebook)

        self.notebook.add(devices_tab, text="Devices")
        self.notebook.add(network_tab, text="Network")
        self.notebook.add(processes_tab, text="Processes")
        self.notebook.add(terminal_tab, text="Terminal")

        # Devices tab
        self.devices_empty_var = tk.StringVar(value="")
        self.device_tree = self._tree_with_scroll(
            devices_tab,
            ("readable_name", "message", "mountpoint", "size_gb", "risk_level"),
            ("Device Name", "Description", "Mount Point", "Size (GB)", "Risk"),
        )
        tk.Label(devices_tab, textvariable=self.devices_empty_var, bg="#FFFFFF", fg="#546E7A", font=("Segoe UI", 9)).pack(anchor="w", padx=8, pady=(4, 8))

        # Network tab
        self.network_empty_var = tk.StringVar(value="")
        self.network_tree = self._tree_with_scroll(
            network_tab,
            ("title", "url", "browser", "last_visited", "visit_count"),
            ("Page Title", "URL", "Browser", "Last Visited", "Visits"),
        )
        tk.Label(network_tab, textvariable=self.network_empty_var, bg="#FFFFFF", fg="#546E7A", font=("Segoe UI", 9)).pack(anchor="w", padx=8, pady=(4, 8))

        # Processes tab
        self.processes_empty_var = tk.StringVar(value="")
        self.process_tree = self._tree_with_scroll(
            processes_tab,
            ("process_name", "pid", "cpu", "memory", "risk_level", "category"),
            ("Process Name", "PID", "CPU %", "Memory (MB)", "Risk", "Category"),
        )
        tk.Label(processes_tab, textvariable=self.processes_empty_var, bg="#FFFFFF", fg="#546E7A", font=("Segoe UI", 9)).pack(anchor="w", padx=8, pady=(0, 8))

        # Terminal tab
        self.terminal_empty_var = tk.StringVar(value="")
        self.terminal_tree = self._tree_with_scroll(
            terminal_tab,
            ("detected_at", "event_type", "tool", "full_command", "remote_ip", "risk_level"),
            ("Time", "Event Type", "Tool", "Command", "Remote IP", "Risk"),
        )
        tk.Label(terminal_tab, textvariable=self.terminal_empty_var, bg="#FFFFFF", fg="#546E7A", font=("Segoe UI", 9)).pack(anchor="w", padx=8, pady=(4, 8))

        self.status_bar = tk.Label(self.session_frame, textvariable=self.status_bar_var, bg="#ECEFF1", fg="#546E7A", font=("Segoe UI", 8), anchor="w")
        self.status_bar.pack(fill=tk.X)

    def show_start(self):
        self.session_frame.pack_forget()
        self.start_frame.pack(fill=tk.BOTH, expand=True)

    def show_session(self):
        self.start_frame.pack_forget()
        self.session_frame.pack(fill=tk.BOTH, expand=True)

    def _record_count(self, data_map):
        return sum(len(data_map.get(k, [])) for k in ("devices", "browserHistory", "processes", "terminalEvents"))

    def _set_export_state(self, loading: bool):
        self.export_btn.configure(state=tk.DISABLED if loading else tk.NORMAL)
        self.export_btn.configure(text="Syncing..." if loading else "Export Data")
        if loading:
            self.progress.grid()
            self.progress.start(10)
        else:
            self.progress.stop()
            self.progress.grid_remove()

    def _show_start_message(self, text: str, success: bool):
        self.start_status_var.set(text)
        self.start_status_label.configure(fg="#2E7D32" if success else "#C62828")
        self.root.after(3000 if success else 4000, lambda: self.start_status_var.set(""))

    def on_start(self):
        roll_no = self.roll_var.get().strip()
        name = self.name_var.get().strip()
        session_id = self.session_var.get().strip()
        lab_no = self.lab_var.get().strip()

        if not roll_no or not name or not session_id or not lab_no:
            self._show_start_message("Roll No., Name, Session ID, and Lab No. are required.", success=False)
            return

        db.start_session(session_id, roll_no, name, lab_no)
        self.runtime.start(session_id, roll_no, lab_no)

        self.active_session = {
            "rollNo": roll_no,
            "name": name,
            "sessionId": session_id,
            "labNo": lab_no,
        }
        self._reset_display_cache()
        self.header_left_var.set(f"{name} | {roll_no}")

        self.show_session()
        self.refresh_session_view()

    def on_end_session(self):
        if not self.active_session:
            return
        EndSessionDialog(self.root, self._confirm_end_session)

    def _confirm_end_session(self):
        self.runtime.stop()
        db.end_session(self.active_session["sessionId"], self.active_session["rollNo"])
        self.active_session = None
        self._reset_display_cache()
        self.show_start()

    def _reset_display_cache(self):
        self.displayed_rowids = {
            "devices": set(),
            "browserHistory": set(),
            "processes": set(),
            "terminalEvents": set(),
        }
        for tree in [
            getattr(self, "device_tree", None),
            getattr(self, "network_tree", None),
            getattr(self, "process_tree", None),
            getattr(self, "terminal_tree", None),
        ]:
            if tree is not None:
                self._clear_tree(tree)

    def _probe_backend(self):
        host = config.BACKEND_HOST
        port = config.BACKEND_PORT
        try:
            socket.getaddrinfo(host, port)
        except OSError:
            return "no_lan"

        try:
            with socket.create_connection((host, port), timeout=3):
                return "ok"
        except OSError as exc:
            if getattr(exc, "errno", None) in {errno.ENETUNREACH, errno.EHOSTUNREACH}:
                return "no_lan"
            if isinstance(exc, ConnectionRefusedError) or isinstance(exc, socket.timeout):
                return "unreachable"
            return "unreachable"

    def on_export(self):
        roll_no = self.roll_var.get().strip()
        session_id = self.session_var.get().strip()
        lab_no = self.lab_var.get().strip()
        name = self.name_var.get().strip()

        if not roll_no or not session_id:
            self._show_start_message("Roll No. and Session ID are required for export.", success=False)
            return

        self._set_export_state(True)

        def _worker():
            probe = self._probe_backend()
            if probe == "no_lan":
                self.root.after(0, lambda: self._export_done(False, "No LAN available, try again later."))
                return
            if probe == "unreachable":
                self.root.after(0, lambda: self._export_done(False, "Backend server is not reachable. Try again later."))
                return

            unsynced_data = db.get_unsynced(session_id, roll_no)
            if self._record_count(unsynced_data) == 0:
                self.root.after(0, lambda: self._export_done(False, "No unsynced records found."))
                return

            devices = []
            for device in unsynced_data.get("devices", []):
                d = dict(device)
                metadata = d.get("metadata")
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except Exception:
                        metadata = {}
                if not isinstance(metadata, dict):
                    metadata = {}
                d["metadata"] = metadata
                d["device_type"] = "usb"
                devices.append(d)

            payload = {
                "sessionId": session_id,
                "rollNo": roll_no,
                "labNo": lab_no,
                "name": name,
                "devices": devices,
                "browserHistory": unsynced_data.get("browserHistory", []),
                "processes": unsynced_data.get("processes", []),
                "terminalEvents": unsynced_data.get("terminalEvents", []),
            }

            try:
                response = requests.post(
                    f"{config.API_BASE_URL}/api/telemetry/ingest",
                    json=payload,
                    timeout=(5, 30),
                )
                response.raise_for_status()
                body = response.json()
                if not body.get("success"):
                    self.root.after(0, lambda: self._export_done(False, "Export failed: server did not confirm success."))
                    return

                db.mark_synced(session_id, roll_no)
                self.root.after(0, lambda: self._export_done(True, "Export complete. Data synced."))
            except requests.exceptions.Timeout:
                self.root.after(0, lambda: self._export_done(False, "Export timed out. Check network and try again."))
            except requests.exceptions.ConnectionError:
                self.root.after(0, lambda: self._export_done(False, "Backend server is not reachable."))
            except requests.exceptions.HTTPError:
                detail = ""
                try:
                    detail = response.text
                except Exception:
                    detail = ""
                detail = detail.strip()
                msg = f"Export failed: {response.status_code}"
                if detail:
                    msg = f"{msg} - {detail}"
                self.root.after(0, lambda: self._export_done(False, msg))
            except Exception as exc:
                self.root.after(0, lambda: self._export_done(False, f"Export failed: {exc}"))

        threading.Thread(target=_worker, daemon=True).start()

    def _export_done(self, success: bool, message: str):
        self._set_export_state(False)
        self._show_start_message(message, success=success)

    def _clear_tree(self, tree):
        for item in tree.get_children():
            tree.delete(item)

    def _risk_tag(self, risk_level: str) -> str:
        risk = str(risk_level or "normal").lower()
        if risk in {"high", "medium", "low", "normal"}:
            return risk
        return "normal"

    def _truncate(self, value: str, length: int = 60) -> str:
        if value is None:
            return ""
        text = str(value)
        return text if len(text) <= length else f"{text[:length]}..."

    def _safe_time_from_iso(self, value: str) -> str:
        if not value:
            return "—"
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%H:%M:%S")
        except Exception:
            return "—"

    def _safe_time_from_unix(self, value):
        if value is None:
            return "—"
        try:
            return datetime.fromtimestamp(float(value)).strftime("%H:%M:%S")
        except Exception:
            return "—"

    def _title_fallback(self, url: str) -> str:
        if not url:
            return "—"
        try:
            parsed = urlparse(url)
            host = parsed.netloc or ""
            path = parsed.path or ""
            text = (host + path).strip()
            return text or url
        except Exception:
            return url

    def refresh_session_view(self):
        if not self.active_session:
            return

        payload = db.get_all_for_session(self.active_session["sessionId"], self.active_session["rollNo"])

        # Devices
        devices = payload.get("devices", [])
        for row in devices:
            row_id = row.get("_rowid")
            if row_id in self.displayed_rowids["devices"]:
                continue
            self.displayed_rowids["devices"].add(row_id)
            metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
            self.device_tree.insert(
                "",
                tk.END,
                values=(
                    row.get("readable_name") or "USB Storage Device",
                    row.get("message") or "",
                    metadata.get("mountpoint") or "—",
                    metadata.get("total_gb") if metadata.get("total_gb") is not None else "—",
                    (row.get("risk_level") or "normal").lower(),
                ),
                tags=(self._risk_tag(row.get("risk_level")),),
            )
        self.devices_empty_var.set("No USB devices connected." if len(self.device_tree.get_children()) == 0 else "")

        # Network (Browser History)
        browser_history = sorted(
            payload.get("browserHistory", []),
            key=lambda item: float(item.get("last_visited") or 0),
            reverse=False,
        )
        for row in browser_history:
            row_id = row.get("_rowid")
            if row_id in self.displayed_rowids["browserHistory"]:
                continue
            self.displayed_rowids["browserHistory"].add(row_id)
            title = row.get("title") or self._title_fallback(row.get("url") or "")
            self.network_tree.insert(
                "",
                tk.END,
                values=(
                    title,
                    self._truncate(row.get("url") or "", 60),
                    row.get("browser") or "—",
                    self._safe_time_from_unix(row.get("last_visited")),
                    int(row.get("visit_count") or 1),
                ),
            )
        self.network_empty_var.set("No browsing activity since session started." if len(self.network_tree.get_children()) == 0 else "")

        # Processes
        process_rows = [
            row
            for row in payload.get("processes", [])
            if str(row.get("status") or "").lower() != "ended"
            and str(row.get("risk_level") or "").lower() != "safe"
        ]
        risk_order = {"high": 0, "medium": 1, "low": 2, "normal": 3}
        process_rows.sort(
            key=lambda row: (
                risk_order.get(str(row.get("risk_level") or "normal").lower(), 4),
                str(row.get("detected_at") or ""),
                int(row.get("_rowid") or 0),
            )
        )

        for row in process_rows:
            row_id = row.get("_rowid")
            if row_id in self.displayed_rowids["processes"]:
                continue
            self.displayed_rowids["processes"].add(row_id)
            display_name = row.get("label") or row.get("name") or "Unknown Process"
            self.process_tree.insert(
                "",
                tk.END,
                values=(
                    display_name,
                    row.get("pid") if row.get("pid") is not None else "—",
                    f"{float(row.get('cpu') or 0.0):.1f}",
                    f"{float(row.get('memory') or 0.0):.1f}",
                    str(row.get("risk_level") or "normal").lower(),
                    row.get("category") or "—",
                ),
                tags=(self._risk_tag(row.get("risk_level")),),
            )

        self.processes_empty_var.set("No notable processes detected." if len(self.process_tree.get_children()) == 0 else "")

        # Terminal
        terminal_rows = sorted(
            payload.get("terminalEvents", []),
            key=lambda item: str(item.get("detected_at") or ""),
            reverse=False,
        )
        for row in terminal_rows:
            row_id = row.get("_rowid")
            if row_id in self.displayed_rowids["terminalEvents"]:
                continue
            self.displayed_rowids["terminalEvents"].add(row_id)

            full_command = row.get("full_command") or "—"
            if full_command == "—" and str(row.get("event_type") or "") == "terminal_request":
                ip = row.get("remote_ip") or ""
                port = row.get("remote_port") or ""
                if ip and port:
                    full_command = f"{ip}:{port}"
                elif ip:
                    full_command = ip

            self.terminal_tree.insert(
                "",
                tk.END,
                values=(
                    self._safe_time_from_iso(row.get("detected_at")),
                    row.get("event_type") or "—",
                    row.get("tool") or "unknown",
                    full_command,
                    row.get("remote_ip") or "—",
                    (row.get("risk_level") or "normal").lower(),
                ),
                tags=(self._risk_tag(row.get("risk_level")),),
            )

        self.terminal_empty_var.set("No terminal activity recorded." if len(self.terminal_tree.get_children()) == 0 else "")

        self.status_bar_var.set(
            f"Last updated: {datetime.now().strftime('%H:%M:%S')} | Devices: {len(devices)} | "
            f"History: {len(browser_history)} | Processes: {len(process_rows)} | Terminal: {len(terminal_rows)}"
        )

        interval_seconds = int(getattr(config, "MONITOR_INTERVAL", getattr(config, "SNAPSHOT_INTERVAL", 5)))
        interval_ms = max(1000, interval_seconds * 1000)
        self.root.after(interval_ms, self.refresh_session_view)

    def on_close(self):
        if self.runtime.running:
            self._show_start_message("Cannot close while a session is active.", success=False)
            return
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    app = LabGuardianGUI()
    app.run()


if __name__ == "__main__":
    main()
