"""Optional health-check web endpoint.

Only needed if you also run web.sh alongside the bot worker (e.g. on a
platform that requires binding to $PORT to keep the dyno/service alive).
This does not start a second bot instance -- it never constructs a
Pyrogram Client.
"""

import os

from flask import Flask

app = Flask(__name__)


@app.route("/")
def hello():
    return "AnimePaheBot is running."


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
