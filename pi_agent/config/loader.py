import os
from pathlib import Path
import yaml


def load():
    """
    優先使用環境變數 HOMEPI_CONFIG 指定的 YAML；
    否則 fallback 到 專案內 ./config/homepi.yml；
    再不行就回傳空設定。
    """
    cfg_path = os.environ.get("HOMEPI_CONFIG")
    if cfg_path:
        p = Path(cfg_path)
    else:
        p = Path(__file__).resolve().parent / "homepi.yml"

    if p.is_file():
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return data

    return {}
