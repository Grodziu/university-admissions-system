import hashlib
import secrets
from datetime import timedelta
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from .models import Session


def issue_session(user):
    raw = secrets.token_urlsafe(40)
    Session.objects.filter(user=user, expires_at__lt=timezone.now()).delete()
    Session.objects.create(user=user, key_hash=hashlib.sha256(raw.encode()).hexdigest(),
                           expires_at=timezone.now() + timedelta(hours=4))
    return raw


class SessionAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth = request.headers.get('Authorization', '')
        if not auth:
            return None
        if not auth.startswith('Bearer ') or len(auth) > 200:
            raise AuthenticationFailed('Niepoprawna sesja.')
        digest = hashlib.sha256(auth[7:].encode()).hexdigest()
        session = Session.objects.select_related('user').filter(key_hash=digest, expires_at__gt=timezone.now(), user__is_active=True).first()
        if not session:
            raise AuthenticationFailed('Sesja wygasła. Zaloguj się ponownie.')
        return session.user, session

    def authenticate_header(self, request):
        return 'Bearer'
