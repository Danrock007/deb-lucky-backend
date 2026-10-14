from rest_framework import serializers

from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    def validate_name(self, value):
        cleaned_name = value.strip()

        if not cleaned_name:
            raise serializers.ValidationError(
                "Category name cannot be empty."
            )

        return cleaned_name

    class Meta:
        model = Category
        fields = ["id", "name", "description", "is_active"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    image = serializers.SerializerMethodField()

    def get_image(self, product):
        if not product.image:
            return None
        request = self.context.get("request")
        image_url = product.image.url
        return request.build_absolute_uri(image_url) if request else image_url

    def validate_name(self, value):
        cleaned_name = value.strip()

        if not cleaned_name:
            raise serializers.ValidationError(
                "Product name cannot be empty."
            )

        return cleaned_name

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "Product price must be greater than zero."
            )

        return value

    def validate_stock_quantity(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Stock quantity cannot be negative."
            )

        return value

    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "category_name",
            "name",
            "description",
            "price",
            "stock_quantity",
            "image",
            "badge",
            "is_active",
        ]