# VERTU 内容自动化 vvv 群回销模板

适用对象：`vertu-10`、`vertu-2`、`vertu` 和 `vertu-skill`。

唯一群通知通道：

- provider：`vvv_user_robot`
- app ID：`VERTU_VVV_APP_ID`
- channel ID：`VERTU_VVV_CHANNEL_ID`
- endpoint：`VERTU_VVV_PUSH_ENDPOINT`
- sender：`scripts/vertu-vvv-notify.ts`

禁止使用旧微信网关、`WECHAT_*` 配置、群名称路由或昵称路由。App Secret
只能来自 `VERTU_VVV_APP_SECRET` 或 macOS Keychain，禁止写入 Skill、脚本、
飞书、运行产物或回销正文。

成功发布模板：

```text
【VERTU 英文内容发布回销｜YYYY-MM-DD】

✅ 今日已发布：N 篇（Sanity post）
栏目：Guides N｜Lifestyle N｜AI Tools N｜News 0

今日选题
1. Article title
   https://vertu.com/section/slug
...

质量门禁
- 候选轮次：30 / 60 / 90 / 120；入选：N；替补：N；拒绝：N
- SEO QA：N/N PASS
- Discover：N/N READY
- 主图：N/N PASS
- 线上验证：N/N PASS
- Loop Runtime：ALLOW → RELEASED；碰撞/预算阻塞：0

监控计划
- 24h：技术交付与初步 GA4
- 72h：成熟 GSC Discover/Search 首轮信号
- 7d：一次受控优化判断
- 28d：成熟表现归因与选题学习

运行 ID：...
```

阻塞或无可执行项模板：

```text
【VERTU 内容自动化回销｜YYYY-MM-DD】

状态：BLOCKED / DAILY_QUOTA_BLOCKED / NO_TOPIC / NO_QUEUED_ITEMS / DATA_NOT_MATURE / FAILED
阶段：LOOP_RUNTIME / TOPIC / QA / DISCOVER / IMAGE / SANITY / LIVE_VERIFY / HANDOFF
通过：N
阻塞或无操作原因：...
Loop Runtime：PAUSED / COLLISION_BLOCKED / BUDGET_BLOCKED / ATTEMPT_LIMIT / STATE_INVALID / RELEASE_INCOMPLETE / N/A
运行 ID：...
证据路径：...
```

调用方式：

```bash
pnpm notify:vvv -- --send \
  --body-file <receipt-message.txt> \
  --receipt-file <vvv-notification.json>
```

仅当脚本返回 `status=SENT` 才能记录群回销成功。`DELIVERY_UNKNOWN` 禁止盲目
重发，应保留回执并人工核对。
