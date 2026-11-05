"""Regional rules for residential leases: indexation, energy-label freeze, deposit, notice.

Pure functions and constants, so the tests can check every rule by hand.
None of these rules has been validated by a lawyer yet: each one carries a LEGAL-CHECK.
"""
from datetime import date

from dateutil.relativedelta import relativedelta

# Sources: VWHD = Vlaams Woninghuurdecreet (9 november 2018), BHC = Brusselse Huisvestingscode,
# Waals decreet 15-03-2018 = décret relatif au bail d'habitation.
REGIONS = [
    ("flanders", "Vlaanderen"),
    ("brussels", "Brussel"),
    ("wallonia", "Wallonië"),
]

EPC_LABELS = [
    ("A+", "A+"),
    ("A", "A"),
    ("B", "B"),
    ("C", "C"),
    ("D", "D"),
    ("E", "E"),
    ("F", "F"),
    ("G", "G"),
    ("none", "Geen EPC"),
]

# LEGAL-CHECK: art. 1728bis oud BW, art. 34 VWHD, art. 224 BHC, art. 26 Waals decreet 15-03-2018 - in alle
# drie de gewesten is de geïndexeerde huur = basishuur x nieuw indexcijfer / aanvangsindexcijfer, met de gezondheidsindex.
# Aanvangsindex: de maand vóór de maand waarin het contract gesloten is; nieuw indexcijfer: de maand
# vóór de verjaardag van de inwerkingtreding.

# Energy-label freeze of 2022-2023: per region the window of anniversaries it applied to and the
# share of the indexation that was allowed per label. The lost share is never caught up: after the
# window a correction factor keeps it out of every later indexation.
ENERGY_FREEZE = {
    # LEGAL-CHECK: Vlaams decreet van 14 oktober 2022 (indexering volgens EPC) - verjaardagen van
    # 1 oktober 2022 tot en met 30 september 2023: label A+ tot C volledig, D voor de helft, E, F of
    # geen EPC niet. Vanaf 1 oktober 2023 een correctiefactor (decreet van 2023, nakijken).
    "flanders": {
        "start": date(2022, 10, 1),
        "end": date(2023, 9, 30),
        "rates": {"A+": 1.0, "A": 1.0, "B": 1.0, "C": 1.0, "D": 0.5, "E": 0.0, "F": 0.0, "G": 0.0, "none": 0.0},
    },
    # LEGAL-CHECK: Brusselse ordonnantie van 13 oktober 2022 (indexering volgens EPB) - verjaardagen
    # van 14 oktober 2022 tot en met 13 oktober 2023: label A tot D volledig, E voor de helft, F, G of
    # geen EPB niet. Daarna een correctiefactor (ordonnantie van 2023, nakijken).
    "brussels": {
        "start": date(2022, 10, 14),
        "end": date(2023, 10, 13),
        "rates": {"A+": 1.0, "A": 1.0, "B": 1.0, "C": 1.0, "D": 1.0, "E": 0.5, "F": 0.0, "G": 0.0, "none": 0.0},
    },
    # LEGAL-CHECK: Waals decreet van 19 oktober 2022 (indexation selon le PEB) - verjaardagen van
    # 1 november 2022 tot en met 31 oktober 2023: label A tot C volledig, D en E voor de helft, F, G
    # of geen PEB niet. Daarna een correctiefactor (decreet van 2023, nakijken).
    "wallonia": {
        "start": date(2022, 11, 1),
        "end": date(2023, 10, 31),
        "rates": {"A+": 1.0, "A": 1.0, "B": 1.0, "C": 1.0, "D": 0.5, "E": 0.5, "F": 0.0, "G": 0.0, "none": 0.0},
    },
}

# Retroactive indexation: at most this many months before the written request.
RETROACTIVE_MONTHS = {
    # LEGAL-CHECK: art. 34 Vlaams Woninghuurdecreet - indexering met terugwerkende kracht tot
    # maximaal drie maanden vóór de schriftelijke vraag.
    "flanders": 3,
    # LEGAL-CHECK: art. 224 Brusselse Huisvestingscode - indexering met terugwerkende kracht tot
    # maximaal drie maanden vóór de schriftelijke vraag.
    "brussels": 3,
    # LEGAL-CHECK: art. 26 Waals decreet van 15 maart 2018 - indexering met terugwerkende kracht
    # tot maximaal drie maanden vóór de schriftelijke vraag.
    "wallonia": 3,
}

# Maximum rental deposit in months of rent, per kind of deposit.
DEPOSIT_MAX_MONTHS = {
    # LEGAL-CHECK: art. 37 Vlaams Woninghuurdecreet - huurwaarborg van maximaal drie maanden huur,
    # in elke vorm.
    "flanders": {"blocked_account": 3, "bank_guarantee": 3, "public_guarantee": 3},
    # LEGAL-CHECK: art. 248 Brusselse Huisvestingscode - twee maanden op een geblokkeerde rekening,
    # drie maanden bij een bankwaarborg.
    "brussels": {"blocked_account": 2, "bank_guarantee": 3, "public_guarantee": 3},
    # LEGAL-CHECK: art. 62 Waals decreet van 15 maart 2018 - twee maanden op een geblokkeerde
    # rekening, drie maanden bij een bankwaarborg.
    "wallonia": {"blocked_account": 2, "bank_guarantee": 3, "public_guarantee": 3},
}

# LEGAL-CHECK: art. 3 en 21 VWHD, art. 238 BHC, art. 55 Waals decreet 15-03-2018 - een kortlopend contract (hoogstens drie jaar) eindigt alleen
# na een opzeg drie maanden vóór het einde; anders wordt het een contract van negen jaar.
SHORT_TERM_NOTICE_MONTHS = 3
# LEGAL-CHECK: art. 16 VWHD, art. 237 BHC, art. 55 Waals decreet 15-03-2018 - een contract van negen jaar eindigt met een opzeg van de verhuurder
# zes maanden of van de huurder drie maanden vóór het einde; anders loopt het telkens drie jaar door.
NINE_YEAR_NOTICE_MONTHS = {"landlord": 6, "tenant": 3}

# Zip codes of the Brussels-Capital Region and of Wallonia; everything else in Belgium is Flanders.
BRUSSELS_ZIPS = range(1000, 1300)
WALLONIA_ZIPS = [range(1300, 1500), range(4000, 8000)]


class IndexMissing(Exception):
    """The health index of a month is not in the table yet."""

    def __init__(self, month):
        super().__init__(month)
        self.month = month


def region_from_zip(zip_code):
    try:
        number = int((zip_code or "").strip()[:4])
    except ValueError:
        return False
    if number in BRUSSELS_ZIPS:
        return "brussels"
    if any(number in zips for zips in WALLONIA_ZIPS):
        return "wallonia"
    return "flanders"


def month_before(day):
    """First day of the month before the month of day."""
    return day.replace(day=1) - relativedelta(months=1)


def anniversary(date_start, year):
    """Anniversary of the start date in the given year (29 February becomes 28 February)."""
    return date_start + relativedelta(years=year - date_start.year)


def freeze_correction(region, epc_label, date_start, start_index_month, lookup):
    """Correction factor for the indexation lost during the energy-label freeze.

    Returns (factor, freeze anniversary or None, allowed rate). The factor is
    1 + lost share x (growth of the index in the frozen year - 1): the index growth of that one
    year, or half of it, stays out of every indexation from then on.
    """
    freeze = ENERGY_FREEZE[region]
    rate = freeze["rates"].get(epc_label or "none", 0.0)
    if rate >= 1.0:
        return 1.0, None, rate
    year = freeze["start"].year
    frozen = None
    while year <= freeze["end"].year:
        candidate = anniversary(date_start, year)
        if candidate > date_start and freeze["start"] <= candidate <= freeze["end"]:
            frozen = candidate
            break
        year += 1
    if not frozen:
        return 1.0, None, rate
    previous = frozen - relativedelta(years=1)
    previous_month = start_index_month if previous <= date_start else month_before(previous)
    growth = lookup(month_before(frozen)) / lookup(previous_month)
    return 1.0 + (1.0 - rate) * (growth - 1.0), frozen, rate


def compute_indexation(region, base_rent, date_signed, date_start, anniversary_date, epc_label, lookup,
                       request_date=None):
    """Indexed rent on an anniversary.

    lookup(month) returns the health index of that month or raises IndexMissing.
    """
    start_month = month_before(date_signed)
    new_month = month_before(anniversary_date)
    start_index = lookup(start_month)
    new_index = lookup(new_month)
    factor, frozen, rate = freeze_correction(region, epc_label, date_start, start_month, lookup)
    if frozen and anniversary_date < frozen:
        factor = 1.0  # the freeze only weighs on anniversaries from the frozen one on
    theoretical = base_rent * new_index / start_index
    new_rent = theoretical / factor
    effective = anniversary_date
    if request_date:
        earliest = request_date - relativedelta(months=RETROACTIVE_MONTHS[region])
        effective = max(anniversary_date, earliest)
    return {
        "start_index_month": start_month,
        "start_index": start_index,
        "new_index_month": new_month,
        "new_index": new_index,
        "theoretical_rent": round(theoretical, 2),
        "correction_factor": round(factor, 6),
        "freeze_anniversary": frozen,
        "freeze_rate": rate,
        "new_rent": round(new_rent, 2),
        "effective_date": effective,
    }


def notice_end_date(notice_date, months):
    """End of a notice: it runs from the first day of the month after the notice."""
    # LEGAL-CHECK: art. 16 VWHD, art. 237 BHC, art. 55 Waals decreet 15-03-2018 - de opzegtermijn begint de eerste dag van de maand na de opzeg.
    start = notice_date.replace(day=1) + relativedelta(months=1)
    return start + relativedelta(months=months) - relativedelta(days=1)


def notice_deadline(date_end, lease_type, party="landlord"):
    """Last day to give notice so that the lease ends on date_end."""
    if lease_type == "short":
        months = SHORT_TERM_NOTICE_MONTHS
    elif lease_type == "nine":
        months = NINE_YEAR_NOTICE_MONTHS[party]
    else:
        return False
    # The notice starts on the first of the next month, so it must be given in the month before.
    return (date_end + relativedelta(days=1) - relativedelta(months=months)).replace(day=1) - relativedelta(days=1)
