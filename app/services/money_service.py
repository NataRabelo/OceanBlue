from decimal import Decimal


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
