from djangochannelsrestframework import mixins
from djangochannelsrestframework.generics import GenericAsyncAPIConsumer
from djangochannelsrestframework.observer.generics import (ObserverModelInstanceMixin, action)
from djangochannelsrestframework.observer import model_observer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from . import models
from . import serializers


class RoomConsumer(ObserverModelInstanceMixin, GenericAsyncAPIConsumer):
    queryset = models.Room.objects.all()
    serializer_class = serializers.RoomSerializers
    lookup_field = "pk"

    @database_sync_to_async
    def add_user_to_room(self, pk):
        """
        Добавляет пользователя в комнату.
        """
        try:
            user = self.scope["user"]
            room = models.Room.objects.get(pk=pk)
            if not user.current_rooms.filter(pk=room.pk).exists():
                user.current_rooms.add(room)
            return room
        except models.Room.DoesNotExist:
            raise ValueError(f"Комната с ID {pk} не найдена")

    @database_sync_to_async
    def remove_user_from_room(self, pk):
        """
        Удаляет пользователя из комнаты.
        """
        try:
            user = self.scope["user"]
            room = models.Room.objects.get(pk=pk)
            if user.current_rooms.filter(pk=room.pk).exists():
                user.current_rooms.remove(room)
        except models.Room.DoesNotExist:
            raise ValueError(f"Комната с ID {pk} не найдена")

    @database_sync_to_async
    def get_room(self, pk):
        """
        Возвращает объект комнаты.
        """
        return models.Room.objects.get(pk=pk)

    @database_sync_to_async
    def current_users(self, room):
        """
        Возвращает текущих пользователей в комнате.
        """
        return [
            serializers.UserSerializer(user).data
            for user in room.current_users.all()
        ]

    async def notify_users(self):
        """
        Уведомляет пользователей в комнате об изменении состава.
        """
        if hasattr(self, "room_subscribe"):
            room: models.Room = await self.get_room(self.room_subscribe)
            await self.channel_layer.group_send(
                f"room_{self.room_subscribe}",
                {
                    "type": "update_users",
                    "usuarios": await self.current_users(room)
                }
            )

    async def disconnect(self, code):
        """
        Действия при отключении.
        """
        if hasattr(self, "room_subscribe"):
            await self.remove_user_from_room(self.room_subscribe)
            await self.notify_users()
        await super().disconnect(code)

    @action()
    async def join_room(self, pk, **kwargs):
        """
        Присоединяет пользователя к комнате.
        """
        try:
            self.room_subscribe = pk
            await self.add_user_to_room(pk)
            await self.notify_users()
        except ValueError as e:
            await self.send_json({"error": str(e)})

    @action()
    async def leave_room(self, pk, **kwargs):
        """
        Удаляет пользователя из комнаты.
        """
        try:
            await self.remove_user_from_room(pk)
            await self.notify_users()
        except ValueError as e:
            await self.send_json({"error": str(e)})

    @action()
    async def create_message(self, message, **kwargs):
        """
        Создаёт сообщение в комнате.
        """
        try:
            room: models.Room = await self.get_room(pk=self.room_subscribe)
            new_message = await database_sync_to_async(models.Message.objects.create)(
                room=room,
                user=self.scope['user'],
                text=message
            )
            serialized_data = serializers.MessageSerializer(new_message).data
            await self.channel_layer.group_send(
                f"room_{self.room_subscribe}",
                {
                    "type": "chat.message",
                    "data": serialized_data
                }
            )
        except models.Room.DoesNotExist:
            await self.send_json({"error": "Комната не найдена"})

    @action()
    async def subscribe_to_messages_in_room(self, pk, **kwargs):
        """
        Подписка на сообщения комнаты.
        """
        await self.message_activity.subscribe(room=pk)

    @model_observer(models.Message)
    async def message_activity(self, instance: models.Message, action, **kwargs):
        """
        Наблюдатель за сообщениями.
        """
        serialized_data = serializers.MessageSerializer(instance).data
        await self.send_json(
            {
                "data": serialized_data,
                "action": action.value,
                "pk": instance.pk,
            }
        )

    @message_activity.groups_for_signal
    def message_activity(self, instance: models.Message, **kwargs):
        yield f"room_{instance.room_id}"

    @message_activity.groups_for_consumer
    def message_activity(self, room=None, **kwargs):
        if room is not None:
            yield f"room_{room}"


class UserConsumer(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.PatchModelMixin,
    mixins.UpdateModelMixin,
    mixins.CreateModelMixin,
    mixins.DeleteModelMixin,
    GenericAsyncAPIConsumer
):
    queryset = models.User.objects.all()
    serializer_class = serializers.UserSerializer


