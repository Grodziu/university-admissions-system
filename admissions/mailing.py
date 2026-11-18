"""Save alerts with their e-mail delivery and process the queue on the server."""
from contextlib import contextmanager
from datetime import timedelta
import logging
from threading import Event, Thread

from django.conf import settings
from django.core.mail import send_mail
from django.db import close_old_connections, connections, transaction
from django.utils import timezone

from .models import CandidateContact, EmailDelivery, Notification

log = logging.getLogger(__name__)
MAX_ATTEMPTS = 5


@transaction.atomic
def record_notifications(notifications):
    rows = Notification.objects.bulk_create(notifications, batch_size=250)
    if settings.PK_MAIL_ENABLED and rows:
        addresses = dict(CandidateContact.objects.filter(user_id__in={n.user_id for n in rows}, user__is_active=True)
                         .exclude(notification_email='').values_list('user_id', 'notification_email'))
        EmailDelivery.objects.bulk_create([
            EmailDelivery(notification=row, recipient=addresses[row.user_id]) for row in rows if row.user_id in addresses
        ], batch_size=250)


@transaction.atomic
def deliver_next():
    delivery = (EmailDelivery.objects.select_for_update(skip_locked=True, of=('self',))
                .select_related('notification')
                .filter(state=EmailDelivery.State.PENDING, available_at__lte=timezone.now())
                .order_by('available_at', 'pk').first())
    if not delivery:
        return False
    notice = delivery.notification
    still_requested = CandidateContact.objects.filter(
        user_id=notice.user_id, user__is_active=True, notification_email=delivery.recipient
    ).exists()
    if not still_requested:
        delivery.state = EmailDelivery.State.CANCELLED
    else:
        delivery.attempts += 1
        try:
            sent = send_mail(
                f'Rekrutacja PK — {notice.title}',
                'Masz nowe powiadomienie. Otwórz zakładkę „Powiadomienia” w aplikacji Rekrutacja PK, aby przeczytać szczegóły.',
                None, [delivery.recipient],
            )
            if not sent:
                raise OSError('SMTP did not accept the message')
        except (OSError, ValueError) as error:
            log.warning('E-mail delivery %s failed (%s).', delivery.pk, type(error).__name__)
            if delivery.attempts >= MAX_ATTEMPTS:
                delivery.state = EmailDelivery.State.FAILED
            else:
                delay = 30 * 2 ** (delivery.attempts - 1)
                delivery.available_at = timezone.now() + timedelta(seconds=delay)
        else:
            delivery.state = EmailDelivery.State.SENT
    delivery.save(update_fields=['attempts', 'state', 'available_at'])
    return True


def dispatch(stop):
    try:
        while not stop.is_set():
            close_old_connections()
            try:
                found = deliver_next()
            except Exception:
                log.exception('E-mail queue unavailable.')
                stop.wait(10)
            else:
                if not found:
                    stop.wait(3)
    finally:
        connections.close_all()


@contextmanager
def email_dispatcher():
    if not settings.PK_MAIL_ENABLED:
        yield
        return
    stop = Event()
    worker = Thread(target=dispatch, args=(stop,), daemon=True, name='pk-mail')
    worker.start()
    try:
        yield
    finally:
        stop.set()
        worker.join(timeout=settings.EMAIL_TIMEOUT + 1)
