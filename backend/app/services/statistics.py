"""Member 5: summarize every record matched by the shared business filters."""

from ..validators import RecordFilter


def summarize_records(records: list[dict], filters: RecordFilter) -> dict:
    """Return totals and expense categories for all records matching ``filters``.

    ``filter_records`` is imported lazily because member 4 owns that module. The
    statistics endpoint intentionally has no pagination: it summarizes the same
    complete match set that the records endpoint can expose across all pages.
    """
    from .record_query import filter_records

    matched = filter_records(records, filters)
    income_cents = 0
    expense_cents = 0
    income_count = 0
    expense_count = 0
    expense_categories: dict[str, dict[str, int]] = {}

    for record in matched:
        kind = record['type']
        amount_cents = record['amount_cents']
        if kind == 'income':
            income_cents += amount_cents
            income_count += 1
        elif kind == 'expense':
            expense_cents += amount_cents
            expense_count += 1
            category = record['category']
            category_total = expense_categories.setdefault(
                category, {'amount_cents': 0, 'count': 0}
            )
            category_total['amount_cents'] += amount_cents
            category_total['count'] += 1
        else:
            raise ValueError(f'unsupported record type: {kind!r}')

    expense_by_category = [
        {
            'category': category,
            'amount_cents': totals['amount_cents'],
            'count': totals['count'],
        }
        for category, totals in sorted(
            expense_categories.items(),
            key=lambda item: (-item[1]['amount_cents'], item[0]),
        )
    ]

    return {
        'income_cents': income_cents,
        'expense_cents': expense_cents,
        'balance_cents': income_cents - expense_cents,
        'count': len(matched),
        'income_count': income_count,
        'expense_count': expense_count,
        'expense_by_category': expense_by_category,
    }
