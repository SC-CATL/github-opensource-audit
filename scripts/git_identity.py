#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 GitHub 账号同步 git 提交身份（user.name / user.email）。

时机：gh 登录后、首次发布前、发布前置检查、审计命中 GIT-IDENTITY 时。
写入只发生在显式 --apply，绝不静默改写已有身份。

用法:
    python git_identity.py                  # 只读预览（缺失/不一致时退出码 2）
    python git_identity.py --apply          # 写入全局配置
    python git_identity.py --apply --local  # 只写入当前仓库
    python git_identity.py --json           # 机器可读输出

取值方式:
    gh api user -> login / id / name / email
    user.name  = name，为空回退 login
    user.email = 公开 email，未公开则用 {id}+{login}@users.noreply.github.com

退出码: 0 已是期望值 / 1 无法获取账号或写入失败 / 2 需要写入（仅预览模式）
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys

GH_CANDIDATES = [
    r"C:\Program Files\GitHub CLI\gh.exe",
    r"C:\Program Files (x86)\GitHub CLI\gh.exe",
    os.path.expanduser(r"~\AppData\Local\GitHubCLI\bin\gh.exe"),
    "/usr/bin/gh",
    "/usr/local/bin/gh",
    "/opt/homebrew/bin/gh",
]


def find_gh():
    found = shutil.which("gh")
    if found:
        return found
    for path in GH_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def run(cmd, cwd=None, timeout=30):
    try:
        proc = subprocess.run(
            cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.decode("utf-8", "replace").strip()


def git_get(key, scope, cwd=None):
    args = ["git", "config"]
    if scope:
        args.append(scope)
    return run(args + ["--get", key], cwd=cwd)


def git_set(key, value, scope, cwd=None):
    args = ["git", "config"]
    if scope:
        args.append(scope)
    return run(args + [key, value], cwd=cwd) is not None


def fetch_github_user(gh):
    raw = run([gh, "api", "user"])
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def status_of(current, suggested):
    if not current:
        return "missing"
    return "match" if current == suggested else "differs"


def is_noreply(email, login):
    if not email or not login:
        return False
    return re.match(r"^(?:\d+\+)?%s@users\.noreply\.github\.com$" % re.escape(login), email, re.I) is not None


def email_matches(current, suggested, login):
    """新旧 noreply 格式（带 id 与不带 id）视为等价，避免无意义改写。"""
    if current == suggested:
        return True
    return is_noreply(current, login) and is_noreply(suggested, login)


def main(argv=None):
    parser = argparse.ArgumentParser(description="从 GitHub 账号同步 git 提交身份")
    parser.add_argument("path", nargs="?", default=".", help="仓库目录，默认当前目录")
    parser.add_argument("--apply", action="store_true", help="写入配置（默认只读预览）")
    parser.add_argument("--local", action="store_true", help="只写入当前仓库，默认写全局")
    parser.add_argument("--public-email", action="store_true",
                        help="使用 GitHub 公开邮箱（默认用 noreply 地址保护隐私）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print("错误：目录不存在 %s" % root, file=sys.stderr)
        return 1

    in_repo = run(["git", "rev-parse", "--is-inside-work-tree"], cwd=root) == "true"
    if args.local and not in_repo:
        print("错误：--local 需要在一个 git 仓库内运行", file=sys.stderr)
        return 1

    scope = "--local" if args.local else "--global"
    # 以生效值为准（commit 使用 effective config），同时记录本地覆盖情况
    current_name = git_get("user.name", None, root) or ""
    current_email = git_get("user.email", None, root) or ""
    local_name = (git_get("user.name", "--local", root) or "") if in_repo else ""
    local_email = (git_get("user.email", "--local", root) or "") if in_repo else ""

    gh = find_gh()
    if not gh:
        print("错误：未找到 gh CLI。请安装 GitHub CLI 并执行 gh auth login。", file=sys.stderr)
        return 1

    user = fetch_github_user(gh)
    if not user:
        print("错误：无法读取 GitHub 账号，请先执行 gh auth login。", file=sys.stderr)
        return 1

    login = user.get("login") or ""
    uid = user.get("id")
    public_email = user.get("email")
    suggested_name = user.get("name") or login
    if public_email and args.public_email:
        suggested_email = public_email
        email_note = "使用 GitHub 公开邮箱（--public-email）"
    else:
        suggested_email = "%s+%s@users.noreply.github.com" % (uid, login)
        email_note = "使用 noreply 地址保护隐私；如需公开邮箱加 --public-email"

    name_status = status_of(current_name, suggested_name)
    email_status = "match" if email_matches(current_email, suggested_email, login) \
        else status_of(current_email, suggested_email)
    if name_status == "match" and email_status == "match":
        overall = "match"
    elif name_status == "missing" or email_status == "missing":
        overall = "missing"
    else:
        overall = "differs"

    payload = {
        "repo": root if in_repo else None,
        "scope": scope.lstrip("-"),
        "status": overall,
        "current": {"name": current_name, "email": current_email},
        "github": {
            "login": login, "id": uid,
            "name": user.get("name"), "email": public_email,
        },
        "suggested": {"name": suggested_name, "email": suggested_email},
        "email_note": email_note,
        "applied": False,
    }

    if overall == "match" and not args.apply:
        payload["applied"] = True
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print("git 身份已是期望值（%s）" % scope.lstrip("-"))
            print("  user.name  = %s" % current_name)
            print("  user.email = %s" % current_email)
        return 0

    if args.json and not args.apply:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2

    if not args.apply:
        print("git 身份状态：%s（%s）" % (
            {"missing": "缺失", "differs": "与 GitHub 账号不一致"}[overall],
            scope.lstrip("-"),
        ))
        print("  user.name  : %s" % (current_name or "未设置"))
        print("  user.email : %s" % (current_email or "未设置"))
        print("")
        print("GitHub 账号")
        print("  login : %s" % login)
        print("  name  : %s" % (user.get("name") or "未设置"))
        print("  email : %s" % (public_email or "未公开"))
        print("")
        print("建议值")
        print("  user.name  = %s" % suggested_name)
        print("  user.email = %s" % suggested_email)
        print("  （%s）" % email_note)
        if scope == "--global" and in_repo and (local_name or local_email):
            print("")
            print("注意：当前仓库存在本地覆盖（local 优先于 global）")
            print("  local user.name  = %s" % (local_name or "未设置"))
            print("  local user.email = %s" % (local_email or "未设置"))
            print("  如需一并统一，加 --local。")
        print("")
        print("写入配置：python scripts/git_identity.py --apply [--local]")
        return 2

    ok_name = git_set("user.name", suggested_name, scope, root)
    ok_email = git_set("user.email", suggested_email, scope, root)
    if not (ok_name and ok_email):
        print("错误：写入 git 配置失败", file=sys.stderr)
        return 1

    if scope == "--global" and in_repo:
        if local_name and local_name != suggested_name:
            print("警告：本仓库本地 user.name=%s 会覆盖全局值，需统一请加 --local。" % local_name)
        if local_email and local_email != suggested_email:
            print("警告：本仓库本地 user.email=%s 会覆盖全局值，需统一请加 --local。" % local_email)

    payload["applied"] = True
    payload["status"] = "match"
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("已写入（%s）" % scope.lstrip("-"))
        print("  user.name  = %s" % suggested_name)
        print("  user.email = %s" % suggested_email)
        print("  （%s）" % email_note)
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
