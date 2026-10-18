"""Flask application object."""

from werkzeug.serving import run_simple


class Flask:
    """The Flask application object."""
    
    def __init__(self, import_name, **kwargs):
        self.import_name = import_name
        self.name = import_name
        self.url_map = {}
        self.view_functions = {}
    
    def route(self, rule, **options):
        """Decorate a function to register a URL rule."""
        def decorator(f):
            self.url_map[rule] = f
            self.view_functions[rule] = f
            return f
        return decorator
    
    def run(self, host=None, port=None, **kwargs):
        """Run the application."""
        run_simple(host or '127.0.0.1', port or 5000, self, **kwargs)
