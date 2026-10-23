from mimetypes import guess_type

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.storage import FileSystemStorage
from django.contrib import admin
from django.http import FileResponse, Http404, JsonResponse
from django.urls import include, path
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


def serve_media(request, path):
    storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    try:
        media_file = storage.open(path, "rb")
    except (FileNotFoundError, IsADirectoryError, SuspiciousFileOperation) as exc:
        raise Http404("Media file not found.") from exc
    return FileResponse(
        media_file,
        content_type=guess_type(path)[0] or "application/octet-stream",
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("media/<path:path>", serve_media, name="media"),
    path("api/health/", health_check, name="health-check"),
    path("api/catalog/", include("catalog.urls")),
    path("api/orders/", include("orders.urls")),
    path("api/contact/", include("support.urls")),
    path("api/accounts/", include("accounts.urls")),
]
