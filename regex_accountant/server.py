import logging
import os
from pathlib import Path

import flask

import regex_accountant.log as log
import regex_accountant.persist as persist


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

        return app

    def load_transactions(self):
        cfg = persist.read_config()
        txns = []
        for account in cfg["accounts"]:
            ts = persist.read_txns(account)
            if ts:
                txns.extend(ts["txns"])
        self.txns = txns
        logging.info(
            f"Loaded {len(txns)} transactions from {len(cfg['accounts'])} accounts"
        )


log.setup_logger(debug=bool(os.environ.get("REGEX_ACCOUNTANT_DEBUG")))
server = Server()
flask_app = server.app
