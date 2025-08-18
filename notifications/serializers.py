# 引入 Django Rest Framework 的 serializers 模組
from rest_framework import serializers

# 從當前目錄的 models.py 檔案中引入 Notification 模型
from .models import Notification


# 定義一個名為 NotificationSerializer 的類別，它繼承自 serializers.ModelSerializer
class NotificationSerializer(serializers.ModelSerializer):
    # source="user" 表示這個 'recipient' 欄位對應到 Notification 模型上的 'user' 欄位。
    # read_only=True 表示這個欄位只能被讀取，不能透過 API 進行寫入或修改。
    # API 輸出範例 -> "recipient": 123 (其中 123 是 user 的 id)
    recipient = serializers.PrimaryKeyRelatedField(source="user", read_only=True)

    message = serializers.CharField(source="body")

    # 定義 'target_ct' 欄位 (target content type)
    # SerializerMethodField 是一個特殊欄位，它的值不是直接從模型中取得，
    # 而是透過呼叫序列化器中一個名為 'get_<field_name>' 的方法來動態產生。
    # 在這個例子中，它的值會由下面的 get_target_ct 方法決定。
    target_ct = serializers.SerializerMethodField()

    # 定義 'target_id' 欄位
    # source="target_object_id" 表示這個欄位對應到模型上的 'target_object_id' 欄位。
    # 'target_ct' 和 'target_id' 通常一起使用，用於 Django 的 GenericForeignKey (通用外鍵)，
    # 讓通知可以指向任何一種不同的模型物件（例如：一篇貼文、一則留言等）。
    target_id = serializers.CharField(source="target_object_id", read_only=True)

    # Meta 內部類別，用於設定序列化器的主要行為
    class Meta:
        # 指定這個序列化器要對應的 Django 模型
        model = Notification

        # 'fields' 列表定義了最終 API 輸出中應該包含哪些欄位。
        # 這裡明確列出了所有要暴露給前端的欄位。
        fields = [
            "id",
            "recipient",  # 對應到模型的 user 欄位 (ID)
            "title",
            "message",  # 對應到模型的 body 欄位
            "kind",
            "event",
            "is_read",
            "created_at",
            "expires_at",
            "group",
            "device",
            "target_ct",  # 動態產生的欄位，方便前端判斷目標類型
            "target_id",  # 通用外鍵的目標物件 ID
            "dedup_key",  # 用於防止重複通知的鍵
            "meta",  # 其他元數據，通常是 JSON 格式
        ]

        # 'read_only_fields' 列表定義了哪些欄位是唯讀的。
        # 即使這些欄位沒有在上方單獨定義 'read_only=True'，在這裡指定也會生效。
        # 這些欄位會出現在 API 的 GET 請求的回應中，但在 POST 或 PUT 請求中會被忽略，
        # 以防止客戶端修改它們。
        read_only_fields = ["id", "recipient", "created_at"]

    def get_target_ct(self, obj):
        """
        這個方法為上面定義的 'target_ct' (SerializerMethodField) 提供值。
        它被 DRF 自動呼叫，每次序列化一個 Notification 物件時都會執行。

        參數:
        - self: 序列化器本身的實例。
        - obj:  正在被序列化的 Notification 模型物件實例。

        功能:
        這個通知的目標可能是一個貼文、一個使用者或其他任何模型。
        為了讓前端知道這個通知的目標是哪種類型的物件，我們需要回傳模型的名稱。
        'obj.target_content_type' 是 Django ContentType 框架的一個欄位，
        它儲存了目標物件的類型資訊。

        邏輯:
        1. 檢查 'obj.target_content_type_id' 是否存在。如果通知沒有指向任何特定物件，這個 ID 可能會是 None。
        2. 如果存在，就透過 'obj.target_content_type' 取得 ContentType 物件，
           再用 '.model' 屬性取得該模型的名稱（小寫字串，例如 'post', 'comment'）。
        3. 如果不存在，就回傳 None。
        """
        return obj.target_content_type.model if obj.target_content_type_id else None
