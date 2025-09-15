from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.contrib.auth.models import User, Group
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class CustomOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """
    Кастомный OIDC backend для интеграции с Keycloak.
    Автоматически создаёт пользователей и назначает им дефолтные группы.
    """

    def create_user(self, claims):
        """Создание нового пользователя из claims Keycloak"""
        user = super().create_user(claims)

        # Заполняем дополнительные поля
        user.first_name = claims.get('given_name', '')
        user.last_name = claims.get('family_name', '')
        user.email = claims.get('email', '')

        # Помечаем пользователя как созданного через Keycloak
        user.save()

        # Назначаем дефолтные группы
        self.assign_default_groups(user)

        logger.info(f"Created new user from Keycloak: {user.username} ({user.email})")
        return user

    def update_user(self, user, claims):
        """Обновление существующего пользователя"""
        user.first_name = claims.get('given_name', '')
        user.last_name = claims.get('family_name', '')
        user.email = claims.get('email', '')
        user.save()

        logger.info(f"Updated user from Keycloak: {user.username}")
        return user

    def assign_default_groups(self, user):
        """Назначение дефолтных групп новому пользователю из Keycloak"""
        try:
            # Получаем группы для назначения по умолчанию
            default_groups = getattr(settings, 'OIDC_DEFAULT_GROUPS', ['Наблюдатель'])

            for group_name in default_groups:
                try:
                    group = Group.objects.get(name=group_name)
                    user.groups.add(group)
                    logger.info(f"Assigned group '{group_name}' to user {user.username}")
                except Group.DoesNotExist:
                    logger.warning(f"Default group '{group_name}' does not exist")

        except Exception as e:
            logger.error(f"Error assigning default groups to {user.username}: {e}")

    def filter_users_by_claims(self, claims):
        """Поиск пользователя по claims"""
        username = self.get_username(claims)
        if not username:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(username__iexact=username)

    def get_username(self, claims):
        """Извлечение username из claims"""
        # Попробуем несколько полей для получения username
        username_fields = ['preferred_username', 'sub', 'email', 'name']

        for field in username_fields:
            username = claims.get(field)
            if username:
                # Очищаем username от недопустимых символов
                username = username.lower().replace('@', '_').replace('.', '_')
                return username[:150]  # Django username limit

        return None

    def verify_claims(self, claims):
        """Дополнительная проверка claims"""
        # Проверяем, что есть необходимые поля
        if not claims.get('sub'):
            logger.warning("Missing 'sub' claim in Keycloak response")
            return False

        if not self.get_username(claims):
            logger.warning("Could not extract username from Keycloak claims")
            return False

        return super().verify_claims(claims)