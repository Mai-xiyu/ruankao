import re
import sys
from pathlib import Path

import pymysql
from pymysql import MySQLError
from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import get_settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import Tag  # noqa: E402,F401
from app.models import *  # noqa: E402,F403
from app.services.import_service import import_payload, load_import_payload  # noqa: E402


PRESET_TAGS = [
    "网络基础",
    "OSI模型",
    "TCP/IP",
    "IP地址与子网划分",
    "CIDR",
    "VLSM",
    "IPv6",
    "VLAN",
    "Trunk",
    "STP",
    "链路聚合",
    "静态路由",
    "RIP",
    "OSPF",
    "BGP",
    "ACL",
    "NAT",
    "DHCP",
    "DNS",
    "HTTP",
    "HTTPS",
    "FTP",
    "邮件服务",
    "Linux服务",
    "Windows Server",
    "网络安全",
    "VPN",
    "防火墙",
    "入侵检测",
    "综合布线",
    "网络规划",
    "故障排查",
    "配置题",
    "计算题",
    "案例分析",
]


def log(message: str) -> None:
    print(f"[init] {message}")


def is_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return not lowered or "请在本地" in value or lowered in {"password", "changeme", "change-me"}


def validate_business_password(password: str) -> None:
    if is_placeholder(password):
        raise ValueError("DB_PASSWORD 为空或仍是占位符，请在 .env 中填写业务用户强密码")
    if len(password) < 12:
        raise ValueError("DB_PASSWORD 长度必须 >= 12")
    if "'" in password:
        raise ValueError("DB_PASSWORD 不允许包含单引号")
    if "\\" in password:
        raise ValueError("DB_PASSWORD 不允许包含反斜杠")
    if "\n" in password or "\r" in password:
        raise ValueError("DB_PASSWORD 不允许包含换行")


def validate_admin_password(password: str) -> None:
    if is_placeholder(password):
        raise ValueError("MYSQL_ADMIN_PASSWORD 为空或仍是占位符，请在 .env 中填写管理员密码")


def validate_identifier(value: str, name: str) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_]+", value):
        raise ValueError(f"{name} 只能包含字母、数字和下划线")


def quote_identifier(value: str) -> str:
    validate_identifier(value, "数据库名")
    return f"`{value}`"


def create_database_and_user() -> None:
    settings = get_settings()
    validate_admin_password(settings.mysql_admin_password)
    validate_business_password(settings.db_password)
    validate_identifier(settings.db_name, "DB_NAME")
    validate_identifier(settings.db_user, "DB_USER")

    log("连接 MySQL 管理员账户")
    try:
        conn = pymysql.connect(
            host=settings.mysql_admin_host,
            port=settings.mysql_admin_port,
            user=settings.mysql_admin_user,
            password=settings.mysql_admin_password,
            charset="utf8mb4",
            autocommit=True,
            connect_timeout=10,
        )
    except MySQLError as exc:
        raise RuntimeError(f"MySQL 管理员连接失败，请检查主机、端口、用户、密码和网络：{exc}") from exc

    try:
        with conn.cursor() as cursor:
            log(f"创建数据库 {settings.db_name}")
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS {quote_identifier(settings.db_name)} "
                "DEFAULT CHARACTER SET utf8mb4 DEFAULT COLLATE utf8mb4_unicode_ci"
            )

            log(f"创建业务用户 {settings.db_user}")
            cursor.execute(
                "CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s",
                (settings.db_user, "%", settings.db_password),
            )

            log("授予业务用户最小业务权限")
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, ALTER, INDEX "
                f"ON {quote_identifier(settings.db_name)}.* TO %s@%s",
                (settings.db_user, "%"),
            )
            try:
                cursor.execute("FLUSH PRIVILEGES")
            except MySQLError as exc:
                if getattr(exc, "args", [None])[0] == 1227:
                    log("当前管理员缺少 RELOAD 权限，跳过 FLUSH PRIVILEGES；GRANT 已由 MySQL 即时生效")
                else:
                    raise
    except MySQLError as exc:
        raise RuntimeError(f"创建数据库、用户或授权失败，请检查管理员权限：{exc}") from exc
    finally:
        conn.close()


def test_business_connection() -> None:
    settings = get_settings()
    log("测试业务用户连接")
    try:
        conn = pymysql.connect(
            host=settings.db_host,
            port=settings.db_port,
            user=settings.db_user,
            password=settings.db_password,
            database=settings.db_name,
            charset="utf8mb4",
            connect_timeout=10,
        )
        conn.close()
    except MySQLError as exc:
        raise RuntimeError(f"业务用户连接失败，请检查授权、业务密码和数据库可达性：{exc}") from exc


def create_tables() -> None:
    log("创建业务表")
    Base.metadata.create_all(bind=engine)


def seed_tags() -> None:
    log("写入预置标签")
    with SessionLocal() as db:
        existing = set(db.execute(select(Tag.name)).scalars())
        for name in PRESET_TAGS:
            if name not in existing:
                db.add(Tag(name=name, category="knowledge"))
        db.commit()


def import_sample_data() -> None:
    sample = BACKEND_DIR / "data" / "samples" / "2024_spring_morning_sample.json"
    if not sample.exists():
        log("未找到样例数据，跳过导入")
        return
    log("导入样例数据")
    payload = load_import_payload(sample)
    with SessionLocal() as db:
        result = import_payload(db, payload, source_file=str(sample), source_type="json", update_existing=False)
    log(
        "样例导入完成："
        f"新增 {result.success_count}，更新 {result.updated_count}，跳过 {result.skipped_count}，失败 {result.failed_count}"
    )


def main() -> int:
    try:
        create_database_and_user()
        test_business_connection()
        create_tables()
        seed_tags()
        import_sample_data()
        log("数据库初始化完成")
        return 0
    except Exception as exc:
        log(f"初始化失败：{exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
