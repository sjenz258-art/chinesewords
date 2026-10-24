"""Portable single-profile JSON backup/restore for parents using only a phone.

Only explicit application columns are copied. Restore uses one transaction and
never opens uploaded SQLite files or executes SQL supplied by a backup.
"""
import json
import math
import re
import sqlite3
from .analysis import unique_characters
from .database import CATEGORIES
from .pinyin_engine import validate_correction

TABLES = {
    'characters': ('char','category'),
    'stories': ('id','title','body','targets','story_type','source','desired','favourite','created_at'),
    'pinyin_corrections': ('phrase','readings'),
    'pinyin_positions': ('digest','position','reading'),
    'pinyin_reviews': ('signature','payload','created_at'),
}
MAX_BYTES = 10*1024*1024


def export_backup(db):
    with db.connect() as conn:
        conn.execute('BEGIN')
        tables={table:[dict(r) for r in conn.execute(
            f'SELECT {",".join(columns)} FROM {table} WHERE child_id=1')]
                for table,columns in TABLES.items()}
    return json.dumps({'app':'little-story-garden','version':1,'tables':tables},ensure_ascii=False,indent=2)


def _validate(table,row):
    if not isinstance(row,dict) or set(row) != set(TABLES[table]):
        raise ValueError('Invalid backup columns')
    integer_fields={'id','position','desired','favourite'}
    for name,value in row.items():
        if name in integer_fields:
            if type(value) is not int or not -(2**63) <= value < 2**63:
                raise ValueError('Invalid integer')
        elif not isinstance(value,str):
            raise ValueError('Invalid text')
    if table == 'characters':
        if len(row['char']) != 1 or not unique_characters(row['char']) or row['category'] not in CATEGORIES:
            raise ValueError('Invalid character')
    elif table == 'stories':
        if row['id'] < 1 or not row['title'].strip() or not unique_characters(row['body']) or not 80 <= row['desired'] <= 500 or row['favourite'] not in (0,1):
            raise ValueError('Invalid story')
        targets=json.loads(row['targets'])
        if not isinstance(targets,list) or any(not isinstance(c,str) or len(c)!=1 or not unique_characters(c) for c in targets):
            raise ValueError('Invalid targets')
    elif table == 'pinyin_corrections':
        row['phrase'],row['readings'] = validate_correction(row['phrase'],row['readings'])
    elif table == 'pinyin_positions':
        if not re.fullmatch('[0-9a-f]{64}',row['digest']) or row['position'] < 0:
            raise ValueError('Invalid position')
        _,row['reading'] = validate_correction('字',row['reading'])
    elif table == 'pinyin_reviews':
        if not re.fullmatch('[0-9a-f]{64}',row['signature']):
            raise ValueError('Invalid signature')
        payload=json.loads(row['payload'])
        if not isinstance(payload,dict) or not isinstance(payload.get('readings'),list) or not isinstance(payload.get('model'),str):
            raise ValueError('Invalid review')
        for field in ('input_tokens','output_tokens'):
            v=payload.get(field)
            if v is not None and (type(v) is not int or v<0):
                raise ValueError('Invalid usage')
        cost=payload.get('cost')
        if cost is not None and (type(cost) not in (int,float) or not math.isfinite(cost) or cost<0):
            raise ValueError('Invalid cost')
        acknowledgements=payload.get('acknowledged',{})
        if not isinstance(acknowledgements,dict) or any(not str(k).isdigit() or not isinstance(v,str) for k,v in acknowledgements.items()):
            raise ValueError('Invalid choices')
        # Full character alignment is revalidated against text when a review is used.
        for item in payload['readings']:
            if not isinstance(item,dict) or type(item.get('index')) is not int or item['index']<0 or type(item.get('uncertain')) is not bool:
                raise ValueError('Invalid reading')
            validate_correction(item.get('char',''),item.get('pinyin',''))
            if len(item['char'])!=1 or any(not isinstance(item.get(k,''),str) for k in ('reason','rewrite')):
                raise ValueError('Invalid review explanation')


def restore_backup(db,payload):
    if len(payload.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Backup exceeds 10 MB')
    try:
        data=json.loads(payload)
        if not isinstance(data,dict) or data.get('app') != 'little-story-garden' or data.get('version') != 1 or not isinstance(data.get('tables'),dict) or set(data['tables']) != set(TABLES):
            raise ValueError('Unsupported backup')
        for table,rows in data['tables'].items():
            if not isinstance(rows,list):
                raise ValueError('Invalid rows')
            for row in rows:
                _validate(table,row)
        with db.connect() as conn:
            for table in TABLES:
                conn.execute(f'DELETE FROM {table} WHERE child_id=1')
            for table,columns in TABLES.items():
                conn.executemany(f'INSERT INTO {table}(child_id,{",".join(columns)}) VALUES({",".join("?" for _ in range(len(columns)+1))})',
                                 [(1,*(row[c] for c in columns)) for row in data['tables'][table]])
    except (ValueError,TypeError,AttributeError,KeyError,sqlite3.IntegrityError,OverflowError) as exc:
        raise ValueError('備份格式無效或資料互相衝突；現有資料未更改。') from exc
