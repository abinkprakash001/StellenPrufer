import sys
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app

class VercelPathMiddleware:
    """Ensures clean routing for Vercel serverless function invocations."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        for prefix in ["/api/index.py", "/api/index"]:
            if path.startswith(prefix + "/"):
                path = path[len(prefix):]
                break
            elif path == prefix:
                path = "/"
                break
        
        # If Flask has routes defined with /api/..., ensure prefix exists
        if not path.startswith("/api") and path != "/" and not path.endswith(".html"):
            environ["PATH_INFO"] = "/api" + path
        else:
            environ["PATH_INFO"] = path
            
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
