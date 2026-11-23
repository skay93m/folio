"""URL patterns for Folio reference gallery and catalogue."""

from django.urls import path

from folio import views

app_name = "folio"

urlpatterns = [
    path("", views.gallery_view, name="gallery"),
    path("catalogue/", views.catalogue_index_view, name="catalogue"),
    path("catalogue/<slug:slug>/", views.catalogue_detail_view, name="catalogue_detail"),
]
