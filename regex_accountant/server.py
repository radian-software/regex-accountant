from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path

import flask

from regex_accountant.fetcher_api import Transaction
import regex_accountant.log as log
import regex_accountant.persist as persist
from regex_accountant.postprocess import ExtTransaction as Txn
from regex_accountant.query import Query
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
            txns = list(reversed(self.txns))
            if query := flask.request.args.get("q", "").strip():
                txns = Query(query).apply(txns)
            return flask.render_template(
                "app.html",
                txns=txns,
                query=query,
            )

        @app.route("/styles/<path>")
        def _route_styles(path: str):
            return flask.send_from_directory(
                here / "server_assets" / "static" / "styles", path
            )

        @app.route("/txn/<account_id>/<txn_id>")
        def _route_txn(account_id: str, txn_id: str):
            if not (txn := self.txns_by_id[account_id, txn_id]):
                return flask.abort(404)
            return flask.render_template(
                "txn.html",
                txn=txn,
                txn_json=json.dumps(utils.obj_to_dict(txn, prune=True), indent=2),
            )

        return app

    def load_transactions(self):
        cfg = persist.read_config()
        txns = []
        for account in cfg["accounts"]:
            ts = persist.read_txns(account)
            if ts:
                txns.extend(
                    utils.dict_to_obj(Txn, {**txn, "account": account})
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
