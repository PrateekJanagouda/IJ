from django.urls import path

from . import views as v

urlpatterns = [
    path("notifications/", v.NotificationListView.as_view()),
    path("notifications/unread-count/", v.UnreadCountView.as_view()),
    path("notifications/read-all/", v.MarkAllReadView.as_view()),
    path("notifications/<uuid:notification_id>/read/", v.MarkReadView.as_view()),
]
