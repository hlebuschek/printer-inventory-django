"""
Template tags for loading Vite-generated assets with proper hashed filenames.
"""
import json
import os
from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def vite_asset(entry_point):
    """
    Returns the hashed filename for a Vite entry point by reading the manifest.

    Usage:
        {% vite_asset 'frontend/src/main.js' %}

    Returns:
        The path to the hashed JS file (e.g., 'dist/js/main.Z0oy_p-e.js')
    """
    manifest_path = os.path.join(settings.STATIC_ROOT or settings.BASE_DIR, 'static', 'dist', '.vite', 'manifest.json')

    # Fallback for development
    if not os.path.exists(manifest_path):
        manifest_path = os.path.join(settings.BASE_DIR, 'static', 'dist', '.vite', 'manifest.json')

    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        if entry_point in manifest:
            file_path = manifest[entry_point]['file']
            return static(f'dist/{file_path}')
        else:
            # Fallback to unhashed name
            return static('dist/js/main.js')
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # Fallback if manifest not found
        return static('dist/js/main.js')


@register.simple_tag
def vite_css(entry_point):
    """
    Returns the hashed CSS filename for a Vite entry point by reading the manifest.

    Usage:
        {% vite_css 'frontend/src/main.js' %}

    Returns:
        The path to the hashed CSS file (e.g., 'dist/css/main.BY_F1g0D.css')
    """
    manifest_path = os.path.join(settings.STATIC_ROOT or settings.BASE_DIR, 'static', 'dist', '.vite', 'manifest.json')

    # Fallback for development
    if not os.path.exists(manifest_path):
        manifest_path = os.path.join(settings.BASE_DIR, 'static', 'dist', '.vite', 'manifest.json')

    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)

        if entry_point in manifest and 'css' in manifest[entry_point]:
            css_files = manifest[entry_point]['css']
            if css_files:
                return static(f'dist/{css_files[0]}')

        # Fallback to unhashed name
        return static('dist/css/main.css')
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        # Fallback if manifest not found
        return static('dist/css/main.css')
