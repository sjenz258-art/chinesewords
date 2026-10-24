# Pinyin accuracy enhancement

The application now combines a larger offline phrase vocabulary with an optional independent AI reading pass. This reduces the amount of comparison parents need to do; it does not certify arbitrary stories as error-free. No qualified educator has reviewed or endorsed this release's full pronunciation output.

## What to do in the app

1. Paste or generate a story as usual. Offline vocabulary rules and basic pronunciation checks run immediately, with no API calls. The expansion adds more than 100 phrase entries covering common polyphonic words, neutral tones and children's story vocabulary. Examples include 頭髮/發現, 種子/種花, 乾淨/能幹, 教書/教室, 盛飯/盛開 and 睡着/笑着. Contextually ambiguous phrases such as 教學 and 轉動 are intentionally not given a blanket rule.
2. If you have configured an OpenAI key, expand **提高拼音準確度：可選 AI 核對及例外清單**, then click **用 AI 核對拼音（需 API 費用）**. This sends the entire body and original character positions to OpenAI. It does not send your child's character database or the offline readings. The model is asked to judge each character from full sentence context independently, using the same tone conventions.
3. The app compares every returned reading with the current offline/parent-corrected readings. Matching readings no longer appear on the exception list. The status explicitly says this is automatic agreement, not human verification. Any disagreement, missing offline reading, or uncertainty reported by the AI remains marked on the screen and pinyin PDF.
4. Review only the listed exceptions. **採用 AI 讀音** stores that occurrence's suggested reading; **保留目前讀音並確認此例外** keeps your current reading. Both record a parent choice, not professional verification. Suggestions for simpler wording appear when the AI returns them; they are not guaranteed for every exception, and are never applied automatically. Edit the draft if a rewrite is useful, then run a new review of the new body. No API rewrite is needed to edit the text yourself.
5. Save or print. Saving still works without an API key or completed review, but warns about pending issues. All three PDFs use the same resolved readings/markers as the screen. The pinyin sheet reports automatic review status; AI-agreed readings are not called human-verified. The Chinese-only/practice PDFs contain no pinyin.

The review is opt-in: generating, saving, opening, printing or rerunning the app never triggers a paid pronunciation request automatically. If the request fails or returns incomplete/misaligned/invalid readings, no partial AI result is applied. Offline reading remains available, and a previous valid review is retained.

## Configuration and cost

The existing `OPENAI_API_KEY` is reused securely from environment variables or Streamlit secrets. By default the review uses `OPENAI_MODEL`. You can choose a different compatible model:

```dotenv
OPENAI_PINYIN_MODEL=gpt-4.1-mini
OPENAI_PINYIN_INPUT_USD_PER_MILLION=
OPENAI_PINYIN_OUTPUT_USD_PER_MILLION=
```

Enter current model-specific USD-per-million-token prices if you want a cost estimate. If review and story models are the same and review prices are empty, the app uses the story-model rates. If the models differ, it requires explicit review prices rather than applying the wrong rates. Streamlit secrets accept the same names in TOML format. Never put the API key in a repository.

Review responses contain one record per Chinese character and can use substantially more output tokens than a story-generation request. The app displays actual returned token counts and an estimate after each successful review when pricing is configured. Current pricing: https://openai.com/api/pricing/. Failed or rejected responses may still be billed. Requests have a 90-second timeout and no automatic SDK retries. Reviews support 1–800 Chinese characters and at most 5000 total codepoints; split longer material into sections. Manual mode has no new length restriction.

## Storage and reproducibility

Reviews and parent decisions are stored in a child-scoped SQLite table and included in complete SQLite and complete JSON backups. The full JSON backup can be restored from the phone interface. Character-only exports do not include them. The cache identity includes the exact body, model, pronunciation engine version and review prompt version. Any text change, even a newline, requires a new review. Different titles with identical bodies can share the same review. Changing a correction reruns the comparison against the cached independent readings without another API charge; a confirmation is valid only while the current reading still matches the parent's recorded choice. A different model or engine/review version also invalidates automatic reuse. Updating an alias's underlying provider model is not detectable: click **重新用 AI 核對拼音** if you want a fresh response. You can delete a review from the interface.

The app sends no offline baseline readings in the AI prompt, to reduce anchoring. However, dictionary/AI agreement is not statistical independence or proof of accuracy. Both can make the same mistake. The cached response stores model, token counts and estimated cost, never the API key. It is scoped by child and story content; this does not add application authentication. Existing private-deployment and cloud-persistence guidance still applies.

## Tone conventions and limitations

The previous 一/不 rules remain, with common reduplication added: 看一看 → kàn yi kàn and 是不是 → shì bu shì. Dictionary third tones remain unchanged (nǐ hǎo); neutral tones have no mark. Position/phrase corrections remain final and take precedence. Special speech emphasis, names, rare words, segmentation errors and unusual pauses can still be wrong. Parents may use the correction tools at any time, even when a character has no warning.

AI responses must cover every Han character exactly once, match original codepoint positions and characters, supply explicit uncertainty, and use syntactically valid pinyin syllables. Validation rejects invented syllables such as `xyz`, tone numbers, duplicated/omitted positions and markup in readings. It cannot establish whether an otherwise valid syllable is correct in context. AI explanations and rewrite suggestions are advisory, not automatic edits.

The phrase dictionary is developer-authored teaching vocabulary with regression tests; it is **not** an educator-certified dictionary. A collection of stories and complete pinyin reviewed by a qualified Mandarin educator would offer stronger assurance, but obtaining that human review remains outside this automated implementation. There is no fabricated educator endorsement or measured accuracy percentage.

## Validation

Run `python -m pytest -q`. Tests cover the expanded pronunciation pairs and reduplication; independent review input and cost calculations; complete/misaligned/invalid responses; comparison and parent choices; cache persistence, invalidation and child scoping; no-key/error handling and sanitised credentials; screen/PDF consistency; and the real Streamlit accept-reading/PDF workflow. API responses are mocked, so these establish behaviour, not a measured improvement in live-model linguistic accuracy. A live paid API review was not run in development.


The subsequent reliability review tightened built-in phrase matching to word boundaries, fixed compound-number/calendar uses of 一, expanded ordinary reduplication, and recalculates preceding 一/不 tones using a parent-corrected following reading. Engine-version changes invalidate cached AI comparisons so old automatic agreement is not presented as a current check. Saved parent corrections remain. A new paid review remains optional.
