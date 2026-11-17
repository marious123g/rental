from datetime import datetime, time
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from .models import Product, Asset, Order, Audit
from .services import validate_order, conflicts

class ProductSerializer(serializers.ModelSerializer):
    class Meta: model=Product; fields="__all__"
class AssetSerializer(serializers.ModelSerializer):
    product_name = serializers.CharField(source="product.name", read_only=True)
    class Meta: model=Asset; fields="__all__"
class RentalDateField(serializers.DateField):
    """按业务时区提供日期接口，兼容数据库已有的时间字段。"""
    def to_internal_value(self, data):
        day = super().to_internal_value(data)
        return timezone.make_aware(datetime.combine(day, time.min), timezone.get_default_timezone())

    def to_representation(self, value):
        return super().to_representation(timezone.localdate(value, timezone.get_default_timezone()))

class OrderSerializer(serializers.ModelSerializer):
    rental_start = RentalDateField()
    rental_end = RentalDateField()
    asset_code = serializers.CharField(source="asset.code", read_only=True)
    product_name = serializers.CharField(source="asset.product.name", read_only=True)
    product_model = serializers.CharField(source="asset.product.model", read_only=True)
    class Meta: model=Order; fields="__all__"; read_only_fields=["created_at"]

class BaseViewSet(viewsets.ModelViewSet):
    def record(self, action, obj): Audit.objects.create(actor=self.request.user.username, action=action, detail={"type":obj.__class__.__name__,"id":obj.pk,"snapshot":{f.name:str(getattr(obj,f.attname)) for f in obj._meta.fields}})
    def perform_create(self, serializer): self.record("create", serializer.save())
    def perform_update(self, serializer): self.record("update", serializer.save())
    def perform_destroy(self, instance):
        try:
            with transaction.atomic():
                self.record("delete", instance)
                instance.delete()
        except ProtectedError: raise ValidationError("已有历史关联，无法删除，请停用。")

class ProductViewSet(BaseViewSet):
    queryset=Product.objects.all().order_by("id"); serializer_class=ProductSerializer
class AssetViewSet(BaseViewSet):
    queryset=Asset.objects.select_related("product").all().order_by("id"); serializer_class=AssetSerializer
    @action(detail=False)
    def availability(self, request):
        start=parse_datetime(request.query_params.get("start", "")); end=parse_datetime(request.query_params.get("end", ""))
        if not start or not end or not start.tzinfo or not end.tzinfo or start >= end: raise ValidationError("请提供带时区且起点早于终点的完整占用区间。")
        result=[]
        for asset in self.get_queryset().filter(product__name__icontains=request.query_params.get("q", "")):
            orders=conflicts(asset,start,end)
            active=asset.order_set.exclude(status__in=["completed","cancelled"]).order_by("dispatch_at")
            result.append({"id":asset.id,"code":asset.code,"product":str(asset.product),"state":asset.state,"available":asset.state=="active" and not orders.exists(),"conflicting_orders":list(orders.values("id","status","expected_return","available_at")),"schedule":list(active.values("id","status","dispatch_at","expected_return","available_at"))})
        return Response(result)
class OrderViewSet(BaseViewSet):
    queryset=Order.objects.select_related("asset__product").all().order_by("-id"); serializer_class=OrderSerializer
    def get_queryset(self):
        qs=super().get_queryset()
        if self.action == "list":
            for word in self.request.query_params.get("q", "").split():
                qs=qs.filter(Q(asset__product__name__icontains=word) | Q(asset__product__model__icontains=word) | Q(asset__code__icontains=word))
        return qs
    def perform_create(self, serializer):
        with transaction.atomic():
            Asset.objects.select_for_update().get(pk=serializer.validated_data["asset"].pk)
            validate_order(serializer.validated_data)
            super().perform_create(serializer)
    def perform_update(self, serializer):
        with transaction.atomic():
            current=Order.objects.select_for_update().get(pk=serializer.instance.pk)
            ids=sorted({current.asset_id, serializer.validated_data.get("asset",current.asset).pk})
            list(Asset.objects.select_for_update().filter(pk__in=ids).order_by("pk"))
            serializer.instance=current
            validate_order(serializer.validated_data,current)
            super().perform_update(serializer)
    @action(detail=True, methods=["post"], url_path="confirm-shipment")
    def confirm_shipment(self, request, pk=None):
        with transaction.atomic():
            current=Order.objects.select_for_update().get(pk=self.get_object().pk)
            if current.status != "pending":
                raise ValidationError("只有待发货订单可以确认发货。")
            Asset.objects.select_for_update().get(pk=current.asset_id)
            validate_order({"status":"shipping"},current)
            current.status="shipping"
            current.save(update_fields=["status"])
            self.record("confirm_shipment",current)
        return Response(self.get_serializer(current).data)

    @action(detail=True, methods=["post"], url_path="complete-inspection")
    def complete_inspection(self, request, pk=None):
        with transaction.atomic():
            current=Order.objects.select_for_update().get(pk=self.get_object().pk)
            if current.status not in ["returning","inspection"]:
                raise ValidationError("只有归还中或待验收订单可以完成验收。")
            Asset.objects.select_for_update().get(pk=current.asset_id)
            # 此操作表示已经收货且验收完成，归还中订单一并通过验收步骤。
            current.status="inspection"
            actual_return=current.actual_return or timezone.now()
            validate_order({"status":"completed","actual_return":actual_return},current)
            current.status="completed"
            current.actual_return=actual_return
            current.save(update_fields=["status","actual_return"])
            self.record("complete_inspection",current)
        return Response(self.get_serializer(current).data)

    def destroy(self, request, *args, **kwargs): raise ValidationError("订单保留历史，请将待发货订单状态改为已取消。")
