import logging
import os

import flask

import regex_accountant.log as log
import regex_accountant.persist as persist


class Server:
    def __init__(self):
        self.app = flask.Flask(__name__)
        self.load_transactions()
        self.setup_routes()

    def setup_routes(self):
        @self.app.route("/")
        def _route_app():
            return "Hello world"

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
