"""
Launcher — запуск групп приложений по профилям
Использование:
  python launcher.py              # список профилей
  python launcher.py work         # запустить профиль work
  python launcher.py work games   # запустить несколько профилей
"""
from __future__ import annotations
import os, sys, subprocess, webbrowser, json, time
from pathlib import Path
from typing import List, Dict, Optional

CONFIG_DIR = Path("config")
CONFIG_DIR.mkdir(exist_ok=True)
PROFILES_FILE = CONFIG_DIR / "launcher_profiles.json"

DEFAULT_PROFILES: Dict[str, Dict] = {
    "work": {
        "apps": [
            {"name": "Chrome", "path": "C:/Program Files/Google/Chrome/Application/chrome.exe"},
            {"name": "VS Code", "path": "C:/Users/K1suke/AppData/Local/Programs/Microsoft VS Code/Code.exe"},
        ],
        "sites": [
            "https://github.com",
            "https://mail.google.com",
        ],
        "delay": 1,
    },
    "games": {
        "apps": [
            {"name": "Steam", "path": "C:/Program Files (x86)/Steam/Steam.exe"},
        ],
        "sites": [],
        "delay": 2,
    },
    "social": {
        "apps": [],
        "sites": [
            "https://t.me",
            "https://discord.com/app",
            "https://youtube.com",
        ],
        "delay": 0.5,
    },
    "all": {
        "apps": [],
        "sites": [
            "https://youtube.com",
            "https://music.youtube.com",
            "https://github.com",
        ],
        "delay": 0.5,
    },
}


def load_profiles() -> Dict:
    if PROFILES_FILE.exists():
        try:
            return json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    save_profiles(DEFAULT_PROFILES)
    return DEFAULT_PROFILES


def save_profiles(profiles: Dict):
    PROFILES_FILE.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")


def list_profiles(profiles: Dict):
    print("Доступные профили:")
    for name, p in profiles.items():
        apps = [a["name"] for a in p.get("apps", [])]
        sites = p.get("sites", [])
        print(f"  {name}:")
        if apps:
            print(f"    приложения: {', '.join(apps)}")
        if sites:
            print(f"    сайты: {', '.join(sites)}")


def run_profile(name: str, profiles: Dict):
    p = profiles.get(name)
    if not p:
        print(f"Профиль '{name}' не найден")
        return False

    apps: List = p.get("apps", [])
    sites: List = p.get("sites", [])
    delay: float = p.get("delay", 0.5)

    print(f"Запуск профиля '{name}':")
    launched = 0

    for app in apps:
        path = app.get("path", "")
        name_a = app.get("name", path)
        if path and Path(path).exists():
            try:
                subprocess.Popen([path], shell=True)
                print(f"  + {name_a}")
                launched += 1
                time.sleep(delay)
            except Exception as e:
                print(f"  ! {name_a}: {e}")
        else:
            print(f"  - {name_a}: путь не найден ({path})")

    for url in sites:
        try:
            webbrowser.open(url)
            print(f"  + {url}")
            launched += 1
            time.sleep(delay)
        except Exception as e:
            print(f"  ! {url}: {e}")

    print(f"Запущено: {launched}")
    return True


def main():
    profiles = load_profiles()

    if len(sys.argv) < 2:
        list_profiles(profiles)
        print("\nИспользование: python launcher.py <профиль1> [профиль2 ...]")
        return

    for name in sys.argv[1:]:
        run_profile(name, profiles)


if __name__ == "__main__":
    main()
