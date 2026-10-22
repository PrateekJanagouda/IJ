from django.urls import path

from . import views

urlpatterns = [
    path("media/", views.MediaUploadView.as_view()),
    path("media/<uuid:asset_id>/", views.serve),
]
