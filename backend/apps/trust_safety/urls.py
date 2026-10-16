from django.urls import path

from . import views as v

urlpatterns = [
    path("reports/", v.ReportListView.as_view()),
    path("blocks/", v.BlockListView.as_view()),
    path("blocks/<uuid:user_id>/", v.BlockDetailView.as_view()),
    path("moderation/reports/", v.ModerationQueueView.as_view()),
    path("moderation/reports/<uuid:report_id>/", v.ModerationReportView.as_view()),
    path("moderation/reports/<uuid:report_id>/actions/", v.ModerationActionView.as_view()),
]
