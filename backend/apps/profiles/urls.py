from django.urls import path

from . import views

urlpatterns = [
    path("genres/", views.GenreListView.as_view()),
    path("skills/", views.SkillListView.as_view()),
    path("profiles/", views.ProfileSearchView.as_view()),
    path("profiles/me/", views.MyProfileView.as_view()),
    path("profiles/me/portfolio/", views.MyPortfolioView.as_view()),
    path("profiles/me/portfolio/<uuid:item_id>/", views.MyPortfolioItemView.as_view()),
    path("profiles/<uuid:profile_id>/", views.ProfileDetailView.as_view()),
    path("venues/", views.VenueListView.as_view()),
    path("venues/<uuid:venue_id>/", views.VenueDetailView.as_view()),
    path("venues/<uuid:venue_id>/managers/", views.VenueManagersView.as_view()),
]
