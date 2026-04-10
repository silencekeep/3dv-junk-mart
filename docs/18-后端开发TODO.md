# 电商平台后端开发 TODO

> 适用范围：`C:\Users\86198\Desktop\AI\3dv-junk-mart\API_PROTO.md` 与 `C:\Users\86198\Desktop\AI\3dv-junk-mart\DATABASE_PROTO.md`
>
> 目标：把当前仓库里的后端从 3DGS 任务流实现，迁移为电商平台后端；数据库采用 SQLite；并通过 HTTP 关联远程 3D Gaussian Splatting (3DGS) 训练服务。

## 1. 目标与边界

### 1.1 后端目标
- 提供完整的电商平台后端 API，覆盖认证、用户、主页、搜索、商品、发布、聊天、订单、评价、通知、会员、钱包与配置。
- 返回与 `API_PROTO.md` 一致的资源模型与页面 bootstrap 数据，不把 Flutter 页面布局写死在后端。
- 以 SQLite 作为后端主数据库，保证本地开发、单机部署、离线验证都能运行。
- 通过远程 3DGS 训练服务完成商品视频的 3D 重建、Mask、训练、导出、Viewer 链接生成等能力。

### 1.2 迁移边界
- 保留 FastAPI 作为 Web 框架。
- 替换当前 3DGS 任务流型接口为电商资源型接口。
- 保留本地文件存储作为媒体和模型文件的落点，数据库只保存元数据和引用。
- 远程 3DGS 训练服务保持独立，不把训练代码重新塞回电商后端。
- 先实现可用的 MVP 再逐步补齐高级能力，避免一次性重写导致不可控。

### 1.3 现状判断
- 当前后端仍带有 3DGS 任务流实现痕迹，例如 `backend/app/routes/reconstructions.py`、`shared/task_store.py`、`trainer/`。
- 当前 `backend/app/schemas.py` 已经出现了一部分电商资源模型，但还没有完整路由和数据库支撑。
- `DATABASE_PROTO.md` 提供的是完整的领域模型参考，但实现层需要改成 SQLite 版本，而不是直接照搬 PostgreSQL 设计。

## 2. 技术决策清单

### 2.1 SQLite 设计原则
- 使用单文件 SQLite 数据库作为主存储，推荐路径由环境变量 `SQLITE_DB_PATH` 决定，默认落在 `storage/db/business.db`。
- 开启 `PRAGMA foreign_keys = ON`，并启用 WAL 模式以减少写锁影响。
- 时间字段统一使用 UTC 字符串。
- 布尔字段统一使用 `INTEGER` 0/1。
- JSON 结构统一存成 `TEXT`，使用 `json.dumps` / `json.loads` 处理。
- 对搜索、统计和聚合字段建立索引，避免 SQLite 在列表页和搜索页上退化。

### 2.2 API 设计原则
- 统一返回 `ApiEnvelope` 风格的响应：`code`、`message`、`data`、`meta`、`errors`。
- 统一错误码映射，业务冲突、校验失败、权限失败、系统错误分别归类。
- 页面 bootstrap 接口与资源接口分离，但 bootstrap 只负责聚合数据，不负责页面排版。
- 所有资源 ID 使用字符串，不暴露自增数字主键给前端。

### 2.3 3DGS 训练服务联动原则
- 远程训练服务保持为独立能力，通过 HTTP 调用，不直接依赖本地训练脚本。
- 通过环境变量配置远程训练服务地址，当前远程部署可指向 `http://222.199.216.192:9000` 这类地址。
- 对远程服务的状态轮询、失败重试、超时处理、模型 URL 解析要封装到单独 service 层。
- 后端只保存训练任务与模型产物的业务元数据，具体模型文件仍由远程训练服务或其静态资源托管。

## 3. 推荐目录改造方案

> 下面不是强制目录，但建议按这个方向重构，便于后续维护和测试。

- `backend/app/main.py`：应用入口、CORS、中间件、路由注册、健康检查。
- `backend/app/schemas.py`：电商资源模型、请求/响应模型、分页与 envelope 定义。
- `backend/app/routes/`：按业务域拆分路由，例如 `auth.py`、`users.py`、`listings.py`、`orders.py`、`messages.py`、`reviews.py`、`notifications.py`、`pages.py`、`config.py`。
- `backend/app/services/`：业务服务层，负责事务、聚合、远程 3DGS 调用、支付/订单状态流转。
- `backend/app/repositories/`：SQLite 仓库层，封装 CRUD 与查询。
- `backend/app/core/`：配置、错误码、权限、分页、响应封装、日志与中间件。
- `backend/app/db/` 或 `backend/app/persistence/`：SQLite 连接、初始化、迁移、种子数据。
- `shared/`：只保留真正跨模块的配置与路径工具，逐步移除 3DGS 任务流专用实现。
- `tests/`：SQLite 临时库、接口合同测试、远程 3DGS 客户端 mock 测试。

## 4. 分阶段 TODO

### P0. 冻结规范与基础设施

#### P0.1 固化后端契约
- [ ] 统一确认 `API_PROTO.md` 中的接口范围与字段命名。
- [ ] 统一确认 `DATABASE_PROTO.md` 中哪些表属于首发必需，哪些可以后置。
- [ ] 明确首版是否需要兼容当前 3DGS 任务页接口，还是直接切换为纯电商 API。
- [ ] 明确前端是否依赖 `/pages/*` bootstrap 接口，如果依赖，则必须优先实现。

#### P0.2 配置与环境变量
- [ ] 新增 SQLite 数据库路径配置，默认使用 `storage/db/business.db`。
- [ ] 新增远程 3DGS 服务地址配置，例如 `TRAINER_SERVICE_BASE_URL` 或 `GS_SERVICE_BASE_URL`。
- [ ] 新增远程 3DGS 服务公共访问地址配置，例如 `TRAINER_SERVICE_PUBLIC_BASE_URL`。
- [ ] 新增远程 3DGS 服务超时配置、内部鉴权 token 配置。
- [ ] 新增后端统一 `BASE_URL`、静态资源路径、日志路径配置。

#### P0.3 数据库初始化
- [ ] 设计 SQLite 初始化脚本或迁移脚本。
- [ ] 建立数据库连接封装、事务封装、连接复用与关闭策略。
- [ ] 启用 `foreign_keys`、WAL、busy timeout 等 SQLite 运行参数。
- [ ] 定义数据库种子数据导入流程。
- [ ] 为本地开发与 CI 提供独立的临时数据库生成方式。

#### P0.4 旧代码清理策略
- [ ] 识别当前 3DGS 任务流代码中可复用的部分和必须删除的部分。
- [ ] 逐步拆掉 `reconstructions.py` 这类任务流路由，避免新旧接口混在一起。
- [ ] 把 `shared/task_store.py` 中 3DGS 专用的文件任务存储逻辑拆离或替换成 SQLite 仓库。
- [ ] 保留 `trainer/` 中真正可复用的远程调用封装思路，删除只服务旧任务流的耦合代码。

### P1. SQLite 数据模型与仓库层

#### P1.1 认证与用户
- [ ] 实现 `users` 表。
- [ ] 实现 `user_profiles` 表。
- [ ] 实现 `auth_sessions` 表。
- [ ] 实现 `user_consents` 表。
- [ ] 实现 `login_attempts` 表。
- [ ] 实现 `user_stats` 表，并定义按用户维度的统计回填与增量更新策略。
- [ ] 实现 `user_follows` 表，并提供关注、取消关注、粉丝列表和关注列表的仓库接口。
- [ ] 实现 `user_addresses` 表，并支持默认地址、收货地址和提货地址管理。
- [ ] 预留 `auth_identity` 表或身份绑定扩展位，用于 phone、email、username、oauth 等多身份场景。
- [ ] 实现基础索引：手机号、邮箱、session、登录尝试时间。
- [ ] 实现用户、资料、统计、关注、地址、会话、同意记录的仓库类。

#### P1.2 商品与分类
- [ ] 实现 `categories` 表。
- [ ] 实现 `listings` 表。
- [ ] 实现 `listing_drafts` 表。
- [ ] 实现 `listing_media` 表。
- [ ] 实现 `listing_specs` 表。
- [ ] 实现 `listing_tags`、`listing_tag_links` 表。
- [ ] 实现 `listing_favorites`、`listing_views` 表。
- [ ] 实现 `listing_search_documents` 表。
- [ ] 为商品标题、状态、分类、地点、排序字段建立索引。

#### P1.3 主页与服务入口
- [ ] 实现 `home_banners` 表。
- [ ] 实现 `home_sections` 表。
- [ ] 实现 `service_catalog` 表。
- [ ] 实现首页、快捷入口、推荐位的仓库查询。

#### P1.4 聊天与消息
- [ ] 实现 `conversations` 表。
- [ ] 实现 `conversation_members` 表。
- [ ] 实现 `messages` 表。
- [ ] 实现 `message_reactions` 表。
- [ ] 为会话、消息时间、未读状态建立索引。

#### P1.5 订单、支付、物流
- [ ] 实现 `orders` 表。
- [ ] 实现 `order_items` 表。
- [ ] 实现 `order_status_events` 表。
- [ ] 实现 `shipments` 表。
- [ ] 实现 `shipment_events` 表。
- [ ] 实现 `payments` 表。
- [ ] 实现 `payment_transactions` 表。
- [ ] 订单快照必须独立于商品当前状态，不能反向依赖商品实时字段。

#### P1.6 评价、钱包、会员、平台配置
- [ ] 实现 `reviews`、`review_media`、`review_tags`、`review_tag_links`、`trust_scores` 表。
- [ ] 实现 `wallet_accounts`、`wallet_transactions` 表。
- [ ] 实现 `membership_plans`、`membership_subscriptions` 表。
- [ ] 实现 `notifications`、`feature_flags`、`app_config`、`outbox_events`、`audit_logs` 表。
- [ ] 为钱包、通知、审计、平台配置建立独立仓库。

#### P1.7 数据完整性
- [ ] 所有主键使用字符串 ID，统一生成策略。
- [ ] 软删除策略和状态流转规则统一定义。
- [ ] 关键写操作必须放在事务中完成。
- [ ] 发布后的商品快照不得被草稿表回写污染。
- [ ] 消息采用追加写，不允许原地编辑。
- [ ] 订单、支付、评价、物流状态变更必须写状态事件表。

### P2. API 基础层与响应规范

#### P2.1 统一响应封装
- [ ] 实现 `ApiEnvelope` 输出工具。
- [ ] 实现 `ApiMeta`、分页元信息、请求 ID 注入。
- [ ] 实现错误响应映射表，按校验、认证、权限、冲突、系统错误分类。
- [ ] 保证所有路由都遵守同一返回结构。

#### P2.2 中间件与基础接口
- [ ] 实现请求 ID 中间件。
- [ ] 实现统一日志中间件。
- [ ] 实现 CORS 策略。
- [ ] 实现 `/health`。
- [ ] 实现 `/version`。
- [ ] 实现 `/config/public`。

#### P2.3 分页与查询策略
- [ ] 统一分页参数命名。
- [ ] 统一列表接口返回 `meta.page`。
- [ ] 明确 offset/limit 或 cursor 的选型。
- [ ] 为首页、搜索、商品列表、消息列表、订单列表设计可复用分页查询。

### P3. 认证、会话、资料

#### P3.1 注册与登录
- [ ] 实现 `POST /auth/register`。
- [ ] 实现 `POST /auth/login`。
- [ ] 实现 `POST /auth/logout`。
- [ ] 实现 `POST /auth/refresh`。
- [ ] 实现 `GET /auth/session`。
- [ ] 明确并实现登录页 `guest entry` 的后端策略，允许未登录用户进入只读浏览模式，并定义游客态可访问接口范围。
- [ ] 注册时必须同时写入 `users`、`user_profiles`、`user_consents`、`auth_sessions`。
- [ ] 登录时写入 `login_attempts`，并更新 `last_login_at`。

#### P3.2 资料与设置
- [ ] 实现 `GET /users/me`。
- [ ] 实现 `PATCH /users/me`。
- [ ] 实现 `GET /pages/me/settings`。
- [ ] 实现 `GET /users/{user_id}`。
- [ ] 实现 `GET /users/{user_id}/followers` 和 `/following`。
- [ ] 实现 `GET /users/me/stats`。
- [ ] 生日到年龄的派生计算放在服务层，不能重复存储成两个主字段。

#### P3.3 权限与安全
- [ ] 明确当前版本是否先做匿名可访问和登录后可写。
- [ ] 对用户私有资源做所有权检查。
- [ ] 对敏感操作写审计日志。
- [ ] 为登录接口增加失败次数限制与锁定策略。

### P4. 主页、搜索、商品、发布

#### P4.1 主页与导航
- [ ] 实现 `GET /pages/home`。
- [ ] 实现 `GET /home/feed`。
- [ ] 实现 `GET /categories`。
- [ ] 实现 `GET /service-catalog`。
- [ ] 实现 `GET /banners`。
- [ ] 支持首页 hero、分类 grid、精选、快捷入口、推荐位组合。

#### P4.2 搜索与发现
- [ ] 实现 `GET /pages/search`。
- [ ] 实现 `GET /search/suggestions`。
- [ ] 实现 `GET /search/facets`。
- [ ] 实现 `GET /listings`。
- [ ] 实现 `GET /categories/{category_id}/listings`。
- [ ] 为商品搜索建立 projection 或 FTS 方案。
- [ ] 支持关键词、分类、价格、地点、状态等过滤。

#### P4.3 商品详情与收藏
- [ ] 实现 `GET /pages/listings/{listing_id}`。
- [ ] 实现 `GET /listings/{listing_id}`。
- [ ] 实现 `GET /listings/{listing_id}/media`。
- [ ] 实现 `GET /listings/{listing_id}/seller`。
- [ ] 实现 `GET /listings/{listing_id}/specs`。
- [ ] 实现 `GET /listings/{listing_id}/similar`。
- [ ] 实现 `GET /listings/{listing_id}/inquiries`。
- [ ] 为商品详情返回 `3d_preview` 数据块，至少包含 `preview_status`、`viewer_url`、`model_url`、`model_ply_url`、`model_sog_url` 和 `log_url`。
- [ ] 商品详情在 3D 资源未就绪时必须返回明确的加载中、生成中或失败状态，并提供静态图降级信息。
- [ ] 实现 `POST /listings/{listing_id}/favorite`。
- [ ] 实现 `DELETE /listings/{listing_id}/favorite`。

#### P4.4 卖家发布流
- [ ] 实现 `POST /listings/drafts`。
- [ ] 实现 `GET /listings/drafts/{draft_id}`。
- [ ] 实现 `PATCH /listings/drafts/{draft_id}`。
- [ ] 实现 `POST /listings/drafts/{draft_id}/publish`。
- [ ] 实现 `POST /uploads/presign`。
- [ ] 商品发布时生成稳定的封面媒体、草稿快照与正式商品记录。

### P5. 远程 3DGS 训练服务接入

#### P5.1 服务客户端
- [ ] 新建独立的 3DGS 客户端封装，不要让 API 路由直接调用 subprocess。
- [ ] 对接远程训练服务的基础地址、超时、重试、鉴权头。
- [ ] 统一处理网络错误、非 2xx、超时和服务不可达场景。
- [ ] 封装任务创建、状态查询、启动、取消、Mask 预览、Mask 确认、Mask Debug、模型产物查询。

#### P5.2 商品与 3DGS 关联
- [ ] 设计商品、媒体资产与 3D 模型任务之间的关联关系。
- [ ] 上传视频后能够发起远程 3DGS 任务。
- [ ] 将远程返回的 `model_url`、`model_ply_url`、`model_sog_url`、`viewer_url`、`log_url` 落库。
- [ ] 商品发布成功后，将远程 3DGS 返回的模型与 Viewer 链接回写到 listing 的 3D 预览字段中。
- [ ] 将任务进度、状态、错误信息同步到 SQLite。
- [ ] 决定是否在本地后端代理远程静态资源，或直接把远程 URL 暴露给前端。

#### P5.3 训练状态同步
- [ ] 设计轮询任务或后台 worker，同步远程训练状态到本地数据库。
- [ ] 定义失败重试、幂等更新和最终态合并策略。
- [ ] 对 `ready`、`failed`、`cancelled` 等状态定义清晰的本地镜像。
- [ ] 如果后端需要支持发布页里的 3D 模型查看，必须确保 Viewer URL 可稳定获取。

#### P5.4 3DGS 业务规则
- [ ] 训练服务由远程服务器提供，不在电商后端本地重新部署训练框架。
- [ ] 需要在文档中明确远程服务地址、端口、环境变量、访问权限与故障排查方式。
- [ ] 如果后续电商平台增加“商品 3D 重建”能力，必须复用这个远程服务客户端层，而不是在路由里散写调用逻辑。

### P6. 聊天、订单、评价、通知、钱包、会员

#### P6.1 聊天
- [ ] 实现 `GET /pages/conversations/{conversation_id}`。
- [ ] 实现 `GET /conversations`。
- [ ] 实现 `GET /conversations/{conversation_id}`。
- [ ] 实现 `GET /conversations/{conversation_id}/messages`。
- [ ] 实现 `POST /conversations/{conversation_id}/messages`。
- [ ] 实现 `POST /conversations/{conversation_id}/read`。
- [ ] 实现 `POST /conversations/{conversation_id}/typing`。
- [ ] 消息必须保持追加写，不能覆盖历史内容。

#### P6.2 订单与物流
- [ ] 实现 `GET /pages/orders/{order_id}/success`。
- [ ] 实现 `GET /pages/orders/{order_id}`。
- [ ] 实现 `GET /orders/{order_id}`。
- [ ] 实现 `GET /orders/{order_id}/timeline`。
- [ ] 实现 `GET /orders/{order_id}/receipt`。
- [ ] 实现 `POST /orders/{order_id}/confirm-receipt`。
- [ ] 实现 `POST /orders/{order_id}/cancel`。
- [ ] 实现 `POST /orders/{order_id}/dispute`。
- [ ] 订单创建时必须写 item snapshot 和 totals snapshot。

#### P6.3 评价与信任
- [ ] 实现 `GET /pages/reviews/{order_id}`。
- [ ] 实现 `GET /reviews/tags`。
- [ ] 实现 `POST /reviews`。
- [ ] 实现 `GET /orders/{order_id}/review-draft`。
- [ ] 实现 `PATCH /orders/{order_id}/review-draft`。
- [ ] 实现 `GET /listings/{listing_id}/reviews`。
- [ ] 审核评价发布条件，默认只允许完成订单后评价。

#### P6.4 通知、会员、钱包
- [ ] 实现 `GET /notifications`。
- [ ] 实现 `POST /notifications/{notification_id}/read`。
- [ ] 实现 `POST /notifications/read-all`。
- [ ] 实现 `GET /badges/summary`。
- [ ] 实现 `GET /wallet/summary` 与 `GET /wallet/transactions`。
- [ ] 实现 `GET /memberships/current` 与 `POST /memberships/upgrade`。
- [ ] 把余额和订单、会员变更统一走 ledger 或事件表。

#### P6.5 实时同步（可选增强）
- [ ] 评估并实现 `/ws/conversations/{conversation_id}` 与 `/ws/notifications` 实时通道。
- [ ] 定义实时事件为 append-only 事件流，携带事件 ID、server timestamp 和未读计数增量。
- [ ] 明确 WebSocket 或 SSE 不可用时的轮询降级策略，避免影响 REST 主流程。

### P7. 页面 Bootstrap 与前端对接

#### P7.1 页面级接口
- [ ] 实现 `GET /pages/auth/login`。
- [ ] 实现 `GET /pages/auth/register`。
- [ ] 实现 `GET /pages/home`。
- [ ] 实现 `GET /pages/search`。
- [ ] 实现 `GET /pages/listings/{listing_id}`。
- [ ] 实现 `GET /pages/conversations/{conversation_id}`。
- [ ] 实现 `GET /pages/orders/{order_id}`。
- [ ] 实现 `GET /pages/orders/{order_id}/success`。
- [ ] 实现 `GET /pages/reviews/{order_id}`。
- [ ] 实现 `GET /pages/me`。
- [ ] 实现 `GET /pages/me/settings`。

#### P7.2 Bootstrap 数据组合
- [ ] 所有 bootstrap 接口都要返回前端可直接渲染的组合数据。
- [ ] 主页 bootstrap 需要包含 hero、分类、推荐、快捷入口。
- [ ] 商品详情 bootstrap 需要包含 listing、media、seller、specs、similar、inquiries、reviews、actions。
- [ ] 商品详情 bootstrap 需要包含 3D 预览入口、模型状态和失败占位信息，确保前端可以直接渲染 3D 展示模块。
- [ ] 订单详情 bootstrap 需要包含 status、address、snapshot、timeline、receipt、action bar。
- [ ] 个人中心 bootstrap 需要包含 profile、stats、listings、VIP、wallet、service cards。

#### P7.3 兼容性与扩展性
- [ ] 后端返回值可以多字段扩展，但不能随意改字段语义。
- [ ] 对前端未识别字段保持兼容。
- [ ] 页面 bootstrap 只负责资源组合，不要依赖 Flutter 组件名。

### P8. 测试、验收与运维

#### P8.1 测试
- [ ] 为 SQLite 仓库层补单元测试。
- [ ] 为认证、商品、订单、聊天、评价、通知、钱包等核心接口补集成测试。
- [ ] 为远程 3DGS 客户端补 mock 测试。
- [ ] 为页面 bootstrap 接口补 contract 测试。
- [ ] 为错误码与分页元信息补回归测试。

#### P8.2 验收
- [ ] `/health`、`/version`、`/config/public` 可用。
- [ ] 登录、注册、会话恢复可用。
- [ ] 首页、搜索、商品详情、卖家发布流可用。
- [ ] 远程 3DGS 服务联动可用，能在商品场景里拿到模型 URL 或 Viewer URL。
- [ ] SQLite 数据可以正确导出、备份和恢复。

#### P8.3 部署与运维
- [ ] 提供本地与 Linux 服务器的环境变量样例。
- [ ] 提供 SQLite 备份/恢复脚本。
- [ ] 提供日志和静态资源缓存策略。
- [ ] 明确远程 3DGS 服务不可达时的降级行为。
- [ ] 保持部署文档与 API 文档同步更新。

## 5. 推荐里程碑顺序

### M1. 后端骨架可运行
- SQLite 初始化完成。
- FastAPI 入口可启动。
- `health/version/config` 可访问。
- envelope、错误码、分页元信息统一。

### M2. 账号与浏览链路可用
- 注册、登录、会话、资料、主页、搜索、商品详情接口可用。
- 主页和详情页能返回前端可直接渲染的数据。
- SQLite 种子数据可把应用跑起来。

### M3. 发布与 3DGS 联动可用
- 卖家发布流可创建草稿、上传媒体、发布商品。
- 商品视频可以关联远程 3DGS 训练任务。
- 能拿到远程模型产物和 Viewer 链接。

### M4. 交易闭环可用
- 聊天、订单、物流、评价、通知、钱包、会员接口完善。
- 订单状态流转、评价规则、消息追加写都符合规范。

### M5. 稳定化与上线准备
- 测试补齐。
- 运维脚本补齐。
- 文档与代码同步。
- 兼容性与回归检查完成。

## 6. 文件级改造清单

> 这部分用于拆工单时定位到具体文件。

- `backend/app/main.py`：替换路由注册、统一中间件、健康检查。
- `backend/app/schemas.py`：补齐电商资源模型、页面 bootstrap 模型、分页模型、错误模型。
- `backend/app/routes/`：按领域拆分为 auth/users/home/listings/messages/orders/reviews/notifications/pages/config 等。
- `backend/app/services/`：新增领域服务与远程 3DGS 客户端。
- `backend/app/repositories/`：新增 SQLite 仓库。
- `backend/app/db/` 或 `backend/app/core/database.py`：新增连接、迁移、初始化、种子。
- `shared/config.py`：补齐 SQLite 与远程 3DGS 配置。
- `shared/task_store.py`：如果继续保留，需要降级为通用文件存储工具，否则逐步弃用。
- `storage/db/`：放 SQLite 数据库文件与备份目录。
- `tests/`：放核心接口和数据库测试。
- `deploy/`：放服务部署脚本、环境变量和备份脚本。

## 7. 风险与注意事项

- SQLite 适合单机和中小并发场景，但不适合高并发写入，后面要保留平滑迁移到 PostgreSQL 的可能性。
- 远程 3DGS 服务不可作为电商后端的单点依赖，商品浏览和非 3D 功能必须在远程训练服务异常时仍可用。
- 旧的 3DGS 任务流代码不要一次性删除，建议先抽离可复用部分，再逐步替换。
- 页面 bootstrap 接口和资源接口必须同步演进，否则前端很容易出现字段不一致。
- 订单、钱包、评价等模块需要更严格的事务边界，避免 SQLite 写入时状态漂移。

## 8. 完成标准

- 电商平台后端可以使用 SQLite 独立启动。
- 所有 `API_PROTO.md` 中定义的关键接口都已实现或按阶段实现。
- 所有 `DATABASE_PROTO.md` 中首发必需的数据模型都有 SQLite 落地方案。
- 后端能够稳定关联远程 3DGS 训练服务，并把模型结果回写到业务数据中。
- 测试、部署、备份、文档都能支撑后续迭代。
