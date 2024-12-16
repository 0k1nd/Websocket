from http.client import HTTPResponse
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth.views import LoginView
from django.http import JsonResponse
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import make_password
from . import models
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

def room(request, pk):
    room = get_object_or_404(models.Room, pk=pk)
    return render(request, 'chat/room.html', {"room": room, "ws_url": f"ws://{request.get_host()}/ws/chat/{room.pk}/"})

class RegisterView(APIView):
    def post(self, request):
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
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        }, status=status.HTTP_201_CREATED)


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'  # Путь к вашему шаблону

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.user.is_authenticated:
            # Генерация токенов для текущего пользователя
            refresh = RefreshToken.for_user(self.request.user)
            context['access_token'] = str(refresh.access_token)
            context['refresh_token'] = str(refresh)
        return context