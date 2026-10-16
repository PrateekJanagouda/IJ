from celery import shared_task

from . import services


@shared_task(name="apps.outbox.tasks.dispatch_outbox")
def dispatch_outbox():
    return services.process_pending()
