# Changelog

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- `scripts/git_identity.py`：从 GitHub 账号同步 `user.name` / `user.email`，默认使用 noreply 地址保护隐私（`--public-email` 可改用公开邮箱）；默认只读，`--apply` 才写入，幂等。
- 审计新增 `GIT-IDENTITY`（P2）：git 仓库未配置提交身份时提示。
- `SKILL.md` 与 `references/github-publish.md` 明确身份同步的时机（登录后、发布前、审计、手动）与取值链路。

## [1.1.0] - 2026-11-21

### Added

- `references/github-publish.md`：认证、workflow scope、凭据助手、push 排查、远端验证清单、分支保护。
- `SKILL.md` 新增「发布执行与验证」章节：前置检查、建仓推送、远端逐项验证、本地绿 ≠ 远端绿。
- 非 git 模式下按 `.gitignore` 近似过滤，报告头显示跳过数量，减少产物误报。

### Fixed

- 内网域名规则要求 URL / 邮箱上下文再识别 `.local`，修复 `args.local`、`obj.local` 之类代码属性被误判。
- `.auditignore` 现在同时作用于 git 历史扫描，避免文档示例在历史中持续误报。
- 历史扫描复用工作区扫描的误报过滤（占位符、行内豁免、私钥密钥体校验），修复 `postgres://user:pass@host/db`、文档私钥示例被误判为 P0。
- 历史扫描按 hunk 合并连续新增行后再匹配，真实多行私钥仍可正确命中。

### Changed

- CI 的 GitHub Actions 升级到 `checkout@v7`、`setup-python@v7`、`upload-artifact@v7`，消除 Node 20 弃用告警。

## [1.0.0] - 2026-11-21

### Added

- `SKILL.md`：审查流程（含每次确认许可证）、P0–P3 分级、红线与报告要求。
- 每次审查强制确认本次版本采用的许可证：`--license` 声明，交互式终端自动询问，CI 用 `--no-prompt`。
- 新增 `LIC-UNCONFIRMED`（未确认）、`LIC-MISMATCH`（声明与文件不一致）、`LIC-PROPRIETARY`（声明保留所有权利）三条检查。
- 报告头与 JSON 输出新增本次版本许可证字段。
- `scripts/audit_repo.py`：零依赖只读扫描器，支持工作区 / 已跟踪 / 历史三种范围。
- 敏感内容检测：私钥、`.env`、云平台令牌、JWT、连接串口令、内网地址、个人信息。
- 卫生检测：依赖与构建目录、系统残留、数据文件、大文件三级阈值、`.gitignore` 失效检测。
- 合规检测：必备文件矩阵、LICENSE 文本转 SPDX、README 四要素、包清单元数据一致性。
- 误报控制：`.auditignore`、行内 `audit:allow`、私钥密钥体校验、占位符过滤。
- `references/`：五份细则文档（禁止内容、必备文件、许可证、历史清理、报告模板）。
- MIT 许可证，版权归属 SC-CATL。

### Security

- 报告中所有凭据自动脱敏，只保留首尾各 4 位。
- 扫描器全程只读，不修改、不删除任何文件。
