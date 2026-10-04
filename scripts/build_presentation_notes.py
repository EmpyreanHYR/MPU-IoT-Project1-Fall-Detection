"""Build local bilingual presenter content from the maintained speaker guides."""
from pathlib import Path
import html
import json
import re

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'docs/index.html').read_text()
chinese = (ROOT / 'docs/speaker-notes-zh.md').read_text()
chinese_parts = [block.partition('\n')[2].strip()
                 for block in re.split(r'(?m)^## ', chinese)[1:]]
clean = lambda text: html.unescape(re.sub('<[^>]+>', ' ', text)).strip()
notes = []
for i, match in enumerate(re.finditer(
        r'<section class="slide[^\"]*" id="([^"]+)" data-title="([^"]+)"[\s\S]*?</section>', source)):
    section = match.group(0)
    speech = re.search(r'<aside class="speaker-notes"><h3>Speaker notes · (\d+) seconds</h3><p>([\s\S]*?)</p></aside>', section)
    title = re.search(r'<h[12]>([\s\S]*?)</h[12]>', section)
    notes.append({
        'id': match.group(1), 'label': match.group(2),
        'title': clean(title.group(1)),
        'seconds': int(speech.group(1)) if speech else 0,
        'en': clean(speech.group(2)) if speech else
        'Use this appendix only when answering a relevant question. It is outside the timed twelve-slide talk.',
        'zh': chinese_parts[i] if i < len(chinese_parts) else
        '此页用于答辩，不计入十二页正文的七分钟讲述。回答时明确区分已验证结果、历史记录与未测试范围。',
    })
assert len(notes) == 14 and sum(n['seconds'] for n in notes) == 420
(ROOT / 'docs/assets/presentation-notes.js').write_text(
    'window.FALLGUARD_NOTES = ' + json.dumps(notes, ensure_ascii=False, indent=2) + ';\n')
print('Built 12 timed slides and 2 untimed appendices; total speech budget: 420 seconds')
