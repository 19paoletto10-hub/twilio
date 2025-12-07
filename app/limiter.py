import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Module-level Limiter instance so decorators (imported at module import time)
# have a valid object reference. The storage backend (Redis) is configured
# on the Flask app before `limiter.init_app(app)` is called.
limiter = Limiter(key_func=get_remote_address)


def init_limiter(app):
    """Initialize the Limiter extension on `app`.

    If `RATELIMIT_STORAGE_URL` is provided in the environment, set it on
    `app.config['RATELIMIT_STORAGE_URI']` so `flask-limiter` uses Redis.
    """
    storage = os.getenv("RATELIMIT_STORAGE_URL")
    default_limits = ["200 per day", "50 per hour"]
    if storage:
        app.config.setdefault("RATELIMIT_STORAGE_URI", storage)
    # Ensure a sane default if not already configured
    app.config.setdefault("RATELIMIT_DEFAULT", default_limits)
    limiter.init_app(app)
    return limiter

