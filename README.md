🤖 AI Assistant Platform
Live Demo: https://ai-assistant.herokuapp.com (replace with actual link)

🧭 Table of Contents
📘 Overview
🧑‍💻 Features
🔐 User Authentication
🤖 Bot Management
💬 Test Playground
💳 Stripe Payment Integration
🧠 AI Chat (OpenAI)
📊 Monitor Logs & Analytics
🎨 Styling and UX
🔄 CRUD Operations & Data Flow
🏗️ Architecture Overview
📊 Database Models Overview
📊 Database Design & ERD
🛠️ Technologies Used
📁 Project Structure
🧪 Testing & Validation
🌍 Deployment
🚀 Future Enhancements
🙏 Credits
👤 Author

📘 Overview
The AI Assistant Platform is a full-stack Django web application where users can register, create intelligent assistant bots, test them live, and subscribe to premium plans using Stripe. Built from scratch with scalable design, real-time interaction, and a smooth UX, this project demonstrates multi-app integration, API communication, and secure authentication.

🧑‍💻 Features
✅ Key Functionality
Multi-app Django architecture

User registration and login/logout

Bot creation with custom personality and category

Real-time chat with OpenAI-powered responses

Stripe-based subscription plans

Role-based bot access (free/premium)

Dashboard and Playground with responsive UI

🔐 User Authentication
Built with Django's User model

Register, login, logout views

Secure sessions and CSRF protection

Conditional navigation for authenticated users

Styled forms: register.html, login.html

🤖 Bot Management
Create, update, delete AI bots

Bots have name, category, personality, creator link

Bot list cards show category, ownership, and premium badge

Permissions: users can only manage their own bots

Template views: list.html, form.html, confirm_delete.html

💬 Test Playground
Interactive chat interface per bot

Ajax chat submission and real-time reply rendering

Chat history saved per bot per user

Scrollable chat log UI with dark/light theme support

Bot personality passed to OpenAI for customized responses

💳 Stripe Payment Integration
Stripe test mode integrated

Checkout session creation with Stripe.js

Payments required for accessing premium bots

Decorators & middleware restrict access without subscription

Views: checkout, success, cancel, webhook

CSRF protection + Django messages for feedback

🧠 AI Chat Integration
OpenAI GPT used to power bot responses

API keys managed in .env

Prompt combines user message + bot's category/personality

Response formatted and displayed with JS

📊 Monitor Logs & Analytics
All bot interactions are logged and can be reviewed by staff through the Django Admin interface.

✅ Logged Data (via BotUsageLog model)
👤 User

🤖 Bot

💬 Message

🔢 Token count (OpenAI usage)

🕒 Timestamp

🛠️ Admin Dashboard Features
Access: https://yourdomain.com/admin/ (staff only)

Date range filters, search by username, bot name, message

Export selected logs as CSV

Dark mode and custom branding

Staff-only access enforced

🎨 Styling and UX
Responsive Design: Mobile-first CSS Flexbox layouts adapt smoothly to phones, tablets, desktops.

Dark/Light Theme Toggle: Preference saved in localStorage and applied site-wide.

Consistent UI Elements: Buttons, forms, nav use uniform fonts, colors, spacing.

Flexbox Layouts: Used for navbars, chat boxes, forms for easy alignment.

Styled Forms: Clear, accessible registration, login, bot creation, and knowledge upload forms.

Dynamic Feedback: Django messages show success/error/info notifications consistently.

Accessible Design: ARIA labels, keyboard focus support on buttons and forms.

🔄 CRUD Operations & Data Flow
Bot CRUD Lifecycle
Create Bot: User fills form (name, category, personality), bot saved with owner.

Read/List Bots: User's bots shown on dashboard with details and badges.

Update Bot: Edit form accessible to owner only.

Delete Bot: Confirmation page restricts deletion to owner.

Data Flow Diagram (Simplified)
mermaid
Kopiera
flowchart TD
    A[User] -->|Submit Bot Form| B[Backend Bot Create View]
    B --> C[Bot Model Instance saved with Owner]
    A -->|View Bots| D[Bot List View]
    D --> E[Query bots by User]
    A -->|Edit/Delete Bot| F[Bot Edit/Delete Views]
    F --> C
Chat & Knowledge Upload Flow

User sends message via chat UI

Frontend AJAX sends message to backend

Backend stores message, fetches relevant knowledge chunks with embeddings

Combines context + bot personality, sends prompt to OpenAI API

AI response stored and returned to frontend

Knowledge upload allows file submission processed to enrich bot answers

🏗️ Architecture Overview
Django Multi-App Project:

accounts for user management

bots for AI assistant functionality

payments for Stripe integration

dashboard for homepage and analytics

Frontend:

Django templates + embedded JavaScript for AJAX chat

Static assets served with Whitenoise

Backend:

PostgreSQL in production, SQLite locally

OpenAI API integration in bots.utils

Stripe webhook and payment processing in payments app

Security & Access Control:

Decorators for authentication and ownership

Subscription guards for premium features

Site-wide CSRF protection

📊 Database Models Overview
Model	Purpose	Key Fields
User	Built-in Django user	username, email, password
Bot	AI assistant bot	name, category, personality, owner (FK User)
ChatMessage	User and bot chat messages	bot (FK), user (FK), message, sender, timestamp
KnowledgeBase	Uploaded files for bot knowledge	file, bot (FK), uploaded_by, timestamp
KnowledgeChunk	Text chunks with embeddings	knowledge_file (FK), text, embedding (JSONB)
BotUsageLog	Logs user-bot interactions	user (FK), bot (FK), message, token_count, timestamp
UserProfile	User subscription and message count	daily_message_count, is_subscribed

📊 Database Design & ERD (Entity-Relationship Diagram)
ERD Overview
The AI Assistant Platform uses a relational database with entities linked as follows:

User (Django’s User model)
owns → Bot

Bot
has many → ChatMessage, KnowledgeBase, BotUsageLog

KnowledgeBase
split into many → KnowledgeChunk

ChatMessage
linked to → User and Bot

BotUsageLog
logs interactions between User and Bot

ERD Diagram (example PNG to include in your repo)

(Replace with actual diagram path and image)

🛠️ Technologies Used
Backend:

Python 3.13

Django 4.2

SQLite (local)

PostgreSQL (production)

Stripe API

OpenAI API

Frontend:

HTML5, CSS3

Vanilla JS + AJAX

Flexbox layouts

Dark/light mode toggle

Mobile-first design

Deployment:

Heroku

Gunicorn + Whitenoise

Python Decouple for env variables

Pipenv / requirements.txt

📁 Project Structure
bash
Kopiera
ai-assistant/
├── ai_assistant/        # Project settings
├── accounts/            # Authentication system
├── bots/                # Bot models and views
├── dashboard/           # Homepage and analytics
├── payments/            # Stripe integration
├── templates/           # HTML templates
├── static/              # CSS, JS, images
├── .env                 # Environment variables
├── Procfile             # Heroku runtime config
├── runtime.txt          # Python version
└── requirements.txt     # Dependencies
🧪 Testing & Validation
✅ Manual Testing
Feature	Test Description	Status
Register/Login Forms	Valid + invalid inputs	✅
Bot CRUD	Permissions, validation, ownership	✅
Chat Playground	Real-time interaction + scroll	✅
Stripe Payment Flow	Success and cancel flows	✅
Access Control	Premium-only bots require subscription	✅
Theme Toggle	Dark/light transitions on all pages	✅
Footer/Nav	Layout consistent across screen sizes	✅
Monitor Logs & Analytics	Logs saved and appear in admin	✅
CSV Export	Downloads filtered logs	✅
Staff-only Admin Access	Admin panel restricted to staff users	✅

✅ Validation
HTML & CSS: W3C validators passed

JavaScript: JSHint no critical errors

Python: Flake8 + Black (PEP8 compliant)

🌍 Deployment
Hosting: Heroku

Database: PostgreSQL

Static Files: Whitenoise

Stripe keys stored in .env, loaded via python-decouple

Deployment Steps
heroku create

Set environment variables (STRIPE keys, SECRET_KEY, etc.)

git push heroku main

heroku run python manage.py migrate

heroku open

🚀 Future Enhancements
Bot avatars and image uploads

Bot cloning/sharing

OAuth2 login (Google/GitHub)

Chat analytics/dashboard per user

Monthly usage tracking

Email verification on registration

Premium tier with monthly token limits

🙏 Credits
Stripe Docs: https://stripe.com/docs

OpenAI Docs: https://platform.openai.com/docs

Django Docs: https://docs.djangoproject.com

👤 Author
👨‍💻 Hussein Elali
GitHub: @god-zil-la

Built from scratch with ❤️ — Designed, developed, styled, tested, and deployed by Hussein.

📌 Purpose of Knowledge Upload
Add Custom Information: Users upload documents/texts that the bot uses as context for more specific answers.

Inject Domain-Specific Knowledge: Upload domain files like recipes, policies for tailored responses.

Improve Bot Responses Dynamically: Supplement AI’s general knowledge with uploaded info.

Expand Bot Capabilities Without Coding: End-users customize bot knowledge without modifying code or retraining.

📌 How It Works Behind the Scenes (Simplified)
User uploads files (PDF, text, data).

Backend extracts info, chunks and embeds it.

Indexed data available to bot for chat context.

Bot uses uploaded knowledge to answer user queries more accurately.

End of README

✅ Step 1: Create a Discord bot in the Discord Developer Portal
1️⃣ Go to Discord Developer Portal: https://discord.com/developers/applications
2️⃣ Create a new application and name it.
3️⃣ In the Bot tab, click Add Bot.
4️⃣ Copy the Bot Token and keep it safe!
5️⃣ Go to OAuth2 > URL Generator, select bot as scope, and permissions:

Read Messages

Send Messages
6️⃣ Generate the URL and invite the bot to your server.

🤖 Discord Bot Development in VS Code
Build and run your Discord bot locally with full OpenAI integration, using VS Code!

✅ Step 1: Create Your Bot in the Discord Developer Portal

1️⃣ Go to 👉 Discord Developer Portal.
2️⃣ Click "New Application" and give it a name.
3️⃣ In the sidebar, click Bot and choose "Add Bot".
4️⃣ Click Reset Token or Copy Token to get your bot's secret token.

⚠️ Keep this token safe! Never commit it to Git.
5️⃣ Go to OAuth2 > URL Generator.

Select bot as scope.

Set Bot Permissions:

✅ Read Messages

✅ Send Messages
6️⃣ Copy the generated invite URL.
7️⃣ Invite your bot to your server.

🖼️ You can add screenshots here:

css
Kopiera
Redigera
![Discord Developer Portal](link-to-your-image)
![Add Bot](link-to-your-image)
![Copy Token](link-to-your-image)
✅ Step 2: Clone This Repository in VS Code

1️⃣ Open VS Code.
2️⃣ Clone your repo or open the project folder.

bash
Kopiera
Redigera
git clone https://github.com/yourusername/your-repo.git
cd your-repo
🖼️ Optional screenshot of VS Code with project open:

css
Kopiera
Redigera
![VS Code Project](link-to-your-image)
✅ Step 3: Create and Activate a Virtual Environment

1️⃣ In VS Code Terminal:

Create:

bash
Kopiera
Redigera
python -m venv venv
Activate:

Windows PowerShell:

powershell
Kopiera
Redigera
venv\Scripts\Activate
macOS / Linux:

bash
Kopiera
Redigera
source venv/bin/activate
✅ You’ll see (venv) in your terminal prompt.

🖼️ Example:

css
Kopiera
Redigera
![VS Code Terminal with venv activated](link-to-your-image)
✅ Step 4: Install Dependencies

Install all required packages from requirements.txt:

bash
Kopiera
Redigera
pip install -r requirements.txt
Includes:

discord.py

openai

python-dotenv

Other project dependencies

🖼️ Example:

css
Kopiera
Redigera
![pip install screenshot](link-to-your-image)
✅ Step 5: Add Your Secrets to .env

Create a .env file in the project root:

ini
Kopiera
Redigera
DISCORD_TOKEN=your-discord-bot-token
OPENAI_API_KEY=your-openai-api-key
⚠️ Important:
✅ NEVER commit this file to Git.
✅ Use .gitignore to exclude .env.

🖼️ Example:

arduino
Kopiera
Redigera
![VS Code .env File](link-to-your-image)
✅ Step 6: Review or Edit the Bot Code

Open discord_bot.py in VS Code:

Customize:

Bot command prefix (default: !)

Greeting messages

OpenAI model (e.g. gpt-3.5-turbo)

Example section in code:

python
Kopiera
Redigera
bot = commands.Bot(command_prefix="!", intents=intents)
🖼️ Example:

pgsql
Kopiera
Redigera
![VS Code with discord_bot.py open](link-to-your-image)
✅ Step 7: Run the Bot Locally in VS Code

In your activated virtual environment:

bash
Kopiera
Redigera
python discord_bot.py
✅ Terminal output:

pgsql
Kopiera
Redigera
Logged in as YourBotName
🖼️ Example:

arduino
Kopiera
Redigera
![Bot running in terminal](link-to-your-image)
✅ Step 8: Test Your Bot in Discord

1️⃣ Go to your Discord server.
2️⃣ Send your bot a message or use commands:

diff
Kopiera
Redigera
!hello
!ping
✅ Your bot will:

Respond with friendly greetings

Use OpenAI to answer questions intelligently

🖼️ Example:

css
Kopiera
Redigera
![Discord chat with bot](link-to-your-image)
✅ Files Involved
discord_bot.py → Main bot logic and OpenAI integration.

.env → Your Discord Token and OpenAI API key (excluded from Git).

requirements.txt → All Python dependencies.

✅ Example Commands
yaml
Kopiera
Redigera
!hello    → Bot replies: "Hello from the bot!"
!ping     → Bot replies: "Pong!"
Any text  → Bot replies via OpenAI ChatCompletion
✅ Notes

Works in VS Code terminal with virtual environments.

Designed for local development, but can be deployed to a server.

Make sure your bot has permissions in your Discord server.

🖼️ Suggested Screenshots to Add
✅ Developer Portal setup
✅ .env file in VS Code
✅ VS Code terminal running bot
✅ Chat example in Discord

📌 Related Links
Discord Developer Portal

discord.py documentation

OpenAI Python Library