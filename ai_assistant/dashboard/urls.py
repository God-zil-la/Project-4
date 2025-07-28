from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.home, name='home'),

    # Test error views
    path('test400/', views.trigger_400, name='test-400'),
    path('test403/', views.trigger_403, name='test-403'),
    path('test500/', views.trigger_500, name='test-500'),
]
