"""Monthly remittance to the landlord: the fee of the rental agent and the balance.

Pure functions, so the tests can check every amount by hand. Amounts are rounded to the cent.
"""
from datetime import date

# LEGAL-CHECK: art. 18 §1 en art. 37 WBTW, KB nr. 20 (tabel A en B) - het ereloon van de rentmeester is een
# dienst aan 21% btw. De huur die hij int en doorstort is geen omzet van het kantoor: de verhuur zelf is
# vrijgesteld (art. 44 §3, 2° WBTW) en hoort bij de verhuurder.
FEE_VAT_RATE = 21.0


def money(amount):
    return round(amount + 0.0, 2)


def months_between(first, second):
    """Number of months from the month of first to the month of second (0 for the same month)."""
    return (second.year - first.year) * 12 + second.month - first.month


def months_to_charge(month, mandate_start, last_charged=None, mandate_end=None):
    """Months of a fixed monthly fee still to charge in the remittance of month.

    The months since the last month charged, or since the start of the mandate (that month included).
    A month after the end of the mandate is never charged.
    """
    month = month.replace(day=1)
    if mandate_end and month > mandate_end.replace(day=1):
        month = mandate_end.replace(day=1)
    if last_charged:
        return max(months_between(last_charged.replace(day=1), month), 0)
    return max(months_between(mandate_start.replace(day=1), month) + 1, 0)


def percent_fee(base, percent):
    """Fee as a percentage of the rent (and charges) received."""
    return money(base * percent / 100.0)


def fixed_fee(amount, months):
    return money(amount * months)


def fee_vat(untaxed, rate=FEE_VAT_RATE):
    return money(untaxed * rate / 100.0)


def split_received(received, rent, charges):
    """Split an amount received on a rent invoice over rent and charges, in proportion.

    A partial payment pays rent and charges alike; the rent part is rounded, the charges get the rest.
    """
    total = rent + charges
    if not total:
        return 0.0, 0.0
    rent_part = money(received * rent / total)
    return rent_part, money(received - rent_part)


def balance(received, costs, fee_total):
    """What is transferred to the landlord: received minus costs paid for him minus the fee."""
    return money(received - costs - fee_total)


def month_end(month):
    following = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    return date.fromordinal(following.toordinal() - 1)
