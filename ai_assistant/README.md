## Project 4 - AI Assistant Platform

### Overview

A Django-based full-stack AI assistant platform with multiple apps including user authentication, a dashboard, bot management, and payment integration using Stripe. Built from scratch and deployed with Heroku.

---

### ✅ Features Implemented

#### 1. Project Setup

* Project initialized with `django-admin startproject` and virtual environment setup.
* Folder structure aligned to:

  ```
  ai-assistant/
    |-- ai_assistant/
    |-- dashboard/
    |-- accounts/
    |-- bots/
    |-- payments/
    |-- templates/
    |-- static/
  ```
* Django apps registered in `settings.py` with proper dotted paths (e.g., `ai_assistant.accounts`).

#### 2. Models & Migrations

* Models for accounts, bots, and payments defined.
* Migrations run with `python manage.py makemigrations && migrate`.

#### 3. Admin Panel

* Admin interface configured.
* Models registered for view/edit via Django admin.

#### 4. Views & Templates

* `dashboard/index.html` rendered with a working homepage view.
* All apps wired with minimal views for testing routes.
* Templates folder linked in settings.

#### 5. Static Files

* Static folder structure: `static/css`, `static/js`, `static/images`.
* `STATIC_URL` set in settings.
* Basic CSS styles loaded in templates.

---

### ✅ Step 6: Authentication

* User registration, login, logout implemented.
* `accounts/views.py` handles authentication.
* Templates:

  * `login.html`, `register.html`, `logout.html`
* Uses Django built-in `User` model.
* Conditional navigation based on auth status.

### ✅ Step 7: Bot Management

* `bots` app handles CRUD for assistant bots.
* Models include Bot (name, category, description, creator).
* Permissions:

  * Only the creator can edit/delete a bot.
* Templates:

  * `bots/list.html`, `bots/detail.html`, `bots/form.html`
* Views:

  * List, Create, Update, Delete implemented with Django CBVs.

### ✅ Step 8: Stripe Integration

* `payments` app integrated with Stripe test mode.
* Stripe public and secret keys stored in `.env`.
* Checkout session created via view.
* Stripe webhooks placeholder ready.
* Payments linked to bot usage/subscription.
* Templates:

  * `payments/checkout.html`, `payments/success.html`, `payments/cancel.html`

---

### 🛠️ Technologies Used

* Python 3.13
* Django 4.2
* PostgreSQL (dev: SQLite)
* HTML5, CSS3, JavaScript
* Stripe API
* Gunicorn, Whitenoise (for deployment)

### ✅ Deployment

* Project deployed to Heroku.
* Procfile, `runtime.txt`, and `requirements.txt` configured.
* Static files served via Whitenoise.
* Environment variables loaded via `python-decouple`.

---

This README will be continuously updated with future steps, testing details, and OAuth integration.

---
🧱 Completed Steps
Project Setup

Created a Django project ai_assistant with apps: dashboard, accounts, bots, payments.

Static File Handling

Fixed {% static %} issue by adding {% load static %} in base.html.

Stripe Integration

Installed Stripe (pip install stripe) and added public/private keys in settings.

Homepage Working

dashboard/index.html renders properly through base.html.

Verified styling and template blocks load without errors.

💳 Stripe Payment Integration
The project includes a Stripe-based subscription system:

Billing Page: Accessible at /payments/, allows users to initiate a subscription payment.

Checkout Session: Created using Stripe's API via the create_checkout_session view.

Success/Cancel Pages: Users are redirected to /payments/success/ or /payments/cancel/ after payment.

JavaScript Integration: Stripe.js is used on the frontend for redirection.

.env Configuration:

env
Kopiera
Redigera
STRIPE_PUBLIC_KEY=your_test_public_key
STRIPE_SECRET_KEY=your_test_secret_key
Environment Loading: API keys are securely loaded using os.getenv() from the .env file.

⚠️ Make sure to replace test keys with live keys in production.

Styling & UX Features
✅ Dark/Light Theme Toggle
Users can switch between dark and light modes with smooth transitions. The toggle button is consistently styled across both themes.

✅ Consistent Button Design
All navigation and action buttons (including Logout and Toggle Theme) have:

Matching size, padding, and font

Unified color scheme (no blue backgrounds or hover effects)

Uniform hover behavior (subtle darkening only)

No borders or unwanted outlines

✅ Footer Consistency

The footer is fixed to the bottom of the page across all devices (mobile, tablet, desktop).

It matches the button background color in both themes.

Text is bold and legible, with a subtle shadow in light mode.

✅ Responsive Layout

Flexbox-based navigation and content layout

Fully responsive from narrow mobile screens to wide desktop monitors

✅ Clean Visual Hierarchy

Modern card texture for subscription plans

Subtle shadows and transitions

Font consistency and spacing across all sections

