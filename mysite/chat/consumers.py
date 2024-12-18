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

        try:
            user = self.scope["user"]
            room = models.Room.objects.get(pk=pk)
            if not user.current_rooms.filter(pk=room.pk).exists():
                user.current_rooms.add(room)
            return room
        except models.Room.DoesNotExist:
            raise ValueError(f"Комната с ID {pk} не найдена")

    async def remove_user_from_room(self, pk):
        try:
            user = self.scope["user"]
            room = await models.Room.objects.aget(pk=pk)
            is_in_room = await sync_to_async(user.current_rooms.filter(pk=room.pk).exists)()

            if is_in_room:
                await sync_to_async(user.current_rooms.remove)(room)
        except models.Room.DoesNotExist:
            raise ValueError(f"Комната с ID {pk} не найдена")

    @database_sync_to_async
    def get_room(self, pk):  #получения праймари ключа
        try:
            room = models.Room.objects.get(pk=pk)
            logger.info(f"Комната найдена: {room}")
            return room
        except models.Room.DoesNotExist:
            raise ValueError(f"Комната с ID {pk} не найдена")

    @database_sync_to_async
    def current_users(self, room):  #все пользователи в комнате
        return [
            serializers.UserSerializer(user).data
            for user in room.current_users.all()
        ]

    async def create_object_async(self, room, user, text):
        obj = await models.Message.objects.acreate(    #ассинхронное создание объекта
            room=room,
            user=user,
            text=text,
        )
        logger.info(f"Сообщение создано: {obj}")
        return obj

    async def serialize_message(self, message_instance):
        return await sync_to_async(lambda: serializers.MessageSerializer(message_instance).data)() #ассинхронная сериализация

    async def disconnect(self, code):
        if hasattr(self, "room_subscribe"):
            await self.channel_layer.group_discard(
                f"room_{self.room_subscribe}",
                self.channel_name
            )
            await self.remove_user_from_room(self.room_subscribe)
            await self.notify_users()
        await super().disconnect(code)

    async def get_message_history(self, pk):
        try:
            # Проверяем наличие комнаты
            room = await database_sync_to_async(models.Room.objects.get)(pk=pk)

            # Извлекаем сообщения из базы данных
            messages = await database_sync_to_async(
                lambda: list(
                    models.Message.objects.filter(room=room).select_related('room').order_by('create_at')
                )
            )()

            logger.info(f"История сообщений для комнаты {pk}: {len(messages)} сообщений найдено.")

            for message in messages:
                serialized_data = await sync_to_async(
                    lambda: serializers.MessageSerializer(message).data
                )()

                await self.channel_layer.group_send(
                    f"room_{self.room_subscribe}",
                    {
                        "type": "chat.message",
                        "data": serialized_data
                    }
                )
        except models.Room.DoesNotExist:
            logger.error(f"Комната с ID {pk} не найдена.")
            await self.send_json({"error": f"Комната с ID {pk} не найдена."})
        except Exception as e:
            logger.error(f"Ошибка в get_message_history: {e}", exc_info=True)
            await self.send_json({"error": f"Произошла ошибка: {str(e)}"})

    @action()
    async def join_room(self, pk, **kwargs):
        try:
            self.room_subscribe = pk
            await self.add_user_to_room(pk)
            await self.channel_layer.group_add(  # Подписка на группу
                f"room_{pk}",
                self.channel_name
            )
            await self.notify_users()
            await self.get_message_history(pk)
            await self.send_json({"success": f"Вы присоединились к комнате {pk}"})
        except ValueError as e:
            await self.send_json({"error": str(e)})

    async def update_users(self, event):
        logger.info("Обновление пользователей: %s", event)
        usuarios = event.get("usuarios", [])
        await self.send_json({
            "action": "update_users",
            "usuarios": usuarios
        })

    async def notify_users(self):
        if hasattr(self, "room_subscribe"):
            room = await self.get_room(self.room_subscribe)
            usuarios = await self.current_users(room)
            logger.info("Уведомление пользователей: %s", usuarios)
            await self.channel_layer.group_send(
                f"room_{self.room_subscribe}",
                {
                    "type": "update_users",  
                    "usuarios": await self.current_users(room)
                }
            )

    @action()
    async def leave_room(self, pk, **kwargs):
        try:
            await self.remove_user_from_room(pk)
            await self.notify_users()
        except ValueError as e:
            await self.send_json({"error": str(e)})


    async def chat_message(self, event):

        logger.info("chat_message вызван: %s", event["data"])
        data = event["data"]
        await self.send_json({
            "action": "create",
            "data": data
        })

    @action()
    async def create_message(self, message, **kwargs):
        try:
            logger.debug("Начало create_message: %s", message)

            if not hasattr(self, "room_subscribe"):
                raise ValueError("Пользователь не присоединился к комнате.")

            room = await self.get_room(pk=self.room_subscribe)
            logger.info("Комната найдена: %s", room)

            new_message = await self.create_object_async(
                room=room,
                user=self.scope['user'],
                text=message
            )

            serialized_data = await self.serialize_message(new_message)

            await self.channel_layer.group_send(
                f"room_{self.room_subscribe}",
                {
                    "type": "chat.message",
                    "data": serialized_data
                }
            )
        except ValueError as e:
            logger.error("Ошибка: %s", e, exc_info=True)
            await self.send_json({"error": f"Ошибка при создании сообщения: {str(e)}"})
        except Exception as e:
            logger.error("Ошибка в create_message: %s", e, exc_info=True)
            await self.send_json({"error": f"Ошибка при создании сообщения: {str(e)}"})

    @action()
    async def subscribe_to_messages_in_room(self, pk, **kwargs):
        await self.message_activity.subscribe(room=pk)

    @model_observer(models.Message)
    async def message_activity(self, instance: models.Message, action, **kwargs):
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


