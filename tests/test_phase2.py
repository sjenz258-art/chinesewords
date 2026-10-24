from io import BytesIO
from pathlib import Path
import pytest
from pypdf import PdfReader
from chinese_reader.database import Database
from chinese_reader.pinyin_engine import annotate, validate_correction
from chinese_reader.pdf_export import create_pdf, load_fonts
from chinese_reader.reading import story_html


def syllables(text, **kwargs):
    return [t.pinyin for t in annotate(text, **kwargs)]


def test_polyphonic_context():
    assert syllables('長大長短音樂快樂') == ['zhǎng','dà','cháng','duǎn','yīn','yuè','kuài','lè']
    assert syllables('銀行行走重新重要睡覺覺得') == ['yín','háng','xíng','zǒu','chóng','xīn','zhòng','yào','shuì','jiào','jué','de']


def test_tone_sandhi_and_boundaries():
    assert syllables('一個') == ['yí','gè']
    assert syllables('一天') == ['yì','tiān']
    assert syllables('不是') == ['bú','shì']
    assert syllables('不好') == ['bù','hǎo']
    assert syllables('第一')[1] == 'yī'
    assert syllables('一二三')[0] == 'yī'
    assert syllables('一，不。') == ['yī','','bù','']
    assert syllables('一個', sandhi=False)[0] == 'yī'
    assert syllables('你好') == ['nǐ','hǎo']  # lexical third tones are retained


def test_punctuation_newlines_and_alignment():
    text='長大，\n\n音樂！abc 123\r\n<你好>\U000323af'
    tokens=annotate(text)
    assert len(tokens) == len(text)
    assert ''.join(t.char for t in tokens) == text
    assert tokens[2].pinyin == ''
    assert tokens[-1].uncertain  # unknown extension character is transparent
    assert all(not any(c.isdigit() for c in t.pinyin) for t in tokens)


def test_review_warnings_and_parent_priority(tmp_path):
    assert annotate('行')[0].uncertain
    assert not any(t.uncertain for t in annotate('銀行'))
    db=Database(tmp_path/'db.sqlite')
    db.save_pinyin_correction('長大','zhǎng dà')
    db.save_position_correction('長大長大',2,'cháng')
    db=Database(tmp_path/'db.sqlite')
    result=annotate('長大長大',db.pinyin_corrections(),overrides=db.position_corrections('長大長大'))
    assert result[0].pinyin == 'zhǎng'
    assert result[2].pinyin == 'cháng'
    assert result[2].source == 'parent'
    assert not db.position_corrections('長大長大。')
    assert not db.pinyin_corrections(child_id=2)
    assert db.backup().startswith(b'SQLite format 3')
    db.delete_pinyin_correction('長大')
    db.delete_position_corrections('長大長大')
    assert not db.pinyin_corrections()
    assert not db.position_corrections('長大長大')


@pytest.mark.parametrize('phrase,reading',[('長大','zhang3 da4'),('長大','zhǎng'),('長，大','zhǎng dà'),('長','<script>')])
def test_correction_validation(phrase,reading):
    with pytest.raises(ValueError):
        validate_correction(phrase,reading)


def test_three_html_modes_and_escape():
    for mode in ('chinese','pinyin','tap'):
        html=story_html('長大\n<script>',[],['長'],mode=mode)
        assert f'mode-{mode}' in html
        assert '<ruby' in html and '<rt>zhǎng</rt>' in html
        assert '<details' in html and '<br>' in html
        assert '<script>' not in html
    with pytest.raises(ValueError):
        story_html('長',[],[],readings=annotate('大'))


@pytest.mark.parametrize('version,pages',[('pinyin',1),('chinese',1),('practice',2)])
def test_a4_pdf_fonts_and_content(version,pages):
    body=Path('samples/story.txt').read_text()
    data=create_pdf('小鳥的雨天朋友',body,version,targets=list('鳥雨朋友'))
    doc=PdfReader(BytesIO(data))
    assert len(doc.pages) == pages
    for page in doc.pages:
        assert float(page.mediabox.width) == pytest.approx(595.276,abs=.01)
        assert float(page.mediabox.height) == pytest.approx(841.89,abs=.01)
        fonts=page['/Resources']['/Font'].get_object()
        embedded=[font.get_object() for font in fonts.values() if '/FontDescriptor' in font.get_object()]
        assert embedded
        assert all('/FontFile2' in font['/FontDescriptor'].get_object() for font in embedded)
    text=doc.pages[0].extract_text()
    assert '小鳥的雨天朋友' in text.replace('\n','')
    assert '小' in text and '鳥' in text
    assert ('xiǎo' in text) == (version == 'pinyin')


def test_pdf_pinyin_coordinates_and_page_bounds():
    from reportlab.pdfbase import pdfmetrics
    data=create_pdf('對齊測試','長大，音樂。')
    page=PdfReader(BytesIO(data)).pages[0]
    items=[]
    def visitor(text,cm,tm,font,size):
        text=text.strip()
        if text:
            items.append((text,float(tm[4]),float(tm[5]),size))
    page.extract_text(visitor_text=visitor)
    chinese=next(item for item in items if item[0] == '長')
    py=next(item for item in items if item[0] == 'zhǎng')
    cx=chinese[1]+pdfmetrics.stringWidth('長','Chinese',18)/2
    px=py[1]+pdfmetrics.stringWidth('zhǎng','Pinyin',8.5)/2
    assert cx == pytest.approx(px,abs=.001)
    assert py[2]-chinese[2] == pytest.approx(23)
    assert all(x >= 40 and y >= 24 and y < 820 for _,x,y,_ in items)


def test_long_pdf_pagination_and_unsupported_glyph():
    data=create_pdf('長故事','小鳥快樂地唱歌。\n'*100)
    assert len(PdfReader(BytesIO(data)).pages) > 1
    with pytest.raises(ValueError,match='不支援'):
        create_pdf('故事','小鳥\U0010ffff')
