from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def money(value, field, allow_zero=False):
    try:
        result = Decimal(str(value).replace(",", "."))
        if not result.is_finite() or abs(result) >= Decimal("10000000000"):
            raise ValueError()
        result = result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if result < 0 or (result == 0 and not allow_zero):
            raise ValueError()
    except (ValueError, InvalidOperation):
        raise ValueError(f"Valor invalido para {field}.")
    return result


def positive_integer(value, field):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise ValueError(f"{field} deve ser inteiro positivo.")
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} deve ser inteiro positivo.")
    if result <= 0 or result > 2147483647:
        raise ValueError(f"{field} deve ser inteiro positivo.")
    return result


def allocate_money(amount, balances):
    total = sum(balances, Decimal("0.00"))
    if amount < 0 or amount > total or any(balance < 0 for balance in balances):
        raise ValueError("Estorno ultrapassa o saldo da operacao original.")
    allocated = Decimal("0.00")
    cumulative = Decimal("0.00")
    portions = []
    for balance in balances:
        cumulative += balance
        target = (amount * cumulative / total).quantize(Decimal("0.01")) if total else Decimal("0.00")
        portions.append(target - allocated)
        allocated = target
    return portions
