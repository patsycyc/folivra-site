"""書目作者欄位清理（離線書目包與後端共用）。

國圖、文化部的書目常帶圖書館編目格式的雜訊，例如：
    'Oliver, Jamie (Jamie Trevor), 1975- author. https://isni.org/... (Purchase)'
    '劉宸君, 1998-2017, 文字作者'
清理後分別為 'Jamie Oliver'、'劉宸君'。
中文常見的責任標示（例如「東山彰良作；王靜怡譯」）是有用資訊，保留不動，只統一分隔符號。
"""
from __future__ import annotations

import re

_HAN = re.compile(r'[㐀-鿿぀-ヿ가-힯]')
_URL = re.compile(r'https?:\S*')
_ACQ = re.compile(r'\((?:Gift|Purchase|Exchange|Donation|Deposit|贈書|購買|交換)\)', re.I)
_OPEN_PAREN = re.compile(r'\s*\([^()]*$')
_PREFIX = re.compile(r'^(?:authors?|editors?|writers?)\s+(?=\S)', re.I)
_REL = (r'(?:author|editor|illustrator|translator|compiler|artist|photographer|issuing body|contributor'
        r'|writer of (?:introduction|preface|foreword|afterword|added commentary)|narrator|adapter'
        r'|cartographer|designer|creator|director|performer|host institution|organizer|publisher|sponsor'
        r'|cover designer|book designer|calligrapher|interviewer|interviewee|hono(?:u)?ree|dedicatee'
        r'|researcher|copyright holder|composer'
        r'|文字作者|作者|藝術創作者|繪者|繪圖者|插畫者|插圖者|譯者|翻譯者|編者|編譯者|主編|編輯|演講者'
        r'|攝影者|口述者|改編者|作曲者|校訂者|審訂者)')
_RELS = re.compile(r'(?:,\s*|\s+)' + _REL + r'(?:\s*(?:,|and|&|、)\s*' + _REL + r')*\.?\s*$', re.I)
_DATES = re.compile(r',?\s*(?:\d{3,4}\??-(?:\d{3,4}\??)?|active \d{3,4}(?:-\d{3,4})?)\s*$')
_FULLER = re.compile(r'\s*\([^()]*\)\s*$')
_ROLE_ONLY = re.compile(r'^' + _REL + r'$', re.I)


def _strip_end(p: str) -> str:
    p = p.strip().rstrip(',').strip()
    # 結尾句點：縮寫（J.、Jr.、St.）保留，其餘去掉
    if p.endswith('.') and not re.search(r'(?:\b\w|Jr|Sr|St)\.$', p):
        p = p[:-1].rstrip()
    return p


def _clean_part(p: str) -> str:
    p = _PREFIX.sub('', p.strip())
    marc = False
    for _ in range(4):
        q = _strip_end(_DATES.sub('', _RELS.sub('', p).strip()))
        if q != p.strip():
            marc = True
        if marc:
            q = _FULLER.sub('', q).strip()
        if q == p:
            break
        p = q
    if _ROLE_ONLY.match(p):
        return ''
    if _HAN.search(p):
        return p
    m = re.fullmatch(r'([^,]+),\s*([^,]+)', p)
    if m and marc and not re.search(r'\d', p):
        p = f'{m[2].strip()} {m[1].strip()}'
    return p


def clean_author(raw: str | None) -> str:
    s = _URL.sub('', raw or '')
    s = _ACQ.sub('', s)
    s = _OPEN_PAREN.sub('', s)
    s = re.sub(r'\s+', ' ', s).strip()
    parts = [x for x in (_clean_part(x) for x in re.split(r'\s*;\s*', s)) if x]
    sep = '；' if any(_HAN.search(x) for x in parts) else '; '
    return sep.join(parts)
