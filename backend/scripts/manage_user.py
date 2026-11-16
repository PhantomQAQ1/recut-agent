"""管理员命令行：创建账号、解锁、启停、改密、查看列表。

注册不开放，首个管理员也用这里创建。密码用 getpass 交互输入，不经过环境变量。

用法（在 backend 目录下）：
    .venv\\Scripts\\python -m scripts.manage_user create --email you@example.com --name 你的名字 --role admin
    .venv\\Scripts\\python -m scripts.manage_user list
    .venv\\Scripts\\python -m scripts.manage_user unlock --email you@example.com
    .venv\\Scripts\\python -m scripts.manage_user disable --email someone@example.com
    .venv\\Scripts\\python -m scripts.manage_user enable  --email someone@example.com
    .venv\\Scripts\\python -m scripts.manage_user passwd  --email someone@example.com

脚本化（CI / 一次性初始化）可加 --password-stdin 从管道读密码：
    echo "My-Strong-Password" | python -m scripts.manage_user create --email a@b.com --name A --password-stdin
"""

from __future__ import annotations

import argparse
import getpass
import sys

import db
import repositories as repo
import security
from errors import AppError

MIN_NAME = "请填写显示名称"


def _prompt_password() -> str:
    while True:
        first = getpass.getpass("密码：")
        problem = security.password_problem(first)
        if problem:
            print(f"  [x] {problem}")
            continue
        second = getpass.getpass("再输入一次：")
        if first != second:
            print("  [x] 两次输入不一致")
            continue
        return first


def _read_password(args: argparse.Namespace) -> str:
    """交互输入；加了 --password-stdin 时从标准输入读一行，便于脚本化建号。"""
    if getattr(args, "password_stdin", False):
        raw = sys.stdin.readline().rstrip("\r\n")
        problem = security.password_problem(raw)
        if problem:
            raise AppError(problem)
        return raw
    return _prompt_password()


def cmd_create(args: argparse.Namespace) -> int:
    email = repo.normalize_email(args.email)
    if repo.get_user_by_email(email):
        print(f"[x] 邮箱已存在：{email}")
        return 1
    name = (args.name or "").strip() or MIN_NAME
    if len(name) < 1:
        print(f"[x] {MIN_NAME}")
        return 1
    password = _read_password(args)
    user = repo.create_user(
        email=email,
        password_hash=security.hash_password(password),
        display_name=name,
        role=args.role,
    )
    print(f"[OK] 已创建 #{user.id} {user.email}（{user.role}）")
    return 0


def cmd_list(_: argparse.Namespace) -> int:
    users = repo.list_users()
    if not users:
        print("（还没有任何账号，先用 create 建一个）")
        return 0
    print(f"{'ID':<4} {'邮箱':<32} {'名称':<12} {'角色':<7} {'状态':<9} 锁定至")
    for user in users:
        lock = db.to_iso(user.locked_until) or "-"
        status = "locked" if user.is_locked() else user.status
        print(
            f"{user.id:<4} {user.email:<32} {user.display_name:<12} "
            f"{user.role:<7} {status:<9} {lock}"
        )
    return 0


def cmd_unlock(args: argparse.Namespace) -> int:
    user = repo.get_user_by_email(args.email)
    if user is None:
        print(f"[x] 找不到账号：{args.email}")
        return 1
    repo.unlock_user(user.id)
    print(f"[OK] 已解锁并清零失败次数：{user.email}")
    return 0


def cmd_disable(args: argparse.Namespace) -> int:
    return _set_status(args.email, "disabled", "已停用（同时吊销该用户所有会话）")


def cmd_enable(args: argparse.Namespace) -> int:
    return _set_status(args.email, "active", "已启用")


def _set_status(email: str, status: str, message: str) -> int:
    user = repo.get_user_by_email(email)
    if user is None:
        print(f"[x] 找不到账号：{email}")
        return 1
    repo.set_status(user.id, status)
    if status == "disabled":
        repo.revoke_user_sessions(user.id)
    print(f"[OK] {user.email} {message}")
    return 0


def cmd_passwd(args: argparse.Namespace) -> int:
    user = repo.get_user_by_email(args.email)
    if user is None:
        print(f"[x] 找不到账号：{args.email}")
        return 1
    password = _read_password(args)
    repo.set_password(user.id, security.hash_password(password))
    repo.revoke_user_sessions(user.id)
    print(f"[OK] 已重置密码并吊销 {user.email} 的所有会话")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ReCut Agent 账号管理（仅管理员使用）")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="创建账号")
    create.add_argument("--email", required=True)
    create.add_argument("--name", default="")
    create.add_argument("--role", choices=["member", "admin"], default="member")
    create.set_defaults(func=cmd_create)

    sub.add_parser("list", help="列出账号").set_defaults(func=cmd_list)

    unlock = sub.add_parser("unlock", help="解锁账号并清零失败次数")
    unlock.add_argument("--email", required=True)
    unlock.set_defaults(func=cmd_unlock)

    for name, func, help_text in (
        ("disable", cmd_disable, "停用账号并踢下线"),
        ("enable", cmd_enable, "重新启用账号"),
        ("passwd", cmd_passwd, "重置密码（交互输入）"),
    ):
        node = sub.add_parser(name, help=help_text)
        node.add_argument("--email", required=True)
        node.set_defaults(func=func)

    # 脚本化入口：不弹密码输入，直接从标准输入读一行。
    for name in ("create", "passwd"):
        sub.choices[name].add_argument(
            "--password-stdin",
            action="store_true",
            help="从标准输入读取密码，便于 CI/脚本建号",
        )

    return parser


def main(argv: list[str] | None = None) -> int:
    # Windows 控制台默认 GBK，遇到不可编码字符时宁可显示成 ? 也不要抛异常中断。
    try:
        sys.stdout.reconfigure(errors="replace")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    args = build_parser().parse_args(argv)
    db.init_db()
    try:
        return int(args.func(args))
    except AppError as exc:
        print(f"[x] {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
