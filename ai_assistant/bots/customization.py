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
    """Build optional response preferences without overriding explicit requests."""
    preferences = []

    tone = {
        "friendly": "Use a warm, friendly tone.",
        "professional": "Use a professional, matter-of-fact tone.",
    }.get(bot.response_tone)

    length = {
        "concise": "Keep answers concise and focused on the key points.",
        "detailed": (
            "Give fuller explanations and useful examples where appropriate, "
            "within the existing response limit."
        ),
    }.get(bot.response_length)

    communication_style = {
        "formal": "Use formal and polished language.",
        "casual": "Use natural, conversational language.",
        "educational": "Explain concepts clearly with helpful teaching examples.",
        "technical": "Use precise technical terminology when appropriate.",
    }.get(bot.communication_style)

    response_structure = {
        "paragraphs": "Prefer well-organized paragraphs.",
        "bullet_points": "Prefer bullet points when presenting information.",
        "step_by_step": "Prefer numbered, step-by-step explanations.",
    }.get(bot.response_structure)

    language_name = dict(DEFAULT_LANGUAGE_CHOICES).get(bot.default_language)
    default_language = (
        (
            f"Respond in {language_name} by default, regardless of the "
            "language used in the user's message. Only switch languages "
            "when the user explicitly asks for a different response language."
        )
        if bot.default_language != "auto" and language_name
        else None
    )

    if bot.default_language == "my":
        default_language += (
            " Write in natural, fluent Burmese using standard Myanmar "
            "script and appropriate grammar, vocabulary, and sentence "
            "structure. Avoid unnatural literal translations, invented "
            "words, and unnecessary English. Preserve technical terms "
            "when translation would make them less accurate. "
            "If uncertain about a fact, say so rather than inventing it."
        )

    proactivity = {
        "minimal": "Answer directly without unnecessary suggestions or follow-up questions.",
        "balanced": "Offer relevant next steps when useful. Ask a focused follow-up question only when clarification would materially improve the answer.",
        "proactive": "Anticipate useful next steps without losing focus. When important information is missing, ask one specific and relevant follow-up question. Do not invent missing facts, ask unnecessary questions, or override explicit user preferences.",
    }.get(bot.proactivity)

    preferences.extend(
        value for value in (
            tone,
            length,
            communication_style,
            response_structure,
            default_language,
            proactivity,
        )
        if value
    )

    custom_instructions = (bot.custom_instructions or "").strip()

    if custom_instructions:
        preferences.append(
            "Additional assistant instructions:\n" + custom_instructions
        )

    if not preferences:
        return ""

    return (
        "\n\nDEFAULT RESPONSE PREFERENCES:\n"
        "Apply these preferences unless higher-priority instructions or "
        "the user's explicit current request require otherwise. "
        "Do not override safety, category restrictions, authoritative "
        "Knowledge Base facts, or existing response limits.\n"
        + "\n".join(preferences)
    )


COMMUNICATION_STYLE_CHOICES = [
    ("default", "Use existing instructions"),
    ("formal", "Formal"),
    ("casual", "Casual"),
    ("educational", "Educational"),
    ("technical", "Technical"),
]

RESPONSE_STRUCTURE_CHOICES = [
    ("default", "Automatic"),
    ("paragraphs", "Paragraphs"),
    ("bullet_points", "Bullet points"),
    ("step_by_step", "Step by step"),
]

DEFAULT_LANGUAGE_CHOICES = [
    ('auto', 'Automatic'),
    ('en', 'English'),
    ('sv', 'Swedish'),
    ('af', 'Afrikaans'),
    ('sq', 'Albanian'),
    ('am', 'Amharic'),
    ('ar', 'Arabic'),
    ('hy', 'Armenian'),
    ('az', 'Azerbaijani'),
    ('eu', 'Basque'),
    ('be', 'Belarusian'),
    ('bn', 'Bengali'),
    ('bs', 'Bosnian'),
    ('bg', 'Bulgarian'),
    ('my', 'Burmese'),
    ('ca', 'Catalan'),
    ('zh-hans', 'Chinese (Simplified)'),
    ('zh-hant', 'Chinese (Traditional)'),
    ('hr', 'Croatian'),
    ('cs', 'Czech'),
    ('da', 'Danish'),
    ('nl', 'Dutch'),
    ('et', 'Estonian'),
    ('tl', 'Filipino'),
    ('fi', 'Finnish'),
    ('fr', 'French'),
    ('ka', 'Georgian'),
    ('de', 'German'),
    ('el', 'Greek'),
    ('gu', 'Gujarati'),
    ('ha', 'Hausa'),
    ('he', 'Hebrew'),
    ('hi', 'Hindi'),
    ('hu', 'Hungarian'),
    ('is', 'Icelandic'),
    ('ig', 'Igbo'),
    ('id', 'Indonesian'),
    ('ga', 'Irish'),
    ('it', 'Italian'),
    ('ja', 'Japanese'),
    ('kn', 'Kannada'),
    ('kk', 'Kazakh'),
    ('km', 'Khmer'),
    ('ko', 'Korean'),
    ('lo', 'Lao'),
    ('lv', 'Latvian'),
    ('lt', 'Lithuanian'),
    ('mk', 'Macedonian'),
    ('ms', 'Malay'),
    ('ml', 'Malayalam'),
    ('mr', 'Marathi'),
    ('ne', 'Nepali'),
    ('nb', 'Norwegian Bokmal'),
    ('ps', 'Pashto'),
    ('fa', 'Persian'),
    ('pl', 'Polish'),
    ('pt', 'Portuguese'),
    ('pt-br', 'Portuguese (Brazil)'),
    ('pa', 'Punjabi'),
    ('ro', 'Romanian'),
    ('ru', 'Russian'),
    ('sr', 'Serbian'),
    ('si', 'Sinhala'),
    ('sk', 'Slovak'),
    ('sl', 'Slovenian'),
    ('so', 'Somali'),
    ('es', 'Spanish'),
    ('sw', 'Swahili'),
    ('ta', 'Tamil'),
    ('te', 'Telugu'),
    ('th', 'Thai'),
    ('tr', 'Turkish'),
    ('uk', 'Ukrainian'),
    ('ur', 'Urdu'),
    ('uz', 'Uzbek'),
    ('vi', 'Vietnamese'),
    ('cy', 'Welsh'),
    ('yo', 'Yoruba'),
    ('zu', 'Zulu'),
]

PROACTIVITY_CHOICES = [
    ("default", "Use existing instructions"),
    ("minimal", "Minimal"),
    ("balanced", "Balanced"),
    ("proactive", "Proactive"),
]
