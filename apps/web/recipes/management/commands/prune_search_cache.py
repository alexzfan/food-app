from django.core.management.base import BaseCommand

from recipes import search_cache


class Command(BaseCommand):
    help = "Delete cached YouTube searches and orphaned videos past the prune age."

    def handle(self, *args, **options):
        result = search_cache.prune()
        self.stdout.write(
            self.style.SUCCESS(
                f"Pruned {result['queries']} searches, {result['videos']} videos."
            )
        )
