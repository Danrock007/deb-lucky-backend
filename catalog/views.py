from rest_framework import generics
from rest_framework.exceptions import ValidationError
from .models import Product, Category
from .serializers import CategorySerializer, ProductSerializer


class ProductListView(generics.ListAPIView):
    serializer_class = ProductSerializer

    def get_queryset(self):
        queryset = Product.objects.filter(is_active=True)

        category_id = self.request.query_params.get("category")

        if category_id is not None:
            if not category_id.isdigit() or int(category_id) <= 0:
                raise ValidationError({
                    "category": "Category ID must be a positive integer."
                })

            queryset = queryset.filter(category_id=int(category_id))

        return queryset


class ProductDetailView(generics.RetrieveAPIView):
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer


class CategoryListView(generics.ListAPIView):
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
