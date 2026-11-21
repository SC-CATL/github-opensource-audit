# Changelog

本文件遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### Added

- `references/github-publish.md`：认证、workflow scope、凭据助手、push 排查、远端验证清单、分支保护。
- `SKILL.md` 新增「发布执行与验证」章节：前置检查、建仓推送、远端逐项验证、本地绿≠远端绿。
- 非 git 模式下按 `.gitignore` 近似过滤，报告头显示跳过数量，减少产物误报。

### Fixed

- 历史扫描复用工作区扫描的误报过滤（占位符、行内豁免、私钥密钥体校验），修复 `postgres://user:pass@host/db`、文档私钥示例被误判为 P0。
- 历史扫描按 hunk 合并连续新增行后再匹配，真实多行私钥仍可正确命中。

### Changed

- CI 的 GitHub Actions 升级到 `checkout@v7`、`setup-python@v7`、`upload-artifact@v7`，消除 Node 20 弃用告警。

### Added

- 每次审查强制确认本次版本采用的许可证：`--license` 声明，交互式终端自动询问，CI 用 `--no-prompt`。
- 新增 `LIC-UNCONFIRMED`（未确认）、`LIC-MISMATCH`（声明与文件不一致）、`LIC-PROPRIETARY`（声明保留所有权利）三条检查。
- 报告头与 JSON 输出新增本次版本许可证字段。

## [1.0.0] - 2026-11-21

### Added

- `SKILL.md`：七步审查流程、P0–P3 分级、红线与报告要求。
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
