"""Optional: python -m samples.load_samples (idempotent for characters and sample story)."""
import os
from pathlib import Path
from chinese_reader.database import Database
from chinese_reader.generator import STORY_TYPES
from chinese_reader.imports import parse_upload


def main():
    db = Database(os.getenv('DATABASE_PATH', 'data/reading.db'))
    with Path('samples/characters.csv').open(encoding='utf-8') as file:
        for char, category in parse_upload(file, 'characters.csv', 'Learning'):
            db.put_characters(char, category)
    title = '小鳥的雨天朋友'
    if not any(s['title'] == title for s in db.stories()):
        db.save_story(title, Path('samples/story.txt').read_text(encoding='utf-8'),
                      list('鳥雨朋友'), STORY_TYPES[0], 'Manual')
    print('Synthetic sample characters and story loaded.')


if __name__ == '__main__':
    main()
