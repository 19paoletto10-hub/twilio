from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Create a Limiter instance. In production you should configure a shared storage (Redis).
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per day", "50 per hour"]) 
