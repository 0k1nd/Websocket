from django.contrib.auth.models import AnonymousUser
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from rest_framework.exceptions import AuthenticationFailed
from jwt import decode as jwt_decode, ExpiredSignatureError, InvalidTokenError
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()


class JwtAuthMiddleware(BaseMiddleware):
    """
    Middleware для обработки JWT-токенов в WebSocket соединениях.
    """

    async def __call__(self, scope, receive, send):
        """
        Главная точка входа в middleware.
        """
        query_string = scope.get("query_string", b"").decode()
        token = self._get_token_from_query(query_string)

        if token:
            scope["user"] = await self._authenticate_user(token)
        else:
            scope["user"] = AnonymousUser()  # Анонимный пользователь при отсутствии токена

        return await super().__call__(scope, receive, send)

    def _get_token_from_query(self, query_string):
        """
        Извлекает токен из строки запроса.
        """
        try:
            query_params = dict(x.split("=") for x in query_string.split("&"))
            return query_params.get("token")
        except Exception:
            return None

    @database_sync_to_async
    def _authenticate_user(self, token):
        """
        Аутентифицирует пользователя по токену.
        """
        try:
            # Расшифровка токена
            decoded_data = jwt_decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = decoded_data.get("user_id")

            if not user_id:
                raise AuthenticationFailed("Пользователь отсутствует в токене")

            # Получение пользователя из базы данных
            return User.objects.get(id=user_id)

        except ExpiredSignatureError:
            raise AuthenticationFailed("Токен истёк")
        except InvalidTokenError:
            raise AuthenticationFailed("Недействительный токен")
        except User.DoesNotExist:
            raise AuthenticationFailed("Пользователь не найден")

