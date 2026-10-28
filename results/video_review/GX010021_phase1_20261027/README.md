# GX010021 第一阶段视频事实核验准备

状态：**CANDIDATE / PENDING**。日期：2026-10-27（Asia/Shanghai）。没有人工审定，没有Gold，没有正式Agent Benchmark或Replay Harness。

直接打开同目录的 [index.html](index.html)。页面内嵌候选数据，无需前端依赖或服务。
原视频通过相对路径引用，须保留本目录与项目根目录的位置关系。若浏览器限制本地媒体，从项目根运行
`python -m http.server 8000 --bind 127.0.0.1`，再访问
`http://127.0.0.1:8000/results/video_review/GX010021_phase1_20261027/index.html`。
支持任务筛选、原视频跳转、历史/当前片段、解码帧、55条原文对照、本机待审草稿与JSON导出。
草稿保存在浏览器localStorage；导出文件需另行存档。页面不会批准实体、修改数据包或写Gold。

## 文件与结果

- [timeline.md](timeline.md)：27组事件/状态候选与逐段人工确认重点。
- [tasks.md](tasks.md)：9条新增任务，T1三条、T2两条、T3四条，含全部核验字段。
- [review_data.json](review_data.json)：审核侧车，存放候选答案、视觉方法、不确定性、人工队列与实验映射，不改变原Schema。
- `../../../datasets/ego_mc/GX010021_video_phase1_20261027/`：Schema 0.1.0的独立增量包，保留原包记录。
- `clips/`：36个H.264审核代理片段；[clip_manifest.json](clip_manifest.json)含原视频区间、哈希、时长与PENDING状态。
- `frames/`、[frame_index.json](frame_index.json)：349张解码取样帧，含实际PTS与SHA-256；`sheets/`为18张已检查接触表。
- `detail/`：鸡蛋60–90、油554–582、黄油426–434、粉598–604、入烤箱686–694秒的2fps加密取样。标签是名义近似时间，不用于帧级Gold定界。
- [ffprobe.json](ffprobe.json)：媒体流信息；[keyframes.json](keyframes.json)为84个编码关键帧元数据，实际关键帧图像在`keyframe_images/`，PTS与哈希在[keyframe_image_index.json](keyframe_image_index.json)。这些额外图像为PENDING，语义观察依据上述已检查接触表。
- `experiment_backup/`：旧E1–E6计划、旧实验README与旧准备配置完整备份；原计划未改写。

视频为854×480、30000/1001 fps、696.929567秒。ffprobe只发现视频流和tmcd时间码数据流，**没有音频流**。
所有55条原标注只能确认“原文中这样写”，不能确认真实发言、句子起止、同步偏移、语音许可或承诺。

## 观察、推断与门禁

本次由AI查看本地视频解码图片；未调用外部视频分析API，没有真实人工审核者。
先检查全片约2.002秒间隔的349张画面，再检查五段2fps加密接触表。不是全片连续逐帧穷尽分析；
取样间短动作、遮挡、画外行为可能遗漏。片段时间是已检查证据包络，不是从标注点扩出的动作真值。
精确动作开始/结束均为null。状态检查点是待审提案，known_at取保守证据结束时间，不是在线发布许可。

视觉描述用AI_VISUAL_CANDIDATE标识并引用视频；原文按原JSON Pointer、quote与标签保留。
糖、牛奶、黄油、面粉、食用油等名称含外观/包装身份推断；可直接看见的棕色颗粒、白色液体、黄色块、白粉、淡黄色液体分别陈述。
不能据此填写精确配方用量、温度、黏度、防粘效果。没有将原发言Event直接转换成动作。

Schema未改动。原provenance.method枚举没有AI视觉方法，新增记录沿用text_candidate，
notes明确说明是AI对实际画面的候选观察，非人工、非仅从原标注推导；详细方法在侧车保存。
原annotation_utterance与新增observed_action继续分层。全部新实体均CANDIDATE/PENDING、PRIVATE；
available_at:null，任务禁用、earliest_answerable_time:null、history_necessity:PENDING。
两个版本gold.jsonl均0字节；规则有效期、supersedes、历史必要性没有自动批准。

新包保留原55条文字证据、91条实体，新增36条视频证据、27个Event、27个State、5个Dependency、9个Task。
完整新包为91 Evidence、82 Event、30 State、9 Dependency、19 Rule、12 Task、7 Intervention、0 Gold。
旧3条Task和旧状态占位原样保留；工作台重点显示本轮9条，不能混同两轮数量。

## 人工复核优先项

1. 60–90秒：两次打蛋与完整蛋放回；79秒反馈不能证明已打入三枚。
2. 390–432秒：两次取出仍有黄色块状物；431.658秒Success不等于完全融化；实际加热时长UNKNOWN。
3. 556–581秒：瓶身、倒液体与倾斜、内壁覆盖；画面无法验证文字许可链。
4. 598–604秒：追加白粉动作、量与材料；不自动判违规。
5. 632–642、686–694秒：倒入与入烤箱的精确边界；630.612秒指令不等于动作起点。
6. 8–16秒温度、94–166秒量杯刻度、472–530/604–630秒平滑度：不足字段继续UNKNOWN。

T3先独立盲看“题面+当前窗口”，再加入历史；记录较近替代画面、台面残留、文字捷径、常识猜测是否足够。
30秒窗口只是审核提案，10/30/60秒敏感性检查待做。历史距离为查询减拟议历史证据最晚结束，仅作描述。
较强候选为525秒回溯鸡蛋处理与第二轮微波状态；烤模材料题有残留捷径，许可链题缺音轨且单句可能泄露答案，历史必要性均未确认。

## 复现与校验

项目依赖见根requirements.txt；提取另需本机FFmpeg/ffprobe和Pillow；UI测试可选Playwright与已安装的Edge。
不需联网或模型服务。提取/打包脚本拒绝覆盖已有交付版本；重新提取应换输出版本路径，保留本次文件。
tools/prepare_gx010021_media.py提取媒体、帧和保护快照；tools/build_gx010021_phase1.py
打包tools/gx010021_visual_notes.json中已检查的笔记，生成代理片段与新实验版本；
tools/render_gx010021_review.py重建HTML/Markdown。完整FFmpeg参数在extraction_commands.json、detail_commands.json、clip_commands.json中。

```powershell
python -m benchmark.validate --data datasets/ego_mc/GX010021_video_phase1_20261027 --assets-snapshot results/preparation/original_assets.json --report results/video_review/GX010021_phase1_20261027/validation.json
python tools/validate_gx010021_review.py
python -m unittest discover -s benchmark/tests -v
python tools/test_gx010021_workbench.py
python -m benchmark.validate --data datasets/ego_mc/GX010021_video_phase1_20261027 --require-gold --report results/video_review/GX010021_phase1_20261027/readiness.json
```

最后一条应退出1，因Gold为空。结构PASS不等于语义已审定。
自动检查覆盖原资产哈希、旧候选字节保留、引用与时间因果切断、视觉/原文分层、候选门禁、帧/片段哈希与时长、实验禁用。
[validation.json](validation.json)、[review_validation.json](review_validation.json)、[tests.txt](tests.txt)、[ui_tests.json](ui_tests.json)、[readiness.json](readiness.json)保存实际结果。
现有26项与新增8项测试全部通过。UI在file://下测试通过，含H.264片段解码与正确的原视频绝对时间跳转。

两处README只追加当前入口说明；旧实验README已备份。原视频、标注、设计稿、原候选证据、Schema均未修改；没有批量分析其他视频。
