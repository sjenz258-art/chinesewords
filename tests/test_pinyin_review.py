import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from chinese_reader.generator import Settings
from chinese_reader.database import Database
from chinese_reader.pinyin_engine import annotate, validate_correction
from chinese_reader.pinyin_review import (request_review, validate_review, compare, resolved_readings,
                                         review_key, ReviewError)
from chinese_reader.analysis import is_han


def response_data(text):
    return {'readings':[dict(index=i,char=t.char,pinyin=t.pinyin,uncertain=False,reason='',rewrite='')
                        for i,t in enumerate(annotate(text)) if is_han(t.char)]}


class Client:
    def __init__(self,data,error=None):
        self.data,self.error=data,error
        self.chat=NS(completions=NS(create=self.create))
    def create(self,**kwargs):
        self.request=kwargs
        if self.error:
            raise self.error
        return NS(choices=[NS(message=NS(content=json.dumps(self.data,ensure_ascii=False)))],
                  usage=NS(prompt_tokens=100,completion_tokens=200))


@pytest.mark.parametrize('text,expected',[
    ('頭髮發現種子種花','tóu fa fā xiàn zhǒng zi zhòng huā'),
    ('乾淨能幹教書教室','gān jìng néng gàn jiāo shū jiào shì'),
    ('盛飯盛開朝着朝陽','chéng fàn shèng kāi cháo zhe zhāo yáng'),
    ('睡着笑着答應回答','shuì zháo xiào zhe dā ying huí dá'),
    ('看一看是不是好不好','kàn yi kàn shì bu shì hǎo bu hǎo'),
    ('一起一個一條','yì qǐ yí gè yì tiáo')])
def test_expanded_context_and_reduplication(text,expected):
    assert ' '.join(t.pinyin for t in annotate(text)) == expected


def test_ai_independent_input_and_cost():
    client=Client(response_data('長大，\n快樂。'))
    result=request_review(Settings(model='review-model',input_rate=1,output_rate=2),'長大，\n快樂。',client)
    assert result['cost'] == pytest.approx(.0005)
    assert client.request['model'] == 'review-model'
    payload=json.loads(client.request['messages'][1]['content'])
    assert set(payload) == {'story','characters'}
    assert payload['characters'][2] == {'index':4,'char':'快'}
    assert 'pinyin' not in client.request['messages'][1]['content']


@pytest.mark.parametrize('mutation',['missing','duplicate','wrongchar','wrongindex','badpinyin','notbool','injected','impossible'])
def test_reject_incomplete_or_misaligned_reviews(mutation):
    text='長大，'
    data=response_data(text)
    if mutation=='missing': data['readings'].pop()
    elif mutation=='duplicate': data['readings'][1]=deepcopy(data['readings'][0])
    elif mutation=='wrongchar': data['readings'][0]['char']='短'
    elif mutation=='wrongindex': data['readings'][0]['index']=2
    elif mutation=='badpinyin': data['readings'][0]['pinyin']='zhang3'
    elif mutation=='notbool': data['readings'][0]['uncertain']='false'
    elif mutation=='injected': data['readings'][0]['pinyin']='<script>'
    elif mutation=='impossible': data['readings'][0]['pinyin']='xyz'
    with pytest.raises(ValueError): validate_review(text,data)


def test_compare_only_exceptions_and_manual_acknowledgement():
    text='長大，行。'
    data=response_data(text)
    data['readings'][0]['pinyin']='cháng'
    data['readings'][2]['uncertain']=True
    data['readings'][2]['rewrite']='小鳥向前走。'
    tokens,issues,agreed=compare(annotate(text),data)
    assert [i['index'] for i in issues] == [0,3]
    assert tokens[0].pinyin=='zhǎng'  # No silent AI replacement
    assert tokens[0].uncertain
    assert not tokens[1].uncertain
    data['acknowledged']={'0':'zhǎng'}
    _,issues,_=compare(annotate(text),data)
    assert [i['index'] for i in issues] == [3]
    changed=annotate(text,overrides={0:'cháng'})
    data['readings'][0]['uncertain']=True
    _,issues,_=compare(changed,data)
    assert [i['index'] for i in issues] == [0,3]  # Old confirmation cannot bless a new reading


def test_review_persistence_invalidation_and_backup(tmp_path):
    text='小鳥長大了。'
    db=Database(tmp_path/'db.sqlite')
    result={**response_data(text),'model':'review-model','input_tokens':100,'output_tokens':200,'cost':None}
    db.save_pinyin_review(review_key(text,'review-model'),result)
    db=Database(tmp_path/'db.sqlite')
    tokens,issues,agreed,review=resolved_readings(db,text,'review-model')
    assert issues == [] and review and agreed==5
    assert not resolved_readings(db,text+'\n','review-model')[3]
    assert not resolved_readings(db,text,'different-model')[3]
    assert not db.pinyin_review(review_key(text,'review-model'),child_id=2)
    backup=tmp_path/'backup.sqlite'
    backup.write_bytes(db.backup())
    assert Database(backup).pinyin_review(review_key(text,'review-model'))
    db.delete_pinyin_review(review_key(text,'review-model'))
    assert not resolved_readings(db,text,'review-model')[3]


def test_corrupt_cache_preserves_offline_warnings(tmp_path):
    db=Database(tmp_path/'db.sqlite')
    db.save_pinyin_review(review_key('行','test'),{'readings':[]})
    assert resolved_readings(db,'行','test')[0][0].uncertain
    assert resolved_readings(db,'行','test')[3] is None


def test_no_key_no_network_and_sanitised_error():
    with pytest.raises(ReviewError): request_review(Settings(),'長大')
    with pytest.raises(ReviewError) as caught:
        request_review(Settings(api_key='secret-test'),'長大',Client(None,RuntimeError('secret-test')))
    assert 'secret-test' not in str(caught.value)
    assert caught.value.__suppress_context__
    with pytest.raises(ReviewError): request_review(Settings(),'長'*801,Client(None))
    assert 'secret-test' not in repr(Settings(api_key='secret-test'))


def test_pdf_uses_review_markers_and_original_readings(tmp_path):
    from io import BytesIO
    from pypdf import PdfReader
    from chinese_reader.pdf_export import create_pdf
    text='長大，音樂。'
    data=response_data(text)
    data['readings'][0]['pinyin']='cháng'
    tokens,issues,_=compare(annotate(text),data)
    pdf=create_pdf('拼音核對',text,readings=tokens,review_note='自動核對不等於人工驗證。')
    extracted=PdfReader(BytesIO(pdf)).pages[0].extract_text()
    assert 'zhǎng' in extracted and 'cháng' not in extracted
    assert '自動核對不等於人工驗證。' in extracted.replace('\n','')
    with pytest.raises(ValueError): create_pdf('錯誤','音樂',readings=tokens)
