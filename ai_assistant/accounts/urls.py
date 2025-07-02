from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from ai_assistant.accounts.forms import CustomPasswordResetForm
from . import views
from django.urls import path
from .api_views import PublicChatAPIView

app_name = 'accounts'

urlpatterns = [
    # User registration and activation
    path('register/', views.register, name='register'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),

    # Login / Logout
    path('login/', auth_views.LoginView.as_view(
        template_name='accounts/login.html',
        redirect_authenticated_user=True
    ), name='login'),

    path('logout/', auth_views.LogoutView.as_view(
        next_page='accounts:login'
    ), name='logout'),

    # Password Reset - Step 1: Enter Email
    path('password-reset/', auth_views.PasswordResetView.as_view(
        form_class=CustomPasswordResetForm,
        template_name='accounts/password_reset.html',
        email_template_name='accounts/password_reset_email.txt',        
        html_email_template_name='accounts/password_reset_email.html',  
        subject_template_name='accounts/password_reset_subject.txt',
        success_url=reverse_lazy('accounts:password_reset_done'),
    ), name='password_reset'),

    # Password Reset - Step 2: Email Sent Confirmation
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'
    ), name='password_reset_done'),

    # Password Reset - Step 3: Reset Form (from link)
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='accounts/password_reset_confirm.html',
        success_url=reverse_lazy('accounts:password_reset_complete')
    ), name='password_reset_confirm'),

    # Password Reset - Step 4: Completion Success
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'
    ), name='password_reset_complete'),

    path('api/public-chat/', PublicChatAPIView.as_view(), name='public-chat-api'),
]
