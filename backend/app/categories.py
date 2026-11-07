"""Canonical categories shared by validation and the HTTP endpoint."""

INCOME_CATEGORIES = ('工资', '奖金', '兼职', '理财', '其他收入')
EXPENSE_CATEGORIES = ('餐饮', '交通', '购物', '住房', '医疗', '娱乐', '学习', '其他支出')


def get_categories() -> dict:
    """Return fresh lists so callers cannot mutate the category definitions."""
    return {'income': list(INCOME_CATEGORIES), 'expense': list(EXPENSE_CATEGORIES)}
