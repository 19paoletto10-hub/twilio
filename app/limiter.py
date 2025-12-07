import os
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


def init_limiter(app):
	"""Initialize and return a Limiter for the given app.

	Reads `RATELIMIT_STORAGE_URL` from environment to configure Redis backend
	in production. Falls back to in-memory storage for development.
	"""
	storage = os.getenv("RATELIMIT_STORAGE_URL")
	default_limits = ["200 per day", "50 per hour"]
	if storage:
		limiter = Limiter(key_func=get_remote_address, storage_uri=storage, default_limits=default_limits)
	else:
		limiter = Limiter(key_func=get_remote_address, default_limits=default_limits)
	limiter.init_app(app)
	return limiter

