🤖 AI Assistant Platform

Live Demo: https://ai-assistant.herokuapp.com (replace with actual link)

* 🧭 Table of Contents
* 📘 Overview
* 🧑‍💻 Features
* 🔐 User Authentication
* 🤖 Bot Management
* 💬 Test Playground
* 💳 Stripe Payment Integration
* 🧠 AI Chat (OpenAI)
* 🛠️ Technologies Used
* 📁 Project Structure
* 🧪 Testing & Validation
* 🌍 Deployment
* 🚀 Future Enhancements
* 🙏 Credits
* 👤 Author

## 📘 Overview

* The AI Assistant Platform is a full-stack Django web application where users can register, create intelligent assistant bots, test them live, and subscribe to premium plans using Stripe. Built from scratch with scalable design, real-time interaction, and a smooth UX, this project demonstrates multi-app integration, API communication, and secure authentication.

## 🧑‍💻 Features

### ✅ Key Functionality

* Multi-app Django architecture
* User registration and login/logout
* Bot creation with custom personality and category
* Real-time chat with OpenAI-powered responses
* Stripe-based subscription plans
* Role-based bot access (free/premium)
* Dashboard and Playground with responsive UI

## 🔐 User Authentication

* Built with Django's User model
* Register, login, logout views
* Secure sessions and CSRF protection
* Conditional navigation for auth users
* Styled forms: register.html, login.html

## 🤖 Bot Management

* Create, update, delete AI bots
* Bots have name, category, personality, creator link
* Bot list cards show category, ownership, and premium badge
* Permissions: users can only manage their own bots
* Template views: list.html, form.html, confirm_delete.html

## 💬 Test Playground

* Interactive chat interface per bot
* Ajax chat submission and real-time reply rendering
* Chat history saved per bot per user
* Scrollable chat log UI with dark/light theme support
* Bot personality passed to OpenAI for customized responses

## 💳 Stripe Payment Integration

* Stripe test mode integrated
* Checkout session creation with Stripe.js
* Payments required for accessing premium bots
* Decorators & middleware restrict access without subscription
* Views: checkout, success, cancel, webhook
* CSRF protection + Django messages for feedback

## 🧠 AI Chat Integration

* OpenAI GPT used to power bot responses
* API keys managed in .env
* Prompt combines user message + bot's category/personality
* Response formatted and displayed with JS

## 🛠️ Technologies Used

*** Backend: ***
* Python 3.13
* Django 4.2
* SQLite (local)
* PostgreSQL (production)
* Stripe API
* OpenAI API
*** Frontend: ***
* HTML5, CSS3
* Vanilla JS + AJAX
* Flexbox-based layout
* Dark/light mode toggle
* Mobile-first design
*** Deployment: ***
* Heroku
* Gunicorn + Whitenoise
* Python Decouple for env vars
* Pipenv / requirements.txt

## 📁 Project Structure

ai-assistant/
├── ai_assistant/        # Project settings
├── accounts/            # Auth system
├── bots/                # Bot models and views
├── dashboard/           # Homepage and layout
├── payments/            # Stripe integration
├── templates/           # HTML templates
├── static/              # CSS, JS, images
├── .env                 # Env variables
├── Procfile             # Heroku runtime
├── runtime.txt          # Python version
└── requirements.txt     # Dependencies

## 🧪 Testing & Validation

### ✅ Manual Testing

Feature                         Test Description                       Status

Register/Login Forms            Valid + invalid inputs                   ✅
Bot CRUD                        Permissions, validation, ownership       ✅
Chat Playground                 Real-time interaction + scroll           ✅
Stripe Payment Flow             Success and cancel flows                 ✅
Access Control                  Premium-only bots require subscription   ✅
Theme Toggle                    Dark/light transitions work on all pages ✅
Footer/Nav                      Layout consistent on all screen sizes    ✅

## ✅ Validation

* HTML & CSS: W3C validators passed
* JavaScript: JSHint with no critical errors
* Python: Flake8 + Black (PEP8-compliant)

## 🌍 Deployment

* Hosting: Heroku
* Database: PostgreSQL
* Static Files: Whitenoise
* Stripe Keys: stored in .env, loaded with python-decouple
*** Steps: ***
1. heroku create
2. Add env vars: STRIPE keys, SECRET_KEY
3. git push heroku main
4. heroku run python manage.py migrate
5. heroku open

## 🚀 Future Enhancements

* Bot avatars and image uploads
* Bot cloning/sharing
* OAuth2 login (Google/GitHub)
* Chat analytics/dashboard per user
* Monthly usage tracking
* Email verification on register
* Premium tier with monthly token limits

## 🙏 Credits

* Stripe Docs: https://stripe.com/docs
* OpenAI Docs: https://platform.openai.com/docs
* Django Docs: https://docs.djangoproject.com

## 👤 Author

👨‍💻 Hussein ElaliGitHub: @god-zil-la

Built from scratch with ❤️ — Designed, developed, styled, tested, and deployed by Hussein.