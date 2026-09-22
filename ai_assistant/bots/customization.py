"""Assistant-level preferences; neutral defaults preserve existing behavior."""
TONE_CHOICES = [
    ('default', 'Use personality & instructions'),
    ('friendly', 'Friendly'),
    ('professional', 'Professional'),
]
LENGTH_CHOICES = [
    ('default', 'Use personality & instructions'),
    ('concise', 'Concise'),
    ('detailed', 'Detailed'),
]
ICON_CHOICES = [
    ('default', 'None (current appearance)'),
    ('robot', '🤖 Robot'),
    ('sparkles', '✨ Sparkles'),
    ('book', '📚 Books'),
    ('briefcase', '💼 Briefcase'),
]
ICON_SYMBOLS = {'robot': '🤖', 'sparkles': '✨', 'book': '📚', 'briefcase': '💼'}
TONE_HINT = 'Choose a default tone. More specific personality instructions or chat requests take priority.'
LENGTH_HINT = 'Choose a default level of detail. Existing response limits still apply.'
ICON_HINT = 'Shown in your assistant list and chat. This does not change its replies.'


def response_preferences(bot):
    preferences = []
    tone = {
        'friendly': 'Use a warm, friendly tone.',
        'professional': 'Use a professional, matter-of-fact tone.',
    }.get(bot.response_tone)
    length = {
        'concise': 'Keep answers concise and focused on the key points.',
        'detailed': 'Give fuller explanations and useful examples where appropriate, within the existing response limit.',
    }.get(bot.response_length)
    preferences.extend(value for value in (tone, length) if value)
    if not preferences:
        return ''
    return (
        '\n\nDEFAULT RESPONSE PREFERENCES:\n'
        'Use these only where the configured personality/instructions or current '
        'request do not specify a more specific response style. They do not '
        'change category, safety, Knowledge Base, or response language rules.\n'
        + '\n'.join(preferences)
    )
