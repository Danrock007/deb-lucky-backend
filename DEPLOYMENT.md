# Backend deployment

## Required production configuration

Set these values in the hosting provider's secret/environment settings; do not
commit a real `.env` file:

- `DJANGO_DEBUG=false`
- `DJANGO_SECRET_KEY`: a newly generated, private Django secret
- `DJANGO_ALLOWED_HOSTS`: comma-separated API and storefront proxy hostnames,
  without schemes
- `CORS_ALLOWED_ORIGINS`: exact HTTPS storefront origins
- `CSRF_TRUSTED_ORIGINS`: exact HTTPS origins used for Django admin
- `DATABASE_URL`: managed PostgreSQL connection string
- `PAYSTACK_SECRET_KEY`: the server-side Paystack secret key
- `PAYSTACK_CALLBACK_URL`: the storefront's HTTPS `/checkout` URL
- `DJANGO_SECURE_SSL_REDIRECT=true` when the host terminates TLS and forwards
  `X-Forwarded-Proto: https` through to Django

Set `DJANGO_MEDIA_ROOT` to a persistent, writable volume mounted at the same
path on every backend instance (for example `/data/media`). Uploaded images
are not included in the container image. In production, configure the
platform's reverse proxy or object-storage/CDN to serve that media directory
at the same `/media/` URL. Django's direct media file serving is enabled only
for local development.

Configure the SMTP variables (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, and `DEFAULT_FROM_EMAIL`) before launch
to deliver order-confirmation messages. Delivery failures are logged without
rolling back a verified payment.

## Container deployment

Build the backend image from this directory:

```sh
docker build -t deb-lucky-backend .
```

Before starting the web process for a new release, run:

```sh
docker run --rm --env-file .env deb-lucky-backend python manage.py migrate
docker run --rm --env-file .env deb-lucky-backend python manage.py import_frontend_product_images
```

The import command copies bundled initial photos onto existing catalog
products and skips products whose image is already in media storage. Static
assets are collected into the image during build. Run the image on port `8000`;
its default command uses Gunicorn. Configure the host's health check to call
`/api/health/`. Create the initial admin user with `python manage.py
createsuperuser` using the same production environment.

The storefront may be hosted on a separate static site or built from
`client/Dockerfile`. With a same-origin deployment, the Nginx frontend proxies
`/api/` to the backend service (default upstream `backend:8000`). For separate
origins, set the frontend build argument `VITE_API_URL` to
`https://api.example.com/api` and configure the matching CORS origin on Django.

Inventory is checked both when an order is prepared and when its payment is
confirmed, but it is not reserved while the customer is on Paystack. If stock
is exhausted during checkout, the payment stays visible as pending for manual
reconciliation/refund in Paystack. Monitor pending orders, especially for
low-stock items.

## Paystack

Configure the Paystack dashboard webhook URL as
`https://api.example.com/api/orders/paystack/webhook/`. The webhook endpoint
validates Paystack's HMAC signature and independently verifies each payment
before changing order status or inventory. The checkout callback also performs
server-side transaction verification and is safe to retry.

Use Paystack test keys and test transactions in staging. Switch to a live
secret key only after the HTTPS domain, database backups, webhook, admin
account, and payment reconciliation process have been verified.
