"""A4 canvas typesetting: the exact same reading tokens as the web interface.

Each pinyin/character pair shares a measured cell centre. Fonts are embedded;
unsupported glyphs raise a useful error rather than silently printing tofu.
"""
from io import BytesIO
from pathlib import Path
from functools import lru_cache
from dataclasses import replace
import re
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from fontTools.ttLib import TTFont as InspectFont
from .analysis import is_han
from .pinyin_engine import annotate

FONT_DIR = Path(__file__).resolve().parent.parent / 'assets' / 'fonts'
VERSIONS = {'pinyin': '拼音閱讀', 'chinese': '中文閱讀', 'practice': '練習工作紙'}


@lru_cache(maxsize=1)
def load_fonts():
    cmaps = {}
    for alias, filename in [('Chinese', 'NotoSansTC-Regular.ttf'), ('Pinyin', 'DejaVuSans.ttf')]:
        path = FONT_DIR / filename
        pdfmetrics.registerFont(TTFont(alias, str(path)))
        with InspectFont(path) as font:
            cmaps[alias] = set(font.getBestCmap())
    return cmaps


def font_for(char):
    cmaps = load_fonts()
    return 'Chinese' if ord(char) in cmaps['Chinese'] else 'Pinyin'


def ensure_glyphs(text):
    cmaps = load_fonts()
    supported = cmaps['Chinese'] | cmaps['Pinyin']
    missing = sorted(c for c in set(text) if not c.isspace() and ord(c) not in supported)
    if missing:
        raise ValueError('PDF 字型不支援以下字元，請修改或移除：' + ''.join(missing))


def default_questions(body):
    sentences = [s.strip().strip('「」『』“”') for s in re.split('[。！？\n]+', body) if s.strip().strip('「」『』“”')]
    chosen = [sentences[i] for i in sorted({0, len(sentences)//2, len(sentences)-1})] if sentences else []
    return [f'讀「{s}」。這句說了甚麼事？' for s in chosen][:3]


class Sheet:
    def __init__(self, stream, title, subtitle):
        self.canvas = canvas.Canvas(stream, pagesize=A4, pageCompression=1)
        self.canvas.setTitle(title)
        self.canvas.setAuthor('小小故事園')
        self.width, self.height = A4
        self.left, self.right, self.bottom = 48, self.width-48, 48
        self.y = self.height-52
        self.page = 1
        self.canvas.setFillColorRGB(.12,.22,.2)
        self.text(title, 20, line_height=29)
        self.text(subtitle, 9, line_height=18)
        self.y -= 32

    def footer(self):
        self.canvas.setFont('Pinyin', 8)
        self.canvas.setFillColorRGB(.4,.4,.4)
        self.canvas.drawCentredString(self.width/2, 25, str(self.page))

    def new_page(self):
        self.footer()
        self.canvas.showPage()
        self.page += 1
        self.y = self.height-52

    def room(self, height):
        if self.y-height < self.bottom:
            self.new_page()

    def text(self, text, size=12, line_height=22):
        x = self.left
        self.room(line_height)
        self.canvas.setFillColorRGB(.12,.18,.16)
        normalised = text.replace('\r\n','\n').expandtabs(4)
        normalised = ''.join('\n' if c in '\r\n\v\f\x85\u2028\u2029' else ' ' if c.isspace() else c for c in normalised)
        for char in normalised:
            font = font_for(char)
            width = pdfmetrics.stringWidth(char, font, size)
            if char == '\n' or x+width > self.right:
                self.y -= line_height
                self.room(line_height)
                x = self.left
                if char == '\n':
                    continue
            self.canvas.setFillColorRGB(.12,.18,.16)
            self.canvas.setFont(font, size)
            self.canvas.drawString(x, self.y, char)
            x += width
        self.y -= line_height

    def story(self, tokens, with_pinyin=True, targets=(), highlight=False):
        size, py_size = 18, 8.5
        line_height = 43 if with_pinyin else 33
        x = self.left
        closing = '，。！？、；：）》」』】”’'
        def width(t):
            if t.char == '\n':
                return 0
            base = max(22, pdfmetrics.stringWidth(t.char, font_for(t.char), size)+4)
            return max(base, pdfmetrics.stringWidth(t.pinyin,'Pinyin',py_size)+5) if with_pinyin else base
        # Keep entire closing-punctuation runs with the preceding character,
        # and opening quotes with the next character, rather than looking ahead once.
        units = []
        pending = []
        opening = '（《「『【“‘'
        for i, token in enumerate(tokens):
            if token.char == '\r' and i+1 < len(tokens) and tokens[i+1].char == '\n':
                continue
            if token.char in '\r\n\v\f\x85\u2028\u2029':
                if pending:
                    units.append(pending)
                    pending = []
                units.append([replace(token,char='\n')])
            elif token.char in closing and units and units[-1][0].char != '\n' and not pending:
                units[-1].append(token)
            elif token.char in opening:
                pending.append(token)
            else:
                visible = replace(token,char=' ') if token.char.isspace() else token
                units.append(pending+[visible])
                pending = []
        if pending:
            units.append(pending)
        for unit in units:
            if unit[0].char == '\n':
                self.y -= line_height
                self.room(line_height)
                x = self.left
                continue
            if x+sum(width(t) for t in unit) > self.right and x > self.left:
                self.y -= line_height
                self.room(line_height)
                x = self.left
            for token in unit:
                w = width(token)
                if x+w > self.right:  # Pathological long punctuation runs still fit the page.
                    self.y -= line_height
                    self.room(line_height)
                    x = self.left
                self.room(line_height)
                centre = x+w/2
                if highlight and token.char in targets:
                    self.canvas.setFillColorRGB(1,.93,.78)
                    self.canvas.rect(x, self.y-4, w, 24, fill=1, stroke=0)
                self.canvas.setFillColorRGB(.12,.18,.16)
                self.canvas.setFont(font_for(token.char), size)
                self.canvas.drawCentredString(centre, self.y, token.char)
                if with_pinyin and token.pinyin:
                    self.canvas.setFont('Pinyin', py_size)
                    self.canvas.setFillColorRGB(.3,.3,.3)
                    self.canvas.drawCentredString(centre, self.y+23, token.pinyin)
                    if token.uncertain:
                        self.canvas.setStrokeColorRGB(.3,.3,.3)
                        self.canvas.setLineWidth(.4)
                        self.canvas.line(centre-w/2+2,self.y+21,centre+w/2-2,self.y+21)
                x += w
        self.y -= line_height

    def answer_lines(self, count=2):
        self.room(count*25)
        self.canvas.setStrokeColorRGB(.7,.7,.7)
        self.canvas.setLineWidth(.5)
        for _ in range(count):
            self.y -= 25
            self.canvas.line(self.left,self.y,self.right,self.y)
        self.y -= 20

    def finish(self):
        self.footer()
        self.canvas.save()


def create_pdf(title, body, version='pinyin', targets=(), corrections=None,
               overrides=None, highlight=True, questions=None, vocabulary=None, discussion='', readings=None, review_note=''):
    if version not in VERSIONS:
        raise ValueError('Unknown worksheet version')
    tokens = readings if readings is not None else annotate(body, corrections, overrides=overrides)
    if ''.join(t.char for t in tokens) != body:
        raise ValueError('Pinyin and text do not align')
    questions = default_questions(body) if questions is None else questions
    vocabulary = ''.join(dict.fromkeys(targets)) if vocabulary is None else vocabulary
    printed = title+body
    if version == 'pinyin':
        printed += review_note+''.join(t.pinyin for t in tokens)
    elif version == 'practice':
        printed += vocabulary+''.join(questions)+discussion
    ensure_glyphs(printed)
    output = BytesIO()
    sheet = Sheet(output,title,VERSIONS[version]+' · 姓名：____________  日期：____________')
    sheet.story(tokens, version == 'pinyin', targets, highlight and version != 'pinyin')
    if version == 'pinyin' and any(t.uncertain for t in tokens):
        sheet.text('拼音下劃線表示尚待核對（多音字或核對結果不同）。',9,18)
    if version == 'pinyin' and review_note:
        sheet.text(review_note,9,18)
    if version == 'practice':
        sheet.new_page()
        sheet.text('詞語與閱讀練習',18,30)
        sheet.text('目標詞語（讀一讀，再抄寫）：',12,24)
        sheet.text(vocabulary or '家長可在匯出前加入目標詞語。',16,28)
        sheet.answer_lines()
        sheet.text('閱讀問題（由家長核對；預設為句意重述練習）：',11,24)
        for i, question in enumerate(questions,1):
            sheet.room(140)
            sheet.text(f'{i}. {question}',12,23)
            sheet.answer_lines()
        if discussion:
            sheet.room(100)
            sheet.text('一起聊聊：'+discussion,12,23)
            sheet.answer_lines()
    sheet.finish()
    return output.getvalue()
