def largest_remainder(total, weights, digits=0):
    """Split total over weights, rounded to `digits` decimals, summing exactly to total.

    Every part is rounded down first; the units that are left go to the parts with the
    largest rounding remainder. A negative total (credit note) is split as its absolute
    value and the sign is applied afterwards.
    """
    weight_sum = sum(weights)
    if not weights or not weight_sum:
        raise ValueError("Cannot split over weights that add up to zero.")
    factor = 10 ** digits
    sign = -1 if total < 0 else 1
    units = round(abs(total) * factor)
    exact = [units * w / weight_sum for w in weights]
    parts = [int(x) for x in exact]
    by_remainder = sorted(range(len(weights)), key=lambda i: exact[i] - parts[i], reverse=True)
    for i in by_remainder[: units - sum(parts)]:
        parts[i] += 1
    return [sign * p / factor for p in parts] if digits else [sign * p for p in parts]
