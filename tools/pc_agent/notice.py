"""
On-screen notices on a lab PC (2026-10-21, owner: "pop up on the laptop itself, coloured, be creative").

One UI thread with one hidden Tk root shows every notice as a card: a coloured header strip with a big
symbol, the title, the text, who sent it and when, and a "Got it" button. Cards fade in, stay on top,
stack downwards if several arrive, and never block the agent. The 60 s restart / shut-down countdown is
a card too. Windows 7 has no colour-emoji font, so the symbols are drawn in colour from Segoe UI Symbol.
Without tkinter (or off Windows) a plain message box / print is used.
"""
from __future__ import annotations

import queue
import threading
import time
from datetime import datetime
from typing import Optional

# kind -> (header colour, symbol, label)
STYLES = {
    "message": ("#2563eb", "✉", "Message from lab staff"),        # envelope
    "share":   ("#7c3aed", "▶", "Screen sharing"),                # play
    "view":    ("#0891b2", "◉", "Your screen is being viewed"),   # fisheye
    "ok":      ("#16a34a", "✔", "Access"),                        # check mark
    "warn":    ("#ea580c", "⚠", "Lab staff"),                     # warning sign
    "exam":    ("#dc2626", "✎", "Exam mode"),                     # pencil
    "info":    ("#475569", "ℹ", "Smart Lab"),                     # information
}
_q: "queue.Queue[tuple]" = queue.Queue()
_started = [False]
_lock = threading.Lock()


def _fallback(title: str, text: str) -> None:
    print(f"[{title}] {text}")
    try:
        import ctypes
        MB_ICONINFORMATION, MB_TOPMOST, MB_SETFOREGROUND = 0x40, 0x40000, 0x10000
        threading.Thread(target=ctypes.windll.user32.MessageBoxW, daemon=True,
                         args=(None, text, title, MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND)).start()
    except Exception:
        pass


def _ui() -> None:
    try:
        import tkinter as tk
    except ImportError:
        while True:
            item = _q.get()
            if item[0] == "card":
                _fallback(item[2], item[3])
    root = tk.Tk()
    root.withdraw()
    open_cards: list = []

    def place(card) -> None:
        card.update_idletasks()
        w, h = card.winfo_width(), card.winfo_height()
        sw = card.winfo_screenwidth()
        y = 40 + sum(c.winfo_height() + 14 for c in open_cards if c is not card and c.winfo_exists())
        card.geometry(f"+{(sw - w) // 2}+{y}")

    def show(kind: str, title: str, text: str, sender: Optional[str], countdown: int) -> None:
        colour, symbol, label = STYLES.get(kind, STYLES["info"])
        card = tk.Toplevel(root)
        card.overrideredirect(True)                       # a card, not a grey system dialog
        card.attributes("-topmost", True)
        try:
            card.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        card.configure(bg=colour)
        frame = tk.Frame(card, bg="white", padx=0, pady=0)
        frame.pack(padx=3, pady=3)
        head = tk.Frame(frame, bg=colour)
        head.pack(fill="x")
        tk.Label(head, text=symbol, bg=colour, fg="white", font=("Segoe UI Symbol", 30), padx=18, pady=6).pack(side="left")
        tk.Label(head, text=title or label, bg=colour, fg="white", font=("Segoe UI", 15, "bold"),
                 anchor="w", padx=4).pack(side="left", fill="x", expand=True)
        body = tk.Frame(frame, bg="white", padx=22, pady=14)
        body.pack(fill="both")
        msg = tk.Label(body, text=text, bg="white", fg="#0f172a", font=("Segoe UI", 13), wraplength=460,
                       justify="left", anchor="w")
        msg.pack(fill="x")
        counter = None
        if countdown:
            counter = tk.Label(body, text=str(countdown), bg="white", fg=colour, font=("Segoe UI", 48, "bold"))
            counter.pack(pady=(6, 0))
        meta = (f"From {sender} · " if sender else "") + datetime.now().strftime("%H:%M")
        tk.Label(body, text=meta, bg="white", fg="#64748b", font=("Segoe UI", 9), anchor="w").pack(fill="x", pady=(10, 0))

        def close() -> None:
            if card in open_cards:
                open_cards.remove(card)
            card.destroy()
            for c in open_cards:
                place(c)
        if not countdown:                                   # a countdown stays until the PC goes down
            tk.Button(body, text="Got it", command=close, bg=colour, fg="white", activebackground=colour,
                      relief="flat", font=("Segoe UI", 11, "bold"), padx=26, pady=4, cursor="hand2").pack(anchor="e", pady=(8, 0))
        open_cards.append(card)
        place(card)

        def fade(a: float = 0.0) -> None:
            try:
                card.attributes("-alpha", min(1.0, a))
            except tk.TclError:
                return
            if a < 1.0:
                card.after(25, fade, a + 0.1)
        fade()
        if countdown and counter is not None:
            end = time.monotonic() + countdown

            def tick() -> None:
                if not card.winfo_exists():
                    return
                counter.config(text=str(max(0, int(round(end - time.monotonic())))))
                card.after(250, tick)
            tick()

    cover = {"win": None}

    def cover_on(title: str, text: str) -> None:
        """Maintenance (2026-10-21): a full-screen cover over every monitor that cannot be closed and
        keeps itself on top; clicks and keys go to it, not to the programs behind."""
        if cover["win"] is not None and cover["win"].winfo_exists():
            return
        import ctypes
        u = ctypes.windll.user32
        x, y, w, h = u.GetSystemMetrics(76), u.GetSystemMetrics(77), u.GetSystemMetrics(78), u.GetSystemMetrics(79)
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.configure(bg="#0b1220", cursor="no")
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        stripe = tk.Frame(win, bg="#f59e0b", height=14)
        stripe.pack(fill="x", side="top")
        box = tk.Frame(win, bg="#0b1220")
        box.place(relx=0.5, rely=0.45, anchor="center")
        tk.Label(box, text="\u2692", bg="#0b1220", fg="#f59e0b", font=("Segoe UI Symbol", 110)).pack()
        tk.Label(box, text=title, bg="#0b1220", fg="white", font=("Segoe UI", 54, "bold")).pack(pady=(0, 6))
        tk.Label(box, text=text, bg="#0b1220", fg="#cbd5e1", font=("Segoe UI", 20), wraplength=int(w * 0.6),
                 justify="center").pack()
        clock = tk.Label(box, text="", bg="#0b1220", fg="#64748b", font=("Segoe UI", 14))
        clock.pack(pady=(24, 0))
        tk.Frame(win, bg="#f59e0b", height=14).pack(fill="x", side="bottom")
        for seq in ("<Alt-F4>", "<Escape>", "<Key>"):
            win.bind(seq, lambda e: "break")
        cover["win"] = win

        def keep_on_top() -> None:
            if not win.winfo_exists():
                return
            win.attributes("-topmost", True)
            win.lift()
            try:
                win.focus_force()
            except tk.TclError:
                pass
            clock.config(text=datetime.now().strftime("%H:%M") + "  \u00b7  Smart Lab")
            win.after(400, keep_on_top)
        keep_on_top()
        try:
            win.grab_set_global()                         # mouse and keyboard stay on the cover
        except tk.TclError:
            pass

    def cover_off() -> None:
        w = cover["win"]
        cover["win"] = None
        if w is not None and w.winfo_exists():
            try:
                w.grab_release()
            except tk.TclError:
                pass
            w.destroy()

    def pump() -> None:
        try:
            while True:
                item = _q.get_nowait()
                if item[0] == "card":
                    show(*item[1:])
                elif item[0] == "cover_on":
                    cover_on(item[1], item[2])
                elif item[0] == "cover_off":
                    cover_off()
        except queue.Empty:
            pass
        root.after(100, pump)
    pump()
    root.mainloop()


def _start() -> None:
    with _lock:
        if not _started[0]:
            _started[0] = True
            threading.Thread(target=_ui, daemon=True).start()


def notice(kind: str, text: str, title: str = "", sender: Optional[str] = None, countdown: int = 0) -> None:
    """Show a card on this PC (non-blocking)."""
    print(f"[{kind}] {title or STYLES.get(kind, STYLES['info'])[2]}: {text}")
    _start()
    _q.put(("card", kind, title, text, sender, countdown))


def cover(on: bool, title: str = "Under Maintenance",
          text: str = "Lab staff are working on this PC. It cannot be used right now - please use another PC.") -> None:
    """The full-screen maintenance cover on / off."""
    print(f"[maintenance] cover {'on' if on else 'off'}")
    _start()
    _q.put(("cover_on", title, text) if on else ("cover_off",))
