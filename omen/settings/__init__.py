"""Settings package.

Select an environment via ``DJANGO_SETTINGS_MODULE``:

* ``omen.settings.dev``  – local development (SQLite fallback, dev-login, mock AI).
* ``omen.settings.prod`` – production (Postgres, S3, gunicorn, hardened security).

``manage.py`` defaults to ``omen.settings.dev``.
"""
