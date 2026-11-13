from django.core.management.base import BaseCommand
from django.db import transaction
from rental.models import Product, Asset, Audit


class Command(BaseCommand):
    help = "为无实物库存的商品创建一件正常状态实物；默认仅预览，--apply 才写入。"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="执行同步，默认仅预览")

    @transaction.atomic
    def handle(self, *args, **options):
        apply = options["apply"]
        # PostgreSQL 上锁定商品，使本命令的并发执行串行化。
        products = list(Product.objects.select_for_update().order_by("pk"))
        existing = set(Asset.objects.values_list("product_id", flat=True))
        codes = set(Asset.objects.values_list("code", flat=True))
        created = skipped = 0
        for product in products:
            if product.pk in existing:
                skipped += 1
                continue
            base = f"AUTO-{product.pk:06d}"
            code = base
            suffix = 1
            while code in codes:
                code = f"{base}-{suffix}"
                suffix += 1
            codes.add(code)
            if apply:
                asset = Asset.objects.create(product=product, code=code, state="active")
                Audit.objects.create(actor="sync_product_assets", action="create", detail={
                    "type":"Asset", "id":asset.pk,
                    "snapshot":{"product":product.pk,"code":code,"state":"active"},
                })
            created += 1
            self.stdout.write(f"{'创建' if apply else '计划创建'} {code} · {product}")
        self.stdout.write(self.style.SUCCESS(
            f"{'同步完成' if apply else '预览完成（未写入）'}：新增 {created} 件，跳过 {skipped} 个已有库存商品。"
        ))
        if not apply:
            self.stdout.write("确认后添加 --apply 执行。每种商品仅补建一件，实际多件库存请另行添加。")
