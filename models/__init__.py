"""
models package
--------------
Exposes a single shared SQLAlchemy `db` instance that every model file
imports from. This avoids circular-import problems between app.py and
individual model modules.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
