from django.shortcuts import redirect, render
from django.templatetags.static import static

from community.models import Post


def landing(request):
    recent_posts = Post.objects.filter(is_removed=False).select_related("author")[:3]
    return render(request, "core/landing.html", {"recent_posts": recent_posts})


def privacy(request):
    return render(request, "core/privacy.html")


def terms(request):
    return render(request, "core/terms.html")


def favicon(request):
    # Resolved at request time, not import time: with the production
    # manifest-hashed static storage, calling the `static` tag/function at
    # URLconf module-load time would require collectstatic to have already
    # run, which isn't guaranteed at that point (see the versioned_static
    # tag's own DEBUG-only branch for the same constraint).
    return redirect(static("img/favicon.svg"), permanent=True)
