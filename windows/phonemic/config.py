import json
import os
from dataclasses import dataclass, asdict, field


@dataclass
class AppConfig:
    wifi_ip: str = ""
    mode: str = "usb"
    high_quality: bool = False
    noise_gate: bool = False
    noise_gate_threshold: float = 0.02


def config_path() -> str:
    folder = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PhoneMic")
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "config.json")


def load_config() -> AppConfig:
    try:
        with open(config_path(), "r", encoding="utf-8") as f:
            raw = json.load(f)
        valid = {k: v for k, v in raw.items() if k in AppConfig.__dataclass_fields__}
        return AppConfig(**valid)
    except Exception:
        return AppConfig()


def save_config(cfg: AppConfig) -> None:
    try:
        with open(config_path(), "w", encoding="utf-8") as f:
            json.dump(asdict(cfg), f)
    except Exception:
        pass
