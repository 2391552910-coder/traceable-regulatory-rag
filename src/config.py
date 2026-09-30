"""实验配置加载"""
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: str | None = None) -> dict:
    cfg_path = Path(path) if path else ROOT / "configs" / "default.yaml"
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # 环境变量覆盖（API Key 不落仓库）
    cfg["llm"]["api_key"] = os.getenv("LLM_API_KEY", cfg["llm"].get("api_key", ""))
    return cfg
