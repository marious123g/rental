# 租赁管理系统

Vue 3 + Django 5.2 + PostgreSQL 16。包含登录、商品目录、实物库存、订单创建修改取消、状态流转、档期查询和操作记录（后台查看）。界面时间按浏览器本地时区显示，服务端使用 Asia/Shanghai。

## 本地开发（Windows）

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
Copy-Item frontend/dist/app.js static/
Copy-Item frontend/dist/style.css static/
.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py createsuperuser
.\.venv\Scripts\python manage.py runserver
```

访问 http://127.0.0.1:8000。开发使用 SQLite；正式部署使用 PostgreSQL。登录后先建商品目录，再建实物，再建订单。选商品和实物时使用下拉框。

## AWS Ubuntu 22.04 / 24.04 部署

建议起步配置 2 核 / 4 GB 内存（非性能保证）、足够磁盘及固定公网 IP。给域名配置 A 记录指向服务器。EC2 安全组开放 TCP 80、443，22 只允许自己的 IP。数据库不开放公网端口。

将整个项目（排除 .venv、node_modules、.env、db.sqlite3）上传至 `/opt/rental`，进入目录：

```bash
sudo bash deploy/install-docker.sh
cp .env.example .env
openssl rand -hex 32
openssl rand -hex 32
nano .env
sudo bash deploy/deploy.sh
sudo docker compose exec web python manage.py createsuperuser
sudo bash deploy/setup-https.sh rental.example.com your-email@example.com
```

将两个随机值分别写入 SECRET_KEY、POSTGRES_PASSWORD；替换 ALLOWED_HOSTS 和 CSRF_TRUSTED_ORIGINS 为真实域名。HTTPS 脚本配置宿主机 Nginx 和 Certbot，容器入口仅监听本机 8080。该脚本适合专用服务器；已有 Nginx 或其他 80/443 服务时请先整合配置。域名解析和 80/443 可达后才可签发证书。首次 HTTPS 配置完成后通过 `https://你的域名` 使用。

不要在已有数据库上直接修改 POSTGRES_PASSWORD，需同步修改数据库用户密码。不要执行 `docker compose down -v`，它会删除数据库卷。

更新：上传代码后再次运行 `sudo bash deploy/deploy.sh`。更新前先备份；迁移可能改变数据库，不提供自动回滚。

## 备份和恢复

```bash
sudo bash deploy/backup.sh
# 覆盖恢复前，先备份当前数据；恢复将暂时停止应用
sudo bash deploy/restore.sh backups/实际文件名.dump --confirm-overwrite
```

备份保存在项目 backups 目录，请复制到异机或私有 S3。仅本机备份无法应对服务器损坏。可通过 root 的 crontab 每日执行：

```cron
0 2 * * * cd /opt/rental && /bin/bash deploy/backup.sh >> /var/log/rental-backup.log 2>&1
```

定期在独立环境验证恢复；根据业务自行设置保留周期，脚本不会自动删除旧备份。`sudo certbot renew --dry-run` 可验证证书续期配置。

## 业务规则

- 每张订单当前关联一件实物，多件商品需拆单；数据结构后续可扩展订单明细。
- 发货 ≤ 租期开始 < 租期结束 ≤ 预计回库 ≤ 整理完成。区间采用左闭右开，前一单整理完成后可立即接下一单。
- 新建订单从待发货开始。待发货可取消；发货后走归还和验收流程。完成需填写实际收到时间。
- 发货后的订单禁止更换实物或修改已确认租期；可调整回库预计时间，但仍需通过冲突检查。
- 活跃订单存在逾期回库时阻止新预订，需人工核实并更新预计时间或完成归还。
- 创建和修改订单在 PostgreSQL 事务中锁定实物，避免并发重复预订。SQLite 仅用于开发，不能验证生产行锁行为。
- 商品和实物有历史引用时禁止删除；改为停用。订单禁止物理删除。后台业务表只读，统一通过业务接口校验。
- 所有已登录账号都有业务操作权限，第一版用于可信内部人员；暂未实现按员工区分权限、物流接口、自动运费或城市运输时效计算。
- 城市和加急为记录字段；查询必须手动填写完整占用区间，预计回库由人工维护。

## 检查

```powershell
.\.venv\Scripts\python manage.py check
.\.venv\Scripts\python manage.py test
```

生产排查：`sudo docker compose logs --tail=100 web nginx db`。后台 `/admin/` 可查看操作记录。

## 将商品目录补充到实物库存

仅为没有任何实物库存的商品创建一件正常状态实物。已有实物（包括停用或维修）会跳过，不会修改已有数量、状态或订单。生成唯一编号 `AUTO-商品ID`，并写入操作记录。默认预览不写入，可重复执行。

```bash
sudo docker compose exec web python manage.py sync_product_assets
sudo docker compose exec web python manage.py sync_product_assets --apply
```

执行前请确认这些商品确实各有一件可出租实物；命令不推断真实库存数量。正式同步前可先运行 `sudo bash deploy/backup.sh`。
