from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.contrib.auth.models import User, Group
from django.conf import settings
from django.core.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)


class CustomOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """
    Кастомный OIDC backend для интеграции с Keycloak.
    Проверяет whitelist разрешенных пользователей.
    """

    def verify_claims(self, claims):
        """Проверка claims и whitelist"""
        # Сначала базовая проверка
        if not super().verify_claims(claims):
            return False

        # Получаем username
        username = self.get_username(claims)
        if not username:
            logger.warning("Could not extract username from Keycloak claims")
            return False

        # КРИТИЧНО: Проверяем whitelist
        from access.models import AllowedUser

        try:
            allowed = AllowedUser.objects.get(
                username__iexact=username,
                is_active=True
            )
            logger.info(f"User '{username}' found in whitelist and is active")
            return True
        except AllowedUser.DoesNotExist:
            logger.warning(
                f"Access denied for '{username}': not in whitelist or inactive"
            )
            return False

    def create_user(self, claims):
        """Создание нового пользователя из claims Keycloak"""
        username = self.get_username(claims)

        # Дополнительная проверка whitelist (на всякий случай)
        from access.models import AllowedUser
        try:
            allowed = AllowedUser.objects.get(
                username__iexact=username,
                is_active=True
            )
        except AllowedUser.DoesNotExist:
            logger.error(f"Attempted to create user '{username}' not in whitelist")
            raise PermissionDenied(
                f"Пользователь '{username}' не найден в списке разрешенных"
            )

        # Создаем пользователя
        user = super().create_user(claims)

        # Заполняем дополнительные поля
        user.first_name = claims.get('given_name', '')
        user.last_name = claims.get('family_name', '')
        user.email = claims.get('email', '')
        user.save()

        # Назначаем дефолтные группы
        self.assign_default_groups(user)

        logger.info(
            f"Created new user from Keycloak: {user.username} ({user.email})"
        )
        return user

    def update_user(self, user, claims):
        """Обновление существующего пользователя"""
        # Проверяем, что пользователь все еще в whitelist
        from access.models import AllowedUser
        try:
            allowed = AllowedUser.objects.get(
                username__iexact=user.username,
                is_active=True
            )
        except AllowedUser.DoesNotExist:
            logger.warning(
                f"User '{user.username}' no longer in whitelist - access will be denied"
            )
            # Деактивируем пользователя
            user.is_active = False
            user.save()
            raise PermissionDenied(
                f"Доступ для пользователя '{user.username}' был отозван"
            )

        # Обновляем данные пользователя
        user.first_name = claims.get('given_name', '')
        user.last_name = claims.get('family_name', '')
        user.email = claims.get('email', '')
        user.is_active = True  # Восстанавливаем, если был деактивирован
        user.save()

        logger.info(f"Updated user from Keycloak: {user.username}")
        return user

    def assign_default_groups(self, user):
        """Назначение дефолтных групп новому пользователю из Keycloak"""
        try:
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
        username_fields = ['preferred_username', 'sub', 'email', 'name']

        for field in username_fields:
            username = claims.get(field)
            if username:
                # Очищаем username от недопустимых символов
                username = username.lower().replace('@', '_').replace('.', '_')
                return username[:150]  # Django username limit

        return None