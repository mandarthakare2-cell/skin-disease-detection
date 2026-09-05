from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about_view, name="about"),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("history/", views.history_view, name="history"),
    path("history/delete/<int:history_id>/", views.delete_history_view, name="delete_history"),
    path("analytics/", views.analytics_view, name="analytics"),
]