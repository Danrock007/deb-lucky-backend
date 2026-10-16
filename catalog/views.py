from rest_framework import generics
from rest_framework.exceptions import ValidationError

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        # Return only active products.
        queryset = Product.objects.filter(
            is_active=True
        ).order_by("id")

        # Read the optional category ID from the URL.
        category_id = self.request.query_params.get("category")

        if category_id is not None:
            # Reject non-numeric, zero, and negative category IDs.
            if not category_id.isdigit() or int(category_id) <= 0:
                raise ValidationError({
                    "category": "Enter a valid positive category ID."
                })

            # Filter products by the selected category.
            queryset = queryset.filter(
                category_id=int(category_id),
                category__is_active=True,
            )

        return queryset


class ProductDetailView(generics.RetrieveAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        # Customers should only retrieve active products.
        return Product.objects.filter(
            is_active=True
        ).order_by("id")


class CategoryListView(generics.ListAPIView):
    # Return only active categories in a consistent order.
    queryset = Category.objects.filter(
        is_active=True
    ).order_by("id")

    serializer_class = CategorySerializer
