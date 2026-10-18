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
    r"\b(?:skapa|generera|gör|göra|bygg|exportera|"
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
    """
    Basic guard against exporting short clarification replies.
    """
    response = str(response or "").strip()

    if len(response.split()) < 25:
        return False

    if response.endswith("?") and len(response.split()) < 100:
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
    if not last["content"].strip().endswith("?"):
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
