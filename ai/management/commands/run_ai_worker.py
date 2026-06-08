"""AI job worker.

Two modes:

* **Cron** (``--once --batch N``): process up to N queued jobs then exit. Wire to
  a Railway cron, e.g. every minute::

      python manage.py run_ai_worker --once --batch 5

* **Loop** (``--loop --interval S``): run continuously as a Railway worker::

      python manage.py run_ai_worker --loop --interval 3
"""

from __future__ import annotations

import time

from django.core.management.base import BaseCommand

from ai.jobs import process_queued


class Command(BaseCommand):
    help = "Process queued AIJob rows (cron --once or continuous --loop)."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Process one batch then exit.")
        parser.add_argument("--loop", action="store_true", help="Run continuously.")
        parser.add_argument("--batch", type=int, default=5, help="Max jobs per batch.")
        parser.add_argument("--interval", type=int, default=3, help="Loop sleep seconds.")

    def handle(self, *args, **opts):
        batch = opts["batch"]
        if opts["loop"]:
            self.stdout.write(self.style.SUCCESS(f"AI worker loop (batch={batch})"))
            while True:
                processed = process_queued(batch)
                if processed:
                    self.stdout.write(f"Processed {processed} job(s).")
                time.sleep(opts["interval"])
        else:
            processed = process_queued(batch)
            self.stdout.write(self.style.SUCCESS(f"Processed {processed} job(s)."))
