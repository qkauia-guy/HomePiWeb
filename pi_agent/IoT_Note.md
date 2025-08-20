<!-- markdownlint-disable -->

# IoT 控制流程筆記

## 1. 使用者操作

- 使用者在網站（前端）點擊 **「開燈 / 關燈 / 切換」** 按鈕。
- 前端送出一個 **POST 請求** 到後端 view：
  ```
  /devices/<device_id>/light/<action>/
  action = "on" | "off" | "toggle"
  ```

---

## 2. Django 後端處理 (`device_light_action`)

1. **驗證登入**：必須是已登入的使用者（`@login_required`）。
2. **只允許 POST**：避免 GET 請求亂觸發（`@require_POST`）。
3. **檢查 action 合法性**：只接受 `on/off/toggle`。
   - 若非法 → 回傳 400 JSON。
4. **檢查裝置權限**：
   - 找到 `Device`，確認 `device.user_id == request.user.id`。
   - 否則 → 回傳 403 Forbidden。
5. **轉換命令**：
   - `on → light_on`
   - `off → light_off`
   - `toggle → light_toggle`
6. **建立 DeviceCommand**（寫入 DB）：
   - `device`：目標裝置
   - `command`：light_on/off/toggle
   - `req_id`：隨機 uuid，供 Pi ACK 用
   - `expires_at`：2 分鐘後過期
   - `status=pending`：等待裝置取走
7. **決定回應**：
   - 若是 AJAX（`X-Requested-With: XMLHttpRequest`）→ 回 JSON：`{ok, req_id, cmd_id}`
   - 否則 → redirect 回上一頁，顯示成功訊息。

---

## 3. 樹莓派 Agent (`http_agent.py`)

1. **定時 Ping**
   - 每 30 秒送 `/api/device/ping/`，告訴伺服器「我在線」。
2. **長輪詢 Pull**
   - 向 `/device_pull` 發送請求，最多等待 20 秒。
   - 若後端有 `pending` 指令 → 回傳 `{cmd, req_id}`。
   - 若沒有 → 回傳 HTTP 204（空）。
3. **執行命令**
   - `light_on()` → LED 亮
   - `light_off()` → LED 滅
   - `light_toggle()` → LED 切換
   - `unlock_hw()` → 模擬解鎖脈衝
   - 未知命令 → 回報錯誤
4. **回報 ACK**
   - 向 `/device_ack` 發送 `{req_id, ok, error}`，更新指令狀態（done / failed）。

---

## 4. 後端 API 配合

- **/api/device/ping/**
  - 更新裝置 last_ping
- **/device_pull**
  - 回傳裝置的第一筆 pending 指令
  - 無 → 回 204
- **/device_ack**
  - 更新 DeviceCommand 狀態（done/failed）

---

# 總結流程圖（文字版）

```
[前端點擊按鈕]
        ↓ (POST /light/<action>)
[Django 建立 DeviceCommand(pending)]
        ↓
[樹莓派 agent → /device_pull]
        ↓ (取指令 cmd, req_id)
[樹莓派執行 LED 控制]
        ↓
[樹莓派 agent → /device_ack]
        ↓
[後端更新指令狀態 = done/failed]
        ↓
[前端 AJAX / 刷新頁面顯示結果]
```
