"""CSV/Excel exchange without treating column headings as learning material."""
from zipfile import BadZipFile
import pandas as pd
from .database import CATEGORIES
from .analysis import unique_characters

ALIASES = {'character':'character','char':'character','characters':'character',
           '漢字':'character','字':'character','字元':'character',
           'category':'category','分類':'category','類別':'category'}


def parse_upload(file, filename, default_category, has_header=None):
    if default_category not in CATEGORIES:
        raise ValueError('Invalid category')
    try:
        reader = pd.read_excel if filename.lower().endswith('.xlsx') else pd.read_csv
        frame = reader(file, dtype=str, keep_default_na=False, header=None)
    except (ValueError, OSError, BadZipFile, EOFError) as exc:
        raise ValueError('無法讀取 CSV / Excel 字表。') from exc
    if frame.empty:
        return []
    first = [str(value).strip().lstrip('\ufeff') for value in frame.iloc[0]]
    headings = [ALIASES.get(value.lower(), value) for value in first]
    if has_header is False:
        return [(c,default_category) for c in unique_characters(''.join(map(str,frame.to_numpy().ravel())))]
    if 'character' in headings:
        if headings.count('character') != 1 or headings.count('category') > 1:
            raise ValueError('Duplicate columns')
        char_column = headings.index('character')
        cat_column = headings.index('category') if 'category' in headings else None
        result = []
        for row in frame.iloc[1:].itertuples(index=False,name=None):
            category = str(row[cat_column]).strip() if cat_column is not None else default_category
            if category not in CATEGORIES:
                raise ValueError('Category must be Mastered, Learning or New.')
            result.extend((c,category) for c in unique_characters(str(row[char_column])))
        return result
    if 'category' in headings:
        raise ValueError('Category column requires a character column')
    values = frame.iloc[1:] if has_header is True else frame
    return [(c,default_category) for c in unique_characters(''.join(map(str,values.to_numpy().ravel())))]
