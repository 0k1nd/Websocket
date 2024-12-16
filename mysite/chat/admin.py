from django.contrib import admin
from django.contrib.admin import ModelAdmin
from . import models

@admin.register(models.User)
class UserAdmin(ModelAdmin):
    list_filter = ["is_staff", "is_active"]

@admin.register(models.Message)
class MessageAdmin(ModelAdmin):
    pass

@admin.register(models.Room)
class RoomAdmin(ModelAdmin):
    pass