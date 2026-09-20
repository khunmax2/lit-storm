# SearXNG, self-hosted

A metasearch engine for the app to research with: one query fans out to
Google, Bing, DuckDuckGo, arXiv, PubMed, Semantic Scholar and dozens more,
and comes back as one list. No key, and no rate limit but your own.

## Running it

```bash
docker compose up -d
```

Then on the app's **Search sources** page, enter `http://localhost:8080`,
press **Test**, and **Use this**.

Listens on `127.0.0.1:8080` only. A metasearch instance open to a network
gets used as a proxy by strangers within hours.

## The one setting that matters

JSON output is **off by default** in SearXNG, and a public instance almost
never turns it on. Without it, every request from the app gets a 403 and a
page of HTML. `settings.yml` here switches it on:

```yaml
search:
  formats: [html, json]
```

The app's Test button reports the 403 by name if you point it at an
instance that lacks this, rather than a bare "no results".

## Why there is no academic fork here

This was going to be built on `searxng-LDR-academic`, a fork described as
SearXNG cut down for academic work. Its `settings.yml` was checked before
deciding:

- 150 engines listed, 82 disabled, **68 enabled**
- of those 68, **12 are academic** — the rest are Google, Bing, GitHub,
  a recipe site, a lyrics site, a weather service
- **10 of the 12 are stock upstream engines**, named in upstream's own
  `settings.yml` already; the fork adds only `openaire` and `loc`

So the fork contributes two engine files, in exchange for carrying ten
months of divergence from an upstream whose engines break as the sites
they scrape change. This `settings.yml` enables the ten stock engines
instead. If OpenAIRE or Library of Congress matter, the two files can be
copied from the fork's `searx/engines/`.

## Before this faces anyone but you

- Set `SEARXNG_SECRET` to something generated; the default is for local use.
- Keep the `limiter` off only while the app is the sole client.
- `searxng/searxng:latest` moves weekly and engines break as target sites
  change. Pin a tag once it works, and expect to bump it.
