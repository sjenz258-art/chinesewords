from html import escape
from .pinyin_engine import annotate

# Small, explicit offline glossary; unknown words are never assigned invented meanings.
MEANINGS = {'小鳥': '小型的鳥。', '朋友': '彼此喜歡、互相關心的人。',
            '長大': '年紀增加，身體也慢慢成長。', '長短': '長和短，或長度的比較。',
            '音樂': '由聲音、節奏和旋律組成的藝術。', '快樂': '開心、愉快。',
            '雨': '從雲中落下的水滴。', '家': '與家人一起生活的地方。',
            '幫助': '替別人做事，讓困難減少。', '彩虹': '雨後天空中有多種顏色的弧形光帶。'}


def story_html(text, mastered, learning, font_size=30, highlight=True,
               mode='chinese', readings=None):
    if mode not in ('chinese', 'pinyin', 'tap'):
        raise ValueError('Unknown reading mode')
    tokens = readings if readings is not None else annotate(text)
    if ''.join(t.char for t in tokens) != text:
        raise ValueError('Pinyin and text must align exactly')
    output = []
    for index, token in enumerate(tokens):
        c = token.char
        if c == '\r' and index+1 < len(tokens) and tokens[index+1].char == '\n':
            continue
        if c in '\r\n\v\f\x85\u2028\u2029':
            output.append('<br>')
            continue
        category = 'mastered' if c in mastered else 'learning' if c in learning else 'unfamiliar'
        category = category if highlight else 'plain'
        if not token.pinyin:
            c = ' ' if c.isspace() else c
            punctuation = f'<span class="{category}">{escape(c)}</span>'
            if c in '，。！？、；：）》」』】”’' and output and output[-1] != '<br>':
                output[-1] = '<span class="reading-unit">' + output[-1] + punctuation + '</span>'
            else:
                output.append(punctuation)
            continue
        meaning = MEANINGS.get(token.word, MEANINGS.get(c, '小字典未收錄；請家長一起查詞典。'))
        note = ' · 讀音待核對' if token.uncertain else ''
        output.append(f'<span class="{category}"><details class="reading-token" name="story-pronunciation"><summary aria-label="{escape(c+": "+token.pinyin+note, quote=True)}">'
                      f'<ruby class="{"uncertain" if token.uncertain else ""}">{escape(c)}<rt>{escape(token.pinyin)}</rt></ruby></summary>'
                      f'<span class="word-tip">{escape(token.word)} · {escape(token.pinyin+note)}<br>{escape(meaning)}</span></details></span>')
    return f'<div class="story mode-{mode}" style="font-size:{int(font_size)}px">{"".join(output)}</div>'


CSS = '''<style>
.story {font-family:"PingFang TC","Microsoft JhengHei","Noto Sans TC",sans-serif;
line-height:2.8; letter-spacing:.04em; overflow-wrap:anywhere; padding:1rem;
background:#fffefb; border-radius:16px; border:1px solid #e0e8df;}
.mastered {color:#21664a;} .learning {color:#9b4d00; background:#fff0d6; border-radius:3px;}
.unfamiliar {color:#666;} .plain {color:#233d38;}
.story .reading-unit {display:inline-block;white-space:nowrap;}
.story ruby {ruby-position:over; ruby-align:center;}
.story rt {font-family:Arial,sans-serif;font-size:.38em;letter-spacing:0;color:#45504b;}
.story .uncertain {text-decoration:underline dotted #9b4d00;text-underline-offset:.15em;}
.story .reading-token {display:inline-block;position:relative;vertical-align:baseline;}
.story summary {display:inline-block;list-style:none;cursor:pointer;min-width:1.25em;text-align:center;}
.story summary::-webkit-details-marker {display:none;}
.story summary:focus-visible {outline:2px solid #267566;}
.story .word-tip {position:absolute;z-index:10;top:100%;left:0;width:210px;max-width:65vw;
background:#fff9e9;color:#233d38;border:1px solid #abbcaf;border-radius:8px;padding:8px;
font-size:14px;line-height:1.6;letter-spacing:0;box-shadow:0 2px 8px #0002;}
.story .reading-token:not([open])>.word-tip {display:none;}
.mode-chinese rt {display:none;} .mode-tap rt {visibility:hidden;}
.mode-tap .reading-token[open] rt {visibility:visible;}
.stButton button {min-height:44px;} [data-testid="stMetricValue"] {font-size:1.6rem;}
@media(max-width:600px){.story .word-tip{position:fixed;top:auto;bottom:1rem;left:1rem;right:1rem;width:auto;max-width:none;}.block-container{padding:1rem .8rem 3rem;} .story{padding:.6rem;}}
</style>'''
