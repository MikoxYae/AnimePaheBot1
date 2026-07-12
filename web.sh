#!/usr/bin/env bash
# Use this ONLY if your host requires a web-facing process bound to $PORT
# to keep the service alive (e.g. certain "web" dyno types). This starts
# just the optional Flask health-check endpoint -- it must NEVER also start
# bot.py, or you will end up with two Pyrogram clients fighting over the
# same bot token (Telegram then delivers updates unpredictably to whichever
# one currently holds the connection, and commands appear to "not work").
#
# The actual Telegram bot worker is started separately via start.sh
# (see Procfile's "worker" process).
set -e
exec gunicorn app:app
