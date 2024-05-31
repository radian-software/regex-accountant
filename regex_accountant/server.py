from dataclasses import dataclass
import logging
import os
from pathlib import Path

import flask

from regex_accountant.fetcher_api import Transaction
import regex_accountant.log as log
import regex_accountant.persist as persist
import regex_accountant.utils as utils


@dataclass
class ExtTransaction(Transaction):
    account: str = ""

    @property
    def summary(self) -> str:
        s = self.description or self.description_short or self.description_details
        if part := (self.client or self.client_short):
            if self.amount > 0:
                s += f" from {part}"
            else:
                s += f" to {part}"
        if part := (
            self.payment_method or self.payment_method_short or self.payment_method_long
        ):
            s += f" via {part}"
        return s


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
            return flask.render_template("app.html", txns=reversed(self.txns))

        @app.route("/styles/<path>")
        def _route_styles(path: str):
            return flask.send_from_directory(
                here / "server_assets" / "static" / "styles", path
            )

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
                    utils.dict_to_obj(ExtTransaction, {**txn, "account": account})
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
