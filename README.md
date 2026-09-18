# 🤖 AI Assistant Platform

> **Current platform status — September 2026:** Production web app live on `www.myaiassistantapp.se`; native Expo/React Native Android app in Google Play Closed Testing; Stripe production billing in Live Mode; iOS distribution pending Apple Developer Program activation.

> A production-focused AI SaaS platform for creating, customizing, training, managing, and integrating specialized AI assistants.

**AI Assistant Platform** is a full-stack SaaS application built with **Django**, **OpenAI**, **Stripe**, **PostgreSQL**, and Redis-compatible infrastructure. **Discord integration is planned for U5** rather than presented as a currently released customer feature.

The platform allows users to create purpose-built AI assistants, extend them with their own documents and Knowledge, maintain separate conversations, monitor AI usage, manage subscription plans, and use the supported web and native mobile clients. Customer-facing Discord integration and API Access are planned for U5.

Unlike a simple chatbot project, the application is designed as a complete multi-user AI product with account plans, usage quotas, subscription lifecycle management, Retrieval-Augmented Generation (RAG), persistent conversations, analytics, API authentication, external integrations, production security controls, automated regression testing, and cloud deployment.

The production platform now has both a web client and a native mobile client. The Expo/React Native Android application uses the same Django backend so accounts, assistants, conversations, Knowledge, quotas, analytics, and entitlement rules remain shared across clients.

---

## 🌐 Live Application

### Production Deployment

The AI Assistant Platform is deployed on Heroku and uses the production Django application stack.

**Live application:**

[https://www.myaiassistantapp.se/](https://www.myaiassistantapp.se/)

The Django application is hosted on Heroku behind the production custom domain.

The hosted environment is used throughout final release validation and is updated as completed backend changes pass automated and production-level verification.

The production web application is configured with **Stripe Live Mode**. Test Mode remains reserved for safe development and payment-flow validation and is kept separate from production credentials, Price IDs, webhooks, and Checkout configuration.

---

## 🚀 Highlights

- 🤖 Create and manage specialized AI assistants
- 🎯 Category-based assistant behaviour and domain enforcement
- 📚 Retrieval-Augmented Generation (RAG) using custom Knowledge
- 📄 Knowledge support for TXT, PDF, and DOCX documents
- 🧠 Semantic retrieval using OpenAI embeddings
- 🔍 Exact, lexical, and semantic Knowledge retrieval strategies
- 💬 Persistent and independently managed conversations
- ♾️ Unlimited stored chats across all account plans
- 🔄 Shared AI chat service used by web and API entry points
- 📊 Token usage, request usage, and estimated AI cost tracking
- 🚦 Account-wide monthly AI message quotas
- 💾 Account-wide Knowledge storage quotas
- ⚡ Plan-aware request rate limiting
- 🧩 Plan-aware assistant limits
- 🔐 Protected backend/native API authentication
- 🛡️ Ownership validation across assistants, conversations, Knowledge, and API access
- 💳 Free, Premium, and Pro subscription plans
- 🔁 Stripe upgrade, downgrade, cancellation, recovery, and webhook workflows
- 📉 Safe downgrade behaviour that preserves existing user content
- 🧾 Stripe Checkout and Customer Portal integration
- ⚡ Redis-backed production rate-limit architecture
- 🎮 Discord BYOB integration planned for U5
- 📦 Discord Bridge/setup package planned for U5
- 👤 Registration, email verification, login, logout, and password recovery
- ✉️ Transactional account and subscription email workflows
- 📈 User dashboard and analytics
- 📤 CSV analytics export
- 🌙 Dark and Light interface themes
- 📱 Responsive desktop, tablet, and mobile web interface
- ☁️ Heroku production deployment
- 🗄️ PostgreSQL production database architecture
- 🧪 Extensive automated regression testing
- 🔒 Production-oriented security and fail-closed configuration controls
- 📲 Native Expo/React Native Android client using the shared Django backend

---

## 💼 Product Plans at a Glance

| Plan | Price | AI Assistants | AI Messages | Knowledge Storage | API | Discord |
| --- | ---: | ---: | ---: | ---: | :---: | :---: |
| **Free** | **$0/month** | 1 | 150/month | 10 MB | — | — |
| **Premium** | **$29/month** | 5 | 3,000/month | 250 MB | — | — |
| **Pro** | **$59/month** | 15 | 10,000/month | 1 GB | Planned U5 | Planned U5 |

All plans support persistent conversations and unlimited stored chats.

AI message quotas and Knowledge storage limits are enforced across the entire user account rather than separately per assistant.

When a user moves to a lower plan, existing assistants, conversations, and Knowledge are preserved. If the account is already above the new plan's assistant or Knowledge limit, the existing content remains accessible while creation of additional over-limit resources is blocked until the account is within the applicable limit.

---

## 🧭 Current Release Status

The platform is actively deployed and has moved beyond a web-only release candidate.

### Web

- Production site: **https://www.myaiassistantapp.se/**
- Django backend hosted on Heroku
- Production custom domain and HTTPS in use
- Stripe production configuration uses **Live Mode**
- Free, Premium, and Pro plan limits are enforced by the backend
- Dashboard, analytics, account flows, assistants, chat, and Knowledge are available through the web client
- SEO endpoints include `sitemap.xml`, `robots.txt`, canonical URLs, Privacy, and public account-deletion information

### Native Android

The dedicated mobile application is built with **Expo / React Native** and is no longer a planned WebView client.

- Package: `com.mrhusse.aiassistant`
- Google Play track: **Closed Testing (Alpha)**
- Current tested release: **versionCode 4 / versionName 1.0.0**
- Play release name: **1.2 - Native Bug Fixes**
- Signed with the approved production upload key
- Existing closed-test users can update through the Google Play test listing
- The app shares the production Django backend and account data with the web application
- Native areas include authentication, Dashboard, Analytics, assistant management/chat, Knowledge access, and Account functionality
- The v4 release includes Android keyboard/chat layout fixes plus Analytics date and Message Count fixes

### iOS

The React Native codebase is designed to support iOS as well as Android. The first iOS distribution is intentionally parked until the Apple Developer Program membership required for device/TestFlight distribution is active. Platform-specific keyboard and device behaviour will be physically verified on iPhone during that release cycle.

### Source Repositories

- Web/backend: `https://github.com/God-zil-la/Project-4`
- Native mobile: `https://github.com/God-zil-la/ai-assistant-mobile`

Development now proceeds as complete upgrade packages: each upgrade is implemented, tested, regression-checked, released, and closed before the next package begins.

---

## 📱 Native Mobile Application

AI Assistant Platform now includes a dedicated **Expo / React Native** mobile application rather than wrapping the production website in a WebView.

The mobile client communicates with the same Django backend used by the web application. This keeps business rules authoritative on the server and prevents the mobile client from becoming a separate copy of the product logic.

### Shared Platform Data

A user can work with the same platform data across supported clients:

- User account and authentication state
- Effective Free, Premium, or Pro entitlement
- AI assistants
- Persistent conversations and messages
- Knowledge sources
- Monthly AI usage
- Assistant and Knowledge limits
- Dashboard information
- Analytics information
- Backend ownership and security rules

### Android Distribution

The Android app is currently distributed through Google Play Closed Testing.

| Item | Current Status |
| --- | --- |
| Framework | Expo / React Native |
| Android package | `com.mrhusse.aiassistant` |
| Play track | Closed Testing (Alpha) |
| versionCode | 4 |
| versionName | 1.0.0 |
| Release name | `1.2 - Native Bug Fixes` |
| Backend | Production Django API |
| WebView | No — dedicated native client |

Closed-test updates may be reached through the tester's Google Play listing. Production distribution will be handled separately when the application is ready to leave testing.

### Android v4 Validation Focus

The current v4 build specifically addresses:

- Chat layout while the Android keyboard is open
- Keyboard open/close behaviour in short and long conversations
- Multiline message composition and sending
- Response visibility after sending
- Analytics date presentation on smaller screens
- Live Analytics Message Count presentation
- General native UI stability

### iOS Direction

Because the client is React Native, the same application codebase provides the foundation for iOS. iOS distribution will begin after the required Apple Developer membership is active, followed by registered-device builds and TestFlight validation.

---

## 📸 Preview

Application screenshots, validation results, architecture diagrams, and workflow illustrations are included throughout this README.

The screenshots document important parts of the platform during its development and validation. Where an older screenshot contains historical pricing, interface text, or functionality, the accompanying documentation identifies it as historical rather than presenting it as current product information.

All current product limits, pricing, and release information are documented in the relevant sections of this README.

---

# ✨ Features

AI Assistant Platform combines specialized artificial intelligence, persistent conversations, the current Retrieval-Augmented Generation (RAG) implementation, account-level usage controls, subscription management, analytics, and protected backend/native interfaces in a single Django-based SaaS platform. Customer-facing Discord integration and API Access are planned for U5.

The system is designed around shared backend services rather than isolated feature implementations. Web chat, supported API access, usage accounting, Knowledge retrieval, plan enforcement, and external integrations reuse the same core business rules wherever practical.

This architecture allows the platform to grow without requiring separate implementations of the core AI workflow for every client.

---

## 🤖 AI Assistants

Users can create and manage specialized AI assistants with their own identity, category, conversations, and Knowledge. Expanded personality, instructions, behaviour, and appearance controls are assigned to **U1 — Assistant Customization**.

Each assistant belongs to its owner and is isolated from assistants belonging to other accounts.

### Assistant Capabilities

- Create custom AI assistants
- Edit existing assistants
- Delete assistants
- Configure assistant names and current supported settings
- Expanded personality, instructions, behaviour, and appearance controls are planned for U1
- Organize assistants by category
- Apply category-specific domain rules
- Maintain separate conversations for each assistant
- Use assistant-specific Knowledge
- Generate context-aware AI responses
- Track AI usage through the owning account
- Access supported integrations according to the user's plan

### Assistant Limits

Assistant limits are enforced at account level:

| Plan | Maximum AI Assistants |
| --- | ---: |
| **Free** | 1 |
| **Premium** | 5 |
| **Pro** | 15 |

The limit controls creation of additional assistants; it does not automatically delete existing assistants when an account moves to a lower plan.

For example, if an account has several assistants while subscribed to Pro and later becomes Free, the existing assistants remain stored. Because Free allows one assistant, creation of another assistant remains blocked while the account is already at or above that limit.

This prevents subscription changes from unexpectedly destroying user data.

### Specialized and General Assistants

Specialized assistants can be restricted to their configured subject area using category-aware domain enforcement.

This helps prevent a purpose-built assistant from silently becoming an unrestricted general chatbot.

General-purpose categories can bypass unnecessary domain classification when a specialized restriction is not required.

---

## 📚 Knowledge Base & RAG

This section describes the **current Knowledge/RAG implementation**. The broader **Knowledge Base / RAG 2.0** work is assigned to U2.

Each assistant can be extended with user-provided Knowledge through a Retrieval-Augmented Generation (RAG) pipeline.

Instead of fine-tuning the underlying AI model for every assistant, relevant information is retrieved from the assistant's stored Knowledge and supplied as context when it is useful for the current request.

### Supported Knowledge Sources

The current v1.0 Knowledge system supports:

- TXT documents
- PDF documents containing extractable text
- DOCX documents
- Manually entered text

Scanned or image-only PDFs are not currently processed through OCR. A PDF therefore needs extractable text for its contents to become usable Knowledge.

### Knowledge Processing

The Knowledge pipeline includes:

- File-type validation
- Text extraction
- Manual-text ingestion
- Hard-bounded text chunking
- Batched OpenAI embedding generation
- Embedding response validation
- Atomic database persistence
- Source-size accounting
- Assistant-specific Knowledge isolation
- Retrieval planning
- Exact and lexical matching
- Semantic similarity matching
- Relevant chunk ranking
- Neighbouring-context expansion
- Relevant Knowledge injection into AI prompts
- Graceful fallback when useful Knowledge is not found
- Cleanup when upload processing fails
- Embedding usage and cost accounting

The current embedding implementation uses `text-embedding-3-small`.

### Retrieval Behaviour

Knowledge retrieval is designed to handle more than simple vector similarity.

Depending on the request, the retrieval pipeline can combine exact or lexical matching with semantic similarity so that both precise values and conceptually related information can be located.

This is particularly useful for documents containing technical values, customer records, structured reference material, and longer documents where the relevant information may be surrounded by important context.

Retrieved Knowledge remains strictly scoped to the selected assistant. Knowledge belonging to another assistant is not included simply because it is semantically similar.

### Knowledge Storage Limits

Knowledge storage is measured across the entire account:

| Plan | Knowledge Storage |
| --- | ---: |
| **Free** | 10 MB |
| **Premium** | 250 MB |
| **Pro** | 1 GB |

The quota represents the combined source size of Knowledge belonging to all assistants owned by the account.

It is **not** a separate allowance for every assistant.

Uploaded files are accounted for using their source size, while manually entered text is measured using its UTF-8 byte size.

Quota validation occurs before expensive extraction, chunking, and embedding work is started when an upload would exceed the account's available storage.

### Knowledge and Plan Downgrades

A downgrade does not automatically delete existing Knowledge.

If an account already contains more Knowledge than the new plan permits:

1. Existing Knowledge remains stored.
2. Existing assistants and conversations remain stored.
3. The account keeps the data it already created.
4. Additional Knowledge is blocked while the account remains above the applicable storage limit.
5. Deleting Knowledge reduces the account's recorded usage and can make storage available again.

This allows plan limits to be enforced without destructive downgrade behaviour.

---

## 💬 AI Playground & Conversations

Each assistant includes an interactive web playground for communicating with the AI.

The interface uses asynchronous requests so messages can be sent and responses displayed without reloading the complete page.

### Playground Functionality

- Real-time AJAX chat
- AI responses powered by OpenAI
- Persistent conversations
- Multiple conversations per assistant
- Create new conversations
- Switch between conversations
- Rename conversations
- Delete conversations
- Conversation-specific message history
- Assistant-specific Knowledge retrieval
- Category and domain enforcement
- Monthly AI message quota enforcement
- Request-rate enforcement
- Usage and cost accounting
- Safe message rendering
- Responsive mobile interface
- Dark and Light mode support

### Unlimited Stored Chats

Stored chats are not capped by the Free, Premium, or Pro plan.

Users can maintain persistent conversation history independently of their monthly AI message allowance.

The monthly quota controls **new AI processing**, not whether previously stored conversations remain available.

### Monthly AI Message Quotas

AI message allowances are enforced across the complete user account:

| Plan | AI Messages per Month |
| --- | ---: |
| **Free** | 150 |
| **Premium** | 3,000 |
| **Pro** | 10,000 |

All assistants owned by the same account share the same monthly allowance.

For example, a Premium user does not receive 3,000 messages for every assistant. The account receives 3,000 AI messages per month in total.

Plan changes do not reset the current monthly usage counter.

When the monthly allowance has been reached, new AI processing is blocked while existing assistants, conversations, messages, and Knowledge remain available.

### Shared Chat Service

The web interface and supported API entry points use the same central chat service.

The shared service coordinates core behaviour such as:

- Account-plan enforcement
- Monthly AI quota handling
- Request-rate limiting
- Category and domain checks
- Knowledge retrieval
- Conversation context
- OpenAI processing
- Usage accounting
- Message persistence
- Error handling

Centralizing this workflow reduces duplicated AI logic and helps keep behaviour consistent across different interfaces.

The native Android client uses this same architecture and existing Django backend.

---

## 🧭 Category & Domain Enforcement

Specialized assistants can be restricted to their configured subject areas so they remain focused on the purpose for which they were created.

Domain enforcement is part of the central AI-processing workflow rather than being implemented only in the browser. This helps keep behaviour consistent across supported entry points.

### Domain Controls

- Category-specific domain rules
- Lightweight classification before the main AI response
- Out-of-domain detection before unnecessary Knowledge retrieval and main AI generation
- General-purpose assistants bypass unnecessary classification
- Domain decisions are included in AI usage accounting
- Shared enforcement through the central chat-processing service
- Automated regression coverage for category behaviour

When an assistant is configured for a specialized domain, unrelated requests can be rejected instead of silently turning the assistant into an unrestricted general-purpose chatbot.

This is especially important for assistants intended for focused use cases such as technical support, business information, product assistance, documentation, or other specialized Knowledge.

General-purpose assistants remain available for use cases where strict domain enforcement is unnecessary.

---

## 🧠 AI Usage & Cost Tracking

AI activity is tracked by the backend to provide account usage information, analytics, operational visibility, quota enforcement, and estimated AI cost monitoring.

Usage tracking is separate from the subscription limits presented to customers.

### Tracked AI Data

The platform can record information including:

- Input tokens
- Output tokens
- Total token usage
- Model identifier
- AI request usage
- Embedding usage
- Estimated model cost
- Per-user usage
- Per-assistant activity
- Current-month usage
- Historical usage information

### AI Models

The current AI configuration includes:

- `gpt-4o-mini` for assistant responses
- `text-embedding-3-small` for Knowledge embeddings

Model pricing configuration is used internally to estimate AI operating costs from recorded token and embedding usage.

These internal cost calculations are intended for analytics and operational monitoring. They are **not** the customer's monthly message quota.

---

## 🚦 Plans, Quotas & Rate Limiting

AI Assistant Platform uses several independent protection mechanisms.

They serve different purposes and should not be confused with one another:

1. **Assistant limits** control how many assistants an account can create.
2. **Monthly AI message quotas** control the amount of new AI processing included in the account plan.
3. **Knowledge storage quotas** control the combined Knowledge source size stored across the account.
4. **Request-rate limits** protect the service from unusually rapid request bursts and abuse.

### Current Plan Limits

| Plan | Assistants | AI Messages | Knowledge | Request Rate |
| --- | ---: | ---: | ---: | ---: |
| **Free** | 1 | 150/month | 10 MB | 20 requests/minute |
| **Premium** | 5 | 3,000/month | 250 MB | 60 requests/minute |
| **Pro** | 15 | 10,000/month | 1 GB | 120 requests/minute |

Chats remain unlimited across all three plans.

### Account-Wide AI Quotas

Monthly AI message quotas belong to the **user account**, not to individual assistants.

All assistants owned by the same user therefore consume the same monthly allowance.

For example:

- A Free account receives 150 AI messages per month in total.
- A Premium account receives 3,000 AI messages per month in total.
- A Pro account receives 10,000 AI messages per month in total.

Creating additional assistants does not create additional message allowances.

### Calendar-Month Usage

AI message usage is tracked for the current calendar month.

Changing plans does not reset the existing monthly usage counter.

This prevents plan changes from being used to repeatedly reset usage during the same month.

When the applicable monthly allowance has been reached, new AI processing is blocked while existing account data remains intact.

Stored assistants, conversations, previous messages, and Knowledge are not deleted simply because the AI message quota has been reached.

### Account-Wide Knowledge Quotas

Knowledge storage is also account-wide.

The storage allowance is shared between all assistants owned by the user:

- Free: 10 MB
- Premium: 250 MB
- Pro: 1 GB

The platform checks whether new Knowledge would exceed the applicable account storage limit before expensive extraction, chunking, and embedding processing begins.

### Request-Rate Protection

Monthly quotas and request-rate limits solve different problems.

A user may still have monthly AI messages available while temporarily exceeding the allowed request rate.

Current request-rate protection is plan-aware:

- Free: 20 requests per minute
- Premium: 60 requests per minute
- Pro: 120 requests per minute

This provides additional protection against accidental request loops, automated abuse, and unusually high short-term traffic.

Redis-backed caching is implemented for production-oriented rate-limit storage, while local development can use the configured local-memory fallback.

Hosted Redis connectivity remains part of the final production configuration verification and is not treated as a replacement for monthly quota enforcement.

---

## 💳 Subscription Infrastructure

Subscription management is implemented with Stripe for the web platform.

The production application is configured for **Stripe Live Mode**. Stripe Test Mode remains available only for isolated development and validation workflows; production credentials, Price IDs, webhooks, and Checkout configuration are kept separate.

### Current Subscription Plans

| Plan | Monthly Price | Assistants | AI Messages | Knowledge | API | Discord |
| --- | ---: | ---: | ---: | ---: | :---: | :---: |
| **Free** | **$0 USD** | 1 | 150/month | 10 MB | — | — |
| **Premium** | **$29 USD** | 5 | 3,000/month | 250 MB | — | — |
| **Pro** | **$59 USD** | 15 | 10,000/month | 1 GB | Planned U5 | Planned U5 |

The Free plan does not require a paid Stripe subscription.

Premium and Pro are recurring paid subscription tiers for the web platform.

### Implemented Stripe Functionality

The subscription system includes:

- Stripe Checkout
- Premium subscription purchases
- Pro subscription purchases
- Stripe Customer Portal integration
- Subscription metadata validation
- Signed webhook verification
- Checkout completion handling
- Subscription upgrade handling
- Subscription downgrade handling
- Subscription cancellation handling
- Scheduled cancellation handling
- Subscription recovery handling
- Duplicate webhook protection
- Current-subscription reconciliation
- Customer ownership validation
- Subscription ownership validation
- Price validation
- Billing-period validation
- Stripe Test/Live mode mismatch protection
- Retryable provider-failure handling
- Sanitized payment-provider errors
- Plan-entitlement synchronization

### Upgrade & Downgrade Behaviour

Plan changes are designed to preserve user data.

A downgrade does **not** automatically delete assistants, conversations, messages, or Knowledge simply because the lower plan has smaller limits.

Instead, the lower plan's limits control future creation and usage after the lower entitlement becomes effective.

For example, if a user moves from Pro to Premium while owning seven assistants:

- The seven existing assistants remain stored.
- Their existing conversations remain stored.
- Their existing Knowledge remains stored.
- Premium's five-assistant limit prevents creation of another assistant while the account remains above that limit.

The same principle applies to Knowledge storage.

If retained Knowledge exceeds the new plan's storage allowance, existing Knowledge remains stored while additional Knowledge uploads are blocked until sufficient storage becomes available.

Monthly AI usage is also preserved across plan changes rather than being reset.

### Cancellation to Free

When a paid subscription ends and the account returns to Free:

- Existing assistants are preserved.
- Existing conversations and messages are preserved.
- Existing Knowledge is preserved.
- The Free assistant limit applies to creation of new assistants.
- The Free Knowledge quota applies to new Knowledge additions.
- The Free monthly AI message allowance applies to new AI processing.

This avoids destructive subscription behaviour while still enforcing the limits of the active plan.

### Stripe Development & Production Modes

The production web application is configured with **Stripe Live Mode**.

Stripe Test Mode remains available only for isolated development and regression validation. Test credentials, Test Price IDs, test webhooks, and test Checkout configuration must remain separate from production.

The production configuration uses Live credentials, Live Price IDs, production webhook configuration, Checkout, and Customer Portal settings. Development and automated tests must never create real customer charges.

### Android Billing

The native Android client uses the same Django backend, user accounts, assistants, conversations, Knowledge, quotas, analytics, and entitlement system.

Android in-app subscription purchases are planned to use **Google Play Billing** rather than routing Android in-app purchases through Stripe.

The backend will remain the authoritative source for the user's effective entitlement regardless of which supported client is being used.

---

## 🤖 Discord Integration — U5 Roadmap

Discord integration is assigned to **U5 — Discord Integration + API Access** and should be treated as roadmap work rather than a currently released customer feature.

The planned direction is a **Bring Your Own Bot (BYOB)** workflow for eligible accounts. U5 is intended to cover the complete customer-facing package, including setup guidance, Discord application/bot configuration, required intents and permissions, secure token handling, assistant binding, connection status and diagnostics, usage/limits, and the bridge/API path required for Discord messages to reach the selected AI assistant.

Earlier prototypes, experiments, or partial backend work do not make the complete Discord product feature released. The U5 package must be implemented, tested end-to-end, regression-checked, deployed, and released before this README describes Discord as generally available.
---

## 📊 Dashboard & Analytics

The authenticated dashboard provides users with visibility into their assistants, AI usage, and account activity.

Analytics are kept conceptually separate from subscription quota enforcement.

Quota services determine whether new AI processing or Knowledge additions are permitted, while analytics provide visibility into recorded activity.

### User Dashboard

The dashboard can provide information including:

- Assistant overview
- Account plan information
- Current monthly AI usage
- Monthly AI allowance
- Usage progress
- AI request activity
- Token usage
- Estimated AI cost
- Conversation activity
- Assistant-level statistics

### Usage Tracking

The analytics system is backed by recorded AI usage information rather than estimating activity from the browser.

Tracked information can include:

- AI requests
- Input tokens
- Output tokens
- Total tokens
- Model identifiers
- Embedding usage
- Estimated model cost
- User activity
- Assistant activity
- Current-month usage

### CSV Export

Analytics data can be exported to CSV for external review and reporting.

This allows usage information to be examined outside the web dashboard when required.

### Administrative Analytics

Staff-facing analytics provide additional operational visibility while remaining separate from normal user-facing account data.

Administrative access is protected by Django's staff and permission controls.

---

## 👤 User Management & Account Access

Authentication and account management are handled by Django with additional application-specific account and subscription state.

### Account Features

The platform supports:

- User registration
- Email verification
- Account activation
- Login
- Logout
- Password reset
- Password update
- Secure authenticated sessions
- Protected routes
- User profiles
- Account plan tracking
- Subscription entitlement tracking
- Monthly AI usage tracking
- Protected backend/native authentication
- Transactional account emails

### Registration & Verification

New accounts use an email-verification workflow before normal account use.

Verification links activate the intended account and the authentication flow returns the user to the appropriate application experience.

### Password Recovery

Password recovery is implemented through Django's secure password-reset workflow.

Users can request a reset email, follow the generated reset link, choose a new password, and regain authenticated account access.

### Transactional Emails

Account and subscription workflows include transactional email handling for important events such as:

- Registration and verification
- Password recovery
- Successful subscription events
- Subscription changes
- Subscription cancellation

Email links are expected to return users to the appropriate account or application destination rather than leaving the workflow disconnected from the web application.

### Account State

The user's effective plan is used by backend entitlement checks to determine access to plan-specific functionality.

Frontend presentation may adapt to the authenticated state, but backend authorization remains authoritative.

This means hiding a button is never treated as sufficient protection for a restricted feature.

---

## 🔌 API & External Integrations

The platform already uses protected backend API functionality for supported first-party/native client communication.

A **customer-facing API Access product** is assigned to **U5 — Discord Integration + API Access** and is not yet described as a released customer feature.

### Current Backend Role

The native Android application communicates with the Django backend so the same server-side ownership, plan, quota, Knowledge, conversation, analytics, and security rules remain authoritative across clients.

### Planned U5 API Access

U5 is intended to add the complete customer-facing API package, including:

- Account API-key management
- Secure key rotation
- Assistant invocation
- Plan/entitlement enforcement
- Usage and rate limits
- Request validation
- Ownership validation
- Documentation and examples
- Integration with the U5 Discord workflow

Earlier protected endpoints, adapters, tests, or internal API work should not be interpreted as the complete public API product being generally available.

### Integrated Services

| Integration | Purpose |
| --- | --- |
| **OpenAI API** | AI responses and Knowledge embeddings |
| **Stripe** | Web subscription and billing infrastructure |
| **Django REST Framework** | Protected backend/native interfaces |
| **Redis-compatible cache** | Production-oriented rate-limit infrastructure |
| **PostgreSQL** | Production relational database |
| **Heroku** | Cloud deployment platform |

The web application and native mobile client are interfaces to the same core platform rather than separate AI products.
---

## 🎨 User Experience

The web application is designed as a responsive SaaS interface that works across desktop, tablet, and mobile screen sizes.

The interface is built around authenticated account state, assistant management, persistent conversations, Knowledge management, analytics, subscriptions, and plan-aware functionality.

### Responsive Design

The application includes:

- Responsive desktop layouts
- Tablet-friendly layouts
- Mobile navigation
- Responsive forms
- Responsive assistant management
- Responsive chat interfaces
- Responsive Knowledge controls
- Responsive account and billing interfaces
- Responsive analytics views

The web client is intended to remain fully usable on smaller screens while preserving access to the same backend account and assistant data.

### Dark & Light Themes

Users can switch between Dark and Light interface themes.

Theme support is applied across the platform so the application maintains a consistent visual identity throughout public pages, authenticated areas, forms, dashboards, assistant management, and chat interfaces.

### Authenticated-State Interface

Public and authenticated users are presented with different actions where appropriate.

When a user is already signed in, navigation and calls to action can adapt to the authenticated state rather than continuing to present registration-oriented actions intended for new users.

This keeps the interface aligned with the user's current account state.

### Interactive Chat Experience

The assistant playground uses asynchronous communication so users can send messages and receive AI responses without requiring a complete page reload.

The chat experience includes:

- AJAX-based message submission
- Persistent conversation history
- Conversation switching
- Conversation creation
- Conversation renaming
- Conversation deletion
- Assistant-specific context
- Knowledge-aware responses
- Plan-aware AI processing
- Monthly quota feedback
- Error feedback
- Responsive chat controls

### User Feedback

The interface uses application messages to communicate important events such as:

- Successful actions
- Validation errors
- Knowledge upload results
- Plan restrictions
- Quota restrictions
- Account actions
- Subscription events
- Processing failures

Clear feedback is especially important for operations that depend on backend validation rather than frontend state alone.

### Accessibility & Forms

Forms and interactive controls are designed with standard HTML and Django form behaviour so validation remains available on the server even when client-side enhancements are present.

The interface includes:

- Labelled form controls
- Server-side validation
- Validation feedback
- Protected form submissions
- Responsive form layouts
- Clear action buttons
- Navigation suitable for different viewport sizes

### Client/Backend Separation

The browser interface is not treated as the security boundary.

Frontend controls improve the user experience, while authentication, authorization, plan restrictions, quotas, ownership validation, and sensitive business rules are enforced by the Django backend.

This allows the native Android client and future supported clients to reuse the same backend rules without depending on web-interface behaviour.

---

## 🔒 Security & Reliability

Security, authorization, failure handling, and data isolation are built into the backend architecture.

The application follows a defence-in-depth approach: sensitive operations are protected by backend validation even when corresponding restrictions are also represented in the user interface.

### Authentication & Authorization

Implemented account protections include:

- Django authentication
- Protected authenticated routes
- Secure session handling
- Active-account validation
- Email-verification workflow
- Password-reset workflow
- Staff-only administrative functionality
- Backend plan-entitlement enforcement

Authentication determines who the user is, while authorization and ownership validation determine which resources that user may access.

### Object Ownership & Data Isolation

User-owned resources are validated on the backend.

Protection includes ownership checks for:

- AI assistants
- Conversations
- Chat messages
- Knowledge
- API operations
- Subscription-related account operations

Knowledge retrieval is also scoped to the selected assistant so information belonging to another assistant is not introduced merely because it appears semantically relevant.

### CSRF & Request Protection

Django's request-security mechanisms are used throughout the web application.

Implemented controls include:

- CSRF protection
- Authentication checks
- Authorization checks
- Input validation
- Request-body shape validation
- Protected state-changing operations
- Safe redirects and controlled error handling

### Backend / Native API Security

Protected backend/native API functionality includes:

- API-key authentication
- Active-user validation
- Plan/entitlement enforcement where applicable
- Assistant ownership validation
- Conversation ownership validation
- Request validation
- Monthly AI quota enforcement
- Request-rate enforcement
- Sanitized client-facing errors

Backend/native credentials and provider secrets are treated as secrets and are not intended for public display or source-control storage. Customer-facing API-key management is planned for U5.

### Knowledge Security & Reliability

Knowledge ingestion and retrieval include protections such as:

- Supported file-type validation
- Source-size quota validation
- Account-wide Knowledge quota enforcement
- Quota checks before expensive processing
- Text extraction validation
- Hard-bounded chunking
- Embedding response validation
- Atomic Knowledge persistence
- Failed-upload cleanup
- Assistant-specific Knowledge isolation
- Ownership validation for deletion
- Safe handling of legacy Knowledge ownership metadata

Knowledge quotas are based on the owning account rather than relying solely on nullable uploader metadata.

### AI Quota Protection

Monthly AI usage is enforced by the backend before new AI processing is allowed.

The central processing workflow uses account-level quota handling so supported AI entry points share the same monthly allowance.

Important quota behaviour includes:

- Free: 150 AI messages per month
- Premium: 3,000 AI messages per month
- Pro: 10,000 AI messages per month
- Account-wide usage
- Calendar-month tracking
- No quota reset when changing plans
- Blocking before new AI processing when the allowance is exhausted
- Existing chats and data remain available when processing is blocked

Quota handling is separate from short-term request-rate limiting.

### Rate Limiting

Plan-aware request-rate controls provide additional protection against rapid request bursts and abuse.

Current configured request rates are:

| Plan | Request Rate |
| --- | ---: |
| **Free** | 20 requests/minute |
| **Premium** | 60 requests/minute |
| **Pro** | 120 requests/minute |

Redis-compatible caching is implemented for production-oriented rate-limit storage.

Local development can use the configured local-memory fallback.

Redis-compatible caching remains part of the production-oriented rate-limit architecture and should be revalidated whenever production infrastructure or cache configuration changes.

### Stripe Security

The payment infrastructure includes multiple layers of validation around subscription state.

Implemented protections include:

- Stripe Checkout
- Signed webhook verification
- Webhook event idempotency
- Customer ownership validation
- Subscription ownership validation
- Subscription metadata validation
- Price validation
- Billing-period validation
- Transactional subscription reconciliation
- Test/Live mode mismatch protection
- Retryable provider-failure handling
- Sanitized payment-provider errors

The production application uses **Stripe Live Mode**. Test credentials and Test Mode Price IDs remain isolated from production configuration.

### Secret Management

Sensitive configuration is expected to be provided through environment variables rather than committed directly to source control.

Examples include:

- Django secret configuration
- Database credentials
- OpenAI credentials
- Stripe credentials
- Stripe webhook secrets
- Email credentials
- Redis configuration
- Other provider-specific secrets

Secrets must not be included in the README, screenshots, Git history, public logs, or administrative list displays.

### Administrative Security

Administrative interfaces are intentionally restricted from exposing unnecessary sensitive information.

Implemented hardening includes:

- Reduced sensitive information exposure
- API credentials excluded from inappropriate administrative displays
- Sensitive credentials excluded from searchable admin fields
- No intentional secret logging during application startup
- Staff-only administrative functionality

### Error Handling

The application includes custom handling for common HTTP error conditions:

- `400 Bad Request`
- `403 Forbidden`
- `404 Not Found`
- `500 Internal Server Error`

Production-facing error handling is designed to provide useful user feedback without exposing unnecessary internal implementation details.

### Fail-Closed Behaviour

Security-sensitive production configuration is designed to fail safely rather than silently weakening important controls.

Where infrastructure is required for a production protection mechanism, configuration failures should be visible during validation instead of quietly changing the intended security model.

### Automated Regression Protection

Security and reliability behaviour is covered by automated Django tests across important application areas.

Regression coverage includes areas such as:

- Authentication
- Account workflows
- Assistant ownership
- Conversation ownership
- Knowledge isolation
- Knowledge uploads
- Knowledge storage quotas
- AI monthly quotas
- Plan enforcement
- API access
- Stripe subscription workflows
- Upgrade and downgrade behaviour
- Cancellation behaviour
- Preservation of existing content
- Error handling

Historical and targeted test counts are treated as development checkpoints. A future release should document its own complete regression result when that release is prepared.

### Production Release Verification

The core security and reliability controls are implemented.

Production releases use a dedicated verification pass covering:

- Complete regression test suite
- Django production settings
- `DEBUG=False`
- Production host and HTTPS configuration
- Production Redis connectivity
- Test-only routes and configuration
- Environment-variable review
- Secret exposure review
- Stripe production configuration
- Deployment configuration
- Database migrations
- Final live smoke testing

Stripe Live Mode is active in production; Test Mode remains isolated for development and regression validation.

---

# 📸 Application Tour

The following screenshots provide a visual tour of the AI Assistant Platform and demonstrate key parts of the web application.

Some screenshots were captured during earlier development stages. Where an older screenshot contains historical pricing, wording, or interface state, it is explicitly identified as historical and should not be interpreted as the current product configuration.

Current pricing and plan limits are documented in the Product Plans and Subscription sections of this README.

---

## 🏠 Home Page

The landing page introduces the AI Assistant Platform, highlights its main capabilities, and provides navigation appropriate to the user's authentication state.

Visitors can access account registration and authentication, while authenticated users can continue into the application and their existing account functionality.

![Home - Dark Mode](readme-img-validation/home-darkmode.jpg)

---

## ☀️ Light Theme

The web application supports both Dark and Light interface themes.

Users can switch between themes while continuing to use the same application functionality.

![Home - Light Mode](readme-img-validation/home-lightmode.jpg)

---

## 🤖 Create an AI Assistant

Authenticated users can create specialized AI assistants using the settings currently exposed by the product. Expanded personality, instructions, behaviour, and appearance controls are planned for **U1 — Assistant Customization**.

Assistant creation is subject to the active account plan:

| Plan | Maximum Assistants |
| --- | ---: |
| **Free** | 1 |
| **Premium** | 5 |
| **Pro** | 15 |

Existing assistants are preserved if a later plan downgrade places the account above its new creation limit.

![Create Bot](readme-img-validation/create-bot.jpg)

---

## 💬 AI Playground

Each assistant includes an interactive AI Playground for persistent conversations.

The playground connects to the shared backend AI-processing service and can use:

- Conversation history
- Assistant configuration
- Category and domain enforcement
- Assistant-specific Knowledge
- Monthly account AI quota
- Request-rate protection
- OpenAI response generation
- Usage accounting

Messages are submitted asynchronously so conversations can continue without full-page reloads.

**Historical screenshot:** The original playground screenshot was captured during an earlier development stage and showed a recipe assistant, message controls, and a Knowledge upload interface. The original screenshot remains preserved in the project history.

---

## 📚 Knowledge Base

Users can extend individual assistants with custom Knowledge.

The current Knowledge system supports:

- TXT files
- PDF files containing extractable text
- DOCX files
- Manually entered text

Uploaded content is extracted, processed, divided into bounded chunks, embedded, and stored for retrieval during relevant AI conversations.

Knowledge remains scoped to the owning assistant and account.

Scanned or image-only PDFs are not currently processed through OCR.

![Knowledge Upload](readme-img-validation/answer-upload-knowledge-txt.jpg)

---

## ✅ Knowledge Processing Complete

After successful processing, uploaded Knowledge becomes available to the assistant's retrieval pipeline.

The system can combine exact, lexical, and semantic retrieval techniques to identify useful information before generating an AI response.

Knowledge storage is subject to the account-wide plan allowance:

| Plan | Knowledge Storage |
| --- | ---: |
| **Free** | 10 MB |
| **Premium** | 250 MB |
| **Pro** | 1 GB |

Quota validation occurs before expensive extraction and embedding processing when a new addition would exceed the available storage allowance.

![Knowledge Upload Confirmation](readme-img-validation/knowledge-upload-confirm.jpg)

---

## 🤖 Discord Integration — Planned U5

Discord is part of the **U5** upgrade package. The intended design uses a customer-owned Discord bot connected securely to the AI Assistant backend.

Any historical Discord screenshots or earlier bridge experiments should be interpreted as development history, not as proof that the complete U5 customer feature is currently released.
---

## 💳 Plans & Membership

AI Assistant Platform provides three account plans:

| Plan | Price | Assistants | AI Messages | Knowledge | API | Discord |
| --- | ---: | ---: | ---: | ---: | :---: | :---: |
| **Free** | **$0/month** | 1 | 150/month | 10 MB | — | — |
| **Premium** | **$29/month** | 5 | 3,000/month | 250 MB | — | — |
| **Pro** | **$59/month** | 15 | 10,000/month | 1 GB | Planned U5 | Planned U5 |

Chats remain unlimited across all plans.

The screenshot below was captured during development and may contain historical plan presentation. The table above represents the current product configuration.

![Premium Upgrade](readme-img-validation/premium-upgrade.jpg)

---

## 💳 Secure Stripe Checkout

Paid web subscriptions are processed through Stripe Checkout.

The production web application is configured with **Stripe Live Mode**, including production credentials, Live Price IDs, production webhook configuration, and production Checkout settings. Test Mode remains separate for safe development validation.

**Historical screenshot:** An earlier Stripe sandbox screenshot showed a Pro Bot Plan priced at USD 15.00. That amount is historical and does **not** represent the current Pro price of **$59/month**. The original screenshot remains preserved in the project history.

---

## ✅ Successful Payment

Successful Stripe subscription flows return the account to the application with the appropriate subscription state available to the backend.

Payment and subscription handling includes server-side verification rather than relying solely on the browser's successful Checkout redirect.

The screenshot below demonstrates a completed payment using Stripe's official test environment.

![Payment Successful](readme-img-validation/payment-successful.jpg)

---

## 📧 User Registration

New users can create an account through the integrated registration system.

The account workflow includes:

1. Registration
2. Verification email
3. Account activation
4. Authenticated application access

Account verification helps ensure that registration and account access are connected to the intended email address.

![Email Registration](readme-img-validation/email-register.jpg)

---

## 🔐 Password Recovery

Users who forget their password can use the email-based password recovery workflow.

The complete flow supports:

1. Requesting a password-reset email
2. Opening the generated reset link
3. Setting a new password
4. Returning to authenticated account access

Password-reset links use Django's secure token-based password recovery system.

![Password Reset](readme-img-validation/email-reset-password.jpg)

---

## 📨 Email Notifications

Important account and subscription events can generate transactional email notifications.

Email workflows include events such as:

- Account registration and verification
- Password recovery
- Subscription confirmation
- Subscription changes
- Subscription cancellation

Links contained in these workflows are intended to return users to the relevant account or application destination.

![Email Notification](readme-img-validation/email-notification.jpg)

---

## ⚠️ Form Validation

Forms use backend validation to prevent invalid or incomplete information from being accepted simply because client-side checks are bypassed.

Validation feedback is presented to users in a clear interface while the Django backend remains responsible for authoritative validation.

![Login Validation](readme-img-validation/login-error.jpg)

---

# 🔄 System Workflows

The following workflows illustrate how the main components of the AI Assistant Platform interact.

The diagrams were created during development and are preserved as part of the project's technical documentation. The accompanying descriptions below reflect the current backend architecture, including account-wide quotas, multi-format Knowledge processing, centralized AI processing, and plan-aware access control.

---

## 🔁 CRUD Workflow

AI assistants are managed through authenticated CRUD operations backed by Django and PostgreSQL.

### Workflow

1. The authenticated user opens the assistant management interface.
2. Django determines the user's effective account plan.
3. The backend checks the applicable assistant creation limit.
4. Submitted assistant data is validated.
5. The assistant is associated with the authenticated owner.
6. Django ORM persists the assistant in the database.
7. Existing assistants can be viewed and updated by their owner.
8. Assistants can be deleted through ownership-protected operations.
9. Changes are reflected throughout the user's authenticated application.

### Plan-Aware Creation

Assistant creation limits are enforced by the backend:

| Plan | Maximum Assistants |
| --- | ---: |
| **Free** | 1 |
| **Premium** | 5 |
| **Pro** | 15 |

A downgrade does not automatically delete assistants that already exist above the lower plan's limit.

Instead, existing content is preserved while creation of additional assistants is blocked until the account is within the applicable limit.

![CRUD Workflow](readme-img-validation/crud.jpg)

---

## 💬 AJAX Chat Flow

The AI Playground uses asynchronous requests so users can continue conversations without full-page reloads.

The current chat architecture performs significantly more backend processing than simply forwarding a browser message directly to OpenAI.

### Workflow

1. The user submits a message from an assistant conversation.
2. JavaScript sends the request asynchronously to Django.
3. Django validates the authenticated user and request.
4. The backend validates assistant and conversation ownership.
5. The shared AI-processing service applies the relevant account and assistant rules.
6. Monthly AI quota availability is checked.
7. Request-rate protection is applied.
8. Specialized assistants can apply category/domain enforcement.
9. Relevant assistant Knowledge is retrieved when appropriate.
10. Existing conversation context is prepared.
11. The AI request is sent to OpenAI.
12. Usage information is recorded.
13. The assistant response is persisted to the conversation.
14. Django returns the result to the browser.
15. JavaScript updates the conversation without a complete page reload.

### Centralized Processing

The central processing architecture allows supported chat entry points to share important backend rules rather than duplicating them independently.

Conceptually:

    Browser / Supported Client
              │
              ▼
        Django Endpoint
              │
              ▼
      Ownership Validation
              │
              ▼
      Central AI Service
              │
              ├── Monthly AI quota
              ├── Rate limiting
              ├── Domain enforcement
              ├── Knowledge retrieval
              ├── Conversation context
              ├── OpenAI processing
              └── Usage accounting
              │
              ▼
       Stored AI Response
              │
              ▼
            Client

This architecture also reduces the risk of another supported interface bypassing the same quota or assistant-processing rules used by the web playground.

![AJAX Chat Flow](readme-img-validation/ajax-chat-Flow-diagram.jpg)

---

## 📚 Knowledge Base Processing

Knowledge sources are processed before becoming available to an assistant's retrieval pipeline.

The current Knowledge system supports:

- TXT files
- PDF files containing extractable text
- DOCX files
- Manual text entry

Scanned or image-only PDFs are not currently processed with OCR.

### Upload & Processing Workflow

1. The authenticated user selects an assistant.
2. The user provides a supported file or manually entered text.
3. Django validates ownership of the target assistant.
4. The source size is calculated.
5. Existing account-wide Knowledge usage is calculated.
6. The applicable plan storage allowance is checked.
7. If the new source would exceed the quota, processing is blocked before extraction, chunking, or embedding generation.
8. Supported source content is extracted or normalized.
9. Text is divided into bounded chunks.
10. Embeddings are generated using `text-embedding-3-small`.
11. Knowledge metadata and chunks are persisted.
12. The Knowledge becomes available to the owning assistant's retrieval pipeline.

### Account-Wide Storage Limits

| Plan | Knowledge Storage |
| --- | ---: |
| **Free** | 10 MB |
| **Premium** | 250 MB |
| **Pro** | 1 GB |

Storage usage is calculated across the user's assistants rather than providing a separate allowance for every assistant.

For uploaded files, the original source size is used for quota accounting.

For manual Knowledge, UTF-8 encoded text size is used.

A source that brings the account exactly to its storage limit is allowed. A source that would exceed the limit is blocked before expensive processing begins.

### Retrieval Workflow

When Knowledge is relevant to an AI request, the retrieval pipeline can use multiple retrieval signals instead of relying exclusively on a single semantic similarity result.

Conceptually:

    User Question
         │
         ▼
    Query Planning
         │
         ├── Exact matching
         ├── Lexical relevance
         └── Semantic relevance
         │
         ▼
    Candidate Knowledge Chunks
         │
         ▼
    Ranking / Selection
         │
         ▼
    Relevant Context
         │
         ▼
    AI Response Generation

The retrieval system can also use neighbouring chunks and document context where appropriate to improve the usefulness of retrieved information.

Knowledge remains strictly scoped to the selected assistant.

A semantically similar chunk belonging to another assistant must not be included merely because it matches the user's question.

![Knowledge Base Processing](readme-img-validation/knowledge-upload-flow-diagram.jpg)

---

## 🗄️ Database Entity Relationship Diagram (ERD)

The Entity Relationship Diagram illustrates the major data relationships used by the Django application.

The platform uses Django ORM with PostgreSQL in production.

### Main Data Relationships

The application data model includes relationships such as:

- Users own AI assistants.
- Users have profile and account-plan state.
- AI assistants belong to individual users.
- Assistants contain persistent conversations.
- Conversations contain chat messages.
- Assistants can contain multiple Knowledge sources.
- Knowledge sources are divided into searchable Knowledge chunks.
- Knowledge sources retain source-size information for account-wide storage accounting.
- AI activity produces usage records.
- User profiles maintain account-level AI usage state.
- Subscription information determines paid-plan entitlement.
- Stripe customer and subscription state is associated with the corresponding platform account.

### Ownership Model

Resource ownership is important to both application behaviour and security.

Conceptually:

    User
     │
     ├── User Profile / Plan State
     │
     ├── Subscription State
     │
     └── AI Assistants
             │
             ├── Conversations
             │       │
             │       └── Chat Messages
             │
             ├── Knowledge Sources
             │       │
             │       └── Knowledge Chunks
             │
             └── AI Usage Activity

Backend ownership validation prevents authenticated users from treating another user's assistant, conversation, or Knowledge as their own resource.

### Downgrade Preservation

Plan limits control future usage and creation without destructively rewriting these database relationships.

For example, when an account downgrades:

- Existing assistants remain stored.
- Existing conversations remain stored.
- Existing messages remain stored.
- Existing Knowledge remains stored.
- Subscription entitlement changes.
- New operations are evaluated against the newly effective plan limits.

This allows the data model to preserve user content independently from subscription-tier changes.

![Database ERD](readme-img-validation/erd.jpg)

---

# ✅ Validation

The AI Assistant Platform has been continuously tested throughout development using automated regression tests, Django validation tools, manual end-to-end testing, standards validators, and live hosted verification.

Validation covers both expected behaviour and important failure paths.

Earlier targeted test counts are treated as development checkpoints rather than a permanent project-wide total. Each major release should record its own applicable regression result.

---

## 🧪 Automated Backend Testing

The Django backend contains regression coverage across the major application systems.

### Covered Areas

Automated testing includes areas such as:

- User authentication
- Account activation
- Email verification
- Password recovery
- Assistant CRUD operations
- Assistant ownership
- Assistant plan limits
- Conversation management
- Conversation ownership
- Chat-message persistence
- AI processing
- Category and domain enforcement
- Knowledge ingestion
- Knowledge retrieval
- Knowledge isolation
- Knowledge storage quotas
- Monthly AI message quotas
- Usage accounting
- API authentication
- API authorization
- API entitlement/authorization groundwork
- Request validation
- Rate limiting
- Stripe Checkout workflows
- Stripe webhook processing
- Subscription state
- Upgrade behaviour
- Downgrade behaviour
- Cancellation behaviour
- Preservation of existing user content
- Error handling

### Recent Verified Regression Work

Recent development checkpoints have successfully validated the newly completed account-wide quota and subscription-continuation behaviour.

This includes targeted regression coverage for:

- Account-wide monthly AI message limits
- Free, Premium, and Pro monthly allowances
- Atomic AI quota reservation
- Quota release when processing fails
- Blocking new AI processing after quota exhaustion
- No monthly quota reset when changing plans
- Account-wide Knowledge storage
- TXT, PDF, DOCX, and manual Knowledge sources
- Knowledge quota validation before expensive processing
- Exact-limit Knowledge acceptance
- Over-limit Knowledge rejection
- Knowledge preservation after downgrade
- Assistant preservation after downgrade
- Conversation preservation after downgrade
- Chat-message preservation after downgrade
- Pro-to-Premium continuation
- Paid-to-Free continuation
- Lower-plan assistant creation restrictions
- API entitlement/authorization groundwork
- Stripe subscription behaviour

The project has also passed focused regression suites for account, assistant, payment, Knowledge, API, and continuation behaviour during development.

### Supporting Django Checks

Development validation also includes:

- Django system checks
- Migration consistency checks
- Ruff code-quality checks
- Git diff/whitespace validation
- Focused regression tests after backend changes

Recent quota and Knowledge work has passed Django system and migration consistency checks during its development cycle.

### Negative-Path Testing

The regression suite intentionally tests invalid and blocked operations.

Examples include:

- Unauthorized resource access
- Invalid API requests
- Plan-restricted operations
- Exhausted AI quotas
- Knowledge storage overflow
- Invalid subscription state
- Provider failures
- Ownership violations

As a result, warning or error log output can appear during a successful test run when the test intentionally exercises an expected failure path.

The important assertion is that the application rejects the operation correctly and preserves valid application state.

### Release Regression

For future major releases, the applicable automated suite should be executed against the release code.

A release validation pass should record:

- Total discovered tests
- Total executed tests
- Final pass/fail result
- Django system-check result
- Migration consistency result
- Ruff result
- Release configuration checks

This avoids presenting an intermediate targeted test count as though it represents the final complete application.

---

## 🌐 HTML Validation

HTML pages have been validated using the W3C HTML Validator during development.

Validation focuses on maintaining standards-compliant markup across public and authenticated interfaces.

### Validation Goals

- Semantic HTML5
- Valid document structure
- Accessible markup
- Correct form structure
- Standards-compliant elements and attributes
- No critical validation errors

![HTML Validation](readme-img-validation/home-valid-html.jpg)

---

## 🎨 CSS Validation

Stylesheets have been checked using the W3C CSS Validator during development.

### Validation Goals

- Standards-compliant CSS
- No critical syntax errors
- Consistent responsive styling
- Valid media-query behaviour
- Cross-browser-compatible layout rules

**Historical validation result:** The retained W3C CSS validation result reported **"Congratulations! No errors found."** for the stylesheet submitted at that development checkpoint.

The screenshot/result represents that historical validation run and should not be interpreted as a newly executed final-release validation.

The original screenshot remains preserved in the project history.

---

## 🚀 Lighthouse Audit

Google Lighthouse has been used to evaluate the quality of the web interface.

### Areas Evaluated

- Performance
- Accessibility
- Best Practices
- Search Engine Optimization (SEO)

Lighthouse testing complements functional backend testing by evaluating browser-facing quality and usability characteristics.

![Lighthouse](readme-img-validation/lighthouse.jpg)

---

## 📱 Responsive Testing

The web interface has been tested across multiple viewport sizes to ensure that core application functionality remains usable on different devices.

### Layouts Tested

- Desktop
- Laptop
- Tablet
- Mobile

Responsive behaviour includes:

- Navigation
- Forms
- Assistant management
- Chat interfaces
- Knowledge controls
- Dashboard content
- Account pages
- Subscription interfaces

CSS media queries and flexible layouts allow the interface to adapt to smaller screens without creating a separate mobile web application.

---

## 🔒 Functional Testing

Manual functional testing has been performed alongside automated backend regression testing.

This is especially important for workflows that involve multiple systems or external services.

### Account Workflows

Manually tested account functionality includes:

- Registration
- Email verification
- Account activation
- Login
- Logout
- Password reset
- Authenticated account access
- Transactional account emails

### Assistant & Chat Workflows

Manual testing includes:

- Assistant creation
- Assistant editing
- Assistant deletion
- Plan-aware assistant limits
- AI Playground conversations
- Conversation creation
- Conversation management
- Persistent chat history
- Category and domain enforcement
- Out-of-domain behaviour

### Knowledge Workflows

Knowledge testing includes:

- TXT ingestion
- PDF ingestion
- DOCX ingestion
- Manual text Knowledge
- Knowledge extraction
- Chunk creation
- Embedding generation
- Exact information retrieval
- Semantic retrieval
- Assistant isolation
- Knowledge deletion
- Account-wide storage limits
- Over-limit rejection
- Downgrade preservation

Scanned or image-only PDF OCR is not part of the current v1 Knowledge feature set.

### AI Quota Testing

Monthly AI quota behaviour has been tested through the live application.

The Free-plan boundary has been verified by reaching **149/150**, successfully processing the final allowed AI message to reach **150/150**, and then confirming that the following request is blocked without increasing the stored usage count.

This verifies the intended boundary behaviour for the account-wide monthly quota system.

### Knowledge Quota Testing

Knowledge storage quota behaviour has also been validated against the hosted application.

An over-limit Knowledge addition was correctly blocked with the applicable plan storage message, while the stored Knowledge count and usage remained unchanged after the rejected operation.

This verifies that an over-limit request does not leave partially persisted Knowledge behind.

### Backend/API Groundwork Testing

Backend/API groundwork validation includes:

- API-key authentication
- Active-account validation
- Pro-plan entitlement
- Request validation
- Assistant ownership
- Conversation ownership
- Protected chat operations
- Plan-restricted access
- Sanitized error responses

Protected backend/API experiments include entitlement and ownership checks. The complete customer-facing API Access product remains part of U5.

### Discord / API Roadmap Validation

Earlier Discord/API experiments and backend tests are development history. The complete customer-facing Discord and API Access package belongs to **U5** and will receive its own end-to-end and regression validation before the affected release.


### Stripe Testing

Stripe subscription functionality has been tested extensively using **Stripe Test Mode**.

Verified development flows include:

- Checkout success
- Checkout cancellation
- Customer billing portal
- New Pro subscription
- Premium pricing presentation
- Pro pricing presentation
- Cancel-at-period-end
- Continued paid access before the subscription boundary
- Keeping an existing Pro subscription
- Subscription downgrade behaviour
- Subscription continuation behaviour
- Paid-to-Free transition behaviour
- Preservation of assistants, conversations, and Knowledge

The current web pricing is:

| Plan | Price |
| --- | ---: |
| **Free** | $0/month |
| **Premium** | $29/month |
| **Pro** | $59/month |

Those payment-flow checks were performed in Stripe Test Mode during development. The **current production web application uses Stripe Live Mode**.

Test credentials, Test Price IDs, test webhooks, and test Checkout configuration remain isolated from the current Live Mode production configuration.

---

## ☁️ Hosted Application Validation

Important backend changes have been deployed and validated against the hosted Heroku application during development.

Hosted verification has included areas such as:

- Monthly AI quota enforcement
- Knowledge storage quota enforcement
- Database migrations
- Free-plan API restriction
- Subscription behaviour
- Knowledge persistence behaviour
- Live application responses after deployment

This remains distinct from release-specific production verification.

Release-specific verification validates the complete production configuration rather than assuming that individually successful development deployments prove every later release.

---

## 🔐 Production Security & Configuration Verification

A dedicated production security/configuration verification remains part of the release process.

The verification covers:

- Complete automated regression suite
- Production Django settings
- `DEBUG=False`
- Allowed hosts
- HTTPS-related production configuration
- Environment variables
- Secret exposure
- Database configuration
- Production Redis connectivity
- Rate-limit configuration
- Test-only routes
- Test-only configuration
- Static-file configuration
- Production migrations
- Heroku configuration
- API protection
- Stripe configuration
- Final hosted smoke testing

Any exposed or partially exposed credentials identified during release verification should be rotated as appropriate.

---

## 💳 Stripe Production Validation

The production web application is already configured with **Stripe Live Mode**.

Development payment-flow testing remains isolated in Stripe Test Mode. Production verification should confirm that Live credentials, Live Price IDs, the production webhook endpoint/signing secret, Checkout configuration, Customer Portal behaviour, subscription entitlement, cancellation, and billing behaviour remain correct after payment-related changes.

Real customer payments must never be used merely to replace tests that can safely be performed in Test Mode.
---

## ✅ Validation Status

The current application has passed the major development-stage tests performed for its implemented v1 functionality, including live verification of the recently completed monthly AI quota and Knowledge storage systems.

The remaining validation work is intentionally concentrated into the final release pass:

    Current backend functionality
              │
              ▼
    Complete regression suite
              │
              ▼
    Production security/config audit
              │
              ▼
    Hosted infrastructure verification
              │
              ▼
    Stripe Live Mode configuration
              │
              ▼
    Production payment configuration verification
              │
              ▼
         Web production release

Release-specific test totals and production-verification results should be documented for the release being validated.

---

# 🛠️ Technology Stack

AI Assistant Platform is built as a Django-based SaaS application with a responsive web frontend, a native Expo/React Native mobile client, OpenAI-powered AI processing, the current Retrieval-Augmented Generation (RAG) implementation, Stripe subscription infrastructure, PostgreSQL persistence, Redis-compatible caching, and protected backend/native APIs. Customer-facing Discord integration and API Access are planned for U5.

The architecture separates user-facing interfaces from backend business rules so authentication, ownership, plan entitlements, quotas, Knowledge retrieval, and AI processing can be reused by supported clients.

---

## 🖥️ Backend

| Technology | Purpose |
| --- | --- |
| Python 3.13 | Core programming language |
| Django 5.2.3 | Main web framework |
| Django REST Framework 3.16.0 | Protected REST API functionality |
| Django ORM | Database abstraction and relational data access |
| Gunicorn 21.2.0 | Production WSGI application server |
| WhiteNoise 6.9.0 | Static-file serving |
| PostgreSQL | Hosted relational database |
| SQLite | Local development and isolated test support |

### Backend Responsibilities

The Django backend is responsible for:

- Authentication
- Account activation
- User profiles
- Assistant CRUD
- Conversation persistence
- AI processing
- Category/domain enforcement
- Knowledge ingestion
- Knowledge retrieval
- Monthly AI quotas
- Knowledge storage quotas
- Request-rate protection
- Usage accounting
- API authentication
- API authorization
- Subscription entitlement
- Stripe webhook processing
- Discord bridge communication (U5 preparatory work)
- Administrative functionality

Important business rules are enforced server-side rather than depending on frontend visibility or client behaviour.

---

## 🎨 Frontend

| Technology | Purpose |
| --- | --- |
| HTML5 | Application structure |
| CSS3 | Styling and responsive layouts |
| JavaScript (ES6) | Client-side interaction |
| AJAX | Asynchronous chat and interface requests |
| Django Templates | Server-rendered application views |

The frontend provides the browser interface for the platform while the Django backend remains authoritative for authentication, authorization, ownership, plans, quotas, and subscription state.

### Frontend Capabilities

The current web client includes:

- Responsive navigation
- Dark and Light themes
- Authentication interfaces
- Assistant management
- AI Playground
- Persistent conversations
- Knowledge management
- Account management
- Analytics
- Subscription and billing interfaces
- Discord setup interfaces (planned U5)
- Protected backend/native API communication
- User feedback and validation messages

The native Android client consumes the same backend platform rather than duplicating these business rules independently.

---

## 🤖 Artificial Intelligence

| Technology | Purpose |
| --- | --- |
| OpenAI `gpt-4o-mini` | AI conversations and domain classification |
| OpenAI `text-embedding-3-small` | Knowledge embeddings |
| Retrieval-Augmented Generation (RAG) | Assistant-specific Knowledge retrieval |
| Exact & lexical retrieval | Direct information matching |
| Semantic retrieval | Meaning-based Knowledge matching |
| Embedding batching | Efficient Knowledge processing |
| Prompt engineering | Assistant behaviour and category enforcement |
| Usage accounting | Request, token, embedding, and estimated-cost tracking |

### AI Processing Architecture

Supported AI requests are routed through shared backend processing rather than allowing each interface to implement independent AI rules.

The processing pipeline can include:

```text
Authenticated Request
        │
        ▼
Ownership Validation
        │
        ▼
  Central AI Service
        │
        ├── Effective plan
        ├── Monthly AI quota
        ├── Request-rate protection
        ├── Category/domain enforcement
        ├── Knowledge retrieval
        ├── Conversation context
        ├── OpenAI request
        └── Usage accounting
        │
        ▼
   AI Response
```

The current AI conversation model is `gpt-4o-mini`.

Knowledge embeddings use `text-embedding-3-small`.

### OpenAI Client

The project currently documents the OpenAI Python package as:

```text
openai==0.28.0
```

The backend therefore uses the API integration style compatible with that package version.

The OpenAI client should not be upgraded casually as part of unrelated maintenance because a major client-version change may require corresponding integration changes and regression testing.

---

## 📚 Knowledge Processing

Knowledge processing supports multiple source formats.

| Technology | Purpose |
| --- | --- |
| PyMuPDF 1.26.1 | PDF text extraction |
| python-docx 1.2.0 | DOCX text extraction |
| UTF-8 text processing | TXT and manual Knowledge |
| NumPy 2.3.1 | Vector and numerical operations |
| OpenAI embeddings | Semantic representation |
| PostgreSQL | Knowledge metadata and chunk persistence |

### Supported Knowledge Sources

The current v1 Knowledge system supports:

- TXT
- PDF with extractable text
- DOCX
- Manual text

Scanned and image-only PDFs are not currently processed through OCR.

Knowledge sources are subject to account-wide storage limits before expensive processing begins.

---

## ⚡ Cache & Rate Limiting

| Technology | Purpose |
| --- | --- |
| Redis 8.1.0 | Redis client/infrastructure component |
| django-redis 7.0.0 | Django Redis cache backend |
| Django LocMemCache | Local development fallback |
| Plan-aware rate limiting | Short-term request protection |

### Current Rate Limits

| Plan | Requests per Minute |
| --- | ---: |
| **Free** | 20 |
| **Premium** | 60 |
| **Pro** | 120 |

Rate limiting is separate from monthly AI message quotas.

Monthly quotas control the amount of AI processing available during the calendar month, while request-rate limits protect the application from rapid bursts of requests.

Production-oriented configuration uses Redis-compatible caching rather than intentionally relying on per-process local memory.

Hosted Redis connectivity should be verified as part of production infrastructure checks whenever the relevant configuration changes.

---

## 💳 Payment Processing

| Technology | Purpose |
| --- | --- |
| Stripe 12.2.0 | Subscription-provider integration |
| Stripe Checkout | Paid-plan Checkout flow |
| Stripe Billing Portal | Customer billing management |
| Stripe Webhooks | Signed subscription-event processing |
| Stripe Test Mode | Isolated development and regression validation |

### Subscription Architecture

Stripe is used for web subscription infrastructure for the paid plans:

| Plan | Web Price |
| --- | ---: |
| **Free** | $0/month |
| **Premium** | $29/month |
| **Pro** | $59/month |

Subscription processing includes backend entitlement logic rather than treating a successful browser redirect as authoritative payment state.

The integration includes:

- Stripe Checkout
- Customer creation and association
- Subscription association
- Signed webhook handling
- Event idempotency
- Billing portal
- Cancellation handling
- Cancel-at-period-end behaviour
- Subscription reconciliation
- Upgrade/downgrade behaviour
- Effective-plan calculation

### Current Payment Environment

The production web application uses **Stripe Live Mode**. Test Mode is reserved for isolated development and regression validation.

Production payment configuration includes the Live publishable/secret keys, Live Premium and Pro Price IDs, production webhook configuration/signing secret, Checkout configuration, and Customer Portal configuration. Payment-related changes should be verified safely in Test Mode first and then smoke-checked against production configuration without creating unnecessary real charges.

---

## 🤖 Discord Integration — U5 Roadmap

The Discord stack below represents the **planned U5 architecture**, not a currently released customer feature.

| Planned Technology | Purpose |
| --- | --- |
| discord.py | Discord bot communication |
| Discord Developer Portal | Customer-owned bot configuration |
| Bring Your Own Bot (BYOB) | Customer-controlled Discord deployment |
| Platform API | Planned bridge communication with Django |

The intended U5 design uses a downloadable/customer-run bridge with the customer's own Discord bot. The complete setup flow, security, diagnostics, entitlement/usage enforcement, documentation, and end-to-end validation remain U5 roadmap work.

---

## 🗄️ Database

| Technology | Purpose |
| --- | --- |
| PostgreSQL | Hosted relational database |
| SQLite | Local development and isolated tests |
| Django ORM | Relational model access |
| Database transactions | Atomic state changes |

PostgreSQL stores application state including:

- Users and profiles
- Assistants
- Conversations
- Chat messages
- Knowledge metadata
- Knowledge chunks
- Knowledge source sizes
- AI usage information
- Subscription-related state
- Stripe event processing state

Database transactions are used where operations require consistent state, including important Knowledge and subscription workflows.

---

## ☁️ Cloud & Deployment

| Technology | Purpose |
| --- | --- |
| Heroku | Production web hosting |
| Heroku-24 | Current application stack |
| PostgreSQL | Hosted relational database |
| Redis-compatible infrastructure | Production cache architecture |
| Gunicorn | Production WSGI server |
| WhiteNoise | Static-file delivery |
| Git | Version control |
| GitHub | Source-code repository and history |

### Hosted Application

The project has an active Heroku deployment.

Production URL:

```text
https://www.myaiassistantapp.se/
```

Recent backend releases, including the account-wide monthly AI quota and account-wide Knowledge storage quota work, have been deployed and validated against the hosted application.

### Heroku Process Model

The production web process is started with Gunicorn:

```text
web: gunicorn ai_assistant.buildabot.wsgi --log-file -
```

The planned U5 Discord architecture does not require a permanent shared Discord worker in the Heroku web process.

### Release Verification

The web application is already live in production. Future releases receive release-specific regression, configuration, infrastructure, and smoke verification.

---

## 🧪 Development & Validation Tools

| Tool | Purpose |
| --- | --- |
| Visual Studio Code | Primary development environment |
| Git | Version control and diff validation |
| GitHub | Repository hosting |
| Heroku CLI | Hosted application management |
| Django Test Framework | Automated backend regression testing |
| Django System Checks | Application/configuration validation |
| Django Migration Checks | Model/migration consistency |
| Postman | API testing |
| Ruff | Python code-quality validation |
| W3C HTML Validator | HTML standards validation |
| W3C CSS Validator | CSS standards validation |
| Lighthouse | Performance, accessibility, best-practices, and SEO auditing |

These tools support both development and release verification rather than replacing application-level regression testing.

---

# 📦 Python Packages

The project uses Python packages for the Django application, AI integration, payments, caching, database connectivity, Discord integration, document processing, deployment, and development tooling.

The versions below reflect the dependency versions currently documented by the project.

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
| gunicorn | 21.2.0 | Production WSGI server |
| whitenoise | 6.9.0 | Static-file serving |
| psycopg2-binary | 2.9.10 | PostgreSQL database adapter |
| dj-database-url | 2.3.0 | Database URL configuration |
| python-decouple | 3.8 | Environment-based configuration |
| discord.py | Managed by `requirements.txt` | Discord integration |
| Pillow | 11.2.1 | Image processing |
| PyMuPDF | 1.26.1 | PDF processing |
| python-docx | 1.2.0 | DOCX processing |
| numpy | 2.3.1 | Vector and numerical operations |
| requests | 2.32.3 | HTTP requests |
| ruff | 0.11.0 | Python code-quality tooling |

---

## Package Notes

### OpenAI

The application currently documents:

```text
openai==0.28.0
```

The existing backend therefore uses the API syntax compatible with that client version.

A future migration to a newer major OpenAI Python client should be handled as a deliberate technical upgrade with corresponding regression testing rather than as an unrelated dependency bump.

### Redis

`django-redis` and `redis` provide the production-oriented cache and rate-limiting architecture.

Local development can use the configured Django local-memory cache where appropriate.

Hosted Redis connectivity will be explicitly checked during the production infrastructure verification.

### Document Processing

Knowledge document support is provided by:

```text
PyMuPDF==1.26.1
python-docx==1.2.0
```

These packages allow the Knowledge pipeline to extract text from supported PDF and DOCX sources.

TXT and manual Knowledge use normal text processing and do not require a dedicated document parser.

### Configuration

Application secrets and service credentials are supplied through environment configuration rather than being committed directly to source control.

Sensitive configuration includes values such as:

- Django secret configuration
- OpenAI credentials
- Stripe credentials
- Stripe webhook secrets
- Database credentials
- Email credentials
- Redis configuration

### Dependency Source of Truth

`requirements.txt` remains the authoritative dependency manifest for the application.

The README documents important dependencies for human readers, but the actual installation set should always be taken from the repository's dependency file.

Before final release, dependency documentation can be compared once more with `requirements.txt` as part of the configuration audit.

---

# 📂 Project Structure

The project is organized using Django's multi-app architecture.

Each application is responsible for a clearly defined area of the platform, helping keep authentication, AI processing, analytics, subscriptions, infrastructure, and user-facing features separated and maintainable.

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

## 📦 Application Responsibilities

The repository is divided into focused Django applications so each major platform domain has a clear place in the codebase.

At a high level:

| Application | Primary Responsibility |
| --- | --- |
| `accounts` | Authentication, user profiles, account state, effective plans, Stripe account references, monthly AI usage state, and public API credentials |
| `bots` | AI assistants, conversations, shared AI processing, domain enforcement, Knowledge/RAG, quotas, rate limiting, public API endpoints, and Discord integration |
| `dashboard` | AI usage records, token and embedding analytics, estimated provider-cost reporting, statistics, and CSV export |
| `payments` | Stripe Checkout, Billing Portal, subscription lifecycle management, webhook processing, reconciliation, and payment-provider validation |
| `buildabot` | Core Django project configuration, URL routing, WSGI/ASGI, cache configuration, environment settings, test configuration, and production checks |

The applications remain separate by responsibility while sharing backend services and account state where platform-wide rules must remain consistent.

Detailed application responsibilities, data relationships, AI request processing, Knowledge architecture, subscription flows, and infrastructure design are documented in the **Architecture** section below.

---

## 🔗 How the Applications Work Together

The individual Django applications remain separated by responsibility but cooperate through shared models, utilities, services, and account state.

A typical AI request can involve several application areas:

```text
User Account
    │
    ▼
accounts
Authentication / Plan State
    │
    ▼
bots
Assistant / Conversation / AI Processing
    │
    ├──────────────► Knowledge Retrieval
    │
    ├──────────────► OpenAI
    │
    ▼
dashboard
Usage & Cost Analytics
```

A paid subscription also connects application areas:

```text
Stripe
  │
  ▼
payments
Subscription State
  │
  ▼
accounts
Effective Plan / Entitlements
  │
  ▼
bots
Feature & Quota Enforcement
```

This separation allows the application to keep payment-provider logic out of the core AI-processing code while still enforcing the correct account entitlement.

---

## 🎯 Why This Structure?

The project follows a modular Django architecture where each application has a focused responsibility.

This provides several benefits:

- Clear separation of concerns
- Easier maintenance
- More focused automated testing
- Reduced duplication
- Reusable backend services
- Easier security auditing
- Easier feature expansion
- Clearer ownership of application logic
- Better support for multiple clients

The architecture is also important for future platform expansion.

For example, the native Android application can reuse the existing account, assistant, conversation, Knowledge, quota, and subscription architecture instead of rebuilding the entire SaaS backend separately.

---

# 🏗️ Architecture

The AI Assistant Platform follows Django's **Model–View–Template (MVT)** architecture and is divided into focused applications for accounts, AI assistants, analytics, payments, and infrastructure.

The backend is designed so the current web and native Android clients reuse the same account, entitlement, Knowledge, conversation, and AI-processing logic. The same architecture is intended to support the customer-facing API and Discord integration planned for U5.

---

## 🧩 High-Level Architecture

```text
                           Clients
                              │
               ┌──────────────┼──────────────┐
               ▼              ▼              ▼
          Web Interface    Public API    Native Android App
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

This architecture keeps the browser and external clients thin while important business rules remain enforced by Django.

Client applications should not decide account entitlement, ownership, quotas, subscription state, or Knowledge isolation independently.

---

## 🧱 Application Architecture

The project is divided into several Django applications, each responsible for a specific platform domain.

### 👤 Accounts

The `accounts` application manages identity, account state, plan information, and authentication/entitlement data used by supported clients. Customer-facing API Access is planned for U5.

#### Responsibilities

- User registration
- Email verification
- Account activation
- Login and logout
- Password reset
- User profiles
- Free, Premium, and Pro account plans
- Effective-plan calculation
- Stripe customer references
- Stripe subscription references
- API authentication/authorization groundwork
- Secure customer API-key rotation planned for U5
- Account-level monthly AI usage state

The account layer provides plan and entitlement information used throughout the rest of the platform.

---

### 🤖 Bots

The `bots` application contains the main AI functionality and assistant-processing architecture.

#### Responsibilities

- AI assistant CRUD
- Assistant ownership validation
- Assistant plan limits
- Shared AI chat service
- Conversation management
- Conversation persistence
- Category and domain enforcement
- OpenAI chat requests
- Knowledge uploads
- TXT processing
- PDF text extraction
- DOCX text extraction
- Manual Knowledge
- Knowledge storage accounting
- Knowledge chunking
- Embedding generation
- Exact and lexical retrieval
- Semantic Knowledge retrieval
- Retrieval-Augmented Generation
- Monthly AI quota enforcement
- Redis-backed rate limiting
- Public API endpoints
- API request validation
- API entitlement/authorization groundwork
- Discord integration
- AI regression testing

The shared chat service centralizes the main AI workflow so supported clients can reuse the same quota, retrieval, conversation, ownership, and assistant-behaviour rules.

---

### 📊 Dashboard

The `dashboard` application records and reports AI activity.

#### Responsibilities

- AI usage logging
- Input-token tracking
- Output-token tracking
- Model tracking
- Estimated AI cost calculations
- Monthly usage reporting
- Analytics
- Usage statistics
- CSV exports

Usage and estimated provider cost are analytics data.

They are not the active customer-facing plan limits.

---

### 💳 Payments

The `payments` application contains the Stripe subscription infrastructure used by the web platform.

#### Responsibilities

- Stripe Checkout
- Premium subscriptions
- Pro subscriptions
- Signed webhook processing
- Subscription synchronization
- Webhook-event idempotency
- Customer validation
- Subscription ownership validation
- Price validation
- Upgrade handling
- Downgrade handling
- Cancel-at-period-end
- Cancellation handling
- Subscription recovery and reconciliation
- Stripe Test Mode workflows

Stripe Test Mode remains available for isolated development/regression work; the production web application uses **Stripe Live Mode**.

Stripe Live Mode is already configured in production and should be revalidated after payment-related production changes.

---

### ⚙️ Buildabot

The `buildabot` package contains the central Django project and infrastructure configuration.

#### Responsibilities

- Django settings
- URL routing
- WSGI configuration
- ASGI configuration
- Redis/cache configuration
- Local cache fallback
- Automated-test settings
- Environment-based configuration
- Production configuration checks
- Error handlers

---

## 🗄️ Data Model

The platform uses Django ORM to manage relationships between users, assistants, conversations, Knowledge sources, Knowledge chunks, usage records, subscriptions, and processed Stripe events.

### Core Relationships

- One user can own multiple AI assistants.
- Each assistant belongs to one user.
- A user can create multiple conversations with an assistant.
- Chat messages can belong to a specific conversation.
- Each assistant can have multiple Knowledge sources.
- Knowledge sources are split into searchable chunks.
- Knowledge chunks contain data required for retrieval.
- Knowledge sources store source-size information for storage accounting.
- AI usage logs record model, token, and usage information.
- User profiles store plan, subscription, and account-level AI usage state.
- Processed Stripe event identifiers are stored for webhook idempotency.

### Account-Wide Limits

Two important customer-facing limits are account-wide rather than assistant-specific.

```text
User Account
    │
    ├── Monthly AI Messages
    │       ├── Free: 150
    │       ├── Premium: 3,000
    │       └── Pro: 10,000
    │
    └── Knowledge Storage
            ├── Free: 10 MB
            ├── Premium: 250 MB
            └── Pro: 1 GB
```

Existing application data is preserved when subscription entitlement changes.

Plan changes affect future access and creation rather than automatically deleting stored assistants, conversations, messages, or Knowledge.

### Database Environments

The application supports SQLite for local development and isolated automated testing.

The hosted application uses the PostgreSQL-oriented production architecture.

---

## 🧠 AI Request Lifecycle

A normal supported AI request follows the shared backend workflow.

```text
User / Client Request
        │
        ▼
Authentication
        │
        ▼
Assistant / Resource Ownership
        │
        ▼
Effective Plan
        │
        ▼
Short-Term Rate Limit
        │
        ▼
Monthly AI Quota Reservation
        │
        ▼
Category / Domain Processing
        │
        ├── Specialized Out-of-Domain Request
        │             │
        │             ▼
        │      Controlled AI Response
        │
        ▼
Knowledge Retrieval
        │
        ├── No Relevant Knowledge
        │             │
        │             ▼
        │     Continue Without Knowledge Context
        │
        ▼
Conversation Context
        │
        ▼
OpenAI Request
        │
        ▼
Persist Usage / Messages
        │
        ▼
Response
```

### Quota Reservation

The monthly AI quota is reserved before AI processing begins.

If processing fails with an exception, the reservation can be released so a failed provider or application operation does not incorrectly consume a successful-message allowance.

A successfully processed AI request consumes the allowance even when a specialized assistant determines that the request is outside its configured domain.

Once the monthly allowance is exhausted, the next AI request is blocked before a new OpenAI chat request is performed.

### Domain Enforcement

Specialized assistants use category and domain controls to remain focused on their configured subject area.

Out-of-domain handling remains part of the controlled AI workflow rather than providing an unrestricted fallback assistant.

### Knowledge Failure Behaviour

Knowledge retrieval can degrade safely when no relevant context is available or when retrieval itself cannot provide usable context.

The assistant can continue according to the applicable assistant rules without using unrelated Knowledge from another assistant.

---

## 📚 Knowledge Processing & Retrieval Flow

Knowledge is processed before it becomes available to an assistant's retrieval pipeline.

Supported v1 sources include TXT, PDF with extractable text, DOCX, and manual text.

```text
Knowledge Source
      │
      ▼
Calculate Source Size
      │
      ▼
Account-Wide Storage Check
      │
      ├── Would Exceed Limit
      │          │
      │          ▼
      │       Reject
      │
      ▼
Extract / Normalize Text
      │
      ▼
Chunk Generation
      │
      ▼
Embedding Generation
      │
      ▼
Embedding Validation
      │
      ▼
Persist Knowledge & Chunks
      │
      ▼
Available for Retrieval
```

The storage check occurs before expensive extraction, chunking, or embedding work.

### Storage Accounting

For uploaded files, the original source file size is used for account-wide Knowledge quota accounting.

For manual Knowledge, UTF-8 encoded text size is used.

Exactly reaching the plan limit is allowed.

Exceeding the plan limit is blocked.

### Retrieval Architecture

Knowledge retrieval uses more than a single semantic comparison.

```text
User Question
      │
      ▼
Query Planning
      │
      ├── Exact Matching
      ├── Lexical Matching
      └── Semantic Matching
      │
      ▼
Candidate Chunks
      │
      ▼
Ranking / Selection
      │
      ├── Document Context
      └── Neighbouring Chunks
      │
      ▼
Relevant Knowledge Context
      │
      ▼
AI Processing
```

Knowledge remains scoped to the selected assistant.

Chunks from another user's assistant or another assistant belonging to the same user must not be injected simply because they are semantically similar.

### OCR Limitation

Scanned or image-only PDFs are not currently processed with OCR in v1.

---

## 🚦 Usage & Rate-Limit Architecture

AI access is protected by separate controls for short-term request bursts and monthly plan usage.

```text
Request
   │
   ▼
Authentication / Ownership
   │
   ▼
Effective Account Plan
   │
   ├── Monthly AI Message Allowance
   │
   └── Requests Per Minute
            │
            ▼
     Shared AI Processing
```

### Monthly AI Allowances

| Plan | AI Messages per Month |
| --- | ---: |
| **Free** | 150 |
| **Premium** | 3,000 |
| **Pro** | 10,000 |

These allowances are account-wide and follow the calendar month.

Changing plan does not reset the existing monthly counter.

### Short-Term Request Limits

| Plan | Requests per Minute |
| --- | ---: |
| **Free** | 20 |
| **Premium** | 60 |
| **Pro** | 120 |

Short-term request limits are separate from monthly AI allowances.

### Cost Tracking

Estimated AI provider cost is still tracked for analytics and operational visibility.

It is not currently used as a customer-facing monthly plan cap.

The plan configuration therefore does not rely on the previous monthly dollar-cost safety limits as active plan entitlement rules.

### Redis

Redis-compatible caching is part of the production rate-limiting architecture.

Local development can use Django's local-memory cache where configured.

Hosted Redis connectivity should be included in production infrastructure verification after relevant configuration changes.

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
  ├── Update Subscription / Plan State
  └── Record Processed Event ID
  │
  ▼
Webhook Response
```

The webhook architecture includes:

- Signature validation
- Event-mode validation
- Event idempotency
- Customer validation
- Subscription ownership validation
- Price validation
- Current-subscription reconciliation
- Stale-event handling
- Retryable provider failure handling

A browser redirect from Stripe is not treated as sufficient proof of subscription state.

Authoritative subscription entitlement is derived from the backend subscription state and validated Stripe events.

---

## 🔄 Upgrade & Downgrade Architecture

Subscription changes are handled without destructively removing user content.

### Upgrade

When a higher plan becomes effective, the account receives the higher plan's applicable limits and features.

### Downgrade

A scheduled downgrade preserves the currently active higher-plan entitlement until the subscription boundary.

When the lower plan becomes effective:

```text
Existing User Data
      │
      ├── Assistants preserved
      ├── Conversations preserved
      ├── Messages preserved
      └── Knowledge preserved
              │
              ▼
       New Lower Plan
              │
              ▼
Future Actions Evaluated
Against Lower Limits
```

For example, if a user has more assistants than the new lower plan allows, the existing assistants remain available but creation of another assistant is blocked until the account is within the plan limit.

The same preservation principle applies to existing Knowledge.

---

## 🔌 External Services

| Service | Purpose |
| --- | --- |
| OpenAI API | AI chat and embedding generation |
| Stripe API | Subscription infrastructure |
| Discord API | User-owned Discord assistant integration |
| Redis | Cache and rate-limiting architecture |
| PostgreSQL | Hosted relational database |
| Heroku | Web application hosting |

### Current Service State

OpenAI is used by the active application for AI processing and embeddings.

Stripe production billing is configured in **Live Mode**. Test Mode is reserved for isolated development and regression validation.

The web application is already deployed on Heroku, including recent monthly AI quota and Knowledge storage changes.

Redis remains part of the configured production-oriented rate-limit architecture and is included in infrastructure verification.

---

## 🔐 Security Boundaries

The architecture applies security at multiple layers.

### Authentication

Protected browser functionality requires an authenticated account.

The public API uses its supported API authentication flow.

### Resource Ownership

Backend ownership validation protects resources such as:

- Assistants
- Conversations
- Messages
- Knowledge

A client-supplied identifier is not sufficient to authorize access to another user's resource.

### Plan Entitlement

Feature access is enforced by backend plan checks.

For example:

- API access is Pro-only.
- Discord integration is Pro-only.
- Assistant creation uses the effective plan's assistant limit.
- AI processing uses the effective plan's monthly AI allowance.
- Knowledge additions use the effective plan's storage allowance.

### Request Protection

The architecture also uses protections including:

- CSRF protection
- API validation
- Rate limiting
- Stripe webhook signatures
- Environment-based secrets
- Production configuration checks
- Sanitized failure handling

Frontend hiding alone is not treated as a security boundary.

---

## 🎯 Architectural Principles

### Separation of Concerns

Each Django application has a focused responsibility, reducing coupling between authentication, AI processing, subscriptions, analytics, and infrastructure.

### Shared Business Logic

Core AI behaviour is centralized in shared backend processing rather than duplicated independently across clients.

### Ownership First

Resources are resolved together with their expected owner wherever appropriate instead of trusting arbitrary object identifiers from a client.

### Account-Wide Entitlements

Monthly AI messages and Knowledge storage are account-level plan resources rather than separate allowances for every assistant.

### Domain Control

Specialized assistants remain restricted to their configured subject areas.

### Knowledge Isolation

Retrieval is scoped so relevant-looking content from the wrong assistant is not used as context.

### Resilience

Knowledge retrieval can degrade gracefully, while important persistence and subscription operations use defensive validation and transactions.

### Usage Control

Monthly AI message allowances and short-term request-rate protection control AI access.

Estimated provider cost remains available for analytics without functioning as an active plan cap.

### Security

Authentication, API-key validation, ownership checks, CSRF protection, webhook signatures, environment-based secrets, plan entitlement, and production configuration checks are integrated throughout the platform.

### Maintainability

Reusable services, isolated configuration, automated regression tests, and Django's modular application structure make the project easier to extend and maintain.

### Future Client Support

The shared backend is designed to support additional clients, including the native Android application, without rebuilding the core SaaS logic separately.

---

## 📌 Documentation Status Convention

To avoid mixing historical development work with released product functionality, this README uses three status concepts:

- **Current** — implemented and part of the presently documented product/client state.
- **Historical** — earlier screenshots, prototypes, tests, or development checkpoints retained for project history.
- **Roadmap** — planned work that must not be presented as released until its upgrade package is completed and shipped.

The U1-U5 items below are **Roadmap** work unless a later release section explicitly marks an upgrade as completed.

---

# 🧭 Product Upgrade Roadmap

The next major product work is organized into complete upgrade packages. Related UI, backend/API work, tests, regression coverage, and release work are grouped together so the same systems are not repeatedly reopened for small disconnected changes.

| Upgrade | Package | Main Direction |
| --- | --- | --- |
| **U1** | Assistant Customization | Personality, instructions, behaviour, appearance, plan-aware controls, and related assistant configuration work |
| **U2** | Knowledge Base / RAG 2.0 | Improved retrieval, embeddings/RAG, multiple documents, assistant-specific Knowledge, isolation, and related usage/storage improvements |
| **U3** | Website Widget / Public Chatbot | Embeddable customer website widget, public visitor chat, per-assistant widget settings, and backend enforcement |
| **U4** | Advanced Customization + Branding | Expanded design/behaviour customization and paid-plan removal of AI Assistant branding where applicable |
| **U5** | Discord Integration + API Access | Discord setup/bridge workflow, connection status and diagnostics, account API keys, assistant invocation, limits, documentation, and examples |

### Upgrade Release Rule

Each package follows the same sequence:

1. Group the main feature with technically related improvements.
2. Implement the complete package.
3. Run focused and regression validation.
4. Deploy/build the affected clients and backend.
5. Perform release smoke testing.
6. Close the upgrade before beginning the next package.

New feature ideas are assigned to the most appropriate not-yet-started upgrade, or to a later upgrade when they do not belong in U1-U5.

---

# 🛣️ Roadmap

AI Assistant Platform has a live production web application and a native Android client distributed through Google Play Closed Testing.

The current core platform includes account management, assistant CRUD/chat, the existing Knowledge/RAG implementation, analytics, plan enforcement, and Stripe Live Mode billing on the web.

The next major product work is organized into the U1-U5 upgrade packages above. Features assigned to those packages are roadmap work and must not be interpreted as already released merely because supporting backend experiments, earlier prototypes, or historical documentation exist.

---

## Completed ✅

### Core Platform

- User registration
- Email verification
- Account activation
- Login and logout
- Password reset
- Authenticated account management
- AI assistant CRUD
- Free, Premium, and Pro account plans
- Plan-aware assistant limits
- Responsive web interface
- Dark and Light themes
- Persistent conversations
- Conversation rename and delete functionality
- Dashboard and analytics
- CSV exports
- Error pages for 400, 403, 404, and 500 responses

### Current Plan Structure

| Plan | Price | Assistants | AI Messages / Month | Knowledge | API | Discord |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| **Free** | $0 | 1 | 150 | 10 MB | No | No |
| **Premium** | $29/month | 5 | 3,000 | 250 MB | No | No |
| **Pro** | $59/month | 15 | 10,000 | 1 GB | Yes | Yes |

Chats are not limited by a separate plan-level conversation count.

Monthly AI messages and Knowledge storage are account-wide resources.

---

### AI Backend

- OpenAI-powered AI chat
- `gpt-4o-mini` conversation model
- Shared chat service
- Specialized assistant categories
- Category and domain enforcement
- Conversation-specific history
- Persistent chat messages
- Account-wide monthly AI message quotas
- Atomic quota reservation
- Quota release on failed processing where applicable
- No quota reset when changing plans
- Token tracking
- Model tracking
- Estimated AI cost accounting
- Graceful backend error handling
- Shared processing architecture for supported clients

The previous daily-plan-message model and monthly dollar-cost plan caps are no longer the active customer-facing entitlement system.

---

### Knowledge & RAG

- Knowledge Base uploads
- TXT support
- PDF text extraction
- DOCX support
- Manual text Knowledge
- Account-wide Knowledge storage quotas
- Source-size accounting
- Quota validation before extraction and embedding work
- Knowledge chunking
- Batched embedding generation
- Embedding response validation
- Exact matching
- Lexical matching
- Semantic retrieval
- Neighbouring-chunk expansion
- Document-aware retrieval
- Retrieval-Augmented Generation (RAG)
- Assistant-level Knowledge isolation
- Graceful fallback when relevant Knowledge is unavailable
- Atomic Knowledge persistence
- Knowledge preservation across subscription downgrades

Current v1 does not provide OCR for scanned or image-only PDFs.

---

### Backend API & Security

- Protected REST endpoints for supported backend/native communication
- API authentication/authorization groundwork
- Secure customer API-key rotation planned for U5
- Active-user validation
- Request-shape validation
- Assistant ownership validation
- Conversation ownership validation
- API entitlement/authorization groundwork
- Customer API-key exposure protection planned for U5
- CSRF protection for browser workflows
- Environment-based secret configuration
- Plan-aware short-term rate limiting
- Redis-backed production rate-limit architecture
- Production cache configuration checks
- Sanitized error handling

Current request-rate limits:

| Plan | Requests per Minute |
| --- | ---: |
| **Free** | 20 |
| **Premium** | 60 |
| **Pro** | 120 |

---

### Discord Integration

- Bring Your Own Bot (BYOB) architecture
- Pro-only Discord entitlement
- Downloadable Discord bridge
- User-owned Discord bot configuration
- Shared Django AI backend
- End-to-end Discord response flow verified
- Planned U5 architecture does not require a permanent shared Discord worker in the Heroku web application

The Discord bridge allows a user's own Discord bot to communicate with the same backend assistant logic used by the platform.

---

### Subscription Backend

- Stripe Checkout
- Premium subscription plan
- Pro subscription plan
- Stripe Billing Portal
- Signed webhook processing
- Webhook signature validation
- Webhook event idempotency
- Subscription state synchronization
- Customer validation
- Subscription ownership validation
- Price validation
- Upgrade handling
- Scheduled downgrade handling
- Cancel-at-period-end handling
- Subscription cancellation
- Subscription recovery/reconciliation
- Stale-event handling
- Retryable provider-failure handling
- Effective-plan calculation
- Stripe Test Mode workflow validation

### Non-Destructive Downgrades

Subscription downgrades preserve existing user-created content.

This includes:

- Assistants
- Conversations
- Chat messages
- Knowledge

If the new lower plan has stricter limits, future creation or addition operations can be blocked until the account is within those limits.

Existing content is not automatically deleted merely because entitlement changes.

---

### Testing & Quality

Development validation has included automated and live regression coverage for areas such as:

- Authentication
- Account flows
- AI chat
- Category enforcement
- Conversation isolation
- Knowledge processing
- Knowledge retrieval
- Knowledge quotas
- Monthly AI quotas
- API security
- API entitlement
- Usage accounting
- Rate limiting
- Subscription handling
- Stripe webhooks
- Downgrade behaviour
- Content preservation

Recent focused verification has included passing account, bot, payment, Knowledge, and continuation regression suites.

Release-specific regression results should be documented for the release being validated.

Additional development checks have included:

- Django system checks
- Migration consistency checks
- Ruff validation
- Hosted boundary testing
- Live API entitlement checks
- Stripe Test Mode workflow testing

---

## Current Release Work 🚧

The remaining work before the web v1.0 release is intentionally narrow.

### 1. Final Regression Audit

Run the complete final regression pass against the release candidate.

This includes:

- Full automated test suite
- Django system check
- Migration consistency check
- Ruff validation
- Final regression verification for recently completed systems
- Hosted smoke tests

The final project-wide test count should be recorded only after this pass has completed.

### 2. Production Security & Configuration Audit

Verify the final production environment, including:

- `DEBUG=False`
- Production hosts
- HTTPS-related configuration
- Environment variables
- Secret handling
- Database configuration
- Test-only routes
- Test-only configuration
- Static-file configuration
- API protection
- Error handling
- Heroku configuration
- Production Redis connectivity
- Deployment configuration

Any partially exposed test credentials identified during the audit should be rotated before the affected release.

### 3. Stripe Production Verification

Stripe Live Mode is already active in production; payment-related releases should verify the production configuration after safe Test Mode regression testing.

Payment-related production verification includes:

- Live publishable key
- Live secret key
- Live Premium Price ID
- Live Pro Price ID
- Live webhook endpoint
- Live webhook signing secret
- Production Checkout configuration
- Production Billing Portal configuration
- Confirmation that Test Mode values are not used by production
- Safe production smoke verification without unnecessary real charges

The production platform already uses Live Mode; payment-related changes must preserve a valid, isolated production configuration.

### 4. Web Production Release

The web application is already live. Future web releases follow the same regression, security, configuration, infrastructure, payment (when affected), deployment, and smoke-verification discipline.

---

## Current Native Android Client ✅

### Android Application

The Android client is now implemented as a dedicated **Expo / React Native** application and is distributed through **Google Play Closed Testing (Alpha)**.

Current release information:

- Package: `com.mrhusse.aiassistant`
- `versionCode 4`
- `versionName 1.0.0`
- Play release: `1.2 - Native Bug Fixes`
- Shared production Django backend
- Shared accounts, assistants, conversations, Knowledge, usage, analytics, and entitlement rules
- Native authentication, Dashboard, Analytics, assistant management/chat, Knowledge access, and Account functionality

The current v4 release includes Android chat/keyboard layout fixes and Analytics date/Message Count fixes.

Google Play Billing and broader store-launch work remain separate from the fact that the native client itself is already implemented and in Closed Testing.

---

## Planned v2 Platform Improvements 📌

These features are intentionally outside the current v1 launch scope.

### Knowledge Update / Replace

A future Knowledge-management improvement can allow users to replace an existing Knowledge source without manually deleting and recreating it.

A potential workflow is:

```text
Existing Knowledge Source
          │
          ▼
Select Replace / Update
          │
          ▼
Upload New Version
          │
          ▼
Remove Old Chunks
          │
          ▼
Re-extract Content
          │
          ▼
Rebuild Embeddings
          │
          ▼
Updated Knowledge Source
```

This is separate from the current snapshot-style upload behaviour.

### User Experience Improvements

Potential v2 improvements include:

- Auto-dismissed flash messages
- Expanded customer-facing usage notifications
- Improved billing dashboard
- More detailed API documentation
- Assistant version history

### Future Knowledge Sources

Possible later Knowledge integrations include:

- Google Drive
- Dropbox
- URLs
- Websites
- Other synchronized external sources

These would require synchronization and update semantics beyond the current uploaded-source model.

---

## Longer-Term Platform Ideas 🚀

Potential longer-term expansion includes:

- AI image generation
- Voice conversations
- Speech-to-text
- Text-to-speech
- Expanded document analysis
- Additional AI models
- Team workspaces
- Shared assistants
- Public assistant marketplace
- Two-factor authentication
- OAuth login
- Multi-language interface
- Custom domains
- Additional external integrations
- Expanded monitoring
- Additional deployment options

These are future product possibilities rather than committed v1 functionality.

---

## Infrastructure Evolution

Future infrastructure work can include:

- Redis monitoring
- PostgreSQL monitoring
- Deployment monitoring
- Expanded automated integration testing
- Docker support
- Additional deployment targets where justified
- Operational alerting
- Performance monitoring

Redis connectivity is production infrastructure and should be revalidated after relevant hosted configuration changes.

---

## Long-Term Vision 🚀

The long-term goal is to develop AI Assistant Platform into a commercially viable multi-client AI service where individuals and businesses can create, customize, equip with their own Knowledge, and manage specialized AI assistants.

The web platform and native Android application are designed to share the same:

- Django backend
- User accounts
- Assistants
- Conversations
- Chat history
- Knowledge
- Plan entitlement
- Usage controls
- AI infrastructure

Future clients and integrations can extend the platform without duplicating the core AI business logic.

The intended progression is:

```text
Web v1.0
   │
   ▼
Android Client
   │
   ▼
Knowledge & UX v2 Improvements
   │
   ▼
Additional Integrations
   │
   ▼
Broader Multi-Client Platform
```

---

# ⭐ Why This Project?

Many AI projects stop at a basic chatbot interface.

AI Assistant Platform was designed as a broader SaaS-style product where users can create, configure, equip, and manage specialized AI assistants from one account.

Instead of treating every assistant as an unrestricted general-purpose chatbot, the platform combines focused AI behaviour, custom Knowledge retrieval, persistent conversations, account-level quotas, subscriptions, APIs, analytics, and external integrations behind a shared Django backend.

The result is not only an AI chat interface, but a complete application architecture designed around real account ownership, entitlement, usage, persistence, security, and future multi-client support.

---

## What Makes This Project Different?

- 🤖 Specialized AI assistants powered by OpenAI
- 🎯 Category and domain enforcement
- 📚 Custom Knowledge Base
- 📄 TXT, PDF, DOCX, and manual Knowledge support
- 🧠 Retrieval-Augmented Generation (RAG)
- 🔎 Exact, lexical, and semantic Knowledge retrieval
- 💬 Persistent and isolated conversations
- 🔄 Shared AI-processing architecture
- 📊 Token, model, usage, and estimated-cost analytics
- 🚦 Account-wide monthly AI quotas
- 📦 Account-wide Knowledge storage quotas
- ⚡ Plan-aware short-term rate limiting
- 🔐 Customer API-key authentication planned for U5
- 🛡️ Ownership and entitlement validation
- 💳 Free, Premium, and Pro plan architecture
- 💳 Stripe subscription infrastructure
- 🔁 Non-destructive subscription downgrades
- 🎮 Discord integration through Bring Your Own Bot
- 📈 Analytics and usage reporting
- 🌙 Dark and Light themes
- 📱 Responsive web interface
- 🧩 Modular Django architecture
- 📲 Native Android client using the same backend and account data

---

## Main Goals

The project was created to demonstrate full-stack software engineering while building a platform capable of developing into a real commercial service.

Key goals include:

- Building a maintainable and extensible Django backend
- Creating useful specialized AI assistants
- Integrating OpenAI chat and embedding services
- Implementing reliable Knowledge retrieval
- Managing persistent conversations and assistant-specific context
- Enforcing account-level AI usage limits
- Enforcing account-level Knowledge storage limits
- Tracking technical AI usage and estimated operating cost
- Protecting AI infrastructure with rate limiting
- Designing secure authentication and public API access
- Implementing subscription and entitlement infrastructure
- Preserving user data safely across plan changes
- Integrating external services without duplicating core business logic
- Supporting multiple clients from the same backend
- Maintaining automated regression coverage as the platform grows
- Preparing the web application for commercial production release

---

## Target Users

The platform is designed for users who want focused AI assistants without having to build the complete AI infrastructure themselves.

Potential users include:

- Developers
- Small businesses
- Discord communities
- Content creators
- Technical communities
- Specialist communities
- Teams working with their own Knowledge
- Individuals who want to create and manage specialized assistants

The longer-term product direction is for the same account, assistants, conversations, Knowledge, plan entitlement, and backend services to be available across the web platform and native Android client.

---

# ⚡ Challenges & Lessons Learned

Building AI Assistant Platform required solving engineering problems across AI integration, data consistency, retrieval quality, account limits, security, subscriptions, caching, usage accounting, external services, and deployment.

As the project developed from a web-based assistant builder into a larger SaaS platform, several earlier implementations had to be redesigned rather than simply extended.

That process became one of the most important parts of the project.

---

## Major Challenges

### 🧠 Building a Shared AI Chat Architecture

One important challenge was preventing AI behaviour from becoming duplicated across different interfaces.

The chat workflow was therefore centralized into shared backend processing responsible for areas such as:

- Authentication context
- Ownership validation
- Effective-plan checks
- Monthly AI quota enforcement
- Rate-limit enforcement
- Category/domain processing
- Knowledge retrieval
- Conversation history
- OpenAI requests
- Usage accounting
- Message persistence
- Consistent error handling

This creates a single backend workflow that can be reused by supported clients.

```text
Web
 │
 ├──────────────┐
 │              │
Public API      │
 │              │
Discord         │
 │              │
 └──────┬───────┘
        ▼
Shared Backend Logic
        │
        ▼
OpenAI / Knowledge / Database
```

The same approach also provides a foundation for the native Android client.

---

### 🎯 Keeping Specialized Assistants in Their Domain

Allowing every assistant to answer every question would reduce the value of creating specialized assistants.

Category-aware domain enforcement was introduced so assistants can remain focused on their intended subject area.

This required balancing:

- Strong domain boundaries
- Useful assistant behaviour
- False-rejection risk
- Classification cost
- General-purpose assistant behaviour
- Consistency across supported clients

General-purpose categories can bypass unnecessary domain classification when strict category enforcement is not required.

This avoids unnecessary processing while allowing specialized assistants to remain focused.

---

### 📚 Building Reliable Knowledge Retrieval

The Knowledge system evolved significantly beyond simply storing uploaded text.

The final v1 retrieval architecture needed to support:

- TXT input
- PDF text extraction
- DOCX extraction
- Manual text
- Text normalization
- Chunk generation
- Embedding generation
- Embedding validation
- Exact matching
- Lexical matching
- Semantic matching
- Candidate ranking
- Neighbouring-chunk expansion
- Document context
- Assistant-level Knowledge isolation
- Retrieval fallback behaviour

A particularly important lesson was that successful communication with an external API does not automatically mean that the returned data should be trusted and persisted without validation.

Embedding responses are therefore validated before final persistence.

---

### 🔎 Improving Retrieval Beyond Semantic Search

Pure semantic similarity was not sufficient for every Knowledge question.

Exact identifiers, names, codes, phrases, product references, archive entries, and similar information can benefit from lexical and exact retrieval in addition to embeddings.

The retrieval architecture therefore evolved toward a combined strategy.

```text
Question
   │
   ▼
Query Analysis
   │
   ├── Exact matching
   ├── Lexical matching
   └── Semantic matching
   │
   ▼
Candidate Ranking
   │
   ▼
Neighbour / Document Context
   │
   ▼
Relevant Knowledge
```

This produces a more robust retrieval system than relying exclusively on vector similarity.

---

### 📦 Account-Wide Knowledge Storage

Knowledge storage also introduced a product-level quota problem.

The platform needed storage limits to apply to the user's account as a whole rather than giving every assistant an independent full allowance.

Current limits are:

| Plan | Knowledge Storage |
| --- | ---: |
| **Free** | 10 MB |
| **Premium** | 250 MB |
| **Pro** | 1 GB |

An important design requirement was preventing unnecessary expensive work when an upload is already too large for the remaining allowance.

The workflow therefore checks source size before:

- Text extraction
- Chunk generation
- Embedding generation

Exactly reaching the storage limit is allowed.

Going beyond the limit is blocked.

---

### 🔒 Atomic Knowledge Uploads

Knowledge ingestion combines external API operations with database persistence.

A failure after only part of an upload had been saved could otherwise leave incomplete Knowledge or orphaned data.

The workflow was designed so that:

- Source quota is checked before expensive processing
- Embeddings are generated before final persistence
- Embedding output is validated
- Parent Knowledge records and chunks are persisted consistently
- Database operations use transactional protection where required
- Failed persistence does not intentionally leave a partially completed Knowledge source

This improves both data integrity and predictable quota behaviour.

---

### 💬 Conversation Isolation

Persistent AI chat required more than storing all messages directly against an assistant.

Separate conversations allow users to:

- Start a new conversation
- Return to an earlier conversation
- Rename conversations
- Delete conversations
- Keep unrelated discussions separate

Ownership validation is also required so one account cannot access another user's conversations through manipulated identifiers or API requests.

---

### 📊 AI Usage and Cost Accounting

AI processing has a real provider cost, so technical usage accounting became an important backend requirement.

The platform records information including:

- Input tokens
- Output tokens
- Total token usage
- Model information
- AI request activity
- Embedding activity
- Estimated AI cost

This information is useful for:

- Analytics
- Operational visibility
- Business analysis
- Usage reporting
- Future pricing decisions

Estimated provider cost is **not** the active customer-facing plan cap.

The current plan entitlement uses account-wide monthly AI message limits instead.

---

### 🚦 Designing Monthly AI Quotas

The platform originally used a different usage-control model.

The current system instead uses clear account-wide monthly message allowances:

| Plan | AI Messages / Month |
| --- | ---: |
| **Free** | 150 |
| **Premium** | 3,000 |
| **Pro** | 10,000 |

This required more than checking a number before sending a response.

The implementation needed to consider:

- Account-wide counting
- Calendar-month usage
- Atomic quota reservation
- Failed AI processing
- Plan changes during a month
- Successful out-of-domain processing
- Blocking before additional AI work once exhausted

Changing plans does not reset the user's current monthly counter.

If processing fails with an exception after quota reservation, the reservation can be released where appropriate.

---

### 🚦 Rate Limiting and Redis

Monthly quotas solve a different problem from short-term request bursts.

The application therefore also applies plan-aware requests-per-minute protection:

| Plan | Requests / Minute |
| --- | ---: |
| **Free** | 20 |
| **Premium** | 60 |
| **Pro** | 120 |

A local-memory cache is useful during development, but it is process-local and unsuitable as the intended production-wide shared limiter.

The Redis-oriented architecture therefore required attention to:

- Redis URL configuration
- `redis://` and secure `rediss://` handling
- Connection timeouts
- Explicit failure behaviour
- Production configuration checks
- Local development fallback
- Rate-limit behaviour

The Redis architecture and automated coverage are implemented.

Hosted Redis connectivity remains part of production infrastructure verification.

---

### 💳 Stripe Subscription State

Subscription handling became significantly more complex than creating a Stripe Checkout Session.

The backend needed to handle:

- Premium and Pro subscriptions
- Checkout completion
- Subscription upgrades
- Subscription downgrades
- Scheduled downgrade behaviour
- Scheduled cancellation
- Cancellation
- Subscription recovery
- Duplicate webhook delivery
- Stale webhook events
- Customer ownership
- Subscription ownership
- Price validation
- Provider failures

Signed webhook events are validated and processed defensively.

Processed event identifiers support idempotency so repeated delivery does not intentionally duplicate state transitions.

The production web application uses **Stripe Live Mode**; Test Mode is isolated for development and regression validation.

---

### 🔄 Safe Subscription Downgrades

A particularly important product decision was preventing downgrades from destroying user content.

A user can move to a plan whose limits are lower than the amount of content already stored.

The chosen behaviour is:

```text
Plan Downgrade
      │
      ▼
Existing Content Preserved
      │
      ├── Assistants
      ├── Conversations
      ├── Messages
      └── Knowledge
      │
      ▼
Future Actions Use New Limits
```

For example, a user who already has more assistants than the new plan allows does not lose those assistants.

Creating additional assistants is blocked until the account is within the new plan's limit.

This separates entitlement from destructive data deletion.

---

### 🔐 Customer API Security — Planned U5

Customer-facing API Access belongs to **U5**. Earlier API authentication/authorization work provides useful backend groundwork, but the complete customer API must not be described as generally available until U5 is released.

The planned security model includes account API keys, active-user and entitlement checks, strict request validation, assistant/conversation ownership checks, usage/rate limits, safe errors, key rotation, and protection against credential exposure in logs, admin interfaces, templates, and client code.
---

### 🎮 Discord Integration — Planned U5

The BYOB Discord architecture documented during development is preparatory work for **U5**, not a claim that the complete customer feature is currently released.

The intended flow remains: customer-owned Discord bot → bridge/API path → Django backend → shared AI service. The complete setup workflow, security, diagnostics, entitlement/usage enforcement, documentation, and end-to-end release validation belong to U5.
---

### ☁️ Deployment and Environment Differences

Local development and hosted production environments require different infrastructure choices.

Areas requiring particular attention included:

- Static files
- Database configuration
- Environment variables
- Secret management
- HTTPS behaviour
- `DEBUG` configuration
- Cache configuration
- Hosted service configuration
- Production checks
- External credentials

The Heroku deployment has already been updated with recent backend work, including the monthly AI quota and Knowledge storage changes.

Future deployment work uses **release-wide verification** rather than treating production readiness as a one-time assumption.

---

## Lessons Learned

Working on this project significantly improved practical understanding of:

- Django application architecture
- Service-layer design
- REST API design
- Authentication and authorization
- Object ownership
- API-key security
- Subscription entitlement
- AI prompt engineering
- Category-aware AI behaviour
- Retrieval-Augmented Generation
- Embeddings
- Exact and lexical retrieval
- Semantic retrieval
- Conversation architecture
- Account-wide quota design
- Transactional database operations
- AI token and cost accounting
- Redis caching and rate limiting
- Stripe subscription lifecycle management
- Webhook security
- Webhook idempotency
- External API failure handling
- Automated regression testing
- Environment configuration
- Secret management
- Cloud deployment
- Maintaining a growing multi-application codebase

---

## Biggest Takeaway

The biggest lesson from the project is that building a reliable AI product involves much more than sending prompts to an AI model.

The surrounding platform must:

- Authenticate users
- Enforce ownership
- Protect secrets
- Isolate user data
- Manage plan entitlement
- Control AI consumption
- Validate external responses
- Retrieve relevant Knowledge
- Persist data safely
- Track operational usage
- Handle subscriptions
- Recover safely from failures
- Remain maintainable as the product grows

Automated testing also became increasingly important as the platform expanded.

Changes to AI behaviour, payments, caching, Knowledge retrieval, quotas, APIs, or account entitlement can affect multiple parts of the system.

Regression coverage therefore became part of the development architecture rather than something left only for the end of the project.

---

# 💡 Design Decisions

Throughout development, architectural and technical decisions have been made to keep the platform maintainable, secure, testable, and capable of supporting additional clients.

---

## Django MVT

The platform follows Django's **Model–View–Template (MVT)** architecture.

Django provides the foundation for:

- Data models
- Views
- Request handling
- Templates
- Authentication
- Database access
- URL routing
- Administrative tools

Shared business logic is moved into dedicated services and utilities instead of being duplicated across multiple views and interfaces.

---

## Multi-App Architecture

The platform is divided into focused Django applications.

The main application areas include:

- Accounts
- Bots
- Dashboard
- Payments
- Project/infrastructure configuration

This provides:

- Clear separation of responsibility
- Smaller modules
- Easier testing
- Reduced coupling
- Better maintainability
- Easier expansion

---

## Shared Chat Service

The core AI workflow is centralized rather than maintaining independent implementations for every interface.

The shared processing path coordinates areas such as:

- Authentication context
- Ownership
- Effective plan
- Monthly AI quota
- Rate limiting
- Category enforcement
- Knowledge retrieval
- Conversation context
- OpenAI processing
- Usage accounting
- Persistence

This allows supported clients to use the same backend rules.

---

## Specialized Assistants

Assistants are designed around categories and intended domains rather than behaving as unrestricted general-purpose chatbots by default.

Domain enforcement helps specialized assistants remain focused.

General-purpose categories can avoid unnecessary classification where strict subject enforcement is not required.

---

## Conversation-Based History

Chat history is separated into conversations rather than treating every message sent to one assistant as a single permanent thread.

Users can therefore:

- Start separate conversations
- Return to previous conversations
- Rename conversations
- Delete conversations
- Keep unrelated topics isolated

Conversation access is also protected by ownership validation.

---

## Retrieval-Augmented Generation

Custom assistant Knowledge uses Retrieval-Augmented Generation rather than model fine-tuning.

The v1 pipeline is conceptually:

```text
Knowledge Source
      │
      ▼
Source-Size Validation
      │
      ▼
Text Extraction / Normalization
      │
      ▼
Chunking
      │
      ▼
Embeddings
      │
      ▼
Exact / Lexical / Semantic Retrieval
      │
      ▼
Relevant Context
      │
      ▼
AI Response
```

Only selected relevant Knowledge is added to the AI context.

This avoids unnecessarily injecting the complete Knowledge Base into every request.

---

## Multiple Knowledge Source Types

The v1 Knowledge system supports:

- TXT
- PDF with extractable text
- DOCX
- Manual text

Scanned and image-only PDFs are not currently processed with OCR.

Uploaded documents behave as snapshots of the content processed at upload time.

Changing an original local document does not automatically update the Knowledge already stored by the platform.

---

## Account-Wide Knowledge Quotas

Knowledge allowance belongs to the account rather than being reset for each assistant.

| Plan | Storage |
| --- | ---: |
| **Free** | 10 MB |
| **Premium** | 250 MB |
| **Pro** | 1 GB |

Source size is checked before extraction, chunking, and embedding work.

This protects both infrastructure and provider cost while giving users one understandable account-level storage allowance.

---

## Batched and Validated Embeddings

Embedding requests are batched instead of requiring an independent request for every chunk.

Returned embedding data is validated before persistence.

Validation can include areas such as:

- Response indices
- Vector values
- Finite numerical values
- Expected dimensions
- Expected response count

The system should not blindly assume that an external response is valid simply because the API call succeeded.

---

## Atomic Knowledge Persistence

Knowledge persistence is designed to avoid partially completed uploads.

Embedding work and validation occur before final persistence, and database operations use transactional handling where required.

This reduces the risk of incomplete Knowledge records remaining after a failure.

---

## Graceful Retrieval Failure

Knowledge enrichment should not necessarily make all AI chat unavailable if retrieval itself fails.

The shared backend can continue without retrieved Knowledge context where appropriate while respecting the assistant's remaining behaviour and domain rules.

Knowledge from unrelated assistants is not used as a fallback.

---

## AI Usage Accounting

Technical AI activity is recorded because provider usage matters operationally and commercially.

Tracked information includes:

- Input tokens
- Output tokens
- Total tokens
- Model information
- Request activity
- Embedding activity
- Estimated cost

This supports analytics and operational visibility.

It is separate from the account's customer-facing monthly message quota.

---

## Plan-Aware Usage Controls

The current plan model separates three different concepts:

```text
Plan Entitlement
      │
      ├── Assistant Limit
      ├── Monthly AI Message Allowance
      ├── Knowledge Storage Allowance
      ├── Feature Access
      └── Requests-per-Minute Protection
```

Current limits are:

| Plan | Assistants | AI / Month | Knowledge | Requests / Minute |
| --- | ---: | ---: | ---: | ---: |
| **Free** | 1 | 150 | 10 MB | 20 |
| **Premium** | 5 | 3,000 | 250 MB | 60 |
| **Pro** | 15 | 10,000 | 1 GB | 120 |

The old daily-message and monthly-dollar-cost plan caps are not the current entitlement model.

---

## Redis for Shared Rate Limiting

Django's local-memory cache is suitable as a development fallback but is process-local.

A shared Redis-compatible cache is therefore the intended production architecture for consistent request-rate protection across application processes.

The configuration includes areas such as:

- Redis URL validation
- Connection timeouts
- Secure `rediss` handling
- Production configuration checks
- Explicit cache behaviour

Final hosted Redis connectivity verification remains part of the release audit.

---

## Database Strategy

SQLite supports local development and isolated automated testing.

The hosted environment uses the PostgreSQL-oriented production architecture through Django ORM.

This keeps local development straightforward while providing a relational production database suitable for the deployed application.

---

## Stripe Checkout and Webhooks

Stripe provides the web subscription infrastructure.

Checkout begins the customer subscription process, while backend subscription state and signed webhook events determine effective entitlement.

The webhook design includes:

- Signature validation
- Mode validation
- Customer validation
- Subscription ownership validation
- Price validation
- Event idempotency
- Transactional updates
- Stale-event reconciliation
- Retryable provider failures

The production web application uses **Stripe Live Mode**; Test Mode remains isolated for development and regression validation.

Live Mode is already active in production and remains subject to release-specific configuration verification.

The native Android client is implemented. Android in-app subscription purchasing is planned to use Google Play Billing, with backend entitlement synchronization keeping account access consistent.

---

## Non-Destructive Plan Changes

Subscription state and stored customer content are deliberately separated.

A downgrade can reduce future entitlement without automatically deleting existing:

- Assistants
- Conversations
- Messages
- Knowledge

Future creation and additions are evaluated against the newly effective plan.

This avoids surprising destructive behaviour during subscription changes.

---

## Customer API Keys — Planned U5

Dedicated customer API-key management is planned for **U5 — Discord Integration + API Access**.

Earlier API-key models, endpoints, or security experiments should be treated as preparatory/historical backend work. The released U5 package is intended to include account key management and rotation, assistant invocation, ownership and entitlement enforcement, usage/rate limits, safe errors, documentation, and examples.

The server-side OpenAI credential remains a separate secret and must never be exposed as a customer API key.
---

## Environment-Based Secrets

Sensitive credentials are not intended to be committed directly to source control.

Environment configuration is used for values such as:

- Django secret configuration
- OpenAI API credentials
- Stripe credentials
- Stripe webhook secrets
- Database configuration
- Redis configuration
- Email credentials

Secret handling remains part of ongoing production and release verification.

---

## Bring Your Own Bot (BYOB) — Planned U5

BYOB is the planned direction for the **U5 Discord integration**. Customers are intended to connect their own Discord bot while the primary AI processing remains inside Django.

The complete customer-facing bridge/setup workflow is roadmap work until U5 has been implemented, tested end-to-end, deployed, and released.
---

## Responsive Web Interface

The web interface is designed to work across:

- Desktop
- Laptop
- Tablet
- Mobile browsers

Responsive layouts keep the web client usable across device sizes. A dedicated Expo/React Native Android client is already implemented and distributed through Google Play Closed Testing.

---

## Automated Regression Testing

As the backend grew, automated regression testing became a core engineering requirement.

Coverage includes important areas such as:

- Authentication
- AI chat behaviour
- Category enforcement
- Knowledge retrieval
- Knowledge quotas
- Embedding validation
- Conversation isolation
- Monthly AI quotas
- Usage accounting
- API security
- API entitlement
- Rate limiting
- Redis configuration
- Stripe subscriptions
- Stripe webhooks
- Downgrade behaviour

Intermediate targeted-suite counts are not treated as the final project-wide regression total.

A complete test count should be recorded for any future release-wide regression run.

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
- Ownership enforcement
- Account-level entitlement
- Automated regression coverage
- Separation between development, test, and production configuration
- Avoiding unnecessary duplication between clients

These decisions allow the platform to evolve without requiring a separate implementation of the core backend for every interface.

---

# 🚀 Installation

Follow the steps below to set up AI Assistant Platform for local development.

The production application has separate Heroku configuration, hosted services, and credentials. Local setup should use development or Test Mode credentials and must not modify production configuration unintentionally.

---

## 📋 Prerequisites

Before getting started, ensure that you have:

- Python 3.13
- Git
- pip
- An OpenAI API key for AI functionality

Optional integrations additionally require:

- A Stripe account for Test Mode payment testing
- A Discord Developer account for Discord integration
- Redis if you want to test the shared Redis-backed cache/rate-limit configuration locally

SQLite can be used for normal local development and isolated automated testing.

The hosted production architecture uses PostgreSQL and Redis-compatible infrastructure, but these services are not required for the most basic local development workflow.

---

## 📥 Clone the Repository

Clone the GitHub repository:

```bash
git clone https://github.com/God-zil-la/Project-4.git
```

Navigate into the project directory:

```bash
cd Project-4
```

---

## 🐍 Create a Virtual Environment

Using a virtual environment keeps project dependencies isolated from the global Python installation.

### Windows PowerShell

Create the environment:

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

### macOS / Linux

Create the environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

---

## 📦 Install Dependencies

Install the project dependencies from `requirements.txt`:

```bash
pip install -r requirements.txt
```

The documented development environment currently uses Python 3.13 and Django 5.2.3.

`requirements.txt` remains the dependency source of truth.

---

## ⚙️ Configure Environment Variables

Application secrets and external-service credentials are supplied through environment configuration.

The documented local workflow does **not** require credentials to be committed to the repository.

At minimum, AI functionality requires:

```text
OPENAI_API_KEY
```

Other environment values used by the application can include configuration for:

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

Additional Stripe price/configuration values may also be required when testing subscription functionality, depending on the current project configuration.

Never commit real:

- API keys
- Passwords
- Stripe secrets
- Webhook signing secrets
- Database credentials
- Redis credentials
- Email credentials
- Production service secrets

to the repository.

### Windows PowerShell Example

Environment variables can be supplied for the current PowerShell session:

```powershell
$env:DJANGO_DEBUG="True"
$env:OPENAI_API_KEY="your-development-key"
```

Use development credentials locally.

Do not copy production secrets into source files or example documentation.

---

## 🗄️ Local Database Setup

Apply Django migrations to the configured local database:

```bash
python manage.py migrate
```

This creates or updates the schema required by the current application code.

Production migrations should be handled as part of a controlled deployment process rather than by pointing an ordinary local development session at the production database.

---

## 👤 Create an Administrator Account

To create a local Django administrator:

```bash
python manage.py createsuperuser
```

Follow the Django prompts to create the account.

The Django Admin interface should be used only by authorized administrators.

---

## ▶️ Run the Development Server

Start the Django development server:

```bash
python manage.py runserver
```

The application is normally available locally at:

```text
http://127.0.0.1:8000/
```

Django's development server uses HTTP by default.

Do not assume that `https://127.0.0.1:8000/` is available unless a separate local HTTPS environment has explicitly been configured.

---

## 🔑 OpenAI Configuration

AI conversations and Knowledge embeddings require a valid OpenAI API key.

The current application uses:

- `gpt-4o-mini` for AI conversations and relevant classification work
- `text-embedding-3-small` for Knowledge embeddings

The documented OpenAI Python client version is:

```text
openai==0.28.0
```

The existing backend therefore follows the integration style supported by that client version.

OpenAI credentials must remain server-side.

Do not expose the OpenAI API key directly to:

- Browser JavaScript
- Public templates
- Android clients
- Discord users
- Public APIs
- Logs or error responses

Clients communicate with the Django backend rather than directly receiving the platform's OpenAI credential.

---

## 📚 Knowledge Configuration

Knowledge functionality requires OpenAI configuration because embeddings are generated as part of the ingestion pipeline.

Current v1 Knowledge sources include:

- TXT
- PDF with extractable text
- DOCX
- Manual text

Scanned or image-only PDFs are not currently processed with OCR.

### Knowledge Processing

The ingestion pipeline includes:

```text
Knowledge Source
      │
      ▼
Source-Size Calculation
      │
      ▼
Account Storage Quota Check
      │
      ▼
Text Extraction / Normalization
      │
      ▼
Chunking
      │
      ▼
Embedding Generation
      │
      ▼
Embedding Validation
      │
      ▼
Database Persistence
```

The storage quota check is performed before expensive extraction, chunking, and embedding operations.

### Current Knowledge Limits

| Plan | Account-Wide Knowledge |
| --- | ---: |
| **Free** | 10 MB |
| **Premium** | 250 MB |
| **Pro** | 1 GB |

Exactly reaching the configured limit is allowed.

Exceeding it is blocked.

### Retrieval

Knowledge retrieval can use:

- Exact matching
- Lexical matching
- Semantic matching
- Ranking
- Neighbouring chunks
- Relevant document context

Knowledge remains scoped to the correct assistant and owner.

---

## 🚦 Monthly AI Quotas

AI message entitlement is account-wide and based on the current effective plan.

| Plan | AI Messages / Month |
| --- | ---: |
| **Free** | 150 |
| **Premium** | 3,000 |
| **Pro** | 10,000 |

The allowance follows the calendar month.

Changing plan does not reset the current monthly counter.

The monthly quota is separate from:

- Number of stored conversations
- Token analytics
- Estimated AI provider cost
- Requests-per-minute protection

---

## ⚡ Redis Configuration

Redis-compatible caching is used by the production-oriented architecture for shared rate limiting.

The connection is configured through:

```text
REDIS_URL
```

Local development can use the configured local-memory fallback where appropriate.

The application includes production configuration checks so a process-local cache is not silently treated as the intended shared production limiter.

### Current Request Limits

| Plan | Requests / Minute |
| --- | ---: |
| **Free** | 20 |
| **Premium** | 60 |
| **Pro** | 120 |

These limits protect against short-term request bursts and are separate from the monthly AI quota.

Hosted Redis connectivity remains part of production infrastructure verification.

---

## 💳 Stripe Live Production & Safe Development

The production web application uses **Stripe Live Mode**.

Current web pricing:

| Plan | Monthly Price |
| --- | ---: |
| **Free** | $0 |
| **Premium** | $29 USD |
| **Pro** | $59 USD |

Production and development payment environments are intentionally separated.

For development and automated regression testing, use Stripe Test Mode credentials and test payment methods. These tests must not create real customer charges.

Production uses the corresponding Live Mode configuration, including Live credentials, Live Price IDs, production webhook configuration, Checkout, and Customer Portal settings.

Secrets, Price IDs, and webhook signing secrets must be supplied through environment configuration and must not be committed to source control.
---

## 🔄 Subscription Downgrade Behaviour

Plan downgrades preserve existing user-created data.

Existing:

- Assistants
- Conversations
- Messages
- Knowledge

are not automatically deleted when a lower plan becomes effective.

If the account exceeds the lower plan's creation/storage entitlement, new restricted actions remain blocked until the account is within the relevant limit.

This behaviour should also be preserved during local and regression testing.

---

## 🤖 Discord Integration — Planned U5

The complete Discord customer workflow is planned for **U5 — Discord Integration + API Access**.

The intended package includes setup/bridge workflow, connection state and diagnostics, secure credentials, assistant selection, backend enforcement, documentation, and end-to-end validation. Until U5 is completed and released, Discord should not be presented as a currently available production feature.
---

## 🧪 Run Automated Tests

The project contains several Django test modules covering different parts of the application.

A broad targeted test command used during development includes:

```bash
python -X utf8 manage.py test ai_assistant.bots.tests ai_assistant.bots.test_redis ai_assistant.bots.test_quality ai_assistant.bots.test_local_completion ai_assistant.accounts.tests ai_assistant.payments.tests --settings=ai_assistant.buildabot.test_settings --noinput
```

Additional focused regression tests have also been used for newer functionality, including areas such as:

- Monthly AI quotas
- Knowledge storage quotas
- Downgrade behaviour
- Subscription continuation
- API entitlement
- Hosted boundary behaviour

Do not treat an older intermediate test count as the final project-wide regression total.

A future release-wide regression run should document its own full-suite result and test count.

Some tests intentionally exercise failure paths and can therefore generate warning or error log output while still passing correctly.

---

## ✅ Run Django System Checks

Run the Django system check:

```bash
python -X utf8 manage.py check --settings=ai_assistant.buildabot.test_settings
```

A successful result should report no system-check issues.

The release-specific verification should also run the appropriate checks against the release configuration rather than relying only on the isolated test settings.

---

## 🧬 Check Migration Consistency

Check whether model changes require additional migrations:

```bash
python -X utf8 manage.py makemigrations --check --dry-run --settings=ai_assistant.buildabot.test_settings
```

A clean result should report:

```text
No changes detected
```

This command checks model/migration consistency.

It does not apply migrations.

---

## 🧹 Run Ruff

Run Ruff against the project as part of development and release validation.

The exact invocation can follow the repository's normal Ruff workflow.

The goal is to confirm that the current Python source passes the project's configured code-quality checks before the affected release.

---

## 🧹 Check Git Whitespace

Before committing, run:

```bash
git diff --check
```

No output indicates that Git found no whitespace errors in the current diff.

---

## 📁 Static Files

Static assets are served through Django/WhiteNoise in the deployed web application.

For deployment-oriented collection, run:

```bash
python manage.py collectstatic --noinput
```

Static collection is normally part of the deployment process rather than something that must be run before every local development-server start.

---

## ✅ Local Verification Checklist

After local setup, verify the functionality relevant to the services you configured.

Core checks include:

- Register a user
- Verify account activation where email is configured
- Log in and log out
- Test password reset
- Create an AI assistant
- Edit an assistant
- Start a conversation
- Create another conversation
- Verify conversation isolation
- Test an in-domain request
- Test out-of-domain behaviour for a specialized assistant
- Add Knowledge
- Test TXT Knowledge
- Test PDF Knowledge
- Test DOCX Knowledge
- Test manual Knowledge
- Verify Knowledge retrieval
- Check usage analytics
- Verify plan restrictions
- Verify monthly AI quota behaviour
- Verify Knowledge storage quota behaviour
- Verify API authentication and entitlement where applicable
- Run automated regression tests

Optional integration checks include:

- Stripe Test Mode Checkout
- Stripe webhook processing
- Stripe Billing Portal
- Redis-backed rate limiting
- Discord Bridge

These integrations require their corresponding development/Test Mode credentials.

---

## ☁️ Hosted Deployment

The application is already deployed on Heroku.

Production URL:

```text
https://www.myaiassistantapp.se/
```

Recent backend work, including the account-wide monthly AI message quota and Knowledge storage quota, has already been deployed and live-tested.

The hosted environment is therefore **not** intentionally frozen on an older backend version.

The production web application is live at the custom domain above and uses Stripe Live Mode.

Future releases continue to follow the project's package workflow: implement the complete upgrade, run focused and regression validation, deploy/build affected clients, perform smoke testing, and close the package before beginning the next major upgrade.

Redis production connectivity remains one of the explicit checks in the final audit.

---

## 🔐 Production Release Configuration Rules

For production releases and relevant infrastructure changes, verify that:

- `DEBUG` is disabled in production
- Production host configuration is correct
- Production secrets are stored only in environment configuration
- Test-only configuration is not exposed publicly
- Test routes are not unintentionally available
- Database configuration points to the intended production database
- Redis connectivity works in the hosted environment
- Static files are served correctly
- Error pages behave correctly
- API authentication and entitlement remain enforced
- Stripe production configuration contains only Live Mode values
- Stripe webhook signatures validate correctly
- No secrets appear in source control
- No secrets appear in templates or client-side JavaScript
- Partially exposed development/test secrets are rotated where required

These checks are ongoing release/operations safeguards for the already-live production web application; they are not evidence that the project is still waiting for an initial v1.0 launch.

---

# 📄 License

This project is licensed under the **MIT License**.

You are free to use, modify, and distribute the software in accordance with the terms of the license.

See the repository's `LICENSE` file for the complete license text.

---

# 🙏 Acknowledgements

AI Assistant Platform was built using a range of open-source technologies, developer platforms, APIs, documentation, and community resources.

Special thanks to the communities and organizations behind:

- Django
- Django REST Framework
- OpenAI
- Stripe
- Discord
- PostgreSQL
- Redis
- Heroku
- GitHub
- Code Institute

Their tools, documentation, and ecosystems played an important role throughout the development of the project.

The project also benefited from the broader Python, web-development, open-source, and AI-development communities.

---

# 👨‍💻 Author

**Hussein Elali**  
Full Stack Web Developer

- GitHub: https://github.com/God-zil-la
- Portfolio: https://god-zil-la.github.io/portfolio/
- LinkedIn: https://www.linkedin.com/in/hussein-elali/

---

# 🤝 Contributions & Feedback

Feedback, suggestions, bug reports, and constructive contributions are welcome.

If you discover an issue or have an idea for improving the platform, the GitHub repository can be used to review the project and follow future development.

Repository:

https://github.com/God-zil-la/Project-4

---

# ⭐ Support

If you find the project useful or interesting, consider giving the repository a ⭐ on GitHub.

It helps support the project and makes the work easier for other developers and potential users to discover.

---

## Thank You for Visiting AI Assistant Platform! 🤖

AI Assistant Platform began as a web-development project and has evolved into a larger SaaS-style system combining AI, Knowledge retrieval, subscriptions, APIs, analytics, external integrations, and multi-client architecture.

The project will continue to evolve beyond the first web release, while keeping the same core focus:

> Build useful, specialized AI assistants on a secure and maintainable platform that can grow across multiple clients and integrations.

⭐ **Thanks for checking out the project.**