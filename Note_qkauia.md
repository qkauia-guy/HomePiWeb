<!-- markdownlint-disable -->

##### 虛擬環境(使用 mac conda):

1. `conda create --name HomePiWeb python=3.11`
2. `Proceed ([y]/n)? y` 允許安裝基礎套件
3. `conda activate HomePiWeb` 啟動虛擬機
4. `conda deactivate` 結束虛擬機

##### 建立 Django

1. `pip install django`
2. `django-admin startproject HomePiWeb .` **注意命令最後有個「.」代表在當前目錄建立專案**
3. `python manage.py migrate` 根據你的 Django 專案和各個 app 的 migration（資料遷移）檔案，實際在資料庫建立或更新對應的資料表結構。 也就是自動把 models.py 裡設計好的欄位與關聯，同步到實際的資料庫中。
