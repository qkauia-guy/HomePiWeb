from django.urls import reverse
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from groups.models import Group, GroupMembership, GroupDevice
from pi_devices.models import Device

User = get_user_model()


class GroupAccessAndDetachTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            "owner@example.com", "pass123", role="superadmin"
        )
        self.member = User.objects.create_user(
            "member@example.com", "pass123", role="user"
        )
        self.outsider = User.objects.create_user(
            "outsider@example.com", "pass123", role="user"
        )

        self.group = Group.objects.create(name="G", owner=self.owner)

        # owner 的裝置，先掛進群組以便測 detach
        self.d1 = Device.objects.create(is_bound=True)
        self.owner.device = self.d1
        self.owner.save()
        GroupDevice.objects.create(
            group=self.group, device=self.d1, added_by=self.owner
        )

        # 把 member 加入群組（operator）
        GroupMembership.objects.create(
            user=self.member, group=self.group, role="operator"
        )

    def test_group_detail_access_control(self):
        # 擁有者可看
        self.client.force_login(self.owner)
        url = reverse("group_detail", args=[self.group.id])
        self.assertEqual(self.client.get(url).status_code, 200)

        # 成員可看
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(url).status_code, 200)

        # 局外人不可看（被導回列表或顯示錯誤）
        self.client.force_login(self.outsider)
        resp = self.client.get(url, follow=True)
        self.assertNotEqual(resp.redirect_chain, [])  # 有被導回去
        # 或檢查不是 200（視你的實作）
        # self.assertNotEqual(resp.status_code, 200)

    def test_detach_requires_post(self):
        self.client.force_login(self.owner)
        url = reverse("group_detach_device", args=[self.group.id, self.d1.id])
        # GET 應該不允許
        resp = self.client.get(url)
        self.assertIn(
            resp.status_code, [301, 302, 405]
        )  # 視伺服器/中介行為，常見為 405

    def test_only_group_admin_or_owner_can_detach(self):
        url = reverse("group_detach_device", args=[self.group.id, self.d1.id])

        # 一般成員（operator）→ 不可移除
        self.client.force_login(self.member)
        self.client.post(url, follow=True)
        self.assertTrue(
            GroupDevice.objects.filter(group=self.group, device=self.d1).exists()
        )

        # 擁有者 → 可以移除
        self.client.force_login(self.owner)
        self.client.post(url, follow=True)
        self.assertFalse(
            GroupDevice.objects.filter(group=self.group, device=self.d1).exists()
        )
