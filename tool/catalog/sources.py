#!/usr/bin/env python3
"""台灣書目原始資料：查政府資料開放平臺的最新清單、取得檔案、更新 inputs.json。

    python3 tool/catalog/sources.py update <inputs.json> <下載資料夾>
        查 data.gov.tw API，下載清單上的檔案；新的或內容有變的寫回 inputs.json。
        有變動時在 $GITHUB_OUTPUT 寫 changed=true。
    python3 tool/catalog/sources.py fetch <inputs.json> <下載資料夾>
        確保 inputs.json 列出的每個檔案都在下載資料夾、雜湊相符：
        先找本機，再找本 repo 的 catalog-inputs 發行版（保存的原始檔），最後找原始網址。

資料集（皆依政府資料開放授權條款－第 1 版）：
    6730  臺灣出版新書預告書訊（每月，清單只列最近 12 個月）→ newbooks-YYYY-MM.csv
    27311 國家圖書館年度新增書目 → catalog-民國年.csv
    7502  NBINet 圖書聯合目錄新增書目（每季）→ nbinet-民國年Q季.csv
    35215 政府出版品資訊網書目（整份快照）→ gpi.json
舊月份、舊年度的檔案保留在 inputs.json 與發行版裡，重建時一併使用。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

UA = {'User-Agent': 'Folivra catalog builder (https://patsycyc.github.io/folivra-site/catalog/)'}
ARCHIVE = 'https://github.com/patsycyc/folivra-site/releases/download/catalog-inputs/'
DATASETS = ('6730', '27311', '7502', '35215')


def notice(title: str, message: str, level: str = 'notice') -> None:
    message = message.replace('%', '%25').replace('\r', '').replace('\n', '%0A')
    print(f'::{level} title={title}::{message[:3900]}')


def http_get(url: str, timeout: int = 300) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as res:
        return res.read()


def file_name(dataset: str, label: str) -> str | None:
    """資料集與說明 → inputs.json 的檔名；認不得回傳 None。"""
    if dataset == '6730':
        m = re.search(r'(\d{2,3})年(\d{1,2})月', label)
        return f'newbooks-{int(m.group(1)) + 1911}-{int(m.group(2)):02d}.csv' if m else None
    if dataset == '27311':
        m = re.search(r'(\d{2,3})年度', label)
        return f'catalog-{m.group(1)}.csv' if m else None
    if dataset == '7502':
        m = re.search(r'(\d{2,3})年第(\d)季', label)
        return f'nbinet-{m.group(1)}Q{m.group(2)}.csv' if m else None
    if dataset == '35215':
        return 'gpi.json'
    return None


def listed() -> list[dict]:
    out = []
    for ds in DATASETS:
        data = json.loads(http_get(f'https://data.gov.tw/api/v2/rest/dataset/{ds}', 60))
        for d in data.get('result', data).get('distribution', []):
            label = d.get('resourceDescription') or ''
            name = file_name(ds, label)
            if not name:
                notice('認不得的資料', f'{ds}：{label}', 'warning')
                continue
            out.append({'file': name, 'dataset': ds, 'label': label, 'url': d.get('resourceDownloadUrl')})
    return out


def update(inputs_file: Path, raw: Path) -> int:
    inputs = json.loads(inputs_file.read_text(encoding='utf-8'))
    by_name = {e['file']: e for e in inputs}
    raw.mkdir(parents=True, exist_ok=True)
    changes = []
    for item in listed():
        try:
            data = http_get(item['url'])
        except Exception as e:  # noqa: BLE001
            notice('下載失敗', f"{item['file']}：{e!r}", 'warning')
            continue
        sha = hashlib.sha256(data).hexdigest()
        old = by_name.get(item['file'])
        if old and old['sha256'] == sha:
            continue
        (raw / item['file']).write_bytes(data)
        entry = {**item, 'sha256': sha}
        if old:
            old.update(entry)
            changes.append(f"更新 {item['file']}（{len(data):,} bytes）")
        else:
            inputs.append(entry)
            by_name[item['file']] = entry
            changes.append(f"新增 {item['file']}（{len(data):,} bytes）")
    if changes:
        inputs.sort(key=lambda e: e['file'])
        inputs_file.write_text(json.dumps(inputs, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    notice('書目來源', '\n'.join(changes) or '沒有新資料')
    out = os.environ.get('GITHUB_OUTPUT')
    if out:
        with open(out, 'a', encoding='utf-8') as f:
            f.write(f"changed={'true' if changes else 'false'}\n")
            f.write(f"changes={'；'.join(changes)}\n")
    return 0


def fetch(inputs_file: Path, raw: Path) -> int:
    raw.mkdir(parents=True, exist_ok=True)
    missing = []
    for e in json.loads(inputs_file.read_text(encoding='utf-8')):
        path = raw / e['file']
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == e['sha256']:
            continue
        for url in (ARCHIVE + e['file'], e['url']):
            try:
                data = http_get(url)
            except Exception:  # noqa: BLE001
                continue
            if hashlib.sha256(data).hexdigest() == e['sha256']:
                path.write_bytes(data)
                break
        else:
            missing.append(e['file'])
    if missing:
        notice('找不到原始檔', '、'.join(missing), 'error')
        return 1
    return 0


if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] not in ('update', 'fetch'):
        sys.exit(__doc__)
    cmd = update if sys.argv[1] == 'update' else fetch
    sys.exit(cmd(Path(sys.argv[2]), Path(sys.argv[3])))
