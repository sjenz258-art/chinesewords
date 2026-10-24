# Bundled PDF fonts

- `NotoSansTC-Regular.ttf`: static weight-400 instance of Google Fonts' `ofl/notosanstc/NotoSansTC[wght].ttf`, obtained from https://github.com/google/fonts/tree/main/ofl/notosanstc and instantiated using fontTools `instantiateVariableFont(font, {'wght': 400})`. Full font coverage is retained; ReportLab subsets it into each PDF. Licence: `OFL-NotoSansTC.txt`.
- `DejaVuSans.ttf`: DejaVu Sans from the installed Debian `fonts-dejavu-core` package. Licence and copyright: `LICENSE-DejaVu.txt`. Used for Mandarin Latin tone marks.

These assets are application dependencies and must be included when deploying. Font embedding in generated PDFs is allowed by their bundled licences.
