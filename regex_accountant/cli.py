import argparse
import dateparser
import importlib
import json
import logging
import logging.config
import sys

import dataclass_wizard as dw
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
    logging.basicConfig(
        level="INFO",
        format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser("rac")

    subparsers = parser.add_subparsers(dest="cmd")

    parser_auth = subparsers.add_parser("auth")
    parser_auth.add_argument("account", type=str)

    parser_txns = subparsers.add_parser("txns")
    parser_txns.add_argument("account", type=str)
    parser_txns.add_argument("--start-date", type=str, required=True)
    parser_txns.add_argument("--end-date", type=str, required=True)

    for subparser in (parser_auth, parser_txns):
        subparser.add_argument("--debug", action="store_true")
        subparser.add_argument("--force-new-session", action="store_true")
        subparser.add_argument("--force-existing-session", action="store_true")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel("DEBUG")

        # No idea how the eff logging configuration is supposed to
        # work. I just want to configure the root logger, not everyone
        # else's shit, thank you very much. I guess listing every
        # Python module that does and could exist is a workaround??
        for mod in (
            "charset_normalizer",
            "pdfminer.cmapdb",
            "pdfminer.pdfdocument",
            "pdfminer.pdfinterp",
            "pdfminer.pdfpage",
            "pdfminer.pdfparser",
            "pdfminer.psparser",
            "selenium.webdriver.common.selenium_manager",
            "selenium.webdriver.common.service",
            "selenium.webdriver.remote.remote_connection",
            "urllib3.connectionpool",
            "urllib3.util.retry",
        ):
            logging.getLogger(mod).setLevel("INFO")

    start_date = None
    end_date = None

    if args.cmd == "txns":

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

    account_config = dw.fromdict(Config, all_config["accounts"][args.account]["config"])

    if args.force_new_session:
        account_session = None
    else:
        try:
            account_session = dw.fromdict(
                Session,
                all_sessions.get(args.account),
            )
        except Exception:
            account_session = None

    ctx = api.Context(account_config, account_session, args.debug)
    try:
        fetcher = Fetcher()
        if args.force_new_session:
            auth_passed = False
        else:
            try:
                logging.info("Checking auth")
                auth_passed = fetcher.check_auth(ctx)
                if not auth_passed:
                    raise RuntimeError("Auth failed")
            except Exception:
                auth_passed = False
                if args.force_existing_session:
                    raise
        if not auth_passed:
            if args.force_new_session:
                logging.info("Forcing to authenticate a new session")
            else:
                logging.info("Auth failed, re-authenticating")
            new_session = fetcher.authenticate(ctx)
            all_sessions[args.account] = utils.asdict(new_session)
            write_sessions(all_sessions)
            ctx.session = new_session

            logging.info("Checking auth after login")
            auth_passed = fetcher.check_auth(ctx)
            if not auth_passed:
                raise Exception("Auth failed even after login")

        if args.cmd == "auth":

            print("Session is authenticated")

        if args.cmd == "txns":

            logging.info("Getting transactions")
            txns = fetcher.get_transactions(ctx, start_date, end_date)
            print(json.dumps(utils.asdict(txns), indent=2, default=str))

    finally:
        ctx.close_browser()

    sys.exit(0)
