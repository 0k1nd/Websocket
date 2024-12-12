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
        user = self.scope["user"]
        room = models.Room.objects.get(pk=pk)
        if not user.current_rooms.filter(pk=room.pk).exists():
            user.current_rooms.add(room)

    @model_observer(models.Message)
    async def message_activity(self, instance: models.Message, action, **kwargs):
        serialized_data = serializers.MessageSerializer(instance).data
        await self.send_json(
            {
                "data": serialized_data,
                "action": action.value,
                "pk": instance.pk,
            }
        )

    @database_sync_to_async
    def remove_user_from_room(self, pk):
        user = self.scope["user"]
        room = models.Room.objects.get(pk=pk)
        user.current_rooms.remove(room)

    @database_sync_to_async
    def get_room(self, pk):
        return models.Room.objects.get(pk=pk)

    @database_sync_to_async
    def current_users(self, room):
        return [
            serializers.UserSerializer(user).data
            for user in room.current_users.all()
        ]

    async def notify_users(self):
        room: models.Room = await self.get_room(self.room_subscride)
        for group in self.groups:
            await self.channel_layer.group_send(
                group,
                {
                    "type": "update_users",
                    "usuarios": await self.current_users(room)
                }
            )

    async def disconnect(self, code):
        if hasattr(self, "room_subscride"):
            await self.remove_user_from_room(self.room_subscride)
            await self.notify_users()
        await super().disconnect(code)

    @action()
    async def join_room(self, pk, **kwargs):
        self.room_subscride = pk
        await self.add_user_to_room(pk)
        await self.notify_users()

    @action()
    async def leave_room(self, pk, **kwargs):
        await self.remove_user_from_room(pk)

    @action()
    async def create_message(self, message, **kwargs):
        room: models.Room = await self.get_room(pk=self.room_subscride)
        await database_sync_to_async(models.Message.objects.create)(
            room=room,
            user=self.scope['user'],
            text=message
        )

    @action()
    async def subscribe_to_messages_in_room(self, pk, **kwargs):
        await self.message_activity.subscribe(room=pk)

    @model_observer(models.Message)
    async def message_activity(self, message, observer=None, **kwargs):
        await self.send_json(message)

    @message_activity.groups_for_signal
    def message_activity(self, instance: models.Message, **kwargs):
        yield f'room__{instance.room_id}'
        yield f'pk__{instance.pk}'

    @message_activity.groups_for_consumer
    def message_activity(self, room=None, **kwargs):
        if room is not None:
            yield f"room__{room}"


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


