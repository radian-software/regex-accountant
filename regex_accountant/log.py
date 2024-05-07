import logging


def setup_logger(debug: bool):
    logging.basicConfig(
        level="INFO",
        format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if debug:
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
