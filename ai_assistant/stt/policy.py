"""Locked product quotas, expressed as exact integer milliseconds."""
STT_MINUTES = {'free': 0, 'premium': 120, 'pro': 300,
               'business': 600, 'business_max': 1200}
LAUNCHED_PLANS = frozenset({'free', 'premium', 'pro'})


def stt_limit_ms(server_plan):
    # Business definitions do not enable entitlement or launch either plan.
    if server_plan not in LAUNCHED_PLANS:
        return 0
    return STT_MINUTES[server_plan] * 60_000
