{% extends "base.html" %}
{% load i18n %}

{% block content %}
  <h2>{% trans "Set New Password" %}</h2>

  {% if validlink %}
    <form method="post">
      {% csrf_token %}
      {{ form.as_p }}

      <button type="submit">{% trans "Change my password" %}</button>
    </form>
  {% else %}
    <p>{% trans "The password reset link was invalid, possibly because it has already been used. Please request a new password reset." %}</p>
  {% endif %}
{% endblock %}
