from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import UntypedToken
from jwt import ExpiredSignatureError, InvalidTokenError
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

class CookieJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        token = request.COOKIES.get('access_token')
        if not token:
            return None

        try:
            decoded_data = UntypedToken(token)
            user_id = decoded_data.payload.get("user_id")

            if not user_id:
                raise AuthenticationFailed("Пользователь отсутствует в токене")

            user = User.objects.get(id=user_id)
            return user, None

        except ExpiredSignatureError:
            raise AuthenticationFailed("Токен истёк")
        except InvalidTokenError:
            raise AuthenticationFailed("Недействительный токен")
        except User.DoesNotExist:
            raise AuthenticationFailed("Пользователь не найден")

        return None
