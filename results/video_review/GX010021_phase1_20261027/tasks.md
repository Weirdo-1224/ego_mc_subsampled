# T1–T3 候选任务与历史必要性分析

全部 CANDIDATE / PENDING，enabled=false，earliest_answerable_time=null。候选答案只在此侧车/审核JSON中，gold.jsonl仍为空。

当前窗口30秒只是审核提案；10/30/60秒敏感性检查尚未执行。历史距离为查询减拟议历史证据最晚结束，不是已确认的历史依赖距离。充分/最小集合与历史必要性均PENDING。

## T1_oven

查询：16秒；题面：此时是否已实际达到350°F？

历史：无/UNKNOWN

当前：ego_mc:GX010021:video_evidence:oven_controls, ego_mc:GX010021:video_evidence:T1_oven_current

文字：无

候选答案：UNKNOWN；只看到按键，未可靠读出实测温度。

替代证据：当前显示屏可能提供替代证据，需原分辨率连续复核；设定值仍不等于实测值。

历史必要性：当前窗口即可检查按键与显示，历史未表现必要；温度可回答性本身PENDING。

人工遮蔽复核：先仅看题面与当前窗口，写答案与理由；再增加历史比较；单独检查文字标注、残留物、其他较近画面、对象替换和常识猜测。由独立人工判定充分/必要性，未执行Benchmark。

## T1_eggs

查询：90秒；题面：截至90秒，透明方盒里有几枚可见蛋黄？

历史：ego_mc:GX010021:video_evidence:crack_first, ego_mc:GX010021:video_evidence:crack_second

当前：ego_mc:GX010021:video_evidence:return_intact_egg, ego_mc:GX010021:video_evidence:T1_eggs_current

文字：无

候选答案：候选2；不把第三枚取出当作第三枚已打入。

替代证据：78–90秒盒内两个蛋黄本身可能充分；不能宣称必须依赖首次打蛋历史。

历史必要性：弱历史/当前可见对照候选；历史必要性仍PENDING。

人工遮蔽复核：先仅看题面与当前窗口，写答案与理由；再增加历史比较；单独检查文字标注、残留物、其他较近画面、对象替换和常识猜测。由独立人工判定充分/必要性，未执行Benchmark。

## T1_butter

查询：432秒；题面：第二次从微波炉取出时，容器中是否仍有可见黄色块状物？

历史：ego_mc:GX010021:video_evidence:butter_first_check

当前：ego_mc:GX010021:video_evidence:butter_second_check, ego_mc:GX010021:video_evidence:T1_butter_current

文字：无

候选答案：候选有；完全融化不可确认。

替代证据：426–432秒取出近景可直接回答；431.658秒Success不作事实支持。

历史必要性：当前近景可能足够，历史不是强必要候选。

人工遮蔽复核：先仅看题面与当前窗口，写答案与理由；再增加历史比较；单独检查文字标注、残留物、其他较近画面、对象替换和常识猜测。由独立人工判定充分/必要性，未执行Benchmark。

## T2_eggs

查询：200秒；题面：开始搅拌前，“加入两枚鸡蛋”候选前置是否满足？

历史：ego_mc:GX010021:video_evidence:crack_first, ego_mc:GX010021:video_evidence:crack_second, ego_mc:GX010021:video_evidence:return_intact_egg

当前：ego_mc:GX010021:video_evidence:T2_eggs_current

文字：ego_mc:GX010021:evidence:008, ego_mc:GX010021:evidence:017

候选答案：事实子项候选已加入两枚；规范充分性与完整任务答案UNKNOWN。

替代证据：170–200秒混合前盒内蛋黄仍可见，可能直接计数；原始指令文本也可给数量捷径，但不能证明动作完成。

历史必要性：当前窗可能足够计数；不作为已确认长程任务。

人工遮蔽复核：先仅看题面与当前窗口，写答案与理由；再增加历史比较；单独检查文字标注、残留物、其他较近画面、对象替换和常识猜测。由独立人工判定充分/必要性，未执行Benchmark。

## T2_tray

查询：630.612秒；题面：倒面糊之前，烤模准备这一候选前置是否已实际满足？

历史：ego_mc:GX010021:video_evidence:oil_pour_tilt

当前：ego_mc:GX010021:video_evidence:T2_tray_current

文字：ego_mc:GX010021:evidence:038, ego_mc:GX010021:evidence:040, ego_mc:GX010021:evidence:042, ego_mc:GX010021:evidence:051

候选答案：事实子项候选已倒入淡黄色液体并倾斜；是否符合必要覆盖/许可标准UNKNOWN。

替代证据：600.612–630.612秒烤模在旁可见，残留光泽可能给出捷径；逐帧评估是否充分，不能只看曾倒油。

历史必要性：历史提供操作来源；规范必要性与当前替代充分性均PENDING。

人工遮蔽复核：先仅看题面与当前窗口，写答案与理由；再增加历史比较；单独检查文字标注、残留物、其他较近画面、对象替换和常识猜测。由独立人工判定充分/必要性，未执行Benchmark。

## T3_eggs_history

查询：525秒；题面：回顾当前混合物制作过程，最初实际打入了几枚鸡蛋？是否有完整蛋未加入，如何处理？

历史：ego_mc:GX010021:video_evidence:crack_first, ego_mc:GX010021:video_evidence:crack_second, ego_mc:GX010021:video_evidence:return_intact_egg

当前：ego_mc:GX010021:video_evidence:T3_eggs_history_current

文字：无

候选答案：候选打入2枚，第三枚完整蛋放回蛋盒；对象连续性待审。

替代证据：495–525秒为搅拌近景，无法直接数原始鸡蛋；检查台面蛋壳、其他早期视角、题面先验及默认配方猜测。

历史必要性：较强跨窗口历史候选：原始数量/放回事件在当前画面不可直接重建；须做独立遮蔽审核，未运行模型或统计消融。

人工遮蔽复核：先仅看题面与当前窗口，写答案与理由；再增加历史比较；单独检查文字标注、残留物、其他较近画面、对象替换和常识猜测。由独立人工判定充分/必要性，未执行Benchmark。

## T3_butter_history

查询：525秒；题面：第二次取出微波炉容器时，其中是否仍有黄色块状物？

历史：ego_mc:GX010021:video_evidence:butter_first_check, ego_mc:GX010021:video_evidence:butter_second_check

当前：ego_mc:GX010021:video_evidence:T3_butter_history_current

文字：无

候选答案：候选有；物理融化程度/温度UNKNOWN。

替代证据：当前495–525秒面糊外观无法确定426–432秒状态；首次取出可提示但不能替代第二次近景，Success文本可能诱发相反捷径。

历史必要性：跨窗口回溯候选，必须确认“第二次”对象与时间定位；历史必要性PENDING。

人工遮蔽复核：先仅看题面与当前窗口，写答案与理由；再增加历史比较；单独检查文字标注、残留物、其他较近画面、对象替换和常识猜测。由独立人工判定充分/必要性，未执行Benchmark。

## T3_tray_history

查询：630.612秒；题面：在当前倒入前，操作者先前用什么可见方式处理了这个烤模？

历史：ego_mc:GX010021:video_evidence:oil_pour_tilt

当前：ego_mc:GX010021:video_evidence:T3_tray_history_current

文字：无

候选答案：候选从透明瓶倒淡黄色液体并反复倾斜；材料为食用油是待审身份推断。

替代证据：当前窗仍见烤模、瓶子与内表面光泽，可猜材料；该捷径未排除，不宣称历史必要。

历史必要性：约50秒以上的操作回忆候选，但当前残留状态可能足够，优先做人工遮蔽对照。

人工遮蔽复核：先仅看题面与当前窗口，写答案与理由；再增加历史比较；单独检查文字标注、残留物、其他较近画面、对象替换和常识猜测。由独立人工判定充分/必要性，未执行Benchmark。

## T3_rule_chain

查询：556.368秒；题面：截至查询时刻，原始标注声称允许什么材料处理烤模，能否确认视频中实际许可链？

历史：无/UNKNOWN

当前：ego_mc:GX010021:video_evidence:T3_rule_chain_current

文字：ego_mc:GX010021:evidence:038, ego_mc:GX010021:evidence:039, ego_mc:GX010021:evidence:040, ego_mc:GX010021:evidence:041, ego_mc:GX010021:evidence:042

候选答案：原始文字候选为油；视频实际许可链UNKNOWN（无音轨）。

替代证据：单条556.368秒“Yes, you can use oil.”已可能回答文本题；完整历史未必必要；画面拿瓶不证明得到许可。

历史必要性：保留为不可核验/语言捷径对照，不能升为视频规则推理Gold。

人工遮蔽复核：先仅看题面与当前窗口，写答案与理由；再增加历史比较；单独检查文字标注、残留物、其他较近画面、对象替换和常识猜测。由独立人工判定充分/必要性，未执行Benchmark。
