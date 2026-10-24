"""Parent pinyin review and PDF export controls, shared by draft and library."""
import hashlib
import streamlit as st
from .analysis import is_han
from .pinyin_engine import annotate
from .generator import Settings
from .pinyin_review import request_review, resolved_readings, review_key, ReviewError
from .pdf_export import create_pdf, default_questions
from .reading import story_html


def reading_panel(db, text, mastered, learning, size=30, highlight=True, key='read', review_settings=None):
    digest = hashlib.sha256(text.encode()).hexdigest()[:12]
    key = f'{key}_{digest}'
    corrections = db.pinyin_corrections()
    overrides = db.position_corrections(text)
    review_settings = review_settings or Settings()
    tokens, issues, agreed, review = resolved_readings(db, text, review_settings.model)
    accuracy_panel(db, text, tokens, issues, agreed, review, review_settings, key)

    modes = {'只看漢字': 'chinese', '漢字上方顯示拼音': 'pinyin', '點按才顯示拼音': 'tap'}
    mode = st.radio('閱讀模式', list(modes), index=1, horizontal=True, key=key+'_mode')
    st.markdown(story_html(text, mastered, learning, size, highlight, modes[mode], tokens), unsafe_allow_html=True)
    st.caption('點按漢字可查看讀音及小字典。點按模式中再次點按可收起；拼音為普通話。虛線底線表示可能有多種讀音。')
    uncertain = [(i,t) for i,t in enumerate(tokens) if t.uncertain]
    with st.expander(f'家長：核對及修正拼音（{len(uncertain)} 處待核對）'):
        st.caption('自動拼音未經逐字人工驗證。已知詞語規則優先，多音字採保守提示；未標示也可能出錯。')
        if uncertain:
            st.write('待核對：'+'、'.join(f'{t.char}（{t.pinyin}，第{i+1}字元）' for i,t in uncertain))
        positions = [i for i,t in enumerate(tokens) if is_han(t.char)]
        if positions:
            selected = st.selectbox('選擇要修正的字（包含標點的位置編號）', positions,
                                    format_func=lambda i: f'{i+1}：{text[max(0,i-4):i]}【{text[i]}】{text[i+1:i+5]}', key=key+'_pos')
            syllable = st.text_input('這個字的拼音（帶聲調符號）', value=tokens[selected].pinyin, key=f'{key}_syllable_{selected}')
            if st.button('只修正這個位置', key=key+'_save_pos'):
                try:
                    db.save_position_correction(text, selected, syllable)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
            st.caption('位置修正會跟隨完全相同的正文儲存；正文一旦更改，就需要重新核對。它不會把多音字的所有讀法改成相同。')
            phrase = st.text_input('可重用的完整詞語（建議使用詞語，避免單字規則影響其他詞）',
                                   value=tokens[selected].word, key=f'{key}_phrase_{selected}')
            readings = st.text_input('詞語拼音（每字一音，以空格分開）', key=f'{key}_phrase_py_{selected}')
            if st.button('儲存詞語讀音供以後重用', key=key+'_save_phrase'):
                try:
                    db.save_pinyin_correction(phrase, readings)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        if corrections:
            st.write('已儲存詞語規則：'+ '；'.join(f'{w}：{p}' for w,p in corrections.items()))
            remove = st.selectbox('選擇要刪除的詞語規則', list(corrections), key=key+'_remove')
            if st.button('刪除詞語規則', key=key+'_delete'):
                db.delete_pinyin_correction(remove)
                st.rerun()
        if overrides and st.button('清除此正文的所有位置修正', key=key+'_clear'):
            db.delete_position_corrections(text)
            st.rerun()
        st.caption('一／不：採常見連讀變調（一在四聲前讀 yí，在一二三聲前讀 yì；不在四聲前讀 bú）。序數、數字串及句末保留一的原調。輕聲不標調；三聲連讀仍標字典調。特殊語氣、重疊詞和停頓請家長核對。')
    return corrections, overrides


def pdf_panel(db, title, body, targets, key='pdf', review_model='gpt-4.1-mini'):
    digest = hashlib.sha256(body.encode()).hexdigest()[:12]
    key = key+'_'+digest
    with st.expander('列印：下載 A4 PDF'):
        st.caption('三種版本：拼音閱讀、純中文閱讀、練習工作紙。所有版本使用與螢幕相同的修正讀音。')
        highlight = st.checkbox('純中文及練習版本標示目標字', value=True, key=key+'_highlight')
        vocabulary = st.text_input('工作紙目標詞語（可自行編輯）', value='、'.join(targets), key=key+'_vocab')
        st.caption('以下預設為免費、規則式句意重述練習，不是 AI 生成的理解題；家長可改寫。完整學習活動將於 Phase 3 加入。')
        defaults = default_questions(body)
        questions = [st.text_area(f'閱讀問題 {i+1}', value=defaults[i] if i < len(defaults) else '',
                                 key=f'{key}_q{i}', height=90) for i in range(3)]
        questions = [q for q in questions if q.strip()]
        discussion = st.text_input('可選討論題', key=key+'_discussion')
        tokens, issues, agreed, review = resolved_readings(db, body, review_model)
        note = (f'AI 與離線讀音相同：{agreed} 字；待處理：{len(issues)} 處。自動核對不等於人工驗證。'
                if review else '離線自動拼音，未作 AI 或人工逐字核對。')
        if issues:
            st.warning(f'仍有 {len(issues)} 處讀音分歧或疑義；PDF 會保留提示，請處理後再作正式閱讀材料。')
        options = dict(readings=tokens, review_note=note, title=title or '我的故事', body=body, targets=targets,
                       corrections=db.pinyin_corrections(), overrides=db.position_corrections(body),
                       highlight=highlight, questions=questions, vocabulary=vocabulary, discussion=discussion)
        signature = hashlib.sha256(repr(options).encode()).hexdigest()
        if st.button('準備三種 PDF', key=key+'_make'):
            exports,errors = {},[]
            with st.spinner('正在排版 PDF…'):
                for version in ('pinyin','chinese','practice'):
                    try:
                        exports[version] = create_pdf(version=version, **options)
                    except ValueError as exc:
                        errors.append(f'{version}: {exc}')
            st.session_state['_pdf_export'] = (signature, exports)
            st.session_state['_pdf_errors'] = errors
        saved = st.session_state.get('_pdf_export')
        if saved and saved[0] == signature:
            for message in st.session_state.get('_pdf_errors',[]):
                st.error(message)
            for version, label in [('pinyin','拼音閱讀'),('chinese','純中文閱讀'),('practice','練習工作紙')]:
                if version not in saved[1]:
                    continue
                st.download_button('下載 '+label, saved[1][version], f'{version}-a4.pdf', 'application/pdf', key=key+'_dl_'+version)
        st.caption('PDF 已嵌入字型，按 A4 原尺寸或 100% 列印。拼音下劃線提示待核對讀音。練習版包含獨立答題頁，長故事會自動分頁。')


def accuracy_panel(db, text, tokens, issues, agreed, review, settings, key):
    unresolved = len(issues) if issues is not None else sum(t.uncertain for t in tokens)
    if review:
        st.info(f'拼音核對：AI 與離線讀音相同 {agreed} 字 · 待處理 {unresolved} 處。自動一致不等於人工驗證。')
    else:
        st.caption(f'已套用擴充詞語字典；離線檢查有 {unresolved} 處可能需要核對。可選擇 AI 第二次核對，集中處理分歧。')
    with st.expander('提高拼音準確度：可選 AI 核對及例外清單'):
        st.caption('按下核對才會將完整正文傳送至 OpenAI，需 API 費用。AI 獨立閱讀句子，再與離線讀音比較；不會自動改寫故事或取代你的讀音修正。')
        st.caption('模型：'+settings.model+'。同一正文及模型的結果會儲存重用；重新核對會再次計費。')
        if not settings.api_key:
            st.caption('尚未設定 API 金鑰。離線詞語規則、例外提示及手動修正保持免費可用。')
        if st.button('重新用 AI 核對拼音（需 API 費用）' if review else '用 AI 核對拼音（需 API 費用）',
                     key=key+'_review', disabled=not settings.api_key):
            try:
                with st.spinner('正在按完整句子核對拼音…'):
                    result = request_review(settings,text)
                db.save_pinyin_review(review_key(text,settings.model),result)
                st.rerun()
            except ReviewError as exc:
                st.error(str(exc))
        if review:
            ti, to = review.get('input_tokens'), review.get('output_tokens')
            cost = review.get('cost')
            st.caption(f'最近核對：輸入 {ti if ti is not None else "未知"} tokens，輸出 {to if to is not None else "未知"} tokens。'+
                       (f'估算 US${cost:.6f}。' if cost is not None else '未設定此模型單價，無法估算費用。'))
            if not issues:
                st.success('沒有未處理的核對例外。無需逐字比對，仍可隨時修正任何讀音。')
            else:
                st.write('只列出分歧及 AI 仍有疑義的位置：')
                for issue in issues:
                    i = issue['index']
                    st.write(f'第 {i+1} 字元：{text[max(0,i-7):i]}【{text[i]}】{text[i+1:i+8]}')
                    st.write(f'目前：{issue["offline"]} · AI 建議：{issue["ai"]} · {issue["reason"]}')
                    if issue['rewrite']:
                        st.caption('可考慮的簡單改寫（未套用）：'+issue['rewrite'])
                    if st.button('採用 AI 讀音：'+issue['ai'],key=f'{key}_accept_{i}'):
                        st.session_state.pop(f'{key}_syllable_{i}',None)
                        db.save_position_correction(text,i,issue['ai'])
                        review.setdefault('acknowledged',{})[str(i)] = issue['ai']
                        db.save_pinyin_review(review_key(text,settings.model),review)
                        st.rerun()
                    if issue['offline'] != '?' and st.button('保留目前讀音並確認此例外',key=f'{key}_keep_{i}'):
                        db.save_position_correction(text,i,issue['offline'])
                        review.setdefault('acknowledged',{})[str(i)] = issue['offline']
                        db.save_pinyin_review(review_key(text,settings.model),review)
                        st.rerun()
            if st.button('移除此正文的 AI 核對記錄',key=key+'_forget_review'):
                db.delete_pinyin_review(review_key(text,settings.model))
                st.rerun()
        st.caption('改寫後請重新核對；新正文不會沿用舊結果。保留或採用讀音是家長的選擇，不代表專業人工認證。完整 SQLite 備份包含核對記錄。')

