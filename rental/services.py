from django.utils import timezone
from .models import Order

def conflicts(asset, start, end, exclude=None):
    qs = Order.objects.filter(asset=asset).exclude(status__in=["completed", "cancelled"])
    if exclude: qs = qs.exclude(pk=exclude)
    # 逾期未回库不可依赖过期的预计时间释放库存。
    return qs.filter(models.Q(dispatch_at__lt=end, available_at__gt=start) | models.Q(available_at__lte=timezone.now(), status__in=["shipping","rented","returning","inspection"]))

from django.db import models

def validate_order(data, instance=None):
    from rest_framework.exceptions import ValidationError
    get = lambda key: data.get(key, getattr(instance, key, None))
    times = [get(k) for k in ["dispatch_at","rental_start","rental_end","expected_return","available_at"]]
    if all(times) and not (times[0] <= times[1] < times[2] <= times[3] <= times[4]):
        raise ValidationError("时间必须满足：发货 ≤ 租期开始 < 租期结束 ≤ 预计回库 ≤ 可再次发货。")
    status = get("status") or "pending"
    if instance and status != instance.status:
        allowed = {"pending":["shipping","cancelled"],"shipping":["rented","returning"],"rented":["returning"],"returning":["inspection"],"inspection":["completed"],"completed":[],"cancelled":[]}
        if status not in allowed[instance.status]: raise ValidationError("不允许此状态变更。")
    if not instance and status != "pending": raise ValidationError("新订单必须为待发货。")
    if instance and instance.status != "pending":
        for key in ["asset","dispatch_at","rental_start","rental_end"]:
            if key in data and data[key] != getattr(instance,key): raise ValidationError("发货后不可更换实物或修改已确认租期。")
    if status == "completed" and not get("actual_return"): raise ValidationError("完成前请填写实际收到时间。")
    if status not in ["completed","cancelled"] and get("asset"):
        if get("asset").state != "active": raise ValidationError("实物已停用或维修。")
        if conflicts(get("asset"), times[0], times[-1], instance.pk if instance else None).exists(): raise ValidationError("商品档期冲突或存在逾期未归还订单。")
    return data
