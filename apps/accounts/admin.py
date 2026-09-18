from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User

# Пока модель не отличается от встроенной, поэтому переиспользуем стандартный UserAdmin.
# Когда в User появятся свои поля, здесь добавятся fieldsets.
admin.site.register(User, UserAdmin)
