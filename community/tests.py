import shutil
import tempfile

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import PostForm
from .models import Comment, Follow, Like, Post, PostType, Report, ReportReason

MEDIA_ROOT = tempfile.mkdtemp()


def tearDownModule():
    shutil.rmtree(MEDIA_ROOT, ignore_errors=True)


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class PostFormTests(TestCase):
    def test_valid_image_extension_accepted(self):
        image = SimpleUploadedFile("photo.jpg", b"fake-jpeg-bytes", content_type="image/jpeg")
        form = PostForm(data={"post_type": PostType.GENERAL, "body": "hello"}, files={"image": image})
        self.assertTrue(form.is_valid())

    def test_invalid_extension_rejected(self):
        bad_file = SimpleUploadedFile("payload.exe", b"not-an-image", content_type="application/octet-stream")
        form = PostForm(data={"post_type": PostType.GENERAL, "body": "hello"}, files={"image": bad_file})
        self.assertFalse(form.is_valid())

    def test_oversized_image_rejected(self):
        big = SimpleUploadedFile("photo.jpg", b"x" * (6 * 1024 * 1024), content_type="image/jpeg")
        form = PostForm(data={"post_type": PostType.GENERAL, "body": "hello"}, files={"image": big})
        self.assertFalse(form.is_valid())
        self.assertIn("5MB", str(form.errors))

    def test_blank_body_rejected(self):
        form = PostForm(data={"post_type": PostType.GENERAL, "body": ""})
        self.assertFalse(form.is_valid())


class PostModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.post = Post.objects.create(author=self.user, body="Leg day done.")

    def test_like_count(self):
        other = User.objects.create_user("other", "other@example.com", "password123!")
        Like.objects.create(post=self.post, user=self.user)
        Like.objects.create(post=self.post, user=other)
        self.assertEqual(self.post.like_count, 2)

    def test_comment_count_excludes_removed(self):
        Comment.objects.create(post=self.post, author=self.user, body="Nice!")
        Comment.objects.create(post=self.post, author=self.user, body="Hidden", is_removed=True)
        self.assertEqual(self.post.comment_count, 1)

    def test_freshly_created_post_is_not_edited(self):
        self.assertFalse(self.post.is_edited)

    def test_post_updated_well_after_creation_is_edited(self):
        import datetime

        created = self.post.created_at
        self.post.updated_at = created + datetime.timedelta(minutes=5)
        self.assertTrue(self.post.is_edited)


class FeedViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.other = User.objects.create_user("other", "other@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")

    def test_anonymous_can_view_feed(self):
        self.client.logout()
        Post.objects.create(author=self.other, body="Public post")
        response = self.client.get(reverse("community:feed"))
        self.assertContains(response, "Public post")

    def test_anonymous_post_redirects_to_login(self):
        self.client.logout()
        response = self.client.post(reverse("community:feed"), {"post_type": PostType.GENERAL, "body": "hi"})
        self.assertEqual(Post.objects.count(), 0)
        self.assertRedirects(response, reverse("accounts:login"))

    def test_authenticated_user_can_create_post(self):
        response = self.client.post(
            reverse("community:feed"), {"post_type": PostType.PROGRESS, "body": "New PR today!"}
        )
        self.assertRedirects(response, reverse("community:feed"))
        post = Post.objects.get()
        self.assertEqual(post.author, self.user)

    def test_posting_again_too_soon_is_blocked(self):
        self.client.post(reverse("community:feed"), {"post_type": PostType.GENERAL, "body": "First"})
        self.client.post(reverse("community:feed"), {"post_type": PostType.GENERAL, "body": "Second"})
        self.assertEqual(Post.objects.count(), 1)

    def test_removed_posts_excluded_from_feed(self):
        Post.objects.create(author=self.other, body="Spam content", is_removed=True)
        response = self.client.get(reverse("community:feed"))
        self.assertNotContains(response, "Spam content")

    def test_feed_is_paginated(self):
        for i in range(15):
            Post.objects.create(author=self.other, body=f"Post {i}")
        response = self.client.get(reverse("community:feed"))
        self.assertEqual(len(response.context["page"].object_list), 10)


class FollowingFeedTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.followed = User.objects.create_user("followed", "followed@example.com", "password123!")
        self.stranger = User.objects.create_user("stranger", "stranger@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")

    def test_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("community:following_feed"))
        self.assertEqual(response.status_code, 302)

    def test_shows_only_followed_users_posts(self):
        Follow.objects.create(follower=self.user, following=self.followed)
        Post.objects.create(author=self.followed, body="From someone I follow")
        Post.objects.create(author=self.stranger, body="From a stranger")

        response = self.client.get(reverse("community:following_feed"))
        self.assertContains(response, "From someone I follow")
        self.assertNotContains(response, "From a stranger")


class PostDetailViewTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("author", "author@example.com", "password123!")
        self.other = User.objects.create_user("other", "other@example.com", "password123!")
        self.post = Post.objects.create(author=self.author, body="Original post")
        self.client.login(username="other", password="password123!")

    def test_removed_post_hidden_from_non_owner(self):
        self.post.is_removed = True
        self.post.save()
        response = self.client.get(reverse("community:post_detail", args=[self.post.id]), follow=True)
        self.assertRedirects(response, reverse("community:feed"))

    def test_removed_post_visible_to_owner(self):
        self.post.is_removed = True
        self.post.save()
        self.client.login(username="author", password="password123!")
        response = self.client.get(reverse("community:post_detail", args=[self.post.id]))
        self.assertEqual(response.status_code, 200)

    def test_authenticated_user_can_comment(self):
        self.client.post(reverse("community:post_detail", args=[self.post.id]), {"body": "Great work!"})
        comment = Comment.objects.get()
        self.assertEqual(comment.author, self.other)
        self.assertEqual(comment.post, self.post)
        self.assertIsNone(comment.parent)

    def test_reply_to_a_reply_flattens_to_one_level(self):
        top = Comment.objects.create(post=self.post, author=self.author, body="Top level")
        reply = Comment.objects.create(post=self.post, author=self.author, body="A reply", parent=top)

        self.client.post(
            reverse("community:post_detail", args=[self.post.id]),
            {"body": "Reply to a reply", "parent_id": reply.id},
        )
        newest = Comment.objects.latest("id")
        self.assertEqual(newest.parent, top)

    def test_commenting_again_too_soon_is_blocked(self):
        url = reverse("community:post_detail", args=[self.post.id])
        self.client.post(url, {"body": "First comment"})
        self.client.post(url, {"body": "Second comment"})
        self.assertEqual(Comment.objects.filter(author=self.other).count(), 1)


class CommentDeleteTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("author", "author@example.com", "password123!")
        self.other = User.objects.create_user("other", "other@example.com", "password123!")
        self.post = Post.objects.create(author=self.author, body="Post")
        self.comment = Comment.objects.create(post=self.post, author=self.other, body="Mine")

    def test_owner_can_delete_own_comment(self):
        self.client.login(username="other", password="password123!")
        self.client.post(reverse("community:comment_delete", args=[self.comment.id]))
        self.assertFalse(Comment.objects.filter(id=self.comment.id).exists())

    def test_cannot_delete_someone_elses_comment(self):
        self.client.login(username="author", password="password123!")
        response = self.client.post(reverse("community:comment_delete", args=[self.comment.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Comment.objects.filter(id=self.comment.id).exists())


class PostEditDeleteTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user("author", "author@example.com", "password123!")
        self.other = User.objects.create_user("other", "other@example.com", "password123!")
        self.post = Post.objects.create(author=self.author, body="Original")

    def test_owner_can_edit(self):
        self.client.login(username="author", password="password123!")
        self.client.post(
            reverse("community:post_edit", args=[self.post.id]),
            {"post_type": PostType.GENERAL, "body": "Updated body"},
        )
        self.post.refresh_from_db()
        self.assertEqual(self.post.body, "Updated body")

    def test_non_owner_cannot_edit(self):
        self.client.login(username="other", password="password123!")
        response = self.client.get(reverse("community:post_edit", args=[self.post.id]))
        self.assertEqual(response.status_code, 404)

    def test_owner_can_delete(self):
        self.client.login(username="author", password="password123!")
        self.client.post(reverse("community:post_delete", args=[self.post.id]))
        self.assertFalse(Post.objects.filter(id=self.post.id).exists())

    def test_non_owner_cannot_delete(self):
        self.client.login(username="other", password="password123!")
        response = self.client.post(reverse("community:post_delete", args=[self.post.id]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Post.objects.filter(id=self.post.id).exists())


class LikeToggleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.author = User.objects.create_user("author", "author@example.com", "password123!")
        self.post = Post.objects.create(author=self.author, body="Post")
        self.client.login(username="athlete", password="password123!")

    def test_like_then_unlike(self):
        url = reverse("community:post_like_toggle", args=[self.post.id])
        self.client.post(url)
        self.assertTrue(Like.objects.filter(post=self.post, user=self.user).exists())
        self.client.post(url)
        self.assertFalse(Like.objects.filter(post=self.post, user=self.user).exists())

    def test_login_required(self):
        self.client.logout()
        response = self.client.post(reverse("community:post_like_toggle", args=[self.post.id]))
        self.assertEqual(response.status_code, 302)

    def test_open_redirect_via_next_is_rejected(self):
        url = reverse("community:post_like_toggle", args=[self.post.id])
        response = self.client.post(url, {"next": "https://evil.example.com/steal"})
        self.assertRedirects(response, reverse("community:feed"))


class FollowToggleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("athlete", "athlete@example.com", "password123!")
        self.target = User.objects.create_user("target", "target@example.com", "password123!")
        self.client.login(username="athlete", password="password123!")

    def test_follow_then_unfollow(self):
        url = reverse("community:follow_toggle", args=[self.target.username])
        self.client.post(url)
        self.assertTrue(Follow.objects.filter(follower=self.user, following=self.target).exists())
        self.client.post(url)
        self.assertFalse(Follow.objects.filter(follower=self.user, following=self.target).exists())

    def test_cannot_follow_self(self):
        url = reverse("community:follow_toggle", args=[self.user.username])
        self.client.post(url)
        self.assertFalse(Follow.objects.filter(follower=self.user, following=self.user).exists())


class ProfileViewTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", "owner@example.com", "password123!")
        self.visitor = User.objects.create_user("visitor", "visitor@example.com", "password123!")
        self.visible = Post.objects.create(author=self.owner, body="Visible")
        self.removed = Post.objects.create(author=self.owner, body="Removed", is_removed=True)

    def test_visitor_does_not_see_removed_posts(self):
        self.client.login(username="visitor", password="password123!")
        response = self.client.get(reverse("community:profile", args=[self.owner.username]))
        self.assertContains(response, "Visible")
        self.assertNotContains(response, "Removed")

    def test_owner_sees_own_removed_posts(self):
        self.client.login(username="owner", password="password123!")
        response = self.client.get(reverse("community:profile", args=[self.owner.username]))
        self.assertContains(response, "Removed")

    def test_follower_counts(self):
        Follow.objects.create(follower=self.visitor, following=self.owner)
        response = self.client.get(reverse("community:profile", args=[self.owner.username]))
        self.assertEqual(response.context["follower_count"], 1)
        self.assertEqual(response.context["following_count"], 0)


class ReportCreateTests(TestCase):
    def setUp(self):
        self.reporter = User.objects.create_user("reporter", "reporter@example.com", "password123!")
        self.author = User.objects.create_user("author", "author@example.com", "password123!")
        self.post = Post.objects.create(author=self.author, body="Reportable post")
        self.comment = Comment.objects.create(post=self.post, author=self.author, body="Reportable comment")
        self.client.login(username="reporter", password="password123!")

    def test_report_post(self):
        self.client.post(
            reverse("community:report_create", args=["post", self.post.id]),
            {"reason": ReportReason.SPAM, "details": "Looks like spam"},
        )
        report = Report.objects.get()
        self.assertEqual(report.reporter, self.reporter)
        self.assertEqual(report.content_type, ContentType.objects.get_for_model(Post))
        self.assertEqual(report.object_id, self.post.id)
        self.assertEqual(report.content_object, self.post)

    def test_report_comment(self):
        self.client.post(
            reverse("community:report_create", args=["comment", self.comment.id]),
            {"reason": ReportReason.HARASSMENT},
        )
        report = Report.objects.get()
        self.assertEqual(report.content_object, self.comment)

    def test_invalid_kind_rejected(self):
        response = self.client.post(
            reverse("community:report_create", args=["user", self.author.id]),
            {"reason": ReportReason.OTHER},
            follow=True,
        )
        self.assertEqual(Report.objects.count(), 0)
        self.assertContains(response, "can&#x27;t be reported")

    def test_daily_report_limit_is_enforced(self):
        from community.views import REPORT_DAILY_LIMIT

        other_posts = [Post.objects.create(author=self.author, body=f"Post {i}") for i in range(REPORT_DAILY_LIMIT)]
        for post in other_posts:
            self.client.post(
                reverse("community:report_create", args=["post", post.id]), {"reason": ReportReason.SPAM}
            )
        self.assertEqual(Report.objects.count(), REPORT_DAILY_LIMIT)

        self.client.post(reverse("community:report_create", args=["post", self.post.id]), {"reason": ReportReason.SPAM})
        self.assertEqual(Report.objects.count(), REPORT_DAILY_LIMIT)

    def test_login_required(self):
        self.client.logout()
        response = self.client.post(
            reverse("community:report_create", args=["post", self.post.id]), {"reason": ReportReason.SPAM}
        )
        self.assertEqual(response.status_code, 302)


class ModerationAdminActionTests(TestCase):
    def test_mark_removed_hides_post_from_feed(self):
        author = User.objects.create_user("author", "author@example.com", "password123!")
        post = Post.objects.create(author=author, body="Borderline content")
        post.is_removed = True
        post.save()
        response = self.client.get(reverse("community:feed"))
        self.assertNotContains(response, "Borderline content")
