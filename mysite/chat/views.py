from http.client import HTTPResponse

from django.http import HttpResponseRedirect
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.admin import User
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken


from . import models
def test(request):
    return render(request, "chat/test.html")

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
    return render(request, 'chat/room.html', {"room": room})

class RegisterView(APIView):
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        if not username or not password:
            return Response({"error": "Имя пользователя и пароль обязательны"}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(username=username).exists():
            return Response({"error": "Пользователь с таким именем уже существует"}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, password=password)

        refresh = RefreshToken.for_user(user)
        return Response({
            "refresh": str(refresh),
            "access": str(refresh.access_token)
        }, status=status.HTTP_201_CREATED)