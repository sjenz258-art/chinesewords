# Phase 2: pinyin and A4 printing

You do not need to run tests yourself. Use the updated application through your hosted Streamlit link, or run `python -m streamlit run app.py` locally as described in README.md. Uploading this version to an existing deployment requires updating its source files, including `assets/fonts/` and `requirements.txt`; older ZIP files do not update automatically. The application is not automatically published from this workspace.

## Reading and corrections

Open a saved story in **閱讀書庫**, or paste a draft in **創作故事**. Choose:

- **只看漢字** — Chinese text only.
- **漢字上方顯示拼音** — tone-mark pinyin above each character.
- **點按才顯示拼音** — tap a character to reveal its pinyin; tap again to hide it. Native HTML details controls also work with keyboard focus and Enter/Space.

Tap characters in any mode to see the pronunciation and a small offline glossary. The glossary covers only a few words; missing meanings are explicitly labelled, not invented. The font-size and learning-colour controls remain available in the library. Dotted underlines mark potentially ambiguous readings.

Under **家長：核對及修正拼音**, select a character by its numbered position and surrounding text.

- **只修正這個位置** saves the exact reading for that occurrence. It does not change other occurrences. This is the safest option for polyphonic characters. It is stored against a SHA-256 hash of the complete body and its Unicode-codepoint position; changing the body invalidates its use, rather than silently moving it to the wrong character. Identical text reused in another saved story uses the same corrections.
- To reuse a reading, enter a complete Chinese word and one tone-marked syllable per character, separated by spaces (e.g. `音樂` → `yīn yuè`). Longer phrases win over shorter phrases at the same start position. A parent's rule replaces a built-in rule for the same phrase. Rules are applied left-to-right and longest-first, not via a linguistic parser. Single-character rules are allowed, but can affect unrelated words; prefer complete words.
- Delete reusable rules, or clear a body's position corrections, using the supplied controls.

Corrections save immediately to SQLite, even before saving the story. They are included in the **complete SQLite backup**. Character-only CSV/JSON backups contain no pinyin rules. The newer complete JSON backup includes them and can be restored from a phone through the app. Existing Phase 1 databases gain the new tables automatically; stories and character categories are preserved.

## How pronunciations are produced

The offline engine uses pypinyin's phrase dictionary and jieba word segmentation, supplemented by explicit vocabulary rules. OpenCC converts a lookup copy from Traditional to Simplified; the original text is never changed. Each original Unicode codepoint receives exactly one token, including punctuation and line breaks, so ruby and PDF alignment refer to the same text positions. Parent phrase rules take precedence over built-in rules; position corrections take precedence over everything.

Required examples are tested:

| Word | Reading |
| --- | --- |
| 長大 | zhǎng dà |
| 長短 | cháng duǎn |
| 音樂 | yīn yuè |
| 快樂 | kuài lè |

Conventions:

- Tone marks, not tone numbers. Neutral tone has no mark (`de`, `you`). Third-tone combinations retain dictionary spellings, e.g. `nǐ hǎo`, rather than respelling surface third-tone sandhi.
- 一 is `yí` before a fourth tone, `yì` before first/second/third tones, and `yī` at a boundary or before neutral tone. Ordinal 第, serial digit strings and terminal 一 in compound numbers preserve `yī`; multipliers differ (一百 → yì bǎi, 一萬 → yí wàn). Clear weekdays/calendar spans also keep ordinal `yī`.
- 不 is `bú` before a fourth tone, otherwise `bù`. Punctuation and line breaks block sandhi. Decisions use the next lexical tone. Parent corrections are treated as final intended spellings, so automatic sandhi does not change a parent-corrected 一 or 不.
- These are pedagogical rules, not a complete speech prosody model. Reduplication (看一看 / 好不好), lexical exceptions, emphatic speech, names, and unusual pauses need parent review. Correct a particular reading when the displayed form differs from your teaching convention.

A multi-reading character not covered by a reviewed vocabulary rule is conservatively flagged, even if the dictionary selected a plausible reading. Unknown readings show `?`. This can produce many warnings. Conversely, no warning does **not** certify that a reading is correct: dictionaries, segmentation and traditional/simplified mergers can be wrong. No automatic pronunciation has been independently verified by a human. The correction validator checks alignment and tone-mark syntax, not whether a syllable or pronunciation is linguistically correct.

## Printing

Expand **列印：下載 A4 PDF**. Edit target vocabulary, the three questions and optional discussion prompt, then click **準備三種 PDF**. Download:

1. **拼音閱讀** — pinyin above every Chinese character, large text. Potentially ambiguous readings have a small underline and a parent-review note.
2. **純中文閱讀** — no pinyin; optional target-character shading.
3. **練習工作紙** — Chinese story followed by a separate vocabulary/question/handwriting page. Longer prompts automatically paginate.

The default questions are a free rule-based sentence-retelling exercise tied to sentences in the story. They are clearly labelled in the interface and PDF; they are not equivalent to curated or AI-generated comprehension questions. Parents can replace them before printing. Worksheet edits are kept in the current UI session and exported PDF, not saved as reusable story exercises yet; Phase 3 will add persistent exercises.

PDFs use measured cells with a shared centre for each character/pinyin pair, A4 margins, automatic page breaks and licensed embedded fonts. Noto Sans TC (SIL OFL) supplies Traditional Chinese; DejaVu Sans supplies Latin tone marks. Font files and licences are bundled, so no printer-specific fonts or font downloads are needed at runtime. If neither font supports a character, export stops with a list of unsupported glyphs rather than silently producing missing-glyph boxes. Very rare Han characters may need a different font in a future version. Story titles can wrap. Short paragraphs and a typical 200-character story usually fit on one reading page; many explicit newlines or long titles can require more pages. Print A4 at 100%/actual size.

## Validation and sample outputs

Run the complete suite with `python -m pytest -q`. No paid API calls are made. The suite includes Phase 1 regressions, required polyphonic words, 一/不 conventions, original-text alignment, punctuation/newlines, invalid correction syntax, reusable and position correction persistence, A4 dimensions, font embedding, one-page sample reading sheets, two-page practice sheets, numerical character/pinyin centring, long-text pagination, unsupported glyph rejection, and the actual Streamlit correction/PDF workflow.

Sample PDFs are in `samples/pdfs/`; rendered images are in `samples/previews/`. Regenerate both with `python scripts/render_samples.py`. Rendered samples were visually inspected for glyphs, tone marks, spacing, wrapping and answer lines. The sample reading sheet is one A4 page and practice sheet is two pages.

A separate developer browser check at 390 × 844 pixels verified ruby rendering, no page-level horizontal overflow, tap/reveal/hide, and Chinese-only mode. Screenshots are in `samples/previews/`. To repeat that check, install the optional development package `playwright`, run a sample-loaded app at localhost:8501, and use `python scripts/check_mobile.py` with system Chromium. Playwright is not needed to run the application. This is a Chromium mobile viewport check, not a physical iPhone/Safari test; native ruby/details should be checked on your own device after deployment.

Phase 3 (full learning activities and progress tracking) remains outstanding. Optional audio, multiple profiles and durable hosted storage remain future work. Community Cloud SQLite persistence limitations still apply: download a complete backup after each session.

## Subsequent accuracy update

See [PINYIN_ACCURACY.md](PINYIN_ACCURACY.md). The current version expands the vocabulary, handles common 一/不 reduplication, and optionally uses an independent AI pass to show disagreements and remaining doubts. AI-agreed readings have their warning markers removed, with a clear automatic-review status; this does not mean human verification. PDFs share this status. Correction validation now also rejects syllables absent from pypinyin's syllable inventory; that validates form, not contextual correctness.


The reliability update also restricts built-in multi-character rules to jieba word boundaries; explicit parent phrase corrections remain deliberate overrides. It adds longer compound entries and expands common A一A/A不A neutral-tone handling. Uncertain segmentation and linguistic exceptions remain possible. See REVIEW.md for the complete change record.
