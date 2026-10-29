"""書目重建的測試：python3 tool/catalog/test_build_catalog.py"""
import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_catalog as bc  # noqa: E402


class ClassNo(unittest.TestCase):
    def test_holdings(self):
        self.assertEqual(bc.class_from_holdings('臺灣大學圖書館; 935; 1024-1 2017'), '935')
        self.assertEqual(bc.class_from_holdings('淡江大學; 548.61; 8344; 國家圖書館; 008; 8346:43'), '548.61')
        self.assertEqual(bc.class_from_holdings('淡江大學覺生紀念圖書館; PN1997.2; .J87742 2025'), '')
        self.assertEqual(bc.class_from_holdings(''), '')

    def test_field(self):
        self.assertEqual(bc.class_from_field('957.9'), '957.9')
        self.assertEqual(bc.class_from_field(' 863.57 '), '863.57')
        self.assertEqual(bc.class_from_field('1024'), '')
        self.assertEqual(bc.class_from_field(''), '')


class Order(unittest.TestCase):
    def test_kinds_in_v35_order(self):
        files = ['gpi.json', 'newbooks-2026-01.csv', 'nbinet-115Q2.csv', 'newbooks-2025-12.csv', 'catalog-113.csv',
                 'catalog-114.csv', 'nbinet-115Q3.csv']
        got = [e['file'] for e in bc.ordered([{'file': f} for f in files])]
        self.assertEqual(got, ['catalog-113.csv', 'catalog-114.csv', 'nbinet-115Q2.csv', 'nbinet-115Q3.csv',
                               'newbooks-2025-12.csv', 'newbooks-2026-01.csv', 'gpi.json'])

    def test_shard_rule(self):
        self.assertEqual(bc.shard_of('9789861755267'), f'{5267 % 1024:03x}')
        self.assertEqual(bc.shard_of('9780000001024'), '000')


class Build(unittest.TestCase):
    def test_merges_sources_and_keeps_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp) / 'raw'
            raw.mkdir()
            nb = raw / 'newbooks-2025-01.csv'
            with nb.open('w', encoding='utf-8', newline='') as f:
                w = csv.DictWriter(f, ['申請書名', '作者', '出版機構', '分類號', 'ISBN', '作品語文', '建議上架分類', '圖書主題'])
                w.writeheader()
                w.writerow({'申請書名': '原子習慣', '作者': '克利爾, 作者', '出版機構': '方智', '分類號': '177.2',
                            'ISBN': '9789861755267', '作品語文': '繁體中文', '建議上架分類': '心理勵志', '圖書主題': '哲學'})
                w.writerow({'申請書名': '傀儡屍', '作者': '娜歐米作', '出版機構': '笭菁', '分類號': '',
                            'ISBN': '978-626-7472-42-2', '作品語文': '繁體中文', '建議上架分類': '', '圖書主題': '語言/文學'})
            gpi = raw / 'gpi.json'
            gpi.write_text(json.dumps([{'BookTitle': '統計年報', 'Creator': '主計總處', 'Publisher': '主計總處',
                                        'ISBN': '9789570000000', 'Language': '中文', 'Subject': '無'}],
                                      ensure_ascii=False), encoding='utf-8')
            inputs = Path(tmp) / 'inputs.json'
            inputs.write_text(json.dumps([
                {'file': p.name, 'url': 'https://example/' + p.name, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in (nb, gpi)
            ]), encoding='utf-8')
            out = Path(tmp) / 'out'
            result = bc.build(inputs, raw, out, 'test-2')
            self.assertEqual((result['count'], result['invalidIsbnTokens']), (2, 1))
            books = {}
            for f in out.glob('[0-9a-f][0-9a-f][0-9a-f].json'):
                books.update(json.loads(f.read_text(encoding='utf-8')))
            self.assertEqual(books['9789861755267'], ['原子習慣', '克利爾', '方智', 'zh', 'ncl', '177.2', '心理勵志'])
            self.assertEqual(books['9786267472422'][5:], ['', '語言/文學'])
            manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
            self.assertEqual((manifest['format'], manifest['version'], manifest['withClassNo']), (2, 'test-2', 1))

    def test_rejects_changed_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            raw = Path(tmp)
            (raw / 'gpi.json').write_text('[]', encoding='utf-8')
            inputs = raw / 'inputs.json'
            inputs.write_text(json.dumps([{'file': 'gpi.json', 'url': 'u', 'sha256': '0' * 64}]), encoding='utf-8')
            with self.assertRaises(SystemExit):
                bc.build(inputs, raw, raw / 'out', 'x')


if __name__ == '__main__':
    unittest.main()
