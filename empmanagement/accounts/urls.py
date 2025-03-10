from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path('', views.landing_page, name='landing_page'),
    path('login/',views.login_user,name="login_user"),
    path('logout',views.logout_user,name="logout_user"),
    path('signup',views.signup,name="signup"),
]   