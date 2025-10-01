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

##### 進入 Django shell 測試建立 **Device** 物件:

- `python manage.py shell`

```python
from pi_devices.models import Device

# 建立一筆新裝置
d = Device.objects.create()

print(d.id)                 # 新增後的 ID
print(d.serial_number)      # 系統自動產生的序號
print(d.verification_code)  # 自動產生的驗證碼
print(d.token)              # 自動產生的 Token
print(d.is_bound)           # 預設 False
print(d.created_at)         # 自動時間戳記
```

```python
# 進行轉換成註冊頁面QR CODE png
from pi_devices.utils.qrcode_utils import generate_device_qrcode
file_path = generate_device_qrcode(d)
print("QR Code 已儲存於：", file_path) # QR Code 已儲存於： /Users/qkauia/Desktop/HomePiWeb/static/qrcodes/PI-AA5CA0A5.png
```

##### 為什麼要另外拉出`forms.py`？？

0. 首先是 `Django` 慣例

1. 職責分離（Separation of Concerns）

- `views.py` 應該專注在 <u>流程控制</u>（決定要 render 哪個模板、redirect 到哪裡）。
- `forms.py` 專注在 <u>資料驗證與清理</u>（欄位定義、格式檢查、商業規則檢查）。
- 這樣程式結構會更乾淨，避免 views 塞滿驗證邏輯。

2. 避免重複程式碼

- 如果未來這個註冊表單要在別的地方用（例如後台、API、命令列工具），
  你可以直接重複使用 UserRegisterForm，不用每次都重新寫驗證邏輯。

3. 更好的錯誤處理

- `forms.py` 驗證失敗時，會自動幫你把錯誤訊息綁到表單欄位上。
- 前端 template 直接用 `{{ form.errors }}` 就能顯示錯誤，不用自己組字串。

1. 認證相關（Authentication）

| 裝飾器                                            | 說明                                                             | 範例                                                                      |
| ------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------------------- |
| @login_required                                   | 限制必須登入才能訪問該 view。未登入會跳轉到 settings.LOGIN_URL。 | @login_required def dashboard(request): ...                               |
| @permission_required('app_label.permission_code') | 檢查使用者是否擁有指定權限，否則顯示 403 頁面。                  | @permission_required('polls.can_vote') def vote(request): ...             |
| @user_passes_test(test_func)                      | 自訂一個檢查函式（回傳 True 才能訪問）。                         | @user_passes_test(lambda u: u.is_superuser) def secret_area(request): ... |

2. HTTP 請求方法限制（HTTP Method Restrictions）  
   來自 django.views.decorators.http

| 裝飾器                                 | 說明                           | 範例                                                          |
| -------------------------------------- | ------------------------------ | ------------------------------------------------------------- |
| @require_http_methods(["GET", "POST"]) | 限制只能用特定 HTTP 方法訪問。 | @require_http_methods(["POST"]) def submit_form(request): ... |
| @require_GET                           | 限制只能用 GET 請求。          | @require_GET def list_items(request): ...                     |
| @require_POST                          | 限制只能用 POST 請求。         | @require_POST def save_data(request): ...                     |

3. 安全相關（Security）  
   來自 django.views.decorators.csrf 和 django.views.decorators.cache

| 裝飾器               | 說明                                                    | 範例                                             |
| -------------------- | ------------------------------------------------------- | ------------------------------------------------ |
| @csrf_exempt         | 關閉 CSRF 驗證（一般不建議使用，除非 API 或特殊情況）。 | @csrf_exempt def webhook(request): ...           |
| @csrf_protect        | 強制啟用 CSRF 驗證（即使全域關閉）。                    | @csrf_protect def form_view(request): ...        |
| @cache_page(timeout) | 快取整個 view 的輸出一段時間。                          | @cache_page(60 \* 15) def homepage(request): ... |

##### `permissions.py ` 自定義權限

0. 通常會在 `app` 裡新增一個 `permissions.py`
1. 在 `(app)/permissions.py` 寫權限邏輯

```python
# 舉例：(myapp)/permissions.py
from functools import wraps
from django.http import HttpResponseForbidden

def superadmin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:  # 先檢查有沒有登入
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())

        if request.user.role != "superadmin":
            return HttpResponseForbidden("沒有權限")
        return view_func(request, *args, **kwargs)
    return wrapper
```

2. 在 `views.py` 匯入並使用

```python
# 舉例：(myapp)/views.py
from django.http import HttpResponse
from .permissions import superadmin_required

@superadmin_required
def dashboard(request):
    return HttpResponse("這是超級管理員後台")
```

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

##### Django 常用指令說明（初學者版）:

###### `auth` 認證相關指令

| 指令              | 說明                                    |
| ----------------- | --------------------------------------- |
| `createsuperuser` | 建立 Django 管理者帳號，可登入 `/admin` |
| `changepassword`  | 修改使用者密碼                          |

---

###### `contenttypes` 內容類型管理

| 指令                        | 說明                                        |
| --------------------------- | ------------------------------------------- |
| `remove_stale_contenttypes` | 移除未使用的 ContentType 資料（資料庫清理） |

---

###### 資料庫與遷移

| 指令                | 說明                                 |
| ------------------- | ------------------------------------ |
| `makemigrations`    | 根據 models.py 產生遷移檔            |
| `migrate`           | 執行遷移檔並建立/更新資料表          |
| `showmigrations`    | 顯示所有遷移檔的狀態（已執行或尚未） |
| `sqlmigrate`        | 顯示某個遷移檔會執行的 SQL           |
| `sqlflush`          | 顯示清除資料表時的 SQL               |
| `sqlsequencereset`  | 重設自動編號 ID 的 SQL               |
| `squashmigrations`  | 合併多個遷移檔為一個                 |
| `optimizemigration` | 自動優化遷移檔（Django 4+ 新功能）   |
| `inspectdb`         | 從現有資料庫反向產生 models.py       |
| `flush`             | 清空資料表內容（不刪除表）           |

###### 開發與偵錯

| 指令           | 說明                                         |
| -------------- | -------------------------------------------- |
| `runserver`    | 啟動開發伺服器（網址 http://127.0.0.1:8000） |
| `shell`        | 啟動互動式 Python 環境，可操作模型資料       |
| `check`        | 檢查設定或程式碼錯誤                         |
| `diffsettings` | 比較目前設定與預設設定的差異                 |

###### 測試與資料

| 指令         | 說明                           |
| ------------ | ------------------------------ |
| `test`       | 執行自動化測試                 |
| `testserver` | 啟動測試伺服器（載入測試資料） |
| `dumpdata`   | 匯出資料成 JSON 格式           |
| `loaddata`   | 載入 JSON 資料檔案             |

###### 翻譯與語系

| 指令              | 說明                   |
| ----------------- | ---------------------- |
| `makemessages`    | 建立翻譯語系檔（.po）  |
| `compilemessages` | 將翻譯檔編譯成可用格式 |

###### 快取與 Email

| 指令               | 說明                 |
| ------------------ | -------------------- |
| `createcachetable` | 建立資料庫快取表格   |
| `sendtestemail`    | 寄出一封測試用 email |

---

###### `Sessions` 管理

| 指令            | 說明                                |
| --------------- | ----------------------------------- |
| `clearsessions` | 移除過期的 Session 記錄（登入資料） |

---

###### `staticfiles` 靜態資源管理

| 指令            | 說明                                     |
| --------------- | ---------------------------------------- |
| `collectstatic` | 收集所有靜態檔案到 STATIC_ROOT（部署用） |
| `findstatic`    | 查找 static 檔案的實體位置               |

---

###### 專案 / 應用建立

| 指令           | 說明                    |
| -------------- | ----------------------- |
| `startproject` | 建立新的 Django 專案    |
| `startapp`     | 建立新的應用程式（App） |

---

##### `tree` 套件 資料結構樹狀圖指令:

###### 安裝套件

- 在某些 Linux 發行版或 macOS 上，tree 指令可能不是內建的，需要手動安裝。
  - Ubuntu/Debian: `sudo apt-get install tree`
  - macOS (使用 Homebrew): `brew install tree`

| 參數        | 說明                                                             |
| :---------- | :--------------------------------------------------------------- |
| `-L [層級]` | 指定要顯示的目錄層級深度。例如 `tree -L 2` 只會顯示到第二層。    |
| `-d`        | 只顯示目錄，不顯示檔案。                                         |
| `-f`        | 在每個檔案或目錄前顯示完整的相對路徑。                           |
| `-s`        | 列出檔案或目錄的大小。                                           |
| `-h`        | 以更容易閱讀的格式（如 K, M, G）顯示檔案大小。                   |
| `-p`        | 顯示檔案和目錄的權限。                                           |
| `-C`        | 為不同的檔案類型加上顏色，使其更容易區分。                       |
| `-a`        | 顯示所有檔案和目錄，包含隱藏檔（以 `.` 開頭的檔案）。            |
| `-I [範本]` | 忽略符合指定範本的檔案或目錄。例如 `tree -I "node_modules"`。    |
| `-N`        | 在處理非英語系檔名（如中文）時，直接列出原始字元，避免亂碼問題。 |

###### 常用範例

- **限制顯示層級為 2 層，並加上顏色：**

  - `tree -L 2 -C`

- **顯示包含檔案大小和權限的結構：**

  - `tree -shp`

- **將當前目錄結構輸出到一個文字檔：** -`tree -a > directory_structure.txt`

##### 型別提示：

###### 變數型別標註：

```python
age: int = 20
name: str = "Alice"
is_active: bool = True
```

###### 函式型別提示：

```python
def greet(name: str) -> str:
    return f"Hello, {name}"

def add_numbers(a: int, b: int) -> int:
    return a + b
```

> name: str 參數型別標註, -> str 回傳值型別提示

###### 集合、複合型別（需要 typing 套件）：

```python
from typing import List, Dict, Tuple, Optional, Iterable, Any

def total(nums: List[int]) -> int:
    return sum(nums)

def get_user(id: int) -> Optional[str]:
    # 可能傳回 user 資料(str) 或 None
    return None if id == 0 else "User"

def parse(data: Iterable[str]) -> List[str]:
    return [d.lower() for d in data]

def info(user: Dict[str, Any]) -> str:
    # user 是鍵為字串，值任意型別的字典
    return str(user)
```

> List[int]：int 類型清單
> Optional[str]：str 或 None
> Dict[str, Any]：key 為字串、value 任意型別的字典
> Iterable[str]：可被 for 迴圈走訪的字串容器

###### 多重型別回傳 (Union 或 |)：

```python
from typing import Union

def answer(flag: bool) -> Union[int, str]:
    return 123 if flag else "YES"

def code(data: str | int) -> None:
    print(data)
```

###### 補充說明：

- Python 3.9 之後集合型別可直接寫 `list[int]`、`dict[str, float]`，不用 `import typing`。
- 型別提示只給人或檢查工具「看懂」，不會改變 Python 實際運作行為。

##### models 語法學習集：

###### import:

- `from __future__ import annotations`:

`from __future__ import annotations` 是一個特殊的引入指令，但它的作用和一般的 import 不太一樣。它被稱為「未來語句 (Future statement)」。

它啟用了 PEP 563 中定義的「延遲評估類型註解 (Postponed Evaluation of Type Annotations)」功能。

**核心功能：將類型註解變成字串**

```python
# 在 Python 3.8 或更早版本中會報錯
def get_user_name(user: User) -> str:
    return user.name

class User:
    name: str
```

> 在上面的例子中，當 Python 讀到 get_user_name 函式時，User 類別還沒有被定義，所以會立刻拋出 NameError。

加上 from **future** import annotations 的情況：

```python
from __future__ import annotations

# 這段程式碼可以正常執行
def get_user_name(user: User) -> str:
    return user.name

class User:
    name: str
```

> 加上這行指令後，Python 會把 user: User 中的 User 當成一個字串 'User' 來儲存。它不會馬上尋找 User 這個類別是什麼，因此避免了錯誤。等到真正需要進行類型檢查時（例如使用 MyPy 工具），這個字串才會被解析。
