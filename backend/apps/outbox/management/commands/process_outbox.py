import time

from django.core.management.base import BaseCommand

from apps.outbox.services import process_pending


class Command(BaseCommand):
    help = "Dispatch pending outbox events (use --loop to run as a lightweight worker)."

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true")
        parser.add_argument("--interval", type=float, default=2.0)

    def handle(self, *args, loop=False, interval=2.0, **options):
        while True:
            count = process_pending()
            if count:
                self.stdout.write(f"dispatched {count} event(s)")
            if not loop:
                return
            time.sleep(interval)
