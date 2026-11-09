"""What a Run cost, estimated (docs/web-app-design.md: ค่าใช้จ่ายโดยประมาณ).

Tokens and search calls are counted exactly, from the usage the Run's process
reports stage by stage — including a stage that failed part-way. Money is an
estimate: tokens times a price per million, taken from what an Administrator
entered for the model, or else LiteLLM's price table, or else unknown (None)
rather than a guess, with the models that had no price named (price).
"""

from dataclasses import dataclass, field
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


def paid(usage_events):
    """US dollars a remote service reported for its own work (the `usd` of a
    usage event, catalog.remote), already priced there."""
    return sum((Decimal(str(e["usd"])) for e in usage_events if e.get("usd") is not None), Decimal(0))


# A router resells other vendors' models under a prefix of its own, at the
# vendor's price. LiteLLM's table may know such a model only by the vendor's
# name: on 2026-10-09 it dropped every openrouter/ row (newer LiteLLM bills
# OpenRouter from the price each response carries), and LiteLLM fetches that
# table from GitHub when it is first imported.
ROUTERS = ("openrouter/",)


def table_names(model):
    """The names LiteLLM's table is asked for, in turn: the model's own, then
    for a router's model ("openrouter/google/x") the vendor's bare name ("x")."""
    names = [model]
    for router in ROUTERS:
        if model.startswith(router):
            names.append(model[len(router):].split("/", 1)[-1])
    return list(dict.fromkeys(names))


def _table_cost(name, prompt_tokens, completion_tokens):
    """(in, out) US dollars by LiteLLM's table under exactly this name, or None."""
    try:
        import litellm

        cost_in, cost_out = litellm.cost_per_token(
            model=name, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
        )
    except Exception:  # noqa: BLE001 - unknown model: no estimate, not an error
        return None
    return Decimal(str(cost_in)), Decimal(str(cost_out))


def _table_price(model, prompt_tokens, completion_tokens):
    """(US dollars, the name the table priced it by), or None."""
    for name in table_names(model):
        found = _table_cost(name, prompt_tokens, completion_tokens)
        if found is not None:
            return found[0] + found[1], name
    return None


def table_rates(model):
    """(in, out) USD per million tokens by LiteLLM's table, and the name it
    knows the model by; None when it has no price. Asked at a thousand tokens,
    below any long-context tier."""
    for name in table_names(model):
        found = _table_cost(name, 1000, 1000)
        if found is not None:
            return found[0] * 1000, found[1] * 1000, name
    return None


@dataclass
class Priced:
    usd: Decimal | None  # None when some model has no price
    unpriced: list = field(default_factory=list)  # models without one
    priced_as: dict = field(default_factory=dict)  # model -> the table name used, when not its own


def price(by_model, price_in=None, price_out=None, prices=None):
    """US dollars for the tokens used, and what could not be priced.

    `prices` maps a model's name, as its usage is reported, to the
    Administrator's (in, out) USD per million tokens, which win over the
    table; under "*", the price for any name not listed (the Run's main
    model, whose usage a provider may report under a name of its own).
    `price_in`/`price_out` price every model alike (one-model Runs).
    """
    if not by_model:
        return Priced(Decimal(0))
    total = Decimal(0)
    unpriced, priced_as = [], {}
    for model, (p, c) in by_model.items():
        chosen = (prices or {}).get(model) or (prices or {}).get("*")
        if chosen:
            price_in_m, price_out_m = chosen
            total += Decimal(p) * Decimal(price_in_m) / 1_000_000 + Decimal(c) * Decimal(price_out_m) / 1_000_000
            continue
        if price_in is not None and price_out is not None:
            total += Decimal(p) * Decimal(price_in) / 1_000_000 + Decimal(c) * Decimal(price_out) / 1_000_000
            continue
        found = _table_price(model, p, c)
        if found is None:
            unpriced.append(model)
            continue
        total += found[0]
        if found[1] != model:
            priced_as[model] = found[1]
    usd = None if unpriced else total.quantize(Decimal("0.000001"))
    return Priced(usd, unpriced, priced_as)


def estimate(by_model, price_in=None, price_out=None, prices=None):
    """US dollars for the tokens used, or None when no price is known (price)."""
    return price(by_model, price_in, price_out, prices).usd
