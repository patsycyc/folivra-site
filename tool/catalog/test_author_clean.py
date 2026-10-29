"""執行：python3 tool/catalog/test_author_clean.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from author_clean import clean_author  # noqa: E402

CASES = [
    ('Oliver, Jamie (Jamie Trevor), 1975- author. https://isni.org/isni/0000000120185514 (Purchase)', 'Jamie Oliver'),
    ('Fried, Jean J., author.', 'Jean J. Fried'),
    ('Ritter, G. X., author. (Purchase)', 'G. X. Ritter'),
    ('Farina, Katy, author, illustrator. (Purchase)', 'Katy Farina'),
    ('McNulty, Keith.', 'Keith McNulty'),
    ('Spence, Lewis, 1874-1955, author. (Gi', 'Lewis Spence'),
    ('Li, Shizhen, 1518-1593, author https:', 'Shizhen Li'),
    ('author John Steinbeck', 'John Steinbeck'),
    ('writers Evonnie Chiang, Jamie Li', 'Evonnie Chiang, Jamie Li'),
    ('劉宸君, 1998-2017, 文字作者', '劉宸君'),
    ('霍爾 (Hall, Edith), 1959- 文字作者', '霍爾'),
    ('釋達義, 1967- 文字作者, 演講者', '釋達義'),
    ('麥羅斯基 (McCloskey, Robert), 1914-2003, 文字作者, 藝術創作者', '麥羅斯基'),
    ('菲力普斯 (Phillips, Joan), 文字作者 (贈書)', '菲力普斯'),
    ('東山彰良作 ; 王靜怡譯', '東山彰良作；王靜怡譯'),
    ('張明偉, 蔡聖偉, 陳文貴等合著', '張明偉, 蔡聖偉, 陳文貴等合著'),
    ('古龍著', '古龍著'),
    ('文字作者', ''),
    ('', ''),
    (None, ''),
]

failed = 0
for raw, want in CASES:
    got = clean_author(raw)
    if got != want:
        failed += 1
        print(f'FAIL {raw!r}\n  got  {got!r}\n  want {want!r}')
print(f'{len(CASES) - failed}/{len(CASES)} passed')
sys.exit(1 if failed else 0)
