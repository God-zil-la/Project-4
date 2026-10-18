"""Clean and validate generated document payloads before secure persistence."""

import csv
from decimal import Decimal, InvalidOperation
import io
import re

# DOCUMENT_EXPORT_QUALITY_V2

_FAKE_LINK = re.compile(
    r'(?im)^\s*\[\s*(?:download|ladda\s+ner)[^\]]*\]\([^\n)]*\)\s*$'
    r'|^\s*(?:download\s+(?:pdf|docx|csv|xlsx|excel|word)[^\n]*)\s*$'
    r'|^\s*https?://[^\s]*/bots/api/documents/[^\s]*\s*$'
)
_PROMISE = re.compile(
    r'(?i)^(?:jag\s+(?:kommer\s+nu\s+att|ska\s+nu|kommer\s+att)\s+'
    r'(?:generera|skapa|ta\s+fram)|i\s+will\s+(?:now\s+)?'
    r'(?:generate|create))\b'
)
_PREAMBLE = re.compile(
    r'(?i)^(?:här\s+(?:är|kommer|har\s+du)|jag\s+har\s+'
    r'(?:skapat|inkluderat)|here\s+(?:is|are)|i\s+have\s+'
    r'(?:created|included))\b'
)
_HEADING = re.compile(r'^#{1,6}\s+(.+?)\s*$')
_REQUEST_TITLE = re.compile(r'(?i)\b(?:titeln|title(?:d)?)\s*["“]([^"”]{4,100})["”]')


# DOCUMENT_FINAL_HOTFIX_V3
_GENERATED_SANDBOX_LINK = re.compile(
    r'(?im)^\s*\[[^\]\n]+\]\(sandbox:[^\n)]*\)\s*$'
)
_CHAT_TRAILER = re.compile(
    r'(?i)^(?:'
    r'jag\s+(?:skapar|genererar|kommer\s+(?:nu\s+)?att\s+(?:skapa|generera)|ska\s+nu\s+(?:skapa|generera))\b'
    r'|nu\s+har\s+jag\s+(?:genererat|skapat)\b'
    r'|h[aä]r\s+(?:kan\s+du\s+)?(?:ladda\s+ner|[aä]r\s+din\s+nedladdningsl[aä]nk)\b'
    r'|v[aä]nligen\s+v[aä]nta\b'
    r'|h[aä]mta\s+[^\n]+$'
    r'|i\s+(?:will|have)\s+(?:now\s+)?(?:generate|create|generated|created)\b'
    r'|your\s+(?:download|file)\s+(?:link|is\s+ready)\b'
    r')'
)


def strip_generated_links(text):
    """Strip model-invented download URLs before adding the persisted URL."""
    text = _GENERATED_SANDBOX_LINK.sub('', str(text or ''))
    return _FAKE_LINK.sub('', text).strip()


def clean_document_content(text):
    """Remove model-generated chat trailers without deleting document body."""
    result = strip_generated_links(text)
    lines = result.splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and _PREAMBLE.search(lines[0].strip()):
        lines.pop(0)
    # Remove the trailing exchange as a block, including divider and blanks.
    while lines:
        tail = lines[-1].strip()
        if not tail or re.fullmatch(r'[-*_]{3,}', tail):
            lines.pop()
            continue
        if _PROMISE.search(tail) or _CHAT_TRAILER.search(tail):
            lines.pop()
            continue
        break
    cleaned = '\n'.join(lines).strip()
    if not cleaned:
        raise ValueError('No document content remains after removing chat text.')
    return cleaned


def derive_document_title(message, content, file_format):
    requested = _REQUEST_TITLE.search(str(message or ''))
    if requested:
        return requested.group(1).strip()
    for line in str(content).splitlines()[:12]:
        match = _HEADING.match(line.strip())
        if match:
            return match.group(1).strip(' *')[:110]
    for line in str(content).splitlines()[:5]:
        line = line.strip(' *#')
        if 8 <= len(line) <= 110 and not line.endswith(('.', ':', ';')):
            if not _PREAMBLE.search(line) and not _PROMISE.search(line):
                return line
    return {'docx': 'Document', 'pdf': 'Report', 'csv': 'Data'}[file_format]


def _number(cell):
    try:
        return Decimal(str(cell).strip().replace(' ', '').replace('\u00a0', '').replace(',', '.'))
    except (InvalidOperation, ValueError):
        return None


def parse_csv_content(text):
    """Extract a CSV table from tab-separated, Markdown, or delimited output."""
    lines = [line.strip() for line in clean_document_content(text).splitlines()]
    lines = [line for line in lines if line]
    if not lines:
        raise ValueError('CSV table is empty.')

    def markdown_row(line):
        stripped = line.strip().strip('|')
        return [cell.strip() for cell in stripped.split('|')]

    def separator(row):
        return all(re.fullmatch(r':?-{3,}:?', cell.strip()) for cell in row)

    rows = []
    if any('\t' in line for line in lines):
        candidates = [line for line in lines if '\t' in line]
        rows = list(csv.reader(candidates, delimiter='\t'))
    elif any(line.startswith('|') and line.count('|') >= 2 for line in lines):
        candidates = [line for line in lines if line.startswith('|') and line.count('|') >= 2]
        rows = [markdown_row(line) for line in candidates]
        rows = [row for row in rows if not separator(row)]
    else:
        for delimiter in (',', ';'):
            candidates = [line for line in lines if line.count(delimiter) >= 2]
            if candidates:
                parsed = list(csv.reader(candidates, delimiter=delimiter))
                if parsed and len(parsed[0]) >= 2:
                    rows = parsed
                    break
    if len(rows) < 2 or len(rows[0]) < 2:
        raise ValueError('No structured CSV table was found in assistant response.')
    width = len(rows[0])
    if width > 30 or len(rows) > 251:
        raise ValueError('CSV table exceeds export limits.')
    if any(len(row) != width for row in rows):
        raise ValueError('CSV rows have inconsistent numbers of columns.')
    headers = [cell.strip().casefold() for cell in rows[0]]
    if any(not h for h in headers):
        raise ValueError('CSV table contains empty headers.')
    if {'pris_sek', 'antal', 'totalt_sek'}.issubset(headers):
        price_i, count_i, total_i = (headers.index(h) for h in ('pris_sek', 'antal', 'totalt_sek'))
        for row in rows[1:]:
            price, count, total = (_number(row[i]) for i in (price_i, count_i, total_i))
            if None in (price, count, total) or price * count != total:
                raise ValueError('CSV arithmetic mismatch; refusing incorrect export.')
    # Avoid spreadsheet formula injection from text values.
    for row in rows:
        for i, cell in enumerate(row):
            if cell.lstrip().startswith(('=', '+', '@')) or (cell.lstrip().startswith('-') and _number(cell) is None):
                row[i] = "'" + cell
    return rows
