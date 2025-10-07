# ZeroTier 多設備加入同一 Network 教學

## � Network ID

- 目標 Network ID: `8286ac0e47af653f`

---

## �️ Windows 加入流程

### ① 安裝 ZeroTier

- 前往官網下載並安裝 ZeroTier：
  � [https://www.zerotier.com/download/](https://www.zerotier.com/download/)

### ② 啟動 ZeroTier One

- 安裝完成後，系統右下角會有 **ZeroTier One** 圖示
- 可使用 GUI 或命令列操作

### ③ 檢查節點資訊

```powershell
zerotier-cli info
```

範例輸出：

```
200 info b1119e0652 1.14.2 ONLINE
```

### ④ 加入 Network

```powershell
zerotier-cli join 8286ac0e47af653f
```

### ⑤ 確認已加入

```powershell
zerotier-cli listnetworks
```

範例：

```
200 listnetworks 8286ac0e47af653f pi network 16:77:3b:d8:3a:50 OK PRIVATE ethernet_32780 172.28.59.45/16
```

條件：

- `status = OK`
- `ZT assigned ips` 有出現 `172.28.x.x/16`

### ⑥ 後台授權

1. 登入 [https://my.zerotier.com](https://my.zerotier.com)
2. 找到 `8286ac0e47af653f`
3. 在 **Members** 找到該 Windows 的 Node ID
4. 勾選 **Authorized**

### ⑦ 測試連線

在 Windows cmd：

```powershell
ping 172.28.104.118   # 這是 WSL 的 ZeroTier IP
```

瀏覽器訪問：

```
http://172.28.104.118:8888/home
```

---

## � Mac 加入流程

### ① 安裝 ZeroTier

```bash
brew install zerotier-one
```

### ② 啟動服務

```bash
sudo zerotier-cli info
```

### ③ 加入 Network

```bash
sudo zerotier-cli join 8286ac0e47af653f
```

### ④ 確認

```bash
sudo zerotier-cli listnetworks
```

### ⑤ 授權

同樣需到 [https://my.zerotier.com](https://my.zerotier.com) 勾選 **Authorized**

---

## � Raspberry Pi 加入流程

### ① 安裝 ZeroTier

```bash
curl -s https://install.zerotier.com | sudo bash
```

### ② 加入 Network

```bash
sudo zerotier-cli join 8286ac0e47af653f
```

### ③ 確認

```bash
sudo zerotier-cli listnetworks
```

### ④ 授權

到 ZeroTier 網頁後台 **勾選授權**

---

## � WSL (Ubuntu) 加入流程

### ① 安裝 ZeroTier

```bash
curl -s https://install.zerotier.com | sudo bash
```

### ② 啟動並檢查

```bash
sudo zerotier-cli info
```

### ③ 加入 Network

```bash
sudo zerotier-cli join 8286ac0e47af653f
```

### ④ 確認

```bash
sudo zerotier-cli listnetworks
```

---

## ✅ 最終檢查

- 所有設備都應該有一個 **172.28.x.x/16 的 IP**
- 在彼此之間 `ping` 測試
- 確定能透過 ZeroTier IP 存取 Django 服務：

```
http://172.28.xxx.xxx:8888/home
```

---

## � 建議

整理一份對照表：

| 設備         | ZeroTier IP    | 備註        |
| ------------ | -------------- | ----------- |
| Windows      | 172.28.x.x     | 主機        |
| WSL          | 172.28.104.118 | Django 專案 |
| Mac          | 172.28.x.x     | 測試機      |
| Raspberry Pi | 172.28.x.x     | IoT 裝置    |
