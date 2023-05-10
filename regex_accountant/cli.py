import argparse
import importlib
import json
import sys

from xdg_base_dirs import xdg_config_home, xdg_data_home
import yaml

import regex_accountant.fetcher_api as api
import regex_accountant.utils as utils


def read_config():
    try:
        with open(xdg_config_home() / "regex-accountant" / "config.yaml") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        return {}


def read_sessions():
    try:
        with open(xdg_data_home() / "regex-accountant" / "sessions.json") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def write_sessions(sessions):
    d = xdg_data_home() / "regex-accountant"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / "sessions.json.tmp", "w") as f:
        json.dump(sessions, f, indent=2)
        f.write("\n")
    (d / "sessions.json.tmp").rename(d / "sessions.json")


def main():
    parser = argparse.ArgumentParser("rac")
    parser.add_argument("account", type=str)
    parser.add_argument("-f", "--force-auth", action="store_true")
    args = parser.parse_args()

    all_config = read_config()
    all_sessions = read_sessions()

    module_name = all_config["accounts"][args.account]["module"]

    module = importlib.import_module(module_name)
    Fetcher = module.Fetcher
    Config = module.Config
    Session = module.Session

    account_config = utils.dict_to_dataclass(
        all_config["accounts"][args.account]["config"], Config
    )

    try:
        account_session = utils.dict_to_dataclass(
            all_sessions.get(args.account), Session
        )
    except Exception:
        account_session = None

    ctx = api.Context(account_config, account_session)
    try:
        fetcher = Fetcher()
        try:
            auth_passed = fetcher.check_auth(ctx)
        except Exception:
            auth_passed = False
        if not auth_passed:
            if not args.force_auth:
                raise Exception("Auth failed")
            all_sessions[args.account] = utils.dataclass_to_dict(
                fetcher.authenticate(ctx)
            )
            write_sessions(all_sessions)

    finally:
        ctx.close_browser()

    sys.exit(0)
