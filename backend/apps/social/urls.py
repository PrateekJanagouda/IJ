from django.urls import path

from . import views as v

urlpatterns = [
    path("feed/", v.HomeFeedView.as_view()),
    path("feed/discover/", v.DiscoverFeedView.as_view()),
    path("posts/", v.PostListView.as_view()),
    path("posts/<uuid:post_id>/", v.PostDetailView.as_view()),
    path("posts/<uuid:post_id>/repost/", v.RepostView.as_view()),
    path("posts/<uuid:post_id>/like/", v.PostLikeView.as_view()),
    path("posts/<uuid:post_id>/comments/", v.PostCommentsView.as_view()),
    path("comments/<uuid:comment_id>/", v.CommentDetailView.as_view()),
    path("users/<uuid:user_id>/follow/", v.FollowView.as_view()),
    path("users/<uuid:user_id>/followers/", v.FollowersView.as_view()),
    path("users/<uuid:user_id>/following/", v.FollowingView.as_view()),
]
