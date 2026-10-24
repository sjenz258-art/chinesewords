# Phrase vocabulary

`pinyin_phrases.json` contains developer-authored Mandarin teaching vocabulary, supplementing pypinyin's phrase dictionary. Values are lexical readings; automatic 一/不 conventions apply afterward. Longer phrases win at the same position. Parent corrections override identical phrases, and final position corrections override all rules. This is not a human-certified dictionary. Linguistically meaningful regression examples are in `tests/test_pinyin_review.py`; full-story agreement still requires optional contextual review.
