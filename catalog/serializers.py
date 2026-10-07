from rest_framework import serializers
from .models import Category, Product


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id",
            "category",
            "name",
            "description",
            "price",
            "stock_quantity",
            "is_active",
        ]


class CategorySerializer(serializers.ModelSerializer):
    def validate_name(self, value):
        cleaned_name = value.strip() if isinstance(value, str) else value
        if not cleaned_name:
            raise serializers.ValidationError("Category name cannot be empty.")
        return cleaned_name

    def create(self, validated_data):
        return Category.objects.create(**validated_data)

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "description",
            "is_active",
        ]
