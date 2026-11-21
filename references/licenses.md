# 许可证：选择、识别与常见错误

## 一、没有 LICENSE 意味着什么

**保留所有权利（All rights reserved）。**

不是"公共领域"，不是"随便用"。默认著作权法下，别人只能看，不能复制、修改、分发、商用。
即使代码挂在 GitHub 公开仓库上，也一样。GitHub 服务条款只授予"在平台上查看和 fork"的最低权限。

所以：**缺 LICENSE 是 P1，不是可选项。**

---

## 二、怎么选

| 许可证 | 类型 | 适合 | 主要约束 |
|---|---|---|---|
| **MIT** | 宽松 | 库、工具、大多数项目 | 保留版权与许可声明 |
| **Apache-2.0** | 宽松 | 需要专利授权、企业采用 | 保留声明 + NOTICE + 专利条款 |
| **BSD-2/3-Clause** | 宽松 | 与 MIT 类似，BSD 生态 | 保留声明；3-Clause 禁止用作者名背书 |
| **ISC** | 宽松 | 极简，等价 MIT | 保留声明 |
| **MPL-2.0** | 弱传染 | 希望改动回馈但允许闭源集成 | 修改过的**文件**需开源 |
| **LGPL-3.0** | 弱传染 | 库，允许闭源程序动态链接 | 修改库本身需开源 |
| **GPL-3.0** | 强传染 | 确保衍生作品也开源 | 分发衍生作品必须 GPL |
| **AGPL-3.0** | 最强 | 服务端软件，防 SaaS 白嫖 | 网络提供服务也算分发 |
| **Unlicense / CC0** | 公共领域 | 完全放弃权利 | 部分法域不完全可执行 |
| **双许可** | MIT + Apache-2.0 | Rust 生态常见 | 用户二选一 |

选择要点：

- 想被广泛采用 → MIT 或 Apache-2.0。企业法务更认 Apache-2.0（有明确专利授权）。
- 想强制回馈 → GPL/AGPL，但会劝退商业用户。
- 库想被闭源项目用 → 不要 GPL，用 MIT/Apache/MPL/LGPL。
- 文档和素材可以用与代码不同的许可（如代码 MIT + 文档 CC BY 4.0），但必须在 README 里说清。

---

## 三、SPDX 标识

包清单里用 SPDX 短标识，不要写全名：

```
MIT
Apache-2.0
BSD-3-Clause
GPL-3.0-only        # 仅 3.0
GPL-3.0-or-later    # 3.0 或更高
AGPL-3.0-only
MPL-2.0
Unlicense
```

- `GPL-3.0` 是**已废弃写法**，要写 `GPL-3.0-only` 或 `GPL-3.0-or-later`。
- 多许可用 `OR` / `AND`：`MIT OR Apache-2.0`。
- 包清单里的 `license` 字段与 `LICENSE` 文件必须一致。

---

## 四、识别许可证类型

拿到一个 `LICENSE` 文件，按特征判断：

| 特征文本 | 许可证 |
|---|---|
| `Permission is hereby granted, free of charge` | MIT |
| `Apache License` + `Version 2.0, January 2004` | Apache-2.0 |
| `GNU AFFERO GENERAL PUBLIC LICENSE` + `Version 3` | AGPL-3.0 |
| `GNU LESSER GENERAL PUBLIC LICENSE` + `Version 3` | LGPL-3.0 |
| `GNU GENERAL PUBLIC LICENSE` + `Version 3` | GPL-3.0 |
| `GNU GENERAL PUBLIC LICENSE` + `Version 2` | GPL-2.0 |
| `Redistribution and use in source and binary forms` + `Neither the name of` | BSD-3-Clause |
| `Redistribution and use in source and binary forms`（无背书条款） | BSD-2-Clause |
| `Mozilla Public License Version 2.0` | MPL-2.0 |
| `ISC License` / `Permission to use, copy, modify, and/or distribute` | ISC |
| `This is free and unencumbered software released into the public domain` | Unlicense |
| `CC0 1.0 Universal` | CC0-1.0 |

判断顺序：AGPL/LGPL 先于 GPL，BSD-3 先于 BSD-2，否则会误判。

脚本 `scripts/audit_repo.py` 已实现这套匹配。

---

## 五、常见错误

1. **改了名字的 MIT**——把 "MIT License" 改成 "XYZ License"，条款没变。这会让法律上无法识别，等同于自定义许可，别人不敢用。要么用标准 MIT，要么认真起草。
2. **删掉了版权行**——`Copyright (c) 2026 Your Name` 必须保留，否则声明不完整。
3. **年份写成项目创建年**——用当前年份或年份区间 `2024-2026`。
4. **LICENSE 与 package.json 不一致**——`license: "ISC"` 但 `LICENSE` 是 MIT。脚本会报 P2。
5. **README 写"MIT"，LICENSE 是 Apache**——同上。
6. **只写 LICENSE 不给全文**——"本项目采用 MIT 许可" 一行字不构成有效许可声明，要放全文。
7. **依赖传染**——MIT 项目里复制了 GPL 代码，整个项目就得按 GPL 分发。引入第三方代码前查它的许可证。
8. **素材没许可**——图片、字体、图标、数据集不在代码许可证覆盖范围内，必须单独说明。
9. **职务作品**——劳动合同常约定成果归公司。开源前确认有权处置。
10. **换许可证需要所有贡献者同意**——已经有外部贡献的项目，改协议要征得同意，否则只能新开版本。

---

## 六、第三方与 NOTICE

- 内含第三方代码 → 建 `THIRD_PARTY_NOTICES.md`，列：组件名、版本、来源 URL、许可证、版权行。
- Apache-2.0 依赖 → 分发时必须保留其 `NOTICE`。
- 打包分发的二进制 → 附上所有依赖的许可证全文。
- 字体/图标 → 单独一节说明来源与许可（OFL、CC BY 等）。

---

## 七、给用户的措辞

- 缺 LICENSE：不要说"建议加个 LICENSE"，要说"没有 LICENSE 时默认保留所有权利，别人无法合法使用你的代码"。
- 不确定选哪个：默认推荐 MIT；需要专利保护或面向企业推荐 Apache-2.0；明确告知传染性后果再让用户决定 GPL/AGPL。
- 已公开但无 LICENSE：说明可以补加，且补加后对既往版本同样有效（除非已有贡献者）。
