"""
Application entry point for development server.

This module starts the Flask development server. For production deployments,
use gunicorn or another WSGI server instead (see Dockerfile).
"""

from app import create_app

# Create application instance (used by gunicorn: gunicorn run:app)
app = create_app()

if __name__ == "__main__":
    # Development server only - not for production use
    settings = app.config["APP_SETTINGS"]
    
    print(f"🚀 Starting Twilio Chat App in {settings.env} mode")
    print(f"📍 Server: http://{settings.host}:{settings.port}")
    print(f"🔧 Debug mode: {'enabled' if settings.debug else 'disabled'}")
    
    # Wyłączamy reloader w dev, aby uniknąć podwójnego startu workerów oraz
    # sytuacji, w której pierwszy proces kończy się przed pełnym rozruchem.
    app.run(
        host=settings.host,
        port=settings.port,
        debug=settings.debug,
        use_reloader=False,
    )
