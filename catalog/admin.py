from django.contrib import admin
from django.utils.html import format_html

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock_quantity", "image_preview", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("name", "description")
    list_select_related = ("category",)

    @admin.display(description="Image")
    def image_preview(self, product):
        if not product.image:
            return "No image"
        return format_html(
            '<img src="{}" alt="" style="height:48px;width:48px;object-fit:cover" />',
            product.image.url,
        )