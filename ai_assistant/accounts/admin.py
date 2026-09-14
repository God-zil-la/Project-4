from django.contrib import admin
from .models import UserProfile, DeletionFollowUp, FileDeletionJob


@admin.register(DeletionFollowUp)
class DeletionFollowUpAdmin(admin.ModelAdmin):
    list_display = ('id', 'email', 'stripe_customer_id', 'created_at')
    readonly_fields = ('email', 'stripe_customer_id', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(FileDeletionJob)
class FileDeletionJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at')
    readonly_fields = ('name', 'created_at')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin interface customization for the UserProfile model."""

    list_display = (
        'user',
        'is_subscribed',
        'monthly_message_count',
        'message_count_period_start',
    )
    search_fields = ('user__username',)
    readonly_fields = ('api_key',)
