#!/usr/bin/env python3
"""比對重建的書目分片與目前發布的分片（前 5 欄：書名、作者、出版者、語言、來源）。

用法：python3 tool/catalog/compare_shards.py <目前的分片資料夾> <重建的分片資料夾>
結果以 CI 註記輸出；前 5 欄有任何不同就以結束碼 1 結束。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def notice(title: str, message: str, level: str = 'notice') -> None:
    message = message.replace('%', '%25').replace('\r', '').replace('\n', '%0A')
    print(f'::{level} title={title}::{message[:3900]}')


def load(folder: Path) -> dict[str, list]:
    books: dict[str, list] = {}
    for f in sorted(folder.glob('[0-9a-f][0-9a-f][0-9a-f].json')):
        books.update(json.loads(f.read_text(encoding='utf-8')))
    return books


def main(old_dir: str, new_dir: str) -> int:
    old, new = load(Path(old_dir)), load(Path(new_dir))
    missing = sorted(set(old) - set(new))
    added = sorted(set(new) - set(old))
    fields = ['書名', '作者', '出版者', '語言', '來源']
    diff = Counter()
    samples = []
    for key in sorted(set(old) & set(new)):
        for i, name in enumerate(fields):
            if old[key][i] != new[key][i]:
                diff[name] += 1
                if len(samples) < 12:
                    samples.append(f'{key} {name}：{old[key][i]!r} → {new[key][i]!r}')
    same = not missing and not added and not diff
    notice('書目重建比對', f'目前 {len(old):,} 筆，重建 {len(new):,} 筆；少了 {len(missing):,}、多了 {len(added):,}；'
           f'前 5 欄不同：{dict(diff) or "無"}\n例：{samples}\n少了：{missing[:10]}\n多了：{added[:10]}',
           'notice' if same else 'warning')
    cls = sum(bool(r[5]) for r in new.values() if len(r) > 5)
    topic = sum(bool(r[6]) for r in new.values() if len(r) > 6)
    either = sum(bool(r[5]) or bool(r[6]) for r in new.values() if len(r) > 6)
    zh = [r for r in new.values() if r[3] == 'zh']
    zh_either = sum(bool(r[5]) or bool(r[6]) for r in zh)
    notice('分類線索', f'有分類號 {cls:,}（{cls / len(new):.1%}）、有主題 {topic:,}（{topic / len(new):.1%}）、'
           f'至少一項 {either:,}（{either / len(new):.1%}）；中文書 {len(zh):,} 筆中至少一項 {zh_either:,}（{zh_either / max(len(zh), 1):.1%}）')
    return 0 if same else 1


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2]))
