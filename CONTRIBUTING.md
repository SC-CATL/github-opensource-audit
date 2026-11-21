# 贡献指南

感谢你愿意改进这个技能。以下是最小必要的信息。

## 环境

- Python 3.9 或更高（扫描器只用标准库，无需安装依赖）
- Git（历史扫描需要）

## 本地运行

```powershell
git clone <repo>
cd github-opensource-audit
python scripts/audit_repo.py . --history
```

改动后请至少确认两点：

1. 自检通过：`python scripts/audit_repo.py . --quiet` 退出码为 0。
2. 用样例仓库验证新规则：含 `.env`、私钥、大文件的临时目录应能正确命中。

## 修改规则时的约定

- 新增内容正则加到 `scripts/audit_repo.py` 的 `SECRET_PATTERNS`，必须同时给出 `级别`、`原因`、`修复` 三项，不要只加正则。
- 新增文件名规则加到 `SECRET_FILE_RULES`（P0）或 `CRED_FILE_RULES`（P1）。
- 同步更新 `references/` 下对应的说明文档，保持脚本与文档一致。
- 新增规则前先想清楚误报：文档示例、测试夹具、占位符都要能过滤。必要时用 `audit:allow` 行内豁免。
- 不要在规则里写死具体的密钥值，只用模式。

## 提交信息

采用 Conventional Commits：

```
feat: 增加 Docker 配置中的密钥检测
fix: 修复 Windows 路径下的 glob 匹配
docs: 补充许可证选择说明
```

## 如何提问（问题反馈）

使用 [问题反馈模板](.github/ISSUE_TEMPLATE/bug_report.yml)。仓库已关闭空白 issue，必须走模板。

模板要求填的内容，每一项都对应一个排查方向：

| 字段 | 为什么需要 |
|---|---|
| 问题类型 | 误报、漏报、报错的定位路径完全不同 |
| 版本与系统 | 跨平台路径与编码差异是常见原因 |
| 复现步骤 | 没有复现就无法确认修复 |
| 期望 vs 实际 | 只写「有问题」无法判断是规则缺失还是实现错误 |
| 日志（脱敏） | 直接决定能否一次定位 |

**好的提问**

```text
环境：Windows 11 / Python 3.12.10 / v1.0.0
复现：目录下只有 .env.example，内容 DB_PASSWORD=changeme
执行：python scripts/audit_repo.py .
期望：不报警，占位符应被过滤
实际：命中 SEC-FILE，级别 P0
```

**不好的提问**

```text
扫描不太准，麻烦修一下。
```

要点：一个问题一个 issue；给最小复现；密钥一律脱敏；先说现象再说猜测。

## 如何提改进（改进建议）

使用 [改进建议模板](.github/ISSUE_TEMPLATE/feature_request.yml)，按「现状 → 后果 → 方案 → 误报」四段写。

- **先说问题再说方案**：直接给方案容易漏掉真实需求。
- **后果要具体**：写「Dockerfile 里的 ARG 密钥不会被发现，报告给出虚假安全感」，不要写「不够全面」。
- **新增规则必须给误报处理思路**：哪些合法写法会误判、用什么方式排除。没有这一段的规则 PR 不予合并。
- **级别要说明**：新规则默认 P0 还是 P2，会不会让正常项目突然变红。

## 如何提交合并请求

1. Fork 仓库，分支命名 `feat/xxx`、`fix/xxx`、`docs/xxx`。
2. 提交前跑一次自检：`python scripts/audit_repo.py . --quiet`，退出码应为 0。
3. 按 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md) 填写，**标题即最终提交信息**，用 Conventional Commits。
4. 一个 PR 只做一件事，混入无关格式化会被要求拆分。
5. 涉及新规则时，附误报与漏报各一个验证样例。
6. 默认使用 Squash and merge。

评审主要看四点：误报率是否可控、是否跨平台可用、是否保持只读、文档是否同步。

## 报告安全问题

见 [SECURITY.md](SECURITY.md)。**不要开公开 issue**，也不要在 issue 里贴真实密钥。

## 行为准则

参与本项目即表示同意遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
