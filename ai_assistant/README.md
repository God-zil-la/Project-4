# 🤖 AI Assistant Platform

**Live Demo:** [https://ai-assistant.herokuapp.com](https://ai-assistant.herokuapp.com) *(replace with actual link)*

---

## 🧭 Table of Contents

- [📘 Overview](#-overview)  
- [🧑‍💻 Features](#-features)  
- [🔐 User Authentication](#-user-authentication)  
- [🤖 Bot Management](#-bot-management)  
- [💬 Test Playground](#-test-playground)  
- [💳 Stripe Payment Integration](#-stripe-payment-integration)  
- [🧠 AI Chat (OpenAI)](#-ai-chat-openai)  
- [🛠️ Technologies Used](#️-technologies-used)  
- [📁 Project Structure](#-project-structure)  
- [🚀 Setup & Installation](#-setup--installation)  
- [🧪 Testing & Validation](#-testing--validation)  
- [🌍 Deployment](#-deployment)  
- [🚀 Future Enhancements](#-future-enhancements)  
- [🙏 Credits](#-credits)  
- [👤 Author](#-author)  

---

## 📘 Overview

The AI Assistant Platform is a modern, full-stack Django web application where users can create and manage intelligent chatbots powered by OpenAI's GPT models. Users can interact with their bots via a real-time chat playground, customize bot personalities, and subscribe to premium plans for enhanced capabilities.

This project showcases complex Django multi-app architecture, secure user authentication, RESTful API interactions, real-time AJAX updates, Stripe payment integration, and responsive UI design with theme toggling.

---

## 🧑‍💻 Features

- Multi-app Django structure for modularity and scalability  
- User registration, login, logout with profile management  
- Auto-created UserProfile storing subscription status and message usage  
- Create, edit, delete bots with customizable names, categories, and personalities  
- Real-time AJAX-powered chat playground with scrollable chat history  
- OpenAI GPT-3.5 Turbo integration for AI-powered responses  
- Daily message limits enforced for free-tier users  
- Stripe subscription plans with checkout, webhook, and user access control  
- Dark/light mode toggle with persistent user preferences  
- Fully responsive design optimized for mobile and desktop

---

## 🔐 User Authentication

- Based on Django's built-in User model  
- Secure session management and CSRF protection enabled  
- UserProfiles created automatically via Django signals  
- Tracks subscription status and daily message quota  
- Navigation adapts dynamically based on authentication state

---

## 🤖 Bot Management

- Users can create and manage multiple bots  
- Bots include name, category, personality description fields  
- Permissions restrict bot management to owners only  
- CRUD views with validation and friendly UI  
- Bot listings indicate premium access where applicable

---

## 💬 Test Playground

- Interactive AJAX chat interface per bot  
- Messages sent and received asynchronously  
- Chat history saved and retrieved from backend database  
- Bot responses generated with personality and category context  
- Scrollable chat window with smooth auto-scroll  
- Dark and light theme support

---

## 💳 Stripe Payment Integration

- Stripe checkout sessions with client-side Stripe.js  
- Secure webhook handling updates subscription status in UserProfile  
- Payment success and cancel flow pages  
- Decorators restrict access to premium features for unsubscribed users  
- Stripe API keys stored securely in environment variables

---

## 🧠 AI Chat (OpenAI)

- Integration with OpenAI GPT-3.5 Turbo model  
- Dynamic system prompt combining bot category and personality  
- Error handling with fallback messages on API failures  
- API key managed via `.env` and `python-dotenv` for security  
- Conversation history saved for each bot-user pair

---

## 🛠️ Technologies Used

### Backend
- Python 3.13  
- Django 4.2  
- SQLite (development), PostgreSQL (production)  
- Stripe API  
- OpenAI API  

### Frontend
- HTML5, CSS3  
- Vanilla JavaScript with Fetch API and AJAX  
- Responsive Flexbox layout  
- Dark/light mode toggle (localStorage persistence)  

### Deployment
- Heroku Platform  
- Gunicorn WSGI server  
- Whitenoise for static files  
- Environment variables with python-decouple  

---

## 📁 Project Structure

ai-assistant/
├── ai_assistant/ # Project settings and configuration
├── accounts/ # User auth and profiles
├── bots/ # Bot models, views, templates, chat logic
├── dashboard/ # Homepage and main layout
├── payments/ # Stripe payment and subscription management
├── templates/ # Shared and app-specific templates
├── static/ # CSS, JavaScript, images
├── .env # Environment variables (excluded from VCS)
├── Procfile # Heroku process config
├── runtime.txt # Python version for Heroku
└── requirements.txt # Project dependencies

yaml
Kopiera

---

## 🚀 Setup & Installation

1. **Clone the repository**  
   ```bash
   git clone https://github.com/God-zil-la/Project-4.git
   cd Project-4
Create and activate a virtual environment

bash
Kopiera
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
Install dependencies

bash
Kopiera
pip install -r requirements.txt
Create .env file with required variables:

ini
Kopiera
DJANGO_SECRET_KEY=your_secret_key_here
OPENAI_API_KEY=your_openai_api_key_here
STRIPE_PUBLIC_KEY=your_stripe_public_key_here
STRIPE_SECRET_KEY=your_stripe_secret_key_here
Run database migrations

bash
Kopiera
python manage.py migrate
Create superuser for admin access

bash
Kopiera
python manage.py createsuperuser
Run the development server

bash
Kopiera
python manage.py runserver
Access the app at http://127.0.0.1:8000/

🧪 Testing & Validation
Manual Testing
Feature	Description	Status
Registration/Login	Handles valid and invalid inputs	✅
Bot Management	Permission enforcement and CRUD tested	✅
Chat Playground	Real-time messaging and UI behavior	✅
Stripe Payment Flow	Successful checkout and cancellation	✅
Access Control	Premium features locked for free users	✅
Theme Toggle	Dark/light mode persistence and UI	✅
Responsive Design	Works well on mobile and desktop	✅

Automated Testing (Planned)
Unit tests for views and models

Integration tests for chat and payment flows

🌍 Deployment
Hosted on Heroku with PostgreSQL database

Uses Gunicorn as the production WSGI server

Whitenoise serves static files

Sensitive keys stored in Heroku config vars and .env

Deployment steps:

Create Heroku app

Add environment variables via heroku config:set

Push code: git push heroku main

Run migrations: heroku run python manage.py migrate

Open app: heroku open

🚀 Future Enhancements
User-uploaded bot avatars and images

Bot cloning, sharing, and exporting

OAuth2 login via Google, GitHub

Analytics dashboard for bot usage and chat insights

Monthly token usage and billing tiers

Email verification and password reset

Multi-language support for bots and UI

🙏 Credits
Stripe Documentation

OpenAI Documentation

Django Documentation

Inspiration from various Django and React tutorials

👤 Author
👨‍💻 Hussein Elali
GitHub: @god-zil-la

Built from scratch with ❤️ — Designed, developed, tested, and deployed by Hussein.