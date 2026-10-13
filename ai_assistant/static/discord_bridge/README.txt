U5 Discord bridge — release candidate

Use a customer-owned bot in an explicitly selected Discord server.
Enable Message Content Intent. Grant only View Channels, Send Messages,
and Send Messages in Threads when needed. Do not grant Administrator.
Limit channel visibility to intended users. Shared channels share AI history
and can access the selected assistant's Knowledge. DMs are also accepted.

Install requirements.txt, keep .env beside bridge.py and run python bridge.py.
!ping checks Discord only. !ask <question>, direct mentions and DMs call AI.
Use one bridge process per installation. Restarting starts new conversations.
New channels/threads/DMs start independent conversations.

The backend must be your intended HTTPS origin. The default is the hosted
application; for testing configure DEFAULT_DOMAIN on the isolated backend
before downloading. Never point test traffic at production accidentally.
No redirects are followed. No automatic retry is made after a timeout.

DJANGO_API_TOKEN is a Discord credential scoped to this assistant. It is not
your account API key or native login token. Revoke it in Discord Setup.
For old installations download an updated bridge. Do not reuse old tokens.
Do not share the ZIP or .env. The ZIP contains both bot and bridge secrets.
