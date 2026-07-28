"""Render a Livingdocs article (webhook payload or CMS row) to markdown.

Pure functions, standard library only — no HTTP, no Snowflake, no config. This
lives in chm_utils rather than in a service repo because several consumers need
identical rendering: chm-stream embeds the output, chm-mcp serves it as
retrieval context, and any divergence between them silently changes what search
returns.

Livingdocs `content` is an array whose first element is the `article-container`
component; every component carries a `content` dict of directives (strings hold
inline HTML, dicts with a `url` are images) and optional `containers` of child
components. A "document" here is any mapping with `content`, and optionally
`metadata`, `systemdata` and `custom` — the shape of both the collector's
webhook payload and a row of `chm_core_prod.content.articles_v2`.

    from chm_utils.livingdocs import publication_to_markdown, teaser_text, is_ticker

    markdown = publication_to_markdown(document)              # capped for embedding
    full     = publication_to_markdown(document, max_chars=None)

The component/directive tables below are not guesses: they were derived from an
inventory of every component type occurring in
`chm_core_prod.content.articles_v2` (is_current, publication_date > 2026-01-01;
69 distinct components, 89k articles) — see chm-stream's
scripts/component_inventory.sql, which regenerates it. Unknown components fall
back to rendering their string directives as plain paragraphs, so new editorial
components degrade gracefully instead of vanishing.

Live tickers are the reason for the truncation logic: they average ~57k
characters and reach 300k (vs ~3.5k for a normal article), which is both
useless as a single embedding vector and expensive to embed. Ticker posts are
stored newest-first, so keeping the head keeps the latest developments.
"""

import html
import re

# Cap on the markdown handed to the embedding model. The 95th percentile of a
# normal ('default') article is ~6.6k chars, so this passes ~95% of ordinary
# articles through untouched while bounding tickers and outliers.
MAX_EMBED_CHARS = 8000

# Live tickers/newsblogs: how many post blocks to keep (newest first).
MAX_TICKER_POSTS = 5

# Component name -> markdown heading prefix. These carry their text in the
# `title` directive rather than `text`.
_HEADINGS = {
    "subtitle": "##",
    "newsletter-subtitle": "##",
    "newsletter-chaptertitle": "##",
    "infobox": "###",
}

_QUOTES = {"quote"}

# Components whose text is a cross-reference, teaser or unresolved document
# $ref, layout chrome, advertising, or a third-party embed's markup. None of
# them carry article prose.
_SKIP = {
    # teasers / references to *other* documents
    "article-teaser",
    "teaser-author",
    "article-list",
    "newsletter-article-teaser",
    "newsletter-article-list",
    "teaser-infobox-snippet",
    "topic-page",
    "toc",
    # navigational labels ("Region", "2/3")
    "seitenverweis",
    # layout / chrome / advertising
    "divider",
    "trennlinie",
    "newsletter-divider",
    "newsletter-spacer-block",
    "newsletter-advertising-block",
    "newsletter-logo-chmedia",
    "newsletter-header",
    "newsletter-footer",
    "newsletter-greeting",
    "newsletter-conversion-large",
    "newsletter-nps-survey",
    "newsletter-author-image",
    "advertisement-image",
    "sponsored-content",
    # third-party embeds: script/markup payloads, no prose of their own
    "free-html",
    "iframe",
    "qEmbed",
    "instagram-embed",
    "twitter-oembed",
    "facebook-embed",
    "tiktok-oembed",
    "reddit-oembed",
    "datawrapper-oembed",
    "opinary-embed",
}

# Components rendered only through their children (their own directives are
# empty or purely presentational).
_CONTAINER_ONLY = {"highlighted-post", "gallery-container", "infobox-snippet-container"}

_HEADER_COMPONENTS = ("header", "head", "headerLongform", "newsletter-name", "asset-head-gallery")

# Container names that carry the article's header/footer rather than its body,
# used to order a component's containers by meaning instead of mapping order.
_HEADER_CONTAINERS = {"header", "head", "title"}
_FOOTER_CONTAINERS = {"footer"}

# List components, and the marker each renders its items with.
_LIST_MARKERS = {"list": "-", "numeric-list": "1."}

# Indent one nesting level of a list that has no parent item to align under.
_LIST_INDENT = "  "

# Header-style components: ordered directives with their own formatting.
_HEADER_FORMATS = (
    ("label", "**{}**"),
    ("catchline", "**{}**"),
    ("title", "# {}"),
    ("lead", "*{}*"),
)

# Directive keys that annotate rather than carry the main content.
_CAPTION_KEYS = {"caption", "author", "source", "credit", "quelle", "posterauthor"}

# Media components: keep the human-written caption/credit, drop the asset.
_MEDIA = {
    "image",
    "asset-image",
    "newsletter-image",
    "kaltura-embed",
    "youtube-oembed",
    "audioUrl",
}

# Directives that are metadata on a ticker post, not prose.
_TICKER_DATE_KEYS = ("current-date-full", "current-date")

_TICKER_POSTS = {"liveticker-post"}


def _inline_md(text):
    """Livingdocs inline HTML (em/strong/a/br + entities) -> markdown text."""
    t = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    t = re.sub(r"<(strong|b)\b[^>]*>(.*?)</\1>", r"**\2**", t, flags=re.S | re.I)
    t = re.sub(r"<(em|i)\b[^>]*>(.*?)</\1>", r"*\2*", t, flags=re.S | re.I)
    t = re.sub(
        r"""<a\b[^>]*href=["']([^"']*)["'][^>]*>(.*?)</a>""",
        r"[\2](\1)",
        t,
        flags=re.S | re.I,
    )
    t = re.sub(r"<[^>]+>", "", t)  # strip whatever inline markup remains
    t = html.unescape(t)
    t = t.replace("\xa0", " ")
    return t.strip()


def _text(value):
    """Directive value -> clean text. Accepts strings and li-text objects."""
    if isinstance(value, dict):
        value = value.get("text")
    if isinstance(value, str) and value.strip():
        return _inline_md(value)
    return None


def _container_rank(name):
    """Sort key putting a component's containers in reading order.

    Payloads normally store `header` before `main`, but that is mapping order,
    not a guarantee — and the header carries the title, kicker and lead, the
    strongest retrieval signals and the ones a length cap must never be the
    thing to drop. Containers of equal rank keep their mapping order.
    """
    if name in _HEADER_CONTAINERS:
        return 0
    if name in _FOOTER_CONTAINERS:
        return 2
    return 1


def _children(comp):
    containers = comp.get("containers") or {}
    for name in sorted(containers, key=_container_rank):
        for child in containers[name] or []:
            if isinstance(child, dict):
                yield child


def _list_lines(comp, marker, include_images, indent=""):
    """`list` / `numeric-list`: optional title, then list-item children.

    Lists nest — a sub-list is a child of either the list or one of its items —
    and the indent carries that depth into the markdown.
    """
    lines = []
    title = _text((comp.get("content") or {}).get("title"))
    if title:
        lines.append(f"{indent}**{title}**")
    number = 0
    for child in _children(comp):
        nested = _LIST_MARKERS.get(child.get("component") or "")
        if nested:
            # a list nested straight inside a list, without an item of its own
            lines.extend(
                _list_lines(child, nested, include_images, indent + _LIST_INDENT)
            )
            continue
        number += 1
        bullet = f"{number}." if marker == "1." else marker
        lines.extend(_list_item_lines(child, bullet, indent, include_images))
    return lines


def _list_item_lines(item, bullet, indent, include_images):
    """One list item: its own text carries the marker, anything nested inside it
    is indented underneath it. Prefixing every line a child produced with the
    marker would flatten a sub-list into siblings of its parent item and lose
    the hierarchy the source document has."""
    inner = indent + " " * (len(bullet) + 1)  # align with the item's own text
    lines = []
    # the item's own directives only; its children are placed below, indented
    for text in _component_lines({**item, "containers": {}}, include_images):
        lines.append(f"{indent}{bullet} {text}" if not lines else f"{inner}{text}")
    for child in _children(item):
        nested = _LIST_MARKERS.get(child.get("component") or "")
        if nested:
            lines.extend(_list_lines(child, nested, include_images, inner))
        else:
            lines.extend(
                f"{inner}{text}" for text in _component_lines(child, include_images)
            )
    return lines


def _image_md(val):
    url = val.get("url") or val.get("originalUrl")
    if not url:
        return None
    alt = _text(val.get("altText")) or "image"
    return f"![{alt}]({url})"


def _media_lines(comp, include_images):
    """The editorial text attached to an asset (caption, credit), and — only
    when rendering for display — the asset itself. Image URLs are pure noise in
    an embedding, so they are omitted by default."""
    content = comp.get("content") or {}
    lines = []
    if include_images:
        for val in content.values():
            if isinstance(val, dict):
                img = _image_md(val)
                if img:
                    lines.append(img)
    for key in ("title", "description", "caption", "credit", "author"):
        text = _text(content.get(key))
        if text:
            lines.append(f"*{text}*")
    return lines


def _ticker_post_lines(comp, include_images):
    """A ticker post: its timestamp as a heading, then its child components."""
    content = comp.get("content") or {}
    lines = []
    stamp = [
        _text(content.get(key)) for key in _TICKER_DATE_KEYS
    ]
    stamp = [s for s in stamp if s]
    if stamp:
        # bold rather than a heading: posts contain their own `subtitle`
        # headings, and a heading here would invert the hierarchy
        lines.append(f"**{', '.join(stamp)}**")
    for child in _children(comp):
        lines.extend(_component_lines(child, include_images))
    return lines


def _component_lines(comp, include_images=False):
    if not isinstance(comp, dict):
        return []

    name = comp.get("component") or ""
    if name in _SKIP:
        return []

    content = comp.get("content") or {}
    lines = []

    if name in _HEADER_COMPONENTS:
        for key, fmt in _HEADER_FORMATS:
            text = _text(content.get(key))
            if text:
                lines.append(fmt.format(text))
        # containers hold author teasers only -> nothing to recurse into
        return lines

    if name in _TICKER_POSTS:
        return _ticker_post_lines(comp, include_images)

    if name in _LIST_MARKERS:
        return _list_lines(comp, _LIST_MARKERS[name], include_images)

    if name in _MEDIA:
        return _media_lines(comp, include_images)

    if name == "catchword":
        # a single topic keyword ("Tennis", "Trockenheit") - useful retrieval signal
        text = _text(content.get("text"))
        return [f"**{text}**"] if text else []

    if name == "personbox":
        for key in ("name", "role", "bio"):
            text = _text(content.get(key))
            if text:
                lines.append(f"**{text}**" if key == "name" else text)
        return lines

    if name == "question":
        text = _text(content.get("text"))
        return [f"**{text}**"] if text else []

    if name not in _CONTAINER_ONLY:
        heading = _HEADINGS.get(name)
        for key, val in content.items():
            if isinstance(val, dict):
                continue  # assets/services -> handled by _MEDIA, else no text
            text = _text(val)
            if not text:
                continue
            if heading:
                lines.append(f"{heading} {text}")
            elif name in _QUOTES:
                lines.append(f"> {text}")
            elif key in _CAPTION_KEYS:
                lines.append(f"*{text}*")
            else:
                lines.append(text)

    for child in _children(comp):
        lines.extend(_component_lines(child, include_images))

    return lines


def _iter_components(components):
    for comp in components:
        if not isinstance(comp, dict):
            continue
        yield comp
        yield from _iter_components(list(_children(comp)))


def teaser_text(document, join_char="\n"):
    """Teaser label plus title, from metadata only — what a teaser displays.

    Livingdocs renders a teaser from metadata (`teaserLabel`, `title`); the
    article's `header` component is article-page furniture that no teaser shows.
    A consumer matching on "what the teaser says" wants this rather than
    `header_text`.

    On web articles the two agree in ~96% of cases and each covers ~98%, so the
    choice is about semantics, not coverage. The cleaning is not optional
    though: metadata carries raw entities and non-breaking spaces, so without it
    `Abo+&nbsp;Wanderung` would reach an embedding verbatim.
    """
    metadata = document.get("metadata") or {}
    parts = [_text(metadata.get("teaserLabel")), _text(metadata.get("title"))]
    parts = [p for p in parts if p]
    return join_char.join(parts) if parts else None


def header_text(document, join_char="\n"):
    """Kicker/catchline plus title — the short 'what is this about' signal.

    The kicker lives in `label` on a `header` component and in `catchline` on
    `headerLongform`; both are taken when present. Falls back to `teaser_text`
    for payloads without a header component.
    """
    for comp in _iter_components(_root_components(document)):
        if (comp.get("component") or "") not in _HEADER_COMPONENTS:
            continue
        content = comp.get("content") or {}
        parts = [_text(content.get(key)) for key in ("label", "catchline", "title")]
        parts = [p for p in parts if p]
        if parts:
            return join_char.join(parts)

    return teaser_text(document, join_char)


def _root_components(document):
    """Unwrap the article-container, tolerating payloads without one."""
    content = document.get("content") or []
    if not content:
        return []
    first = content[0]
    if isinstance(first, dict) and first.get("component") == "article-container":
        return [first]
    return [c for c in content if isinstance(c, dict)]


def is_ticker(document):
    """Mirror of the `ticker-newsblog` rule in chm-models' articles_v2_flattened,
    restricted to the signals present in a webhook payload."""
    metadata = document.get("metadata") or {}
    custom = document.get("custom") or {}

    if (custom.get("documentClass") or "") == "ticker":
        return True
    if (metadata.get("articleFormat") or "") == "ticker-newsblog":
        return True
    if (metadata.get("articleType") or "") == "live":
        return True

    title = metadata.get("title") or ""
    if "++" in title:
        return True

    label = (metadata.get("teaserLabel") or "").lower()
    if "ticker" in label or "newsblog" in label:
        return True

    for comp in _root_components(document):
        if _has_ticker_component(comp):
            return True
    return False


def _has_ticker_component(comp):
    if not isinstance(comp, dict):
        return False
    name = comp.get("component") or ""
    if name in _TICKER_POSTS:
        return True
    if name == "free-html":
        embed = (comp.get("content") or {}).get("free-html") or {}
        code = (embed.get("params") or {}).get("embedCode") or ""
        if "norkon.net" in code.lower():
            return True
    return any(_has_ticker_component(child) for child in _children(comp))


def _truncate(markdown, max_chars):
    """Cut to max_chars on a paragraph boundary (never mid-sentence)."""
    if max_chars is None or len(markdown) <= max_chars:
        return markdown
    cut = markdown.rfind("\n\n", 0, max_chars)
    if cut <= 0:
        cut = markdown.rfind(" ", 0, max_chars)
    if cut <= 0:
        cut = max_chars
    return markdown[:cut].rstrip()


def _limit_ticker_posts(lines_per_component, max_posts):
    """Keep the header block plus the newest `max_posts` ticker posts."""
    kept = []
    n_posts = 0
    for is_post, lines in lines_per_component:
        if is_post:
            if n_posts >= max_posts:
                continue
            n_posts += 1
        kept.extend(lines)
    return kept


def _walk_top_level(components, include_images):
    """Yield (is_ticker_post, lines) for each top-level body component, so
    ticker posts can be counted and capped before the text is joined."""
    for comp in components:
        name = comp.get("component") or ""
        if name == "article-container" or name in _CONTAINER_ONLY:
            for child in _children(comp):
                yield from _walk_top_level([child], include_images)
            continue
        yield name in _TICKER_POSTS, _component_lines(comp, include_images)


def publication_to_markdown(
    document,
    max_chars=MAX_EMBED_CHARS,
    max_ticker_posts=MAX_TICKER_POSTS,
    include_images=False,
):
    """Livingdocs document -> markdown string.

    Defaults are tuned for embedding: tickers keep their header plus the newest
    `max_ticker_posts` posts, the result is capped at `max_chars` on a paragraph
    boundary, and image URLs are omitted because they are noise in a vector.

    To render an article for display or as LLM context instead, turn all three
    off:

        publication_to_markdown(doc, max_chars=None, max_ticker_posts=None,
                                include_images=True)
    """
    components = _root_components(document)
    blocks = list(_walk_top_level(components, include_images))

    if max_ticker_posts is not None and is_ticker(document):
        body = _limit_ticker_posts(blocks, max_ticker_posts)
    else:
        body = [line for _, lines in blocks for line in lines]

    # Fall back to metadata when the body produced no top-level heading.
    metadata = document.get("metadata") or {}
    header = []
    if not any(line.startswith("# ") for line in body):
        title = _text(metadata.get("title"))
        if title:
            header.append(f"# {title}")
        lead = _text(metadata.get("lead") or metadata.get("teaserLead"))
        if lead:
            header.append(f"*{lead}*")

    markdown = "\n\n".join(line for line in header + body if line)
    markdown = re.sub(r"\n{3,}", "\n\n", markdown).strip()
    return _truncate(markdown, max_chars)
