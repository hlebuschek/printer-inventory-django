"""
Вспомогательные функции для интеграции Vite с Django
"""
import json
import os
from django.conf import settings
from django.utils.safestring import mark_safe


def get_vite_manifest():
    """Читает Vite manifest.json"""
    manifest_path = os.path.join(settings.BASE_DIR, 'static', 'dist', '.vite', 'manifest.json')

    if not os.path.exists(manifest_path):
        return {}

    with open(manifest_path, 'r') as f:
        return json.load(f)


def vite_asset(entry_name='main.js'):
    """
    Возвращает путь к скомпилированному ассету из Vite manifest

    Usage в шаблоне:
        {% load static %}
        <script type="module" src="{% static vite_asset_path %}"></script>
    """
    manifest = get_vite_manifest()

    # Проверяем в production режиме (есть manifest)
    if manifest:
        entry = manifest.get(entry_name, {})
        return f"dist/{entry.get('file', '')}"

    # Development режим - используем Vite dev server
    return f"http://localhost:5173/frontend/src/{entry_name}"


def render_vite_bundle(entry_name='main.js', attrs=''):
    """
    Рендерит тег <script> для подключения Vite бандла

    Usage:
        {{ render_vite_bundle('main.js')|safe }}
    """
    manifest = get_vite_manifest()

    if manifest:
        # Production - используем скомпилированные файлы
        entry = manifest.get(entry_name, {})
        file_path = entry.get('file', '')
        css_files = entry.get('css', [])

        html = ''

        # Подключаем CSS
        for css in css_files:
            html += f'<link rel="stylesheet" href="/static/dist/{css}">\n'

        # Подключаем JS
        html += f'<script type="module" src="/static/dist/{file_path}" {attrs}></script>\n'

        return mark_safe(html)
    else:
        # Development - используем Vite dev server
        html = f'''
        <script type="module" src="http://localhost:5173/@vite/client"></script>
        <script type="module" src="http://localhost:5173/frontend/src/{entry_name}" {attrs}></script>
        '''
        return mark_safe(html)


# Template tags
from django import template

register = template.Library()


@register.simple_tag
def vite_asset_url(entry_name='main.js'):
    """Template tag для получения URL ассета"""
    return vite_asset(entry_name)


@register.simple_tag
def vite_bundle(entry_name='main.js', attrs=''):
    """Template tag для рендеринга бандла"""
    return render_vite_bundle(entry_name, attrs)
