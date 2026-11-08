"""
On-screen notices on a lab PC (2026-10-21; centred + large since 2026-11-04, owner: "bigger, bolder, most
importantly centralized, above whatever is open").

One UI thread with one hidden Tk root shows every notice as a card in the CENTRE of the primary screen,
always on top: a coloured card, big symbol, title, large bold text, who sent it and when, and a button.
A card closed by the user is gone for good. Other parts:
  * cover(): the full-screen OUT OF ORDER screen (maintenance), mouse and keyboard blocked.
  * share_on(): the presenter's screen, full screen and on top, until the share ends.
Windows' secure desktop (UAC, Ctrl+Alt+Del, the sign-in screen) stays above all of this, by design.
Without tkinter (or off Windows) a plain message box / print is used.
"""
from __future__ import annotations

import io
import queue
import threading
import time
from datetime import datetime
from typing import Callable, Optional

# kind -> (colour, symbol, label)
STYLES = {
    "message": ("#2563eb", "✉", "Message from lab staff"),
    "share":   ("#7c3aed", "▶", "Screen sharing"),
    "view":    ("#0891b2", "◉", "Your screen is being viewed"),
    "ok":      ("#16a34a", "✔", "Access"),
    "warn":    ("#ea580c", "⚠", "Lab staff"),
    "exam":    ("#dc2626", "✎", "Exam mode"),
    "info":    ("#475569", "ℹ", "Smart Lab"),
}
INFO_CARD_S = {"share": 6, "view": 6, "ok": 8, "info": 8}      # short status cards close by themselves
_q: "queue.Queue[tuple]" = queue.Queue()
_started = [False]
_lock = threading.Lock()


def center_xy(screen_w: int, screen_h: int, w: int, h: int, stacked: int = 0) -> tuple[int, int]:
    """Top-left corner that centres a w x h card; a stacked card sits a little lower and to the right."""
    return max(0, (screen_w - w) // 2 + 28 * stacked), max(0, (screen_h - h) // 2 + 28 * stacked)


def _fallback(title: str, text: str) -> None:
    print(f"[{title}] {text}")
    try:
        import ctypes
        MB_ICONINFORMATION, MB_TOPMOST, MB_SETFOREGROUND = 0x40, 0x40000, 0x10000
        threading.Thread(target=ctypes.windll.user32.MessageBoxW, daemon=True,
                         args=(None, text, title, MB_ICONINFORMATION | MB_TOPMOST | MB_SETFOREGROUND)).start()
    except Exception:
        pass


_block = {"tid": None, "on": False}


def block_input(on: bool) -> bool:
    """Maintenance (2026-11-04 owner: "mouse and keyboard do nothing"): low-level keyboard + mouse hooks
    of this user's session that swallow every key, click and mouse move. No admin rights needed. The
    hooks die with the agent process, so a crashed agent can never leave a PC frozen. Ctrl+Alt+Del is
    Windows' own and cannot be blocked (Task Manager is closed by the agent while in maintenance).
    Returns True when the hooks are in place."""
    import ctypes
    from ctypes import wintypes
    if not on:
        _block["on"] = False
        if _block["tid"]:
            ctypes.windll.user32.PostThreadMessageW(_block["tid"], 0x0012, 0, 0)     # WM_QUIT
            _block["tid"] = None
        return True
    if _block["tid"]:
        _block["on"] = True
        return True
    ready, ok = threading.Event(), [False]

    def run() -> None:
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        LRESULT = ctypes.c_ssize_t
        HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        u.SetWindowsHookExW.restype = ctypes.c_void_p
        u.SetWindowsHookExW.argtypes = (ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD)
        u.CallNextHookEx.restype = LRESULT
        u.CallNextHookEx.argtypes = (ctypes.c_void_p, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
        u.UnhookWindowsHookEx.argtypes = (ctypes.c_void_p,)
        k.GetModuleHandleW.restype = wintypes.HMODULE
        hooks = []

        def swallow(code, wp, lp):
            if code >= 0 and _block["on"]:
                return 1                                   # eaten: never reaches any program
            return u.CallNextHookEx(None, code, wp, lp)
        proc = HOOKPROC(swallow)
        for kind in (13, 14):                              # WH_KEYBOARD_LL, WH_MOUSE_LL
            h = u.SetWindowsHookExW(kind, proc, k.GetModuleHandleW(None), 0)
            if h:
                hooks.append(h)
        ok[0] = len(hooks) == 2
        _block["tid"] = k.GetCurrentThreadId()
        _block["on"] = True
        ready.set()
        msg = wintypes.MSG()
        while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            u.TranslateMessage(ctypes.byref(msg))
            u.DispatchMessageW(ctypes.byref(msg))
        for h in hooks:
            u.UnhookWindowsHookEx(h)
    threading.Thread(target=run, daemon=True, name="block-input").start()
    ready.wait(3)
    print(f"[maintenance] mouse + keyboard {'blocked' if ok[0] else 'NOT blocked (hooks refused)'}")
    return ok[0]


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
    open_cards: list = []                # [(card, kind)]

    def raise_cards() -> None:
        for card, _k in open_cards:                       # a message stays readable above a running share
            try:
                card.lift()
            except tk.TclError:
                pass

    def place() -> None:
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()     # the primary screen
        for i, (card, _k) in enumerate(open_cards):
            if card.winfo_exists():
                card.update_idletasks()
                # winfo_reqwidth: a card not drawn yet has winfo_width() == 1, which put it top left (lab, 11-04)
                x, y = center_xy(sw, sh, card.winfo_reqwidth(), card.winfo_reqheight(), i)
                card.geometry(f"+{x}+{y}")

    def force_top(win, focus: bool = True) -> None:
        """Above every ordinary window, Chrome and full-screen apps included: HWND_TOPMOST + the Alt-key
        trick that lets a background process take the foreground."""
        try:
            import ctypes
            u = ctypes.windll.user32
            hwnd = int(win.wm_frame(), 16)
            u.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0040)   # TOPMOST, NOSIZE|NOMOVE|SHOWWINDOW
            if focus:                     # take the foreground only at first, so typing is not stolen forever
                u.keybd_event(0x12, 0, 0, 0)
                u.keybd_event(0x12, 0, 2, 0)
                u.SetForegroundWindow(hwnd)
        except Exception:
            pass
        try:
            win.attributes("-topmost", True)
            win.lift()
        except tk.TclError:
            pass

    def close_card(card) -> None:
        open_cards[:] = [c for c in open_cards if c[0] is not card]
        try:
            card.destroy()
        except tk.TclError:
            pass
        place()

    def show(kind: str, title: str, text: str, sender: Optional[str], countdown: int, expires: int) -> None:
        colour, symbol, label = STYLES.get(kind, STYLES["info"])
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        # Sizes follow the screen: on the 1366 x 768 lab monitors a 200-character message must still fit, OK button included.
        s = max(0.6, min(1.25, min(sw / 1920, sh / 1080)))
        big = max(14, int((34 if len(text) > 90 else 44) * s))
        card = tk.Toplevel(root)
        card.withdraw()                                   # drawn only once it is in the centre
        card.overrideredirect(True)
        card.attributes("-topmost", True)
        card.configure(bg="#facc15")                      # bright frame around every notice
        frame = tk.Frame(card, bg=colour)
        frame.pack(padx=10, pady=10)
        head = tk.Frame(frame, bg=colour)
        head.pack(pady=(18, 0))
        tk.Label(head, text=symbol, bg=colour, fg="#facc15", font=("Segoe UI Symbol", int(60 * s), "bold"), padx=14).pack(side="left")
        tk.Label(head, text=(title or label).upper(), bg=colour, fg="white", font=("Segoe UI", int(34 * s), "bold"),
                 wraplength=int(sw * 0.62)).pack(side="left")
        body = tk.Frame(frame, bg=colour, padx=48, pady=24)
        body.pack(fill="both")
        tk.Label(body, text=text, bg=colour, fg="white", font=("Segoe UI", big, "bold"),
                 wraplength=int(sw * 0.72), justify="center").pack(fill="x")
        counter = None
        if countdown:
            counter = tk.Label(body, text=str(countdown), bg=colour, fg="#facc15", font=("Segoe UI", int(96 * s), "bold"))
            counter.pack(pady=(6, 0))
        meta = (f"From {sender}  ·  " if sender else "") + datetime.now().strftime("%H:%M")
        tk.Label(body, text=meta, bg=colour, fg="#e2e8f0", font=("Segoe UI", int(18 * s), "bold")).pack(pady=(16, 0))
        if not countdown:                                  # a countdown stays until it is over or staff end it
            tk.Button(body, text="OK", command=lambda: close_card(card), bg="#facc15", fg="#0f172a",
                      activebackground="#fde047", relief="flat", font=("Segoe UI", int(26 * s), "bold"), padx=int(80 * s), pady=int(10 * s),
                      cursor="hand2").pack(pady=(20, 0))
        open_cards.append((card, kind))
        place()
        card.deiconify()
        place()
        card.after(60, place)
        # Short status cards never take the keyboard away from what the student is typing.
        steal = kind in ("message", "warn", "exam")
        life = expires or INFO_CARD_S.get(kind, 0)
        if life:
            card.after(int(life * 1000), lambda: close_card(card))

        def stay_on_top(n: int = 0) -> None:               # a program opened later cannot cover it
            try:
                if not card.winfo_exists():
                    return
            except tk.TclError:
                return
            force_top(card, focus=steal and n < 2)
            card.after(400 if n < 10 else 1500, stay_on_top, n + 1)
        stay_on_top()
        if counter is not None:
            end = time.monotonic() + countdown

            def tick() -> None:
                try:
                    counter.config(text=str(max(0, int(round(end - time.monotonic())))))
                    card.after(250, tick)
                except tk.TclError:
                    pass
            tick()

    def clear_cards(kinds: tuple) -> None:
        for card, kind in list(open_cards):
            if not kinds or kind in kinds:
                close_card(card)

    cover = {"win": None}

    def cover_on(title: str, text: str) -> None:
        """Maintenance: a full-screen OUT OF ORDER screen over every monitor that cannot be closed and
        keeps itself on top; mouse and keyboard are blocked while it is up."""
        if cover["win"] is not None and cover["win"].winfo_exists():
            return
        import ctypes
        u = ctypes.windll.user32
        x, y, w, h = u.GetSystemMetrics(76), u.GetSystemMetrics(77), u.GetSystemMetrics(78), u.GetSystemMetrics(79)
        bg = "#7f1d1d"
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"{w}x{h}+{x}+{y}")
        win.configure(bg=bg, cursor="none")
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        for side in ("top", "bottom"):                    # yellow / black hazard stripes
            band = tk.Canvas(win, height=46, bg="#facc15", highlightthickness=0)
            band.pack(fill="x", side=side)
            for i in range(0, w + 92, 92):
                band.create_polygon(i, 0, i + 46, 0, i, 46, i - 46, 46, fill="#111111", outline="")
        box = tk.Frame(win, bg=bg)
        box.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(box, text="⚠", bg=bg, fg="#facc15", font=("Segoe UI Symbol", 150, "bold")).pack()
        tk.Label(box, text=title.upper(), bg=bg, fg="white", font=("Segoe UI", 110, "bold")).pack(pady=(0, 10))
        tk.Label(box, text=text, bg=bg, fg="#fde68a", font=("Segoe UI", 30, "bold"), wraplength=int(w * 0.75),
                 justify="center").pack()
        clock = tk.Label(box, text="", bg=bg, fg="#fca5a5", font=("Segoe UI", 18, "bold"))
        clock.pack(pady=(30, 0))
        for seq in ("<Alt-F4>", "<Escape>", "<Key>"):
            win.bind(seq, lambda e: "break")
        cover["win"] = win
        block_input(True)

        def keep_on_top() -> None:
            if not win.winfo_exists():
                return
            force_top(win)
            clock.config(text=datetime.now().strftime("%H:%M") + "  ·  Smart Lab")
            win.after(400, keep_on_top)
        keep_on_top()

    def cover_off() -> None:
        block_input(False)
        w = cover["win"]
        cover["win"] = None
        if w is not None and w.winfo_exists():
            w.destroy()

    # ---- the presenter's screen, full screen and on top (2026-11-04) ----
    share = {"win": None, "stop": None}

    def share_open(fetch: Callable[[], Optional[bytes]], title: str) -> None:
        if share["win"] is not None:                       # never a second viewer
            return
        from PIL import Image, ImageTk
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        win = tk.Toplevel(root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry(f"{sw}x{sh}+0+0")
        win.configure(bg="black")
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        bar = tk.Label(win, text=f"●  LIVE  -  {title}  -  closes when the presenter stops", bg="#7c3aed",
                       fg="white", font=("Segoe UI", 16, "bold"), pady=6)
        bar.pack(fill="x")
        pic = tk.Label(win, bg="black", fg="white", text="Waiting for the first picture...", font=("Segoe UI", 28, "bold"))
        pic.pack(fill="both", expand=True)
        stop = threading.Event()
        latest: list = [None]

        def fetcher() -> None:                             # network off the UI thread
            while not stop.is_set():
                try:
                    latest[0] = fetch() or latest[0]
                except Exception:
                    pass
                stop.wait(0.25)
        threading.Thread(target=fetcher, daemon=True, name="share-fetch").start()
        share.update(win=win, stop=stop)
        shown: list = [None]
        tick_n = [0]

        def draw() -> None:
            if share["win"] is not win:
                return
            data = latest[0]
            if data is not None and data is not shown[0]:
                shown[0] = data
                try:
                    img = Image.open(io.BytesIO(data))
                    avail_h = max(1, sh - bar.winfo_height())
                    scale = min(sw / img.width, avail_h / img.height)
                    img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.BILINEAR)
                    photo = ImageTk.PhotoImage(img)
                    pic.configure(image=photo, text="")
                    pic.image = photo
                except Exception as e:
                    print(f"[share] bad frame: {e}")
            tick_n[0] += 1
            if tick_n[0] % 10 == 1:
                force_top(win, focus=tick_n[0] < 40)
                raise_cards()
            win.after(100, draw)
        draw()

    def share_close() -> None:
        w, s = share["win"], share["stop"]
        share.update(win=None, stop=None)
        if s is not None:
            s.set()
        if w is not None:
            try:
                w.destroy()
            except tk.TclError:
                pass

    def pump() -> None:
        try:
            while True:
                item = _q.get_nowait()
                try:
                    if item[0] == "card":
                        show(*item[1:])
                    elif item[0] == "clear":
                        clear_cards(item[1])
                    elif item[0] == "cover_on":
                        cover_on(item[1], item[2])
                    elif item[0] == "cover_off":
                        cover_off()
                    elif item[0] == "share_on":
                        share_open(item[1], item[2])
                    elif item[0] == "share_off":
                        share_close()
                except Exception as e:                     # one bad notice never ends the UI thread
                    print(f"[notice] {item[0]} failed: {e}")
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


def notice(kind: str, text: str, title: str = "", sender: Optional[str] = None, countdown: int = 0,
           expires: int = 0) -> None:
    """Show a centred card on this PC (non-blocking). expires: close by itself after this many seconds."""
    print(f"[{kind}] {title or STYLES.get(kind, STYLES['info'])[2]}: {text}")
    _start()
    _q.put(("card", kind, title, text, sender, countdown, expires))


def clear(*kinds: str) -> None:
    """Close the open cards of these kinds (none given: every card)."""
    _start()
    _q.put(("clear", kinds))


def cover(on: bool, title: str = "Out of order",
          text: str = "This PC is under maintenance by lab staff. Mouse and keyboard are disabled - please use another PC.") -> None:
    """The full-screen maintenance cover on / off."""
    print(f"[maintenance] cover {'on' if on else 'off'}")
    _start()
    _q.put(("cover_on", title, text) if on else ("cover_off",))


def can_show_share() -> bool:
    """False when tkinter or Pillow is missing: the agent then opens the browser page as before."""
    try:
        import tkinter  # noqa: F401
        from PIL import Image, ImageTk  # noqa: F401
        return True
    except ImportError:
        return False


def share_on(fetch: Callable[[], Optional[bytes]], title: str) -> None:
    """Show the presenter's screen full screen on top; fetch() returns the latest JPEG (or None)."""
    print(f"[share] viewer on: {title}")
    _start()
    _q.put(("share_on", fetch, title))


def share_off() -> None:
    print("[share] viewer off")
    _start()
    _q.put(("share_off",))
