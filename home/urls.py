from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name = "home"),
    path('prediction/',views.prediction,name="prediction")
    # path('city/<cityname>/',views.getCoordinates,name="citygetCoordinates"),
    # path('concentration/',views.pollutantConcentration,name="airpollution"),
]