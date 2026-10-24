import io
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace as NS
import pytest
from chinese_reader.analysis import analyse, characters, unique_characters
from chinese_reader.database import Database
from chinese_reader.generator import Settings, GenerationError, generate, STORY_TYPES
from chinese_reader.imports import parse_upload
from chinese_reader.reading import story_html


def test_han_count_punctuation_and_newlines():
    assert characters('小鳥，\n你好！abc123\U00020000') == list('小鳥你好\U00020000')
    assert analyse('小鳥，\n小鳥！', targets=['小', '雨'])['total'] == 4


def test_duplicate_removal():
    assert unique_characters('小 小，鳥小鳥') == ['小', '鳥']


def test_coverage_frequency_and_familiarity():
    result = analyse('小鳥小鳥雨', mastered=['小'], learning=['鳥'], targets=['鳥', '花'])
    assert result['target_coverage_pct'] == 50
    assert result['target_frequency'] == {'花': 0, '鳥': 2}
    assert result['mastered_unique_pct'] == pytest.approx(100 / 3)
    assert result['mastered_occurrence_pct'] == 40
    assert result['unfamiliar'] == ['雨']
    assert result['missing_targets'] == ['花']
    assert result['target_count'] == 1
    assert analyse('')['target_coverage_pct'] is None
    assert analyse('')['mastered_occurrence_pct'] == 0


@pytest.mark.parametrize('length,valid', [(179, False), (180, True), (200, True), (220, True), (221, False)])
def test_story_length(length, valid):
    assert analyse('鳥' * length)['within_length'] is valid


def test_persistence_and_manual_without_key(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    db = Database(tmp_path / 'test.db')
    db.put_characters('小小，鳥', 'Learning')
    db.put_characters('小', 'Mastered')
    sid = db.save_story('測試', '小鳥\n看雨。', ['鳥', '鳥'], STORY_TYPES[0], 'Manual')
    again = Database(tmp_path / 'test.db')
    assert len(again.characters()) == 2
    assert again.stories()[0]['targets'] == ['鳥']
    again.favourite(sid, True)
    again.save_story('新標題', '小鳥回家。', ['鳥'], STORY_TYPES[0], 'Manual', story_id=sid)
    assert len(again.stories()) == 1
    assert again.stories()[0]['favourite'] == 1
    assert {r['char']: r['category'] for r in again.characters()}['鳥'] == 'Learning'
    assert analyse(again.stories()[0]['body'], targets=['鳥'])['target_count'] == 1
    backup = tmp_path / 'copy.sqlite'
    backup.write_bytes(again.backup())
    assert Database(backup).stories()[0]['title'] == '新標題'
    export = again.export_characters()
    again.remove_characters(['小', '鳥'])
    again.restore_characters(export)
    assert len(again.characters()) == 2
    with pytest.raises(ValueError):
        again.restore_characters(json.dumps({'version': 1, 'characters': [{'char': '雨', 'category': 'invalid'}]}))
    assert len(again.characters()) == 2


def test_profile_isolation_and_invalid_inputs(tmp_path):
    db = Database(tmp_path / 'test.db')
    with db.connect() as conn:
        conn.execute("INSERT INTO children VALUES(2, '測試')")
    db.put_characters('鳥', 'Learning', child_id=2)
    assert not db.characters()
    with pytest.raises(ValueError):
        db.put_characters('鳥', 'invalid')
    with pytest.raises(ValueError):
        db.save_story('', '鳥', [], '', 'Manual')


def test_import_csv_and_excel():
    import pandas as pd
    csv = io.StringIO('character,category\n小小,Mastered\n鳥,Learning\n')
    assert parse_upload(csv, 'list.csv', 'New') == [('小', 'Mastered'), ('鳥', 'Learning')]
    output = io.BytesIO()
    pd.DataFrame({'character': ['雨'], 'category': ['Learning']}).to_excel(output, index=False)
    output.seek(0)
    assert parse_upload(output, 'list.xlsx', 'New') == [('雨', 'Learning')]
    assert parse_upload(io.StringIO('小鳥\n雨'), 'plain.csv', 'New') == [('小', 'New'), ('鳥', 'New'), ('雨', 'New')]


class FakeClient:
    def __init__(self, content=None, error=None):
        self.content, self.error = content, error
        self.chat = NS(completions=NS(create=self.create))

    def create(self, **kwargs):
        self.request = kwargs
        if self.error:
            raise self.error
        return NS(choices=[NS(message=NS(content=self.content))], usage=NS(prompt_tokens=100, completion_tokens=200))


def test_optional_key_and_no_credential_leak():
    with pytest.raises(GenerationError):
        generate(Settings(), [], [], STORY_TYPES[0])
    client = FakeClient(error=RuntimeError('secret-test-key'))
    with pytest.raises(GenerationError) as caught:
        generate(Settings(api_key='secret-test-key'), [], [], STORY_TYPES[0], client=client)
    assert 'secret-test-key' not in str(caught.value)
    assert caught.value.__suppress_context__


def test_generation_model_usage_and_revision():
    client = FakeClient(json.dumps({'title': '故事', 'body': '小鳥回家。'}))
    result = generate(Settings(model='configured-model', input_rate=1, output_rate=2),
                      ['小'], ['鳥'], STORY_TYPES[0], draft='小鳥', revision='加上下雨', client=client)
    assert result['cost'] == pytest.approx(.0005)
    assert client.request['model'] == 'configured-model'
    payload = json.loads(client.request['messages'][1]['content'])
    assert payload['revision'] == '加上下雨'
    assert payload['targets'] == ['鳥']
    with pytest.raises(GenerationError):
        generate(Settings(), [], [], STORY_TYPES[0], client=FakeClient('{}'))


def test_safe_html_and_newlines():
    html = story_html('<script>小\n鳥</script>', ['小'], ['鳥'])
    assert '<script>' not in html
    assert '<br>' in html
    assert 'class="learning"' in html


def test_synthetic_sample_length():
    story = Path('samples/story.txt').read_text()
    assert analyse(story)['within_length']


def test_no_tracked_secrets():
    assert '.env' in Path('.gitignore').read_text()
    assert '.streamlit/secrets.toml' in Path('.gitignore').read_text()
    assert 'OPENAI_API_KEY=\n' in Path('.env.example').read_text()
