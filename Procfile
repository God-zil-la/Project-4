release: python manage.py migrate accounts 0014_userprofile_campaign_reserved_tokens --noinput && python manage.py migrate ai_payments 0006_store_subscriptions --noinput
web: gunicorn ai_assistant.buildabot.wsgi --worker-class gthread --threads 4 --log-file -
