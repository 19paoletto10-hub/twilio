from functools import wraps
from flask import request, current_app, jsonify


def require_api_key(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        # check header first, then query param
        key = request.headers.get("X-API-KEY") or request.args.get("api_key")
        app_settings = current_app.config.get("APP_SETTINGS")
        expected = None
        if app_settings:
            expected = getattr(app_settings, "api_key", None)

        if not expected:
            # If no api key configured, deny by default in production; allow in dev
            if getattr(app_settings, "env", "dev") != "dev":
                return jsonify({"error": "Unauthorized"}), 401
            # dev mode: allow but warn
            current_app.logger.warning("APP_API_KEY not set; allowing request in dev mode")
            return view(*args, **kwargs)

        if not key or key != expected:
            return jsonify({"error": "Unauthorized"}), 401

        return view(*args, **kwargs)

    return wrapped
