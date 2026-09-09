# 🤖 AI Assistant Platform

> A full-stack AI SaaS platform built with **Django**, **OpenAI**, **Stripe**, **Redis**, and **Discord**.

AI Assistant Platform enables users to create specialized AI assistants, extend them with their own knowledge, manage separate conversations, track AI usage, integrate assistants with Discord, and access the platform through secure web and REST interfaces.

The platform is under active development. Core backend functionality is implemented and covered by automated tests, while final production validation, hosted Stripe acceptance testing, production Redis verification, and the planned Android client remain part of the release process.

---

## 🌐 Live Demo

### Cloud Deployment

A Heroku deployment is maintained for the project.

The hosted application may not always represent the latest local backend changes while release validation is in progress.

---

## 🚀 Highlights

- 🤖 Specialized AI assistants powered by OpenAI
- 🧭 Category-based domain enforcement
- 📚 Retrieval-Augmented Generation (RAG) with custom knowledge
- 🧠 Semantic search using OpenAI embeddings
- 💬 Separate and manageable AI conversations
- 🔄 Shared chat service across web and API interfaces
- 📊 Token usage and AI cost tracking
- 🚦 Plan-aware usage limits and rate limiting
- 🔐 Secured REST API with API-key authentication
- 💳 Free, Premium, and Pro account plans
- 💳 Stripe subscription infrastructure in Test Mode
- ⚡ Redis-backed production rate-limit architecture
- 🤖 Bring Your Own Discord Bot (BYOB)
- 👤 Secure Django authentication and authorization
- 🌙 Dark and Light mode
- 📱 Responsive web interface
- ☁️ Heroku deployment architecture
- 📲 Android and Google Play integration planned

---

## 📸 Preview

Application screenshots and workflow diagrams are included throughout this README.

---

# ✨ Features

AI Assistant Platform combines specialized artificial intelligence, knowledge retrieval, conversation management, usage accounting, subscription infrastructure, API access, analytics, and Discord integration in a single Django application.

---

## 🤖 AI Assistants

Users can create and manage specialized AI assistants powered by OpenAI.

### Capabilities

- Create custom AI assistants
- Configure assistant personalities and behaviour
- Organize assistants by category
- Enforce category-specific conversation domains
- Real-time AI conversations
- Context-aware responses
- Separate conversation histories
- Rename and delete conversations
- Daily and monthly usage controls
- Token and AI cost accounting
- Free accounts can create up to 3 assistants
- Premium and Pro accounts can create additional assistants without the Free-plan assistant limit

Assistant category rules help prevent specialized assistants from answering unrelated requests. General-purpose assistants can operate without category classification, while specialized categories use domain checks before the main AI response is generated.

---

## 📚 Knowledge Base

Assistants can be extended with user-provided knowledge through a Retrieval-Augmented Generation workflow.

### Included Functionality

- Upload TXT knowledge files
- Automatic text processing
- Intelligent text chunking
- OpenAI embedding generation
- Batched embedding requests
- Embedding response validation
- Semantic similarity search
- Bot-specific knowledge isolation
- Relevant knowledge injection into AI prompts
- Graceful fallback when retrieval fails
- Atomic knowledge uploads
- Cleanup after failed database operations
- Embedding usage and cost tracking
- Easy knowledge management

The current embedding implementation uses `text-embedding-3-small`. Knowledge retrieval is scoped to the selected assistant so knowledge belonging to another assistant is not included in a response.

---

## 💬 AI Playground

The web playground provides an interactive interface for testing and using assistants.

### Functionality

- Real-time AJAX chat
- AI responses powered by `gpt-4o-mini`
- Separate conversations per assistant
- Create new conversations
- Switch between conversations
- Rename conversations
- Delete conversations
- Conversation-specific history
- Safe Markdown-style message rendering
- Knowledge retrieval when relevant
- Category enforcement
- Usage-limit enforcement
- Rate-limit enforcement
- Mobile-friendly interface
- Dark and Light mode support

The web interface and API use the same shared backend chat service, reducing duplicated AI logic and keeping usage accounting, domain checks, knowledge retrieval, and conversation handling consistent.

---

## 🧭 Category & Domain Enforcement

Specialized assistants are restricted to their configured subject areas.

### Domain Controls

- Category-specific domain rules
- Lightweight classification before the main AI response
- Out-of-domain requests are rejected before knowledge retrieval and the main AI response
- General-purpose assistants bypass unnecessary classification
- Domain decisions are included in AI usage accounting
- Category behaviour is covered by automated regression tests

This architecture helps assistants remain focused on their intended purpose instead of behaving like unrestricted general-purpose chatbots.

---

## 🧠 AI Usage & Cost Tracking

AI activity is tracked by the backend to support analytics, usage controls, and cost monitoring.

### Tracked Data

- Input tokens
- Output tokens
- Total token usage
- Model identifier
- AI request usage
- Embedding usage
- Estimated model cost
- Per-user usage
- Current-month usage

Pricing configuration supports the AI models currently used by the application, including the `gpt-4o-mini` alias and `text-embedding-3-small`.

---

## 🚦 Plans, Usage Limits & Rate Limiting

The application currently defines three account plans.

| Plan | Daily AI Messages | Monthly AI Cost Safety Limit | Request Rate |
| --- | ---: | ---: | ---: |
| Free | 15 | $0.60 | 20 requests/minute |
| Premium | 500 | $10.00 | 60 requests/minute |
| Pro | No normal configured daily cap | No normal configured monthly cost cap | 120 requests/minute |

The Free plan can create up to 3 assistants. Premium and Pro accounts are not subject to the Free-plan assistant limit.

Pro remains protected by request-rate and abuse controls even though it does not have a normal daily or monthly AI usage cap.

Redis-backed caching is implemented for production rate limiting. Local development can use the configured local-memory fallback. Final production Redis connectivity still requires hosted-environment validation.

---

## 💳 Subscription Infrastructure

Subscription handling is implemented with Stripe and is currently restricted to **Stripe Test Mode** during development and release validation.

### Current Plans

| Plan | Monthly Price |
| --- | ---: |
| Free | $0.00 USD |
| Premium | $12.99 USD |
| Pro | $24.99 USD |

### Implemented Stripe Functionality

- Stripe Checkout integration
- Premium and Pro subscriptions
- Subscription metadata validation
- Signed webhook verification
- Checkout completion handling
- Subscription upgrade handling
- Subscription downgrade handling
- Subscription cancellation handling
- Subscription recovery handling
- Duplicate webhook protection
- Current-subscription reconciliation
- Customer and subscription ownership validation
- Price and billing-period validation
- Test/Live mode mismatch protection
- Retryable provider failure handling
- Sanitized payment-provider errors

Stripe Live Mode is not used at this stage. Hosted Test Mode acceptance testing and final production configuration remain release tasks.

The planned Android application will use Google Play Billing rather than Stripe for Android in-app subscription purchases.

---

## 🤖 Discord Integration

Assistants can be connected to user-owned Discord bots through the Bring Your Own Bot (BYOB) workflow.

### Included Features

- Bring Your Own Discord Bot
- Downloadable Discord Bridge package
- Setup Guide
- Commands Guide
- Discord Invite Generator
- Secure API communication
- Windows support
- macOS support
- Linux support

---

## 📊 Dashboard & Analytics

The dashboard provides visibility into assistant and AI activity.

### Analytics

- User dashboard
- Assistant overview
- Usage statistics
- Token usage tracking
- AI cost tracking
- Conversation logs
- CSV export
- Staff-only analytics

---

## 👤 User Management

Authentication and account management are handled by Django.

### Features

- User registration
- Login and logout
- Password reset
- Email notifications
- Secure sessions
- Protected routes
- User profiles
- Account plan tracking
- API-key-based external access

---

## 🔌 APIs & Integrations

The platform exposes REST interfaces and integrates with several external services.

### Integrations

- OpenAI API
- Stripe API
- Discord API
- Django REST Framework
- Redis-compatible cache infrastructure
- PostgreSQL
- Heroku

### API Security

- API-key authentication
- Active-user validation
- Request-body shape validation
- Bot identifier validation
- Conversation ownership validation
- Assistant ownership validation
- Safe API-key rotation support
- Protected chat endpoints
- Sanitized client-facing errors

API keys are treated as credentials and are not exposed in administrative list views or searchable through the Django admin interface.

---

## 🎨 User Experience

The web application is designed to work across desktop and mobile screen sizes.

### Features

- Fully responsive layout
- Dark and Light mode
- Modern user interface
- Responsive navigation
- Accessible forms
- Custom success messages
- Custom error messages
- AJAX-based chat interactions
- Conversation management controls

---

## 🔒 Security & Reliability

Security and failure handling are built into the backend architecture.

### Implemented Controls

- CSRF protection
- Authentication and authorization
- Object ownership validation
- Protected API endpoints
- Environment-based secret configuration
- Secure session handling
- API-key authentication
- Active-account checks
- Input shape validation
- Stripe webhook signature verification
- Stripe event idempotency
- Payment ownership validation
- Transactional payment reconciliation
- Atomic knowledge uploads
- Failed-upload cleanup
- Embedding response validation
- Knowledge isolation between assistants
- Rate limiting
- Fail-closed production cache behaviour
- Sanitized provider errors
- Reduced sensitive information exposure in Django admin
- No sensitive startup logging

Final hosted security review, production Redis connectivity validation, Stripe hosted Test Mode acceptance testing, and deployment verification remain part of the release process.

---

# 📸 Application Tour

The following screenshots provide an overview of the application's interface and demonstrate the main features available throughout the platform.

---

## 🏠 Home Page

The landing page introduces the platform, highlights its core features, and provides quick access to user authentication and the dashboard.

![Home - Dark Mode](readme-img-validation/home-darkmode.jpg)

---

## ☀️ Light Theme

Users can switch between Dark and Light mode at any time. The selected preference is automatically remembered for future visits.

![Home - Light Mode](readme-img-validation/home-lightmode.jpg)

---

## 🤖 Create an AI Assistant

Create fully customized AI assistants by defining their name, category, personality, and behavior.

![Create Bot](readme-img-validation/create-bot.jpg)

---

## 💬 AI Playground

Each assistant includes its own interactive chat playground where conversations take place in real time using OpenAI.

**Historical screenshot, described in English:** The historical playground showed a conversation with a recipe assistant, a message field, a Send button, and a knowledge upload form. The upload controls are described in English as "Choose file", "No file chosen", and "Upload Knowledge". The original screenshot remains in Git history.

---

## 📚 Knowledge Base

Upload your own text files to provide assistants with additional knowledge. Uploaded documents are processed and made available for semantic retrieval.

![Knowledge Upload](readme-img-validation/answer-upload-knowledge-txt.jpg)

---

## ✅ Knowledge Processing Complete

Once processing is complete, the uploaded knowledge becomes immediately available for AI-generated responses.

![Knowledge Upload Confirmation](readme-img-validation/knowledge-upload-confirm.jpg)

---

## 🤖 Discord Integration

Deploy assistants directly to your own Discord server using the included Bring Your Own Bot (BYOB) bridge.

**Historical screenshot, described in English:** The historical Discord conversation showed a user asking how to stay comfortable in hot weather and the assistant returning a numbered list of suggestions. The message field is described in English as "Send a message to @AI Assistant". The original screenshot remains in Git history.

---

## 💳 Premium Membership

Upgrade to a Premium or Pro account to remove the Free plan assistant limit and unlock additional platform features.

![Premium Upgrade](readme-img-validation/premium-upgrade.jpg)

---

## 💳 Secure Stripe Checkout

Premium subscriptions are processed securely through Stripe Checkout.

**Historical screenshot, described in English:** The historical Stripe sandbox Checkout showed a Pro Bot Plan priced at USD 15.00, a Pay with Link button, an email field, card details, cardholder name, country or region, and an option to save payment details. The selected country was Sweden. This historical price is not a statement of current subscription pricing. The original screenshot remains in Git history.

---

## ✅ Successful Payment

Example of a completed payment using Stripe's official test environment.

![Payment Successful](readme-img-validation/payment-successful.jpg)

---

## 📧 User Registration

New users can create an account using the integrated registration system.

![Email Registration](readme-img-validation/email-register.jpg)

---

## 🔐 Password Recovery

Forgotten passwords can be securely reset through the email-based recovery process.

![Password Reset](readme-img-validation/email-reset-password.jpg)

---

## 📨 Email Notifications

Important account events automatically generate email notifications for the user.

![Email Notification](readme-img-validation/email-notification.jpg)

---

## ⚠️ Form Validation

Built-in validation provides clear and user-friendly feedback whenever incorrect or incomplete information is submitted.

![Login Validation](readme-img-validation/login-error.jpg)

---

# 🔄 System Workflows

The following diagrams illustrate the internal architecture of the AI Assistant Platform, showing how data flows through the application and how the different components interact.

---

## 🔁 CRUD Workflow

This diagram illustrates the complete lifecycle of an AI assistant, from creation and management to updating and deletion. It demonstrates how users interact with the application through Django views and how data is stored using the Django ORM.

**Workflow**

- User creates an AI assistant
- Data is validated
- Bot information is stored in the database
- Users can view, edit or delete existing assistants
- Changes are immediately reflected throughout the application

![CRUD Workflow](readme-img-validation/crud.jpg)

---

## 💬 AJAX Chat Flow

The AI Playground uses asynchronous AJAX requests to provide real-time conversations without requiring page reloads.

Each user message is processed by Django before being forwarded to the OpenAI API. The generated response is then returned to the browser and displayed instantly.

**Workflow**

1. User submits a message
2. JavaScript sends an AJAX request
3. Django validates the request
4. OpenAI generates a response
5. The response is returned to Django
6. JavaScript updates the conversation without refreshing the page

![AJAX Chat Flow](readme-img-validation/ajax-chat-Flow-diagram.jpg)

---

## 📚 Knowledge Base Processing

Uploaded knowledge files are automatically processed before becoming available to AI assistants.

The processing pipeline converts raw text into searchable knowledge chunks, enabling semantic retrieval and more accurate AI responses.

**Workflow**

1. User uploads a TXT file
2. The file is processed
3. Text is divided into smaller chunks
4. Embeddings are generated
5. Knowledge is stored in PostgreSQL
6. Relevant information is retrieved during AI conversations

![Knowledge Base Processing](readme-img-validation/knowledge-upload-flow-diagram.jpg)

---

## 🗄️ Database Entity Relationship Diagram (ERD)

The Entity Relationship Diagram illustrates how the application's database models are connected.

The platform is built using Django ORM with PostgreSQL in production, allowing relationships between users, AI assistants, conversations, uploaded knowledge, and subscription data.

### Main Relationships

- Users own multiple AI assistants
- AI assistants contain conversation history
- AI assistants can have multiple knowledge files
- Knowledge files are divided into searchable chunks
- AI assistants generate usage statistics
- Users have subscription information and premium status

![Database ERD](readme-img-validation/erd.jpg)

---

# ✅ Validation

The AI Assistant Platform has been tested throughout development to ensure code quality, accessibility, responsiveness, and compliance with modern web standards.

The following validation tools were used during development.

---

## 🧪 Automated Backend Testing

The backend includes an automated regression suite covering AI chat behaviour, category enforcement, knowledge processing, conversation isolation, API security, usage accounting, Redis-backed rate limiting, and Stripe subscription handling.

The latest verified backend test run was completed on **9 September 2026**:

```text
Found 53 test(s).
Ran 53 tests

OK
```

All **53 explicitly targeted backend tests passed**.

Additional verification completed at the same development checkpoint:

- Django system check: **no issues**
- Migration consistency check: **no changes detected**
- `git diff --check`: **no whitespace errors**

The test suite intentionally exercises failure paths, so warning and error log messages may appear during successful negative-path tests.

---

## 🌐 HTML Validation

HTML pages were validated using the official W3C HTML Validator to ensure semantic structure and standards compliance.

### Validation Goals

- Semantic HTML5
- No critical validation errors
- Accessible document structure
- Standards-compliant markup

![HTML Validation](readme-img-validation/home-valid-html.jpg)

---

## 🎨 CSS Validation

Stylesheets were validated using the W3C CSS Validator to verify syntax correctness and CSS standards compliance.

### Validation Goals

- Valid CSS3
- No critical errors
- Consistent styling
- Cross-browser compatibility

**Historical screenshot, described in English:** The historical W3C CSS validation result reported: "Congratulations! No errors found." It identified the submitted document as CSS Level 3 + SVG and provided validation badges and embedding instructions. This describes the retained historical result; it is not a new validation run. The original screenshot remains in Git history.

---

## 🚀 Lighthouse Audit

Google Lighthouse was used to evaluate the application's overall quality and user experience.

The audit focuses on several important areas of modern web development.

### Areas Tested

- Performance
- Accessibility
- Best Practices
- Search Engine Optimization (SEO)

The application achieved high Lighthouse scores while maintaining responsive layouts and a modern user experience.

![Lighthouse](readme-img-validation/lighthouse.jpg)

---

## 📱 Responsive Testing

The user interface was tested across multiple screen sizes to ensure a consistent experience on different devices.

### Devices Tested

- Desktop
- Laptop
- Tablet
- Mobile

The responsive layout adapts automatically using CSS media queries and flexible layouts.

---

## 🔒 Functional Testing

The platform has been manually tested throughout development alongside the automated backend regression suite.

### Features Tested

- User registration
- Login and logout
- Password reset
- AI assistant creation
- Assistant editing and deletion
- AI Playground conversations
- Conversation creation and management
- Category and domain enforcement
- Knowledge Base uploads
- Knowledge retrieval and fallback behaviour
- AI usage and cost tracking
- Free, Premium, and Pro plan restrictions
- REST API authentication and validation
- API conversation ownership protection
- Rate limiting
- Discord integration
- Stripe development workflow
- Dashboard functionality
- Responsive navigation

Stripe remains in **Test Mode**. Final hosted Stripe acceptance testing, production Redis connectivity validation, hosted deployment verification, and final security review remain release tasks.

---

## ✅ Validation Summary

The current backend development checkpoint passed all **53 explicitly targeted automated tests**. Django reported **no system-check issues**, the migration consistency check reported **no changes detected**, and `git diff --check` completed without whitespace errors.

HTML, CSS, responsive behaviour, Lighthouse performance, and major application workflows have also been tested during development.

These results provide a verified development checkpoint but do not by themselves certify the application as production-ready. Final hosted infrastructure, payment, security, Redis, and deployment validation is still required.

---

# 🛠️ Technology Stack

The AI Assistant Platform uses a Django-based backend with OpenAI services, subscription infrastructure, Redis-backed caching and rate limiting, PostgreSQL support, and a responsive JavaScript frontend.

---

## 🖥️ Backend

| Technology | Purpose |
| --- | --- |
| Python 3.13 | Core programming language |
| Django 5.2.3 | Web framework |
| Django REST Framework 3.16.0 | REST API development |
| Gunicorn 21.2.0 | Production WSGI server |
| WhiteNoise 6.9.0 | Static file serving |
| PostgreSQL | Hosted database architecture |
| SQLite | Local and isolated test database support |
| Django ORM | Database abstraction and transactional data access |

---

## 🎨 Frontend

| Technology | Purpose |
| --- | --- |
| HTML5 | Application structure |
| CSS3 | Styling and responsive layouts |
| JavaScript (ES6) | Client-side functionality |
| AJAX | Asynchronous web chat and interface actions |

---

## 🤖 Artificial Intelligence

| Technology | Purpose |
| --- | --- |
| OpenAI `gpt-4o-mini` | AI conversations and domain classification |
| OpenAI `text-embedding-3-small` | Semantic knowledge embeddings |
| Retrieval-Augmented Generation (RAG) | Assistant-specific knowledge retrieval |
| Embedding batching | Efficient knowledge processing |
| Semantic similarity search | Relevant knowledge selection |
| Prompt engineering | Assistant behaviour and category enforcement |
| Usage accounting | Token and estimated AI cost tracking |

The project currently uses the OpenAI Python package version `0.28.0` and therefore retains the compatible API integration used by the existing backend.

---

## ⚡ Cache & Rate Limiting

| Technology | Purpose |
| --- | --- |
| Redis 8.1.0 | Production cache and rate-limit data store |
| django-redis 7.0.0 | Django Redis cache backend |
| Django LocMemCache | Local development fallback |
| Plan-aware rate limiting | Free, Premium, and Pro request protection |

Production settings require the Redis-backed cache architecture rather than silently relying on per-process local memory. Final hosted Redis connectivity validation remains a release task.

---

## 💳 Payment Processing

| Technology | Purpose |
| --- | --- |
| Stripe 12.2.0 | Subscription provider integration |
| Stripe Checkout | Subscription checkout flow |
| Stripe Webhooks | Signed subscription event processing |
| Stripe Test Mode | Payment development and release validation |

The application remains restricted to **Stripe Test Mode** at the current development stage. Stripe Live Mode has not been enabled.

---

## 🤖 Discord Integration

| Technology | Purpose |
| --- | --- |
| discord.py | Discord bot communication |
| Discord Developer Portal | User-owned bot configuration |
| Bring Your Own Bot (BYOB) | External assistant deployment through user-owned Discord bots |

---

## 🗄️ Database

| Technology | Purpose |
| --- | --- |
| PostgreSQL | Hosted relational database architecture |
| SQLite | Local development and test support |
| Django ORM | Relational data access |
| Database transactions | Atomic knowledge and subscription operations |

---

## ☁️ Cloud & Deployment

| Technology | Purpose |
| --- | --- |
| Heroku | Existing cloud deployment platform |
| PostgreSQL | Hosted relational database |
| Redis-compatible service | Production cache architecture |
| Git | Version control |
| GitHub | Source code hosting |

The hosted environment is intentionally not being updated during the current backend validation phase. Final deployment verification will be completed before release.

---

## 🧪 Development & Validation Tools

| Tool | Purpose |
| --- | --- |
| Visual Studio Code | Development environment |
| Git | Version control and diff validation |
| Heroku CLI | Hosted application management |
| Django Test Framework | Automated backend regression testing |
| Django System Checks | Configuration validation |
| Django Migration Checks | Model and migration consistency validation |
| Postman | API testing |
| Ruff | Python development tooling |
| W3C HTML Validator | HTML validation |
| W3C CSS Validator | CSS validation |
| Lighthouse | Performance and accessibility auditing |

---

# 📦 Python Packages

The project uses a focused set of Python packages for the web framework, AI integration, payments, caching, deployment, database access, Discord integration, file processing, and development tooling.

## Core Packages

| Package | Version | Purpose |
| --- | ---: | --- |
| Django | 5.2.3 | Core web framework |
| djangorestframework | 3.16.0 | REST API development |
| openai | 0.28.0 | AI chat and embedding requests |
| stripe | 12.2.0 | Subscription and webhook integration |
| django-redis | 7.0.0 | Redis cache backend for Django |
| redis | 8.1.0 | Redis client |
| django-extensions | 4.1 | Development utilities |
| gunicorn | 21.2.0 | WSGI server |
| whitenoise | 6.9.0 | Static file serving |
| psycopg2-binary | 2.9.10 | PostgreSQL database adapter |
| dj-database-url | 2.3.0 | Database URL configuration |
| python-decouple | 3.8 | Environment-based configuration |
| discord.py | Managed by `requirements.txt` | Discord integration |
| Pillow | 11.2.1 | Image processing |
| PyMuPDF | 1.26.1 | PDF processing support |
| python-docx | 1.2.0 | DOCX document processing |
| numpy | 2.3.1 | Vector and numerical operations |
| requests | 2.32.3 | HTTP requests |
| ruff | 0.11.0 | Python code-quality tooling |

## Package Notes

The application currently uses `openai==0.28.0`. The existing backend therefore uses the API syntax compatible with that package version rather than the newer OpenAI client interface.

`django-redis` and `redis` provide the production cache and rate-limiting architecture, while local development can use the configured local-memory fallback.

Secrets and service credentials are supplied through environment configuration. A local `.env` file is not required by the documented development workflow.

The complete dependency list, including transitive and supporting packages, is maintained in `requirements.txt`.

---

# 📂 Project Structure

The project is organized using Django's multi-app architecture. Each application is responsible for a specific area of functionality, making the codebase modular, maintainable, and easy to extend.

```text
ai-assistant/
│
├── accounts/                          # Authentication, profiles, plans and API access
│   ├── management/
│   │   └── commands/
│   │       └── rotate_public_api_key.py
│   ├── migrations/
│   ├── templates/
│   ├── admin.py
│   ├── api_views.py
│   ├── forms.py
│   ├── models.py
│   ├── plan_utils.py
│   ├── signals.py
│   ├── tests.py
│   ├── tokens.py
│   ├── urls.py
│   ├── utils.py
│   └── views.py
│
├── bots/                              # AI assistants, chat, RAG and public API
│   ├── migrations/
│   ├── templates/
│   ├── api_views.py
│   ├── apps.py
│   ├── chat_service.py                # Shared AI chat service
│   ├── checks.py                      # Production configuration checks
│   ├── discord_download.py
│   ├── forms.py
│   ├── knowledge_utils.py             # Embeddings and semantic retrieval
│   ├── models.py
│   ├── openai_client.py
│   ├── request_validation.py          # Public API request validation
│   ├── serializers.py
│   ├── test_local_completion.py
│   ├── test_quality.py
│   ├── test_redis.py
│   ├── tests.py
│   ├── urls.py
│   ├── utils.py
│   └── views.py
│
├── buildabot/                         # Django project configuration
│   ├── cache_config.py                # Redis/cache configuration
│   ├── settings.py
│   ├── test_settings.py               # Isolated automated-test settings
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── dashboard/                         # Analytics and AI usage accounting
│   ├── migrations/
│   ├── templates/
│   ├── cost_utils.py                  # AI cost calculations
│   ├── models.py
│   ├── tests.py
│   ├── urls.py
│   └── views.py
│
├── payments/                          # Stripe subscription infrastructure
│   ├── migrations/
│   │   └── 0001_initial.py            # Stripe event idempotency model
│   ├── templates/
│   ├── models.py
│   ├── tests.py
│   ├── urls.py
│   ├── views.py
│   └── webhooks.py
│
├── static/                            # Global static assets
│   ├── css/
│   ├── discord_bridge/
│   ├── images/
│   ├── js/
│   └── pdf/
│
├── templates/                         # Shared application templates
│   ├── bots/
│   ├── dashboard/
│   └── payments/
│
├── media/                             # User-uploaded files
│
├── requirements.txt                   # Python dependencies
├── manage.py                          # Django management entry point
├── Procfile                           # Heroku process configuration
├── runtime.txt                        # Runtime configuration
├── .gitignore
├── .python-version
└── README.md
```

---

## 📦 Application Overview

### 👤 Accounts

The `accounts` application manages authentication, user profiles, account plans, Stripe account references, and public API access.

**Responsibilities**

- User registration and authentication
- Login, logout, and password reset
- Account activation and email workflows
- User profile management
- Free, Premium, and Pro plan state
- Stripe customer and subscription references
- Public API key authentication
- Secure API key rotation
- Account-level plan utilities

---

### 🤖 Bots

The `bots` application contains the core AI functionality of the platform and provides the shared chat architecture used by the web interface, APIs, and future clients.

**Responsibilities**

- AI assistant CRUD
- Shared AI chat service
- Conversation management
- Conversation history and titles
- Category and domain enforcement
- OpenAI chat integration
- Knowledge Base uploads
- Embedding generation and batching
- Semantic knowledge retrieval
- Retrieval-augmented generation (RAG)
- Usage-limit enforcement
- Redis-backed rate limiting
- Public REST API endpoints
- API request validation
- Discord integration
- AI quality and regression testing

---

### 📊 Dashboard

The `dashboard` application provides usage analytics and records the AI activity required for cost and token accounting.

**Responsibilities**

- User dashboard
- AI usage logging
- Input and output token tracking
- Model tracking
- AI cost calculations
- Monthly usage calculations
- Analytics and usage statistics
- CSV exports

---

### 💳 Payments

The `payments` application contains the Stripe subscription infrastructure for the web platform.

**Responsibilities**

- Stripe Checkout
- Premium and Pro subscription plans
- Subscription state synchronization
- Signed webhook processing
- Webhook event idempotency
- Subscription ownership validation
- Upgrade, downgrade, cancellation, and recovery handling
- Test Mode payment workflows

Stripe remains in **Test Mode** while development and validation continue. Final hosted payment validation is still required before enabling real payments.

---

### ⚙️ Buildabot

The `buildabot` package contains the central Django project configuration and infrastructure settings.

**Responsibilities**

- Django project settings
- URL routing
- WSGI and ASGI configuration
- Redis cache configuration
- Local cache fallback
- Environment-based service configuration
- Isolated automated-test settings
- Production configuration checks

---

## 🎯 Why This Structure?

The project follows a modular architecture where every Django application has a single responsibility.

This approach provides several advantages:

- Better code organization
- Easier maintenance
- Improved scalability
- Simpler testing
- Reusable components
- Clear separation of concerns

---

# 🏗️ Architecture

The AI Assistant Platform follows Django's **Model–View–Template (MVT)** architecture and is divided into focused applications for accounts, AI assistants, analytics, payments, and infrastructure.

The backend is designed so the web interface, public API, and future Android client can share the same core AI and account logic.

---

## 🧩 High-Level Architecture

```text
                          Clients
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         Web Interface    Public API    Future Android App
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                      Django Backend
                             │
          ┌──────────────────┼──────────────────┐
          ▼                  ▼                  ▼
      Accounts App        Bots App        Payments App
          │                  │                  │
          │                  ▼                  ▼
          │           Shared Chat Service    Stripe API
          │                  │
          │        ┌─────────┼─────────┐
          │        ▼         ▼         ▼
          │     OpenAI    Knowledge   Redis
          │        │       Retrieval   Cache
          │        │          │         │
          └────────┴──────────┴─────────┘
                             │
                             ▼
                       Django ORM
                             │
                             ▼
                         Database
                             │
                             ▼
                    Dashboard & Analytics
```

---

## 🧱 Application Architecture

The project is divided into multiple Django applications, each responsible for a specific area of the platform.

### 👤 Accounts

The `accounts` application manages authentication, user profiles, plan state, and public API access.

**Responsibilities**

- User registration
- Login and logout
- Password reset
- Account activation
- User profiles
- Free, Premium, and Pro account plans
- Stripe customer and subscription references
- Public API key authentication
- Secure API key rotation

---

### 🤖 Bots

The `bots` application contains the main AI functionality.

**Responsibilities**

- AI assistant CRUD
- Shared AI chat service
- Conversation management
- Category and domain enforcement
- OpenAI chat requests
- Knowledge Base uploads
- Embedding generation and batching
- Semantic knowledge retrieval
- Retrieval-augmented generation
- Usage-limit enforcement
- Redis-backed rate limiting
- Public API endpoints
- Request validation
- Discord integration
- AI quality regression tests

The shared chat service centralizes the main AI workflow so different clients can reuse the same rules, usage accounting, retrieval logic, conversation handling, and safety controls.

---

### 📊 Dashboard

The `dashboard` application records and reports AI activity.

**Responsibilities**

- AI usage logging
- Input and output token tracking
- Model tracking
- AI cost calculations
- Monthly usage calculations
- Analytics
- Usage statistics
- CSV exports

---

### 💳 Payments

The `payments` application contains the Stripe subscription infrastructure used by the web platform.

**Responsibilities**

- Stripe Checkout
- Premium and Pro plans
- Signed webhook processing
- Subscription synchronization
- Webhook event idempotency
- Subscription ownership validation
- Upgrade and downgrade handling
- Cancellation and recovery handling
- Test Mode subscription workflows

Stripe is currently used in **Test Mode**. Final hosted payment validation remains a release task before real payments are enabled.

---

### ⚙️ Buildabot

The `buildabot` package contains the central Django project and infrastructure configuration.

**Responsibilities**

- Django settings
- URL routing
- WSGI and ASGI configuration
- Redis cache configuration
- Local cache fallback
- Test settings
- Environment-based configuration
- Production configuration checks

---

## 🗄️ Data Model

The platform uses Django ORM to manage relationships between users, assistants, conversations, knowledge, usage records, subscriptions, and processed Stripe events.

### Core Relationships

- One user can own multiple AI assistants.
- Each assistant belongs to one user.
- A user can create multiple conversations with an assistant.
- Messages can belong to a specific conversation.
- Each assistant can have multiple uploaded knowledge sources.
- Knowledge sources are split into searchable chunks.
- Knowledge chunks store embedding vectors for semantic retrieval.
- AI usage logs record model and token information.
- User profiles store account-plan and subscription state.
- Processed Stripe event identifiers are stored to support webhook idempotency.

The application supports local development and automated testing with SQLite. The hosted architecture is designed for PostgreSQL.

---

## 🧠 AI Request Lifecycle

A typical in-domain chat request follows the shared backend workflow below.

```text
User Message
     │
     ▼
Authentication / API Key Validation
     │
     ▼
Plan Usage Check
     │
     ▼
Rate Limit Check
     │
     ▼
Category / Domain Check
     │
     ├── Out of Domain
     │        │
     │        ▼
     │   Safe Rejection
     │
     ▼
Knowledge Retrieval
     │
     ├── No Relevant Knowledge
     │        │
     │        ▼
     │   Continue Without Context
     │
     ▼
Conversation History
     │
     ▼
OpenAI Chat Request
     │
     ▼
Usage & Cost Logging
     │
     ▼
Save Conversation Messages
     │
     ▼
Response
```

The service is designed to continue safely if knowledge retrieval fails, while still preventing unrestricted cross-domain behavior for specialized assistants.

---

## 📚 Knowledge Retrieval Flow

Uploaded knowledge is processed before it becomes available to an assistant.

```text
Uploaded Knowledge
       │
       ▼
Text Processing
       │
       ▼
Chunk Generation
       │
       ▼
Batched Embedding Requests
       │
       ▼
Embedding Validation
       │
       ▼
Atomic Database Save
       │
       ▼
Semantic Similarity Search
       │
       ▼
Relevant Knowledge Context
       │
       ▼
AI Response
```

Embedding responses are validated before persistence, and database writes are handled atomically so incomplete uploads do not leave partially saved knowledge behind.

---

## 🚦 Usage & Rate-Limit Architecture

AI access is controlled at multiple levels.

```text
Request
   │
   ▼
Account Plan
   │
   ├── Daily Message Limit
   ├── Monthly Cost Safety Limit
   └── Requests Per Minute
              │
              ▼
             Redis
              │
              ▼
         Chat Allowed
```

Current plan-aware request rates are:

| Plan | Requests per Minute |
| --- | ---: |
| Free | 20 |
| Premium | 60 |
| Pro | 120 |

Redis is used for the production rate-limiting architecture. Local development can fall back to Django's local-memory cache.

Final hosted Redis connectivity validation remains pending.

---

## 💳 Subscription Event Flow

Stripe subscription state is synchronized through signed webhook events.

```text
Stripe
  │
  ▼
Signed Webhook Event
  │
  ▼
Signature Validation
  │
  ▼
Mode & Event Validation
  │
  ▼
Retrieve Current Subscription State
  │
  ▼
Validate Customer / Owner / Price
  │
  ▼
Database Transaction
  │
  ├── Update User Plan
  └── Record Processed Event ID
  │
  ▼
Webhook Response
```

The webhook implementation includes idempotency, ownership checks, price validation, stale-event reconciliation, and retryable provider failures.

---

## 🔌 External Services

| Service | Purpose |
| --- | --- |
| OpenAI API | AI chat and embedding generation |
| Stripe API | Subscription infrastructure in Test Mode |
| Discord API | Discord assistant integration |
| Redis | Cache and rate-limiting architecture |
| PostgreSQL | Hosted database architecture |
| Heroku | Existing cloud deployment platform |

The current hosted environment has intentionally not been updated during the latest backend validation work. Final deployment validation remains pending.

---

## 🎯 Architectural Principles

### Separation of Concerns

Each Django application has a focused responsibility, reducing coupling between authentication, AI logic, payments, analytics, and infrastructure.

### Shared Business Logic

Core AI behavior is centralized in the shared chat service instead of being duplicated across the web interface and APIs.

### Domain Control

Specialized assistants are restricted to their configured categories so they remain focused on their intended subject areas.

### Resilience

Knowledge retrieval failures can degrade gracefully without stopping the complete chat request, while database and payment operations use defensive validation and transactional handling.

### Usage Control

Daily limits, monthly cost safety limits, and request-rate controls help protect the platform against excessive AI usage.

### Security

Authentication, API-key validation, ownership checks, CSRF protection, webhook signatures, environment-based secrets, and production configuration checks are integrated across the platform.

### Maintainability

Reusable services, isolated configuration, automated regression tests, and Django's modular application structure make the project easier to extend and maintain.

### Future Client Support

The shared backend architecture is designed to support additional clients, including the planned Android application, without duplicating the core AI workflow.

---

# 🛣️ Roadmap

The AI Assistant Platform is under active development. The core backend architecture is substantially implemented and covered by automated regression tests, while production infrastructure, payment validation, mobile development, and final release work remain ongoing.

## Completed ✅

### Core Platform

- User registration and authentication
- Account activation and password reset
- AI assistant CRUD
- Free, Premium, and Pro account plans
- Plan-aware assistant limits
- Responsive web interface
- Dark and light themes
- Dashboard and analytics
- CSV exports
- Discord Bridge and Discord integration

### AI Backend

- OpenAI-powered AI chat
- Shared chat service for web and API clients
- Specialized assistant categories
- Category and domain enforcement
- Conversation creation and management
- Conversation-specific history
- Conversation rename and delete functionality
- Knowledge Base uploads
- Knowledge chunking
- Batched embedding generation
- Embedding response validation
- Semantic knowledge retrieval
- Retrieval-augmented generation (RAG)
- Graceful fallback when knowledge retrieval fails
- Atomic knowledge persistence
- Input and output token tracking
- AI model tracking
- AI usage cost calculation
- Daily plan usage limits
- Monthly AI cost safety limits

### API & Security

- REST API
- Public API-key authentication
- API request-shape validation
- Conversation ownership validation
- Secure API-key rotation command
- API-key protection in Django Admin
- Redis-backed rate-limiting architecture
- Production cache configuration checks

### Subscription Backend

- Stripe Checkout integration
- Premium subscription plan
- Pro subscription plan
- Signed Stripe webhook processing
- Subscription state synchronization
- Upgrade and downgrade handling
- Cancellation and subscription recovery handling
- Webhook event idempotency
- Customer and subscription ownership validation
- Price and subscription validation
- Stale-event reconciliation
- Stripe Test Mode backend coverage

### Testing & Quality

- Automated AI chat regression tests
- Category-enforcement tests
- Knowledge retrieval tests
- Conversation isolation tests
- API security tests
- Usage and cost-accounting tests
- Redis and rate-limit tests
- Stripe subscription and webhook tests
- 53 targeted backend tests passing at the latest documented validation checkpoint

---

## In Progress 🚧

- Final backend cleanup and documentation
- README synchronization with the current codebase
- Improved analytics and customer-facing usage reporting
- Customer-facing subscription management
- Hosted Stripe Test Mode validation
- Production Redis connectivity validation
- Final hosted deployment validation
- Production security review

The existing hosted deployment is intentionally not being updated during the current backend validation phase.

---

## Planned 📌

### Android & Mobile

- Native Android application
- Shared Django backend for web and Android clients
- Google Play Billing integration
- Backend entitlement synchronization for Android subscriptions
- Google Play AI-content reporting and safety requirements
- Final Google Play release preparation

### Platform Features

- AI image generation
- Voice conversations
- Speech-to-text
- Text-to-speech
- AI document analysis
- Additional AI models
- Team workspaces
- Shared assistants
- Public assistant marketplace
- API documentation
- Usage notifications
- Expanded billing dashboard
- Assistant version history
- Two-factor authentication
- OAuth login
- Multi-language interface
- Custom domains

### Infrastructure

- Production Redis validation and monitoring
- Final PostgreSQL deployment validation
- Deployment monitoring
- Expanded automated integration testing
- Docker support
- Additional deployment options where appropriate

---

## Long-Term Vision 🚀

The long-term goal is to develop the AI Assistant Platform into a commercially viable multi-client AI service where individuals and businesses can create, customize, equip with their own knowledge, and manage specialized AI assistants.

The web platform and planned Android application are designed to share the same Django backend, account system, assistant data, conversations, knowledge retrieval, usage controls, and AI infrastructure.

Future expansion can extend the same platform architecture to additional integrations and client applications without duplicating the core AI business logic.

---

# ⭐ Why This Project?

Many AI projects stop at a basic chatbot interface. The AI Assistant Platform was designed as a broader SaaS-style system where users can create, customize, equip, and manage specialized AI assistants from one platform.

Instead of treating every assistant as a general-purpose chatbot, the platform combines category-aware AI behavior, custom knowledge retrieval, conversation management, usage controls, subscriptions, APIs, analytics, and external integrations behind a shared Django backend.

## What Makes This Project Different?

- 🤖 Specialized AI assistants powered by OpenAI
- 🎯 Category and domain enforcement to keep assistants focused
- 📚 Custom Knowledge Base with embedding-based semantic retrieval
- 🧠 Retrieval-augmented generation (RAG)
- 💬 Persistent, separate conversations with managed history
- 🔄 Shared AI chat service used across different client interfaces
- 📊 Token, model, usage, and AI cost accounting
- 🚦 Plan-aware message limits and rate limiting
- 🔐 Public API-key authentication and ownership validation
- 💳 Free, Premium, and Pro account architecture
- 💳 Stripe subscription infrastructure with signed and idempotent webhooks
- 🎮 Discord integration using a Bring Your Own Bot (BYOB) approach
- 📈 Analytics and usage reporting
- 🌙 Dark and Light themes
- 📱 Responsive web interface
- 🧩 Modular Django architecture designed for additional clients
- 📲 Planned Android application using the same backend and account data

## Main Goals

The project was created to demonstrate full-stack software engineering while developing a platform that can evolve into a real commercial product.

Key goals include:

- Building a maintainable and extensible Django backend
- Creating useful specialized AI assistants instead of unrestricted generic chatbots
- Integrating OpenAI chat and embedding services
- Implementing reliable knowledge retrieval
- Managing persistent conversations and assistant-specific context
- Tracking AI usage and operating cost
- Protecting AI resources with plan limits and rate limiting
- Designing secure authentication and public API access
- Implementing subscription infrastructure and entitlement handling
- Integrating multiple external services without duplicating core business logic
- Building a backend that can support both web and mobile clients
- Maintaining automated regression coverage as the platform grows
- Preparing the application for final production validation and commercial release

## Target Users

The platform is designed for users who need focused AI assistants without building the complete AI infrastructure themselves.

Potential users include:

- Developers
- Small businesses
- Discord communities
- Content creators
- Technical and specialist communities
- Teams that need assistants grounded in their own knowledge
- Individuals who want to create and manage specialized AI assistants

The long-term product direction is to make the same assistants, conversations, knowledge, account plans, and backend services accessible across the web platform and future Android application.

---

# ⚡ Challenges & Lessons Learned

Building the AI Assistant Platform involved solving engineering problems across AI integration, data consistency, security, subscriptions, caching, usage accounting, external services, and deployment.

As the project developed from a web-based AI assistant builder into a broader SaaS-style platform, several features required redesigning earlier implementations rather than simply adding new code.

## Major Challenges

### 🧠 Building a Shared AI Chat Architecture

An important challenge was preventing AI behavior from becoming duplicated across the web interface and public API.

The chat workflow was centralized into a shared service responsible for:

- Account-plan checks
- Rate-limit enforcement
- Category and domain validation
- Knowledge retrieval
- Conversation history
- OpenAI requests
- Usage accounting
- Message persistence
- Consistent error handling

This creates a single backend workflow that can also support future clients such as the planned Android application.

---

### 🎯 Keeping Specialized Assistants in Their Domain

Allowing every assistant to answer every question would reduce the value of having specialized assistants.

Category-aware domain enforcement was therefore introduced so assistants can reject unrelated requests while continuing to answer questions within their configured subject area.

This required balancing:

- Strict domain boundaries
- Useful assistant behavior
- False rejection risk
- Additional classifier cost
- Consistent behavior across web and API clients

General-purpose categories can bypass unnecessary classification, avoiding additional AI requests where domain enforcement is not required.

---

### 📚 Reliable Knowledge Retrieval

The Knowledge Base evolved beyond simply storing uploaded text.

The retrieval pipeline required:

- Text processing
- Chunk generation
- Batched embedding requests
- Embedding response validation
- Correct embedding ordering
- Semantic similarity comparison
- Assistant-level knowledge isolation
- Retrieval fallback behavior
- Usage accounting for embedding requests

A particularly important lesson was that external API success does not automatically mean the returned data is safe to persist.

Embedding responses are therefore validated before database writes are completed.

---

### 🔒 Atomic Knowledge Uploads

Knowledge uploads involve both external AI requests and local database operations.

A failure after only part of an upload had been saved could leave incomplete knowledge records or uploaded files behind.

The upload workflow was redesigned so:

- Embeddings are completed before knowledge is committed
- Parent records and chunks are saved atomically
- Invalid or empty embedding results fail explicitly
- Failed database operations clean up uploaded files
- Completed external API usage is still accounted for

This improved both data integrity and cost accounting.

---

### 💬 Conversation Isolation

Persistent chat required more than simply storing messages against an assistant.

Separate conversations were introduced so users can:

- Start new conversations
- Switch between existing conversations
- Rename conversations
- Delete conversations
- Keep history isolated between conversations

Ownership validation is also required so one user cannot access another user's conversations through the API.

---

### 📊 AI Usage and Cost Accounting

AI usage has a direct operating cost, so token tracking became an important backend requirement.

The platform records:

- Input tokens
- Output tokens
- Total token usage
- Model information
- Billable AI requests
- Estimated AI cost

This required handling both chat and embedding usage while keeping historical records compatible with newer accounting logic.

The resulting data is also used for plan-level cost controls and future business analysis.

---

### 🚦 Rate Limiting and Redis

Rate limiting must work consistently when the application runs across production processes.

A local-memory cache is useful during development, but it is not sufficient as a production-wide rate limiter.

The Redis configuration therefore required:

- Redis URL validation
- Secure `redis` and `rediss` handling
- Connection timeouts
- Explicit failure behavior
- Production configuration checks
- Local development fallback
- Rate-limit race-condition testing

The Redis architecture and automated tests are implemented, while final hosted Redis connectivity validation remains pending.

---

### 💳 Stripe Subscription State

Subscription handling became significantly more complex than creating a Stripe Checkout Session.

The backend needed to correctly handle:

- Premium and Pro plans
- Checkout completion
- Subscription upgrades
- Subscription downgrades
- Scheduled cancellation
- Immediate cancellation
- Subscription recovery
- Duplicate webhook delivery
- Stale webhook events
- Customer ownership
- Subscription ownership
- Price validation
- Provider failures

Signed webhook events are validated and processed transactionally, while processed event identifiers provide idempotency.

Stripe remains in **Test Mode**, and final hosted payment validation is still required before real payments are enabled.

---

### 🔐 Public API Security

Providing API access introduced a different security boundary from normal browser authentication.

The public API required:

- API-key authentication
- Active-user validation
- Strict request-shape validation
- Safe identifier handling
- Conversation ownership checks
- Secure API-key rotation
- Protection against accidental key exposure in Django Admin

One important lesson was that secrets should not only be protected in source code; they also need to be protected from logs, administrative interfaces, debugging output, and error responses.

---

### 🎮 Discord Integration

Instead of requiring every user to share one central Discord bot, the project uses a Bring Your Own Bot (BYOB) approach.

This required connecting:

```text
Discord
   │
   ▼
Discord Bridge
   │
   ▼
Django API
   │
   ▼
Shared AI Backend
```

The approach keeps the main AI logic inside Django while allowing users to connect their own Discord bots.

---

### ☁️ Deployment and Environment Differences

Local development and hosted deployment introduced different infrastructure requirements.

Areas that required particular attention included:

- Static file handling
- Database configuration
- Environment variables
- Secret management
- HTTPS behavior
- Debug versus production settings
- Cache configuration
- Hosted service configuration

The existing Heroku deployment is being kept separate from the current backend validation work so unfinished infrastructure changes are not introduced into the hosted application prematurely.

---

## Lessons Learned

Working on this project significantly improved my understanding of:

- Django application architecture
- Service-layer design
- REST API design
- Authentication and authorization
- API-key security
- AI prompt engineering
- Category-aware AI behavior
- Retrieval-augmented generation
- Embeddings and semantic retrieval
- Conversation architecture
- Transactional database operations
- AI token and cost accounting
- Redis caching and rate limiting
- Stripe subscription lifecycle management
- Webhook security and idempotency
- External API failure handling
- Automated regression testing
- Environment and secret management
- Cloud deployment
- Maintaining a growing multi-application codebase

---

## Biggest Takeaway

The biggest lesson from this project is that building a reliable AI product involves much more than sending prompts to an AI model.

The surrounding system must control access, protect secrets, isolate user data, validate external responses, track operating costs, recover safely from failures, manage subscriptions, and remain maintainable as new clients and features are introduced.

Automated testing also became increasingly important as the platform grew. Changes to AI behavior, payments, caching, knowledge retrieval, or API security can affect multiple parts of the application, making regression coverage essential before deployment.

The project has therefore evolved from focusing primarily on individual features to focusing on the reliability and architecture of the complete platform.

---

# 💡 Design Decisions

Throughout development, architectural and technical decisions have been made to keep the platform maintainable, secure, testable, and capable of supporting additional clients as the project grows.

---

## Django MVT

The project follows Django's Model–View–Template (MVT) architecture.

Django provides the foundation for:

- Data models
- Views and request handling
- Templates
- Authentication
- Database access
- URL routing
- Administrative tools

Business logic that is shared across multiple entry points is moved into dedicated services and utilities instead of being duplicated inside views.

---

## Multi-App Architecture

The platform is divided into focused Django applications rather than placing all functionality inside one application.

The main applications are:

- Accounts
- Bots
- Dashboard
- Payments

This provides:

- Clear separation of responsibilities
- Smaller and more focused modules
- Easier testing
- Reduced coupling
- Better maintainability
- Easier future expansion

---

## Shared Chat Service

The main AI workflow is centralized in a shared chat service instead of maintaining separate AI implementations for each interface.

The shared service coordinates:

- Plan validation
- Rate limiting
- Category enforcement
- Knowledge retrieval
- Conversation history
- OpenAI requests
- Usage accounting
- Message persistence

This allows the web interface and public API to use the same AI behavior and provides a reusable backend path for the planned Android application.

---

## Specialized Assistants

Assistants are designed around categories and intended domains rather than operating as unrestricted general-purpose chatbots.

Domain enforcement helps each specialized assistant remain focused on its configured subject.

General-purpose categories can bypass unnecessary classification, reducing additional AI requests and operating cost when strict domain enforcement is not required.

---

## Conversation-Based History

Chat history is organized into separate conversations instead of treating every message sent to an assistant as one continuous history.

This design allows users to:

- Start new conversations
- Return to previous conversations
- Rename conversations
- Delete conversations
- Keep unrelated discussions separated

Conversation ownership is enforced when conversations are accessed through the API.

---

## Retrieval-Augmented Generation

Custom assistant knowledge uses retrieval-augmented generation rather than model fine-tuning.

The Knowledge Base pipeline includes:

```text
Upload
  │
  ▼
Text Processing
  │
  ▼
Chunking
  │
  ▼
Embeddings
  │
  ▼
Semantic Retrieval
  │
  ▼
Relevant Context
  │
  ▼
AI Response
```

Only relevant knowledge is added to the AI request, helping keep prompts focused while avoiding unnecessary context.

---

## Batched and Validated Embeddings

Embedding requests are batched instead of sending every knowledge chunk as an independent request.

This reduces unnecessary API overhead while preserving the relationship between each text chunk and its embedding.

Returned embeddings are validated for:

- Response indices
- Vector values
- Finite numeric values
- Consistent dimensions
- Expected response count

The ordering is reconstructed from returned indices rather than assuming the external API response is already correctly ordered.

---

## Atomic Knowledge Persistence

Knowledge records and chunks are saved transactionally.

Embeddings are completed and validated before the final database persistence step.

If persistence fails, the operation is rolled back and associated uploaded files are cleaned up where required.

This prevents partially completed knowledge uploads from remaining in the application.

---

## Graceful Retrieval Failure

A Knowledge Base failure should not automatically make the entire AI chat unavailable.

If semantic retrieval fails unexpectedly, the shared chat service can continue without retrieved context while recording the failure safely.

This separates optional knowledge enrichment from the core ability to complete a chat request.

---

## AI Usage Accounting

AI usage is recorded because API consumption is both a technical and commercial concern.

Usage records include:

- Input tokens
- Output tokens
- Total tokens
- Model information
- Billable requests
- Estimated AI cost

Both chat and embedding activity can contribute to operating cost.

This accounting provides the foundation for analytics, plan controls, and future commercial monitoring.

---

## Plan-Aware Usage Controls

Free, Premium, and Pro accounts have different AI usage rules.

Controls are separated into:

- Daily message limits
- Monthly AI cost safety limits
- Requests-per-minute limits

The Pro plan does not have a normal daily or monthly usage cap, but it remains subject to rate limiting and abuse protection.

This design separates normal product entitlement from infrastructure protection.

---

## Redis for Shared Rate Limiting

Django's local-memory cache is suitable as a development fallback but is process-local and therefore not sufficient for reliable multi-process production rate limiting.

The hosted architecture therefore uses Redis as the shared cache layer.

The Redis configuration includes:

- URL validation
- Connection timeouts
- Explicit cache failure behavior
- Secure `rediss` handling
- Production configuration checks

Final hosted Redis connectivity validation remains pending.

---

## Database Strategy

SQLite is used for local development and automated testing.

The hosted architecture is designed to use PostgreSQL through Django ORM.

This keeps local development simple while allowing the deployed application to use a relational database suited to hosted workloads.

Final hosted infrastructure validation remains part of the release process.

---

## Stripe Checkout and Webhooks

Stripe was selected for the web subscription infrastructure.

The implementation separates Checkout from subscription entitlement synchronization.

Stripe Checkout starts the subscription process, while signed webhook events are used to reconcile subscription state with the Django account.

The webhook architecture includes:

- Signature validation
- Test and Live Mode validation
- Customer validation
- Subscription ownership validation
- Price validation
- Event idempotency
- Transactional account updates
- Stale-event reconciliation
- Retryable provider failures

Stripe remains in **Test Mode** during development. Real payments will not be enabled until final hosted payment validation is complete.

The planned Android application will use Google Play Billing rather than Stripe for Android in-app subscriptions, with backend entitlement synchronization keeping account access consistent.

---

## Public API Keys

The public API uses dedicated API keys rather than exposing normal browser authentication credentials.

API security includes:

- Active-user validation
- Request-shape validation
- Ownership checks
- Safe identifier handling
- API-key rotation
- Restricted API-key exposure in Django Admin

API keys are separate from the server-side OpenAI API credential.

---

## Environment-Based Secrets

Sensitive credentials are not intended to be stored directly in source code or committed to the repository.

Environment configuration is used for values such as:

- Django secret key
- OpenAI API key
- Stripe credentials
- Database configuration
- Redis configuration
- Email credentials

The project does not depend on a local `.env` file as part of the documented development workflow.

---

## Bring Your Own Bot (BYOB)

Discord integration follows a Bring Your Own Bot approach.

Users can connect their own Discord bot while the main AI processing remains inside the Django backend.

This provides:

- User ownership of the Discord bot
- Independent Discord configuration
- Separation between Discord and core AI logic
- Reuse of the existing backend
- Greater flexibility for different Discord communities

---

## Responsive Web Interface

The web interface is designed to adapt across:

- Desktop
- Laptop
- Tablet
- Mobile devices

Responsive layouts and CSS media queries allow the existing web client to remain usable while a dedicated Android application is developed separately.

---

## Automated Regression Testing

As the backend grew, automated regression testing became a core design requirement rather than an optional final step.

Tests cover critical areas including:

- AI chat behavior
- Category enforcement
- Knowledge retrieval
- Embedding validation
- Conversation isolation
- Usage accounting
- API security
- Rate limiting
- Redis configuration
- Stripe subscriptions and webhooks

The latest documented backend validation checkpoint contains **53 passing targeted tests**.

---

## Focus on Maintainability

Long-term maintainability influences the architecture throughout the project.

Key principles include:

- Shared business logic
- Focused Django applications
- Reusable services and utilities
- Defensive validation
- Transactional persistence
- Explicit failure handling
- Automated regression coverage
- Clear separation between local, test, and hosted configuration
- Avoiding unnecessary duplication between clients

These decisions allow the platform to continue evolving without requiring separate implementations of the core backend for every interface.

---

# 🚀 Installation

Follow the steps below to set up the AI Assistant Platform for local development.

The hosted environment has separate configuration and should not be modified as part of the local setup process.

---

## 📋 Prerequisites

Before getting started, ensure that you have:

- Python 3.13
- Git
- pip
- An OpenAI API key for AI functionality
- A Stripe account for optional Test Mode payment testing
- A Discord Developer account for optional Discord integration

SQLite can be used for local development and automated testing.

The hosted architecture is designed to use PostgreSQL and Redis, but those services are not required for the basic local development setup.

---

## 📥 Clone the Repository

Clone the repository:

```bash
git clone https://github.com/God-zil-la/ai-assistant.git
```

Navigate into the project directory:

```bash
cd ai-assistant
```

---

## 🐍 Create a Virtual Environment

### Windows PowerShell

Create the virtual environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

### macOS / Linux

Create the virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

---

## 📦 Install Dependencies

Install the project dependencies:

```bash
pip install -r requirements.txt
```

The project currently uses Django 5.2.3 and Python 3.13 for the documented local development environment.

---

## ⚙️ Configure Environment Variables

Application secrets and external-service credentials are supplied through environment variables.

The documented local workflow does **not** require a `.env` file.

At minimum, AI functionality requires:

```text
OPENAI_API_KEY
```

Other configuration values may include:

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG
DATABASE_URL
REDIS_URL
STRIPE_PUBLIC_KEY
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
```

The exact variables required depend on which integrations are being tested.

Never commit real API keys, passwords, webhook secrets, database credentials, or other private values to the repository.

### Windows PowerShell Example

Environment variables can be supplied for the current PowerShell session:

```powershell
$env:DJANGO_DEBUG="True"
$env:OPENAI_API_KEY="your-development-key"
```

Use your own development credentials locally. Do not place real credentials directly in source files.

---

## 🗄️ Local Database Setup

For a new local development database, apply the Django migrations:

```bash
python manage.py migrate
```

This command applies migrations to the database configured for the current environment.

Production or hosted migrations should be handled separately as part of a controlled deployment process.

---

## 👤 Create an Administrator Account

If an administrator account is required locally:

```bash
python manage.py createsuperuser
```

Follow the Django prompts to create the account.

---

## ▶️ Run the Development Server

Start the Django development server:

```bash
python manage.py runserver
```

The local application is normally available at:

```text
http://127.0.0.1:8000/
```

Django's development server serves HTTP by default. It should not be opened locally as an HTTPS development endpoint unless a separate HTTPS development setup has been configured.

---

## 🔑 OpenAI Configuration

AI chat and Knowledge Base embeddings require a valid OpenAI API key.

The backend currently uses:

- `gpt-4o-mini` for AI chat and domain classification
- `text-embedding-3-small` for Knowledge Base embeddings

The project currently uses `openai==0.28.0`, so the existing integration follows the API syntax supported by that package version.

Do not expose the OpenAI API key to browser or mobile clients. AI requests are handled by the Django backend.

---

## 📚 Knowledge Base

After OpenAI configuration is available, the Knowledge Base can generate embeddings for uploaded knowledge and use semantic retrieval during assistant conversations.

The current backend includes:

- Text chunking
- Batched embedding generation
- Embedding validation
- Atomic persistence
- Semantic retrieval
- Retrieval failure fallback
- Embedding usage accounting

Uploaded knowledge belongs to the configured assistant and should not be shared across unrelated assistants.

---

## 🚦 Redis Configuration

Redis is used by the hosted architecture for shared caching and AI rate limiting.

The Redis connection is configured through:

```text
REDIS_URL
```

Local development can use the configured local-memory cache fallback when Redis is not available.

The application includes production configuration checks to prevent the local-memory backend from being treated as the intended production cache.

Final hosted Redis connectivity validation remains pending.

---

## 💳 Stripe Test Mode

Stripe development must remain in **Test Mode** until final payment and deployment validation is complete.

The web subscription architecture supports:

- Premium subscriptions
- Pro subscriptions
- Stripe Checkout
- Signed webhooks
- Subscription synchronization
- Upgrade and downgrade handling
- Cancellation and recovery
- Webhook idempotency

The current subscription prices are:

| Plan | Monthly Price |
| --- | ---: |
| Premium | $12.99 USD |
| Pro | $24.99 USD |

Stripe credentials and webhook secrets must be provided through environment configuration and must never be committed to the repository.

Do not use Stripe Live Mode credentials during normal development or automated testing.

Hosted Stripe Test Mode validation remains a release task.

The planned Android application will use Google Play Billing for Android in-app subscriptions rather than Stripe.

---

## 🤖 Discord Integration

Discord integration is optional.

The project uses a Bring Your Own Bot approach where users configure their own Discord application while AI processing remains connected to the Django backend.

The included Discord Bridge resources contain:

- Bridge application
- Setup guide
- Command guide
- Discord-specific requirements
- Example configuration

General setup:

1. Create a Discord application.
2. Create and configure its bot.
3. Enable the required Gateway Intents.
4. Configure the Discord Bridge.
5. Connect it to the Django API.
6. Invite the bot to the Discord server.
7. Start the bridge.

Discord credentials and API keys must be kept private.

---

## 🧪 Run the Automated Backend Tests

The backend regression suite is split across several test modules.

Run the documented targeted suite with:

```bash
python -X utf8 manage.py test ai_assistant.bots.tests ai_assistant.bots.test_redis ai_assistant.bots.test_quality ai_assistant.bots.test_local_completion ai_assistant.accounts.tests ai_assistant.payments.tests --settings=ai_assistant.buildabot.test_settings --noinput
```

At the latest documented validation checkpoint on **9 September 2026**, this suite reported:

```text
Found 53 test(s).
Ran 53 tests

OK
```

Some tests intentionally exercise failure paths and can therefore produce warning or error log messages while the overall test suite still passes.

---

## ✅ Run Django System Checks

Run:

```bash
python -X utf8 manage.py check --settings=ai_assistant.buildabot.test_settings
```

The latest documented validation completed with:

```text
System check identified no issues (0 silenced).
```

---

## 🧬 Check Migration Consistency

Check whether model changes require additional migrations:

```bash
python -X utf8 manage.py makemigrations --check --dry-run --settings=ai_assistant.buildabot.test_settings
```

At the latest documented checkpoint:

```text
No changes detected
```

This check does not apply pending migrations to a database.

---

## 🧹 Check Git Whitespace

Before committing changes, run:

```bash
git diff --check
```

No output indicates that Git found no whitespace errors in the current diff.

---

## 📁 Static Files

Static assets are handled through Django and WhiteNoise.

For a deployment environment, static files can be collected with:

```bash
python manage.py collectstatic --noinput
```

This is normally part of the deployment workflow rather than a requirement every time the local development server is started.

---

## ✅ Local Verification Checklist

After local setup, verify the functionality relevant to the services you configured.

Core checks include:

- Register and authenticate a user
- Create and edit an AI assistant
- Start a conversation
- Create a second conversation and verify history isolation
- Test an in-domain assistant request
- Verify an unrelated request is rejected for a specialized assistant
- Upload and retrieve assistant knowledge
- Check usage and analytics data
- Verify public API authentication where required
- Run the automated backend regression suite

Optional integration checks include:

- Stripe Test Mode Checkout and webhook behavior
- Redis-backed rate limiting
- Discord Bridge integration

These optional checks require their corresponding external services and credentials.

---

## ☁️ Hosted Deployment Status

An existing Heroku deployment is maintained separately from the latest local backend work.

The current development process intentionally follows:

```text
Local Development
       │
       ▼
Automated Validation
       │
       ▼
Git / GitHub Checkpoint
       │
       ▼
Final Infrastructure Validation
       │
       ▼
Controlled Hosted Deployment
```

The latest backend changes should not be considered fully production-validated until the remaining hosted Stripe, Redis, database, security, and deployment checks have been completed.

---

# 📄 License

This project is licensed under the MIT License.

You are free to use, modify, and distribute this software in accordance with the terms of the license.

See the LICENSE file for more information.

---

# 🙏 Acknowledgements

This project would not have been possible without the excellent open-source tools and services provided by the following communities and organizations.

Special thanks to:

- Django
- OpenAI
- Stripe
- Discord
- Heroku
- PostgreSQL
- Django REST Framework
- Code Institute
- GitHub

Their documentation, tools, and communities played an important role throughout the development of this project.

---

# 👨‍💻 Author

**Hussein Elali**

Full Stack Web Developer

- GitHub: https://github.com/God-zil-la
- Portfolio: https://god-zil-la.github.io/portfolio/
- LinkedIn: https://www.linkedin.com/in/hussein-elali/

---

# ⭐ Support

If you found this project useful, consider giving it a ⭐ on GitHub.

Feedback, suggestions, and contributions are always welcome.

---

## Thank you for visiting AI Assistant Platform!


### USD subscription billing configuration

Premium costs $12.99 USD/month (1299 cents); Pro costs $24.99 USD/month
(2499 cents). Checkout and webhook plan reconciliation share the pricing
configuration in `ai_assistant/payments/pricing.py`. Only a single quantity
of a recognized USD price billed every month grants paid access.

Checkout uses inline Stripe `price_data`, so no pre-created Price IDs or new
Price ID environment variables are required. Keep the existing Test Mode
`STRIPE_SECRET_KEY`, `STRIPE_PUBLIC_KEY`, and `STRIPE_WEBHOOK_SECRET` configuration.
Do not substitute live credentials. No Stripe Dashboard changes are required
for new Test Mode checkouts.

Existing subscriptions are not converted automatically. A legacy non-USD
subscription will no longer qualify for paid access when reconciled by this
version. Existing Test Mode subscriptions must be replaced or updated to the
recognized monthly USD prices before using this version with those accounts.
This repository change does not modify any Stripe subscriptions or settings.
