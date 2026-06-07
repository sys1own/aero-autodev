"""Sample cold-path: configuration boilerplate."""

DATABASE_URL = "sqlite:///data.db"
DEBUG = True
MAX_RETRIES = 3
LOG_LEVEL = "INFO"

ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

TEMPLATES = {
    "engine": "jinja2",
    "dirs": ["templates/"],
}
