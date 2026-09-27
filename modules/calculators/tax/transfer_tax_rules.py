"""Shared ordinary inheritance/gift tax brackets, amounts in KRW."""
from modules.calculators.finance.finance_models import D, num


def rate_and_deduction(base):
    base = num(base, 0, 10**15)
    for ceiling, rate, deduction in (
        (100000000, '.10', 0), (500000000, '.20', 10000000),
        (1000000000, '.30', 60000000), (3000000000, '.40', 160000000),
        (10**15, '.50', 460000000),
    ):
        if base <= ceiling:
            return D(rate), D(deduction)


def ordinary_tax(base):
    base = num(base, 0, 10**15)
    rate, deduction = rate_and_deduction(base)
    return max(D(0), base*rate-deduction)
