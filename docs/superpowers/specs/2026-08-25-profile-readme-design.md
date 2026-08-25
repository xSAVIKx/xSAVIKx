# GitHub Profile README — Design

**Date:** 2026-08-25
**Repo:** published as public `xSAVIKx/xSAVIKx` (GitHub renders it on the profile page)
**Status:** approved design, ready for implementation planning

## Goal

A profile README that acts as a strong calling card: an honest, high-signal
snapshot of who Yurii Serhiichuk is and what he builds, readable in twenty
seconds, that stays current without manual upkeep.

Not optimized for a single conversion (hiring, speaking, or stars). Optimized
for signal density and for never going stale.

## Voice

Quiet authority. Plain prose, no emoji, no badges, no stats cards. The
credentials sit in the background; the work speaks. Fits on one laptop screen.

Explicitly rejected: badge walls, `github-readme-stats` cards, trophy/streak
widgets, contribution snake, typing-SVG animations. They are commoditized,
they render the page as someone else's SVGs, and they say nothing a reader
can act on.

## Content structure

Five blocks, in order:

### 1. Headline (static)

    # Yurii Serhiichuk

    Cloud architecture and DevOps.
    Google Developer Expert, Cloud.

Deliberately omits the employer and the job title. Yurii is changing roles
soon; a headline that needs editing when his situation changes is a headline
that goes stale. Domain framing survives the change untouched.

### 2. Positioning paragraph (static)

Two sentences: what he does, and what he is working on now. Draft:

> I make cloud infrastructure cheaper and less exciting to operate.
> Lately: agents that run production systems, and portable knowledge
> formats for LLM tooling.

### 3. Selected work (static, hand-curated)

Four repositories, one sentence each on why it matters. Four with real
sentences beats six with none. `openweathermap-java-api` and
`gcp-server-environments` are dropped from the README; they may stay pinned.

Draft copy, pending Yurii's line-by-line review:

- **sre-agent** — Multi-agent SRE platform: agents that triage and act on
  production incidents. (Python)
- **okf-skills** — Open Knowledge Format: your data's structure as a
  portable, versioned map, as code. (Go)
- **cloudevents/sdk-python** — Top contributor to the Python SDK for the
  CNCF CloudEvents spec. (verified: ranked first by commit count on the
  GitHub contributors endpoint, 2026-08-25)
- **AndroidScreencast** — Display and control Android devices from your
  desktop. (Java)

### 4. Writing (auto-updated)

The five most recent posts from the personal blog, with dates. This is the
only block automation may touch.

### 5. Contact / "Elsewhere" (static) — implemented heading is "## Elsewhere"

Website primary and visually dominant, everything else secondary:

    **[serhiichuk.dev](https://serhiichuk.dev)** — best place to reach me

    [LinkedIn](https://linkedin.com/in/YuriiSerhiichuk) ·
    [X](https://x.com/xSAVIKx) ·
    [Sessionize](https://sessionize.com/yuriiserhiichuk) ·
    [dev.to](https://dev.to/xsavikx) ·
    [Medium](https://xsavikx.medium.com/)

## Technical design

### Repo layout

    README.md                          # profile page; source of truth for all static copy
    scripts/update_writing.py          # stdlib-only; fetches posts, rewrites one block
    tests/test_update_writing.py       # fixture-driven, no network
    tests/fixtures/blog-rss.xml        # captured from the live feed
    .github/workflows/update-readme.yml
    docs/superpowers/specs/            # this document

### Dependencies

Standard library only: `urllib.request`, `xml.etree.ElementTree`, `email.utils`
(for RFC 2822 date parsing), `argparse`. No `requirements.txt`, no `pip install`
step in CI, no dependency updates to triage, no supply chain.

### Data source

Single source: `https://serhiichuk.dev/blog/rss.xml`

Verified 2026-08-25: valid RSS 2.0, channel title "Yurii Serhiichuk — Blog",
10 items, elements `item/title`, `item/link`, `item/guid`, `item/description`,
`item/pubDate`, dates in RFC 2822 (`Fri, 21 Aug 2026 00:00:00 GMT`).

**No fallback source.** A dev.to fallback was considered and rejected: dev.to
carries 3 posts to the blog's 10, so falling back on a transient outage would
*downgrade* the block and then restore it the next night — churn that makes
the page worse rather than more resilient. The failure rule below covers
outages correctly on its own.

### Update mechanism

`README.md` holds the real content. The script rewrites only the text between:

    <!-- posts start -->
    <!-- posts end -->

Everything outside those markers is hand-written and never touched by
automation. Replacement is idempotent: running twice yields the same file.

Workflow `update-readme.yml`:

- triggers: nightly cron `0 6 * * *`, `workflow_dispatch`, push to `main`
- `permissions: contents: write`, uses the built-in `GITHUB_TOKEN` (no PAT)
- commits only when `git diff` is non-empty, to avoid 365 empty commits a year

### Failure behavior

If the feed fetch or parse fails, the script exits non-zero **without
modifying README.md**. The Action goes red and notifies; the profile page
keeps showing the last known-good list.

The worst failure mode of a self-updating README is publishing an empty
section to the world. This design makes that state unreachable: the README is
only ever written from a fully parsed, non-empty result.

Each request gets a 10-second timeout and one retry.

### Rendering

Each item renders as a dated list entry, newest first, capped at 5:

    - [Post title](https://serhiichuk.dev/blog/post-slug/) — 21 Aug 2026

## Testing

Test the two things that can actually be wrong. No network in the suite.

**Marker replacement:**
- replaces content between markers, leaves surrounding text byte-identical
- idempotent across repeated runs
- errors clearly when a marker is missing or the pair is inverted

**Feed parsing:**
- parses the captured fixture into `(title, url, date)` triples
- parses RFC 2822 dates correctly, including the GMT offset
- caps at 5 items, newest first
- a feed with fewer than 5 items renders all of them; this is not an error
- raises on malformed XML and on a well-formed feed with zero items

**Integration:** a `--dry-run` flag prints the rendered block to stdout without
writing, for eyeballing before the first real commit.

## Out of scope (YAGNI)

- Speaking/talks block — the public Sessionize profile lists no sessions;
  automating it would require enabling the Sessionize API endpoint. Revisit
  only if that changes.
- Recent-releases block — considered and cut. Deliberate.
- Any stats, badge, streak, or trophy widget.
- Merging Medium or dev.to posts into the writing block; the blog is the
  superset and the canonical home.
- Scraping HTML anywhere. Feeds and APIs only.

## Open items

1. Yurii reviews the selected-work copy line by line before it ships.
2. Confirm whether "top contributor" should read "maintainer" for
   `cloudevents/sdk-python`.
3. Remote must be created as a **public** repo named exactly `xSAVIKx`.
   The local directory name (`xsavikx-github-profile`) does not matter.
