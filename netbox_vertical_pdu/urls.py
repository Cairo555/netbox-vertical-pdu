from django.urls import path
from . import views

urlpatterns = [
    path("racks/<int:rack_pk>/add/", views.PlacementEditView.as_view(), name="verticalplacement_add"),
    path("racks/<int:rack_pk>/placements/<int:pk>/edit/", views.PlacementEditView.as_view(), name="verticalplacement_edit"),
    path("racks/<int:rack_pk>/placements/<int:pk>/delete/", views.PlacementDeleteView.as_view(), name="verticalplacement_delete"),
]
