from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/users/', consumers.UserConsumer.as_asgi(), name='user_ws'),
    path('ws/chat/', consumers.RoomConsumer.as_asgi(), name='chat_ws'),
]
