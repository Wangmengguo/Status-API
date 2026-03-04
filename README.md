# API Status Monitor

一个最简洁的 API 可用性监测页面：

- GitHub Actions 每 5 分钟自动检测一次 API
- 检测结果写入 `data/status.json` 和 `data/history.json`
- GitHub Pages 自动展示网页（类似 status page）

---

## 1) 你需要做的准备

1. 把本项目推到 GitHub 仓库
2. 在仓库中打开 `Settings -> Secrets and variables -> Actions`
3. 新建一个 Secret：`API_KEYS_JSON`
4. 值填写为 JSON（示例）：

```json
{
  "FOXCODE_KEY": "sk-xxx",
  "AIBERM_KEY": "sk-yyy",
  "AIGOCODE_KEY": "sk-zzz"
}
```

---

## 2) 配置要监测的 API

编辑 `config.yaml`：

```yaml
apis:
  - name: "Foxcode"
    base_url: "https://code.newcli.com/claude/aws"
    model: "claude-opus-4-6"
    api_key_env: "FOXCODE_KEY"

  - name: "Aiberm"
    base_url: "https://aiberm.com"
    model: "claude-opus-4-6"
    api_key_env: "AIBERM_KEY"

  - name: "Aigocode"
    base_url: "https://api.aigocode.com"
    model: "claude-opus-4-6"
    api_key_env: "AIGOCODE_KEY"

settings:
  check_timeout: 30
  max_history_days: 90
  user_message: "ping"
```

字段说明：

- `name`：页面展示名
- `base_url`：API 的 base URL（不带 `/chat/completions` 也可以）
- `model`：要测试的代表模型（建议每个服务只测 1 个）
- `api_key_env`：API key 的逻辑名称，会从 `API_KEYS_JSON` 里查找

---

## 3) 启用 GitHub Pages

1. 进入仓库 `Settings -> Pages`
2. `Source` 选择 `Deploy from a branch`
3. Branch 选择 `main`，目录选择 `/ (root)`
4. 保存后等待部署完成

页面地址通常是：

`https://<你的GitHub用户名>.github.io/<仓库名>/`

---

## 4) GitHub Actions 自动检测

工作流文件在：

`/.github/workflows/check.yml`

默认每 5 分钟执行一次，也支持手动触发：

- GitHub 仓库 -> `Actions` -> `API Status Check` -> `Run workflow`

---

## 5) 本地手动测试（可选）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export API_KEYS_JSON='{"FOXCODE_KEY":"你的key","AIBERM_KEY":"你的key","AIGOCODE_KEY":"你的key"}'
python checker.py
```

执行后会更新：

- `data/status.json`（当前状态）
- `data/history.json`（历史与事件）

---

## 6) 常见问题

- 页面显示 `Missing env: XXX`  
  说明 `API_KEYS_JSON` 中没有该 key 名，或名称不匹配。

- API 返回 4xx  
  多数是 key、模型名或 base_url 不正确。

- 想新增一个 API  
  在 `config.yaml -> apis` 里复制一条配置即可。
