# Backend deployment

## Required production configuration

Set these values in the hosting provider's secret/environment settings; do not
commit a real `.env` file:

- `DJANGO_DEBUG=false`
- `DJANGO_SECRET_KEY`: a newly generated, private Django secret
- `DJANGO_ALLOWED_HOSTS`: comma-separated API and storefront proxy hostnames,
  without schemes
- `CORS_ALLOWED_ORIGINS`: exact HTTPS storefront origins
- `CSRF_TRUSTED_ORIGINS`: exact HTTPS storefront and admin origins
- `DATABASE_URL`: managed PostgreSQL connection string
- `PAYSTACK_SECRET_KEY`: the server-side Paystack secret key
- `PAYSTACK_CALLBACK_URL`: the storefront's HTTPS `/checkout` URL
- `ACCOUNT_VERIFICATION_URL`: the storefront's HTTPS `/account/verify` URL
- `DJANGO_SESSION_COOKIE_SAMESITE=None` for a storefront and API on separate
  sites; secure cookies are enabled in production
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
to deliver order-confirmation and customer email-verification messages.
Customer accounts are activated only after the customer verifies ownership of
the email address; verification links expire after 24 hours. Delivery failures
are logged and returned as errors.

Account sessions use Django's CSRF-protected session cookies. The API enables
credentialed CORS; allow only the storefront in `CORS_ALLOWED_ORIGINS` and
`CSRF_TRUSTED_ORIGINS`. Configure a shared cache or edge rate limit for the
10-per-hour account authentication limit when running multiple backend
instances.

Set `CONTACT_EMAIL` to the inbox that should receive storefront contact-form
submissions. The `/api/contact/` endpoint sends messages through the configured
email backend, applies a five-per-hour anonymous request limit, and returns an
error instead of reporting success when delivery is unavailable. Configure a
shared Django cache or edge rate limit if that limit must be shared across
multiple backend instances. In local development, Django prints contact
messages to the console.

The storefront newsletter form is not connected to a mailing-list provider.
Connect it only after selecting a provider and configuring its credentials and
required subscriber-consent/unsubscribe flow.

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

The storefront is maintained in the separate `Deb_Lucky_Fashion_Jewelries`
repository. It may be hosted on a static site or built from that repository's
`client/Dockerfile` with the `client` directory as the Docker build context:

```sh
docker build -f client/Dockerfile -t deb-lucky-storefront client
```

For a same-origin deployment, put the Nginx frontend and backend on the same
network and set `API_UPSTREAM` to the backend service hostname and port
(default `backend:8000`). The frontend then proxies `/api/` to Django. For
separate origins, set the frontend build argument `VITE_API_URL` to
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
