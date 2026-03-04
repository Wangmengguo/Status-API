# API Status Monitor 运维指南

供日常查阅和后续 agent 继续工作参考。

---

## 一、架构概览

```
GitHub Actions (cron)  →  checker.py  →  data/*.json  →  GitHub Pages
                              ↓
                        各第三方 API (HTTP 探测)
```

- **检测脚本**：`checker.py`，支持 Anthropic 和 OpenAI 两种 API 格式
- **数据文件**：`data/status.json`（当前状态）、`data/history.json`（历史与事件）
- **状态页面**：`index.html`，纯静态，直接 fetch 上述 JSON 渲染

---

## 二、API 格式说明

当前监测的 API 分为两种格式，由 `config.yaml` 的 `format` 字段控制：

| format      | 端点                 | 认证方式                | 说明                          |
|------------|----------------------|-------------------------|-------------------------------|
| `anthropic` | `/v1/messages`       | `x-api-key` header      | Claude 原生格式，模仿 Claude Code |
| `openai`   | `/v1/chat/completions` | `Authorization: Bearer` | OpenAI 兼容格式               |

Anthropic 格式会附带 `anthropic-version` 和 `User-Agent: claude-code/2.1.0`，以提高兼容性。

---

## 三、检测周期与费用

- **cron**：`*/15 0-15 * * *`（UTC 0:00–15:59 = 北京时间 8:00–23:59）
- **间隔**：15 分钟一次
- **静默时段**：北京时间 0:00–8:00 不检测（节省费用）
- **每天检测次数**：约 64 次
- **参考费用**：每次约 $0.002，每月约 $3.8

---

## 四、暂停 / 恢复检测

### 4.1 暂停全部检测

1. 打开仓库 → `Actions` → `API Status Check`
2. 右上角 `···` → `Disable workflow`
3. 恢复：同路径 → `Enable workflow`

### 4.2 暂停某个 API

1. 打开仓库 → 点击 `config.yaml`
2. 点击编辑按钮（铅笔图标）
3. 在要暂停的 API 条目每行前加 `#` 注释：

```yaml
  # - name: "Aigocode #3"
  #   base_url: "https://api.aigocode.com"
  #   model: "claude-opus-4-6"
  #   api_key_env: "AIGOCODE_KEY_3"
  #   format: "anthropic"
```

4. 右上角 `Commit changes` 保存
5. 恢复：去掉注释后再次 Commit

---

## 五、状态页面说明

- **时间线**：48 个方块，每格 = 1 小时，最近 48 小时
- **颜色**：绿 = 正常，黄 = 降级，红 = 宕机，灰 = 无数据
- **事件列表**：展示 Investigating / Resolved 事件及时长

---

## 六、手动触发检测

仓库 → `Actions` → `API Status Check` → `Run workflow` → 绿色按钮

---

## 七、当前配置的 API 列表（截至 2026-03）

| 名称         | Base URL                          | 模型             | Secret 名        |
|--------------|-----------------------------------|------------------|-------------------|
| Foxcode      | https://code.newcli.com/claude/aws | claude-opus-4-6 | FOXCODE_KEY       |
| Aiberm       | https://aiberm.com                | claude-opus-4-6 | AIBERM_KEY        |
| Aigocode #1  | https://api.aigocode.com          | claude-opus-4-6 | AIGOCODE_KEY_1    |
| Aigocode #2  | https://api.aigocode.com          | claude-opus-4-6 | AIGOCODE_KEY_2    |
| Aigocode #3  | https://api.aigocode.com          | claude-opus-4-6 | AIGOCODE_KEY_3    |

---

## 八、常见问题排查

| 现象                 | 可能原因                          | 处理建议                      |
|----------------------|-----------------------------------|-------------------------------|
| Missing env: XXX     | `API_KEYS_JSON` 缺 key 或名称错误 | 检查 Secrets，key 名与配置一致 |
| HTTP 404             | 端点路径错误                      | 确认 `format` 与提供商文档一致 |
| HTTP 401             | key 无效或权限不足                | 检查 key、模型、base_url       |
| HTTP 502              | 服务端问题或模型不可用            | 稍后重试或联系服务商           |
| 时间线全灰           | 数据未积累或历史被 prune          | 等待几轮检测或检查 history.json |

---

## 九、文件结构（供 agent 参考）

```
Status_API/
├── .github/workflows/check.yml   # 调度与步骤
├── config.yaml                   # API 列表（主要编辑）
├── checker.py                    # 检测逻辑
├── data/
│   ├── status.json               # 当前状态（自动生成）
│   └── history.json              # 历史与事件（自动生成）
├── index.html                    # 状态页
├── requirements.txt
├── README.md                     # 初次搭建说明
└── OPERATIONS.md                 # 本文档
```

关键逻辑在 `checker.py` 的 `check_one_api`、`build_request`、`validate_response`。

---

## 十、状态页地址

https://wangmengguo.github.io/Status-API/
