from datetime import datetime, timedelta
import itertools
import json
import logging
import re
import shutil

from xdg_base_dirs import xdg_cache_home, xdg_config_home, xdg_data_home
import yaml


def read_config() -> dict:
    try:
        with open(xdg_config_home() / "regex-accountant" / "config.yaml") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}


def read_sessions() -> dict:
    try:
        with open(xdg_data_home() / "regex-accountant" / "sessions.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def read_rules() -> dict:
    try:
        with open(xdg_config_home() / "regex-accountant" / "rules.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def write_sessions(sessions: dict):
    d = xdg_data_home() / "regex-accountant"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "sessions.json.tmp", "w") as f:
        json.dump(sessions, f, indent=2)
        f.write("\n")
    (d / "sessions.json.tmp").rename(d / "sessions.json")


def read_txns(account: str):
    try:
        with open(
            xdg_data_home() / "regex-accountant" / "transactions" / f"{account}.json"
        ) as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def write_txns(account: str, txns: dict):
    d = xdg_data_home() / "regex-accountant" / "transactions"
    d.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy(d / f"{account}.json", d / f"{account}.json.bak")
    except FileNotFoundError:
        pass
    with open(d / f"{account}.json.tmp", "w") as f:
        json.dump(txns, f, indent=2)
        f.write("\n")
    (d / f"{account}.json.tmp").rename(d / f"{account}.json")


def write_to_staging_area(category: str, obj: dict) -> str:
    assert not re.search(r"[0-9]", category)
    for idx in itertools.count():
        fname = (
            xdg_cache_home() / "regex-accountant" / "staging" / f"{category}{idx}.json"
        )
        if fname.exists():
            continue
        fname.parent.mkdir(parents=True, exist_ok=True)
        with open(fname, "w") as f:
            json.dump(
                {
                    "created_ts": int(datetime.now().timestamp()),
                    "data": obj,
                },
                f,
                indent=2,
            )
            f.write("\n")
        idx_file = (
            xdg_cache_home() / "regex-accountant" / "staging" / f"{category}.json"
        )
        earliest_idx = idx
        try:
            with open(idx_file) as f:
                earliest_idx = json.load(f)["earliest_idx"]
        except FileNotFoundError:
            pass
        with open(idx_file, "w") as f:
            json.dump(
                {
                    "updated_ts": int(datetime.now().timestamp()),
                    "earliest_idx": earliest_idx,
                    "latest_idx": idx,
                },
                f,
                indent=2,
            )
            f.write("\n")
        with open(xdg_cache_home() / "regex-accountant" / "staging.json", "w") as f:
            json.dump(
                {
                    "updated_ts": int(datetime.now().timestamp()),
                    "latest_category": category,
                },
                f,
                indent=2,
            )
            f.write("\n")
        return f"{category}{idx}"
    raise AssertionError


def read_from_staging_area(tag: str) -> dict:
    if not tag:
        with open(xdg_cache_home() / "regex-accountant" / "staging.json") as f:
            tag = json.load(f)["latest_category"]
    if not re.search(r"[0-9]", tag):
        with open(
            xdg_cache_home() / "regex-accountant" / "staging" / f"{tag}.json"
        ) as f:
            idx = json.load(f)["latest_idx"]
            tag += str(idx)
    with open(xdg_cache_home() / "regex-accountant" / "staging" / f"{tag}.json") as f:
        return json.load(f)["data"]


def read_from_fetcher_cache(ident: str, ttl: timedelta | None = None) -> str | None:
    fname = xdg_cache_home() / "regex-accountant" / "fetcher-cache" / ident
    try:
        if ttl is not None:
            if datetime.now() - datetime.fromtimestamp(fname.stat().st_mtime) > ttl:
                logging.debug(
                    f"Removing {ident} from fetcher cache as it has passed ttl"
                )
                fname.unlink()
                return None
        with open(fname) as f:
            val = f.read()
            logging.debug(f"Read {ident} from fetcher cache")
            return val
    except FileNotFoundError:
        return None


def write_to_fetcher_cache(ident: str, val: str) -> None:
    fname = xdg_cache_home() / "regex-accountant" / "fetcher-cache" / ident
    fname.parent.mkdir(parents=True, exist_ok=True)
    with open(fname, "w") as f:
        f.write(val)
