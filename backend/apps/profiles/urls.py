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
    path("venues/<uuid:venue_id>/availability/", views.VenueAvailabilityView.as_view()),
    path("venues/<uuid:venue_id>/bookings/", views.VenueBookingsView.as_view()),
    path("venues/<uuid:venue_id>/blocks/", views.VenueBlockView.as_view()),
    path("venue-bookings/mine/", views.MyVenueBookingsView.as_view()),
    path("venue-bookings/<uuid:booking_id>/confirm/",
         views.VenueBookingActionView.as_view(action="confirm")),
    path("venue-bookings/<uuid:booking_id>/decline/",
         views.VenueBookingActionView.as_view(action="decline")),
    path("venue-bookings/<uuid:booking_id>/cancel/",
         views.VenueBookingActionView.as_view(action="cancel")),
]
