# Project review and reliability improvements

Reviewed the implemented Phase 1/2 application, including code, tests, pronunciation rules and their limits, character imports/statistics, story persistence, API error/cost handling, review-cache behaviour, backup/restore, mobile controls and PDF typesetting. Independent focused reviews covered pinyin, data handling and PDF/reading code. Issues below were reproduced and fixed. This is a software review, not certification of every Chinese sentence or pronunciation.

## Important fixes

| Area | Problem found | Change |
| --- | --- | --- |
| Saved corrections | Saving stripped leading/trailing body whitespace, changing the hash and losing the association with position corrections/AI reviews. | Preserve the body exactly. Titles are still trimmed. |
| Pronunciation context | Built-in phrases matched arbitrary substrings: 子彈 could override 猴子彈琴, 西藏 could match inside 東西藏起來, and 長大 could override 長大衣. | Require multi-character built-in rules to match complete segmentation boundaries. Add explicit longer entries such as 長大衣 and 背書包. Parent rules remain deliberate overrides. Unresolved dictionary/segmentation readings remain flagged. |
| Tone changes | 一/不 used the uncorrected following reading. Number endings and calendar expressions could receive the wrong tone. | Apply position corrections before sandhi. Distinguish 一百/一萬 from 十一個/二十一隻; preserve fixed words, weekdays and clear calendar expressions. Expand common verb reduplication. |
| Valid pinyin | Correct syllabic nasal 嗯 → ń was discarded by an ASCII-letter check. Tone marks on the wrong vowel and `nv` spelling could be accepted. | Recognise normalised valid syllables; reject invalid mark placement and require ü rather than v. |
| Character imports | Headings could become characters; a headerless list beginning with 字 could silently lose that character. | Recognise standard English/Chinese headings, add an explicit auto/header/no-header choice, and import all changes in one transaction. |
| Restoring data | Malformed JSON roots or out-of-range integers could crash restore. Full restoration previously required filesystem access. | Validate data before replacement, reject integers outside SQLite's range, roll back SQL conflicts, and add a complete JSON download/upload/restore flow usable from a phone. |
| Story updates | Editing an AI-origin story in manual mode changed its source label; updating a missing story ID could falsely report success. | Preserve provenance and reject updates that affect no story. |
| Cached reviews | Cached readings passed validation but comparison still used the unnormalised originals. | Compare the validated/normalised readings. Parent-confirmed choices retain parent provenance. |
| PDF layout | A single-character punctuation lookahead could separate closing punctuation; unusual pasted whitespace could print missing glyphs; CR-only breaks differed on screen and paper. | Keep punctuation runs together and normalise display whitespace/line breaks consistently without changing stored text. |
| PDF reliability | Unprinted worksheet fields could block reading-sheet downloads; one failed format prevented all formats; glyph-map unions were rebuilt for every character. | Validate only printed content, retain successful formats, and check unique characters against one supported-glyph set. |
| Mobile reader | Right-edge pop-ups could overflow; multiple fixed pop-ups could overlap. | Keep mobile panels within viewport bounds and use mutually exclusive native details controls. Tap the open character again to close. |
| Configuration/cost | Infinite price values were accepted, missing token usage looked like zero, and DATABASE_PATH did not honour Streamlit secrets. | Reject nonfinite rates, show unknown usage accurately, normalise empty configuration values, and support DATABASE_PATH through the documented configuration sources. |

## Backups on a phone

In **備份與說明**, download **完整 JSON 備份** regularly. It includes stories, favourites, characters, position/phrase pinyin corrections, and cached AI reviews/parent choices. To restore it, upload the file under **還原完整 JSON 備份**, confirm replacement and click **還原完整資料**. Validation and replacement are atomic. Use the separate character-only export only when you want to transfer the character list. The existing SQLite backup remains available for computer-based archival and larger libraries. JSON upload/restore is limited to 10 MB and targets the single profile used by this version.

## Validation

The automated regression suite now has 100 passing tests. New cases cover exact-body preservation, parent-informed sandhi, numeral/calendar/compound phrase examples, syllabic nasals, pinyin spelling, header/no-header files, atomic imports, malformed and oversized backup values, complete JSON round trips, SQL rollback, cached-review normalisation, PDF punctuation/whitespace and unprinted fields, and reopening an AI-origin story through manual mode. Existing character analysis, API sanitisation, manual/no-key, ruby modes, pinyin review and PDF tests remain in place.

All paid API responses in tests are mocked. This validates behaviour and safe failure handling, not a measured live-model pronunciation accuracy rate. No paid API calls were made for this review.

Regenerated the three sample PDFs and their renderings. The sample reading versions each fit one A4 page; the practice version has a separate answer page. Font embedding, glyph support, measured pinyin centring, bounds and long-text pagination are checked programmatically. Rendered previews are available in `samples/previews/`.

The developer browser check passed: full JSON download/upload/restore, library reopening, a 390-pixel viewport without horizontal overflow, exclusive tap reveal, and tooltip bounds. Its repeatable script is `scripts/check_review_browser.py`: it starts a temporary local instance, downloads/restores a full JSON backup, opens the library, then checks a 390-pixel reading viewport, exclusive tap reveal and tooltip bounds. It requires optional Playwright, system Chromium, and local socket permission. Physical iPhone Safari behaviour is not certified by a Chromium viewport check.

## Remaining improvements, in order of usefulness

1. **Durable hosted storage and access control.** Local SQLite on Community Cloud can disappear on restart. Phone restore reduces recovery friction but is not automatic durable storage. Instances still share one database and need private hosting/access controls; built-in user authentication and account isolation are not implemented.
2. **Real pronunciation evaluation.** Build an educator-reviewed benchmark of complete stories, names, neutral tones and difficult contexts, and evaluate optional live models against it. The developer-authored vocabulary and AI agreement are not educator verification. Segmentation, names, semantic neutral-tone differences and calendar/duration ambiguity remain possible sources of errors.
3. **Phase 3 learning activities.** Persist editable exercises; add richer comprehension/vocabulary activities, explicit read/recognition records and exposure tracking. Current printable questions are honestly labelled rule-based retelling prompts.
4. **Phase 4 features.** Add spaced repetition, multiple-child controls and optional audio after the learning records exist.
5. **Usability on real devices.** Test iPhone Safari and physical A4 printing with the family's preferred text sizes. Keyboard/zoom/accessibility and device-specific ruby rendering deserve continued testing.
6. **Release automation.** Add continuous integration, repeatable dependency locking and deployment automation when a usable Git repository is connected. This workspace currently contains local source files and downloadable packages; this review does not publish a hosted app.

Do not rely on older ZIP downloads to contain these fixes. Use the newly packaged review release when deploying or updating an existing deployment.
