import os

from django import template
from django.conf import settings
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def versioned_static(path):
    """Like {% static %}, but appends the file's mtime as a cache-busting
    query string in development, where static files aren't content-hashed.
    In production, ManifestStaticFilesStorage already hashes filenames, so
    no extra versioning is needed there.
    """
    url = static(path)
    if not settings.DEBUG:
        return url

    file_path = settings.BASE_DIR / "static" / path
    try:
        version = int(os.path.getmtime(file_path))
    except OSError:
        return url
    return f"{url}?v={version}"
