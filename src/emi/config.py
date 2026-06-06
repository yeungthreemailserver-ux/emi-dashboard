"""Paths, constants, and config loading for EMI."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROC_DIR = DATA_DIR / "processed"
DB_PATH = DATA_DIR / "emi.db"

# SEC requires a descriptive User-Agent with contact info for the data.sec.gov APIs.
# Override with the EMI_SEC_USER_AGENT environment variable.
SEC_USER_AGENT = os.environ.get(
    "EMI_SEC_USER_AGENT",
    "Electronic Market Intelligence research yeungthreemailserver@gmail.com",
)


def load_universe() -> dict:
    with open(CONFIG_DIR / "universe.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_sources() -> dict:
    with open(CONFIG_DIR / "sources.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def iter_companies(universe: dict):
    """Flatten the tiered universe into per-company dicts carrying their tier id."""
    for tier in universe.get("tiers", []):
        for company in tier.get("companies", []):
            yield {**company, "tier": tier["id"]}


# --- Layered universe (v2): one YAML file per supply-chain layer in config/universe/ ---
UNIVERSE_DIR = CONFIG_DIR / "universe"


def load_layers() -> list:
    """Load every layer file from config/universe/*.yaml, sorted by filename."""
    if not UNIVERSE_DIR.exists():
        return []
    layers = []
    for path in sorted(UNIVERSE_DIR.glob("*.yaml")):
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if data:
            data["_file"] = path.name
            layers.append(data)
    return layers


def iter_universe():
    """Flatten the layered universe into per-company dicts with layer/sublayer context.

    Yields keys: layer, layer_name, sublayer, sublayer_name, name, ticker, region, end_market.
    """
    for layer in load_layers():
        lid, lname = layer.get("layer"), layer.get("name")
        for sub in layer.get("sublayers", []) or []:
            sid, sname = sub.get("id"), sub.get("name")
            for c in sub.get("companies", []) or []:
                yield {
                    "layer": lid,
                    "layer_name": lname,
                    "sublayer": str(sid) if sid is not None else None,
                    "sublayer_name": sname,
                    "name": c.get("name"),
                    "ticker": str(c.get("ticker")),
                    "region": c.get("region"),
                    "end_market": c.get("end_market"),
                }
