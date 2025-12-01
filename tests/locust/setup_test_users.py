#!/usr/bin/env python
"""
Скрипт для создания тестовых пользователей для Locust тестирования.

Использование:
    python tests/locust/setup_test_users.py

Или через manage.py:
    python manage.py shell < tests/locust/setup_test_users.py
"""

import os
import sys
import django

# Настройка Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'printer_inventory.settings')
django.setup()

from django.contrib.auth.models import User
from access.models import AllowedUser


def create_django_test_user():
    """Создает тестового пользователя для Django авторизации"""
    username = 'locust_test'
    password = 'locust_password_123'
    email = 'locust_test@example.com'

    print(f"\n{'=' * 60}")
    print("СОЗДАНИЕ ТЕСТОВОГО ПОЛЬЗОВАТЕЛЯ ДЛЯ DJANGO")
    print(f"{'=' * 60}\n")

    # Проверяем, существует ли пользователь
    if User.objects.filter(username=username).exists():
        print(f"✓ Пользователь '{username}' уже существует")
        user = User.objects.get(username=username)
    else:
        # Создаем пользователя
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name='Locust',
            last_name='Test'
        )
        print(f"✓ Создан пользователь: {username}")

    # Добавляем в whitelist
    if AllowedUser.objects.filter(username=username).exists():
        print(f"✓ Пользователь '{username}' уже в whitelist")
        allowed_user = AllowedUser.objects.get(username=username)
        if not allowed_user.is_active:
            allowed_user.is_active = True
            allowed_user.save()
            print(f"✓ Активирован пользователь в whitelist")
    else:
        allowed_user = AllowedUser.objects.create(
            username=username,
            email=email,
            full_name='Locust Test User',
            is_active=True,
            added_by='setup_script',
            notes='Тестовый пользователь для Locust нагрузочного тестирования'
        )
        print(f"✓ Добавлен в whitelist: {username}")

    print(f"\n{'=' * 60}")
    print("УЧЕТНЫЕ ДАННЫЕ ДЛЯ LOCUST")
    print(f"{'=' * 60}")
    print(f"Username: {username}")
    print(f"Password: {password}")
    print(f"Email:    {email}")
    print(f"\nЭкспортируйте в environment:")
    print(f"export LOCUST_DJANGO_USER={username}")
    print(f"export LOCUST_DJANGO_PASSWORD={password}")
    print(f"{'=' * 60}\n")


def create_keycloak_whitelist():
    """Добавляет Keycloak пользователя в whitelist"""
    username = 'user'  # Дефолтный пользователь из Keycloak

    print(f"\n{'=' * 60}")
    print("ДОБАВЛЕНИЕ KEYCLOAK ПОЛЬЗОВАТЕЛЯ В WHITELIST")
    print(f"{'=' * 60}\n")

    if AllowedUser.objects.filter(username=username).exists():
        print(f"✓ Пользователь '{username}' уже в whitelist")
        allowed_user = AllowedUser.objects.get(username=username)
        if not allowed_user.is_active:
            allowed_user.is_active = True
            allowed_user.save()
            print(f"✓ Активирован пользователь в whitelist")
    else:
        allowed_user = AllowedUser.objects.create(
            username=username,
            full_name='Keycloak Test User',
            is_active=True,
            added_by='setup_script',
            notes='Keycloak пользователь для Locust тестирования'
        )
        print(f"✓ Добавлен в whitelist: {username}")

    print(f"\n{'=' * 60}")
    print("УЧЕТНЫЕ ДАННЫЕ KEYCLOAK")
    print(f"{'=' * 60}")
    print(f"Username: {username}")
    print(f"Password: 12345678 (установлено в Keycloak)")
    print(f"\nУбедитесь, что:")
    print(f"1. Keycloak запущен: docker-compose up keycloak")
    print(f"2. Пользователь '{username}' существует в Keycloak realm")
    print(f"\nЭкспортируйте в environment:")
    print(f"export LOCUST_KEYCLOAK_USER={username}")
    print(f"export LOCUST_KEYCLOAK_PASSWORD=12345678")
    print(f"{'=' * 60}\n")


def show_all_test_users():
    """Показывает всех тестовых пользователей"""
    print(f"\n{'=' * 60}")
    print("ВСЕ ТЕСТОВЫЕ ПОЛЬЗОВАТЕЛИ В WHITELIST")
    print(f"{'=' * 60}\n")

    test_users = AllowedUser.objects.filter(
        notes__icontains='locust'
    ) | AllowedUser.objects.filter(
        username__in=['locust_test', 'user']
    )

    if test_users.exists():
        for user in test_users.distinct():
            status = "✓ Активен" if user.is_active else "✗ Отключен"
            print(f"{status} | {user.username:20} | {user.full_name:30} | {user.email}")
    else:
        print("Нет тестовых пользователей")

    print(f"\n{'=' * 60}\n")


def delete_test_users():
    """Удаляет тестовых пользователей (для очистки)"""
    print(f"\n{'=' * 60}")
    print("УДАЛЕНИЕ ТЕСТОВЫХ ПОЛЬЗОВАТЕЛЕЙ")
    print(f"{'=' * 60}\n")

    # Удаляем Django пользователя
    if User.objects.filter(username='locust_test').exists():
        User.objects.filter(username='locust_test').delete()
        print("✓ Удален Django пользователь: locust_test")

    # Удаляем из whitelist
    deleted_count = AllowedUser.objects.filter(
        username__in=['locust_test', 'user'],
        notes__icontains='locust'
    ).delete()[0]

    print(f"✓ Удалено из whitelist: {deleted_count} записей")
    print(f"\n{'=' * 60}\n")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description='Управление тестовыми пользователями для Locust'
    )
    parser.add_argument(
        '--create-all',
        action='store_true',
        help='Создать всех тестовых пользователей'
    )
    parser.add_argument(
        '--django-only',
        action='store_true',
        help='Создать только Django пользователя'
    )
    parser.add_argument(
        '--keycloak-only',
        action='store_true',
        help='Добавить только Keycloak пользователя в whitelist'
    )
    parser.add_argument(
        '--show',
        action='store_true',
        help='Показать всех тестовых пользователей'
    )
    parser.add_argument(
        '--delete',
        action='store_true',
        help='Удалить всех тестовых пользователей'
    )

    args = parser.parse_args()

    if args.delete:
        response = input("Вы уверены, что хотите удалить тестовых пользователей? (yes/no): ")
        if response.lower() == 'yes':
            delete_test_users()
        else:
            print("Отменено")
    elif args.show:
        show_all_test_users()
    elif args.django_only:
        create_django_test_user()
    elif args.keycloak_only:
        create_keycloak_whitelist()
    else:
        # По умолчанию создаем всех
        create_django_test_user()
        create_keycloak_whitelist()
        show_all_test_users()

    print("\n✓ Готово! Теперь вы можете запустить Locust тесты:")
    print("  ./run_locust.sh web")
    print("  ./run_locust.sh quick")
    print()
