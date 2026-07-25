import json

import pytest

from chm_utils import livingdocs
from chm_utils.livingdocs import header_text, is_ticker, publication_to_markdown


def load_fixture(name):
    """A real CMS payload, dumped from chm_core_prod.content.articles_v2."""
    with open(f'tests/fixtures/{name}.json') as f:
        return json.load(f)


def component(name, content=None, containers=None):
    comp = {'component': name, 'content': content or {}}
    if containers:
        comp['containers'] = containers
    return comp


def document(components, metadata=None, custom=None, header=None):
    containers = {'main': components}
    if header:
        containers['header'] = header
    return {
        'content': [component('article-container', containers=containers)],
        'metadata': metadata or {},
        'custom': custom or {},
    }


class TestInlineMarkup:

    def test_bold_italic_links_and_breaks(self):
        doc = document([
            component('paragraph', {'text': 'Ein <strong>fetter</strong> und <em>kursiver</em> Satz.'}),
            component('paragraph', {'text': 'Mit <a href="https://example.ch">Link</a> &amp; Entity.'}),
            component('paragraph', {'text': 'Zeile eins<br>Zeile zwei'}),
        ])
        md = publication_to_markdown(doc)

        assert 'Ein **fetter** und *kursiver* Satz.' in md
        assert '[Link](https://example.ch) & Entity.' in md
        assert 'Zeile eins\nZeile zwei' in md

    def test_unknown_markup_is_stripped(self):
        doc = document([component('paragraph', {'text': 'H<sub>2</sub>O und <div>Rest</div>'})])
        md = publication_to_markdown(doc)

        assert '<' not in md
        assert 'H2O' in md

    def test_non_breaking_space_becomes_space(self):
        doc = document([component('paragraph', {'text': 'Vor\xa0dem Titel'})])
        assert '\xa0' not in publication_to_markdown(doc)


class TestComponents:

    def test_directive_key_depends_on_component(self):
        # subtitle carries text in `title`, paragraph in `text`, quote renders
        # as a blockquote, catchword is a bare topic keyword
        doc = document([
            component('subtitle', {'title': 'Zwischentitel'}),
            component('paragraph', {'text': 'Fliesstext.'}),
            component('quote', {'text': 'Ein Zitat.'}),
            component('catchword', {'text': 'Tennis'}),
        ])
        md = publication_to_markdown(doc)

        assert '## Zwischentitel' in md
        assert 'Fliesstext.' in md
        assert '> Ein Zitat.' in md
        assert '**Tennis**' in md

    def test_header_directives_are_ordered(self):
        doc = document([], header=[
            component('header', {'label': 'Kicker', 'title': 'Titel', 'lead': 'Lead'}),
        ])
        md = publication_to_markdown(doc)

        assert md.index('**Kicker**') < md.index('# Titel') < md.index('*Lead*')

    def test_nested_containers_are_rendered(self):
        doc = document([
            component('infobox', {'title': 'Zur Person'}, containers={
                'infoboxContent': [component('paragraph', {'text': 'Verschachtelt.'})],
            }),
        ])
        md = publication_to_markdown(doc)

        assert '### Zur Person' in md
        assert 'Verschachtelt.' in md

    def test_interview_question_is_emphasised(self):
        doc = document([
            component('question', {'text': 'Wie geht es Ihnen?'}),
            component('answer', {'text': 'Gut, danke.'}),
        ])
        md = publication_to_markdown(doc)

        assert '**Wie geht es Ihnen?**' in md
        assert 'Gut, danke.' in md

    def test_lists_render_as_bullets(self):
        doc = document([
            component('list', {'title': 'Punkte'}, containers={
                'list': [
                    component('list-item', {'text': 'Eins'}),
                    component('list-item', {'text': 'Zwei'}),
                ],
            }),
        ])
        md = publication_to_markdown(doc)

        assert '**Punkte**' in md
        assert '- Eins' in md
        assert '- Zwei' in md

    @pytest.mark.parametrize('name,content', [
        ('article-teaser', {'teaser': {'title': 'Anderer Artikel'}}),
        ('teaser-author', {'teaser': {'name': 'Autor'}}),
        ('seitenverweis', {'text': 'Region'}),
        ('free-html', {'free-html': {'params': {'embedCode': '<script>x</script>'}}}),
        ('toc', {'toc': {'entries': ['Kapitel']}}),
    ])
    def test_non_article_components_are_skipped(self, name, content):
        doc = document([
            component('paragraph', {'text': 'Echter Artikeltext.'}),
            component(name, content),
        ])
        md = publication_to_markdown(doc)

        assert 'Echter Artikeltext.' in md
        for noise in ('Anderer Artikel', 'Autor', 'Region', 'script', 'Kapitel'):
            assert noise not in md

    def test_media_keeps_caption_drops_url(self):
        doc = document([
            component('image', {
                'image': {'url': 'https://cdn.example.ch/x.jpg'},
                'caption': 'Eine Bildlegende.',
                'author': 'Fotograf',
            }),
        ])
        md = publication_to_markdown(doc)

        assert 'Eine Bildlegende.' in md
        assert 'Fotograf' in md
        assert 'cdn.example.ch' not in md

    def test_unknown_component_degrades_to_text(self):
        doc = document([component('brand-new-component', {'text': 'Wichtiger Text.'})])
        assert 'Wichtiger Text.' in publication_to_markdown(doc)

    def test_falls_back_to_metadata_when_no_header(self):
        doc = document(
            [component('paragraph', {'text': 'Nur Fliesstext.'})],
            metadata={'title': 'Metadaten-Titel', 'lead': 'Metadaten-Lead'},
        )
        md = publication_to_markdown(doc)

        assert md.startswith('# Metadaten-Titel')
        assert '*Metadaten-Lead*' in md

    def test_document_without_article_container(self):
        doc = {'content': [component('paragraph', {'text': 'Lose Komponente.'})], 'metadata': {}}
        assert 'Lose Komponente.' in publication_to_markdown(doc)

    def test_empty_document_is_empty_string(self):
        assert publication_to_markdown({'content': []}) == ''


class TestHeaderText:

    def test_label_and_title_without_lead(self):
        doc = document([], header=[
            component('header', {'label': 'Kicker', 'title': 'Der Titel', 'lead': 'Das Lead'}),
        ])
        assert header_text(doc) == 'Kicker\nDer Titel'

    def test_catchline_from_header_longform(self):
        doc = document([component('headerLongform', {'catchline': 'Serie', 'title': 'Teil 1'})])
        assert header_text(doc) == 'Serie\nTeil 1'

    def test_falls_back_to_metadata(self):
        doc = document(
            [component('paragraph', {'text': 'Text.'})],
            metadata={'teaserLabel': 'Analyse', 'title': 'Der Titel'},
        )
        assert header_text(doc) == 'Analyse\nDer Titel'

    def test_returns_none_without_any_title(self):
        assert header_text(document([])) is None


class TestTickerDetection:

    @pytest.mark.parametrize('doc', [
        document([], custom={'documentClass': 'ticker'}),
        document([], metadata={'articleFormat': 'ticker-newsblog'}),
        document([], metadata={'articleType': 'live'}),
        document([], metadata={'title': 'Krieg ++ Neue Angriffe'}),
        document([], metadata={'teaserLabel': 'Newsblog Basel'}),
        document([component('liveticker-post', {'current-date': '10:00 Uhr'})]),
        document([component('free-html', {
            'free-html': {'params': {'embedCode': '<div src="https://norkon.net/live"></div>'}},
        })]),
    ])
    def test_signals(self, doc):
        assert is_ticker(doc)

    def test_ordinary_article_is_not_a_ticker(self):
        doc = document(
            [component('paragraph', {'text': 'Normal.'})],
            metadata={'title': 'Ein normaler Artikel'},
        )
        assert not is_ticker(doc)


class TestTruncation:

    def _ticker(self, n_posts):
        posts = [
            component('liveticker-post', {'current-date': f'{hour}:00 Uhr'}, containers={
                'content': [component('paragraph', {'text': f'Meldung {hour}.'})],
            })
            # newest first, the order Livingdocs stores them in
            for hour in range(23, 23 - n_posts, -1)
        ]
        return document(posts, custom={'documentClass': 'ticker'})

    def test_only_newest_posts_are_kept(self):
        md = publication_to_markdown(self._ticker(10), max_chars=None, max_ticker_posts=3)

        assert 'Meldung 23.' in md
        assert 'Meldung 21.' in md
        assert 'Meldung 20.' not in md

    def test_non_ticker_posts_are_not_capped(self):
        doc = document([component('paragraph', {'text': f'Absatz {i}.'}) for i in range(50)])
        md = publication_to_markdown(doc, max_chars=None)
        assert 'Absatz 49.' in md

    def test_long_article_capped_on_paragraph_boundary(self):
        doc = document([
            component('paragraph', {'text': f'Absatz {i}. ' + 'Fülltext. ' * 40})
            for i in range(200)
        ])
        md = publication_to_markdown(doc)

        assert len(md) <= livingdocs.MAX_EMBED_CHARS
        assert md.endswith('.')

    def test_max_chars_none_returns_everything(self):
        doc = document([component('paragraph', {'text': 'x' * 20000})])
        assert len(publication_to_markdown(doc, max_chars=None)) > 19000

    def test_short_article_is_untouched(self):
        doc = document([component('paragraph', {'text': 'Kurz.'})])
        assert publication_to_markdown(doc).count('Kurz.') == 1


class TestRealPayloads:
    """Against real articles pulled from the CMS, which exercise component
    combinations no hand-written fixture would think to produce."""

    def test_liveticker_keeps_header_and_newest_posts(self):
        doc = load_fixture('ld_liveticker_event')
        assert is_ticker(doc)

        full = publication_to_markdown(doc, max_chars=None, max_ticker_posts=None)
        embed = publication_to_markdown(doc)

        assert len(full) > len(embed)
        assert len(embed) <= livingdocs.MAX_EMBED_CHARS
        # the header survives truncation, and the newest post is kept
        assert 'GPK-Bericht zur Basler Polizei' in embed
        assert 'Parlament genehmigt Bericht' in embed

    def test_ticker_without_liveticker_posts_is_still_capped(self):
        # documentClass says ticker, but it is built from headerLongform and
        # highlighted-post rather than liveticker-post components
        doc = load_fixture('ld_ticker_event')
        assert is_ticker(doc)
        assert len(publication_to_markdown(doc)) <= livingdocs.MAX_EMBED_CHARS

    @pytest.mark.parametrize('name', ['ld_liveticker_event', 'ld_ticker_event'])
    def test_no_html_survives_rendering(self, name):
        md = publication_to_markdown(load_fixture(name), max_chars=None)

        assert '<p>' not in md and '<div' not in md
        assert '&nbsp;' not in md and '\xa0' not in md

    def test_header_text_from_real_payload(self):
        assert header_text(load_fixture('ld_liveticker_event')) == (
            'Grosser Rat\nGPK-Bericht zur Basler Polizei: Eymann wünscht sich Ruhe fürs Korps'
        )
