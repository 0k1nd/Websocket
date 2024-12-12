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
    Middleware для обработки JWT токенов в WebSocket соединениях.
    """

    async def __call__(self, scope, receive, send):
        """
        Проверяет JWT токен из query_string или заголовка WebSocket.
        """
        try:
            # Получение query_string и парсинг токена
            query_string = scope.get("query_string", b"").decode()
            token_key = dict(
                x.split("=") for x in query_string.split("&")
            ).get("token", None)

            if token_key is None:
                raise ValueError("JWT токен отсутствует")

            # Проверка и получение пользователя
            scope["user"] = await self.get_user(token_key)
            print("Авторизованный пользователь:", scope["user"])
        except Exception as e:
            print("Ошибка авторизации:", e)
            scope["user"] = AnonymousUser()  # Если ошибка, пользователь анонимный

        return await super().__call__(scope, receive, send)

    @database_sync_to_async
    def get_user(self, token_key):
        """
        Декодирует токен и возвращает пользователя.
        """
        try:
            # Расшифровка токена
            decoded_data = jwt_decode(token_key, settings.SECRET_KEY, algorithms=["HS256"])
            user_id = decoded_data.get("user_id")

            if not user_id:
                raise AuthenticationFailed("Пользователь отсутствует в токене")

            # Получение пользователя из базы данных
            user = User.objects.get(id=user_id)
            return user
        except ExpiredSignatureError:
            raise AuthenticationFailed("Срок действия токена истёк")
        except InvalidTokenError:
            raise AuthenticationFailed("Неверный токен")
        except User.DoesNotExist:
            raise AuthenticationFailed("Пользователь не найден")

def JwtAuthMiddlewareStack(inner):
    """
    Оборачивает внутренний ASGI consumer middleware для обработки JWT.
    """
    return JwtAuthMiddleware(inner)
