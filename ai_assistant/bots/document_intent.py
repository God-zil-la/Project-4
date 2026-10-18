import re


FILE_REQUESTS = {
    "pdf": re.compile(r"\bpdf(?:-fil|-dokument)?\b", re.I),
    "docx": re.compile(
        r"\b(?:docx|word(?:-fil|-dokument)?)\b", re.I
    ),
    "xlsx": re.compile(
        r"\b(?:xlsx|excel(?:-fil|-ark)?|spreadsheet)\b", re.I
    ),
    "csv": re.compile(r"\bcsv(?:-fil)?\b", re.I),
}

CREATE_ACTION = re.compile(
    r"\b(?:skapa|generera|g\u00f6r|g\u00f6ra|bygg|exportera|"
    r"create|generate|make|build|export)\b",
    re.I,
)

GENERIC_DOCUMENT = re.compile(
    r"\b(?:nedladdningsbar(?:t|a)?|downloadable)\b"
    r".{0,60}\b(?:dokument|document|fil|file|arbetsbok|workbook)\b"
    r"|"
    r"\b(?:dokument|document|fil|file|arbetsbok|workbook)\b"
    r".{0,60}\b(?:nedladdningsbar(?:t|a)?|downloadable)\b",
    re.I | re.S,
)




# Gate expensive document classification for plausible document requests.
# Unicode escapes avoid terminal encoding corruption.
DOCUMENT_CANDIDATE = re.compile(
    r"(?:\b(?:pdf|docx|xlsx|csv|document|download|downloadable|"
    r"export|spreadsheet|workbook|dokument|arbetsbok|"
    r"documento|archivo|fichier)\b|"
    r"nedladd|exportera|excel|word.file|"
    r"\u0648\u062b\u064a\u0642\u0629|"
    r"\u0645\u0633\u062a\u0646\u062f|"
    r"\u0645\u0644\u0641|"
    r"\u062a\u062d\u0645\u064a\u0644|"
    r"\u0926\u0938\u094d\u0924\u093e\u0935\u0947\u091c|"
    r"\u092b\u093c\u093e\u0907\u0932|"
    r"\u6587\u6863|"
    r"\u6587\u4ef6|"
    r"\u4e0b\u8f7d|"
    r"\u5bfc\u51fa|"
    r"\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9|"
    r"\ub2e4\uc6b4\ub85c\ub4dc)",
    re.I,
)


def is_document_candidate(message):
    """Cheap, side-effect-free document classification gate."""
    return bool(DOCUMENT_CANDIDATE.search(str(message or "")))


def requested_document_format(message):
    """Detect explicit file generation requests."""

    message = str(message or "")

    if not CREATE_ACTION.search(message):
        return None

    formats = [
        name
        for name, pattern in FILE_REQUESTS.items()
        if pattern.search(message)
    ]

    if len(formats) > 1:
        return None

    if formats:
        return formats[0]

    # A generic downloadable document defaults to Word.
    # Explicit Excel workbook requests are handled above.
    if GENERIC_DOCUMENT.search(message):
        return "docx"

    return None


def document_content_ready(message, response):
    """Export only substantive completed answers, not clarification replies."""
    response = str(response or "").strip()

    if len(response.split()) < 25:
        return False

    # A reply requesting essential details is not a completed document.
    clarification_patterns = (
        r"\b(?:kan du|skulle du kunna|could you|can you|please)\b"
        r".{0,120}\b(?:ange|ber?tta|specificera|provide|specify|tell me)\b",
        r"\b(?:vilka specifika|vilket ?mne|vilka ?mnen|vad vill du"
        r"|what topics|what subject|what should)\b",
        r"\b(?:f?r att b?rja|innan jag b?rjar|before i begin"
        r"|to get started|i need more information)\b",
        r"\b(?:n?r jag har denna information|once i have"
        r"|when you provide)\b",
    )

    for pattern in clarification_patterns:
        if re.search(pattern, response, re.I | re.S):
            return False

    # Questions in the closing part of the answer often indicate
    # that the assistant is still gathering document requirements.
    tail = response[-700:]
    if "?" in tail:
        question_patterns = (
            r"\b(?:kan du|vilka|vilket|vilken|vad|hur|n?r"
            r"|could you|can you|what|which|how|would you)\b"
            r"[^?]{0,180}\\?",
        )
        if any(re.search(p, tail, re.I) for p in question_patterns):
            return False

    return True




# DOCUMENT_FOLLOWUP_V2
CANCEL_DOCUMENT = re.compile(
    r"\b(?:avbryt|strunta i|gl\u00f6m det|\u00e5ngra|cancel|"
    r"never mind|forget it|don't create|skapa inte)\b",
    re.I,
)

CLARIFICATION = re.compile(
    r"(?:\?|\b(?:vad ska|vilket \u00e4mne|vilken typ|"
    r"what topic|what subject|please specify|"
    r"could you specify|tell me what)\b)",
    re.I,
)


def resolve_document_format(message, history):
    """
    Detect an explicit document request or its immediate follow-up.
    """
    message = str(message or "").strip()

    if not message or CANCEL_DOCUMENT.search(message):
        return None

    explicit = requested_document_format(message)
    if explicit:
        return explicit

    # Acknowledgements must not restart an earlier document export.
    if message.casefold().strip(" .!?") in {
        "tack", "tack s? mycket", "thank you", "thanks",
        "thank you very much", "ok", "okay",
    }:
        return None

    if not isinstance(history, (list, tuple)):
        return None

    conversation = [
        item for item in history
        if isinstance(item, dict)
        and item.get("role") in ("user", "assistant")
        and isinstance(item.get("content"), str)
    ]

    if len(conversation) < 2:
        return None

    last = conversation[-1]
    previous = conversation[-2]

    if last["role"] != "assistant":
        return None

    if previous["role"] != "user":
        return None

    # Only continue a pending export after an actual question.
    # An ordinary completed answer must never reactivate it.
    # A clarification may end with a statement after its question.
    # Do not reactivate exports after a completed document.
    if "?" not in last["content"]:
        return None

    if not CLARIFICATION.search(last["content"]):
        return None

    pending_format = requested_document_format(
        previous["content"]
    )

    if not pending_format:
        return None

    if message.endswith("?"):
        return None

    if CREATE_ACTION.search(message) and not FILE_REQUESTS[
        pending_format
    ].search(message):
        return None

    return pending_format
