"""Deterministic source binding and bounded, local workbook validation."""

import ast
from collections import Counter
from decimal import Decimal, ROUND_HALF_UP
import math
import re

from openpyxl.formula import Tokenizer
from openpyxl.utils.cell import range_boundaries


_AMOUNT = re.compile(
    r'(?<![\w.])(-?(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)'
    r'(?:[.,]\d{1,2})?)(?!\d|[.,]\d)(?:\s*(SEK|kr\b|kronor\b|EUR|USD))?', re.I
)
_TOTAL = re.compile(
    r'\b(?:sum|summa|summan|total\w*|resultat\w*|profit|balance|'
    r'\u00e5rskostnad\w*|\u00e5rsint\u00e4kt\w*|annual\s+(?:cost|revenue)\w*)\b', re.I
)


def extract_amounts(text):
    """Extract monetary inputs and stated results without an AI round trip.

    Bare small counts and years are not money. Ambiguous prose is retained in
    context; concise labels are also used to check cell placement.
    """
    amounts = []
    for match in _AMOUNT.finditer(text):
        # Ignore numbered section headings such as "1. Monthly Budget".
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_prefix = text[line_start:match.start()]
        following = text[match.end():]
        if (
            not match[2]
            and not line_prefix.strip()
            and re.match(r"\.\s+\S", following)
        ):
            continue
        # Worksheet headings are structural metadata, not monetary inputs.
        if not match[2] and re.search(
            r'\b(?:worksheet|sheet|kalkylblad|arbetsblad|flik|ark)\s*$',
            line_prefix,
            re.I,
        ):
            continue
        value = Decimal(re.sub(r'[ \u00a0\u202f]', '', match[1]).replace(',', '.'))
        prefix = re.split(r'[,;\n()]+|\.\s+', text[:match.start()])[-1].strip(' :\"\'')
        suffix = text[match.end():match.end() + 35]
        if not match[2] and (abs(value) < 1000 or 1900 <= value <= 2100):
            assignment = re.search(r'[:=]\s*$', text[max(0, match.start() - 3):match.start()])
            labelled = re.fullmatch(r'[^\W\d_]+(?:\s+[^\W\d_]+){0,2}', prefix)
            metadata = re.match(r'\s*(?:ark|sheets?|months?|m\u00e5nader|\u00e5r|years?)\b', suffix, re.I)
            if not assignment and (not labelled or metadata or 1900 <= value <= 2100):
                continue
        # Separate monetary entries without consuming characters from labels.
        previous_amounts = list(_AMOUNT.finditer(prefix))
        if previous_amounts:
            prefix = prefix[previous_amounts[-1].end():].lstrip()

        label = prefix.strip(' :=')
        # A quoted worksheet heading is metadata, not a source-row label.
        label = re.sub(
            r'^["\x27][^"\x27]{1,31}["\x27]\s*:\s*',
            '',
            label,
        )
        # Remove instruction words only at the beginning of source labels.
        label = re.sub(
            r'^(?:(?:include|including|and|och|inkludera|samt)\s+)+',
            '',
            label,
            flags=re.I,
        )
        # A month range describes the period, not the money category.
        if re.fullmatch(
            r'(?:jan(?:uary|uari)?\s*(?:-|\u2013|to|through|till)\s*'
            r'dec(?:ember)?)(?:\s+with)?',
            label,
            re.I,
        ):
            label = ''
        if len(label.split()) > 4:
            label = ''
        context = text[max(0, match.start() - 80):match.end() + 60]
        trailing_label = re.match(r'\s*(resultat|profit)\b', suffix, re.I)
        derived = bool(_TOTAL.search(prefix) or trailing_label)
        if trailing_label:
            label = trailing_label[1]
        # Sales may be named after the amount instead of before it.
        if not label and re.search(
            r'\b(?:sales|revenue|f\u00f6rs\u00e4ljning|int\u00e4kter)\b',
            suffix,
            re.I,
        ):
            label = 'Sales' if re.search(
                r'\b(?:sales|revenue)\b', suffix, re.I
            ) else 'F\u00f6rs\u00e4ljning'
        repeated = bool(
            re.search(r'(?:varje\s+m\u00e5nad|each\s+month|per\s+month)', suffix, re.I)
            and re.search(r'jan(?:uari|uary)?\s*(?:-|\u2013|to|through|till)\s*dec(?:ember)?|12\s+(?:m\u00e5nader|months)', context, re.I)
        )
        amounts.append({
            'id': 'amount_' + str(len(amounts) + 1),
            'value': str(value), 'label': label, 'context': context,
            'derived': derived, 'count': 12 if repeated and not derived else 1,
        })
    return amounts


def requested_sheet_names(text):
    """Read a quoted sheet list when the request explicitly introduces one."""
    match = re.search(r'\b(?:ark|sheets?)\s*[:=]?\s*(?=[\"\'])', text, re.I)
    if not match:
        return []
    section = text[match.end():].split('\n', 1)[0]
    return re.findall(r'[\"\']([^\"\'\n]{1,31})[\"\'](?!\s*!)', section)


def validate_structure(specification):
    if not isinstance(specification, dict) or set(specification) != {'sheets'}:
        raise ValueError('Invalid workbook structure.')
    sheets = specification['sheets']
    if not isinstance(sheets, list) or not 1 <= len(sheets) <= 12:
        raise ValueError('Invalid worksheet collection.')
    names = set()
    for sheet in sheets:
        if not isinstance(sheet, dict) or set(sheet) != {'name', 'rows'}:
            raise ValueError('Invalid worksheet structure.')
        name, rows = sheet['name'], sheet['rows']
        if (not isinstance(name, str) or not 1 <= len(name) <= 31
                or re.search(r'[\[\]:*?/\\]', name) or name.startswith("'")
                or name.endswith("'") or name.casefold() in names):
            raise ValueError('Invalid worksheet name.')
        names.add(name.casefold())
        if not isinstance(rows, list) or not 1 <= len(rows) <= 250:
            raise ValueError('Invalid worksheet rows.')
        for row in rows:
            if not isinstance(row, list) or not 1 <= len(row) <= 30:
                raise ValueError('Invalid worksheet row.')
            for value in row:
                if value is not None and not isinstance(value, (str, int, float, bool, dict)):
                    raise ValueError('Invalid cell value.')
                if isinstance(value, float) and not math.isfinite(value):
                    raise ValueError('Non-finite cell value.')
                if isinstance(value, str) and (len(value) > 10000 or re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', value)):
                    raise ValueError('Invalid cell text.')


class FormulaValues:
    """Evaluate only a small numeric Excel grammar; never execute model code."""

    def __init__(self, specification, source_amounts=()):
        self.sheets = {s['name'].casefold(): s['rows'] for s in specification['sheets']}
        self.cache = {}
        self.active = set()
        self.source_amounts = source_amounts
        self.reference_count = 0

    def cell(self, sheet, row, col):
        key = (sheet.casefold(), row, col)
        if key in self.cache:
            return self.cache[key]
        if key in self.active:
            raise ValueError(
                f'Circular formula detected at {sheet}!R{row}C{col}.'
            )
        if len(self.active) >= 100:
            raise ValueError('Formula dependency depth exceeds 100.')
        rows = self.sheets.get(key[0])
        if rows is None or not 1 <= row <= len(rows) or not 1 <= col <= len(rows[row - 1]):
            raise ValueError('Formula references an absent cell.')
        value = rows[row - 1][col - 1]
        if isinstance(value, str) and value.startswith('='):
            self.active.add(key)
            try:
                value = self.formula(value, sheet)
            finally:
                self.active.remove(key)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            value = Decimal(str(value))
        else:
            value = None
        self.cache[key] = value
        return value

    def reference(self, reference, sheet):
        if '!' in reference:
            sheet, reference = reference.rsplit('!', 1)
            if sheet.startswith("'") and sheet.endswith("'"):
                sheet = sheet[1:-1].replace("''", "'")
        if not re.fullmatch(r'\$?[A-Za-z]{1,3}\$?[1-9]\d*(?::\$?[A-Za-z]{1,3}\$?[1-9]\d*)?', reference):
            raise ValueError('Unsupported or external formula reference.')
        c1, r1, c2, r2 = range_boundaries(reference)
        if not (1 <= c1 <= c2 <= 30 and 1 <= r1 <= r2 <= 250):
            raise ValueError('Formula range exceeds workbook limits.')
        self.reference_count += (r2 - r1 + 1) * (c2 - c1 + 1)
        if self.reference_count > 1000000:
            raise ValueError('Formula evaluation exceeds workbook limits.')
        values = [self.cell(sheet, r, c) for r in range(r1, r2 + 1) for c in range(c1, c2 + 1)]
        return values if ':' in reference else values[0]

    def formula(self, formula, sheet):
        values = {}
        expression = []
        try:
            tokens = Tokenizer(formula).items
        except Exception as exc:
            raise ValueError('Malformed formula.') from exc
        for token in tokens:
            if token.type == 'WHITE-SPACE':
                continue
            if token.type == 'OPERAND' and token.subtype in ('RANGE', 'NUMBER'):
                if token.subtype == 'NUMBER':
                    if not re.fullmatch(r'\d+(?:\.\d*)?(?:[Ee][+-]?\d+)?', token.value):
                        raise ValueError('Invalid formula number.')
                    if abs(Decimal(token.value)) >= 1000 and self.source_amounts:
                        raise ValueError('Monetary formulas must reference source cells.')
                key = 'v' + str(len(values))
                values[key] = (self.reference(token.value, sheet) if token.subtype == 'RANGE'
                               else Decimal(token.value))
                expression.append(key)
            elif token.type == 'FUNC' and token.subtype == 'OPEN':
                function = token.value[:-1].upper()
                if function not in ('SUM', 'AVERAGE', 'MIN', 'MAX', 'COUNT', 'ROUND'):
                    raise ValueError('Unsupported spreadsheet function.')
                expression.append(function + '(')
            elif ((token.type in ('FUNC', 'PAREN') and token.value in ('(', ')'))
                  or (token.type == 'SEP' and token.value == ',')
                  or (token.type in ('OPERATOR-PREFIX', 'OPERATOR-INFIX') and token.value in ('+', '-', '*', '/'))):
                expression.append(token.value)
            else:
                raise ValueError('Unsupported formula syntax.')

        def evaluate(node):
            if isinstance(node, ast.Name) and node.id in values:
                return values[node.id]
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
                value = evaluate(node.operand)
                return value if isinstance(node.op, ast.UAdd) else -value
            if isinstance(node, ast.BinOp):
                left, right = evaluate(node.left), evaluate(node.right)
                if not isinstance(left, Decimal) or not isinstance(right, Decimal):
                    raise ValueError('Arithmetic requires numeric cells.')
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.Div):
                    return left / right
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
                args = [evaluate(arg) for arg in node.args]
                flat = [v for arg in args for v in (arg if isinstance(arg, list) else [arg]) if v is not None]
                if any(not isinstance(v, Decimal) for v in flat):
                    raise ValueError('Non-numeric formula argument.')
                name = node.func.id
                if name == 'SUM':
                    return sum(flat, Decimal(0))
                if name == 'COUNT':
                    return Decimal(len(flat))
                if name in ('AVERAGE', 'MIN', 'MAX') and flat:
                    return {'AVERAGE': lambda: sum(flat) / len(flat), 'MIN': lambda: min(flat), 'MAX': lambda: max(flat)}[name]()
                if name == 'ROUND' and len(flat) == 2 and flat[1] == int(flat[1]) and abs(flat[1]) <= 15:
                    return flat[0].quantize(Decimal(10) ** -int(flat[1]), rounding=ROUND_HALF_UP)
            raise ValueError('Unsupported formula expression.')

        try:
            value = evaluate(ast.parse(''.join(expression), mode='eval').body)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise ValueError('Formula must return a finite number.')
            return value
        except (SyntaxError, ArithmeticError, TypeError, RecursionError) as exc:
            raise ValueError('Invalid numeric formula.') from exc


def bind_and_validate(specification, amounts=()):
    validate_structure(specification)
    sources = {item['id']: item for item in amounts}
    used = Counter()
    months = {key: set() for key in sources}
    month_aliases = (
        ('jan', 'januari', 'january'), ('feb', 'februari', 'february'),
        ('mar', 'mars', 'march'), ('apr', 'april'), ('maj', 'may'),
        ('jun', 'juni', 'june'), ('jul', 'juli', 'july'), ('aug', 'augusti', 'august'),
        ('sep', 'september'), ('okt', 'oktober', 'oct', 'october'),
        ('nov', 'november'), ('dec', 'december'),
    )
    for sheet in specification['sheets']:
        for row in sheet['rows']:
            row_text = ' '.join(v for v in row if isinstance(v, str) and not v.startswith('=')).casefold()
            for index, value in enumerate(row):
                if (sources and isinstance(value, (int, float)) and not isinstance(value, bool)
                        and abs(value) >= 1000 and not 1900 <= value <= 2100):
                    raise ValueError('Monetary inputs require source bindings.')
                if isinstance(value, dict):
                    if set(value) != {'source'} or not isinstance(value['source'], str) or value['source'] not in sources:
                        raise ValueError('Unknown source binding.')
                    source = sources[value['source']]
                    if source['derived']:
                        raise ValueError('Derived totals require cell formulas.')
                    if source['label'] and source['count'] == 1 and source['label'].casefold() not in row_text:
                        raise ValueError('Source label does not match its row.')
                    number = Decimal(source['value'])
                    row[index] = int(number) if number == int(number) else float(number)
                    used[source['id']] += 1
                    for month, aliases in enumerate(month_aliases):
                        if any(re.search(r'\b' + alias + r'\b', row_text) for alias in aliases):
                            months[source['id']].add(month)
    evaluator = FormulaValues(specification, amounts)
    calculated = []
    for sheet in specification['sheets']:
        for r, row in enumerate(sheet['rows'], 1):
            for c, value in enumerate(row, 1):
                if isinstance(value, str) and value.startswith('='):
                    label = ' '.join(v for v in row if isinstance(v, str) and not v.startswith('=')).casefold()
                    calculated.append((evaluator.cell(sheet['name'], r, c), label))
    for source in amounts:
        if source['derived']:
            if not any(value == Decimal(source['value']) and
                       (not source['label'] or source['label'].casefold() in label)
                       for value, label in calculated):
                raise ValueError('Computed totals do not match the request.')
        elif used[source['id']] < source['count']:
            raise ValueError('Missing source input: ' + source['id'])
        elif source['count'] == 12 and len(months[source['id']]) != 12:
            raise ValueError('Monthly inputs must cover twelve distinct months.')
    return evaluator
