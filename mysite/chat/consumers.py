from djangochannelsrestframework import mixins
from djangochannelsrestframework.generics import GenericAsyncAPIConsumer
from djangochannelsrestframework.observer.generics import (ObserverModelInstanceMixin, action)
from djangochannelsrestframework.observer import model_observer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from . import models
from . import serializers

import logging

logger = logging.getLogger('chat')


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

    async def remove_user_from_room(self, pk):
        """
        Удаляет пользователя из комнаты.
        """
        try:
            user = self.scope["user"]
            # Получаем комнату асинхронно
            room = await models.Room.objects.aget(pk=pk)

            # Проверяем, состоит ли пользователь в комнате, асинхронно
            is_in_room = await sync_to_async(user.current_rooms.filter(pk=room.pk).exists)()

            if is_in_room:
                # Удаляем пользователя из комнаты, асинхронно
                await sync_to_async(user.current_rooms.remove)(room)
        except models.Room.DoesNotExist:
            raise ValueError(f"Комната с ID {pk} не найдена")

    @database_sync_to_async
    def get_room(self, pk):
        """
        Получение комнаты по pk.
        """
        try:
            room = models.Room.objects.get(pk=pk)
            print(f'комната найдена{room}')
            return room
        except models.Room.DoesNotExist:
            raise ValueError(f"Комната с ID {pk} не найдена")

    @database_sync_to_async
    def current_users(self, room):
        """
        Возвращает текущих пользователей в комнате.
        """
        return [
            serializers.UserSerializer(user).data
            for user in room.current_users.all()
        ]

    async def create_object_async(self, room, user, text):
        obj = await models.Message.objects.acreate(
                room=room,
                user=user,
                text=text,
            )
        print(f"Created object: {obj}")
        return obj

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

    async def serialize_message(self, message_instance):
        return await sync_to_async(lambda: serializers.MessageSerializer(message_instance).data)()

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
        try:
            print("----------------------------")
            logger.debug("Начало create_message: %s", message)
            logger.debug("room_subscribe: %s", self.room_subscribe)

            # Асинхронное получение комнаты
            room = await self.get_room(pk=self.room_subscribe)
            logger.info("Комната найдена: %s", room)

            # Асинхронное создание сообщения
            new_message = await self.create_object_async(
                room=room,
                user=self.scope['user'],
                text=message
            )
            logger.info("Сообщение создано: %s", new_message)

            # Сериализация сообщения
            serialized_data = await self.serialize_message(new_message)
            logger.debug("Сообщение сериализовано: %s", serialized_data)

            # Отправка сообщения в группу
            await self.channel_layer.group_send(
                f"room_{self.room_subscribe}",
                {
                    "type": "chat.message",
                    "data": serialized_data
                }
            )
            logger.info("Сообщение отправлено: %s", serialized_data)
        except Exception as e:
            logger.error("Ошибка в create_message: %s", e, exc_info=True)
            await self.send_json({"error": f"Ошибка при создании сообщения: {str(e)}"})

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
        serialized_data = await self.serialize_message(instance)
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


