#!/usr/bin/env python3
"""從國圖、文化部的原始開放資料重建台灣書目分片（#56），並保留分類線索（#57）。

書名、作者、出版者、語言的整理沿用 v35 的 build-taiwan-books.py（v35_build_taiwan_books.py，
直接載入它的函式，選擇同一 ISBN 多筆資料的規則也相同），再套用作者欄位清理（author_clean.py）。

輸入依 inputs.json 的檔名分類：catalog-*（國圖年度新增）、nbinet-*（NBINet 新增）、
newbooks-*（新書預告，依月份）、gpi.json（政府出版品），依此順序處理（與 v35 相同）。

用法：
    python3 tool/catalog/build_catalog.py <inputs.json> <下載資料夾> <輸出資料夾> [--version 版本]

輸出（格式 2，與格式 1 相容：前 5 欄不變，只多 2 欄）：
    <輸出>/000.json … 3ff.json   {isbn13: [書名, 作者, 出版者, 語言, 來源, 分類號, 主題]}
    <輸出>/manifest.json
分類號：新書預告的「分類號」或 NBINet 索書號中的中文圖書分類號（例如 863.57），沒有則為空字串。
主題：新書預告的「建議上架分類／常用分類」，其次「圖書主題」，或政府出版品的 Subject；沒有則為空字串。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from author_clean import clean_author  # noqa: E402

_spec = importlib.util.spec_from_file_location('v35_books', HERE / 'v35_build_taiwan_books.py')
v35 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v35)

FORMAT = 2
SHARDS = 1024


def shard_of(isbn13: str) -> str:
    """App 端 catalogShard() 用同一條規則：ISBN-13 末 4 碼 % 1024，三位小寫十六進位。"""
    return f'{int(isbn13[-4:]) % SHARDS:03x}'


_KINDS = ('catalog', 'nbinet', 'newbooks', 'gpi')


def kind_of(name: str) -> str:
    for k in _KINDS:
        if name.startswith(k):
            return k
    raise SystemExit(f'不認得的輸入檔：{name}')


def ordered(inputs: list[dict]) -> list[dict]:
    """依種類（國圖、NBINet、新書預告、政府出版品）排序，同種類依檔名（年度、季、月份）。"""
    return sorted(inputs, key=lambda e: (_KINDS.index(kind_of(e['file'])), e['file']))
_CLASS = re.compile(r'^\d{3}(?:\.\d+)?$')
_CLASS_IN = re.compile(r'(?<![\d.])\d{3}(?:\.\d+)?(?![\d])')


def class_from_field(value: str) -> str:
    """新書預告「分類號」欄：取第一個中文圖書分類號。"""
    m = _CLASS_IN.search(value or '')
    return m.group() if m else ''


def class_from_holdings(value: str) -> str:
    """NBINet「館藏地及索書號」：館名; 分類號; 書號; 館名; …，取第一個中文圖書分類號（略過美國國會分類號）。"""
    for part in (value or '').split(';'):
        part = part.strip()
        if _CLASS.match(part):
            return part
    return ''


def read_rows(path: Path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        if path.name.endswith('.json'):
            yield from json.load(f)
        else:
            yield from csv.DictReader(f)


def build(inputs_file: Path, raw: Path, out: Path, version: str) -> dict:
    inputs = ordered(json.loads(inputs_file.read_text(encoding='utf-8')))
    books: dict[str, list[str]] = {}
    scores: dict[str, tuple] = {}
    class_no: dict[str, str] = {}
    topic: dict[str, str] = {}
    sources = []
    rows_seen = invalid = 0
    for entry in inputs:
        name = entry['file']
        path = raw / name
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry['sha256']:
            raise SystemExit(f'{name} 的雜湊與 inputs.json 不同：{digest}')
        rows = 0
        before = len(books)
        for row in read_rows(path):
            rows += 1
            rows_seen += 1
            lang = ''
            origin = 'ncl'
            cls = hint = ''
            # 以下欄位對應與 v35 build-taiwan-books.py 相同。
            kind = kind_of(name)
            if kind == 'catalog':
                t = v35.title(row.get('題名')); a = v35.clean(row.get('作者')); p = v35.publisher(row.get('出版項'))
                isbn = row.get('ISBN', ''); priority = 3
            elif kind == 'nbinet':
                t = v35.title(row.get('書名 (245$a$b)')); a = v35.clean(row.get('編著者 (245$c)'))
                p = v35.publisher(row.get('出版項 (264)') or row.get('出版項 (260)'))
                isbn = row.get('ISBN (020$a$c)', ''); priority = 3
                cls = class_from_holdings(row.get('館藏地及索書號(949$a$d$e)', ''))
            elif kind == 'gpi':
                t = v35.title(row.get('BookTitle')); a = v35.clean(row.get('Creator')); p = v35.clean(row.get('Publisher'))
                isbn = row.get('ISBN', ''); lang = row.get('Language', ''); priority = 4; origin = 'gpi'
                subject = v35.clean(row.get('Subject'))
                hint = '' if subject == '無' else subject
            else:
                t = v35.title(row.get('申請書名') or row.get('書名')); a = v35.clean(row.get('作者'))
                p = v35.clean(row.get('出版機構') or row.get('出版單位'))
                isbn = row.get('ISBN', ''); lang = row.get('作品語文', ''); priority = 2
                cls = class_from_field(row.get('分類號', ''))
                hint = v35.clean(row.get('建議上架分類') or row.get('常用分類') or row.get('圖書主題'))
            if not t:
                continue
            lang = v35.language(lang, t)
            for match in v35.ISBN.finditer(str(isbn or '')):
                key = v35.isbn_key(match.group())
                if not key:
                    invalid += 1
                    continue
                score = (lang == 'zh' and bool(v35.HAN.search(t)), priority, bool(p), bool(a), min(len(t), 100))
                if key not in books or score > scores[key]:
                    previous = books.get(key, ['', '', ''])
                    books[key] = [t, a or previous[1], p or previous[2], lang, origin]
                    scores[key] = score
                else:
                    if not books[key][1]:
                        books[key][1] = a
                    if not books[key][2]:
                        books[key][2] = p
                # 分類線索：第一個有值的來源（依 inputs.json 順序）。
                if cls and not class_no.get(key):
                    class_no[key] = cls
                if hint and not topic.get(key):
                    topic[key] = hint
        sources.append({'file': name, 'url': entry['url'], 'sha256': digest, 'rows': rows, 'newIsbns': len(books) - before})

    shards: dict[str, dict] = defaultdict(dict)
    for key in sorted(books):
        t, a, p, lang, origin = books[key]
        shards[shard_of(key)][key] = [t, clean_author(a), p, lang, origin, class_no.get(key, ''), topic.get(key, '')]
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob('*.json'):
        old.unlink()
    for key in sorted(shards):
        (out / f'{key}.json').write_text(json.dumps(shards[key], ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    manifest = {
        'format': FORMAT,
        'version': version,
        'builtAt': datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
        'count': len(books),
        'chineseCount': sum(b[3] == 'zh' for b in books.values()),
        'withClassNo': len(class_no),
        'withTopic': len(topic),
        'shardCount': SHARDS,
        'record': ['title', 'author', 'publisher', 'language', 'origin', 'classNo', 'topic'],
        'sourceLabels': {'ncl': '國家圖書館開放書目', 'gpi': '文化部政府出版品書目'},
        'license': '政府資料開放授權條款－第1版',
        'licenseUrl': 'https://data.gov.tw/license',
        'datasets': ['https://data.gov.tw/dataset/27311', 'https://data.gov.tw/dataset/7502',
                     'https://data.gov.tw/dataset/6730', 'https://data.gov.tw/dataset/35215'],
        'inputRows': rows_seen,
        'invalidIsbnTokens': invalid,
        'files': sources,
    }
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return {k: manifest[k] for k in ('count', 'chineseCount', 'withClassNo', 'withTopic', 'inputRows', 'invalidIsbnTokens')}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('inputs')
    ap.add_argument('raw')
    ap.add_argument('out')
    ap.add_argument('--version', default=datetime.now(timezone(timedelta(hours=8))).strftime('%Y%m%d-1'))
    args = ap.parse_args()
    print(json.dumps(build(Path(args.inputs), Path(args.raw), Path(args.out), args.version), ensure_ascii=False))
