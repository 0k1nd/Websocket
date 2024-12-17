from http.client import HTTPResponse
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework.decorators import action
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.views import LoginView
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from .forms import LoginForm
from django.http import JsonResponse
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import make_password
from functools import wraps
from . import models
from . import serializers
def test(request):
    return render(request, "chat/test.html")

@login_required
def index(request):
    if request.method == "POST":
        name = request.POST.get("name", None)
        if name:
            room = models.Room.objects.create(name=name, host=request.user)
            return HttpResponseRedirect(reverse("room", kwargs={"pk": room.pk}))
        return render(request, 'chat/index.html', {"error": "Имя комнаты обязательно!"})
    return render(request, 'chat/index.html')


def custom_authentication_action(detail=False, methods=None, url_path=None):
    def decorator(func):
        @action(detail=detail, methods=methods, url_path=url_path, permission_classes=[])
        @wraps(func)  # Сохраняем имя и метаданные оригинальной функции
        def wrapped_action(self, request, *args, **kwargs):
            email = request.data.get('email')
            password = request.data.get('password')

            if not email or not password:
                return Response({'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)

            user = authenticate(email=email, password=password)
            if user is not None:
                login(request, user)
                refresh = RefreshToken.for_user(user)
                response = Response({'message': 'Login successful'}, status=status.HTTP_200_OK)
                response.set_cookie(
                    key='access_token',
                    value=str(refresh.access_token),
                    httponly=True,  # Куки недоступны через JavaScript
                    secure=False,  # Только для HTTPS
                    samesite='Lax'  # Защита от CSRF
                )
                response.set_cookie(
                    key='refresh_token',
                    value=str(refresh),
                    httponly=True,
                    secure=False,
                    samesite='Lax'
                )
                return Response({
                    'access_token': str(refresh.access_token),
                    'refresh_token': str(refresh),
                    'user': serializers.UserSerializer(request.user).data,
                }, status=status.HTTP_200_OK)

            else:
                return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        return wrapped_action
    return decorator

class RoomViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated | IsAdminUser]
    queryset = models.Room.objects.all()
    serializer_class = serializers.RoomSerializers
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['name', 'id', 'current_users']
    search_fields = ['name', 'host', 'current_users']
    ordering_fields = ['id']

    @action(detail=False, methods=['POST'], url_path="create")
    def index(self, request):
        name = request.POST.get("name", None)
        if name:
            room = models.Room.objects.create(name=name, host=request.user)
            serializered_data = serializers.RoomSerializers(room)
            return Response({
                'status': 'success',
                'message': 'Room created successfully.',
                "data": serializered_data,
                "url": f"/api/rooms/{room.pk}/one"
            },status=status.HTTP_201_CREATED)
        return Response({
            'status': 'failing',
            'message': 'Name is required.',
        }, status=status.HTTP_400_BAD_REQUEST)


    @action(detail=True, url_path='one')
    def one(self, request, pk):
        room = get_object_or_404(models.Room, pk=pk)
        return render(request, 'chat/room.html',{"room": room, "ws_url": f"ws://{request.get_host()}/ws/chat/{room.pk}/"})

class RegisterView(viewsets.ModelViewSet ):
    queryset = []
    serializer_class = serializers.UserSerializer

    @action(detail=False, methods=['POST'], url_path='create')
    def create_user(self, request):
        # Обработка JSON и форм
        username = request.data.get("username")
        password = request.data.get("password")
        email = request.data.get("email")

        # Отладка
        print("Request Content-Type:", request.content_type)
        print("Request Data:", request.data)

        if not username or not password:
            return Response({"error": "Имя пользователя и пароль обязательны"}, status=status.HTTP_400_BAD_REQUEST)

        if models.User.objects.filter(username=username).exists():
            return Response({"error": "Пользователь с таким именем уже существует"}, status=status.HTTP_400_BAD_REQUEST)

        user = models.User.objects.create_user(username=username, email=email, password=password)
        refresh = RefreshToken.for_user(user)

        return Response({
            "status": "success",
            "message": "Registrations successfully",
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        }, status=status.HTTP_201_CREATED)

    @custom_authentication_action(detail=False, methods=['POST'], url_path='login')
    def login_view(self, request, *args, **kwargs):
        pass


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'  # Путь к вашему шаблону

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            refresh = RefreshToken.for_user(self.request.user)
            context['access_token'] = str(refresh.access_token)
            context['refresh_token'] = str(refresh)
        return context

class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response({'error': 'Refresh token not found'}, status=status.HTTP_401_UNAUTHORIZED)

        # Добавляем refresh_token в тело запроса
        request.data['refresh'] = refresh_token
        response = super().post(request, *args, **kwargs)

        # Устанавливаем новые токены в куки
        if response.status_code == 200:
            access_token = response.data['access']
            response.set_cookie(
                key='access_token',
                value=access_token,
                httponly=True,
                secure=False,
                samesite='Lax'
            )

        return response