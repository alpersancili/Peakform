from django.shortcuts import render

from community.models import Post


def landing(request):
    recent_posts = Post.objects.filter(is_removed=False).select_related("author")[:3]
    return render(request, "core/landing.html", {"recent_posts": recent_posts})


def privacy(request):
    return render(request, "core/privacy.html")


def terms(request):
    return render(request, "core/terms.html")
