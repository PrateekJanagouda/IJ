from django.urls import path

from . import views

urlpatterns = [
    path("auth/csrf/", views.CsrfView.as_view()),
    path("auth/register/", views.RegisterView.as_view()),
    path("auth/login/", views.LoginView.as_view()),
    path("auth/logout/", views.LogoutView.as_view()),
    path("auth/me/", views.MeView.as_view()),
    path("auth/me/roles/", views.MyRolesView.as_view()),
    path("auth/password/change/", views.PasswordChangeView.as_view()),
    path("auth/password/reset/", views.PasswordResetRequestView.as_view()),
    path("auth/password/reset/confirm/", views.PasswordResetConfirmView.as_view()),
]
