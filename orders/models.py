from django.db import models
from catalog.models import Product


class Order(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    order_number = models.CharField(
        max_length=30,
        unique=True,
    )

    customer_name = models.CharField(max_length=200, default="")
    customer_email = models.EmailField()
    shipping_address = models.CharField(max_length=255, default="")
    shipping_city = models.CharField(max_length=100, default="")
    shipping_postal_code = models.CharField(max_length=50, default="")
    shipping_country = models.CharField(max_length=100, default="")
    payment_reference = models.CharField(
        max_length=120,
        unique=True,
        null=True,
        blank=True,
        default=None,
    )

    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    quantity = models.PositiveIntegerField()

    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"