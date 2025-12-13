"""
Template tags for Vite asset integration.
Automatically resolves hashed filenames from Vite's manifest.json
"""
import json
import os
from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()

# Cache the manifest in memory
_manifest_cache = None


def load_manifest():
    """Load Vite manifest.json file"""
    global _manifest_cache

    if _manifest_cache is not None and not settings.DEBUG:
        return _manifest_cache

    manifest_path = os.path.join(settings.BASE_DIR, 'static', 'dist', '.vite', 'manifest.json')

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            _manifest_cache = json.load(f)
            return _manifest_cache
    except FileNotFoundError:
        # Manifest not found - probably in dev mode or assets not built
        return {}
    except json.JSONDecodeError:
        # Invalid JSON
        return {}


@register.simple_tag
def vite_asset(asset_path):
    """
    Returns the URL to a Vite-built asset with hash.

    Usage in templates:
        {% load vite_tags %}
        <script type="module" src="{% vite_asset 'frontend/src/main.js' %}"></script>

    The asset_path should be relative to the frontend directory (as it appears in manifest.json)
    """
    manifest = load_manifest()

    if not manifest:
        # Fallback: return static path as-is if manifest not found
        # This is useful during development
        return static(f'dist/{asset_path}')

    # Look up the asset in the manifest
    entry = manifest.get(asset_path)

    if not entry:
        # Asset not found in manifest, return as-is
        return static(f'dist/{asset_path}')

    # Return the hashed file path
    file_path = entry.get('file')
    if file_path:
        return static(f'dist/{file_path}')

    # Fallback
    return static(f'dist/{asset_path}')


@register.simple_tag
def vite_css(asset_path):
    """
    Returns the URL to CSS files associated with a Vite entry point.

    Usage:
        {% vite_css 'frontend/src/main.js' %}

    Returns the CSS file URL if the entry point has associated CSS.
    """
    manifest = load_manifest()

    if not manifest:
        return ''

    entry = manifest.get(asset_path)

    if not entry:
        return ''

    # Get the CSS files from the entry
    css_files = entry.get('css', [])

    if css_files:
        # Return the first CSS file (usually there's only one per entry)
        return static(f'dist/{css_files[0]}')

    return ''
