"""Tkinter GUI entrypoint for Lab Guardian local monitoring client."""

import asyncio
import errno
import os
import socket
import threading
import tkinter as tk
from datetime import datetime
from tkinter import ttk

import requests

from . import config, db, dispatcher


RISK_COLORS = {
    "dangerous": ("#FDECEA", "#C62828"),
    "high": ("#FDECEA", "#C62828"),
    "suspicious": ("#FFF8E1", "#F57F17"),
    "medium": ("#FFF8E1", "#F57F17"),
    "safe": ("#E8F5E9", "#2E7D32"),
    "low": ("#E8F5E9", "#2E7D32"),
}

PROCESS_RISK_ORDER = {"dangerous": 0, "suspicious": 1, "safe": 2}


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

        db.init_db()

        self.runtime = MonitorRuntime()
        self.active_session = None

        self.roll_var = tk.StringVar()
        self.name_var = tk.StringVar()
        self.session_var = tk.StringVar()
        self.lab_var = tk.StringVar()

        self.start_status_var = tk.StringVar(value="")
        self.status_bar_var = tk.StringVar(value="Ready")

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

        tree.tag_configure("evenrow", background="#F5F5F5")
        tree.tag_configure("oddrow", background="#FFFFFF")
        tree.tag_configure("risk_high", background="#FDECEA", foreground="#C62828")
        tree.tag_configure("risk_medium", background="#FFF8E1", foreground="#F57F17")
        tree.tag_configure("risk_low", background="#E8F5E9", foreground="#2E7D32")
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

        processes_tab = ttk.Frame(self.notebook)
        devices_tab = ttk.Frame(self.notebook)
        network_tab = ttk.Frame(self.notebook)
        domains_tab = ttk.Frame(self.notebook)
        terminal_tab = ttk.Frame(self.notebook)
        browser_tab = ttk.Frame(self.notebook)

        self.notebook.add(processes_tab, text="Processes")
        self.notebook.add(devices_tab, text="Devices")
        self.notebook.add(network_tab, text="Network")
        self.notebook.add(domains_tab, text="Domain Activity")
        self.notebook.add(terminal_tab, text="Terminal Events")
        self.notebook.add(browser_tab, text="Browser History")

        self.process_tree = self._tree_with_scroll(
            processes_tab,
            ("pid", "process_name", "cpu_percent", "memory_mb", "status", "risk_level", "category"),
            ("PID", "Process Name", "CPU %", "Memory (MB)", "Status", "Risk Level", "Category"),
        )

        ttk.Label(devices_tab, text="USB Devices", style="FieldLabel.TLabel").pack(anchor="w", padx=8, pady=(8, 2))
        self.usb_tree = self._tree_with_scroll(
            devices_tab,
            ("device_name", "readable_name", "device_type", "risk_level", "connected_at", "status"),
            ("Device Name", "Readable Name", "Type", "Risk Level", "Connected At", "Status"),
        )

        ttk.Label(devices_tab, text="External Drives", style="FieldLabel.TLabel").pack(anchor="w", padx=8, pady=(8, 2))
        self.external_tree = self._tree_with_scroll(
            devices_tab,
            ("device_name", "readable_name", "device_type", "risk_level", "connected_at", "status"),
            ("Device Name", "Readable Name", "Type", "Risk Level", "Connected At", "Status"),
        )

        info = ttk.Frame(network_tab, padding=8)
        info.pack(fill=tk.X)
        self.ip_var = tk.StringVar(value="-")
        self.gateway_var = tk.StringVar(value="-")
        self.dns_var = tk.StringVar(value="-")
        ttk.Label(info, text="IP Address:", style="FieldLabel.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(info, textvariable=self.ip_var).grid(row=0, column=1, sticky="w", padx=(6, 0))
        ttk.Label(info, text="Gateway:", style="FieldLabel.TLabel").grid(row=1, column=0, sticky="w")
        ttk.Label(info, textvariable=self.gateway_var).grid(row=1, column=1, sticky="w", padx=(6, 0))
        ttk.Label(info, text="DNS:", style="FieldLabel.TLabel").grid(row=2, column=0, sticky="w")
        ttk.Label(info, textvariable=self.dns_var).grid(row=2, column=1, sticky="w", padx=(6, 0))

        ttk.Label(network_tab, text="Active Connections", style="FieldLabel.TLabel").pack(anchor="w", padx=8, pady=(2, 2))
        self.connections_tree = self._tree_with_scroll(
            network_tab,
            ("remote_ip", "remote_host", "remote_port", "pid", "process"),
            ("Remote IP", "Remote Host", "Remote Port", "PID", "Process"),
        )

        self.domain_tree = self._tree_with_scroll(
            domains_tab,
            ("domain", "request_count", "risk_level", "last_accessed"),
            ("Domain", "Request Count", "Risk Level", "Last Accessed"),
        )

        self.terminal_tree = self._tree_with_scroll(
            terminal_tab,
            ("time", "event_type", "tool", "remote_ip", "remote_host", "port", "pid", "command", "risk_level", "message"),
            ("Time", "Event Type", "Tool", "Remote IP", "Remote Host", "Port", "PID", "Command", "Risk Level", "Message"),
        )

        self.browser_tree = self._tree_with_scroll(
            browser_tab,
            ("url", "title", "visit_count", "last_visit"),
            ("URL", "Title", "Visit Count", "Last Visit"),
        )

        self.status_bar = tk.Label(self.session_frame, textvariable=self.status_bar_var, bg="#ECEFF1", fg="#546E7A", font=("Segoe UI", 8), anchor="w")
        self.status_bar.pack(fill=tk.X)

    def show_start(self):
        self.session_frame.pack_forget()
        self.start_frame.pack(fill=tk.BOTH, expand=True)

    def show_session(self):
        self.start_frame.pack_forget()
        self.session_frame.pack(fill=tk.BOTH, expand=True)

    def _record_count(self, id_map):
        return sum(len(v) for v in id_map.values())

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
        self.show_start()

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

            payload, id_map = db.get_unsynced_export_payload(session_id, roll_no)
            if self._record_count(id_map) == 0:
                self.root.after(0, lambda: self._export_done(False, "No unsynced records found."))
                return

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

                db.mark_synced(id_map)
                stored = body.get("stored") or {}
                total = sum(int(v or 0) for v in stored.values())
                if total <= 0:
                    total = self._record_count(id_map)
                self.root.after(0, lambda: self._export_done(True, f"Export complete. {total} records synced."))
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

    def _format_dt(self, value):
        if not value:
            return "-"
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone().strftime("%c")
        except Exception:
            return str(value)

    def _risk_tag(self, risk_level: str):
        if risk_level in {"dangerous", "high"}:
            return "risk_high"
        if risk_level in {"suspicious", "medium"}:
            return "risk_medium"
        if risk_level in {"safe", "low"}:
            return "risk_low"
        return ""

    def _clear_tree(self, tree):
        for i in tree.get_children():
            tree.delete(i)

    def _insert_rows(self, tree, rows, value_builder, risk_getter=None):
        self._clear_tree(tree)
        for idx, row in enumerate(rows):
            base_tag = "evenrow" if idx % 2 == 0 else "oddrow"
            tags = [base_tag]
            if risk_getter:
                risk_tag = self._risk_tag(risk_getter(row))
                if risk_tag:
                    tags = [risk_tag]
            tree.insert("", tk.END, values=value_builder(row), tags=tuple(tags))

    def refresh_session_view(self):
        if not self.active_session:
            return

        payload = db.get_latest_session_payload(self.active_session["sessionId"], self.active_session["rollNo"])

        processes = [p for p in payload.get("processes", []) if (p.get("status") or "").lower() != "ended"]
        processes.sort(
            key=lambda p: (
                PROCESS_RISK_ORDER.get((p.get("risk_level") or "").lower(), 3),
                -(float(p.get("cpu_percent") or 0)),
            )
        )
        self._insert_rows(
            self.process_tree,
            processes,
            lambda p: (
                p.get("pid"),
                p.get("process_name") or "-",
                f"{float(p.get('cpu_percent') or 0):.2f}",
                f"{float(p.get('memory_mb') or 0):.1f}",
                p.get("status") or "-",
                p.get("risk_level") or "-",
                p.get("category") or "-",
            ),
            lambda p: (p.get("risk_level") or "").lower(),
        )

        devices = payload.get("devices", [])
        usb_devices = [d for d in devices if (d.get("device_type") or "").lower() == "usb"]
        external_devices = [d for d in devices if (d.get("device_type") or "").lower() != "usb"]

        def _device_values(d):
            status = "Connected" if not d.get("disconnected_at") else "Disconnected"
            return (
                d.get("device_name") or "-",
                d.get("readable_name") or "-",
                d.get("device_type") or "-",
                d.get("risk_level") or "-",
                self._format_dt(d.get("connected_at")),
                status,
            )

        self._insert_rows(self.usb_tree, usb_devices, _device_values, lambda d: (d.get("risk_level") or "").lower())
        self._insert_rows(self.external_tree, external_devices, _device_values, lambda d: (d.get("risk_level") or "").lower())

        network = payload.get("network") or {}
        self.ip_var.set(network.get("ip_address") or "-")
        self.gateway_var.set(network.get("gateway") or "-")
        dns = network.get("dns") or []
        self.dns_var.set(", ".join(dns) if isinstance(dns, list) else str(dns or "-"))

        active_connections = network.get("active_connections") or []
        if not isinstance(active_connections, list):
            active_connections = []
        self._insert_rows(
            self.connections_tree,
            active_connections,
            lambda c: (
                c.get("remote_ip") or "-",
                c.get("remote_host") or "-",
                c.get("remote_port") or "-",
                c.get("pid") or "-",
                c.get("process") or "-",
            ),
        )

        domain_rows = payload.get("domainActivity", [])
        domain_rows.sort(key=lambda d: -int(d.get("request_count") or 0))
        self._insert_rows(
            self.domain_tree,
            domain_rows,
            lambda d: (
                d.get("domain") or "-",
                d.get("request_count") or 0,
                d.get("risk_level") or "-",
                self._format_dt(d.get("last_accessed")),
            ),
            lambda d: (d.get("risk_level") or "").lower(),
        )

        terminal_rows = payload.get("terminalEvents", [])
        terminal_rows.sort(key=lambda t: str(t.get("detected_at") or ""), reverse=True)
        terminal_rows = terminal_rows[:200]
        self._insert_rows(
            self.terminal_tree,
            terminal_rows,
            lambda t: (
                self._format_dt(t.get("detected_at")),
                t.get("event_type") or "-",
                t.get("tool") or "-",
                t.get("remote_ip") or "-",
                t.get("remote_host") or "-",
                t.get("remote_port") or "-",
                t.get("pid") or "-",
                t.get("full_command") or "-",
                t.get("risk_level") or "-",
                t.get("message") or "-",
            ),
            lambda t: (t.get("risk_level") or "").lower(),
        )

        history_rows = payload.get("browserHistory", [])
        history_rows.sort(key=lambda h: str(h.get("last_visit") or ""), reverse=True)
        self._insert_rows(
            self.browser_tree,
            history_rows,
            lambda h: (
                h.get("url") or "-",
                h.get("title") or "-",
                h.get("visit_count") or 0,
                self._format_dt(h.get("last_visit")),
            ),
        )

        status = (
            f"Last updated: {datetime.now().strftime('%H:%M:%S')} | "
            f"Processes: {len(processes)} | "
            f"Devices: {len(devices)} | "
            f"Domain Activity: {len(domain_rows)} | "
            f"Terminal Events: {len(terminal_rows)} | "
            f"Browser History: {len(history_rows)}"
        )
        self.status_bar_var.set(status)

        self.root.after(max(1000, int(config.SNAPSHOT_INTERVAL * 1000)), self.refresh_session_view)

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

