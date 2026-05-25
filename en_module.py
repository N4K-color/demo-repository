"""
Mini English voice module for Jarvis
Standalone usage:  python en_module.py
Import in main.py: from en_module import ENVoiceModule
"""
from __future__ import annotations
import json, threading, queue, time, difflib, webbrowser, os
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional

# ---- config ----

CONFIG_DIR = Path("config")
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "en_settings.json"
DEFAULT_MODEL = str(Path("models") / "en" / "vosk-model-small-en-us-0.15")

@dataclass
class ENSettings:
    wake_word: str = "jarvis"
    sensitivity: int = 3
    model_path: str = DEFAULT_MODEL
    hotkey: str = "ctrl+shift+e"

@dataclass
class ENConfig:
    settings: ENSettings = field(default_factory=ENSettings)

def load_en_config() -> ENConfig:
    if CONFIG_FILE.exists():
        try:
            return ENConfig(settings=ENSettings(**json.loads(CONFIG_FILE.read_text(encoding="utf-8"))))
        except Exception:
            pass
    cfg = ENConfig()
    CONFIG_FILE.write_text(json.dumps(asdict(cfg.settings), indent=2), encoding="utf-8")
    return cfg

def save_en_config(cfg: ENConfig):
    CONFIG_FILE.write_text(json.dumps(asdict(cfg.settings), indent=2), encoding="utf-8")

# ---- English voice module ----

class ENVoiceModule:
    def __init__(self):
        self.cfg = load_en_config()
        self._stop = threading.Event()
        self._q: queue.Queue[bytes] = queue.Queue()
        self._model = None
        self._stream = None
        self._thread: Optional[threading.Thread] = None
        self._engine = None
        self.on_command = None  # callback: fn(text: str) -> bool

    # ---- TTS ----

    def _tts(self):
        if self._engine:
            return
        import pyttsx3
        self._engine = pyttsx3.init()
        self._engine.setProperty('rate', 180)

    def speak(self, text: str):
        try:
            self._tts()
            print(f"EN: {text}")
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception:
            pass

    # ---- STT ----

    def _load_model(self) -> bool:
        if self._model:
            return True
        try:
            from vosk import Model
            p = self.cfg.settings.model_path
            if not Path(p).exists():
                print(f"Model not found: {p}")
                return False
            self._model = Model(p)
            return True
        except Exception as e:
            print(f"Model error: {e}")
            return False

    def _callback(self, indata, frames, time_info, status):
        if status:
            print(status)
        self._q.put(bytes(indata))

    def _open_stream(self):
        import sounddevice as sd
        self._stream = sd.RawInputStream(samplerate=16000, blocksize=640, dtype='int16', channels=1, callback=self._callback)
        self._stream.start()

    def _close_stream(self):
        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
        except Exception:
            pass
        self._stream = None

    # ---- listen once (push-to-talk) ----

    def listen_once(self):
        if not self._load_model():
            self.speak("Model not found. Check path in settings.")
            return
        from vosk import KaldiRecognizer
        try:
            self._open_stream()
            rec = KaldiRecognizer(self._model, 16000)
            self.speak("Listening...")
            t0 = time.time()
            while time.time() - t0 < 10:
                data = self._q.get()
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = (res.get('text') or '').strip()
                    if text:
                        print(f"You: {text}")
                        self._handle(text)
                    break
        finally:
            self._close_stream()

    # ---- always listen (wake word) ----

    def _loop(self):
        if not self._load_model():
            self.speak("Model not found.")
            return
        from vosk import KaldiRecognizer
        wake = self.cfg.settings.wake_word.lower()
        sens = max(1, min(5, self.cfg.settings.sensitivity))
        thr = {1: 0.55, 2: 0.65, 3: 0.75, 4: 0.85, 5: 0.92}[sens]

        try:
            self._open_stream()
            rec = KaldiRecognizer(self._model, 16000)
            self.speak(f"Listening for '{wake}'...")
            last = 0.0
            while not self._stop.is_set():
                data = self._q.get()
                if rec.AcceptWaveform(data):
                    res = json.loads(rec.Result())
                    text = (res.get('text') or '').strip().lower()
                    if not text:
                        continue
                    print(f"Hear: {text}")
                    hit = wake in text or any(difflib.SequenceMatcher(None, wake, w).ratio() >= thr for w in text.split())
                    if hit and time.time() - last > 1.0:
                        last = time.time()
                        self.speak("Yes?")
                        tend = time.time() + 8
                        while time.time() < tend and not self._stop.is_set():
                            d2 = self._q.get()
                            if rec.AcceptWaveform(d2):
                                r2 = json.loads(rec.Result())
                                t2 = (r2.get('text') or '').strip().lower()
                                if t2:
                                    self._handle(t2)
                                break
        finally:
            self._close_stream()

    def start(self):
        self.stop()
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.1)
        self._thread = None

    # ---- command handling ----

    def _handle(self, text: str):
        t = text.lower()
        if self.on_command and self.on_command(t):
            return

        if any(w in t for w in ["youtube", "video"]):
            self.speak("Opening YouTube")
            webbrowser.open("https://youtube.com")
        elif any(w in t for w in ["music", "spotify"]):
            self.speak("Playing music")
            webbrowser.open("https://music.youtube.com")
        elif any(w in t for w in ["time", "clock"]):
            from datetime import datetime
            self.speak(f"It's {datetime.now():%H:%M}")
        elif any(w in t for w in ["google", "search"]):
            query = t.replace("search", "").replace("google", "").strip()
            if query:
                webbrowser.open(f"https://google.com/search?q={query}")
                self.speak(f"Searching {query}")
        elif any(w in t for w in ["hello", "hi", "hey"]):
            self.speak("Hello! How can I help you?")
        elif any(w in t for w in ["bye", "goodbye", "exit", "quit"]):
            self.speak("Goodbye!")
        else:
            self.speak(f"Command not recognized: {text}")

# ---- standalone ----

if __name__ == "__main__":
    import keyboard
    en = ENVoiceModule()
    keyboard.add_hotkey(en.cfg.settings.hotkey, en.listen_once)
    print(f"EN module ready. Press {en.cfg.settings.hotkey} or run: python en_module.py")
    en.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        en.stop()
