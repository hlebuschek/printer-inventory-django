# printer_inventory/auth_backends.py
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from django.contrib.auth.models import User, Group
from django.conf import settings
from django.core.exceptions import PermissionDenied
import logging
import json
from datetime import datetime
from pathlib import Path

# Основной логгер
logger = logging.getLogger(__name__)

# Создаем отдельный детальный логгер для Keycloak
keycloak_logger = logging.getLogger('keycloak_auth')
keycloak_logger.setLevel(logging.DEBUG)

# Создаем handler для записи в отдельный файл
log_dir = Path(settings.BASE_DIR) / 'logs'
log_dir.mkdir(exist_ok=True)

handler = logging.FileHandler(log_dir / 'keycloak_auth.log')
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
keycloak_logger.addHandler(handler)


class CustomOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """
    Кастомный OIDC backend для интеграции с Keycloak.
    - Проверяет whitelist разрешенных пользователей
    - Логирует все данные от Keycloak для отладки
    """

    def verify_claims(self, claims):
        """Проверка claims и whitelist"""
        # Логируем все claims для анализа
        self.log_all_claims(claims, "VERIFY CLAIMS")

        # Сначала базовая проверка
        if not super().verify_claims(claims):
            keycloak_logger.warning("Base verify_claims failed")
            return False

        # Получаем username
        username = self.get_username(claims)
        if not username:
            keycloak_logger.warning("Could not extract username from Keycloak claims")
            return False

        # КРИТИЧНО: Проверяем whitelist
        from access.models import AllowedUser

        try:
            allowed = AllowedUser.objects.get(
                username__iexact=username,
                is_active=True
            )
            keycloak_logger.info(f"✓ User '{username}' found in whitelist and is active")
            logger.info(f"User '{username}' authorized via whitelist")
            return True
        except AllowedUser.DoesNotExist:
            keycloak_logger.warning(
                f"✗ Access denied for '{username}': not in whitelist or inactive"
            )
            logger.warning(f"Access denied for '{username}': not in whitelist")
            return False

    def create_user(self, claims):
        """Создание нового пользователя из claims Keycloak"""
        username = self.get_username(claims)

        # Детальное логирование для нового пользователя
        self.log_all_claims(claims, f"NEW USER CREATION: {username}")

        # Дополнительная проверка whitelist (на всякий случай)
        from access.models import AllowedUser
        try:
            allowed = AllowedUser.objects.get(
                username__iexact=username,
                is_active=True
            )
            keycloak_logger.info(f"✓ Whitelist check passed for new user '{username}'")
        except AllowedUser.DoesNotExist:
            keycloak_logger.error(f"✗ Attempted to create user '{username}' not in whitelist")
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

        keycloak_logger.info(f"✓ User created successfully: {user.username} ({user.email})")
        logger.info(f"Created new user from Keycloak: {user.username} ({user.email})")
        return user

    def update_user(self, user, claims):
        """Обновление существующего пользователя"""
        # Детальное логирование при каждом входе
        self.log_all_claims(claims, f"USER LOGIN/UPDATE: {user.username}")

        # Проверяем, что пользователь все еще в whitelist
        from access.models import AllowedUser
        try:
            allowed = AllowedUser.objects.get(
                username__iexact=user.username,
                is_active=True
            )
            keycloak_logger.info(f"✓ Whitelist check passed for '{user.username}'")
        except AllowedUser.DoesNotExist:
            keycloak_logger.warning(
                f"✗ User '{user.username}' no longer in whitelist - access will be denied"
            )
            logger.warning(f"User '{user.username}' no longer in whitelist")

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

        # Назначаем дефолтные группы если их нет
        self.assign_default_groups(user)

        keycloak_logger.info(f"✓ User updated successfully: {user.username}")
        logger.info(f"Updated user from Keycloak: {user.username}")
        return user

    def log_all_claims(self, claims, event_type):
        """Детальное логирование всех данных от Keycloak"""

        keycloak_logger.info("=" * 80)
        keycloak_logger.info(f"{event_type} AT {datetime.now()}")
        keycloak_logger.info("=" * 80)

        # 1. Полный JSON
        try:
            claims_json = json.dumps(claims, indent=2, ensure_ascii=False, sort_keys=True)
            keycloak_logger.info("FULL CLAIMS JSON:")
            keycloak_logger.info(claims_json)
        except Exception as e:
            keycloak_logger.error(f"Error serializing claims: {e}")
            keycloak_logger.info(f"RAW CLAIMS: {claims}")

        # 2. Анализ структуры данных
        keycloak_logger.info("\n" + "=" * 40)
        keycloak_logger.info("DETAILED FIELD ANALYSIS:")
        keycloak_logger.info("=" * 40)

        for key, value in sorted(claims.items()):
            value_type = type(value).__name__

            # Подробный анализ значения
            if value is None:
                keycloak_logger.info(f"  {key} ({value_type}): null")
            elif isinstance(value, bool):
                keycloak_logger.info(f"  {key} ({value_type}): {value}")
            elif isinstance(value, (int, float)):
                keycloak_logger.info(f"  {key} ({value_type}): {value}")
            elif isinstance(value, str):
                keycloak_logger.info(f"  {key} ({value_type}): '{value}'")
            elif isinstance(value, list):
                keycloak_logger.info(f"  {key} ({value_type}): [{len(value)} items]")
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        keycloak_logger.info(f"    [{i}]: {json.dumps(item, ensure_ascii=False)}")
                    else:
                        keycloak_logger.info(f"    [{i}]: {item}")
            elif isinstance(value, dict):
                keycloak_logger.info(f"  {key} ({value_type}): {{dict with {len(value)} keys}}")
                for sub_key, sub_value in value.items():
                    if isinstance(sub_value, (list, dict)):
                        keycloak_logger.info(f"    .{sub_key}: {json.dumps(sub_value, ensure_ascii=False)}")
                    else:
                        keycloak_logger.info(f"    .{sub_key}: {sub_value}")
            else:
                keycloak_logger.info(f"  {key} ({value_type}): {str(value)}")

        # 3. Поиск ролей/групп в разных местах
        keycloak_logger.info("\n" + "=" * 40)
        keycloak_logger.info("SEARCHING FOR ROLES/GROUPS:")
        keycloak_logger.info("=" * 40)

        # Проверяем стандартные места для ролей
        possible_role_locations = [
            'roles',
            'groups',
            'realm_access.roles',
            'resource_access',
            'group',
            'Group',
            'role',
            'authorities',
            'user_roles',
            'assigned_roles',
            'memberOf'
        ]

        for location in possible_role_locations:
            if '.' in location:
                # Вложенный путь (например, realm_access.roles)
                parts = location.split('.')
                current = claims
                for part in parts:
                    if isinstance(current, dict) and part in current:
                        current = current[part]
                    else:
                        current = None
                        break
                if current is not None:
                    keycloak_logger.info(f"  Found at '{location}': {json.dumps(current, ensure_ascii=False)}")
            else:
                # Прямое поле
                if location in claims:
                    value = claims[location]
                    if isinstance(value, (list, dict)):
                        keycloak_logger.info(f"  Found at '{location}': {json.dumps(value, ensure_ascii=False)}")
                    else:
                        keycloak_logger.info(f"  Found at '{location}': {value}")

        # Проверяем resource_access подробнее (роли для каждого клиента)
        if 'resource_access' in claims and isinstance(claims['resource_access'], dict):
            keycloak_logger.info("\n  Detailed resource_access:")
            for client_id, client_data in claims['resource_access'].items():
                if isinstance(client_data, dict) and 'roles' in client_data:
                    keycloak_logger.info(f"    Client '{client_id}' roles: {client_data['roles']}")

        # 4. Проверяем наличие любых полей, содержащих "role" или "group" в названии
        keycloak_logger.info("\n  Fields containing 'role' or 'group' in name:")
        found_any = False
        for key in claims.keys():
            if 'role' in key.lower() or 'group' in key.lower() or 'permission' in key.lower():
                found_any = True
                value = claims[key]
                if isinstance(value, (list, dict)):
                    keycloak_logger.info(f"    {key}: {json.dumps(value, ensure_ascii=False)}")
                else:
                    keycloak_logger.info(f"    {key}: {value}")

        if not found_any:
            keycloak_logger.info("    (none found)")

        keycloak_logger.info("\n" + "=" * 80)
        keycloak_logger.info("END OF KEYCLOAK DATA")
        keycloak_logger.info("=" * 80 + "\n")

    def assign_default_groups(self, user):
        """Назначение дефолтных групп новому пользователю из Keycloak"""
        try:
            default_groups = getattr(settings, 'OIDC_DEFAULT_GROUPS', ['Наблюдатель'])

            for group_name in default_groups:
                try:
                    group = Group.objects.get(name=group_name)
                    user.groups.add(group)
                    keycloak_logger.info(f"✓ Assigned DEFAULT group '{group_name}' to NEW user {user.username}")
                    logger.info(f"Assigned group '{group_name}' to user {user.username}")
                except Group.DoesNotExist:
                    keycloak_logger.warning(f"✗ Default group '{group_name}' does not exist")
                    logger.warning(f"Default group '{group_name}' does not exist")

        except Exception as e:
            keycloak_logger.error(f"✗ Error assigning default groups to {user.username}: {e}")
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
                keycloak_logger.debug(f"Using '{field}' as username source: {username}")
                return username[:150]  # Django username limit

        keycloak_logger.warning("Could not extract username from any field")
        return None