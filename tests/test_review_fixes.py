from copy import deepcopy
from io import StringIO,BytesIO
import json
from pathlib import Path
import pytest
from pypdf import PdfReader
from chinese_reader.database import Database
from chinese_reader.imports import parse_upload
from chinese_reader.pinyin_engine import annotate,validate_correction
from chinese_reader.pinyin_review import resolved_readings,review_key
from chinese_reader.pdf_export import create_pdf
from chinese_reader.backup import export_backup,restore_backup


def test_save_preserves_exact_text_and_correction_identity(tmp_path):
    db=Database(tmp_path/'db')
    text=' \n長大。\n '
    db.save_position_correction(text,2,'zhǎng')
    db.save_story('標題',text,['長'],'原創','Manual')
    body=db.stories()[0]['body']
    assert body == text
    assert db.position_corrections(body) == {2:'zhǎng'}
    with pytest.raises(ValueError):
        db.save_story('標題',text,[],'','Manual',story_id=999)


def test_parent_correction_informs_previous_tone_sandhi():
    assert annotate('不行',overrides={1:'xìng'})[0].pinyin == 'bú'
    assert annotate('一行',overrides={1:'xìng'})[0].pinyin == 'yí'
    assert annotate('一行',overrides={0:'yī',1:'xìng'})[0].pinyin == 'yī'


@pytest.mark.parametrize('text,reading',[
    ('一百','yì'),('一千','yì'),('一萬','yí'),('一二三','yī'),('第一百','yī'),
    ('統一安排','yī'),('唯一朋友','yī'),('萬一跌倒','yī')])
def test_numbers_and_fixed_words(text,reading):
    assert next(t for t in annotate(text) if t.char=='一').pinyin==reading


@pytest.mark.parametrize('data,expected',[
    ('漢字,分類\n鳥,Learning\n雨,Mastered',[('鳥','Learning'),('雨','Mastered')]),
    ('character\n鳥\n雨',[('鳥','New'),('雨','New')]),
    ('字\n鳥\n雨',[('鳥','New'),('雨','New')]),
    ('鳥,雨\n天,水',[('鳥','New'),('雨','New'),('天','New'),('水','New')])])
def test_import_headers_not_learned(data,expected):
    assert parse_upload(StringIO(data),'chars.csv','New') == expected


def test_invalid_import_is_atomic(tmp_path):
    db=Database(tmp_path/'db')
    db.put_characters('鳥','Learning')
    with pytest.raises(ValueError): db.import_characters([('雨','Mastered'),('天','typo')])
    assert db.characters() == [{'char':'鳥','category':'Learning'}]
    with pytest.raises(ValueError): parse_upload(BytesIO(b'not excel'),'bad.xlsx','Learning')


@pytest.mark.parametrize('payload',['null','[]','42','{"version":1,"characters":[null]}'])
def test_malformed_character_backup_never_changes_data(tmp_path,payload):
    db=Database(tmp_path/'db')
    db.put_characters('鳥','Learning')
    with pytest.raises(ValueError): db.restore_characters(payload)
    assert len(db.characters())==1


def test_portable_complete_backup_roundtrip_and_rollback(tmp_path):
    db=Database(tmp_path/'db')
    db.put_characters('鳥','Learning')
    db.save_story('故事','小鳥。',['鳥'],'動物','Manual')
    db.save_pinyin_correction('小鳥','xiǎo niǎo')
    db.save_position_correction('小鳥。',1,'niǎo')
    rows=[dict(index=i,char=c,pinyin=p,uncertain=False,reason='',rewrite='') for i,c,p in [(0,'小','xiǎo'),(1,'鳥','niǎo')]]
    db.save_pinyin_review(review_key('小鳥。','test'),dict(readings=rows,model='test',cost=None))
    snapshot=export_backup(db)
    restored=Database(tmp_path/'restored')
    restore_backup(restored,snapshot)
    assert json.loads(export_backup(restored)) == json.loads(snapshot)
    assert resolved_readings(restored,'小鳥。','test')[1]==[]
    malformed=json.loads(snapshot)
    malformed['tables']['stories'][0]['body']=''
    with pytest.raises(ValueError): restore_backup(db,json.dumps(malformed))
    assert json.loads(export_backup(db))==json.loads(snapshot)
    duplicate=json.loads(snapshot)
    duplicate['tables']['stories']*=2
    with pytest.raises(ValueError): restore_backup(db,json.dumps(duplicate))
    assert json.loads(export_backup(db))==json.loads(snapshot)  # SQL failure rolls back deletes


@pytest.mark.parametrize('value',['null','[]','{}','{"app":"little-story-garden","version":1,"tables":{}}'])
def test_portable_backup_invalid_roots(tmp_path,value):
    db=Database(tmp_path/'db')
    with pytest.raises(ValueError): restore_backup(db,value)


def test_cached_review_normalisation(tmp_path):
    db=Database(tmp_path/'db')
    db.save_pinyin_review(review_key('長','test'),dict(model='test',readings=[dict(index=0,char='長',pinyin=' ZHǍNG ',uncertain=False)]))
    assert resolved_readings(db,'長','test')[1]==[]


@pytest.mark.parametrize('reading',['lǐu','nv','xǐǎo'])
def test_invalid_pinyin_spelling(reading):
    with pytest.raises(ValueError): validate_correction('鳥',reading)


def test_pdf_punctuation_runs_and_whitespace():
    body='鳥'*20+'好！」\r\n鳥\t好。'
    pdf=create_pdf('測試',body,version='chinese')
    entries=[]
    def visit(text,cm,tm,font,size):
        text=text.strip()
        if text: entries.append((text,tm[4],tm[5]))
    page=PdfReader(BytesIO(pdf)).pages[0]
    page.extract_text(visitor_text=visit)
    end=next(i for i,e in enumerate(entries) if e[0]=='！')
    assert entries[end-1][2]==entries[end][2]==entries[end+1][2]
    assert all(40<=x<=550 and y>=24 for _,x,y in entries)


def test_reading_exports_ignore_unprinted_exercise_glyphs():
    for version in ('pinyin','chinese'):
        assert create_pdf('故事','小鳥。',version=version,questions=['\U0010ffff']).startswith(b'%PDF')
    with pytest.raises(ValueError):
        create_pdf('故事','小鳥。',version='practice',questions=['\U0010ffff'])


@pytest.mark.parametrize('text,expected',[
    ('長大衣','cháng dà yī'),('猴子彈琴','hóu zi tán qín'),
    ('看著作','kàn zhù zuò'),('背書包','bēi shū bāo'),
    ('星期一去','xīng qī yī qù'),('二十一隻','èr shí yī zhī'),
    ('一月一日','yī yuè yī rì'),('畫一畫','huà yi huà'),('玩一玩','wán yi wán'),
    ('去不去','qù bu qù'),('吃不吃','chī bu chī')])
def test_segmentation_and_additional_sandhi(text,expected):
    assert ' '.join(t.pinyin for t in annotate(text))==expected


def test_explicit_headerless_import_keeps_zi():
    assert parse_upload(StringIO('字\n人\n山'),'plain.csv','Learning',has_header=False)==[
        ('字','Learning'),('人','Learning'),('山','Learning')]
    assert parse_upload(StringIO('我的字表\n鳥\n雨'),'plain.csv','Learning',has_header=True)==[
        ('鳥','Learning'),('雨','Learning')]


def test_oversized_integer_backup_is_rejected_safely(tmp_path):
    db=Database(tmp_path/'db')
    db.save_story('故事','小鳥。',[],'原創','Manual')
    snapshot=export_backup(db)
    data=json.loads(snapshot)
    data['tables']['stories'][0]['id']=2**100
    with pytest.raises(ValueError): restore_backup(db,json.dumps(data))
    assert json.loads(export_backup(db))==json.loads(snapshot)


def test_pdf_and_html_control_whitespace():
    from chinese_reader.reading import story_html
    assert story_html('A\r\nB\rC\nD',[],[]).count('<br>')==3
    html=story_html('小鳥',[],[])
    assert html.count('name="story-pronunciation"')==2
    data=create_pdf('題\v目','小鳥。',version='practice',questions=['問題\f後半'])
    doc=PdfReader(BytesIO(data))
    assert '\x00' not in ''.join(page.extract_text() for page in doc.pages)


def test_syllabic_nasal_is_not_unknown():
    assert annotate('嗯')[0].pinyin == 'ń'
