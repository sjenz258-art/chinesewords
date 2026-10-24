"""Regenerate the synthetic A4 examples and rendered validation images."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pypdfium2 as pdfium
from chinese_reader.pdf_export import create_pdf

root=Path(__file__).resolve().parent.parent
(root/'samples/pdfs').mkdir(exist_ok=True)
(root/'samples/previews').mkdir(exist_ok=True)
for kind in ('pinyin','chinese','practice'):
    data=create_pdf('小鳥的雨天朋友',(root/'samples/story.txt').read_text(),kind,targets=list('鳥雨朋友'))
    (root/f'samples/pdfs/{kind}.pdf').write_bytes(data)
    doc=pdfium.PdfDocument(data)
    for i,page in enumerate(doc):
        page.render(scale=1.4).to_pil().save(root/f'samples/previews/{kind}-{i+1}.png')
    print(f'{kind}: {len(doc)} A4 page(s)')
