import base64
from tempfile import TemporaryDirectory

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.forms import ClearableFileInput
from django.test import TestCase
from django.test.utils import override_settings
from django.core.files.base import ContentFile
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Category, Product
from .serializers import ProductSerializer


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
)
class AdminInterfaceTest(TestCase):
    def test_admin_homepage_uses_store_branding_and_stylesheet(self):
        user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="safe-test-password",
        )
        self.client.force_login(user)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Store administration")
        self.assertContains(response, "Deb Lucky Store Administration")
        self.assertContains(response, "admin/css/custom_admin.css")


class ProductAdminUploadTest(TestCase):
    def test_add_product_form_uses_an_image_file_upload(self):
        product_admin = admin.site._registry[Product]
        image_field = Product._meta.get_field("image")
        form_field = product_admin.formfield_for_dbfield(
            image_field,
            request=None,
        )

        self.assertIsInstance(form_field.widget, ClearableFileInput)


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

    def test_inactive_category_is_not_returned(self):
        Category.objects.create(
            name="Rings",
            description="Active category",
        )

        Category.objects.create(
            name="Bracelets",
            description="Inactive category",
            is_active=False,
        )

        response = self.client.get("/api/catalog/categories/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["name"],
            "Rings",
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

    def test_product_detail_api(self):
        response = self.client.get(
            f"/api/catalog/products/{self.product.id}/"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.product.id)
        self.assertEqual(
            response.data["name"],
            "Gold Fashion Ring",
        )
        self.assertEqual(response.data["price"], "250.00")

    def test_product_api_returns_backend_media_url_for_uploaded_image(self):
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/"
            "m8sAAAAASUVORK5CYII="
        )
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                self.product.image.save(
                    "gold-ring.png",
                    ContentFile(png_data),
                    save=True,
                )

                response = self.client.get(
                    f"/api/catalog/products/{self.product.id}/"
                )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["image"],
            f"http://testserver/media/products/{self.product.image.name.split('/')[-1]}",
        )

    def test_product_detail_returns_404_for_nonexistent_product(self):
        response = self.client.get("/api/catalog/products/9999/")

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_inactive_product_detail_returns_404(self):
        self.product.is_active = False
        self.product.save()

        response = self.client.get(
            f"/api/catalog/products/{self.product.id}/"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
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
        response = self.client.get(
            "/api/catalog/products/?category=abc"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST,
        )
        self.assertIn("category", response.data)

    def test_product_filter_with_negative_category(self):
        response = self.client.get(
            "/api/catalog/products/?category=-5"
        )

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
