from django.contrib.auth.models import AnonymousUser
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import UntypedToken
from jwt import ExpiredSignatureError, InvalidTokenError
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
        # Получение токена из куки
        token = self._get_token_from_cookie(scope)

        # Если токен не найден в куки, fallback на query string (для отладки)
        if not token:
            token = self._get_token_from_query(scope)

        try:
            if token:
                scope["user"] = await self._authenticate_user(token)
            else:
                scope["user"] = AnonymousUser()
        except Exception as e:
            print(f"Ошибка аутентификации: {e}")
            scope["user"] = AnonymousUser()

        return await super().__call__(scope, receive, send)

    def _get_token_from_cookie(self, scope):
        """
        Получает токен из куки HTTP-запроса.
        """
        try:
            cookies = scope.get("headers", [])
            cookies_dict = {}

            # Парсинг заголовков для получения куки
            for header, value in cookies:
                if header == b"cookie":
                    cookie_str = value.decode()
                    for pair in cookie_str.split("; "):
                        key, val = pair.split("=", 1)
                        cookies_dict[key] = val

            # Получение токена из куки
            return cookies_dict.get("access_token")  # Имя куки с токеном
        except Exception as e:
            print(f"Ошибка извлечения токена из куки: {e}")
            return None

    def _get_token_from_query(self, scope):
        """
        Получает токен из query string (как fallback).
        """
        try:
            query_string = scope.get("query_string", b"").decode()
            if not query_string:
                return None
            query_params = dict(x.split("=") for x in query_string.split("&"))
            return query_params.get("token")
        except Exception as e:
            print(f"Ошибка извлечения токена из query string: {e}")
            return None

    @database_sync_to_async
    def _authenticate_user(self, token):
        """
        Аутентифицирует пользователя по JWT-токену.
        """
        try:
            # Проверка валидности токена
            decoded_data = UntypedToken(token)
            user_id = decoded_data.payload.get("user_id")

            if not user_id:
                raise AuthenticationFailed("Пользователь отсутствует в токене")

            # Получение пользователя из БД
            return User.objects.get(id=user_id)

        except ExpiredSignatureError:
            print("Ошибка: Токен истёк.")
            raise AuthenticationFailed("Токен истёк")
        except InvalidTokenError:
            print("Ошибка: Недействительный токен.")
            raise AuthenticationFailed("Недействительный токен")
        except User.DoesNotExist:
            print("Ошибка: Пользователь не найден.")
            raise AuthenticationFailed("Пользователь не найден")
        except Exception as e:
            print(f"Ошибка при аутентификации: {e}")
            raise AuthenticationFailed("Ошибка аутентификации")
