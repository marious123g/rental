from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter
from rental.api import ProductViewSet, AssetViewSet, OrderViewSet
router=DefaultRouter()
router.register("products",ProductViewSet); router.register("assets",AssetViewSet); router.register("orders",OrderViewSet)
urlpatterns=[path("admin/",admin.site.urls),path("accounts/",include("django.contrib.auth.urls")),path("api/",include(router.urls)),path("",login_required(TemplateView.as_view(template_name="index.html")))]
