from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from .models import Product,Asset,Order

class BookingTests(TestCase):
    def setUp(self):
        self.client=APIClient()
        self.client.force_authenticate(get_user_model().objects.create_user("operator",password="test-password"))
        self.asset=Asset.objects.create(product=Product.objects.create(name="相机"),code="CAM001")
        t=timezone.now()+timedelta(days=10)
        self.data=dict(asset=self.asset.pk,customer="客户",city="上海",dispatch_at=t.isoformat(),rental_start=(t+timedelta(days=1)).isoformat(),rental_end=(t+timedelta(days=2)).isoformat(),expected_return=(t+timedelta(days=3)).isoformat(),available_at=(t+timedelta(days=4)).isoformat())
    def create(self): return self.client.post("/api/orders/",self.data,format="json")
    def test_conflict_and_cancel_release(self):
        first=self.create();self.assertEqual(first.status_code,201)
        self.assertEqual(self.create().status_code,400)
        self.assertEqual(self.client.patch(f"/api/orders/{first.data['id']}/",{"status":"cancelled"},format="json").status_code,200)
        self.assertEqual(self.create().status_code,201)
    def test_invalid_dates(self):
        self.data["rental_end"]=self.data["dispatch_at"]
        self.assertEqual(self.create().status_code,400)
    def test_inactive_asset(self):
        self.asset.state="maintenance";self.asset.save()
        self.assertEqual(self.create().status_code,400)
    def test_cannot_skip_status(self):
        first=self.create()
        self.assertEqual(self.client.patch(f"/api/orders/{first.data['id']}/",{"status":"completed"},format="json").status_code,400)
    def test_history_protected(self):
        self.create()
        self.assertEqual(self.client.delete(f"/api/assets/{self.asset.pk}/").status_code,400)
    def test_login_required(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/orders/").status_code,403)
    def test_overdue_blocks_future_booking(self):
        first=self.create();order=Order.objects.get(pk=first.data['id'])
        for field in ["dispatch_at","rental_start","rental_end","expected_return","available_at"]:
            setattr(order,field,getattr(order,field)-timedelta(days=30))
        order.status="returning";order.save()
        self.assertEqual(self.create().status_code,400)
    def test_boundary_no_overlap(self):
        self.create()
        for key in ["dispatch_at","rental_start","rental_end","expected_return","available_at"]:
            from datetime import datetime
            self.data[key]=(datetime.fromisoformat(self.data[key])+timedelta(days=4)).isoformat()
        self.assertEqual(self.create().status_code,201)

    def test_create_asset_from_existing_product_and_book(self):
        product=Product.objects.create(name="已有商品",model="型号A")
        response=self.client.post("/api/assets/",{"product":product.pk,"code":"NEW-001","state":"active"},format="json")
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.data["product_name"],"已有商品")
        listing=self.client.get("/api/assets/")
        self.assertTrue(any(a["id"]==response.data["id"] for a in listing.data))
        self.data["asset"]=response.data["id"]
        self.assertEqual(self.create().status_code,201)
    def test_duplicate_asset_code_rejected(self):
        response=self.client.post("/api/assets/",{"product":self.asset.product_id,"code":self.asset.code,"state":"active"},format="json")
        self.assertEqual(response.status_code,400)


class SyncProductAssetsTests(TestCase):
    def run_sync(self, apply=False):
        from io import StringIO
        from django.core.management import call_command
        output=StringIO()
        call_command("sync_product_assets", apply=apply, stdout=output)
        return output.getvalue()

    def test_preview_does_not_write(self):
        from .models import Audit
        Product.objects.create(name="相机")
        self.assertIn("AUTO-", self.run_sync())
        self.assertEqual(Asset.objects.count(),0)
        self.assertEqual(Audit.objects.count(),0)

    def test_apply_is_repeatable_and_preserves_existing_stock(self):
        from .models import Audit
        missing=Product.objects.create(name="新商品")
        existing=Product.objects.create(name="已有商品")
        asset=Asset.objects.create(product=existing,code="MANUAL",state="maintenance")
        self.run_sync(True)
        self.run_sync(True)
        self.assertEqual(Asset.objects.count(),2)
        self.assertEqual(Asset.objects.get(product=missing).state,"active")
        asset.refresh_from_db()
        self.assertEqual(asset.state,"maintenance")
        self.assertEqual(Audit.objects.count(),1)

    def test_generated_code_collision_does_not_overwrite(self):
        missing=Product.objects.create(name="缺库存")
        other=Product.objects.create(name="其他商品")
        base=f"AUTO-{missing.pk:06d}"
        Asset.objects.create(product=other,code=base)
        self.run_sync(True)
        self.assertEqual(Asset.objects.get(product=missing).code,base+"-1")
