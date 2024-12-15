from rest_framework import serializers
from . import models

class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = models.User
        fields = ['id', 'username', 'email', 'password']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = models.User(
            email=validated_data['email'],
            username=validated_data['username']
        )
        user.set_password(validated_data['password'])
        user.save()
        return user


class MessageSerializer(serializers.ModelSerializer):
    create_at_formated = serializers.SerializerMethodField()
    user = UserSerializer()

    class Meta:
        model = models.Message
        exclude = []
        depth = 1

    def get_create_at_formated(self, obj: models.Message):
        return obj.create_at.strftime("%d-%m-%Y %H:%M:%S")


class RoomSerializers(serializers.ModelSerializer):
    last_message = serializers.SerializerMethodField()
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = models.Room
        fields = '__all__'
        depth = 1
        read_only_fields = ["messages", "last_message"]

    def get_last_message(self, obj: models.Room):
        last_message = obj.messages.order_by("create_at").last()
        return MessageSerializer(last_message).data if last_message else None
