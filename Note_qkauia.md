<!-- markdownlint-disable -->

##### 虛擬環境(使用 mac conda):

1. `conda create --name HomePiWeb python=3.11` (原先專案資料夾已建立的指令)
2. `Proceed ([y]/n)? y` 允許安裝基礎套件
3. `conda activate HomePiWeb` 啟動虛擬機
4. `conda deactivate` 結束虛擬機

##### 建立 Django

1. `pip install django` 安裝 Django
2. `django-admin startproject HomePiWeb .` **注意命令最後有個「.」代表在當前目錄建立專案**
3. `python manage.py migrate` 根據你的 Django 專案和各個 app 的 migration（資料遷移）檔案，實際在資料庫建立或更新對應的資料表結構。 也就是自動把[models.py](./users/models.py) ( 舉例：users ) 裡設計好的欄位與關聯，同步到實際的資料庫中。

##### 建立 users App, 資料建構：

1. `python manage.py startapp users `

2. 修改 [models.py](./users/models.py)
3. 在 [settings.py](./HomePiWeb/settings.py) **註冊 app**

```
  INSTALLED_APPS = [
    ...
    'users',  # 添加
    ...
  ]
```

另外指定`AUTH_USER_MODEL = 'users.User'`
<u>Django 在啟動時會嘗試找一個叫 users 的 app 裡面有一個 User Model</u>

4. 建立 users app 的 **migration** 檔,實際執行**建立資料表**

```bash
  python manage.py makemigrations users  # 指定建立 users app 的 migration 檔
  python manage.py migrate
```

##### 建立一個 Django 後台的 Super User

- `python manage.py createsuperuser`
- 進入 [Django 後台](http://localhost:8000/admin) 測試登入看看

##### <u>utils</u> 目錄建立原因 和 為什麼要加 **`__init__.py`** 檔案：

- utils 是「工具函式模組（Utility Functions）」的簡稱，專門放置整個專案中可以重複使用的通用程式碼
- 在資料夾下建立 `__init__.py` 是 Python 用來辨識「這是一個可匯入的套件（Package）」的標記。
- 有這個檔案，才能在其他地方使用這樣的語法來匯入：

```python
from pi_devices.utils.qrcode_utils import generate_qrcode
```

##### conda 虛擬機套件 匯入 / 匯出 指令：

- 匯出 `conda env export > environment.yml`
- 之後要重建環境可以用： `conda env create -f environment.yml`

##### Github commit 範例：

1. `<類型>: <簡要描述>`

2. 常見「類型」範例：

- init: 初始化：

  - init: 初始化，專案或模組剛建好時用
  - init: project scaffold
  - init: create users app

- feat: 新增功能：

- feat: add device control API

  - feat: 用戶可上傳大頭貼

- fix: 修正 bug：

  - fix: 修正登入頁無法送出問題
  - fix: 修復儀表板顯示錯誤

- chore: 例行雜項（無功能改動，如升級、調整排版、續行）：

  - chore: update .gitignore
  - chore: remove pyc files

- refactor: 重構（重整程式結構但不改功能）：

  - refactor: split device service function

- docs: 文件／註解更新：

  - docs: update README

- test: 增加或調整測試：

  - test: 新增裝置管理測試

- style: 格式或排版調整（不影響功能）：

  - style: 調整排版及變數命名

- build: 編譯系統、CI/CD 調整：
  - build: update requirements.txt

3. 實用範例

```bash
feat: 使用者可編輯個人資料
fix: 資料庫連線逾時 bug
chore: 調整 settings.py 時區
docs: 補充部署說明於 README
test: 加入 users app 單元測試
refactor: 重構 dashboard 檔案結構
style: 統一程式碼縮排
```
