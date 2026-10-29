# 完整视频事实提取与 Codex 输入包

当前主线：

```text
本地完整 MP4 → DashScope 原生 SDK 上传完整视频
  → qwen3.8-max 单次全片事实提取 → 原样保存 video_facts.md
  → prepare-tasks 导出 codex_input.md（RULES_PENDING）
  → 后续另行制定 Codex 任务构造规则 → 人工复看并单独裁决 Gold
```

视频模型只提取事件、对象、状态、过程与可追溯关系。事实报告是未经人工核验的模型描述，
原始 MP4 是最终事实依据。当前不生成问题、Benchmark 依赖、历史必要性判断或任务候选。

本次改造没有调用 API、没有分析真实视频，也没有复核旧实验数据。真实 endpoint、账户权限、
上传及 qwen3.8-max 的端到端调用仍待后续单视频实测。任务规则尚未制定。

## 文件与入口

```text
annotation_pipeline/
  __main__.py                 python -m annotation_pipeline
  configs/config.example.json 新配置样例
  prompts/video_facts.md      随指令包逐字复制的 Video Fact Extraction V1
  prompts/task_rules.md       RULES_PENDING 与未来候选基本字段约定
  scripts/cli.py              analyze / prepare-tasks
  scripts/common.py           严格配置、路径及 manifest 写入
  scripts/backend.py          DashScope 2.x 原生完整视频调用
  scripts/media.py            只读 ffprobe 预检查
  scripts/pipeline.py         原文落盘与 Codex 输入包导出
  tests/test_pipeline.py      合成文件、模拟 SDK、禁止网络与旧资料读取
  runs/                      本地运行产物，Git 忽略
```

旧 mine/probe/review 命令及其切片、Base64 JSON、依赖挖掘、自动筛选实现已移除。
已有本地配置和运行产物保持原位，不迁移、不复用、不读取。根目录与 task_mining 的历史说明
未在本轮范围内改动；本目录新入口以本文为准。

## 安装与配置

Python 3.11+；FFmpeg 发行包中的 ffprobe 需在 PATH，或通过配置指定。
从仓库根目录执行：

```powershell
python -m pip install -r annotation_pipeline/requirements.txt

# 使用新名字，避免覆盖既有 config.local.json；目标已存在时请直接编辑。
if (-not (Test-Path -LiteralPath annotation_pipeline/configs/qwen.local.json)) {
    Copy-Item -LiteralPath annotation_pipeline/configs/config.example.json -Destination annotation_pipeline/configs/qwen.local.json
}

# 在当前终端设置配置指定的环境变量；真实值由你在本地填写。
$env:DASHSCOPE_API_KEY = "<你的 API Key>"
```

密钥仅从 api_key_env 指定的环境变量读取，不再读取旧凭据 JSON。
不要把真实密钥写入样例配置或 Git。新配置拒绝未知字段，
因此旧配置不会被静默解释成新流程；请基于新样例创建配置。

| 字段 | 默认值与含义 |
|---|---|
| provider / model | dashscope / qwen3.8-max，本轮固定 |
| base_url | https://maas.qianwenaiapi.com/api/v1；按本地账户设置原生 API endpoint，不是 compatible-mode 地址 |
| api_key_env | DASHSCOPE_API_KEY，可改为其他环境变量名称 |
| fps | 1.0；可在配置或 analyze --fps 中调整 |
| timeout_seconds | 300 秒；SDK 自动重试固定关闭 |
| output_dir | ../runs，相对该配置文件所在目录解析 |
| ffprobe | ffprobe，可设置可执行文件路径；自定义路径建议用绝对路径 |

不指定 --config 时使用随代码提供的新 config.example.json，不会隐式加载旧 config.local.json。
--video 相对当前工作目录解析。SDK 延迟导入，prepare-tasks 与合成测试无需安装 SDK 或设置密钥。

实现依据官方 [DashScope 2.x SDK](https://github.com/dashscope/dashscope-sdk-python)
和[视频理解文档](https://docs.qwencloud.com/developer-guides/multimodal/vision)：
使用 dashscope.Client(protocol="native", max_retries=0)，调用
client.multimodal.chat.create，读取 response.output_text 与可用 usage。
Windows 视频输入形如 file://D:/videos/example.MP4，POSIX 为 file:///...。
提示词直接读取整个 Markdown 文本，不添加 system 提示词、不做模板替换、不设置 JSON 输出格式。

## 运行

以下 analyze 命令会上传视频并发出一次可能计费的请求；本轮开发没有执行它：

```powershell
python -m annotation_pipeline analyze --video "D:/local/videos/GX010021.MP4" --video-id GX010021 --run-id GX010021_qwen38_v1 --config annotation_pipeline/configs/qwen.local.json

# 在同一 output_dir 内读取上述报告，仅导出输入包，无 API 请求
python -m annotation_pipeline prepare-tasks --run-id GX010021_qwen38_v1 --config annotation_pipeline/configs/qwen.local.json

# 仅查看命令帮助，无视频读取或 API 请求
python -m annotation_pipeline --help
```

analyze 先检查 MP4 存在且非空、大小限制和 ffprobe 元数据/开头视频包，计算原文件 SHA-256。
这些检查不等于全片解码或视频事实核验。缺视频或 ffprobe 会失败并阻止上传。

本地文件上限按保守的十进制 100 MB（100,000,000 字节）执行。超限明确失败，不压缩、不切片、
不更改 FPS。需要更大完整视频时，应另行采用服务商支持的已上传公网 URL 工作流；
当前 CLI 仅接受本地 MP4，不接受 URL，也不会自动切换传输方式。

成功后目录内容：

```text
runs/<run_id>/
  manifest.json       视频路径/大小/SHA-256、预检查元数据、provider/model/endpoint、
                      prompt_version/prompt_sha256、FPS、调用配置、时间、状态、usage
  prompt.md           本次使用的完整提示词快照
  video_facts.md      模型返回 Markdown 原文，UTF-8，保留空白与换行
  codex_input.md      执行 prepare-tasks 后创建
```

不因 A–G 标题缺失而补写或重排报告。模型原文不代表已覆盖全片，也不代表事实正确。
已知截断/非正常结束会保留返回原文并标记 FAILED，阻止导出；空响应或请求失败不伪造报告。
manifest 记录 CANDIDATE/PENDING 和 fact_verification=NOT_PERFORMED。
usage 缺失时为 null；本地没有计价表，预估费用和真实账单保持 null，后续调用需与提供方对账。

每个 run_id 只能新建一次，成功、失败、调用中断和已有人工目录均不覆盖、不自动重试。
超时或中断可能已计费，manifest 的 CALLING/FAILED 状态不保证没有扣费；核对后再选新 run_id。
调用过程强制终止可能留下 CALLING；程序不会把它当作成功。prepare-tasks 也拒绝覆盖已有输入包。

## Codex 输入包与后续规则

prepare-tasks 只处理本流程 SUCCESS 运行，检查报告哈希后打包：
完整报告原文、原始视频与调用元数据、task_rules.md 绝对路径及其当前内容、Candidate/Gold 边界。
它不调用模型、不读原视频内容、不核验报告事实，也不输出 task_candidates.jsonl。
报告修改、缺失或失败运行会明确拒绝导出。

task_rules.md 明确为 RULES_PENDING，仅登记未来 JSONL 的基本字段：
task_id、video_id、track、query_time、question、proposed_answer、
evidence_refs、dependency_reason、review_status=PENDING。
完整任务契约、历史依赖与遮蔽构造规则留待下一轮讨论，不用旧提示词替代，不新增筛选规则。

Codex 输入包包含全片离线上下文，不可直接提供给被测流式 Agent。
后续候选答案不是真值；只有人工复看原视频并记录真实审核者、时间和理由，确认必要证据、
历史必要性与答案后，才能单独发布 Gold。

## 离线验证

在仓库根目录执行：

```powershell
python -m unittest discover -v
# 只验证本目录
python -m unittest discover -s annotation_pipeline/tests -t . -v
```

新测试只使用临时合成文件和模拟 SDK/ffprobe，阻止真实网络连接，并限制运行时文件读取，
保证不读取旧标注、旧候选、旧 Gold 或旧运行产物。测试覆盖原文保留、单次完整视频请求、
配置/FPS、失败留档、密钥脱敏、覆盖保护和无任务生成的输入包导出。
仓库原有 Legacy 兼容性测试保持原样。
