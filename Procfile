release: python manage.py migrate ai_payments 0006_store_subscriptions --noinput
web: gunicorn ai_assistant.buildabot.wsgi --log-file -
