from __future__ import annotations
import json
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import List

# Директория для конфигов
CONFIG_DIR = Path("config")
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "settings.json"

@dataclass
class Site:
    name: str
    url: str
    autostart: bool = False

@dataclass
class Settings:
    theme: str = "glossy-gray"     # glossy-gray | dark | light
    background: str = ""           # путь к картинке или пусто
    sites: List[Site] = field(default_factory=lambda: [
        Site(name="YouTube", url="https://youtube.com", autostart=False),
        Site(name="Music", url="https://music.youtube.com", autostart=False),
    ])

@dataclass
class Config:
    settings: Settings = field(default_factory=Settings)

DEFAULT_CONFIG = Config()


def _serialize(cfg: Config) -> dict:
    data = asdict(cfg)
    # dataclasses уже превратятся в plain-структуры
    return data


def _deserialize(data: dict) -> Config:
    s = data.get("settings", {})
    # восстановим список сайтов
    sites_raw = s.get("sites", [])
    sites = [Site(**x) for x in sites_raw]
    settings = Settings(
        theme=s.get("theme", DEFAULT_CONFIG.settings.theme),
        background=s.get("background", DEFAULT_CONFIG.settings.background),
        sites=sites or DEFAULT_CONFIG.settings.sites,
    )
    return Config(settings=settings)


def load_config() -> Config:
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return _deserialize(data)
        except Exception:
            pass
    # если нет файла или он битый — создаём дефолтный
    save_config(DEFAULT_CONFIG)
    return DEFAULT_CONFIG


def save_config(cfg: Config) -> None:
    data = _serialize(cfg)
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
