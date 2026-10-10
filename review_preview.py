"""Run the private operator workflow against a supplied local export."""
import argparse
import json
import os
from pathlib import Path

from flask import Flask
from pmi_review import create_blueprint
from pmi_review_store import ReviewStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Existing complete FIND4 JSON export")
    parser.add_argument("--database", required=True, help="Absolute path for persistent local review storage")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()
    source = Path(args.input).resolve()
    database = Path(args.database).resolve()
    if len(os.getenv("PMI_REVIEW_ACCESS_KEY", "")) < 24:
        parser.error("Set PMI_REVIEW_ACCESS_KEY to a private passphrase of at least 24 characters.")
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 128 * 1024
    app.register_blueprint(create_blueprint(lambda: json.loads(source.read_text()),
                           store_factory=lambda: ReviewStore(str(database)), allow_http=True))
    # Loopback only. HTTP cookies are explicitly limited to this local preview.
    app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
