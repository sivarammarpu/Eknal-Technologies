import sys
import os

# Make sure the root of the repo is on the path so we can import app.py
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import app

# Vercel expects a WSGI-compatible object named `app`
# The import above already gives us that.
