import logging
from flask import Flask, request


def configure_logging(app: Flask) -> None:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        root_logger.addHandler(handler)

    @app.before_request
    def log_request():
        app.logger.info(
            "Incoming %s %s from %s",
            request.method,
            request.path,
            request.remote_addr,
        )
