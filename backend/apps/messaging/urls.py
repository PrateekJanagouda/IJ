from django.urls import path

from . import views as v

urlpatterns = [
    path("conversations/", v.ConversationListView.as_view()),
    path("conversations/unread-count/", v.UnreadMessagesView.as_view()),
    path("conversations/<uuid:conversation_id>/", v.ConversationDetailView.as_view()),
    path("conversations/<uuid:conversation_id>/messages/", v.ConversationMessagesView.as_view()),
    path("conversations/<uuid:conversation_id>/read/", v.ConversationReadView.as_view()),
    path("conversations/<uuid:conversation_id>/archive/", v.ConversationArchiveView.as_view()),
    path("messages/<uuid:message_id>/", v.MessageDetailView.as_view()),
]
