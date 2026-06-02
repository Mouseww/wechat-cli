"""配置文件管理"""
from __future__ import annotations
import os
import json
from pathlib import Path
from .models import ServerConfig

CONFIG_DIR = Path.home() / ".wechat-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> ServerConfig:
    """加载配置文件"""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ServerConfig(**data)
    return ServerConfig()


def save_config(config: ServerConfig) -> Path:
    """保存配置文件"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)
    return CONFIG_FILE


def get_config_path() -> Path:
    return CONFIG_FILE
