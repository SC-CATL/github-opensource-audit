# 不该上传的文件与内容

按危险程度排列。每条给「为什么危险 / 怎么识别 / 正确做法」。

---

## 一、密钥与凭据（P0）

### 1. 环境变量文件

- 危险：`.env` 里通常就是生产数据库密码、第三方 API Key、JWT 签名密钥。公开后等于把钥匙贴在门上。
- 识别：`.env`、`.env.local`、`.env.production`、`.env.*.local`。注意 `.env.example` 是允许的，但**里面的值必须是占位符**，不能是真实值改个名字。
- 做法：`.env` 进 `.gitignore`；只提交 `.env.example`，值写成 `DB_PASSWORD=changeme`。已经提交过的，轮换所有涉及凭据。

### 2. 私钥与证书

- 危险：私钥一旦公开，签发的令牌、SSH 访问、代码签名全部失效。
- 识别：`*.pem`、`*.key`、`*.pfx`、`*.p12`、`*.jks`、`*.keystore`、`*.kdbx`、`id_rsa`、`id_ed25519`、`id_ecdsa`、`*.ppk`；文件内容含 `-----BEGIN ... PRIVATE KEY-----`。
- 注意：`id_rsa.pub` 是公钥，可以提交；`.crt` 公钥证书一般也可提交，但要确认不是含私钥的 bundle。
- 做法：私钥移出仓库；`.gitignore` 加 `*.pem`、`*.key`、`id_*`（保留 `!*.pub`）。已经泄露的，重新生成密钥对并作废旧公钥。

### 3. 云与平台令牌

| 类型 | 特征前缀 |
|---|---|
| AWS Access Key | `AKIA` + 16 位大写字母数字 |
| GitHub Token | `ghp_`、`gho_`、`ghu_`、`ghs_`、`ghr_`、`github_pat_` |
| OpenAI / Anthropic | `sk-`、`sk-ant-` |
| Slack | `xoxb-`、`xoxp-`、`xoxa-`、`xoxr-`、`xoxs-` |
| Google API | `AIza` + 35 位 |
| Stripe | `sk_live_`、`rk_live_`（`sk_test_` 危害低但仍应清理） |
| 通用 JWT | `eyJ...eyJ...` |

- 做法：立刻在对应平台 revoke，再生成新令牌，新令牌只放本地环境变量或 Secrets。

### 4. 带凭据的配置文件

- `.npmrc` / `.yarnrc.yml`：可能含 `//registry.npmjs.org/:_authToken=...`
- `.pypirc`：PyPI 上传令牌
- `.netrc` / `_netrc`：机器登录凭据
- `.git-credentials`：明文 Git 账号密码
- `credentials.json` / `service-account*.json`：GCP 服务账号密钥
- `kubeconfig`：集群访问凭据
- `terraform.tfstate` / `*.tfstate.backup`：常含明文密码与私钥
- Postman `*.postman_environment.json`：常含真实 token
- `docker/config.json`：含 registry 登录凭据

### 5. 代码里的硬编码

- 危险：写在源码里的口令同样会进历史，删了也没用。
- 识别：`password = "..."`、`token: "..."`、`api_key=...`、`SECRET_KEY = '...'`、连接串 `postgres://user:pass@host/db`、`Bearer eyJ...`
- 做法：改读环境变量；已经写死并提交过的，轮换该凭据。

### 6. CI / 部署配置

- 危险：`.github/workflows/*.yml`、`.gitlab-ci.yml`、`docker-compose.yml`、`Dockerfile` 里常有直接写死的密钥，或 `ARG SECRET=...`。
- 做法：改用仓库 Secrets（`${{ secrets.X }}`）；注意 `echo` 出密钥会把值打进公开日志。

---

## 二、个人与客户数据（P0）

- 真实手机号（`1[3-9]` 开头 11 位）、身份证号（18 位）、银行卡号、家庭住址、真实姓名+工号
- 用户表导出：`users.csv`、`*.sql` dump、Excel 导出
- 工单/订单/聊天记录导出
- 测试 fixture 里直接用了生产数据
- 截图、演示视频、GIF 里的真实账号、邮箱、头像、客户名称、内部看板
- 日志文件：`*.log` 里常带 IP、邮箱、token、请求体

做法：造合成数据（faker 之类）；截图打码或重做；日志不进仓库。

---

## 三、内网痕迹（P2，暴露架构时升 P1）

- 私网 IP：`10.x.x.x`、`172.16-31.x.x`、`192.168.x.x`
- 内网域名：`*.local`、`*.corp`、`*.internal`、`*.lan`、`*.intra`
- 内部系统 URL、VPN 地址、跳板机地址
- 公司内部 Git 地址：`git@gitlab.company.com:...`、`https://nexus.corp/repository/...`
- 内网端口与拓扑描述、主机命名规范
- 数据库连接串里的内网主机名

做法：换成 `localhost`、`db.example.com`、`<your-host>`；架构图重绘。

---

## 四、构建产物与本地环境（P1）

| 类别 | 典型路径 |
|---|---|
| 依赖目录 | `node_modules/`、`bower_components/`、`.venv/`、`venv/`、`vendor/bundle` |
| 构建输出 | `dist/`、`build/`、`out/`、`target/`、`bin/`、`obj/`、`.next/`、`.nuxt/`、`coverage/`、`htmlcov/` |
| 缓存 | `__pycache__/`、`*.pyc`、`*.pyo`、`.pytest_cache/`、`.mypy_cache/`、`.ruff_cache/`、`.tox/`、`.gradle/`、`.cache/` |
| 编辑器 | `.idea/`、`.vscode/settings.json`（含本机路径/令牌）、`*.swp`、`*.swo` |
| 系统 | `.DS_Store`、`Thumbs.db`、`ehthumbs.db`、`desktop.ini`、`.Spotlight-V100`、`.Trashes` |
| 临时 | `*.log`、`*.tmp`、`*.bak`、`*.orig`、`*.rej` |

- 危险：体积暴涨、评审噪音、可能夹带本地路径和令牌、不同平台冲突。
- 做法：进 `.gitignore`，用 `git rm -r --cached <dir>` 取消跟踪。构建产物走 Release 附件或包管理器。

**`.gitignore` 陷阱**：规则只对未跟踪文件生效。已经提交过的文件，加规则不会自动移除，必须显式 `git rm --cached`。

---

## 五、大文件与二进制（P1）

- GitHub 单文件 >50MB 警告，>100MB 直接拒绝推送；仓库建议 <1GB。
- 常见误提交：数据集、模型权重（`*.pt`、`*.pth`、`*.onnx`、`*.safetensors`、`*.ckpt`、`*.h5`）、视频、PSD/AI 源文件、安装包（`*.exe`、`*.msi`、`*.dmg`）、压缩包（`*.zip`、`*.7z`、`*.tar.gz`）、`*.iso`
- 做法：用 Git LFS（并确认托管额度）或外部存储；Release 附件；`git filter-repo` 清理已提交的大文件（会改写历史）。

---

## 六、版权与合规风险（P1）

- 来源不明的图片、图标、字体、音效、数据集（尤其从网上随手下载的）
- 反编译、破解、去水印产物
- 商业 SDK 的二进制或头文件、需要授权的运行时
- 从别的仓库复制进来但没保留许可证和版权声明的代码
- 内含第三方代码却没有 `NOTICE` / 第三方许可清单
- 与项目许可证冲突的依赖（把 GPL 代码并入 MIT 项目）
- 公司职务作品：**先确认你有权开源**，很多劳动合同把成果归属约定给雇主
- 客户项目代码、外包交付物（通常客户持有版权）

做法：建立 `THIRD_PARTY_NOTICES.md`；素材逐个确认许可并记录来源；职务作品走公司开源审批。

---

## 七、容易被忽略的边界情况

1. **`.env.example` 里是真实值**——只改了文件名，没改内容。
2. **Jupyter notebook 的输出单元格**——里面可能有数据、路径、token、内网地址。
3. **注释掉的旧密码**——`# password = "old_pass_2019"` 一样是泄露。
4. **测试里的真实数据**——"只是测试用"不是理由。
5. **Git submodule 指向私有仓库**——别人 clone 会失败，同时暴露私有地址。
6. **lockfile 里的私有 registry**——`package-lock.json` 里的 `resolved` 字段会带内网地址和 token 参数。
7. **`git commit -m` 消息里带密钥**——历史里能查到。
8. **`.vscode/settings.json`**——常含本机绝对路径、解释器路径、有时还有 token。
9. **`.git/config` 被误提交**——含 remote URL 里的账号密码。
10. **文档/截图里的二维码**——可能指向内部系统。
11. **`Dockerfile` 的 `ARG`/`ENV` 密钥**——`docker history` 能还原。
12. **移动端签名文件**——`*.keystore`、`*.mobileprovision`、`*.p12`。
13. **License key / 激活码**——商业组件的序列号。
14. **崩溃日志与堆栈**——含内存片段、路径、用户标识。
15. **生成代码里嵌入的绝对路径**——`C:\Users\<真名>\...` 暴露用户名。

---

## 八、判定原则

- 拿不准是不是真实数据 → 按 P0 处理，让用户确认，不要替用户下结论。
- "反正是私有仓库" 不是理由：私有转公开、协作者、fork、平台事故都会让它出去。
- 已经推上去过 → 问题从"删文件"升级为"轮换凭据 + 清理历史"。
- 只清理当前提交不够，必须查历史。
