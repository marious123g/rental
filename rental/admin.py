from django.contrib import admin
from .models import Product, Asset, Order, Audit
# 业务写入统一经 API 校验；后台仅查看。
class ReadOnly(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False
for model in [Product, Asset, Order, Audit]: admin.site.register(model, ReadOnly)
admin.site.site_header = "租赁管理后台"
