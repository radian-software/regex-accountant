import argparse
import dateparser
import importlib
import json
import logging
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
    logging.basicConfig(level="INFO")

    parser = argparse.ArgumentParser("rac")
    parser.add_argument("account", type=str)
    parser.add_argument("--start-date", type=str)
    parser.add_argument("--end-date", type=str)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--reauth", action="store_true")
    args = parser.parse_args()

    start_date = dateparser.parse(args.start_date)
    end_date = dateparser.parse(args.end_date)

    if not start_date:
        raise Exception(f"Failed to recognize start date: {args.start_date}")

    if not end_date:
        raise Exception(f"Failed to recognize start date: {args.end_date}")

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

    if args.reauth:
        account_session = None
    else:
        try:
            account_session = utils.dict_to_dataclass(
                all_sessions.get(args.account), Session
            )
        except Exception:
            account_session = None

    ctx = api.Context(account_config, account_session, args.debug)
    try:
        fetcher = Fetcher()
        try:
            logging.info("Checking auth")
            auth_passed = fetcher.check_auth(ctx)
        except Exception:
            auth_passed = False
        if not auth_passed:
            logging.info("Auth failed, re-authenticating")
            all_sessions[args.account] = utils.dataclass_to_dict(
                fetcher.authenticate(ctx)
            )
            write_sessions(all_sessions)

        logging.info("Getting transactions")
        txns = fetcher.get_transactions(ctx, start_date, end_date)
        print(txns)

    finally:
        ctx.close_browser()

    sys.exit(0)
