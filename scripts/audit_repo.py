#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""GitHub 开源发布前审查（只读，无第三方依赖，Python 3.9+）。

用法:
    python audit_repo.py [PATH] [选项]

选项:
    --json OUT            额外写出 JSON 报告
    --md OUT              额外写出 Markdown 报告
    --history             扫描 git 历史（较慢）
    --history-commits N   历史内容扫描的提交上限，默认 300
    --max-size MB         大文件告警阈值，默认 50
    --tracked-only        只扫描已跟踪文件
    --include-untracked   显式包含未跟踪但未忽略的文件（默认已包含）
    --quiet               只输出结论行

退出码:
    0 未发现问题 / 1 存在 P1 或 P2 / 2 存在 P0

设计原则:
    - 只读：不修改、不删除任何文件。
    - 报告中的密钥一律脱敏，只保留首尾各 4 位。
    - 正则只覆盖已知模式，退出码 0 不等于可以发布。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

LEVEL_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
LEVEL_NAME = {"P0": "阻断", "P1": "高", "P2": "中", "P3": "建议"}

MAX_SCAN_BYTES = 2 * 1024 * 1024          # 单文件内容扫描上限
MAX_FINDINGS_PER_PATTERN = 3              # 同一文件同一规则最多报几条
MAX_HISTORY_FINDINGS = 60
WALK_FILE_CAP = 20000                     # 非 git 模式的遍历上限

HEAVY_DIRS = {
    "node_modules", "bower_components", ".venv", "venv", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".nox", ".idea",
    ".gradle", ".next", ".nuxt", ".cache", "htmlcov", ".eggs", ".terraform",
}
LOOSE_DIRS = {"dist", "build", "out", "target", "bin", "obj", "release", "coverage"}

# 文件名直接判 P0
SECRET_FILE_RULES = [
    (r"(?:^|/)\.env$", "环境变量文件"),
    (r"(?:^|/)\.env\.(?!example$|sample$|template$|dist$)[^/]+$", "环境变量文件"),
    (r"\.(?:pem|pfx|p12|jks|keystore|kdbx|ppk)$", "私钥 / 密钥库"),
    (r"(?:^|/)id_(?:rsa|dsa|ecdsa|ed25519)$", "SSH 私钥"),
    (r"(?:^|/)\.git-credentials$", "明文 Git 凭据"),
    (r"(?:^|/)credentials\.json$", "云服务凭据"),
    (r"service[-_]account[^/]*\.json$", "服务账号密钥"),
    (r"(?:^|/)kubeconfig$|(?:^|/)\.kube/config$", "Kubernetes 凭据"),
    (r"\.tfstate(?:\.backup)?$", "Terraform state（含明文密钥）"),
    (r"(?:^|/)secrets?\.(?:ya?ml|json|toml|ini)$", "secrets 文件"),
]

# 文件名判 P1（可能不含凭据，需确认）
CRED_FILE_RULES = [
    (r"(?:^|/)\.npmrc$", "npm 配置（可能含 authToken）"),
    (r"(?:^|/)\.pypirc$", "PyPI 配置（可能含上传令牌）"),
    (r"(?:^|/)\.netrc$|(?:^|/)_netrc$", "netrc 登录凭据"),
    (r"\.postman_environment\.json$", "Postman 环境（可能含 token）"),
]

# 内容正则：(code, 标题, 正则, 级别, 原因, 修复)
SECRET_PATTERNS = [
    ("SEC-PRIVKEY", "私钥文件内容",
     re.compile(r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----"),
     "P0", "私钥公开后任何人都能冒用该身份，且无法追溯。",
     "作废并重新生成密钥对，把私钥移出仓库；已提交过则需清理历史。"),
    ("SEC-AWS", "AWS Access Key",
     re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
     "P0", "可被用于访问或消费 AWS 资源。",
     "在 IAM 中禁用并删除该 Access Key，改用环境变量或 Secrets。"),
    ("SEC-GITHUB", "GitHub Token",
     re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{22,})\b"),
     "P0", "可读写你的仓库、Issue 甚至组织资源。",
     "在 GitHub Settings 中 revoke，重新签发并只放本地。"),
    ("SEC-OPENAI", "AI 平台 API Key",
     re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_\-]{20,}\b"),
     "P0", "可被盗刷产生费用。",
     "在平台后台删除该 Key，改用环境变量。"),
    ("SEC-SLACK", "Slack Token",
     re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b"),
     "P0", "可读取工作区消息或冒充机器人。",
     "在 Slack App 管理页 rotate token。"),
    ("SEC-GOOGLE", "Google API Key",
     re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"),
     "P0", "可能产生计费或访问受限 API。",
     "在 GCP Console 删除该 Key 并限制新 Key 的调用来源。"),
    ("SEC-STRIPE", "Stripe 正式密钥",
     re.compile(r"\b(?:sk|rk)_live_[A-Za-z0-9]{16,}\b"),
     "P0", "可直接发起支付、退款等资金操作。",
     "在 Stripe Dashboard roll key，检查是否有异常交易。"),
    ("SEC-JWT", "JWT 令牌",
     re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\."),
     "P1", "可能包含身份与权限声明，未过期即可直接使用。",
     "确认来源；若为真实令牌则作废并改从环境变量读取。"),
    ("SEC-GENERIC", "疑似硬编码口令 / 令牌",
     re.compile(r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|client[_-]?secret|auth[_-]?key)\b\s*[:=]\s*[\"']([^\"'\s]{8,})[\"']"),
     "P1", "写死在源码里的凭据同样会进入历史，删除提交也无法挽回。",
     "改读环境变量；若为真实凭据，先轮换再清理。"),
    ("SEC-CONNSTR", "连接串中含口令",
     re.compile(r"(?i)\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis|amqp|mssql)://[^\s:@/]+:([^\s@/]{3,})@"),
     "P0", "连接串里带明文密码，可直接连上数据库或消息队列。",
     "改为环境变量注入，轮换数据库密码。"),
    ("SEC-PRIVIP", "内网 IP 地址",
     re.compile(r"\b(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}\b"),
     "P2", "暴露内网拓扑，便于攻击者定位目标。",
     "改为 localhost、环境变量或 example 地址。"),
    ("SEC-INTDOMAIN", "内网域名",
     re.compile(r"(?<![.\w*/-])\b[a-z0-9][a-z0-9\-]*(?:\.[a-z0-9\-]+)*\.(?:local|corp|internal|intranet|lan)\b", re.I),
     "P2", "暴露内部系统命名与访问路径。",
     "改为占位域名，如 db.example.com。"),
    ("SEC-CNMOBILE", "中国手机号",
     re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),
     "P2", "可能是真实用户数据，涉及个人信息合规。",
     "替换为合成数据，确认是否已提交真实数据（是则升 P0）。"),
    ("SEC-CNID", "身份证号",
     re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),
     "P1", "属于敏感个人信息，公开即违规。",
     "立即替换为合成数据；若为真实数据按 P0 处理并评估合规责任。"),
]

PLACEHOLDER_MARKERS = (
    "example.com", "example.org", "your-", "your_", "yourkey", "<", ">",
    "changeme", "change-me", "placeholder", "dummy", "fake", "redacted",
    "****", "todo", "xxxx", "sk_test_", "sk-test", "localhost", "127.0.0.1",
    "0.0.0.0", "sample", "template", "insert_", "replace_me",
    "user:pass", "user:password", ":pass@", ":password@", "old_pass",
    "host/db", "@host", "db.example", "password123",
)

# 行内豁免标记：命中行包含这些字样时跳过（用于文档示例、测试夹具）
IGNORE_MARKERS = ("audit:allow", "gitleaks:allow", "pragma: allowlist secret", "nosec")

# 需要脱敏的规则；内网 IP、域名等非凭据信息保留原文，方便定位
MASK_CODES = {
    "SEC-PRIVKEY", "SEC-AWS", "SEC-GITHUB", "SEC-OPENAI", "SEC-SLACK",
    "SEC-GOOGLE", "SEC-STRIPE", "SEC-JWT", "SEC-GENERIC", "SEC-CONNSTR",
}

# 已知占位号码
PLACEHOLDER_VALUES = {
    "13800138000", "13900000000", "110101199001011234", "110101199003078515",
}

LICENSE_CANDIDATES = [
    "LICENSE", "LICENSE.md", "LICENSE.txt", "LICENSE.rst",
    "LICENCE", "LICENCE.md", "COPYING", "COPYING.txt", "UNLICENSE",
]

SPDX_SIGNATURES = [
    ("AGPL-3.0", [r"GNU AFFERO GENERAL PUBLIC LICENSE", r"Version 3"]),
    ("LGPL-3.0", [r"GNU LESSER GENERAL PUBLIC LICENSE", r"Version 3"]),
    ("LGPL-2.1", [r"GNU LESSER GENERAL PUBLIC LICENSE", r"Version 2\.1"]),
    ("GPL-3.0", [r"GNU GENERAL PUBLIC LICENSE", r"Version 3"]),
    ("GPL-2.0", [r"GNU GENERAL PUBLIC LICENSE", r"Version 2"]),
    ("Apache-2.0", [r"Apache License", r"Version 2\.0"]),
    ("MPL-2.0", [r"Mozilla Public License Version 2\.0"]),
    ("BSD-3-Clause", [r"Redistribution and use in source and binary forms", r"Neither the name of"]),
    ("BSD-2-Clause", [r"Redistribution and use in source and binary forms"]),
    ("ISC", [r"ISC License|Permission to use, copy, modify, and(?:/or)? distribute"]),
    ("Unlicense", [r"free and unencumbered software released into the public domain"]),
    ("CC0-1.0", [r"CC0 1\.0 Universal"]),
    ("MIT", [r"Permission is hereby granted, free of charge"]),
]

LICENSE_NAMES = {
    # 顺序重要：agpl / lgpl 含 "gpl" 子串，必须先匹配
    "agpl": "AGPL", "lgpl": "LGPL", "mit": "MIT", "apache": "Apache-2.0",
    "gpl": "GPL", "bsd": "BSD", "mpl": "MPL-2.0", "isc": "ISC",
    "unlicense": "Unlicense", "cc0": "CC0-1.0",
}

# 每次审查都必须向作者确认本次版本采用的许可证，不允许根据历史推断
LICENSE_CHOICES = [
    ("MIT", "宽松，最通用"),
    ("Apache-2.0", "宽松 + 专利授权，企业友好"),
    ("BSD-3-Clause", "宽松，禁止用作者名背书"),
    ("MPL-2.0", "弱传染，仅修改文件需开源"),
    ("LGPL-3.0-only", "弱传染，库场景"),
    ("GPL-3.0-only", "强传染，衍生作品必须开源"),
    ("AGPL-3.0-only", "最强传染，网络服务也算分发"),
    ("Unlicense", "放弃版权，公共领域"),
    ("Proprietary", "保留所有权利，不授权他人使用"),
]


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    level: str
    code: str
    title: str
    path: str = ""
    line: int = 0
    evidence: str = ""
    why: str = ""
    fix: str = ""


@dataclass
class Baseline:
    root: str = ""
    is_git: bool = False
    branch: str = ""
    commits: int = 0
    tracked: int = 0
    untracked: int = 0
    scanned: int = 0
    total_size: int = 0
    remotes: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def mask(text, keep=4):
    text = str(text).strip()
    if len(text) <= keep * 2:
        return text[:2] + "****"
    return text[:keep] + "****" + text[-keep:]


def is_placeholder(value):
    low = value.lower()
    if value in PLACEHOLDER_VALUES:
        return True
    return any(marker in low for marker in PLACEHOLDER_MARKERS)


def has_key_body(text, pos):
    """私钥头后面必须有足够长的密钥体，否则视为文档示例。"""
    return bool(re.search(r"[A-Za-z0-9+/=]{40,}", text[pos:pos + 400]))


def load_excludes(root, extra):
    patterns = list(extra or [])
    path = os.path.join(root, ".auditignore")
    if os.path.isfile(path):
        for line in read_text(path).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
    return patterns


def is_excluded(rel, patterns):
    from fnmatch import fnmatch
    for pattern in patterns:
        base = pattern.rstrip("/")
        if fnmatch(rel, base) or fnmatch(rel, base + "/*") or rel.startswith(base + "/"):
            return True
    return False


def human_size(num):
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return "%.1f %s" % (num, unit) if unit != "B" else "%d B" % num
        num /= 1024.0
    return "%d B" % num


def git(root, args, timeout=180):
    """执行 git 命令，返回 (ok, stdout_bytes)。"""
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=root,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError):
        return False, b""
    return proc.returncode == 0, proc.stdout


def git_list(root, args):
    ok, out = git(root, args)
    if not ok:
        return None
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def read_text(path, limit=None):
    # utf-8-sig 兼容 Windows 下带 BOM 的文件，否则 JSON 解析会失败
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as fh:
            return fh.read() if limit is None else fh.read(limit)
    except OSError:
        return ""


def is_binary(path):
    try:
        with open(path, "rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return True


def find_license_file(root):
    entries = {n.lower(): n for n in os.listdir(root)} if os.path.isdir(root) else {}
    for cand in LICENSE_CANDIDATES:
        if cand.lower() in entries:
            return entries[cand.lower()]
    return None


def detect_spdx(text):
    low = text
    for name, patterns in SPDX_SIGNATURES:
        if all(re.search(p, low, re.I) for p in patterns):
            return name
    return None


def normalize_spdx(value):
    value = (value or "").strip().strip('"').strip("'")
    value = value.split(" OR ")[0].split(" AND ")[0].strip()
    mapping = {
        "mit": "MIT", "apache-2.0": "Apache-2.0", "apache 2.0": "Apache-2.0",
        "bsd-3-clause": "BSD-3-Clause", "bsd-2-clause": "BSD-2-Clause",
        "gpl-3.0": "GPL-3.0", "gpl-3.0-only": "GPL-3.0",
        "gpl-3.0-or-later": "GPL-3.0", "gpl-2.0": "GPL-2.0",
        "agpl-3.0": "AGPL-3.0", "agpl-3.0-only": "AGPL-3.0",
        "lgpl-3.0": "LGPL-3.0", "mpl-2.0": "MPL-2.0", "isc": "ISC",
        "unlicense": "Unlicense", "cc0-1.0": "CC0-1.0",
    }
    return mapping.get(value.lower(), value)


# ---------------------------------------------------------------------------
# 文件收集
# ---------------------------------------------------------------------------

def collect_files(root, tracked_only):
    """返回 (files, untracked_set)。files 是相对路径列表（/ 分隔）。"""
    is_git, _ = git(root, ["rev-parse", "--is-inside-work-tree"])
    if is_git:
        tracked = git_list(root, ["ls-files", "-z"]) or []
        untracked = []
        if not tracked_only:
            untracked = git_list(root, ["ls-files", "-z", "--others", "--exclude-standard"]) or []
        return tracked, untracked

    # 非 git：遍历目录，剪掉重依赖目录
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        rel_dir = os.path.relpath(dirpath, root).replace("\\", "/")
        if rel_dir == ".":
            rel_dir = ""
        for name in filenames:
            rel = "%s/%s" % (rel_dir, name) if rel_dir else name
            files.append(rel)
            if len(files) >= WALK_FILE_CAP:
                return files, []
    return files, []


# ---------------------------------------------------------------------------
# 各项检查
# ---------------------------------------------------------------------------

def check_secret_files(files, findings):
    seen = set()
    for rel in files:
        low = rel.lower()
        for pattern, label in SECRET_FILE_RULES:
            if re.search(pattern, low):
                if rel in seen:
                    break
                seen.add(rel)
                findings.append(Finding(
                    "P0", "SEC-FILE", "仓库内含 %s" % label, rel, 0, "",
                    "该文件通常包含可直接使用的凭据，推送即等于公开。",
                    "移出仓库并加入 .gitignore；若已提交，先轮换凭据再清理历史。",
                ))
                break
        else:
            for pattern, label in CRED_FILE_RULES:
                if re.search(pattern, low):
                    if rel in seen:
                        break
                    seen.add(rel)
                    findings.append(Finding(
                        "P1", "SEC-FILE", "仓库内含 %s" % label, rel, 0, "",
                        "该类配置常带访问令牌，公开后可能被直接使用。",
                        "确认无真实令牌；建议只提交 .example 模板。",
                    ))
                    break


def check_artifact_dirs(files, findings):
    heavy, loose = {}, {}
    for rel in files:
        parts = rel.split("/")
        for idx, part in enumerate(parts[:-1]):
            if part in HEAVY_DIRS:
                heavy.setdefault("/".join(parts[:idx + 1]), 0)
                heavy["/".join(parts[:idx + 1])] += 1
                break
            if part in LOOSE_DIRS:
                loose.setdefault("/".join(parts[:idx + 1]), 0)
                loose["/".join(parts[:idx + 1])] += 1
                break

    for directory, count in sorted(heavy.items()):
        findings.append(Finding(
            "P1", "HYG-ARTIFACT", "依赖 / 缓存目录被跟踪", directory, 0,
            "%d 个文件" % count,
            "体积暴涨、评审噪音，且可能夹带本机路径与令牌。",
            "git rm -r --cached %s，并加入 .gitignore。" % directory,
        ))
    for directory, count in sorted(loose.items()):
        findings.append(Finding(
            "P2", "HYG-ARTIFACT", "疑似构建产物目录被跟踪", directory, 0,
            "%d 个文件" % count,
            "构建产物不应入库；若该目录其实是源码目录，请忽略本条。",
            "确认后执行 git rm -r --cached %s 并加入 .gitignore。" % directory,
        ))


JUNK_RE = re.compile(
    r"(?:^|/)(?:\.DS_Store|Thumbs\.db|ehthumbs\.db|desktop\.ini|\.Spotlight-V100|\.Trashes)$", re.I)
COMPILED_RE = re.compile(r"\.(?:pyc|pyo|class|o|obj|pdb|ilk|swp|swo)$", re.I)
LOGFILE_RE = re.compile(r"\.(?:log|tmp|bak|orig|rej)$", re.I)
DATAFILE_RE = re.compile(r"\.(?:db|sqlite|sqlite3|mdb|dump|sql\.gz)$", re.I)
BINARY_RE = re.compile(
    r"\.(?:zip|tar|gz|bz2|xz|7z|rar|iso|dmg|mp4|mov|avi|mkv|psd|ai|pt|pth|onnx|safetensors|ckpt|h5|pb|exe|msi)$",
    re.I)


def check_file_hygiene(root, files, findings, max_size_mb):
    warn = max_size_mb * 1024 * 1024
    hard = 100 * 1024 * 1024
    soft = 5 * 1024 * 1024
    for rel in files:
        abspath = os.path.join(root, rel)
        if not os.path.isfile(abspath):
            continue

        if JUNK_RE.search(rel):
            findings.append(Finding(
                "P1", "HYG-JUNK", "系统 / 编辑器残留文件", rel, 0, "",
                "与项目无关，跨平台会造成冲突和噪音。",
                "git rm --cached %s 并加入 .gitignore。" % rel,
            ))
        elif COMPILED_RE.search(rel):
            findings.append(Finding(
                "P2", "HYG-JUNK", "编译产物被跟踪", rel, 0, "",
                "可由源码重新生成，不应入库。",
                "git rm --cached %s 并加入 .gitignore。" % rel,
            ))
        elif LOGFILE_RE.search(rel):
            findings.append(Finding(
                "P2", "HYG-JUNK", "日志 / 临时文件", rel, 0, "",
                "日志常含 IP、邮箱、令牌与请求体。",
                "git rm --cached %s 并加入 .gitignore。" % rel,
            ))
        elif DATAFILE_RE.search(rel):
            findings.append(Finding(
                "P1", "SEC-DATA", "数据库 / 数据转储文件", rel, 0, "",
                "极可能包含真实用户数据，属于 P0 风险来源。",
                "移出仓库；确认内容是否为真实数据，若是则按 P0 处理。",
            ))

        try:
            size = os.path.getsize(abspath)
        except OSError:
            continue

        if size > hard:
            findings.append(Finding(
                "P1", "SIZE-BLOCK", "单文件超过 100MB", rel, 0, human_size(size),
                "GitHub 会直接拒绝推送。",
                "改用 Release 附件或 Git LFS；已提交则需清理历史。",
            ))
        elif size > warn:
            findings.append(Finding(
                "P1", "SIZE-LARGE", "单文件超过 %dMB" % max_size_mb, rel, 0, human_size(size),
                "GitHub 会给出警告，且文件永久留在历史里，clone 变慢。",
                "改用 Release 附件或 Git LFS。",
            ))
        elif size > soft:
            findings.append(Finding(
                "P3", "SIZE-NOTE", "文件偏大", rel, 0, human_size(size),
                "会拖慢 clone；如果是素材或数据集，考虑外置。",
                "确认是否需要入库。",
            ))

        if BINARY_RE.search(rel) and size > soft:
            findings.append(Finding(
                "P2", "SIZE-BINARY", "大体积二进制文件", rel, 0, human_size(size),
                "二进制无法有效 diff，且体积会永久累积。",
                "改放 Release 附件或使用 Git LFS。",
            ))


def iter_secret_hits(text, start_line=1):
    """扫描文本中的敏感模式，产出 (code, title, level, value, line_no, why, fix)。

    工作区与历史扫描共用同一套误报过滤：占位符、行内豁免、私钥密钥体校验。
    """
    lines = text.splitlines()
    for code, title, pattern, level, why, fix in SECRET_PATTERNS:
        hits = 0
        for match in pattern.finditer(text):
            value = match.group(1) if match.groups() else match.group(0)
            if is_placeholder(value) or is_placeholder(match.group(0)):
                continue
            offset = text.count("\n", 0, match.start())
            line_text = lines[offset].lower() if offset < len(lines) else ""
            if any(marker in line_text for marker in IGNORE_MARKERS):
                continue
            if code == "SEC-PRIVKEY" and not has_key_body(text, match.end()):
                continue
            yield code, title, level, value, start_line + offset, why, fix
            hits += 1
            if hits >= MAX_FINDINGS_PER_PATTERN:
                break


def check_content(root, files, findings):
    for rel in files:
        abspath = os.path.join(root, rel)
        if not os.path.isfile(abspath):
            continue
        try:
            size = os.path.getsize(abspath)
        except OSError:
            continue
        if size > MAX_SCAN_BYTES or size == 0 or is_binary(abspath):
            continue

        text = read_text(abspath)
        if not text:
            continue

        for code, title, level, value, line_no, why, fix in iter_secret_hits(text):
            findings.append(Finding(
                level, code, title, rel, line_no,
                mask(value) if code in MASK_CODES else value, why, fix,
            ))

        emails = set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text))
        real = {e for e in emails if not e.lower().endswith(("example.com", "example.org", "test.com"))}
        if len(real) >= 5:
            findings.append(Finding(
                "P2", "SEC-EMAILS", "文件中含大量邮箱地址", rel, 0,
                "%d 个不同邮箱" % len(real),
                "可能是真实用户或员工名单，涉及个人信息合规。",
                "确认来源；真实名单移出仓库并改用合成数据。",
            ))


def check_ignore(root, files, findings):
    ignore_path = os.path.join(root, ".gitignore")
    if not os.path.isfile(ignore_path):
        findings.append(Finding(
            "P1", "GIT-IGNORE-MISSING", "缺少 .gitignore", ".gitignore", 0, "",
            "构建产物、依赖目录与密钥文件会持续被误提交。",
            "按技术栈生成 .gitignore，至少覆盖 .env、依赖目录、构建输出。",
        ))
        return
    content = read_text(ignore_path)
    if ".env" not in content:
        findings.append(Finding(
            "P2", "GIT-IGNORE-ENV", ".gitignore 未忽略 .env", ".gitignore", 0, "",
            "环境变量文件是最常见的泄露源。",
            "添加一行 .env，同时提供 .env.example 模板。",
        ))

    ignored_tracked = git_list(root, ["ls-files", "-z", "-ci", "--exclude-standard"])
    if ignored_tracked:
        preview = "、".join(ignored_tracked[:5])
        if len(ignored_tracked) > 5:
            preview += " 等"
        findings.append(Finding(
            "P1", "GIT-IGNORE-FAILED", "已跟踪文件违反 .gitignore",
            preview, 0, "共 %d 个" % len(ignored_tracked),
            ".gitignore 只对未跟踪文件生效，这些文件仍会被推送。",
            "执行 git rm -r --cached <路径> 后提交。",
        ))


def prompt_license(detected):
    """交互式询问本次版本采用的许可证；非交互环境由调用方跳过。"""
    default_idx = 1
    print("")
    print("=" * 60)
    print("本次版本采用哪种许可证？")
    print("=" * 60)
    for idx, (name, note) in enumerate(LICENSE_CHOICES, 1):
        mark = ""
        if detected and normalize_spdx(name).lower() == detected.lower():
            mark = "   <- 当前 LICENSE 检测结果"
            default_idx = idx
        print("  %d) %-16s %s%s" % (idx, name, note, mark))
    print("  也可直接输入 SPDX 标识（如 CC-BY-4.0）")
    try:
        raw = input("选择编号 [默认 %d]: " % default_idx).strip()
    except (EOFError, KeyboardInterrupt):
        print("")
        return None
    if not raw:
        return LICENSE_CHOICES[default_idx - 1][0]
    if raw.isdigit():
        idx = int(raw)
        if 1 <= idx <= len(LICENSE_CHOICES):
            return LICENSE_CHOICES[idx - 1][0]
        return None
    return raw


def check_license_intent(findings, declared, detected):
    """校验作者为本次版本声明的许可证与实际 LICENSE 文件是否一致。"""
    if not declared:
        findings.append(Finding(
            "P2", "LIC-UNCONFIRMED", "未确认本次版本采用的许可证", "LICENSE", 0, "",
            "许可证可能随版本变更，必须由作者明确本次发布采用哪一种；未确认时无法判断授权声明是否成立。",
            "回答许可证问题后重新运行，或显式传入 --license <SPDX>。",
        ))
        return

    declared_norm = normalize_spdx(declared)
    if declared_norm.lower() == "proprietary":
        findings.append(Finding(
            "P1", "LIC-PROPRIETARY", "本次版本声明为保留所有权利", "LICENSE", 0, declared,
            "保留所有权利与公开到 GitHub 的目标冲突，他人无法合法使用、修改或分发。",
            "确认是否真要开源；若要开源，改选 MIT / Apache-2.0 等并补充 LICENSE 全文。",
        ))
        return

    if detected and declared_norm.lower() != detected.lower():
        findings.append(Finding(
            "P1", "LIC-MISMATCH", "声明的许可证与 LICENSE 文件不一致", "LICENSE", 0,
            "声明 %s，文件为 %s" % (declared, detected),
            "本次版本对外声明的授权与实际文件不符，使用者无法判断适用条款。",
            "按声明把 LICENSE 全文替换为 %s，并同步 README 与包清单。" % declared,
        ))


def check_required(root, findings, declared=None):
    entries = os.listdir(root) if os.path.isdir(root) else []
    lower = {name.lower(): name for name in entries}

    if not any(name.startswith("readme") for name in lower):
        findings.append(Finding(
            "P1", "DOC-README", "缺少 README", "README.md", 0, "",
            "没有 README 的项目无法被理解和使用，等于没有入口。",
            "新增 README.md，至少包含定位、安装、最小示例、许可证四节。",
        ))

    if not find_license_file(root):
        fix = "新增 LICENSE，填入标准全文（推荐 MIT），并同步包清单的 license 字段。"
        if declared and normalize_spdx(declared).lower() != "proprietary":
            fix = "按本次版本声明新增 LICENSE，填入 %s 标准全文，并同步 README 与包清单。" % declared
        findings.append(Finding(
            "P1", "LIC-LICENSE", "缺少 LICENSE 文件", "LICENSE", 0, "",
            "没有许可证时默认保留所有权利，任何人都不能合法使用、修改或分发你的代码。",
            fix,
        ))

    recommended = [
        ("CONTRIBUTING", ["contributing.md", "contributing.rst", "contributing.txt"], "P2",
         "CONTRIBUTING.md", "缺少 CONTRIBUTING.md",
         "外部贡献者不知道如何搭环境、跑测试、提 PR。"),
        ("CODE_OF_CONDUCT", ["code_of_conduct.md", "code-of-conduct.md"], "P2",
         "CODE_OF_CONDUCT.md", "缺少 CODE_OF_CONDUCT.md",
         "社区型项目缺少行为准则，冲突处理无依据。"),
        ("SECURITY", ["security.md"], "P2",
         "SECURITY.md", "缺少 SECURITY.md",
         "研究者不知道如何私下报告漏洞，只能开公开 issue。"),
        ("CHANGELOG", ["changelog.md", "changes.md", "history.md"], "P3",
         "CHANGELOG.md", "缺少 CHANGELOG.md",
         "版本变更不可追溯，用户升级时无法判断风险。"),
        ("NOTICE", ["notice", "notice.md", "notice.txt", "third_party_notices.md"], "P3",
         "THIRD_PARTY_NOTICES.md", "缺少第三方许可声明",
         "若内含第三方代码或素材，需保留其许可证与版权声明。"),
        ("CITATION", ["citation.cff"], "P3",
         "CITATION.cff", "缺少 CITATION.cff",
         "学术用途的项目缺少规范引用信息。"),
        (".editorconfig", [".editorconfig"], "P3",
         ".editorconfig", "缺少 .editorconfig",
         "不同编辑器的缩进与换行不一致，产生无意义 diff。"),
    ]
    for label, candidates, level, display, title, why in recommended:
        if not any(c in lower for c in candidates):
            findings.append(Finding(
                level, "DOC-RECOMMENDED", title, display, 0, "", why,
                "按需补充；小项目可只补 CONTRIBUTING 与 SECURITY。",
            ))

    gh = os.path.join(root, ".github")
    if os.path.isdir(gh):
        gh_entries = {n.lower() for n in os.listdir(gh)}
        if "issue_template" not in gh_entries:
            findings.append(Finding(
                "P3", "DOC-RECOMMENDED", "缺少 Issue 模板", ".github/ISSUE_TEMPLATE/", 0, "",
                "issue 质量参差，复现信息经常缺失。", "添加 bug_report.yml 与 feature_request.yml。",
            ))
        if "pull_request_template.md" not in gh_entries:
            findings.append(Finding(
                "P3", "DOC-RECOMMENDED", "缺少 PR 模板", ".github/PULL_REQUEST_TEMPLATE.md", 0, "",
                "PR 描述不统一，评审成本上升。", "添加 PR 模板，要求说明变更与测试方式。",
            ))
        if "workflows" not in gh_entries:
            findings.append(Finding(
                "P3", "DOC-RECOMMENDED", "缺少 CI workflow", ".github/workflows/", 0, "",
                "没有自动化测试，回归只能靠人工发现。", "添加最小 CI：push/PR 时跑测试与 lint。",
            ))
    else:
        findings.append(Finding(
            "P3", "DOC-RECOMMENDED", "缺少 .github 目录",
            ".github/", 0, "",
            "没有 Issue/PR 模板与 CI，协作与质量保障缺位。",
            "添加 .github/ISSUE_TEMPLATE、PULL_REQUEST_TEMPLATE.md 与 workflows。",
        ))


def check_readme(root, findings, spdx):
    entries = os.listdir(root) if os.path.isdir(root) else []
    name = next((n for n in entries if n.lower().startswith("readme")), None)
    if not name:
        return
    text = read_text(os.path.join(root, name))
    if len(text.strip()) < 400:
        findings.append(Finding(
            "P2", "DOC-README-WEAK", "README 内容过短", name, 0,
            "%d 字符" % len(text.strip()),
            "读者无法判断项目用途与用法。",
            "补充定位、安装、最小示例、配置说明、许可证。",
        ))

    sections = [
        ("安装方式", r"(?im)^#{1,4}[^\n]*(?:install|installation|setup|getting started|快速开始|安装)", "P2"),
        ("使用示例", r"(?im)^#{1,4}[^\n]*(?:usage|examples?|quick ?start|使用|示例|用法)", "P2"),
        ("许可证", r"(?im)^#{1,4}[^\n]*(?:licen[cs]e|许可|授权)", "P2"),
        ("贡献指引", r"(?im)^#{1,4}[^\n]*(?:contribut\w*|贡献)", "P3"),
    ]
    for label, pattern, level in sections:
        if not re.search(pattern, text):
            findings.append(Finding(
                level, "DOC-README-SECTION", "README 缺少%s" % label, name, 0, "",
                "读者需要自己猜，导致重复提问或直接放弃。",
                "补充「%s」小节。" % label,
            ))

    if "```" not in text:
        findings.append(Finding(
            "P3", "DOC-README-SECTION", "README 缺少代码示例块", name, 0, "",
            "没有可复制的最小示例，上手成本高。", "添加一段可直接运行的代码块。",
        ))

    if spdx:
        lic_match = re.search(r"(?im)^#{1,4}[^\n]*(?:licen[cs]e|许可|授权)", text)
        if lic_match:
            section = text[lic_match.start():lic_match.start() + 800].lower()
            for word, lic in LICENSE_NAMES.items():
                if word in section and lic.split("-")[0].lower() not in spdx.lower():
                    findings.append(Finding(
                        "P2", "META-LICENSE", "README 许可证与 LICENSE 文件不一致", name, 0,
                        "README 提到 %s，LICENSE 实际为 %s" % (lic, spdx),
                        "两处不一致会让使用者无法判断实际授权。",
                        "统一为 %s，并同步包清单的 license 字段。" % spdx,
                    ))
                    break


def check_manifest(root, findings, spdx):
    findings_license = None
    checked = False

    pkg = os.path.join(root, "package.json")
    if os.path.isfile(pkg):
        checked = True
        try:
            data = json.loads(read_text(pkg))
        except (ValueError, TypeError):
            data = {}
        lic = data.get("license")
        if not lic and isinstance(data.get("licenses"), list) and data["licenses"]:
            first = data["licenses"][0]
            lic = first.get("type") if isinstance(first, dict) else first
        findings_license = lic
        if not lic:
            findings.append(Finding(
                "P2", "META-LICENSE", "package.json 缺少 license 字段", "package.json", 0, "",
                "元数据缺失会让依赖扫描工具无法识别授权。",
                "添加 \"license\": \"%s\"。" % (spdx or "MIT"),
            ))
        if data.get("private") is True:
            findings.append(Finding(
                "P2", "META-PRIVATE", "package.json 标记为私有包", "package.json", 0, "",
                "private: true 表示这个包不打算发布，与开源定位冲突。",
                "确认是否有意开源；若是，移除 private 字段。",
            ))
        publish = data.get("publishConfig") or {}
        registry = str(publish.get("registry", ""))
        if registry and "registry.npmjs.org" not in registry:
            findings.append(Finding(
                "P2", "META-REGISTRY", "publishConfig 指向非公开 registry",
                "package.json", 0, mask(registry),
                "可能暴露内网地址，且用户无法正常安装。",
                "改为 https://registry.npmjs.org 或移除该字段。",
            ))
        if not data.get("repository"):
            findings.append(Finding(
                "P3", "META-REPO", "package.json 缺少 repository 字段", "package.json", 0, "",
                "包页面无法跳转到源码仓库。", "添加 repository 字段指向真实地址。",
            ))

    pyproject = os.path.join(root, "pyproject.toml")
    if os.path.isfile(pyproject):
        checked = True
        text = read_text(pyproject)
        m = re.search(r"(?m)^\s*license\s*=\s*(?:\{\s*text\s*=\s*)?[\"']([^\"']+)[\"']", text)
        license_from_file = bool(re.search(r"(?m)^\s*license\s*=\s*\{\s*file\s*=", text))
        findings_license = m.group(1) if m else None
        has_classifier = bool(re.search(r"License\s*::", text))
        if not m and not license_from_file and not has_classifier:
            findings.append(Finding(
                "P2", "META-LICENSE", "pyproject.toml 缺少 license 字段", "pyproject.toml", 0, "",
                "元数据缺失会让依赖扫描工具无法识别授权。",
                "在 [project] 下添加 license = \"%s\"。" % (spdx or "MIT"),
            ))
        if "git+ssh://" in text or "git+http://" in text:
            findings.append(Finding(
                "P2", "META-PRIVDEP", "依赖指向私有 / 不安全源", "pyproject.toml", 0, "",
                "外部用户无法安装，且暴露内网地址。", "改为公开的包名与版本约束。",
            ))

    cargo = os.path.join(root, "Cargo.toml")
    if os.path.isfile(cargo):
        checked = True
        text = read_text(cargo)
        m = re.search(r"(?m)^\s*license\s*=\s*[\"']([^\"']+)[\"']", text)
        findings_license = m.group(1) if m else None
        if not m:
            findings.append(Finding(
                "P2", "META-LICENSE", "Cargo.toml 缺少 license 字段", "Cargo.toml", 0, "",
                "crates.io 发布需要该字段。", "添加 license = \"%s\"。" % (spdx or "MIT"),
            ))

    composer = os.path.join(root, "composer.json")
    if os.path.isfile(composer):
        checked = True
        try:
            data = json.loads(read_text(composer))
        except (ValueError, TypeError):
            data = {}
        findings_license = data.get("license")
        if not findings_license:
            findings.append(Finding(
                "P2", "META-LICENSE", "composer.json 缺少 license 字段", "composer.json", 0, "",
                "元数据缺失，Packagist 无法识别授权。", "添加 license 字段。",
            ))

    if checked and findings_license and spdx:
        declared = normalize_spdx(str(findings_license))
        if declared.lower() != spdx.lower():
            findings.append(Finding(
                "P2", "META-MISMATCH", "包清单许可证与 LICENSE 文件不一致",
                "包清单", 0, "声明 %s，实际 %s" % (declared, spdx),
                "使用者无法判断真实授权条款。",
                "统一为 %s。" % spdx,
            ))


def check_history(root, findings, max_commits):
    ok, out = git(root, ["rev-list", "--all", "--objects"], timeout=180)
    if not ok:
        return

    seen_paths = set()
    for raw in out.decode("utf-8", "replace").splitlines():
        parts = raw.split(" ", 1)
        if len(parts) < 2:
            continue
        path = parts[1].strip()
        if not path or path in seen_paths:
            continue
        seen_paths.add(path)
        low = path.lower()
        for pattern, label in SECRET_FILE_RULES:
            if re.search(pattern, low):
                findings.append(Finding(
                    "P0", "HIST-SECRET", "历史中存在 %s" % label, path, 0,
                    "该路径在历史中出现过",
                    "任何 clone 过该仓库的人都持有该内容，删除当前文件无法挽回。",
                    "先轮换凭据，再用 git filter-repo 清理历史并 force push。",
                ))
                break

    ok, out = git(
        root,
        ["log", "-p", "--all", "--unified=0", "--no-color", "--no-renames",
         "--max-count=%d" % max_commits],
        timeout=300,
    )
    if not ok or len(out) > 60 * 1024 * 1024:
        findings.append(Finding(
            "P3", "HIST-SKIP", "历史内容扫描未完成", "", 0,
            "输出过大或执行超时" if ok else "git log 执行失败",
            "本次只检查了历史路径，未逐行检查历史内容。",
            "用 gitleaks / trufflehog 做完整历史扫描。",
        ))
        return

    current_file = ""
    current_commit = ""
    block = []
    block_start = 1
    seen = set()
    count = 0
    stop = False

    def flush():
        """把当前 hunk 的连续新增行拼成块再扫描，保证私钥密钥体校验有效。"""
        nonlocal block, count, stop
        if not block or stop:
            block = []
            return
        text = "\n".join(block)
        for code, title, level, value, line_no, _why, _fix in iter_secret_hits(text, block_start):
            key = (code, current_file)
            if key in seen:
                continue
            seen.add(key)
            findings.append(Finding(
                "P0" if level == "P0" else "P1", "HIST-CONTENT",
                "历史提交中出现 %s" % title, current_file, 0,
                "commit %s：%s" % (current_commit, mask(value) if code in MASK_CODES else value),
                "即使当前工作区已删除，历史版本仍可读取。",
                "先轮换凭据，再用 git filter-repo --replace-text 清理。",
            ))
            count += 1
            if count >= MAX_HISTORY_FINDINGS:
                stop = True
                break
        block = []

    for raw in out.decode("utf-8", "replace").splitlines():
        if raw.startswith("commit "):
            flush()
            current_commit = raw[7:14]
            continue
        if raw.startswith("+++ b/"):
            flush()
            current_file = raw[6:]
            continue
        if raw.startswith("@@"):
            flush()
            match = re.search(r"\+(\d+)", raw)
            block_start = int(match.group(1)) if match else 1
            continue
        if raw.startswith("+") and not raw.startswith("+++"):
            block.append(raw[1:])
            continue
        flush()
        if stop:
            break

    flush()


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------

def verdict_of(findings):
    levels = {f.level for f in findings}
    if "P0" in levels:
        return "不可发布", "❌"
    if "P1" in levels or "P2" in levels:
        return "修复后可发布", "⚠️"
    return "可发布", "✅"


def render_markdown(baseline, findings, root, declared=None):
    counts = {lvl: sum(1 for f in findings if f.level == lvl) for lvl in LEVEL_ORDER}
    label, icon = verdict_of(findings)

    lines = []
    lines.append("# GitHub 开源发布审查报告")
    lines.append("")
    lines.append("- **目标**：`%s`" % baseline.root)
    lines.append("- **模式**：%s" % ("git 仓库" if baseline.is_git else "普通目录（未检测到 git）"))
    if baseline.is_git:
        lines.append("- **分支**：`%s`　**提交数**：%d" % (baseline.branch, baseline.commits))
        if baseline.remotes:
            lines.append("- **远端**：%s" % "、".join(baseline.remotes))
        lines.append("- **已跟踪文件**：%d　**未跟踪未忽略**：%d" % (baseline.tracked, baseline.untracked))
    else:
        lines.append("- **文件数**：%d" % baseline.tracked)
    lines.append("- **扫描文件**：%d　**总体积**：%s" % (baseline.scanned, human_size(baseline.total_size)))
    lines.append("- **本次版本许可证**：%s" % (declared if declared else "未确认"))
    lines.append("- **时间**：%s" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    lines.append("- **结论**：%s **%s**" % (icon, label))
    lines.append("")
    lines.append("## 概览")
    lines.append("")
    lines.append("| 级别 | 含义 | 数量 |")
    lines.append("|---|---|---|")
    for lvl in LEVEL_ORDER:
        lines.append("| %s | %s | %d |" % (lvl, LEVEL_NAME[lvl], counts[lvl]))
    lines.append("")

    if not findings:
        lines.append("未命中任何已知风险模式。注意：这不等于绝对安全，仍需人工复核敏感业务逻辑与数据来源。")
        lines.append("")
        return "\n".join(lines)

    for lvl in LEVEL_ORDER:
        group = [f for f in findings if f.level == lvl]
        if not group:
            continue
        lines.append("## %s %s（%d 项）" % (lvl, LEVEL_NAME[lvl], len(group)))
        lines.append("")
        for idx, item in enumerate(group, 1):
            location = item.path or "-"
            if item.line:
                location += ":%d" % item.line
            lines.append("### %d. [%s] %s" % (idx, item.code, item.title))
            lines.append("")
            lines.append("- **位置**：`%s`" % location)
            if item.evidence:
                lines.append("- **证据**：`%s`" % item.evidence)
            if item.why:
                lines.append("- **原因**：%s" % item.why)
            if item.fix:
                lines.append("- **修复**：%s" % item.fix)
            lines.append("")

    lines.append("## 说明")
    lines.append("")
    lines.append("- 报告中的凭据均已脱敏，只保留首尾各 4 位。")
    lines.append("- 本报告只读生成，未修改任何文件。")
    lines.append("- 正则只能覆盖已知模式；退出码 0 不代表可以发布。")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="GitHub 开源发布前审查（只读）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("path", nargs="?", default=".", help="待审查目录，默认当前目录")
    parser.add_argument("--json", metavar="OUT", help="写出 JSON 报告")
    parser.add_argument("--md", metavar="OUT", help="写出 Markdown 报告")
    parser.add_argument("--history", action="store_true", help="扫描 git 历史（较慢）")
    parser.add_argument("--history-commits", type=int, default=300, metavar="N",
                        help="历史内容扫描的提交上限，默认 300")
    parser.add_argument("--max-size", type=float, default=50, metavar="MB",
                        help="大文件告警阈值，默认 50")
    parser.add_argument("--tracked-only", action="store_true", help="只扫描已跟踪文件")
    parser.add_argument("--include-untracked", action="store_true",
                        help="包含未跟踪但未忽略的文件（默认已包含）")
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                        help="跳过匹配的文件或目录（可重复）；也可写在 .auditignore 里")
    parser.add_argument("--license", metavar="SPDX",
                        help="声明本次版本采用的许可证（如 MIT、Apache-2.0）；不填则交互式询问")
    parser.add_argument("--no-prompt", action="store_true",
                        help="不询问许可证（CI 用），报告会标记为未确认")
    parser.add_argument("--quiet", action="store_true", help="只输出结论行")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print("错误：目录不存在 %s" % root, file=sys.stderr)
        return 1

    baseline = Baseline(root=root)
    findings = []

    is_git, _ = git(root, ["rev-parse", "--is-inside-work-tree"])
    baseline.is_git = is_git
    if is_git:
        ok, out = git(root, ["rev-parse", "--abbrev-ref", "HEAD"])
        baseline.branch = out.decode("utf-8", "replace").strip() if ok else "unknown"
        ok, out = git(root, ["rev-list", "--count", "HEAD"])
        if ok:
            try:
                baseline.commits = int(out.decode("utf-8", "replace").strip())
            except ValueError:
                baseline.commits = 0
        ok, out = git(root, ["remote", "-v"])
        if ok:
            remotes = set()
            for line in out.decode("utf-8", "replace").splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    remotes.add(parts[1])
            baseline.remotes = sorted(remotes)

    tracked, untracked = collect_files(root, args.tracked_only)
    baseline.tracked = len(tracked)
    baseline.untracked = len(untracked)

    files = list(dict.fromkeys(tracked + untracked))
    excludes = load_excludes(root, args.exclude)
    if excludes:
        files = [f for f in files if not is_excluded(f, excludes)]
    baseline.scanned = len(files)
    for rel in files:
        try:
            baseline.total_size += os.path.getsize(os.path.join(root, rel))
        except OSError:
            pass

    license_name = find_license_file(root)
    spdx = detect_spdx(read_text(os.path.join(root, license_name))) if license_name else None

    # 每次审查都必须确认本次版本采用的许可证：优先 --license，其次交互式询问
    declared = (args.license or "").strip()
    if not declared and not args.no_prompt and sys.stdin.isatty():
        declared = (prompt_license(spdx) or "").strip()

    check_secret_files(files, findings)
    check_artifact_dirs(files, findings)
    check_file_hygiene(root, files, findings, args.max_size)
    check_content(root, files, findings)
    check_ignore(root, files, findings)
    check_required(root, findings, declared)
    check_license_intent(findings, declared, spdx)
    check_readme(root, findings, spdx)
    check_manifest(root, findings, spdx)

    if args.history:
        if baseline.is_git:
            check_history(root, findings, args.history_commits)
        else:
            findings.append(Finding(
                "P3", "HIST-SKIP", "未检测到 git，跳过历史扫描", "", 0, "",
                "没有 .git 目录，无法检查历史泄露。", "若曾推送过，请在原仓库中重新运行。",
            ))

    findings.sort(key=lambda f: (LEVEL_ORDER[f.level], f.path or "~", f.line))

    report = render_markdown(baseline, findings, root, declared)
    label, icon = verdict_of(findings)
    counts = {lvl: sum(1 for f in findings if f.level == lvl) for lvl in LEVEL_ORDER}

    if args.md:
        with open(args.md, "w", encoding="utf-8") as fh:
            fh.write(report)
    if args.json:
        payload = {
            "root": root,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "verdict": label,
            "counts": counts,
            "baseline": {
                "is_git": baseline.is_git,
                "branch": baseline.branch,
                "commits": baseline.commits,
                "tracked": baseline.tracked,
                "untracked": baseline.untracked,
                "scanned": baseline.scanned,
                "total_size": baseline.total_size,
                "remotes": baseline.remotes,
            },
            "license": spdx,
            "license_declared": declared or None,
            "findings": [f.__dict__ for f in findings],
        }
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)

    if not args.quiet:
        print(report)
    print("%s %s（P0=%d P1=%d P2=%d P3=%d）" % (
        icon, label, counts["P0"], counts["P1"], counts["P2"], counts["P3"]))

    if counts["P0"]:
        return 2
    if counts["P1"] or counts["P2"]:
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    sys.exit(main())
