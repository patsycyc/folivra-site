# 台灣書目分片

閱芽 App 依 ISBN 查詢的台灣書目，放在 `catalog/v2/`（1024 個分片，`{isbn13: [書名, 作者, 出版者, 語言, 來源, 分類號, 主題]}`）。
資料來自國家圖書館、文化部的開放資料，依政府資料開放授權條款－第 1 版使用，說明頁在 `catalog/index.html`。

- `sources.py`：查政府資料開放平臺的最新清單、下載新資料、更新 `inputs.json`（所有用過的原始檔與 SHA-256）。
- `build_catalog.py`：從原始檔重建分片；整理規則沿用網頁版 v35（`v35_build_taiwan_books.py`），再清理作者欄位（`author_clean.py`）。
- `compare_shards.py`：與目前發布的分片比對。
- 原始檔保存在本 repo 的 `catalog-inputs` 發行版；來源網站移除舊檔時，重建仍可使用。

`.github/workflows/catalog.yml` 每月 5 日自動執行，有新資料就重建並發布；也可在 Actions 頁面手動執行。
