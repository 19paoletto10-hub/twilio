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

    def _client_ip() -> str:
        """Resolve caller IP respecting common proxy headers."""

        forwarded_for = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if forwarded_for:
            return forwarded_for

        real_ip = request.headers.get("X-Real-IP", "").strip()
        if real_ip:
            return real_ip

        return request.remote_addr or "unknown"

    @app.before_request
    def log_request():
        app.logger.info(
            "Incoming %s %s from %s",
            request.method,
            request.path,
            _client_ip(),
        )
