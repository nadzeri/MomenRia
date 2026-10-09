import time

from django.core.management.base import BaseCommand

from processing.worker import claim_job, run_job


class Command(BaseCommand):
    help = "Run the database-backed image worker"

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        while True:
            job = claim_job()
            if job:
                run_job(job)
            elif options["once"]:
                return
            else:
                time.sleep(2)
            if options["once"]:
                return

