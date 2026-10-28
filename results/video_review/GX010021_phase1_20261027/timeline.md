# GX010021 视觉事件与状态候选时间线

全部 CANDIDATE / PENDING；非 Gold。无音轨。时间为已检查证据包络，精确动作起止 UNKNOWN。

Agent inspected 18 contact sheets covering 349 decoded frames (actual PTS at about 2.002-second spacing), then 2-fps detail sheets for eggs, oil, butter, powder and oven. No external video model, ASR, or human adjudication. Intervals below are inspected evidence spans, NOT exact action onset/offset. Absence between sampled frames is not established.

约2秒取样覆盖全片，重点5段加密到2fps；非连续逐帧穷尽。区间为已检查证据包络，精确起止UNKNOWN。取样间短动作、遮挡、画面外行为与所有实际语音均未核验。

| 证据区间（秒） | 实际画面候选 | 状态候选 | 人工确认重点 |
|---|---|---|---|
| [8–16](clips/oven_controls.mp4) | 手指触按炉灶/烤箱控制面板；显示屏亮着。 | oven.reached_350F = UNKNOWN | 可见按键操作不等于达到温度；设定值与实测值不可可靠读出。 |
| [22–36](clips/container_change.mp4) | 先拿起白色圆碗，放下后取出透明方形容器并放在操作区。 | mix_box.on_counter = True | 大小是否不合适属于规范判断；画面只支持容器切换候选。 |
| [44–60](clips/take_eggs.mp4) | 打开蛋盒、拿取鸡蛋并回到混合区；台面上可见多枚完整蛋。 | eggs.number_taken_from_carton = UNKNOWN | 取出、放台面、打入是不同事件；准确拿取数需逐帧复核。 |
| [60–66](clips/crack_first.mp4) | 在透明方盒上方打开蛋壳；随后盒内可见一个黄色蛋黄。 | mix_box.visible_yolks = 1 | 时段是证据包络，精确蛋液入盒边界待定。 |
| [68–76](clips/crack_second.mp4) | 再次在同一方盒上方打开蛋壳；随后盒内可见两个蛋黄。 | mix_box.visible_yolks = 2 | 仅为画面计数候选，不从两枚蛋黄推广到任何配方结论。 |
| [78–90](clips/return_intact_egg.mp4) | 盒内仍可见两个蛋黄；手中第三枚蛋保持完整外观，约87–88秒将其放入蛋盒。 | mix_box.visible_yolks = 2 | 应连续复核是否有遗漏动作；79秒Feedback不能直接解释为第三枚已打入。 |
| [94–128](clips/sugar_fill.mp4) | 取糖类包装和黑色量杯，将棕色颗粒倒入量杯并持于混合盒旁。 | sugar.measured_cups = UNKNOWN | 量杯容量刻度不可可靠识读；1/4杯与半杯均不能凭标注回填。 |
| [128–134](clips/sugar_add.mp4) | 将装棕色颗粒的黑色量杯翻转到混合盒上方，盒内随后出现棕色物料。 | mix_box.brown_granules_added = True | 材料身份推为糖、具体杯量仍待包装/刻度复核。 |
| [146–166](clips/milk_add.mp4) | 将纸盒中的白色液体倒入黑色量杯，再倒入透明混合盒。 | mix_box.white_liquid_added = True | 候选材料为牛奶；准确体积UNKNOWN。 |
| [174–200](clips/mixer_setup.mp4) | 取手持电动搅拌器并安装/调整两根搅拌头，再将其移向混合盒。 | mixer.in_use_before_200 = UNKNOWN | 工具可见；许可内容、启动声与确切启动时刻不可由无音轨验证。 |
| [200–234](clips/mix_wet.mp4) | 手持电动搅拌器在透明方盒内移动，原本分开的蛋黄等逐渐混合为浅黄色物。 | mix_box.contents_appearance = 浅黄色混合物 | 精确均匀程度、转速与完成阈值PENDING。 |
| [260–294](clips/flour_add.mp4) | 从柜内取纸袋，用黑色量杯盛白色粉末，约290秒倒入混合盒，表面形成白粉层。 | mix_box.white_powder_added = True | 面粉为包装/上下文身份候选；一杯容量不能独立确认。 |
| [302–340](clips/butter_prepare.mp4) | 拆开包裹黄色固体的包装，将黄色块状物放入透明玻璃长方容器，并移向微波炉。 | butter_dish.contains_yellow_solids = True | 黄油身份为视觉/包装候选；半杯量、容器是否微波安全不能自动确认。 |
| [340–390](clips/microwave_first.mp4) | 将玻璃容器放入微波炉，关门并多次按控制面板，随后等待。 | microwave.programmed_seconds = UNKNOWN | 可见装入/按键；实际功率、加热启止和是否严格15秒均UNKNOWN。 |
| [390–402](clips/butter_first_check.mp4) | 开门取出玻璃容器；黄色液体中仍可见多块形状清晰的黄色固体。 | butter_dish.visible_solid_chunks = True | 不按397.648秒Feedback倒推错误起点。 |
| [402–426](clips/microwave_second.mp4) | 再次把玻璃容器放入微波炉、关门、按键并等待，随后开门。 | microwave.second_program_seconds = UNKNOWN | 第二轮实际加热持续时间UNKNOWN。 |
| [426–432](clips/butter_second_check.mp4) | 第二次取出容器；液体里仍可见黄色块状物。 | butter_dish.visible_solid_chunks = True | 431.658秒Success不能证明完全融化；块状外观的物理解释仍待人工审定。 |
| [442–470](clips/butter_stir_add.mp4) | 用黑色工具在黄色液体容器内搅动，随后将内容物倾倒进原混合盒并刮取。 | mix_box.yellow_liquid_added = True | 材料身份与对象连续性需跨片段复核；未据此宣称全部融化或全部倒净。 |
| [472–530](clips/mix_batter.mp4) | 再次用电动搅拌器混合；后段表面呈较均匀浅黄色，停止后提起搅拌器。 | mix_box.smooth_to_recipe_standard = UNKNOWN | 肉眼较均匀不等于配方所需平滑度；479.580/489.740反馈与525成功不作真值。 |
| [532–556](clips/tray_inspection.mp4) | 混合盒放回台面；操作者处理包装、观察烤模附近，随后手伸向瓶装区。 | loaf_pan.approved_lining_material = UNKNOWN | 纸→剩余黄油→油的许可链只存在于无音轨对应文字；不能由画面推断规则。 |
| [556–581](clips/oil_pour_tilt.mp4) | 拿起绿色瓶盖的透明瓶，将淡黄色液体倒进深灰烤模；随后多次倾斜烤模让液体沿内表面流动。 | loaf_pan.liquid_poured_and_tilted = True | 食用油为外观/瓶身候选；全部内壁均匀覆盖与防粘效果UNKNOWN。 |
| [582–598](clips/batter_inspection.mp4) | 拿起透明混合盒查看表面，随后放下并拿起纸袋。 | mix_box.needs_more_flour = UNKNOWN | 是否需要加粉是规范/配方判断；不能由提问、条件许可或个人意愿确认。 |
| [598–604](clips/extra_powder.mp4) | 从纸袋取少量白色粉末放入混合盒；602–603秒表面可见新白粉堆。 | mix_box.additional_white_powder_added = True | 具体量UNKNOWN；不能直接判为违规。 |
| [604–630](clips/remix.mp4) | 用电动搅拌器再次混合；结束时提起搅拌器并拿起装浅黄色混合物的方盒。 | mix_box.smooth_to_recipe_standard = UNKNOWN | 629.668秒Success和个人评论不构成平滑度真值。 |
| [632–642](clips/pour_batter.mp4) | 将透明方盒倾斜到深灰烤模上方，浅黄色混合物进入烤模。 | loaf_pan.contains_batter = True | 实际倒入约始于634秒附近，须逐帧定界；630.612秒指令不是倒入时刻。 |
| [644–684](clips/scrape_batter.mp4) | 持续用黑色刮具把方盒内残余混合物刮入烤模，随后放下方盒。 | loaf_pan.contains_batter = True | 是否完全刮净不作承诺。 |
| [686–694](clips/oven_insert.mp4) | 端起盛混合物的烤模，打开烤箱门、将烤模放在架上，随后关门。 | loaf_pan.placed_in_oven = True | 不等于烤箱已预热到350°F，也没有成品烘焙结果。 |

## 人工关键片段队列

优先：60–90秒鸡蛋数量与放回；390–432秒两次取出时固体状态；556–581秒烤模处理与覆盖；598–604秒追加白粉；632–642秒实际倒入起点；686–694秒入烤箱。

8–16秒烤箱温度、94–166秒量杯刻度与材料身份、472–530/604–630秒平滑度标准、所有55条真实语音均保持 UNKNOWN/PENDING。其余逐段事项已列在表格与 review_data.json.human_queue。

每项需真实审核者记录观看范围、确认或拒绝的具体命题、精确边界和理由；关键分歧独立复核。当前没有人工批准记录。
