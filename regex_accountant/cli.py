import argparse
import dateparser
from datetime import datetime
import importlib
import logging
import logging.config
import os
import subprocess
import sys
import traceback
from typing import cast, Type

import regex_accountant.fetcher_api as api
import regex_accountant.log as log
import regex_accountant.model as model
import regex_accountant.persist as persist
import regex_accountant.utils as utils
from regex_accountant.utils import PACKAGE_DIR


def main():
    log.setup_logger(debug=False)

    parser = argparse.ArgumentParser("rac")

    subparsers = parser.add_subparsers(dest="cmd", required=True)

    parser_auth = subparsers.add_parser("auth")
    parser_auth.add_argument("account", type=str)

    parser_txns = subparsers.add_parser("txns")
    parser_txns.add_argument("account", type=str)
    parser_txns.add_argument("--start-date", type=str, default="1900-01-01")
    parser_txns.add_argument(
        "--end-date", type=str, default=utils.asdate(datetime.now())
    )

    parser_import = subparsers.add_parser("import")
    parser_import.add_argument("tag", type=str, nargs="?", default="")

    parser_ui = subparsers.add_parser("ui")
    parser_ui.add_argument("--port", type=int, default=8395)

    for subparser in (parser_auth, parser_txns, parser_import, parser_ui):
        subparser.add_argument("--debug", action="store_true")

    for subparser in (parser_auth, parser_txns):
        subparser.add_argument("--force-new-session", action="store_true")
        subparser.add_argument("--force-existing-session", action="store_true")
        subparser.add_argument("--force-reauth", action="store_true")
        subparser.add_argument("--no-check-auth", action="store_true")

    args = parser.parse_args()

    if args.debug:
        log.setup_logger(debug=True)

    start_date = None
    end_date = None

    if args.cmd == "txns":

        start_date = dateparser.parse(args.start_date)
        end_date = dateparser.parse(args.end_date)

        if not start_date:
            raise Exception(f"Failed to recognize start date: {args.start_date}")

        if not end_date:
            raise Exception(f"Failed to recognize start date: {args.end_date}")

        if start_date >= end_date:
            raise Exception("Start date needs to be before end date")

    if args.cmd == "auth" or args.cmd == "txns":

        all_config = persist.read_config()
        all_sessions = persist.read_sessions()

        module_name = all_config["accounts"][args.account]["module"]

        old_sys_path = sys.path
        try:
            sys.path = ["", *sys.path]
            module = importlib.import_module(module_name)
        finally:
            sys.path = old_sys_path

        Fetcher: Type[api.Fetcher] = module.Fetcher
        Config: Type[api.Config] = module.Config
        Session: Type[api.Session] = module.Session

        account_config_raw = all_config["accounts"][args.account]["config"]
        if all_config.get("enable_command_execution_on_config_load"):
            for key, val in account_config_raw.items():
                if val.startswith("!"):
                    val = val[1:]
                    if not val.startswith("!"):
                        val = (
                            subprocess.run(
                                ["bash", "-c", val], stdout=subprocess.PIPE, check=True
                            )
                            .stdout.decode()
                            .strip()
                        )
                account_config_raw[key] = val

        account_config = utils.dict_to_obj(Config, account_config_raw)

        if args.force_new_session:
            account_session = None
        else:
            try:
                account_session = utils.dict_to_obj(
                    Session, all_sessions.get(args.account)
                )
            except Exception:
                account_session = None

        ctx = api.Context(account_config, account_session, args.debug)
        try:
            fetcher = Fetcher()
            fetcher.setup(ctx)
            if args.no_check_auth:
                auth_passed = True
            elif args.force_new_session or args.force_reauth:
                auth_passed = False
            else:
                old_debug = ctx.debug
                ctx.debug = False
                try:
                    logging.info("Checking auth")
                    auth_passed = fetcher.check_auth(ctx)
                    if not auth_passed:
                        raise RuntimeError("Auth failed")
                except Exception:
                    auth_passed = False
                    if args.force_existing_session:
                        raise
                finally:
                    ctx.debug = old_debug
            if not auth_passed:
                if args.force_new_session or args.force_reauth:
                    logging.info("Forcing to authenticate a new session")
                else:
                    logging.info("Auth failed, re-authenticating")
                new_session = fetcher.authenticate(ctx)
                all_sessions[args.account] = utils.obj_to_dict(new_session)
                persist.write_sessions(all_sessions)
                ctx.session = new_session

                logging.info("Checking auth after login")
                auth_passed = fetcher.check_auth(ctx)
                if not auth_passed:
                    raise Exception("Auth failed even after login")

            if args.cmd == "auth":

                logging.info("Session is authenticated")

            if args.cmd == "txns":

                assert isinstance(start_date, datetime)
                assert isinstance(end_date, datetime)

                logging.info("Getting transactions")
                txns = fetcher.get_transactions(ctx, start_date, end_date)
                txn_uids = [txn.source_uid for txn in txns]
                try:
                    assert len(txn_uids) == len(
                        set(txn_uids)
                    ), "non-unique txn ids returned"
                except Exception:
                    if ctx.debug:
                        traceback.print_exc()
                        import pdb

                        pdb.set_trace()
                    raise
                logging.info(f"Got {len(txns)} transactions")
                tag = persist.write_to_staging_area(
                    f"txns_{args.account}",
                    utils.obj_to_dict(
                        model.StagedTransactions(
                            account=args.account,
                            start_date=start_date,
                            end_date=end_date,
                            txns=txns,
                        ),
                        prune=True,
                    ),
                )
                logging.info(f"Wrote to staging area as {tag}")

        finally:
            ctx.close_browser()

    if args.cmd == "import":

        staged_data = persist.read_from_staging_area(args.tag)
        staged_data["txns"] = staged_data.get("txns") or []
        staged = utils.dict_to_obj(
            model.StagedTransactions,
            staged_data,
        )
        store = model.TransactionStore()
        if ts := persist.read_txns(staged.account):
            store.accts[staged.account] = utils.dict_to_obj(model.TransactionSet, ts)
        store.import_transactions(staged)
        persist.write_txns(
            staged.account, utils.obj_to_dict(store.accts[staged.account], prune=True)
        )

    if args.cmd == "ui":

        res = subprocess.run(
            [
                "flask",
                "run",
                "-h",
                "127.0.0.1",
                "-p",
                str(args.port),
                *(
                    [
                        "--debug",
                        "--extra-files",
                        ":".join(str(PACKAGE_DIR / p) for p in ["query.lark"]),
                    ]
                    if args.debug
                    else ["--no-debug"]
                ),
            ],
            env={
                **os.environ,
                "FLASK_APP": "regex_accountant.server:flask_app",
                "REGEX_ACCOUNTANT_DEBUG": "1" if args.debug else "",
            },
        )
        sys.exit(res.returncode)

    sys.exit(0)
