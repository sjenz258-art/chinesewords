"""Run with: streamlit run app.py"""
import os
import math
from pathlib import Path
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from chinese_reader.analysis import analyse, unique_characters
from chinese_reader.database import Database, CATEGORIES
from chinese_reader.generator import Settings, STORY_TYPES, generate, GenerationError
from chinese_reader.imports import parse_upload
from chinese_reader.reading import CSS
from chinese_reader.reading_ui import reading_panel, pdf_panel
from chinese_reader.pinyin_review import resolved_readings
from chinese_reader.backup import export_backup, restore_backup

load_dotenv()
st.set_page_config(page_title='小小故事園', page_icon='📖', layout='centered')
st.markdown(CSS, unsafe_allow_html=True)


def config(name, default=''):
    value = os.getenv(name)
    if value and value.strip():
        return value.strip()
    try:
        value = st.secrets.get(name, default)
        return str(value).strip() if value is not None and str(value).strip() else default
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return default


def rate(name):
    try:
        value = float(config(name))
        return value if math.isfinite(value) and value >= 0 else None
    except ValueError:
        return None


db = Database(config('DATABASE_PATH', 'data/reading.db'))
settings = Settings(config('OPENAI_API_KEY'), config('OPENAI_MODEL', 'gpt-4.1-mini'),
                    rate('OPENAI_INPUT_USD_PER_MILLION'), rate('OPENAI_OUTPUT_USD_PER_MILLION'))
review_model = config('OPENAI_PINYIN_MODEL', settings.model)
review_settings = Settings(settings.api_key, review_model,
    rate('OPENAI_PINYIN_INPUT_USD_PER_MILLION') if config('OPENAI_PINYIN_INPUT_USD_PER_MILLION') else (settings.input_rate if review_model == settings.model else None),
    rate('OPENAI_PINYIN_OUTPUT_USD_PER_MILLION') if config('OPENAI_PINYIN_OUTPUT_USD_PER_MILLION') else (settings.output_rate if review_model == settings.model else None))
for key, default in {'draft_title': '', 'draft_body': '', 'draft_source': 'Manual', 'editing_id': None,
                     'draft_targets': [], 'draft_type': STORY_TYPES[0], 'draft_length': 200}.items():
    # Reassign to preserve draft widget state when navigating between pages.
    st.session_state[key] = st.session_state.get(key, default)
rows = db.characters()
mastered = [r['char'] for r in rows if r['category'] == 'Mastered']
learning = [r['char'] for r in rows if r['category'] == 'Learning']


def analysis_view(body, targets, desired):
    stats = analyse(body, mastered, learning, targets, desired)
    cols = st.columns(3)
    cols[0].metric('正文漢字總數', stats['total'])
    cols[1].metric('不同漢字數', stats['unique'])
    cols[2].metric('目標字涵蓋率', '未選目標' if stats['target_coverage_pct'] is None else f"{stats['target_coverage_pct']:.0f}%")
    st.write(f"已認識字（不同漢字比例）：{stats['mastered_unique_pct']:.1f}% · 已認識字（按出現次數加權）：{stats['mastered_occurrence_pct']:.1f}%")
    st.caption('兩項熟悉度都只計算 Mastered；Learning 不算已掌握。標題、標點及非漢字不計入字數。')
    st.write(f"目標字：{stats['target_count']} / {stats['target_total']} · 未用目標字：{'、'.join(stats['missing_targets']) or '無'}")
    if not stats['within_length']:
        st.warning(f"正文不在所選長度範圍（{desired-20}–{desired+20} 字）內。你可以修改後再儲存。")
    with st.expander(f"目標字頻率與陌生字（{stats['unfamiliar_count']} 個）"):
        if stats['target_frequency']:
            st.dataframe(pd.DataFrame(stats['target_frequency'].items(), columns=['目標字', '出現次數']), hide_index=True)
        st.write('陌生字（包括 New 及未分類）：' + ('、'.join(stats['unfamiliar']) or '無'))
    return stats


st.title('📖 小小故事園')
st.caption('繁體中文故事 · 一起讀，一起學')
page = st.sidebar.radio('前往', ['創作故事', '閱讀書庫', '漢字管理', '備份與說明'])
st.sidebar.caption('Phase 2 · 普通話拼音與 A4 列印')

if page == '漢字管理':
    st.header('漢字管理')
    st.write('Mastered＝已掌握 · Learning＝學習中 · New＝未介紹。故事出現次數不會自動更改分類。')
    with st.form('add_chars'):
        text = st.text_area('輸入或貼上漢字清單（自動去除重複及標點）')
        category = st.selectbox('加入或移至分類', CATEGORIES, index=1)
        if st.form_submit_button('儲存漢字'):
            count = db.put_characters(text, category)
            st.session_state['char_notice'] = f'已儲存 {count} 個不同漢字。'
            st.rerun()
    if 'char_notice' in st.session_state:
        st.success(st.session_state.pop('char_notice'))
    st.subheader('現有漢字')
    for cat in CATEGORIES:
        chars = [r['char'] for r in rows if r['category'] == cat]
        st.write(f"**{cat}（{len(chars)}）**：{''.join(chars) or '尚未加入'}")
    selected = st.multiselect('選擇要移動或刪除的漢字', [r['char'] for r in rows])
    destination = st.selectbox('移至', CATEGORIES)
    if st.button('移動所選漢字', disabled=not selected):
        db.put_characters(''.join(selected), destination)
        st.rerun()
    confirm = st.checkbox('確認刪除所選漢字')
    if st.button('刪除所選漢字', disabled=not selected or not confirm):
        db.remove_characters(selected)
        st.rerun()
    st.subheader('匯入 CSV / Excel')
    st.caption('建議欄名 character,category；category 使用 Mastered、Learning 或 New。普通字表則全部加入所選分類。後出現的重複字分類優先。')
    upload = st.file_uploader('選擇 .csv 或 .xlsx', type=['csv', 'xlsx'])
    import_category = st.selectbox('普通字表預設分類', CATEGORIES, index=1)
    header_choice = st.selectbox('字表第一列', ['自動辨識欄名','第一列是欄名','沒有欄名（第一列也是漢字）'])
    st.caption('若清單第一個字就是「字」或「漢字」，請選「沒有欄名」，以免把它當作標題。')
    if st.button('匯入字表', disabled=upload is None):
        try:
            entries = parse_upload(upload, upload.name, import_category, has_header={'自動辨識欄名':None,'第一列是欄名':True,'沒有欄名（第一列也是漢字）':False}[header_choice])
            db.import_characters(entries)
            st.session_state['char_notice'] = f'已匯入 {len(set(c for c, _ in entries))} 個不同漢字。'
            st.rerun()
        except (ValueError, UnicodeError, OSError, KeyError):
            st.error('無法讀取字表。請檢查格式、編碼（UTF-8）及分類名稱。')
    csv = pd.DataFrame(rows, columns=['char', 'category']).rename(columns={'char': 'character'}).to_csv(index=False).encode('utf-8-sig')
    st.download_button('匯出字表 CSV', csv, 'characters.csv', 'text/csv')

elif page == '創作故事':
    st.header('創作與修改')
    mode = st.radio('故事來源', ['手動模式（免費，無需 API）', 'AI 模式（需自備 OpenAI API）'])
    options = sorted(set(learning) | set(st.session_state.draft_targets))
    targets = st.multiselect('本篇目標字（先到漢字管理加入 Learning 字）', options,
                             key='draft_targets')
    story_type = st.selectbox('故事類型', STORY_TYPES, key='draft_type')
    desired = st.number_input('期望正文漢字數（允許上下 20 字）', 80, 500, step=10, key='draft_length')
    if not learning:
        st.info('可先直接貼上故事；加入 Learning 字後便能選擇練習目標。')
    if mode.startswith('AI'):
        st.caption(f'模型：{settings.model}。故事、目標字及已掌握字會傳送至 OpenAI。API 費用由你的帳戶支付。')
        if not settings.api_key:
            st.warning('尚未設定 API 金鑰。手動模式可照常使用；設定方法見 README。')
        revision = st.text_input('修改要求（可要求自然加入下方分析列出的漏用字）')
        if st.button('產生 / 重新產生 / 按要求修改', disabled=not settings.api_key):
            try:
                with st.spinner('正在寫故事…'):
                    result = generate(settings, mastered, targets, story_type, desired,
                                      st.session_state.draft_body, revision)
                st.session_state.draft_title = result['title']
                st.session_state.draft_body = result['body']
                st.session_state.draft_source = 'AI'
                st.session_state.editing_id = None
                st.session_state['usage'] = result
            except GenerationError as exc:
                st.error(str(exc))
        if 'usage' in st.session_state:
            usage = st.session_state.usage
            st.caption(f"最近一次請求：輸入 {usage['input_tokens'] if usage['input_tokens'] is not None else '未知'} tokens，輸出 {usage['output_tokens'] if usage['output_tokens'] is not None else '未知'} tokens。" +
                       (f"估算 US${usage['cost']:.6f}（不含其他費用）。" if usage['cost'] is not None else '未設定單價，無法估算費用；請到 OpenAI 帳戶查看實際用量。'))
    else:
        st.caption('貼上任何你有權使用的繁體故事。手動輸入與離線拼音不會呼叫 API；可選 AI 拼音核對需另行按鈕啟動。')
        if st.button('載入原創示例故事'):
            st.session_state.draft_title = '小鳥的雨天朋友'
            st.session_state.draft_body = Path('samples/story.txt').read_text(encoding='utf-8').strip()
            st.session_state.draft_source = 'Manual'
            st.session_state.editing_id = None
    st.text_input('故事標題', key='draft_title', max_chars=200)
    st.text_area('故事正文（可直接編輯，按 Ctrl+Enter 或點出文字框更新分析）', key='draft_body', height=280)
    if st.session_state.draft_body:
        analysis_view(st.session_state.draft_body, targets, desired)
        reading_panel(db, st.session_state.draft_body, mastered, learning, key='draft', review_settings=review_settings)
        pdf_panel(db, st.session_state.draft_title, st.session_state.draft_body, targets, key='draft_pdf', review_model=review_settings.model)
    update = st.checkbox('更新目前已載入的故事', disabled=st.session_state.editing_id is None)
    if st.button('儲存至書庫', type='primary'):
        try:
            sid = db.save_story(st.session_state.draft_title, st.session_state.draft_body, targets,
                                story_type, st.session_state.draft_source, desired,
                                st.session_state.editing_id if update else None)
            st.session_state.editing_id = sid
            st.success('故事已儲存。前往「閱讀書庫」便可閱讀。')
            readings, issues, _, _ = resolved_readings(db,st.session_state.draft_body,review_settings.model)
            pending = len(issues) if issues is not None else sum(t.uncertain for t in readings)
            if pending:
                st.warning(f'儲存前檢查：還有 {pending} 處拼音疑義或分歧，已保留提示；可在拼音核對區集中處理。')
        except ValueError as exc:
            st.error(str(exc))

elif page == '閱讀書庫':
    st.header('閱讀書庫')
    favourites_only = st.checkbox('只看最愛')
    stories = [s for s in db.stories() if not favourites_only or s['favourite']]
    if not stories:
        st.info('書庫還沒有故事。前往「創作故事」貼上故事或載入示例，再儲存。')
    else:
        ids = [s['id'] for s in stories]
        if st.session_state.get('reading_id') not in ids:
            st.session_state.reading_id = ids[0]
        by_id = {s['id']: s for s in stories}
        story_id = st.selectbox('選擇故事', ids, format_func=lambda i: f"{by_id[i]['title']} · #{i}", key='reading_id')
        story = by_id[story_id]
        position = ids.index(story_id)
        def navigate(offset):
            st.session_state.reading_id = ids[position + offset]
        left, right = st.columns(2)
        left.button('← 上一篇', disabled=position == 0, on_click=navigate, args=(-1,))
        right.button('下一篇 →', disabled=position == len(ids)-1, on_click=navigate, args=(1,))
        st.subheader(story['title'])
        size = st.slider('字體大小', 22, 48, 32)
        highlight = st.checkbox('顯示學習顏色', value=True)
        if highlight:
            st.caption('綠色＝已掌握 · 橙色＝學習中 · 灰色＝New 或未分類')
        reading_panel(db, story['body'], mastered, learning, size, highlight, key=f'library_{story_id}', review_settings=review_settings)
        pdf_panel(db, story['title'], story['body'], story['targets'], key=f'library_pdf_{story_id}', review_model=review_settings.model)
        fav = st.checkbox('♥ 我的最愛', value=bool(story['favourite']), key=f'fav_{story_id}')
        if fav != bool(story['favourite']):
            db.favourite(story_id, fav)
        with st.expander('家長：查看字數及學習分析'):
            analysis_view(story['body'], story['targets'], story['desired'])
            st.caption(f"來源：{story['source']} · 類型：{story['story_type']} · 建立：{story['created_at'][:10]}")
        if st.button('載入編輯器'):
            st.session_state.draft_title = story['title']
            st.session_state.draft_body = story['body']
            st.session_state.draft_targets = story['targets']
            st.session_state.draft_type = story['story_type']
            st.session_state.draft_length = story['desired']
            st.session_state.draft_source = story['source']
            st.session_state.editing_id = story['id']
            st.success('已載入。請前往「創作故事」修改；勾選更新即可保留原有故事編號。')
        st.download_button('下載故事文字', f"{story['title']}\n\n{story['body']}".encode('utf-8'), f'story-{story_id}.txt', 'text/plain')

else:
    st.header('備份與說明')
    if st.session_state.pop('_restore_notice',False):
        st.success('完整資料已還原。請前往閱讀書庫。')
    st.warning('雲端主機重啟或重新部署後，本機 SQLite 資料可能消失。每次使用後請下載完整備份，保存在自己的裝置。')
    st.download_button('下載完整 JSON 備份（可在手機還原）', export_backup(db), 'reading-backup.json', 'application/json')
    full_restore = st.file_uploader('還原完整 JSON 備份（故事、漢字及拼音記錄）', type=['json'], key='full_restore')
    replace_all = st.checkbox('我已下載目前備份，確認以此備份取代全部資料', key='replace_all')
    if st.button('還原完整資料', disabled=full_restore is None or not replace_all):
        try:
            restore_backup(db,full_restore.getvalue().decode('utf-8'))
            for name in list(st.session_state):
                if name not in ('full_restore','replace_all'):
                    del st.session_state[name]
            st.session_state['_restore_notice'] = True
            st.rerun()
        except (ValueError,UnicodeError):
            st.error('無效的完整備份，資料未更改。請使用本應用程式匯出的完整 JSON 備份。')
    st.download_button('下載完整 SQLite 備份（包含故事）', db.backup(), 'reading-backup.sqlite', 'application/octet-stream')
    st.download_button('下載漢字 JSON 備份', db.export_characters(), 'characters.json', 'application/json')
    st.caption('完整 SQLite 還原：停止應用程式，將備份複製至 data/reading.db，再啟動。不要在程式運作時覆蓋資料庫。')
    restore = st.file_uploader('還原漢字 JSON（會取代現有漢字，保留故事）', type=['json'])
    consent = st.checkbox('我已備份，確認取代現有漢字清單')
    if st.button('還原漢字', disabled=restore is None or not consent):
        try:
            db.restore_characters(restore.getvalue().decode('utf-8'))
            st.success('漢字清單已還原。')
        except (ValueError, KeyError, TypeError, UnicodeError):
            st.error('無效的漢字備份；現有資料未更改。')
    st.write('Phase 2 已提供拼音、讀音修正、三種閱讀模式及 A4 PDF。工作紙提供可編輯的句意重述模板；完整習作及學習進度將於 Phase 3 加入。')
    st.write('此版本供家庭私人使用，沒有登入及帳戶隔離；不要公開部署含孩子私人資料的實例。')
    st.link_button('OpenAI 最新 API 價格', 'https://openai.com/api/pricing/')
