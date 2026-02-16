from django.urls import path
from . import views

urlpatterns = [
    path('upload/', views.upload_kmz, name='upload_kmz'),
    path('map/', views.map_view, name='map_view'),
   path('export/', views.export_geojson, name='export_geojson'),
   path('comparison/', views.comparison_map, name='comparison_map'),
   path('home/', views.homepage, name='home'),
]