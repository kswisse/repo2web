"""Simple Flask application with environment variables."""
import os
from flask import Flask, jsonify

app = Flask(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
API_KEY = os.environ.get("API_KEY")
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"


@app.route("/")
def index():
    return jsonify({"message": "Hello World"})


@app.route("/health")
def health():
    return jsonify({"status": "healthy"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
