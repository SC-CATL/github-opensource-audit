# 必备文件矩阵与最小内容

## 一、总览

| 文件 | 级别 | 何时必需 | 作用 |
|---|---|---|---|
| `README.md` | P1 | 总是 | 第一印象，决定别人是否用你 |
| `LICENSE` | P1 | 总是 | 没有它 = 保留所有权利，别人不能用 |
| `.gitignore` | P1 | 总是 | 防止产物和密钥入库 |
| `CONTRIBUTING.md` | P2 | 接受外部贡献时 | 降低协作成本 |
| `CODE_OF_CONDUCT.md` | P2 | 社区型项目 | 行为准则 |
| `SECURITY.md` | P2 | 处理用户数据或部署服务时 | 漏洞报告渠道 |
| `CHANGELOG.md` | P3 | 有版本发布时 | 变更可追溯 |
| `NOTICE` / `THIRD_PARTY_NOTICES.md` | P2 | 内含第三方代码/素材 | 许可合规 |
| `CITATION.cff` | P3 | 学术用途 | 规范引用 |
| `docs/` | P3 | 文档超过 README 承载量 | 详细文档 |
| `.github/ISSUE_TEMPLATE/` | P3 | 社区型项目 | 提高 issue 质量 |
| `.github/PULL_REQUEST_TEMPLATE.md` | P3 | 接受 PR 时 | 统一 PR 质量 |
| `.github/workflows/` | P3 | 任何正式项目 | 自动化测试 |
| `.editorconfig` | P3 | 多编辑器协作 | 统一缩进换行 |
| `.gitattributes` | P3 | 有二进制/跨平台 | 换行与 LFS 规则 |
| `Dockerfile` / `docker-compose.yml` | P3 | 需要部署 | 一键运行 |

**"必需"的判定**：项目已经公开可被 clone 使用，却没有 `LICENSE`，属于 P1，必须修。只是个人备份仓库且不打算让别人用，可以只提示不阻断。

---

## 二、README 十项要素

按重要性排序，前五项缺失算 P2，后五项算 P3。

1. **项目名 + 一句话定位** —— 用一句话说清"这是什么、解决什么问题"，不要只写"一个 XX 框架"。
2. **安装方式** —— 具体命令，覆盖主要平台/包管理器：`npm i x`、`pip install x`、`cargo add x`、`brew install x`。
3. **最小可运行示例** —— 复制粘贴就能跑通的最短代码，含预期输出。
4. **使用/配置说明** —— 核心参数表，或指向 `docs/` 的链接。
5. **许可证声明** —— 明确写出 SPDX 名称，例如 `MIT License`，并链接到 `LICENSE`。
6. **依赖与兼容性** —— 运行时版本要求、支持的操作系统。
7. **截图 / GIF / 演示链接** —— 有界面的项目几乎必需。
8. **常见问题 / 已知限制** —— 提前说明不支持的场景，减少无效 issue。
9. **贡献指引** —— 链接 `CONTRIBUTING.md`。
10. **致谢 / 第三方来源** —— 素材和代码来源。

额外加分：状态徽章（CI、版本、许可证）、Roadmap、安全说明链接。

### README 常见问题

- 只有标题和一句"TODO"，等于没有。
- 安装命令写了但没写前置条件（需要 Python 3.11+、需要先装 ffmpeg）。
- 示例代码跑不通（改了 API 没更新文档）。
- 徽章指向不存在的 workflow，显示红色 failed。
- 中英文混排但两种都不完整。
- 许可证段落写 `MIT`，`LICENSE` 文件却是 Apache-2.0。

---

## 三、LICENSE 最小要求

- 使用**标准全文**，不要自己改写、删条款、改名字。
- 第一行或版权行写清 `Copyright (c) <年份> <版权人>`。
- 文件名用 `LICENSE`（无扩展名最通用），或 `LICENSE.md` / `LICENSE.txt`。
- 与包清单的 `license` 字段保持一致，用 SPDX 标识（`MIT`、`Apache-2.0`、`GPL-3.0-only`）。

详见 `licenses.md`。

---

## 四、.gitignore 最小内容

至少覆盖当前技术栈的产物目录和密钥文件。要点：

- 按技术栈生成，别手写几十行容易漏。
- **密钥优先级最高**：`.env`、`*.pem`、`*.key`、`id_*`、`credentials.json`。
- 不要忽略 lockfile（`package-lock.json`、`poetry.lock`、`Cargo.lock`）——应用类项目应当提交，保证可复现。
- 不要忽略测试 fixture 里的必要数据。
- 加了规则后检查是否真的生效：`git status --ignored`、`git ls-files -ci --exclude-standard`。

推荐组合：`.gitignore` + `.gitattributes`（处理换行与二进制），需要时再加 `.dockerignore`。

---

## 五、CONTRIBUTING.md 最小内容

1. 如何搭本地开发环境（一条命令最好）
2. 如何跑测试与 lint
3. 分支/提交信息规范
4. PR 流程与评审预期
5. 代码风格要求
6. 报告 bug 的正确位置（链接 issue 模板）

---

## 六、SECURITY.md 最小内容

1. **支持的版本**（哪些版本会收到安全修复）
2. **如何私下报告漏洞**——邮箱或 GitHub Security Advisories，**不要让人开公开 issue**
3. **响应时间预期**
4. 明确禁止公开披露的时限

---

## 七、CODE_OF_CONDUCT.md

直接采用 Contributor Covenant 2.1 全文并填联系方式即可，不要自创。文件里必须有一个可用的举报邮箱或表单，否则形同虚设。

---

## 八、CHANGELOG.md

遵循 [Keep a Changelog](https://keepachangelog.com/)，语义化版本。

```markdown
# Changelog

## [Unreleased]

## [1.2.0] - 2026-03-01
### Added
- 支持批量导入
### Fixed
- 修复 Windows 下路径解析错误
```

要点：最新的在最上面；每版写日期；分类用 Added / Changed / Deprecated / Removed / Fixed / Security；`Unreleased` 段常驻。

---

## 九、Issue / PR 模板

`.github/ISSUE_TEMPLATE/bug_report.yml`（新版用 YAML 表单）、`feature_request.yml`、`.github/PULL_REQUEST_TEMPLATE.md`。

bug 模板至少要求：版本、系统、复现步骤、期望结果、实际结果、日志（提示脱敏）。

---

## 十、CI workflow

最小可用：push 与 PR 时跑测试 + lint。

```yaml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install -e .[dev]
      - run: pytest -q
```

注意：workflow 里不能有明文密钥；`pull_request_target` 慎用（可被 fork 利用窃取 secrets）。

---

## 十一、其他

- `.editorconfig`：统一 `indent_style`、`end_of_line`、`charset = utf-8`、`insert_final_newline`。
- `.gitattributes`：`* text=auto`，二进制标记 `-text`，LFS 规则 `*.psd filter=lfs diff=lfs merge=lfs -text`。
- `THIRD_PARTY_NOTICES.md`：列出第三方代码/素材、来源、许可证、版权行。
- `CITATION.cff`：学术项目必需，否则别人不知道该怎么引用。
