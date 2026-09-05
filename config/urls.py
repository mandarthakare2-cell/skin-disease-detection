from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter

# Import API views
from skin import api

# Create router for API endpoints
router = DefaultRouter()

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("skin.urls")),
    
    # REST API endpoints
    path("api/", include(router.urls)),
    path("api/auth/", include("rest_framework.urls")),
    path("api/status/", api.api_status, name="api-status"),
    path("api/predict/", api.predict_image, name="api-predict"),
    path("api/batch-predict/", api.batch_predict, name="api-batch-predict"),
    path("api/history/", api.prediction_history, name="api-history"),
    path("api/export/", api.export_predictions, name="api-export"),
    path("api/compare/", api.comparison, name="api-compare"),
    path("api/analytics/", api.analytics, name="api-analytics"),
]


from django.views.static import serve
from django.urls import re_path

urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
]