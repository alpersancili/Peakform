from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import CommentForm, PostForm, ReportForm
from .models import Comment, Follow, Like, Post, Report

POSTS_PER_PAGE = 10

REPORTABLE_MODELS = {"post": Post, "comment": Comment}


def _visible_posts(viewer):
    posts = Post.objects.filter(is_removed=False).select_related("author")
    if viewer.is_authenticated:
        posts = posts.annotate(
            viewer_has_liked=Exists(Like.objects.filter(post=OuterRef("pk"), user=viewer))
        )
    return posts


def _paginate(request, queryset):
    paginator = Paginator(queryset, POSTS_PER_PAGE)
    return paginator.get_page(request.GET.get("page"))


def feed(request):
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            messages.success(request, "Posted to the community feed.")
            return redirect("community:feed")
    else:
        form = PostForm()

    page = _paginate(request, _visible_posts(request.user))
    return render(request, "community/feed.html", {"form": form, "page": page, "feed_title": "Community feed"})


@login_required
def following_feed(request):
    following_ids = Follow.objects.filter(follower=request.user).values_list("following_id", flat=True)
    posts = _visible_posts(request.user).filter(author_id__in=following_ids)
    page = _paginate(request, posts)
    return render(
        request,
        "community/feed.html",
        {"form": PostForm(), "page": page, "feed_title": "Following", "following_only": True},
    )


def post_detail(request, post_id):
    post = get_object_or_404(Post.objects.select_related("author"), id=post_id)
    if post.is_removed and not (request.user.is_authenticated and (request.user == post.author or request.user.is_staff)):
        messages.error(request, "That post is no longer available.")
        return redirect("community:feed")

    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        form = CommentForm(request.POST)
        if form.is_valid():
            parent_id = request.POST.get("parent_id")
            parent = None
            if parent_id:
                parent = get_object_or_404(Comment, id=parent_id, post=post)
                if parent.parent_id:
                    parent = parent.parent  # flatten replies-to-replies to one level
            comment = form.save(commit=False)
            comment.post = post
            comment.author = request.user
            comment.parent = parent
            comment.save()
            return redirect("community:post_detail", post_id=post.id)
    else:
        form = CommentForm()

    top_level_comments = (
        post.comments.filter(is_removed=False, parent__isnull=True)
        .select_related("author")
        .prefetch_related("replies__author")
    )
    post.viewer_has_liked = request.user.is_authenticated and post.likes.filter(user=request.user).exists()
    return render(
        request,
        "community/post_detail.html",
        {
            "post": post,
            "comments": top_level_comments,
            "comment_form": form,
            "report_form": ReportForm(),
        },
    )


@login_required
def post_edit(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)
    if request.method == "POST":
        form = PostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, "Post updated.")
            return redirect("community:post_detail", post_id=post.id)
    else:
        form = PostForm(instance=post)
    return render(request, "community/post_form.html", {"form": form, "post": post})


@login_required
def post_delete(request, post_id):
    post = get_object_or_404(Post, id=post_id, author=request.user)
    if request.method == "POST":
        post.delete()
        messages.success(request, "Post deleted.")
        return redirect("community:feed")
    return redirect("community:post_detail", post_id=post.id)


@login_required
def post_like_toggle(request, post_id):
    post = get_object_or_404(Post, id=post_id, is_removed=False)
    if request.method == "POST":
        like, created = Like.objects.get_or_create(post=post, user=request.user)
        if not created:
            like.delete()
    next_url = request.POST.get("next") or ""
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        next_url = reverse("community:feed")
    return redirect(next_url)


@login_required
def comment_delete(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, author=request.user)
    post_id = comment.post_id
    if request.method == "POST":
        comment.delete()
        messages.success(request, "Comment removed.")
    return redirect("community:post_detail", post_id=post_id)


@login_required
def follow_toggle(request, username):
    target = get_object_or_404(User, username=username)
    if request.method == "POST" and target != request.user:
        follow, created = Follow.objects.get_or_create(follower=request.user, following=target)
        if not created:
            follow.delete()
    return redirect("community:profile", username=username)


def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    posts = Post.objects.filter(author=profile_user).select_related("author")
    if not (request.user.is_authenticated and (request.user == profile_user or request.user.is_staff)):
        posts = posts.filter(is_removed=False)
    if request.user.is_authenticated:
        posts = posts.annotate(
            viewer_has_liked=Exists(Like.objects.filter(post=OuterRef("pk"), user=request.user))
        )
    page = _paginate(request, posts)

    is_following = (
        request.user.is_authenticated
        and request.user != profile_user
        and Follow.objects.filter(follower=request.user, following=profile_user).exists()
    )
    context = {
        "profile_user": profile_user,
        "page": page,
        "is_following": is_following,
        "follower_count": Follow.objects.filter(following=profile_user).count(),
        "following_count": Follow.objects.filter(follower=profile_user).count(),
    }
    return render(request, "community/profile.html", context)


@login_required
def report_create(request, kind, object_id):
    model = REPORTABLE_MODELS.get(kind)
    if model is None:
        messages.error(request, "That can't be reported.")
        return redirect("community:feed")

    target = get_object_or_404(model, id=object_id)
    redirect_to = (
        reverse("community:post_detail", args=[target.post_id if kind == "comment" else target.id])
    )

    if request.method == "POST":
        form = ReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.content_type = ContentType.objects.get_for_model(model)
            report.object_id = target.id
            report.save()
            messages.success(request, "Thanks — we'll review this.")
        else:
            messages.error(request, "Couldn't submit that report.")
    return redirect(redirect_to)
