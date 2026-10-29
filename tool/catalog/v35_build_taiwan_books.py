#!/usr/bin/env python3
# 閱芽網頁版 v35 的台灣書目產製腳本（原檔 scripts/build-taiwan-books.py，未修改）。
# build_catalog.py 直接載入這裡的整理函式，確保與 v35 的書名、作者、出版者整理規則一致。
"""Build an exact-ISBN index from NCL and Ministry of Culture open data snapshots."""
import csv,hashlib,json,re,sys
from collections import defaultdict
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
HAN=re.compile(r'[\u3400-\u9fff]');KANA=re.compile(r'[\u3040-\u30ff]')
ISBN=re.compile(r'(?<!\d)(?:97[89][-\s]?(?:\d[-\s]?){9}\d|(?:\d[-\s]?){9}[\dXx])(?!\d)')
def isbn_key(value):
 value=re.sub(r'[\s-]','',value).upper()
 if re.fullmatch(r'97[89]\d{10}',value):return value if sum(int(c)*(1 if i%2==0 else 3)for i,c in enumerate(value))%10==0 else None
 if re.fullmatch(r'\d{9}[\dX]',value)and sum((10 if c=='X'else int(c))*(10-i)for i,c in enumerate(value))%11==0:
  value='978'+value[:9];return value+str((-sum(int(c)*(1 if i%2==0 else 3)for i,c in enumerate(value)))%10)
 return None
def clean(value):return re.sub(r'\s+',' ',re.sub(r'[\x00-\x1f]',' ',str(value or''))).strip()
def title(value):return re.sub(r'\s+',' ',clean(value).replace(':;',': ').replace('：;','：').replace(';;',';')).rstrip(' /:;：=').strip()
def publisher(value):
 value=clean(value).replace(':;',':').replace(',;',',')
 if ':'not in value and'：'not in value:return ''
 value=re.split(r'[:：]',value,maxsplit=1)[1].strip();value=re.split(r'[,;，]\s*\[?(?:1[6-9]\d{2}|20\d{2}|民\d|©)',value,maxsplit=1)[0].strip(' [];:,')
 return ''if re.search(r'出版者不詳|出版項不詳|出版項不明|s\.n\.',value,re.I)else value

def language(value,t):
 value=clean(value)
 if re.search(r'中文|繁體|簡體|漢語',value):return 'zh'
 if re.search(r'英文|英語',value):return 'en'
 if re.search(r'日文|日語',value):return 'ja'
 if re.search(r'韓文|韓語',value):return 'ko'
 primary=t.split('=')[0]
 if KANA.search(primary):return 'ja'
 if HAN.search(primary):return 'zh'
 return 'und'

def build(download_dir):
 raw=Path(download_dir);out=ROOT/'dist/data/books';out.mkdir(parents=True,exist_ok=True)
 inputs=json.loads((ROOT/'scripts/taiwan-book-inputs.json').read_text());books={};scores={};sources=[];rows_seen=invalid=0
 for entry in inputs:
  name,url=entry['file'],entry['url'];path=raw/name;rows=0;before=len(books)
  with path.open(encoding='utf-8-sig',newline='')as f:
   records=json.load(f)if name.endswith('.json')else csv.DictReader(f)
   for row in records:
    rows+=1;rows_seen+=1;lang='';origin='ncl'
    if name=='catalog.csv':t=title(row.get('題名'));a=clean(row.get('作者'));p=publisher(row.get('出版項'));isbn=row.get('ISBN','');priority=3
    elif name=='nbinet.csv':t=title(row.get('書名 (245$a$b)'));a=clean(row.get('編著者 (245$c)'));p=publisher(row.get('出版項 (264)')or row.get('出版項 (260)'));isbn=row.get('ISBN (020$a$c)','');priority=3
    elif name=='gpi.json':t=title(row.get('BookTitle'));a=clean(row.get('Creator'));p=clean(row.get('Publisher'));isbn=row.get('ISBN','');lang=row.get('Language','');priority=4;origin='gpi'
    else:t=title(row.get('申請書名')or row.get('書名'));a=clean(row.get('作者'));p=clean(row.get('出版機構')or row.get('出版單位'));isbn=row.get('ISBN','');lang=row.get('作品語文','');priority=2
    if not t:continue
    lang=language(lang,t)
    for match in ISBN.finditer(str(isbn or'')):
     key=isbn_key(match.group())
     if not key:invalid+=1;continue
     score=(lang=='zh'and bool(HAN.search(t)),priority,bool(p),bool(a),min(len(t),100))
     if key not in books or score>scores[key]:
      previous=books.get(key,['','','']);books[key]=[t,a or previous[1],p or previous[2],lang,origin];scores[key]=score
     else:
      if not books[key][1]:books[key][1]=a
      if not books[key][2]:books[key][2]=p
  sources.append({'file':name,'url':url,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'rows':rows,'newIsbns':len(books)-before})
 shards=defaultdict(dict)
 for key,data in sorted(books.items()):shards[f'{int(key[-3:])%128:02x}'][key]=data
 for old in out.glob('[0-9a-f][0-9a-f].json'):old.unlink()
 for key,data in shards.items():(out/(key+'.json')).write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
 today=datetime.now(timezone(timedelta(hours=8))).date().isoformat()
 manifest={'version':'20261019-1','updatedAt':today,'count':len(books),'chineseCount':sum(b[3]=='zh'for b in books.values()),'shards':sorted(shards),'source':'台灣書目索引','sourceLabels':{'ncl':'國家圖書館開放書目','gpi':'文化部政府出版品書目'},'license':'政府資料開放授權條款－第1版','licenseUrl':'https://data.gov.tw/license','coverage':['國家圖書館113年度新增書目（中外文，含較早出版品）','NBINet 115年第2季新增書目（中外文）','臺灣出版新書預告書訊：2025年1月–2026年8月（中外文）','文化部政府出版品資訊網公開書目快照（具有效 ISBN 的歷年及預告出版紀錄）'],'datasets':['https://data.gov.tw/dataset/27311','https://data.gov.tw/dataset/7502','https://data.gov.tw/dataset/6730','https://data.gov.tw/dataset/35215'],'inputRows':rows_seen,'invalidIsbnTokens':invalid,'files':sources}
 (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 print(json.dumps({'count':len(books),'chineseCount':manifest['chineseCount'],'shards':len(shards),'bytes':sum(p.stat().st_size for p in out.glob('*.json')),'inputRows':rows_seen,'newGpiIsbns':sources[-1]['newIsbns'],'atomicHabits':books.get('9789861755267')},ensure_ascii=False))
if __name__=='__main__':build(sys.argv[1])
