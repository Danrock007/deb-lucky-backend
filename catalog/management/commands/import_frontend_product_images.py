from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from catalog.models import Product


class Command(BaseCommand):
    help = "Copy existing frontend product photos into Django's uploaded media storage."

    def add_arguments(self, parser):
        default_source_dir = Path(__file__).resolve().parents[2] / "initial_product_images"
        parser.add_argument(
            "--source-dir",
            default=default_source_dir,
            help="Path to the initial product image directory.",
        )
        parser.add_argument(
            "--fallback-image",
            default=default_source_dir / "gold-fashion-ring-sample.jpg",
            help="Image file to use for existing products without a matching photo.",
        )

    def handle(self, *args, **options):
        source_dir = Path(options["source_dir"]).resolve()
        fallback_image = (
            Path(options["fallback_image"]).resolve()
            if options["fallback_image"]
            else None
        )
        if not source_dir.is_dir():
            raise CommandError(f"Product image directory does not exist: {source_dir}")
        if fallback_image and not fallback_image.is_file():
            raise CommandError(f"Fallback image does not exist: {fallback_image}")

        imported = 0
        fallback_count = 0
        skipped = 0
        for product in Product.objects.order_by("id"):
            if product.image and product.image.storage.exists(product.image.name):
                skipped += 1
                continue

            original_name = Path(product.image.name).name if product.image else ""
            image_path = source_dir / original_name if original_name else fallback_image
            using_fallback = not original_name
            if image_path is None or not image_path.is_file():
                if fallback_image and fallback_image.is_file():
                    image_path = fallback_image
                    using_fallback = True
                else:
                    raise CommandError(
                        f"No local image found for product {product.pk} ({product.name}); "
                        "provide --fallback-image for missing photos."
                    )

            stored_name = (
                f"gold-fashion-ring-sample{image_path.suffix.lower()}"
                if using_fallback
                else image_path.name
            )
            with image_path.open("rb") as source_file:
                product.image.save(stored_name, File(source_file), save=False)
            product.save(update_fields=["image"])
            imported += 1
            fallback_count += int(using_fallback)
            self.stdout.write(f"Imported {product.name}: {product.image.name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {imported} product images; {fallback_count} used the sample image; "
                f"{skipped} already had uploaded images."
            )
        )
