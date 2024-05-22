import logging
import os
from pathlib import Path

import flask

from regex_accountant.fetcher_api import AccountTransaction, Transaction
import regex_accountant.log as log
import regex_accountant.persist as persist
import regex_accountant.utils as utils


class Server:
    def __init__(self):
        self.load_transactions()
        self.app = self._get_app()

    def _get_app(self):
        here = Path(__file__).resolve().parent
        app = flask.Flask(
            __name__, template_folder=here / "server_assets" / "templates"
        )

        @app.route("/")
        def _route_app():
            return flask.render_template("app.html", txns=self.txns)

        @app.route("/txn/<account_id>/<txn_id>")
        def _route_txn(account_id: str, txn_id: str):
            if not (txn := self.txns_by_id[account_id, txn_id]):
                return flask.abort(404)
            return flask.render_template("txn.html", txn=txn)

        return app

    def load_transactions(self):
        cfg = persist.read_config()
        txns = []
        for account in cfg["accounts"]:
            ts = persist.read_txns(account)
            if ts:
                txns.extend(
                    utils.dict_to_obj(AccountTransaction, {**txn, "account": account})
                    for txn in ts["txns"]
                )
        self.txns = txns
        self.txns.sort(key=lambda txn: txn.sort_date)
        self.txns_by_id = {}
        for txn in self.txns:
            if isinstance(txn.date_posted, str):
                raise RuntimeError(f"{txn.account}, {txn.source_uid}")
            self.txns_by_id[txn.account, txn.source_uid] = txn
        logging.info(
            f"Loaded {len(txns)} transactions from {len(cfg['accounts'])} accounts"
        )


log.setup_logger(debug=bool(os.environ.get("REGEX_ACCOUNTANT_DEBUG")))
server = Server()
flask_app = server.app
