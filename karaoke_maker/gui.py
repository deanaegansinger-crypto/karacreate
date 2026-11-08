"""The Karaoke Maker window.

Drag songs in (or use Add songs), press Start, and check each song's lyrics
when they're ready. The slow work runs one song at a time in the
background, so the window stays usable; its messages show in the log at
the bottom.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

from .cli import LYRICS, WORK_SUFFIX, cmd_build, default_options, prepare_song, read_lyrics_file, write_lyrics_file
from .songs import AUDIO_EXTS, Song, find_song

HERE = Path(__file__).resolve().parent.parent
SETTINGS = HERE / "settings.json"
ICON = HERE / "karaoke.ico"

TEXT_SIZES = {"small": "Small (8 lines)", "large": "Large (5 lines)", "huge": "Huge (4 lines)"}
LANGUAGES = {"": "Detect", "en": "English"}

WAITING, QUEUED, WORKING, READY, BUILDING, DONE, FAILED = (
    "Waiting: press Start", "In the queue", "Working...", "Lyrics ready: check them",
    "Making the files...", "Done", "Didn't work: see the log",
)


class LogWriter:
    """Stands in for stdout/stderr: everything printed goes to the log."""

    def __init__(self, events: queue.Queue) -> None:
        self.events = events

    def write(self, text: str) -> int:
        if text:
            self.events.put(("log", text))
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return False


class Worker(threading.Thread):
    """Runs the slow jobs, one at a time, and reports back through events."""

    def __init__(self, events: queue.Queue) -> None:
        super().__init__(daemon=True)
        self.jobs: queue.Queue = queue.Queue()
        self.events = events

    def run(self) -> None:
        while True:
            kind, key, payload, options = self.jobs.get()
            self.events.put(("status", key, WORKING if kind == "prepare" else BUILDING))
            try:
                if kind == "prepare":
                    print(f"\n=== {payload.name} ===")
                    prepare_song(payload, options)
                    self.events.put(("ready", key, None))
                else:
                    options.work = str(payload)
                    outputs = cmd_build(options)
                    self.events.put(("done", key, outputs))
            except SystemExit as e:
                print(e.code)
                self.events.put(("failed", key, str(e.code)))
            except Exception:
                traceback.print_exc()
                self.events.put(("failed", key, "see the log"))


class LyricsEditor(tk.Toplevel):
    """Check a song's title, artist and lyrics, then make its files."""

    def __init__(self, app: "App", key: str, song: Song) -> None:
        super().__init__(app.root)
        self.app, self.key, self.song = app, key, song
        self.path = song.work / LYRICS
        title, artist, lines = read_lyrics_file(self.path)
        self.title(f"Check the lyrics: {song.name}")
        self.geometry("620x600")
        self.minsize(420, 400)
        self.transient(app.root)
        app.set_icon(self)

        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        self.title_var = tk.StringVar(value=title)
        self.artist_var = tk.StringVar(value=artist)
        for row, (label, var) in enumerate((("Title", self.title_var), ("Artist", self.artist_var))):
            ttk.Label(top, text=label).grid(row=row, column=0, sticky="w", pady=3)
            ttk.Entry(top, textvariable=var).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=3)
        top.columnconfigure(1, weight=1)

        ttk.Label(
            self, padding=(12, 0), wraplength=590, justify="left",
            text="Fix any wrong words against the video. Keep one sung line per line: "
                 "long lines wrap on the karaoke screen. The timing comes from the singing, "
                 "so words you fix or add are still timed.",
        ).pack(fill="x")

        buttons = ttk.Frame(self, padding=(12, 0, 12, 12))
        buttons.pack(side="bottom", fill="x")
        box = ttk.Frame(self, padding=12)
        box.pack(fill="both", expand=True)
        self.text = ScrolledText(box, wrap="word", font=("Segoe UI", 12), undo=True)
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", "\n".join(lines))
        self.text.edit_reset()

        playable = song.original or song.vocals
        if playable and hasattr(os, "startfile"):
            ttk.Button(buttons, text="Play the song", command=lambda: os.startfile(playable)).pack(side="left")
        ttk.Button(buttons, text="Make karaoke files", command=self.make, style="Accent.TButton").pack(side="right")
        ttk.Button(buttons, text="Later", command=self.later).pack(side="right", padx=8)
        self.protocol("WM_DELETE_WINDOW", self.later)
        self.text.focus_set()

    def save(self) -> None:
        lines = self.text.get("1.0", "end").rstrip("\n").splitlines()
        write_lyrics_file(self.path, self.title_var.get().strip(), self.artist_var.get().strip(), lines)

    def make(self) -> None:
        self.save()
        self.app.build(self.key)
        self.app.editor_closed(self)
        self.destroy()

    def later(self) -> None:
        self.save()
        self.app.editor_closed(self, keep=self.key)
        self.destroy()


class App:
    def __init__(self, root: tk.Tk, dnd: bool) -> None:
        self.root = root
        self.events: queue.Queue = queue.Queue()
        sys.stdout = sys.stderr = LogWriter(self.events)  # type: ignore[assignment]
        self.worker = Worker(self.events)
        self.worker.start()
        self.songs: dict[str, Song] = {}
        self.state: dict[str, str] = {}
        self.outputs: dict[str, list[Path]] = {}
        self.to_check: list[str] = []
        self.editor: LyricsEditor | None = None
        self.busy = False
        self.options = default_options()
        self.load_settings()

        root.title("Karaoke Maker")
        root.geometry("780x600")
        root.minsize(620, 460)
        self.set_icon(root)
        style = ttk.Style(root)
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=26)

        # Songs
        head = ttk.Frame(root, padding=(12, 12, 12, 4))
        head.pack(fill="x")
        hint = "Drag songs and their lalal.ai files in here" if dnd else "Add songs and their lalal.ai files"
        ttk.Label(head, text=hint, font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(head, text="Add songs...", command=self.choose_files).pack(side="right")

        table = ttk.Frame(root, padding=(12, 0))
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=("files", "status"), selectmode="extended")
        self.tree.heading("#0", text="Song", anchor="w")
        self.tree.heading("files", text="Files", anchor="w")
        self.tree.heading("status", text="Status", anchor="w")
        self.tree.column("#0", width=330)
        self.tree.column("files", width=190)
        self.tree.column("status", width=190)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<Double-1>", lambda e: self.check_selected())
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_buttons())

        actions = ttk.Frame(root, padding=(12, 6))
        actions.pack(fill="x")
        self.start_btn = ttk.Button(actions, text="Start", command=self.start, style="Accent.TButton")
        self.start_btn.pack(side="left")
        self.check_btn = ttk.Button(actions, text="Check lyrics", command=self.check_selected)
        self.check_btn.pack(side="left", padx=6)
        self.folder_btn = ttk.Button(actions, text="Open folder", command=self.open_folder)
        self.folder_btn.pack(side="left")
        self.remove_btn = ttk.Button(actions, text="Remove", command=self.remove_selected)
        self.remove_btn.pack(side="right")
        self.progress = ttk.Progressbar(actions, mode="determinate", length=140)
        self.progress.pack(side="right", padx=10)

        # Options
        opts = ttk.LabelFrame(root, text="Karaoke screen and files", padding=(10, 6))
        opts.pack(fill="x", padx=12, pady=(4, 6))
        row1, row2, row3 = ttk.Frame(opts), ttk.Frame(opts), ttk.Frame(opts)
        row1.pack(fill="x")
        row2.pack(fill="x", pady=(6, 0))
        row3.pack(fill="x", pady=(6, 0))
        ttk.Label(row3, text="Save files to").pack(side="left")
        self.save_var = tk.StringVar()
        ttk.Entry(row3, textvariable=self.save_var, state="readonly").pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(row3, text="Choose...", command=self.choose_save_folder).pack(side="left")
        ttk.Button(row3, text="New folder...", command=self.new_save_folder).pack(side="left", padx=6)
        ttk.Button(row3, text="Next to songs", command=lambda: self.set_save_folder(None)).pack(side="left")
        self.show_save_folder()
        ttk.Label(row1, text="Text size").pack(side="left")
        self.size_var = tk.StringVar(value=TEXT_SIZES[self.options.text_size])
        size = ttk.Combobox(row1, textvariable=self.size_var, values=list(TEXT_SIZES.values()), state="readonly", width=15)
        size.pack(side="left", padx=(6, 16))
        size.bind("<<ComboboxSelected>>", lambda e: self.options_changed())
        ttk.Label(row1, text="Sung words").pack(side="left")
        self.swatch = tk.Label(row1, width=3, relief="solid", borderwidth=1, cursor="hand2")
        self.swatch.pack(side="left", padx=6)
        self.swatch.bind("<Button-1>", lambda e: self.choose_color())
        ttk.Button(row1, text="Colour...", command=self.choose_color).pack(side="left", padx=(0, 16))
        ttk.Label(row1, text="Language").pack(side="left")
        self.lang_var = tk.StringVar(value=LANGUAGES.get(self.options.language or "", "Detect"))
        lang = ttk.Combobox(row1, textvariable=self.lang_var, values=list(LANGUAGES.values()), state="readonly", width=8)
        lang.pack(side="left", padx=6)
        lang.bind("<<ComboboxSelected>>", lambda e: self.options_changed())
        self.title_var = tk.BooleanVar(value=self.options.title_screen)
        ttk.Checkbutton(row2, text="Title screen at the start", variable=self.title_var, command=self.options_changed).pack(side="left")
        self.mp4_var = tk.BooleanVar(value=self.options.mp4)
        ttk.Checkbutton(row2, text="Also make an MP4 video", variable=self.mp4_var, command=self.options_changed).pack(side="left", padx=16)
        self.lrc_var = tk.BooleanVar(value=self.options.lrc)
        ttk.Checkbutton(row2, text="Also save .lrc", variable=self.lrc_var, command=self.options_changed).pack(side="left")
        self.show_color()

        # Log
        self.log_box = ScrolledText(root, height=8, font=("Consolas", 9), state="disabled", background="#f6f6f6")
        self.log_box.pack(fill="both", padx=12, pady=(0, 12))

        if dnd:
            from tkinterdnd2 import DND_FILES

            for widget in (root, self.tree):
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", lambda e: self.add_files(root.tk.splitlist(e.data)))

        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.update_buttons()
        missing = missing_parts()
        if missing:
            message = (f"Karaoke Maker's setup in {HERE} isn't finished: {', '.join(missing)} "
                       f"{'is' if len(missing) == 1 else 'are'} missing.\n\n"
                       f"Close this window, double-click Install.bat in that folder and let it run until it says "
                       f"\"All set\". Then open Karaoke Maker again.")
            self.log(message + f"\n(Python: {sys.executable})\n")
            root.after(300, lambda: messagebox.showwarning("Karaoke Maker", message, parent=root))
        else:
            self.log("Karaoke Maker is ready. Add songs, then press Start.\n")
        root.after(100, self.poll)

    # ---------------------------------------------------------- settings
    def set_icon(self, window) -> None:
        try:
            window.iconbitmap(str(ICON))
        except tk.TclError:
            pass

    def load_settings(self) -> None:
        try:
            saved = json.loads(SETTINGS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        for key in ("text_size", "sung_color", "title_screen", "lrc", "mp4", "language", "out_dir"):
            if key in saved:
                setattr(self.options, key, saved[key])

    def options_changed(self) -> None:
        self.options.text_size = next(k for k, v in TEXT_SIZES.items() if v == self.size_var.get())
        self.options.title_screen = self.title_var.get()
        self.options.lrc = self.lrc_var.get()
        self.options.mp4 = self.mp4_var.get()
        self.options.language = next(k for k, v in LANGUAGES.items() if v == self.lang_var.get()) or None
        saved = {k: getattr(self.options, k) for k in ("text_size", "sung_color", "title_screen", "lrc", "mp4", "language", "out_dir")}
        try:
            SETTINGS.write_text(json.dumps(saved, indent=1), encoding="utf-8")
        except OSError:
            pass

    def show_save_folder(self) -> None:
        folder = self.options.out_dir
        self.save_var.set(folder if folder else "Next to each song")

    def set_save_folder(self, folder: str | None) -> None:
        self.options.out_dir = folder
        self.show_save_folder()
        self.options_changed()
        if folder:
            self.log(f"Finished files will be saved in {folder}\n")
        else:
            self.log("Finished files will be saved next to each song.\n")

    def choose_save_folder(self) -> None:
        folder = filedialog.askdirectory(parent=self.root, title="Save the karaoke files in...",
                                         initialdir=self.options.out_dir or str(Path.home()), mustexist=True)
        if folder:
            self.set_save_folder(str(Path(folder)))

    def new_save_folder(self) -> None:
        """Make a new folder (inside the save folder, or one picked) and
        save there from now on."""
        parent = self.options.out_dir
        if not parent or not Path(parent).is_dir():
            parent = filedialog.askdirectory(parent=self.root, title="Where should the new folder go?",
                                             initialdir=str(Path.home()), mustexist=True)
            if not parent:
                return
        name = simpledialog.askstring("New folder", f"Name for the new folder in\n{parent}:", parent=self.root)
        name = (name or "").strip().strip(".")
        if not name:
            return
        if any(c in name for c in '<>:"/\\|?*'):
            messagebox.showerror("New folder", 'A folder name can\'t contain any of  < > : " / \\ | ? *', parent=self.root)
            return
        folder = Path(parent) / name
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            messagebox.showerror("New folder", f"Couldn't make the folder:\n{e}", parent=self.root)
            return
        self.set_save_folder(str(folder))

    def show_color(self) -> None:
        self.swatch.configure(background=self.options.sung_color)

    def choose_color(self) -> None:
        _, hex_color = colorchooser.askcolor(self.options.sung_color, parent=self.root, title="Colour of sung words")
        if hex_color:
            self.options.sung_color = hex_color
            self.show_color()
            self.options_changed()

    # ---------------------------------------------------------- songs
    def choose_files(self) -> None:
        exts = " ".join(f"*{e}" for e in sorted(AUDIO_EXTS))
        paths = filedialog.askopenfilenames(parent=self.root, title="Choose songs and their lalal.ai files",
                                            filetypes=[("Songs", exts), ("All files", "*.*")])
        self.add_files(paths)

    def add_files(self, paths) -> None:
        for p in paths:
            path = Path(p)
            if path.is_dir():
                self.add_files([f for f in sorted(path.iterdir()) if f.suffix.lower() in AUDIO_EXTS])
                continue
            if not path.is_file() or path.suffix.lower() not in AUDIO_EXTS:
                continue
            song = find_song(path.resolve())
            if song is None:
                self.log(f"Skipped {path.name}: it's already a finished karaoke track.\n")
                continue
            key = str(song.work)
            if key in self.songs:
                self.songs[key] = song  # may have found more of its files now
                self.tree.item(key, values=(describe(song), self.state[key]))
                continue
            self.songs[key] = song
            done_before = (song.work / LYRICS).exists()
            self.state[key] = WAITING
            self.tree.insert("", "end", iid=key, text=song.name, values=(describe(song), WAITING))
            if done_before:
                self.log(f"{song.name}: worked on before, so the slow steps will be skipped.\n")
        self.update_buttons()

    def selected(self) -> list[str]:
        return list(self.tree.selection())

    def set_state(self, key: str, state: str) -> None:
        if key in self.state:
            self.state[key] = state
            self.tree.set(key, "status", state)
        self.update_buttons()

    def update_buttons(self) -> None:
        sel = self.selected()
        startable = [k for k, s in self.state.items() if s in (WAITING, FAILED)]
        self.start_btn.state(["!disabled"] if startable else ["disabled"])
        checkable = any(self.state.get(k) in (READY, DONE) for k in sel)
        self.check_btn.state(["!disabled"] if checkable else ["disabled"])
        has_output = any(k in self.outputs for k in sel)
        self.folder_btn.state(["!disabled"] if has_output else ["disabled"])
        removable = sel and all(self.state.get(k) not in (QUEUED, WORKING, BUILDING) for k in sel)
        self.remove_btn.state(["!disabled"] if removable else ["disabled"])
        busy = any(s in (QUEUED, WORKING, BUILDING) for s in self.state.values())
        if busy and not self.busy:
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
        elif not busy:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=0)
        self.busy = busy

    def start(self) -> None:
        for key, state in self.state.items():
            if state in (WAITING, FAILED):
                self.set_state(key, QUEUED)
                self.worker.jobs.put(("prepare", key, self.songs[key], argparse.Namespace(**vars(self.options))))

    def build(self, key: str) -> None:
        self.set_state(key, QUEUED)
        self.worker.jobs.put(("build", key, self.songs[key].work, argparse.Namespace(**vars(self.options))))

    def remove_selected(self) -> None:
        for key in self.selected():
            self.tree.delete(key)
            for d in (self.songs, self.state, self.outputs):
                d.pop(key, None)
            if key in self.to_check:
                self.to_check.remove(key)
        self.update_buttons()

    def check_selected(self) -> None:
        for key in self.selected():
            if self.state.get(key) in (READY, DONE):
                self.check(key)
                return

    def check(self, key: str) -> None:
        if self.editor is not None:
            if self.editor.key != key and key not in self.to_check:
                self.to_check.append(key)
            self.editor.lift()
            return
        if key in self.to_check:
            self.to_check.remove(key)
        self.editor = LyricsEditor(self, key, self.songs[key])

    def editor_closed(self, editor: LyricsEditor, keep: str | None = None) -> None:
        self.editor = None
        if self.to_check:
            self.root.after(200, lambda: self.check(self.to_check[0]))

    def open_folder(self) -> None:
        for key in self.selected():
            if key in self.outputs and hasattr(os, "startfile"):
                os.startfile(self.outputs[key][0].parent)
                return

    # ---------------------------------------------------------- events
    def poll(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if event[0] == "log":
                    self.log(event[1])
                    continue
                kind, key, payload = event
                if kind == "status":
                    self.set_state(key, payload)
                elif kind == "ready":
                    self.set_state(key, READY)
                    self.check(key)
                elif kind == "done":
                    self.outputs[key] = payload
                    self.set_state(key, DONE)
                    self.log(f"Made: {', '.join(p.name for p in payload)}\n")
                elif kind == "failed":
                    self.set_state(key, FAILED)
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def log(self, text: str) -> None:
        box = self.log_box
        box.configure(state="normal")
        # Progress bars redraw their line with a carriage return.
        for i, part in enumerate(text.split("\r")):
            if i:
                box.delete("end-1c linestart", "end-1c")
            box.insert("end", part)
        if int(box.index("end-1c").split(".")[0]) > 3000:
            box.delete("1.0", "1000.0")
        box.see("end")
        box.configure(state="disabled")

    def quit(self) -> None:
        busy = any(s in (QUEUED, WORKING, BUILDING) for s in self.state.values())
        if busy and not messagebox.askyesno("Karaoke Maker", "Songs are still being worked on. Stop and close?", parent=self.root):
            return
        self.root.destroy()
        os._exit(0)  # don't wait for a song in progress


def missing_parts() -> list[str]:
    """Parts Install.bat should have installed but didn't (say it was
    closed before it finished)."""
    import importlib.util

    parts = {"numpy": "numpy", "PIL": "pillow", "torch": "torch", "whisperx": "whisperx",
             "demucs": "demucs", "imageio_ffmpeg": "imageio-ffmpeg"}
    return [name for module, name in parts.items() if importlib.util.find_spec(module) is None]


def describe(song: Song) -> str:
    if song.backing and song.vocals:
        return "lalal.ai: both files" if not song.original else "Song + both lalal.ai files"
    if song.backing:
        return "Song + lalal.ai no-vocals"
    if song.vocals:
        return "Song + lalal.ai vocals"
    return "Song only (vocals removed here)"


def main() -> None:
    try:
        try:
            from tkinterdnd2 import TkinterDnD

            root, dnd = TkinterDnD.Tk(), True
        except Exception:
            root, dnd = tk.Tk(), False
        app = App(root, dnd)
        app.add_files(sys.argv[1:])
        root.mainloop()
    except Exception:
        # Started from the desktop shortcut there's no console to show
        # errors in, so keep them in a file and say where.
        log = HERE / "error-log.txt"
        log.write_text(traceback.format_exc(), encoding="utf-8")
        messagebox.showerror("Karaoke Maker", f"Karaoke Maker couldn't start. The details are in:\n{log}")
        raise


if __name__ == "__main__":
    main()
