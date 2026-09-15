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
        'plan',
        'effective_plan_display',
        'complimentary_plan',
        'complimentary_reason',
        'complimentary_until',
        'complimentary_active',
        'is_subscribed',
        'monthly_message_count',
        'message_count_period_start',
    )

    list_filter = (
        'plan',
        'complimentary_plan',
        'complimentary_reason',
        'is_subscribed',
    )

    search_fields = (
        'user__username',
        'user__email',
    )

    readonly_fields = (
        'api_key',
        'effective_plan_display',
        'complimentary_active',
    )

    @admin.display(description='Effective plan')
    def effective_plan_display(self, obj):
        return obj.effective_plan.title()

    @admin.display(boolean=True, description='Complimentary active')
    def complimentary_active(self, obj):
        return obj.has_complimentary_access