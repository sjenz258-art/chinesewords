"""Offline phrase-aware Mandarin readings, with conservative ambiguity warnings.

Text is never normalised for display: one Reading per original codepoint.
Traditional-to-simplified conversion is only a pronunciation lookup aid.
"""
from dataclasses import dataclass
from functools import lru_cache
import logging
import json
from pathlib import Path
import re
import unicodedata
import jieba
from opencc import OpenCC
from pypinyin import pinyin, Style
from pypinyin.constants import PINYIN_DICT
from pypinyin.contrib.tone_convert import to_normal
from .analysis import is_han

jieba.setLogLevel(logging.ERROR)
CONVERTER = OpenCC('t2s')
# Longest match wins. Parent phrase overrides take precedence over these rules.
RULES = {
    '長大': 'zhǎng dà', '長短': 'cháng duǎn', '音樂': 'yīn yuè', '快樂': 'kuài lè',
    '長長': 'cháng cháng', '長頸鹿': 'cháng jǐng lù', '校長': 'xiào zhǎng',
    '銀行': 'yín háng', '行走': 'xíng zǒu', '重新': 'chóng xīn', '重要': 'zhòng yào',
    '覺得': 'jué de', '睡覺': 'shuì jiào', '還是': 'hái shì', '還有': 'hái yǒu',
    '還給': 'huán gěi', '看着': 'kàn zhe', '笑着': 'xiào zhe', '帶着': 'dài zhe',
    '走過': 'zǒu guò', '地方': 'dì fang', '朋友': 'péng you', '小鳥': 'xiǎo niǎo',
    '一': 'yī', '不': 'bù',
}
RULES.update(json.loads((Path(__file__).parent / 'resources/pinyin_phrases.json').read_text(encoding='utf-8')))
ENGINE_VERSION = 'phrase-context-v5'
VOWELS = {'a': 'āáǎà', 'e': 'ēéěè', 'i': 'īíǐì', 'o': 'ōóǒò', 'u': 'ūúǔù', 'ü': 'ǖǘǚǜ'}
MARKS = {c: (base, index + 1) for base, tones in VOWELS.items() for index, c in enumerate(tones)}


@dataclass(frozen=True)
class Reading:
    char: str
    pinyin: str = ''
    word: str = ''
    uncertain: bool = False
    source: str = 'dictionary'


def tone_of(syllable):
    return next((MARKS[c][1] for c in syllable if c in MARKS), 5)


def with_tone(syllable, tone):
    plain = ''.join(MARKS.get(c, (c, 0))[0] for c in syllable)
    if tone == 5:
        return plain
    if 'a' in plain:
        pos = plain.index('a')
    elif 'e' in plain:
        pos = plain.index('e')
    elif 'ou' in plain:
        pos = plain.index('o')
    else:
        pos = next((i for i in range(len(plain)-1, -1, -1) if plain[i] in VOWELS), None)
    return plain if pos is None else plain[:pos] + VOWELS[plain[pos]][tone-1] + plain[pos+1:]


@lru_cache(maxsize=1)
def valid_syllables():
    return {to_normal(s) for readings in PINYIN_DICT.values() for s in readings.split(',')}


def validate_correction(phrase, readings):
    phrase = phrase.strip()
    syllables = unicodedata.normalize('NFC', readings.strip().lower()).split()
    if not phrase or not all(is_han(c) for c in phrase):
        raise ValueError('詞語只可包含漢字。')
    if len(syllables) != len(phrase):
        raise ValueError('每個漢字需要一個拼音，請以空格分開。')
    if any(not re.fullmatch('[a-uw-züāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜêńňǹḿ]+', s) or
           sum(c in MARKS for c in s) > 1 or to_normal(s) not in valid_syllables()
           or (any(c in MARKS for c in s) and with_tone(s,tone_of(s)) != s) for s in syllables):
        raise ValueError('請用帶聲調符號的拼音（例如 zhǎng dà），不要使用數字。輕聲不標調。')
    return phrase, ' '.join(syllables)


@lru_cache(maxsize=128)
def _base(text):
    lookup = CONVERTER.convert(text)
    if len(lookup) != len(text):
        lookup = ''.join(CONVERTER.convert(c)[:1] for c in text)
    raw = pinyin(lookup, style=Style.TONE, heteronym=False, errors=lambda s: list(s), strict=True)
    # errors callback expands punctuation so original offsets always align.
    values = [item[0] for item in raw]
    if len(values) != len(text):
        values = [pinyin(CONVERTER.convert(c), style=Style.TONE, errors=lambda s: list(s))[0][0] for c in text]
    words = list(text)
    for word, start, end in jieba.tokenize(lookup):
        original = text[start:end]
        for index in range(start, end):
            words[index] = original
    result = []
    for i, char in enumerate(text):
        if not is_han(char):
            result.append(Reading(char))
            continue
        options = pinyin(lookup[i], style=Style.TONE, heteronym=True)[0]
        known = to_normal(values[i]) in valid_syllables()
        result.append(Reading(char, values[i] if known else '?', words[i], len(set(options)) > 1 or not known))
    return tuple(result)


@lru_cache(maxsize=128)
def word_boundaries(text):
    lookup = CONVERTER.convert(text)
    if len(lookup) != len(text):
        lookup = ''.join(CONVERTER.convert(c)[:1] for c in text)
    boundaries = {0,len(text)}
    for _,start,end in jieba.tokenize(lookup):
        boundaries.update((start,end))
    return boundaries


def annotate(text, corrections=None, sandhi=True, overrides=None):
    """Reusable phrase corrections + optional position overrides (final surface forms).

    一: yí before tone 4, yì before 1/2/3; yī at boundaries, ordinal 第 and
    digit sequences. 不: bú before tone 4, otherwise bù. Neutral and punctuation
    block sandhi. Third-tone sandhi is deliberately left in dictionary spelling.
    """
    result = list(_base(text))
    rules = {**RULES, **(corrections or {})}
    boundaries = word_boundaries(text)
    index = 0
    while index < len(text):
        matches = [w for w in rules if text.startswith(w, index) and (
            len(w) == 1 or (corrections and w in corrections) or
            (index in boundaries and index+len(w) in boundaries))]
        if not matches:
            index += 1
            continue
        word = max(matches, key=len)
        syllables = rules[word].split()
        if len(syllables) != len(word):
            raise ValueError('Correction does not align with text')
        source = 'parent' if corrections and word in corrections else 'rule'
        for offset, syllable in enumerate(syllables):
            result[index+offset] = Reading(text[index+offset], syllable, word, False, source)
        index += len(word)
    for index, syllable in (overrides or {}).items():
        if 0 <= index < len(result) and is_han(result[index].char):
            token = result[index]
            result[index] = Reading(token.char, syllable, token.word, False, 'parent')
    # Use lexical next tones, not already transformed tones.
    lexical = list(result)
    calendar_positions = set()
    for match in re.finditer(r'[一二三四五六七八九十]+月(?:[一二三四五六七八九十]+[日號])?',text):
        calendar_positions.update(i for i in range(match.start(),match.end()) if text[i] == '一')
    if sandhi:
        for i, token in enumerate(lexical):
            if token.char not in ('一', '不') or token.source == 'parent' or i+1 == len(text):
                continue
            next_token = lexical[i+1]
            if not is_han(next_token.char):
                continue
            tone = tone_of(next_token.pinyin)
            previous = text[i-1] if i else ''
            # Common verb reduplication and A-not-A questions use neutral tone.
            if previous == next_token.char and (
                (token.char == '一' and previous in '看想聽說問試讀寫摸拍走跳數畫玩等找吃喝做跑唱擦洗掃拿放坐站比練學') or
                (token.char == '不' and is_han(previous) and previous not in '一不零〇二三四五六七八九十百千萬億')):
                result[i] = Reading(token.char, 'yi' if token.char == '一' else 'bu',
                                    token.word, token.uncertain, 'sandhi')
                continue
            if next_token.pinyin == '?':
                result[i] = Reading(token.char, token.pinyin, token.word, True, 'sandhi')
                continue
            if token.char == '一':
                previous = text[i-1] if i else ''
                digits = '零〇一二三四五六七八九'
                if text[max(0,i-1):i+1] in ('統一','唯一','萬一') or i in calendar_positions or text[max(0,i-2):i] in ('星期','禮拜') or previous in ('週','周') or previous == '第' or (previous and previous in digits+'十百千萬億兆') or next_token.char in digits:
                    continue
                new_tone = 2 if tone == 4 else 4 if tone in (1, 2, 3) else 1
            else:
                new_tone = 2 if tone == 4 else 4
            result[i] = Reading(token.char, with_tone(token.pinyin, new_tone), token.word, token.uncertain, 'sandhi')
    return result
