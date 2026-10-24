"""Exercise real Streamlit widgets, persistence and no-key manual mode."""
from streamlit.testing.v1 import AppTest
from chinese_reader.database import Database


def start(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_PATH', str(tmp_path / 'ui.db'))
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    app = AppTest.from_file(str(__import__('pathlib').Path('app.py').resolve()), default_timeout=20).run()
    assert not app.exception
    return app


def button(app, label):
    return next(b for b in app.button if b.label == label)


def test_manual_save_library_edit_and_backup(tmp_path, monkeypatch):
    app = start(tmp_path, monkeypatch)
    button(app, '載入原創示例故事').click().run()
    assert app.text_area[0].value
    assert not app.exception
    button(app, '儲存至書庫').click().run()
    assert app.success
    app.sidebar.radio[0].set_value('閱讀書庫').run()
    assert not app.exception
    assert app.subheader[0].value == '小鳥的雨天朋友'
    button(app, '載入編輯器').click().run()
    app.sidebar.radio[0].set_value('創作故事').run()
    assert not app.exception
    app.text_input[0].set_value('修改後的故事').run()
    next(c for c in app.checkbox if c.label == '更新目前已載入的故事').check().run()
    button(app, '儲存至書庫').click().run()
    assert not app.exception
    db = Database(tmp_path / 'ui.db')
    assert len(db.stories()) == 1
    assert db.stories()[0]['title'] == '修改後的故事'
    app.sidebar.radio[0].set_value('備份與說明').run()
    assert not app.exception


def test_character_management_and_missing_key(tmp_path, monkeypatch):
    app = start(tmp_path, monkeypatch)
    app.sidebar.radio[0].set_value('漢字管理').run()
    app.text_area[0].set_value('鳥雨鳥')
    button(app, '儲存漢字').click().run()
    assert not app.exception
    assert len(Database(tmp_path / 'ui.db').characters()) == 2
    app.sidebar.radio[0].set_value('創作故事').run()
    next(r for r in app.radio if r.label == '故事來源').set_value('AI 模式（需自備 OpenAI API）').run()
    assert button(app, '產生 / 重新產生 / 按要求修改').disabled
    assert not app.exception


def test_pinyin_correction_and_pdf_workflow(tmp_path, monkeypatch):
    app = start(tmp_path, monkeypatch)
    app.text_input[0].set_value('多音字練習')
    app.text_area[0].set_value('小鳥長大了，牠喜歡音樂。').run()
    assert not app.exception
    next(r for r in app.radio if r.label == '閱讀模式').set_value('點按才顯示拼音').run()
    assert not app.exception
    position = next(s for s in app.selectbox if s.label.startswith('選擇要修正的字'))
    position.set_value(2).run()
    field = next(t for t in app.text_input if t.label.startswith('這個字的拼音'))
    field.set_value('zhǎng')
    button(app,'只修正這個位置').click().run()
    db=Database(tmp_path/'ui.db')
    assert db.position_corrections('小鳥長大了，牠喜歡音樂。') == {2:'zhǎng'}
    next(t for t in app.text_input if t.label.startswith('可重用的完整詞語')).set_value('音樂')
    next(t for t in app.text_input if t.label.startswith('詞語拼音')).set_value('yīn yuè')
    button(app,'儲存詞語讀音供以後重用').click().run()
    assert db.pinyin_corrections()['音樂'] == 'yīn yuè'
    button(app,'準備三種 PDF').click().run()
    assert not app.exception
    signature, exports=app.session_state['_pdf_export']
    assert len(exports) == 3
    assert all(data.startswith(b'%PDF') for data in exports.values())


def test_ai_pinyin_review_acceptance_workflow(tmp_path, monkeypatch):
    from chinese_reader import reading_ui
    from chinese_reader.pinyin_review import resolved_readings
    calls=[]
    def fake_review(settings,text):
        calls.append(text)
        return {'readings':[
            dict(index=0,char='長',pinyin='cháng',uncertain=False,reason='兩種讀法需核對',rewrite='小鳥慢慢成長。'),
            dict(index=1,char='大',pinyin='dà',uncertain=False,reason='',rewrite='')],
            'model':settings.model,'input_tokens':10,'output_tokens':20,'cost':None}
    monkeypatch.setattr(reading_ui,'request_review',fake_review)
    app=start(tmp_path,monkeypatch)
    monkeypatch.setenv('OPENAI_API_KEY','dummy-test-key')
    app.text_input[0].set_value('測試')
    app.text_area[0].set_value('長大。').run()
    button(app,'用 AI 核對拼音（需 API 費用）').click().run()
    assert not app.exception
    assert calls==['長大。']
    assert button(app,'採用 AI 讀音：cháng')
    button(app,'採用 AI 讀音：cháng').click().run()
    assert not app.exception
    db=Database(tmp_path/'ui.db')
    assert db.position_corrections('長大。') == {0:'cháng'}
    assert resolved_readings(db,'長大。','gpt-4.1-mini')[1] == []
    button(app,'準備三種 PDF').click().run()
    assert not app.exception
    assert len(calls)==1  # Reading and PDF reruns reuse the stored independent review.


def test_reopening_ai_story_preserves_source_and_whitespace(tmp_path,monkeypatch):
    db=Database(tmp_path/'ui.db')
    text='\n小鳥長大了。\n'
    db.save_story('AI 原稿',text,['鳥'],'原創動物故事','AI')
    app=start(tmp_path,monkeypatch)
    app.sidebar.radio[0].set_value('閱讀書庫').run()
    button(app,'載入編輯器').click().run()
    app.sidebar.radio[0].set_value('創作故事').run()
    assert app.text_area[0].value==text
    next(c for c in app.checkbox if c.label=='更新目前已載入的故事').check().run()
    button(app,'儲存至書庫').click().run()
    assert not app.exception
    assert db.stories()[0]['source']=='AI'
    assert db.stories()[0]['body']==text
