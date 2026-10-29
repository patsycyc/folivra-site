"""python3 tool/catalog/test_sources.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sources  # noqa: E402


class Names(unittest.TestCase):
    def test_file_names(self):
        f = sources.file_name
        self.assertEqual(f('6730', '提供115年9月份各出版者向國家圖書館國際標準書號中心申請ISBN之新書書目資料'), 'newbooks-2026-09.csv')
        self.assertEqual(f('6730', '提供114年10月份各出版者…'), 'newbooks-2025-10.csv')
        self.assertEqual(f('27311', '國家圖書館113年度新增書目資訊'), 'catalog-113.csv')
        self.assertEqual(f('7502', 'NBINet圖書聯合目錄(115年第2季)'), 'nbinet-115Q2.csv')
        self.assertEqual(f('35215', '1912年至2025年GPI政府出版品資訊網書目資料'), 'gpi.json')
        self.assertIsNone(f('6730', '說明文件'))
        self.assertIsNone(f('9999', 'x'))


if __name__ == '__main__':
    unittest.main()
