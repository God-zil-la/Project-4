import stripe

from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from ai_assistant.accounts.models import UserProfile


stripe.api_key = settings.STRIPE_SECRET_KEY
endpoint_secret = settings.STRIPE_WEBHOOK_SECRET


ACTIVE_SUBSCRIPTION_STATUSES = {
    "active",
    "trialing",
}


def timestamp_to_datetime(timestamp):
    if not timestamp:
        return None

    return datetime.fromtimestamp(
        timestamp,
        tz=dt_timezone.utc,
    )


def update_profile_from_subscription(profile, subscription):
    """
    Synchronize Stripe subscription data with UserProfile.
    """

    status = subscription.get("status")
    customer_id = subscription.get("customer")
    subscription_id = subscription.get("id")
    current_period_end = subscription.get(
        "current_period_end"
    )

    profile.stripe_customer_id = customer_id
    profile.stripe_subscription_id = subscription_id
    profile.stripe_subscription_status = status
    profile.subscription_current_period_end = (
        timestamp_to_datetime(current_period_end)
    )

    profile.is_subscribed = (
        status in ACTIVE_SUBSCRIPTION_STATUSES
    )

    profile.save(
        update_fields=[
            "stripe_customer_id",
            "stripe_subscription_id",
            "stripe_subscription_status",
            "subscription_current_period_end",
            "is_subscribed",
        ]
    )


@csrf_exempt
def stripe_webhook(request):
    payload = request.body

    sig_header = request.META.get(
        "HTTP_STRIPE_SIGNATURE",
        "",
    )

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            endpoint_secret,
        )

    except ValueError:
        return HttpResponse(status=400)

    except stripe.error.SignatureVerificationError:
        return HttpResponse(status=400)

    event_type = event.get("type")
    event_object = event["data"]["object"]

    # -------------------------------------------------
    # CHECKOUT COMPLETED
    #
    # Find the Django user using client_reference_id.
    # Then retrieve the Stripe subscription and store
    # its real status and identifiers.
    # -------------------------------------------------
    if event_type == "checkout.session.completed":
        session = event_object

        user_id = session.get(
            "client_reference_id"
        )

        subscription_id = session.get(
            "subscription"
        )

        customer_id = session.get(
            "customer"
        )

        if user_id:
            try:
                user = User.objects.get(
                    id=user_id
                )

                profile = user.profile

                if customer_id:
                    profile.stripe_customer_id = (
                        customer_id
                    )

                if subscription_id:
                    subscription = (
                        stripe.Subscription.retrieve(
                            subscription_id
                        )
                    )

                    update_profile_from_subscription(
                        profile,
                        subscription,
                    )

                else:
                    profile.save(
                        update_fields=[
                            "stripe_customer_id",
                        ]
                    )

            except User.DoesNotExist:
                pass

            except UserProfile.DoesNotExist:
                pass

    # -------------------------------------------------
    # SUBSCRIPTION CREATED / UPDATED
    #
    # Stripe can update a subscription independently
    # of Checkout, for example after renewal, payment
    # problems, trial changes or cancellation changes.
    # -------------------------------------------------
    elif event_type in {
        "customer.subscription.created",
        "customer.subscription.updated",
    }:
        subscription = event_object

        customer_id = subscription.get(
            "customer"
        )

        subscription_id = subscription.get(
            "id"
        )

        profile = (
            UserProfile.objects.filter(
                stripe_subscription_id=subscription_id
            ).first()
        )

        if not profile and customer_id:
            profile = (
                UserProfile.objects.filter(
                    stripe_customer_id=customer_id
                ).first()
            )

        if profile:
            update_profile_from_subscription(
                profile,
                subscription,
            )

    # -------------------------------------------------
    # SUBSCRIPTION DELETED
    #
    # Subscription is finished/cancelled.
    # Premium access must be removed.
    # -------------------------------------------------
    elif event_type == "customer.subscription.deleted":
        subscription = event_object

        subscription_id = subscription.get(
            "id"
        )

        customer_id = subscription.get(
            "customer"
        )

        profile = (
            UserProfile.objects.filter(
                stripe_subscription_id=subscription_id
            ).first()
        )

        if not profile and customer_id:
            profile = (
                UserProfile.objects.filter(
                    stripe_customer_id=customer_id
                ).first()
            )

        if profile:
            profile.is_subscribed = False
            profile.stripe_subscription_status = (
                subscription.get("status", "canceled")
            )

            profile.subscription_current_period_end = (
                timestamp_to_datetime(
                    subscription.get(
                        "current_period_end"
                    )
                )
            )

            profile.save(
                update_fields=[
                    "is_subscribed",
                    "stripe_subscription_status",
                    "subscription_current_period_end",
                ]
            )

    return HttpResponse(status=200)