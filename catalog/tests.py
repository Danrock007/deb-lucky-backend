from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category, Product
from .serializers import ProductSerializer


class CategoryModelTest(TestCase):
    def test_category_can_be_created(self):
        category = Category.objects.create(
            name="Test Category",
            description="Test description",
        )

        self.assertEqual(category.name, "Test Category")
        self.assertTrue(category.is_active)


class CategoryAPITest(APITestCase):
    def test_category_list_api(self):
        category = Category.objects.create(
            name="Rings",
            description="Fashion rings and jewelry rings",
        )

        response = self.client.get("/api/catalog/categories/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["name"],
            category.name,
        )


class ProductModelTest(TestCase):
    def test_product_can_be_created(self):
        category = Category.objects.create(
            name="Rings",
            description="Fashion rings and jewelry rings",
        )

        product = Product.objects.create(
            category=category,
            name="Test Gold Ring",
            description="Test product",
            price="250.00",
            stock_quantity=10,
        )

        self.assertEqual(product.name, "Test Gold Ring")
        self.assertEqual(product.stock_quantity, 10)
        self.assertTrue(product.is_active)


class ProductAPITest(APITestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Rings",
            description="Fashion rings and jewelry rings",
        )

        self.product = Product.objects.create(
            category=self.category,
            name="Gold Fashion Ring",
            description="Elegant gold fashion ring",
            price="250.00",
            stock_quantity=10,
        )

    def test_product_list_api(self):
        response = self.client.get("/api/catalog/products/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertIsNone(response.data["next"])
        self.assertIsNone(response.data["previous"])
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["name"],
            "Gold Fashion Ring",
        )

    def test_product_filter_by_category(self):
        response = self.client.get(
            f"/api/catalog/products/?category={self.category.id}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["name"],
            "Gold Fashion Ring",
        )

    def test_inactive_product_is_not_returned(self):
        self.product.is_active = False
        self.product.save()

        response = self.client.get("/api/catalog/products/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_product_filter_with_non_numeric_category(self):
        response = self.client.get("/api/catalog/products/?category=abc")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("category", response.data)

    def test_product_filter_with_negative_category(self):
        response = self.client.get("/api/catalog/products/?category=-5")

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("category", response.data)

    def test_product_pagination_response_structure(self):
        response = self.client.get("/api/catalog/products/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)

    def test_product_serializer_rejects_blank_name(self):
        data = {
            "category": self.category.id,
            "name": "   ",
            "description": "Test product",
            "price": "250.00",
            "stock_quantity": 10,
            "is_active": True,
        }

        serializer = ProductSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_product_serializer_rejects_zero_price(self):
        data = {
            "category": self.category.id,
            "name": "Test Ring",
            "description": "Test product",
            "price": "0.00",
            "stock_quantity": 10,
            "is_active": True,
        }

        serializer = ProductSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("price", serializer.errors)

    def test_product_serializer_rejects_negative_stock(self):
        data = {
            "category": self.category.id,
            "name": "Test Ring",
            "description": "Test product",
            "price": "250.00",
            "stock_quantity": -5,
            "is_active": True,
        }

        serializer = ProductSerializer(data=data)

        self.assertFalse(serializer.is_valid())
        self.assertIn("stock_quantity", serializer.errors)
