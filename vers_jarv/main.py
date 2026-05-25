"""
Jarvis 0.2 — единый EXE с GUI + голосом + конфигом (PySide6)
----------------------------------------------------------------
Функции:
- Вкладки: Сайты, Приложения, Игры, Настройки
- Добавление/редактирование/удаление записей; запуск двойным кликом
- Темы с мгновенным применением + отдельная кнопка «Применить» для фона
- Верхняя панель (toolbar) под цвет темы
- Иконка окна (jarvis.ico, если есть в папке)
- Голос: Vosk + sounddevice + pyttsx3
  • Режимы: Push-to-Talk (по горячим клавишам, до 2) / Always-Listen (по триггер-слову)
  • Настройки: горячие клавиши, триггер-слово, чувствительность (1–5)
- Конфиг: config.json в рабочей папке (создаётся автоматически)

Зависимости:
  pip install PySide6 vosk pyttsx3 sounddevice keyboard

Сборка EXE:
  pyinstaller --noconsole --onefile --icon jarvis.ico --name "JarvisDesktop" main.py

Важно:
- Для распознавания речи скачайте модель Vosk RU (например, vosk-model-small-ru-0.22)
  и укажите путь в настройках (Models → Путь к модели) или в конфиге (stt_model_path).

"""
from __future__ import annotations
import os
import sys
import json
import webbrowser
import subprocess
import threading
import queue
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

# ====== Глобальные пути и константы ======
APP_NAME = "JarvisDesktop"
CONFIG_FILE = Path("config.json")
DEFAULT_MODEL_PATH = str(Path("models") / "vosk-model-small-ru-0.22")

# ====== Конфиг ======
@dataclass
class Settings:
    theme: str = "glossy-gray"  # glossy-gray | dark | light
    background: str = ""        # путь к фоновой картинке
    voice_mode: str = "push_to_talk"  # push_to_talk | always_listen
    hotkeys: List[str] = field(default_factory=lambda: ["ctrl+j", ""])  # до 2 хоткеев
    wake_word: str = "джарвис"
    sensitivity: int = 3  # 1..5
    stt_model_path: str = DEFAULT_MODEL_PATH

@dataclass
class Site:
    name: str
    command: str
    url: str

@dataclass
class AppItem:
    name: str
    command: str
    path: str

@dataclass
class Config:
    settings: Settings = field(default_factory=Settings)
    sites: List[Site] = field(default_factory=lambda: [Site("YouTube", "открой ютуб", "https://youtube.com")])
    apps: List[AppItem] = field(default_factory=lambda: [AppItem("Chrome", "открой браузер", r"C:/Program Files/Google/Chrome/Application/chrome.exe")])
    games: List[AppItem] = field(default_factory=lambda: [AppItem("Пример игра", "запусти игру", r"C:/Games/MyGame/Game.exe")])


def load_config() -> Config:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            # миграция с запасом
            s = Settings(**data.get("settings", {}))
            sites = [Site(**x) for x in data.get("sites", [])]
            apps = [AppItem(**x) for x in data.get("apps", [])]
            games = [AppItem(**x) for x in data.get("games", [])]
            return Config(settings=s, sites=sites, apps=apps, games=games)
        except Exception:
            pass
    cfg = Config()
    save_config(cfg)
    return cfg


def save_config(cfg: Config):
    data = {
        "settings": asdict(cfg.settings),
        "sites": [asdict(x) for x in cfg.sites],
        "apps": [asdict(x) for x in cfg.apps],
        "games": [asdict(x) for x in cfg.games],
    }
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ====== Три темы (QSS) ======

def glossy_gray_qss():
    return """
    QWidget { background: #2f3136; color: #eceff4; font-size: 14px; }
    QTabWidget::pane { border: 1px solid #3a3d44; border-radius: 12px; padding: 4px; }
    QTabBar::tab { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a3d44, stop:1 #2a2c31);
                   border: 1px solid #444851; padding: 8px 14px; border-top-left-radius: 10px; border-top-right-radius: 10px; margin-right: 4px; }
    QTabBar::tab:selected { background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a4e57, stop:1 #33363c); }
    QLineEdit, QComboBox, QTableWidget, QTextEdit, QSpinBox { background: #202226; border: 1px solid #444851; border-radius: 10px; padding: 6px; }
    QTableWidget::item:selected { background: #53616f; }
    QPushButton { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #5a5f69, stop:1 #3f434b);
                  border: 1px solid #6a717d; border-radius: 12px; padding: 8px 14px; }
    QPushButton:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #6b717c, stop:1 #4a4f58); }
    QPushButton:pressed { background: #3a3d44; }
    QToolBar { background: #2a2c31; border-bottom: 1px solid #3a3d44; }
    QHeaderView::section { background: #2a2c31; border: 1px solid #3a3d44; padding: 6px; }
    QMessageBox { background: #2f3136; }
    """

def dark_qss():
    return """
    QWidget { background: #232629; color: #e0e0e0; font-size: 14px; }
    QLineEdit, QComboBox, QTableWidget, QTextEdit, QSpinBox { background: #121417; border: 1px solid #3a3d44; border-radius: 8px; padding: 6px; }
    QPushButton { background: #2f3136; border: 1px solid #3a3d44; border-radius: 10px; padding: 8px 14px; }
    QPushButton:hover { background: #3a3d44; }
    QToolBar { background: #1e2023; border-bottom: 1px solid #3a3d44; }
    """

def light_qss():
    return """
    QWidget { background: #f2f2f2; color: #222; font-size: 14px; }
    QLineEdit, QComboBox, QTableWidget, QTextEdit, QSpinBox { background: #fff; border: 1px solid #ccc; border-radius: 8px; padding: 6px; }
    QPushButton { background: #e6e6e6; border: 1px solid #bbb; border-radius: 10px; padding: 8px 14px; }
    QToolBar { background: #e9e9e9; border-bottom: 1px solid #d9d9d9; }
    """

# ====== Диалоги добав/редакт ======
class ItemDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, *, kind: str = "site", item: Optional[object] = None):
        super().__init__(parent)
        self.setWindowTitle("Добавить" if item is None else "Редактировать")
        self.kind = kind
        form = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit()
        self.cmd_edit = QtWidgets.QLineEdit()
        self.path_edit = QtWidgets.QLineEdit()
        browse_btn = QtWidgets.QPushButton("...")
        browse_btn.setFixedWidth(32)

        hb = QtWidgets.QHBoxLayout()
        hb.addWidget(self.path_edit)
        hb.addWidget(browse_btn)

        form.addRow("Название:", self.name_edit)
        form.addRow("Команда:", self.cmd_edit)
        form.addRow("URL/Путь:", hb)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        v = QtWidgets.QVBoxLayout(self)
        v.addLayout(form)
        v.addWidget(btns)

        if item:
            self.name_edit.setText(getattr(item, 'name', ''))
            self.cmd_edit.setText(getattr(item, 'command', ''))
            self.path_edit.setText(getattr(item, 'url', getattr(item, 'path', '')))

        def on_browse():
            if self.kind == 'site':
                return
            p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Выбрать исполняемый файл", filter="Executable (*.exe)")
            if p:
                self.path_edit.setText(p)
        browse_btn.clicked.connect(on_browse)

    def get_result(self):
        name = self.name_edit.text().strip()
        cmd = self.cmd_edit.text().strip()
        val = self.path_edit.text().strip()
        if self.kind == 'site':
            return Site(name=name, command=cmd, url=val)
        else:
            return AppItem(name=name, command=cmd, path=val)

# ====== Списки (таб-листы) ======
class ListTab(QtWidgets.QWidget):
    changed = QtCore.Signal()

    def __init__(self, parent=None, *, kind: str, items: List[object]):
        super().__init__(parent)
        self.kind = kind
        self.items: List[object] = items

        self.search = QtWidgets.QLineEdit(); self.search.setPlaceholderText("Поиск…")
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Название", "Команда", "URL/Путь"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.launch_selected)

        add_btn = QtWidgets.QPushButton("Добавить")
        edit_btn = QtWidgets.QPushButton("Изменить")
        del_btn = QtWidgets.QPushButton("Удалить")
        run_btn = QtWidgets.QPushButton("Запустить")

        btns = QtWidgets.QHBoxLayout()
        btns.addWidget(add_btn); btns.addWidget(edit_btn); btns.addWidget(del_btn)
        btns.addStretch(1); btns.addWidget(run_btn)

        v = QtWidgets.QVBoxLayout(self)
        v.addWidget(self.search)
        v.addWidget(self.table)
        v.addLayout(btns)

        self.search.textChanged.connect(self.refresh)
        add_btn.clicked.connect(self.add_item)
        edit_btn.clicked.connect(self.edit_item)
        del_btn.clicked.connect(self.delete_item)
        run_btn.clicked.connect(self.launch_selected)

        self.refresh()

    def filtered(self):
        q = self.search.text().strip().lower()
        if not q: return self.items
        def m(x):
            if isinstance(x, Site):
                s = f"{x.name} {x.command} {x.url}".lower()
            else:
                s = f"{x.name} {x.command} {x.path}".lower()
            return q in s
        return [x for x in self.items if m(x)]

    def refresh(self):
        rows = self.filtered()
        self.table.setRowCount(len(rows))
        for r, it in enumerate(rows):
            vals = [it.name, it.command, it.url if isinstance(it, Site) else it.path]
            for c, val in enumerate(vals):
                self.table.setItem(r, c, QtWidgets.QTableWidgetItem(val))

    def add_item(self):
        dlg = ItemDialog(self, kind='site' if self.kind=='site' else 'app')
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self.items.append(dlg.get_result())
            self.refresh(); self.changed.emit()

    def idx_current(self) -> int:
        sel = self.table.selectionModel().selectedRows()
        if not sel: return -1
        row = sel[0].row(); vis = self.filtered(); item = vis[row]
        return self.items.index(item)

    def edit_item(self):
        i = self.idx_current()
        if i < 0: return
        old = self.items[i]
        dlg = ItemDialog(self, kind='site' if self.kind=='site' else 'app', item=old)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self.items[i] = dlg.get_result()
            self.refresh(); self.changed.emit()

    def delete_item(self):
        i = self.idx_current()
        if i < 0: return
        self.items.pop(i)
        self.refresh(); self.changed.emit()

    def launch_selected(self):
        i = self.idx_current()
        if i < 0: return
        self.launch_item(self.items[i])

    def launch_item(self, item):
        try:
            if isinstance(item, Site):
                webbrowser.open(item.url)
            else:
                if item.path and Path(item.path).exists():
                    os.startfile(item.path)
                else:
                    QtWidgets.QMessageBox.warning(self, "Ошибка", "Путь не найден")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Ошибка запуска", str(e))

# ====== Голосовой движок ======
class VoiceAssistant(QtCore.QObject):
    log = QtCore.Signal(str)

    def __init__(self, cfg: Config, *, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._listening = False
        self._always_thread: Optional[threading.Thread] = None
        self._stop_flag = threading.Event()
        self._q: queue.Queue[bytes] = queue.Queue()
        self._engine = None  # pyttsx3
        self._vosk_model = None
        self._sd_stream = None

        # горячие клавиши (для push-to-talk)
        self._hotkey_threads: List[threading.Thread] = []

    # ---- TTS ----
    def _tts_init(self):
        if self._engine: return
        import pyttsx3
        self._engine = pyttsx3.init()
        self._engine.setProperty('rate', 180)

    def speak(self, text: str):
        try:
            self._tts_init()
            self.log.emit(f"Jarvis: {text}")
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception:
            pass

    # ---- STT ----
    def _load_model(self) -> bool:
        if self._vosk_model is not None:
            return True
        try:
            from vosk import Model
            model_path = self.cfg.settings.stt_model_path
            if not Path(model_path).exists():
                self.log.emit(f"Модель не найдена: {model_path}")
                return False
            self._vosk_model = Model(model_path)
            return True
        except Exception as e:
            self.log.emit(f"Ошибка загрузки модели: {e}")
            return False

    def _sd_callback(self, indata, frames, time_info, status):
        if status:
            self.log.emit(str(status))
        self._q.put(bytes(indata))

    def _open_stream(self):
        import sounddevice as sd
        self._sd_stream = sd.RawInputStream(samplerate=16000, blocksize=640, dtype='int16', channels=1, callback=self._sd_callback)
        self._sd_stream.start()

    def _close_stream(self):
        try:
            if self._sd_stream:
                self._sd_stream.stop(); self._sd_stream.close()
        except Exception:
            pass
        self._sd_stream = None

    # ---- Режим push-to-talk ----
    def listen_once(self):
        if not self._load_model():
            self.speak("Не найдена модель распознавания. Укажите путь в настройках.")
            return
        from vosk import KaldiRecognizer
        try:
            self._open_stream()
            rec = KaldiRecognizer(self._vosk_model, 16000)
            self.speak("Слушаю…")
            t0 = time.time()
            while time.time() - t0 < 10:  # ограничим до 10 сек на фразу
                data = self._q.get()
                if rec.AcceptWaveform(data):
                    import json as _json
                    res = _json.loads(rec.Result()); text = (res.get('text') or '').strip()
                    if text:
                        self.log.emit(f"Вы: {text}")
                        self._handle_text(text)
                    break
            self.speak("Готов")
        finally:
            self._close_stream()

    # ---- Режим always-listen (wake word) ----
    def _wake_loop(self):
        if not self._load_model():
            self.speak("Не найдена модель распознавания. Укажите путь в настройках.")
            return
        from vosk import KaldiRecognizer
        import difflib, json as _json
        wake = (self.cfg.settings.wake_word or "джарвис").lower()
        sens = max(1, min(5, int(self.cfg.settings.sensitivity)))
        # карта чувствительности → порог схожести (SequenceMatcher ratio)
        thr_map = {1: 0.55, 2: 0.65, 3: 0.75, 4: 0.85, 5: 0.92}
        thr = thr_map.get(sens, 0.75)

        try:
            self._open_stream()
            rec = KaldiRecognizer(self._vosk_model, 16000)
            self.speak("Слушаю в фоне. Произнесите триггер-слово…")
            last_trigger = 0.0
            while not self._stop_flag.is_set():
                data = self._q.get()
                if rec.AcceptWaveform(data):
                    res = _json.loads(rec.Result()); text = (res.get('text') or '').strip().lower()
                    if not text: continue
                    self.log.emit(f"Фон: {text}")
                    # проверим вхождение или схожесть
                    tokens = text.split()
                    hit = False
                    if wake in text:
                        hit = True
                    else:
                        # по словам — вдруг user сказал коротко/коряво
                        for w in tokens:
                            if difflib.SequenceMatcher(None, wake, w).ratio() >= thr:
                                hit = True; break
                    if hit and (time.time() - last_trigger > 1.0):
                        last_trigger = time.time()
                        self.speak("Да?")
                        # дождаться одной следующей фразы и обработать
                        t_end = time.time() + 8
                        while time.time() < t_end and not self._stop_flag.is_set():
                            d2 = self._q.get()
                            if rec.AcceptWaveform(d2):
                                r2 = _json.loads(rec.Result()); t2 = (r2.get('text') or '').strip().lower()
                                if t2:
                                    self.log.emit(f"Команда: {t2}")
                                    self._handle_text(t2)
                                break
        finally:
            self._close_stream()

    def start_always_listen(self):
        self.stop_always_listen()
        self._stop_flag.clear()
        self._always_thread = threading.Thread(target=self._wake_loop, daemon=True)
        self._always_thread.start()

    def stop_always_listen(self):
        self._stop_flag.set()
        if self._always_thread and self._always_thread.is_alive():
            self._always_thread.join(timeout=0.1)
        self._always_thread = None

    # ---- логика команд ----
    def _handle_text(self, text: str):
        t = text.lower()
        # базовые команды
        if any(w in t for w in ["ютуб", "youtube"]):
            self.speak("Открываю Ютуб")
            webbrowser.open("https://youtube.com"); return
        if any(w in t for w in ["музыка", "spotify", "спотифай"]):
            self.speak("Включаю музыку")
            webbrowser.open("https://music.youtube.com"); return
        if any(w in t for w in ["время", "который час"]):
            import datetime as dt
            now = dt.datetime.now().strftime('%H:%M')
            self.speak(f"Сейчас {now}"); return
        # по словарям из GUI
        def try_launch(items: List[AppItem]):
            for it in items:
                if it.command and it.command.lower() in t:
                    self._launch_item(it); return True
            return False
        if try_launch(main_window.cfg.apps) or try_launch(main_window.cfg.games):
            return
        # сайты
        for s in main_window.cfg.sites:
            if s.command and s.command.lower() in t:
                self.speak(f"Открываю {s.name}"); webbrowser.open(s.url); return
        self.speak("Команда не распознана")

    def _launch_item(self, it: AppItem):
        try:
            if it.path.startswith("http"):
                webbrowser.open(it.path)
            elif Path(it.path).exists():
                os.startfile(it.path)
            else:
                self.speak("Путь не найден")
        except Exception:
            self.speak("Ошибка запуска")

# ====== Настройки (вкладка) ======
class SettingsTab(QtWidgets.QWidget):
    changed = QtCore.Signal()

    def __init__(self, parent=None, cfg: Config=None, voice: VoiceAssistant=None):
        super().__init__(parent)
        self.cfg = cfg; self.voice = voice

        # Тема + фон
        self.theme = QtWidgets.QComboBox(); self.theme.addItems(["glossy-gray", "dark", "light"])
        self.bg_label = QtWidgets.QLabel("Фон: не выбран")
        self.bg_label.setWordWrap(True)
        pick_bg = QtWidgets.QPushButton("Выбрать фон…")
        apply_bg = QtWidgets.QPushButton("Применить фон")

        # Голос
        self.mode = QtWidgets.QComboBox(); self.mode.addItems(["push_to_talk", "always_listen"])
        self.hk1 = QtWidgets.QLineEdit(); self.hk2 = QtWidgets.QLineEdit()
        self.wake = QtWidgets.QLineEdit()
        self.sens = QtWidgets.QSpinBox(); self.sens.setRange(1,5)
        self.model_path = QtWidgets.QLineEdit()
        pick_model = QtWidgets.QPushButton("...")
        pick_model.setFixedWidth(36)

        # Макет формы
        form = QtWidgets.QFormLayout()
        form.addRow("Тема:", self.theme)
        form.addRow("Фон:", self.bg_label)
        form.addRow("", pick_bg)
        form.addRow("", apply_bg)
        form.addRow("Режим голоса:", self.mode)
        form.addRow("Горячая клавиша #1:", self.hk1)
        form.addRow("Горячая клавиша #2:", self.hk2)
        form.addRow("Триггер-слово:", self.wake)
        form.addRow("Чувствительность (1-5):", self.sens)

        hb = QtWidgets.QHBoxLayout(); hb.addWidget(self.model_path); hb.addWidget(pick_model)
        form.addRow("Путь к модели:", hb)

        v = QtWidgets.QVBoxLayout(self); v.addLayout(form); v.addStretch(1)

        # init values
        s = self.cfg.settings
        self.theme.setCurrentText(s.theme)
        self._set_bg_label(s.background)
        self.mode.setCurrentText(s.voice_mode)
        self.hk1.setText(s.hotkeys[0] if len(s.hotkeys)>0 else "")
        self.hk2.setText(s.hotkeys[1] if len(s.hotkeys)>1 else "")
        self.wake.setText(s.wake_word)
        self.sens.setValue(int(s.sensitivity))
        self.model_path.setText(s.stt_model_path)

        # handlers
        self.theme.currentTextChanged.connect(self.on_theme)
        pick_bg.clicked.connect(self.on_pick_bg)
        apply_bg.clicked.connect(self.apply_bg)
        self.mode.currentTextChanged.connect(self.on_mode)
        self.hk1.editingFinished.connect(self.on_hotkeys)
        self.hk2.editingFinished.connect(self.on_hotkeys)
        self.wake.editingFinished.connect(self.on_wake)
        self.sens.valueChanged.connect(self.on_sens)
        pick_model.clicked.connect(self.on_pick_model)
        self.model_path.editingFinished.connect(self.on_model_path)

    def _set_bg_label(self, path: str):
        self.bg_label.setText(path if path else "Фон: не выбран")

    def on_theme(self, t: str):
        self.cfg.settings.theme = t; self.changed.emit()

    def on_pick_bg(self):
        p, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Выбрать фон", filter="Images (*.png *.jpg *.jpeg *.bmp)")
        if p:
            self.cfg.settings.background = p
            self._set_bg_label(p)
            self.changed.emit()

    def apply_bg(self):
        self.changed.emit()

    def on_mode(self, m: str):
        self.cfg.settings.voice_mode = m; self.changed.emit()

    def on_hotkeys(self):
        k1 = self.hk1.text().strip(); k2 = self.hk2.text().strip()
        self.cfg.settings.hotkeys = [k1, k2]
        self.changed.emit()

    def on_wake(self):
        self.cfg.settings.wake_word = self.wake.text().strip() or "джарвис"
        self.changed.emit()

    def on_sens(self, v: int):
        self.cfg.settings.sensitivity = int(v)
        self.changed.emit()

    def on_pick_model(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Папка модели Vosk")
        if d:
            self.model_path.setText(d)
            self.on_model_path()

    def on_model_path(self):
        self.cfg.settings.stt_model_path = self.model_path.text().strip()
        self.changed.emit()

# ====== Главное окно ======
class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jarvis 0.2")
        if Path("jarvis.ico").exists():
            self.setWindowIcon(QtGui.QIcon("jarvis.ico"))
        self.resize(1100, 680)
        self.cfg = load_config()
        self.voice = VoiceAssistant(self.cfg)
        self.voice.log.connect(self.on_log)

        # верхняя панель под тему
        self.toolbar = self.addToolBar("main")
        self.toolbar.setMovable(False)
        act_toggle_bg = QtGui.QAction("Фон", self); act_toggle_bg.triggered.connect(self.toggle_bg)
        act_listen = QtGui.QAction("Сказать", self); act_listen.triggered.connect(self.voice.listen_once)
        self.toolbar.addAction(act_toggle_bg); self.toolbar.addAction(act_listen)

        # центральная область с фоном
        self.center = QtWidgets.QStackedWidget()
        self.bg = QtWidgets.QLabel(); self.bg.setScaledContents(True)
        self.panel = QtWidgets.QWidget()
        self.setCentralWidget(self.center)
        self.center.addWidget(self.bg); self.center.addWidget(self.panel)

        # табы
        self.tabs = QtWidgets.QTabWidget()
        self.sites_tab = ListTab(self, kind='site', items=self.cfg.sites)
        self.apps_tab = ListTab(self, kind='app', items=self.cfg.apps)
        self.games_tab = ListTab(self, kind='game', items=self.cfg.games)
        self.settings_tab = SettingsTab(self, cfg=self.cfg, voice=self.voice)

        for t in (self.sites_tab, self.apps_tab, self.games_tab):
            t.changed.connect(self.on_changed)
        self.settings_tab.changed.connect(self.on_changed)

        self.tabs.addTab(self.sites_tab, "Сайты")
        self.tabs.addTab(self.apps_tab, "Приложения")
        self.tabs.addTab(self.games_tab, "Игры")
        self.tabs.addTab(self.settings_tab, "Настройки")

        lay = QtWidgets.QVBoxLayout(self.panel)
        lay.addWidget(self.tabs)

        # логи в статус-баре
        self.status = self.statusBar()

        self.apply_theme()
        self.apply_background()
        self.apply_voice_mode()

        # хоткеи на лету
        self._hotkey_threads: List[threading.Thread] = []
        self.update_hotkeys()

    # --- применяем тему/фон ---
    def apply_theme(self):
        t = self.cfg.settings.theme
        if t == 'glossy-gray': self.setStyleSheet(glossy_gray_qss())
        elif t == 'dark': self.setStyleSheet(dark_qss())
        else: self.setStyleSheet(light_qss())
        # имитация «верхней рамки» — красим toolbar по теме
        # (реальная системная рамка не перекрашивается Qt без фреймлесса)

    def apply_background(self):
        p = self.cfg.settings.background
        if p and Path(p).exists():
            self.bg.setPixmap(QtGui.QPixmap(p))
        else:
            self.bg.setPixmap(QtGui.QPixmap())

    def toggle_bg(self):
        self.center.setCurrentWidget(self.bg if self.center.currentWidget() is self.panel else self.panel)

    # --- голосовой режим ---
    def apply_voice_mode(self):
        m = self.cfg.settings.voice_mode
        if m == 'always_listen':
            self.voice.start_always_listen()
        else:
            self.voice.stop_always_listen()

    def update_hotkeys(self):
        # снять старые
        for th in getattr(self, '_hotkey_threads', []):
            try:
                th.do_run = False
            except Exception:
                pass
        self._hotkey_threads = []
        keys = [k for k in self.cfg.settings.hotkeys if k]
        if not keys:
            return
        import keyboard
        def worker(key):
            t = threading.current_thread();
            keyboard.add_hotkey(key, lambda: self.voice.listen_once())
            while getattr(t, 'do_run', True):
                time.sleep(0.2)
        for k in keys:
            th = threading.Thread(target=worker, args=(k,), daemon=True)
            th.start(); self._hotkey_threads.append(th)

    # --- общие события ---
    def on_changed(self):
        save_config(self.cfg)
        self.apply_theme()
        self.apply_background()
        self.apply_voice_mode()
        self.update_hotkeys()

    def on_log(self, msg: str):
        self.status.showMessage(msg, 5000)

# ====== Точка входа ======
app = None
main_window: MainWindow

def main():
    global app, main_window
    QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    if Path("jarvis.ico").exists():
        app.setWindowIcon(QtGui.QIcon("jarvis.ico"))
    main_window = MainWindow()
    main_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
