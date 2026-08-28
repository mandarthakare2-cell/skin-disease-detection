from django.urls import path
from . import views


urlpatterns = [

    # HOME
    path(
        "",
        views.home,
        name="home"
    ),

    # REGISTER
    path(
        "register/",
        views.register_view,
        name="register"
    ),

    # LOGIN
    path(
        "login/",
        views.login_view,
        name="login"
    ),

    # LOGOUT
    path(
        "logout/",
        views.logout_view,
        name="logout"
    ),

    # PREDICTION HISTORY
    path(
        "history/",
        views.prediction_history,
        name="prediction_history"
    ),

]