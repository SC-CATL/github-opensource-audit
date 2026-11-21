# GitHub 开源发布审查

一个 OpenCode 技能：在把项目推到 GitHub 之前，检查**有没有不该上传的内容**，以及**开源必备要素是否齐全**。

## 它检查什么

**不该上传的**

- 密钥与凭据：`.env`、私钥、`credentials.json`、云平台令牌、连接串里的明文口令
- 个人信息：真实手机号、身份证、用户名单、数据库 dump
- 内网痕迹：私网 IP、`.corp` / `.internal` 域名、私有 registry
- 垃圾与产物：`node_modules`、`dist`、`__pycache__`、`.DS_Store`、日志、大文件
- 历史泄露：删掉了但历史里还在的敏感文件

**应该有的**

- `README.md`（定位、安装、示例、许可证四要素）
- `LICENSE`（含类型识别与元数据一致性校验）
- `.gitignore`（以及"已跟踪但本该忽略"的检测）
- `CONTRIBUTING.md`、`CODE_OF_CONDUCT.md`、`SECURITY.md`、`CHANGELOG.md`、Issue/PR 模板、CI

## 安装

把整个目录复制到 OpenCode 技能目录：

```powershell
# Windows
Copy-Item -Recurse github-opensource-audit "$env:USERPROFILE\.config\opencode\skills\"

# macOS / Linux
cp -r github-opensource-audit ~/.config/opencode/skills/
```

OpenCode 会自动加载，无需重启。之后只要语义指向「开源到 GitHub」「上传 / 发布 / 推到 GitHub」「这个仓库能公开吗」「开源前检查一下」「README/LICENSE 齐不齐」「清理敏感提交历史」，都会触发；单纯改代码或问 Git 命令不会。

## 使用示例

不需要 OpenCode，也不需要装依赖（Python 3.9+）：

```powershell
python scripts/audit_repo.py . --history --license MIT --md 报告.md
```

**每次审查都会确认本次版本的许可证**：

- 交互式终端下不传 `--license`，会弹出选择菜单。
- 非交互环境（CI、脚本）请显式传 `--license <SPDX>`；用 `--no-prompt` 关闭询问，此时未声明会报 `LIC-UNCONFIRMED`（P2）。
- 声明与 `LICENSE` 文件不一致 → `LIC-MISMATCH`（P1）。

| 退出码 | 含义 |
|---|---|
| 0 | 未命中已知风险 |
| 1 | 存在 P1 / P2 |
| 2 | 存在 P0 |

## 目录

```
SKILL.md                     技能入口：流程、分级、红线
LICENSE                      MIT
CONTRIBUTING.md              贡献指南
CODE_OF_CONDUCT.md           行为准则
SECURITY.md                  漏洞报告渠道
CHANGELOG.md                 版本记录
references/
  forbidden-content.md       不该上传的内容清单
  required-files.md          必备文件矩阵与最小内容
  licenses.md                许可证选择与常见错误
  history-cleanup.md         历史泄露处置（先轮换，再清理）
  report-template.md         报告模板与定级示例
scripts/
  audit_repo.py              只读扫描器
.github/                     Issue / PR 模板与 CI
```

## 贡献

欢迎提 issue 和 PR。开始前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)，参与即表示同意 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

安全问题请按 [SECURITY.md](SECURITY.md) 私下报告，不要开公开 issue。

## 局限

- 只读，不修改文件；不会自动删除或改写历史。
- 正则只覆盖已知模式，退出码 0 不代表绝对安全。
- 不检查 GitHub 远端设置（description、topics、分支保护）。
- 不做依赖 CVE 扫描。

## 许可证

MIT License © 2026 SC-CATL，全文见 [LICENSE](LICENSE)。
