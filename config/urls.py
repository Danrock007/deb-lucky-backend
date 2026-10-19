from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.http import JsonResponse
from django.db import connections
from django.db.utils import DatabaseError


admin.site.site_header = "Deb Lucky Store"
admin.site.site_title = "Deb Lucky Store Administration"
admin.site.index_title = "Store overview"


def health_check(request):
    try:
        connections["default"].ensure_connection()
    except DatabaseError:
        return JsonResponse({"status": "unhealthy"}, status=503)
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", health_check, name="health-check"),
    path("api/catalog/", include("catalog.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/contact/", include("support.urls")),
    path("api/accounts/", include("accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
