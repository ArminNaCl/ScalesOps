"""
URL configuration for scales_ops project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

# Import your FeatureFlagViewSet from your app
from featureflag.api import (
    feature_flag_list_create,
    feature_flag_retrieve,
    feature_flag_toggle,
    dependency_list_create
)
# Create a router for your ViewSets
router = routers.DefaultRouter()



urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/featureflags/', feature_flag_list_create, name='featureflag-list-create'),
    path('api/featureflags/<int:pk>/', feature_flag_retrieve, name='featureflag-retrieve'),
    path('api/featureflags/<int:pk>/toggle/', feature_flag_toggle, name='featureflag-toggle'),


    path('api/dependencies/', dependency_list_create, name='dependency-list-create'),

    

    # OpenAPI Schema and UI endpoints
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

