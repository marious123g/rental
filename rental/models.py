from django.db import models

class Product(models.Model):
    name = models.CharField("商品名称", max_length=120)
    model = models.CharField("型号", max_length=120, blank=True)
    notes = models.TextField("备注", blank=True)
    def __str__(self): return f"{self.name} {self.model}"

class Asset(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="商品")
    code = models.CharField("实物编号", max_length=80, unique=True)
    state = models.CharField("库存状态", max_length=20, choices=[("active","正常"),("maintenance","维修"),("inactive","停用")], default="active")
    def __str__(self): return f"{self.code} · {self.product}"

class Order(models.Model):
    STATES = [("pending","待发货"),("shipping","运输中"),("rented","等待归还"),("returning","归还中"),("inspection","待验收"),("completed","已完成"),("cancelled","已取消")]
    asset = models.ForeignKey(Asset, on_delete=models.PROTECT, verbose_name="出租实物")
    customer = models.CharField("客户姓名", max_length=100)
    phone = models.CharField("联系方式", max_length=80, blank=True)
    city = models.CharField("租赁城市", max_length=100)
    rental_start = models.DateTimeField("租期开始")
    rental_end = models.DateTimeField("租期结束")
    dispatch_at = models.DateTimeField("计划发货时间")
    expected_return = models.DateTimeField("预计回到手中")
    available_at = models.DateTimeField("整理完成可再次发货时间")
    actual_return = models.DateTimeField("实际收到时间", null=True, blank=True)
    urgent = models.BooleanField("加急", default=False)
    status = models.CharField("订单状态", max_length=20, choices=STATES, default="pending")
    notes = models.TextField("备注", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"#{self.pk} {self.customer} / {self.asset.code}"

class Audit(models.Model):
    actor = models.CharField(max_length=150)
    action = models.CharField(max_length=100)
    detail = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
