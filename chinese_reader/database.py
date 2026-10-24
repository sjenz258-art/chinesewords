"""Local SQLite storage, scoped by child; no credentials are stored here."""
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .analysis import unique_characters

CATEGORIES = ('Mastered', 'Learning', 'New')


class Database:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS pinyin_reviews(
                    child_id INTEGER NOT NULL REFERENCES children(id), signature TEXT NOT NULL,
                    payload TEXT NOT NULL, created_at TEXT NOT NULL,
                    PRIMARY KEY(child_id,signature));
                CREATE TABLE IF NOT EXISTS pinyin_corrections(
                    child_id INTEGER NOT NULL REFERENCES children(id), phrase TEXT NOT NULL,
                    readings TEXT NOT NULL, PRIMARY KEY(child_id,phrase));
                CREATE TABLE IF NOT EXISTS pinyin_positions(
                    child_id INTEGER NOT NULL REFERENCES children(id), digest TEXT NOT NULL,
                    position INTEGER NOT NULL, reading TEXT NOT NULL,
                    PRIMARY KEY(child_id,digest,position));
                CREATE TABLE IF NOT EXISTS children(id INTEGER PRIMARY KEY, name TEXT NOT NULL);
                INSERT OR IGNORE INTO children VALUES(1, '小讀者');
                CREATE TABLE IF NOT EXISTS characters(
                    child_id INTEGER NOT NULL REFERENCES children(id), char TEXT NOT NULL,
                    category TEXT NOT NULL CHECK(category IN ('Mastered','Learning','New')),
                    PRIMARY KEY(child_id,char));
                CREATE TABLE IF NOT EXISTS stories(
                    id INTEGER PRIMARY KEY, child_id INTEGER NOT NULL REFERENCES children(id),
                    title TEXT NOT NULL, body TEXT NOT NULL, targets TEXT NOT NULL,
                    story_type TEXT NOT NULL, source TEXT NOT NULL, desired INTEGER NOT NULL,
                    favourite INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL);
            ''')

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def characters(self, child_id=1):
        with self.connect() as conn:
            return [dict(r) for r in conn.execute(
                'SELECT char,category FROM characters WHERE child_id=? ORDER BY char', (child_id,))]

    def put_characters(self, text, category, child_id=1):
        if category not in CATEGORIES:
            raise ValueError('Invalid category')
        chars = unique_characters(text)
        with self.connect() as conn:
            conn.executemany('INSERT INTO characters VALUES(?,?,?) ON CONFLICT(child_id,char) DO UPDATE SET category=excluded.category',
                             [(child_id, c, category) for c in chars])
        return len(chars)

    def import_characters(self, entries, child_id=1):
        entries = list(entries)
        if any(not isinstance(c,str) or len(c) != 1 or not unique_characters(c) or cat not in CATEGORIES
               for c,cat in entries):
            raise ValueError('Invalid character import')
        with self.connect() as conn:
            conn.executemany('INSERT INTO characters VALUES(?,?,?) ON CONFLICT(child_id,char) DO UPDATE SET category=excluded.category',
                             [(child_id,c,cat) for c,cat in entries])
        return len({c for c,_ in entries})

    def remove_characters(self, chars, child_id=1):
        with self.connect() as conn:
            conn.executemany('DELETE FROM characters WHERE child_id=? AND char=?', [(child_id, c) for c in chars])

    def save_story(self, title, body, targets, story_type, source, desired=200, story_id=None, child_id=1):
        if not title.strip() or not unique_characters(body):
            raise ValueError('Please supply a title and Chinese story text.')
        values = (title.strip(), body, json.dumps(unique_characters(''.join(targets)), ensure_ascii=False),
                  story_type, source, int(desired))
        with self.connect() as conn:
            if story_id:
                cursor = conn.execute('UPDATE stories SET title=?,body=?,targets=?,story_type=?,source=?,desired=? WHERE id=? AND child_id=?',
                             (*values, story_id, child_id))
                if cursor.rowcount != 1:
                    raise ValueError('Story no longer exists for this child. Save as a new story.')
                return story_id
            cursor = conn.execute('INSERT INTO stories(title,body,targets,story_type,source,desired,child_id,created_at) VALUES(?,?,?,?,?,?,?,?)',
                                  (*values, child_id, datetime.now(timezone.utc).isoformat()))
            return cursor.lastrowid

    def stories(self, child_id=1):
        with self.connect() as conn:
            rows = [dict(r) for r in conn.execute('SELECT * FROM stories WHERE child_id=? ORDER BY id DESC', (child_id,))]
        for row in rows:
            row['targets'] = json.loads(row['targets'])
        return rows

    def favourite(self, story_id, value, child_id=1):
        with self.connect() as conn:
            conn.execute('UPDATE stories SET favourite=? WHERE id=? AND child_id=?', (int(value), story_id, child_id))

    def backup(self):
        # SQLite backup API includes committed WAL data in a standalone database.
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'backup.sqlite'
            with self.connect() as source, sqlite3.connect(path) as destination:
                source.backup(destination)
            return path.read_bytes()

    def export_characters(self):
        return json.dumps({'version': 1, 'characters': self.characters()}, ensure_ascii=False, indent=2)

    def restore_characters(self, payload):
        data = json.loads(payload)
        if not isinstance(data,dict) or data.get('version') != 1 or not isinstance(data.get('characters'), list):
            raise ValueError('Unsupported backup format')
        rows = data['characters']
        if any(not isinstance(row,dict) or set(row) != {'char', 'category'} or row['category'] not in CATEGORIES
               or not isinstance(row['char'],str) or len(row['char']) != 1 or not unique_characters(row['char']) for row in rows):
            raise ValueError('Invalid character backup')
        # Validate everything before replacing the current character list.
        with self.connect() as conn:
            conn.execute('DELETE FROM characters WHERE child_id=1')
            conn.executemany('INSERT OR REPLACE INTO characters VALUES(1,?,?)', [(r['char'], r['category']) for r in rows])

    def pinyin_corrections(self, child_id=1):
        with self.connect() as conn:
            return {r['phrase']: r['readings'] for r in conn.execute(
                'SELECT phrase,readings FROM pinyin_corrections WHERE child_id=?', (child_id,))}

    def save_pinyin_correction(self, phrase, readings, child_id=1):
        from .pinyin_engine import validate_correction
        phrase, readings = validate_correction(phrase, readings)
        with self.connect() as conn:
            conn.execute('INSERT INTO pinyin_corrections VALUES(?,?,?) ON CONFLICT(child_id,phrase) DO UPDATE SET readings=excluded.readings',
                         (child_id, phrase, readings))

    def delete_pinyin_correction(self, phrase, child_id=1):
        with self.connect() as conn:
            conn.execute('DELETE FROM pinyin_corrections WHERE child_id=? AND phrase=?', (child_id, phrase))

    def position_corrections(self, text, child_id=1):
        from hashlib import sha256
        digest = sha256(text.encode()).hexdigest()
        with self.connect() as conn:
            return {r['position']: r['reading'] for r in conn.execute(
                'SELECT position,reading FROM pinyin_positions WHERE child_id=? AND digest=?', (child_id, digest))}

    def save_position_correction(self, text, position, reading, child_id=1):
        from hashlib import sha256
        from .pinyin_engine import validate_correction
        if position < 0 or position >= len(text):
            raise ValueError('Invalid position')
        _, reading = validate_correction(text[position], reading)
        with self.connect() as conn:
            conn.execute('INSERT INTO pinyin_positions VALUES(?,?,?,?) ON CONFLICT(child_id,digest,position) DO UPDATE SET reading=excluded.reading',
                         (child_id, sha256(text.encode()).hexdigest(), position, reading))

    def delete_position_corrections(self, text, child_id=1):
        from hashlib import sha256
        with self.connect() as conn:
            conn.execute('DELETE FROM pinyin_positions WHERE child_id=? AND digest=?',
                         (child_id, sha256(text.encode()).hexdigest()))


    def pinyin_review(self, signature, child_id=1):
        with self.connect() as conn:
            row = conn.execute('SELECT payload FROM pinyin_reviews WHERE child_id=? AND signature=?',
                               (child_id,signature)).fetchone()
        if not row:
            return None
        try:
            return json.loads(row['payload'])
        except ValueError:
            return None

    def save_pinyin_review(self, signature, payload, child_id=1):
        with self.connect() as conn:
            conn.execute('INSERT INTO pinyin_reviews VALUES(?,?,?,?) ON CONFLICT(child_id,signature) DO UPDATE SET payload=excluded.payload,created_at=excluded.created_at',
                         (child_id,signature,json.dumps(payload,ensure_ascii=False),datetime.now(timezone.utc).isoformat()))

    def delete_pinyin_review(self, signature, child_id=1):
        with self.connect() as conn:
            conn.execute('DELETE FROM pinyin_reviews WHERE child_id=? AND signature=?',(child_id,signature))
