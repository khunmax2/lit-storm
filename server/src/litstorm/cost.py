"""What a Run cost, estimated (docs/web-app-design.md: ค่าใช้จ่ายโดยประมาณ).

Tokens and search calls are counted exactly, from the usage the Run's process
reports stage by stage — including a stage that failed part-way. Money is an
estimate: tokens times a price per million, taken from what an Administrator
entered for the model, or else LiteLLM's price table, or else unknown (None)
rather than a guess.
"""

from decimal import Decimal


def totals(usage_events):
    """(tokens_in, tokens_out, search_calls, tokens by model) over a Run."""
    tokens_in = tokens_out = search = 0
    by_model = {}
    for event in usage_events:
        for model, used in (event.get("llm") or {}).items():
            p = int(used.get("prompt_tokens", 0) or 0)
            c = int(used.get("completion_tokens", 0) or 0)
            tokens_in += p
            tokens_out += c
            m = by_model.setdefault(model, [0, 0])
            m[0] += p
            m[1] += c
        search += sum(int(n or 0) for n in (event.get("search") or {}).values())
    return tokens_in, tokens_out, search, by_model


def _table_price(model, prompt_tokens, completion_tokens):
    try:
        import litellm

        cost_in, cost_out = litellm.cost_per_token(
            model=model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        )
    except Exception:  # noqa: BLE001 - unknown model: no estimate, not an error
        return None
    return Decimal(str(cost_in)) + Decimal(str(cost_out))


def estimate(by_model, price_in=None, price_out=None):
    """US dollars for the tokens used, or None when no price is known.

    `price_in`/`price_out` are the Administrator's USD per million tokens for
    the Run's model and win over the table when set.
    """
    if not by_model:
        return Decimal(0)
    total = Decimal(0)
    for model, (p, c) in by_model.items():
        if price_in is not None and price_out is not None:
            total += Decimal(p) * Decimal(price_in) / 1_000_000 + Decimal(c) * Decimal(price_out) / 1_000_000
            continue
        found = _table_price(model, p, c)
        if found is None:
            return None
        total += found
    return total.quantize(Decimal("0.000001"))
