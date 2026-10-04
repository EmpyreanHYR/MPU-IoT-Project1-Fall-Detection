window.FALLGUARD_NOTES = [
  {
    "id": "opening",
    "label": "Opening",
    "title": "Fall detection on the  edge",
    "seconds": 25,
    "en": "Our project is FallGuard, a camera-based fall-detection prototype. MaskedBiMamba classifies one-second pose sequences, while a Raspberry Pi extracts poses, runs the classifier, and stores records locally. Hailo accelerates pose extraction. Detection continues without Internet access, and the cloud receives retained records after reconnection. We will explain the model, the evidence, and the complete data flow.",
    "zh": "我们的项目是 FallGuard，一个摄像头跌倒检测原型。MaskedBiMamba 根据一秒钟的姿态序列分类；树莓派独立完成姿态提取、分类和记录保存。Hailo 加速姿态网络，断网时本地处理继续，恢复连接后再把记录送到云端。下面介绍模型、实验和完整数据流。"
  },
  {
    "id": "setting",
    "label": "Care setting",
    "title": "Motion provides the context",
    "seconds": 30,
    "en": "A fall can resemble sitting or bending in one frame. Motion provides context, but estimated poses can be interrupted. Our model addresses incomplete observations within a short sequence. The intended care setting also requires an event history that remains available after a network interruption. Our contribution combines temporal modeling and pose quality with local execution and deferred cloud delivery.",
    "zh": "跌倒与坐下、弯腰在单帧中可能相似，需要结合前后动作。姿态提取也会出现中断，因此我们研究如何利用短序列中的有效观察。在辅助生活场景中，网络中断不能让检测停止或丢失事件历史。本项目把时序建模、姿态质量、本地运行和恢复补传结合起来。"
  },
  {
    "id": "system",
    "label": "System design",
    "title": "Inference stays on the Raspberry Pi",
    "seconds": 35,
    "en": "Follow the four local stages: camera or video, pose extraction, temporal classification, and SQLite storage. Hailo runs the pose network; the Pi CPU runs MaskedBiMamba. A local page displays predictions and pending records without a cloud connection. The cloud stores records before acknowledging them. Retries retain the original capture time and do not duplicate the tested records. Compared with the proposal, classification has moved from the cloud to the device.",
    "zh": "沿流程图看四个本地环节：输入画面、姿态提取、时序分类、SQLite 保存。Hailo 运行姿态网络，树莓派 CPU 运行分类器。本地页面无需云连接就能查看结果。云端先保存再确认，重试保留原始时间；已测试的重复提交不会重复入库。相比开题，分类从云端移到了设备。"
  },
  {
    "id": "model",
    "label": "Model design",
    "title": "MaskedBiMamba",
    "seconds": 45,
    "en": "The input contains twelve body joints, with normalized coordinates and confidence. Training masks selected frames. Temporal attention connects positions, and independent forward and backward Mamba branches process the buffered window. A learned quality gate weights frame features using mean joint confidence, visible-joint fraction, and person confidence. Both directions use observations already collected within one second. We reuse the Mamba operator; our work is the combined architecture, evaluation, and system integration.",
    "zh": "输入包含十二个人体关节的归一化坐标和置信度。训练时遮蔽部分帧；时间注意力连接各时刻，独立的正向与反向 Mamba 分支处理已缓存窗口。质量门控根据关节平均置信度、可见关节比例和人体检测置信度给帧特征加权。双向处理只使用已收集的一秒数据，不预读未来动作。我们复用 Mamba 算子，贡献在组合结构、评价和系统集成。"
  },
  {
    "id": "protocol",
    "label": "Evaluation protocol",
    "title": "Separate protocols, explicit metrics",
    "seconds": 35,
    "en": "The primary study combines CAUCAFall and GMDCSA-24: 260 videos and fourteen subject groups. Four subject-disjoint folds and three seeds give twelve evaluations per model. Le2i has a separate baseline study and external evaluation. Forty synthetic clips test edge deployment. Window, video, event, and confirmed-alert metrics answer different questions. Error bars are sample standard deviations. Evaluated video-hour rates must not be interpreted as a full day of continuous monitoring.",
    "zh": "主实验使用 CAUCAFall 和 GMDCSA-24，共二百六十段视频、十四个受试者分组。四折和三个种子使每个模型对应十二次评价。Le2i 用于单独基线和外部评价，四十段合成视频用于边端测试。窗口、视频、事件与确认告警回答不同问题；误差线是样本标准差，分段视频的小时折算率不能当成全天监护频率。"
  },
  {
    "id": "comparison",
    "label": "Baseline comparison",
    "title": "Precision and recall lead to different choices",
    "seconds": 40,
    "en": "The Transformer encoder leads clean window F1 at 0.6581. MaskedBiMamba leads window precision at 0.6048, with video F1 of 0.7632. Its unmatched predicted-event rate is lowest at the common threshold. Confirmation rules are evaluated separately: replay gives confirmed-event recall of 0.7752 and 66.7 unmatched confirmed alerts per evaluated hour. This illustrates the sensitivity-precision trade-off. These short test segments do not establish an acceptable continuous-care notification rate.",
    "zh": "Transformer 的干净窗口 F1 最高，为 0.6581；MaskedBiMamba 的窗口精确率最高，为 0.6048，视频 F1 为 0.7632。在共同阈值下，它的未匹配预测事件率最低。确认规则另行回放，确认事件召回率为 0.7752，每评价小时有 66.7 个未匹配确认告警。结果体现灵敏度与精确率的权衡，不代表持续监护的告警负担已经可接受。"
  },
  {
    "id": "ablation",
    "label": "Ablation study",
    "title": "Which changes contribute?",
    "seconds": 35,
    "en": "We compare ten variants under the same folds and seeds. Removing the backward branch or temporal attention reduces window F1 and increases unmatched predicted events. Other changes have mixed effects. Removing masking improves clean window F1, and removing quality pooling improves clean video F1. The evidence supports the temporal components, while masking and quality processing require calibration for the intended observation conditions. Clean ablations do not isolate the cause of frame-loss tolerance.",
    "zh": "十个变体使用相同划分和种子。去掉反向分支或时间注意力后，窗口 F1 下降，未匹配预测事件增加。其他组件的影响并不一致：去掉遮蔽可提高干净窗口 F1，去掉质量池化可提高干净视频 F1。因此不能概括为所有模块都改善所有指标；干净数据消融也不能确定缺帧优势由哪个模块造成。"
  },
  {
    "id": "robustness",
    "label": "Missing observations",
    "title": "Classification is retained under frame removal",
    "seconds": 35,
    "en": "At thirty percent frame removal, MaskedBiMamba retains window F1 of 0.6276, compared with 0.4361 for TCNTE. A similar trend appears on external Le2i. The current comparison includes frame removal and confidence noise. Earlier joint-removal tests also changed coordinate normalization, so they have been excluded from the model conclusions. They remain clearly marked in the historical archive. These pose perturbations do not evaluate changes in lighting or camera position.",
    "zh": "随机移除百分之三十帧时，MaskedBiMamba 的窗口 F1 为 0.6276，TCNTE 为 0.4361，外部 Le2i 也出现类似趋势。当前主图只保留缺帧与置信度噪声。旧关节缺失测试同时改变了坐标归一化，已退出结论，原始结果在历史资料中明确标记。这里扰动的是姿态，不代表已评价光照或机位变化。"
  },
  {
    "id": "edge",
    "label": "Raspberry Pi results",
    "title": "Complete inference without an external network",
    "seconds": 45,
    "en": "The full Pi pipeline was tested without external network access. Using the same YOLOv8s-pose model, throughput is 20.56 fps with Hailo and 1.73 fps with CPU ONNX, an 11.9-fold difference. Classification still runs on the Pi CPU. Of forty synthetic clips, thirty-nine produce outputs: twenty true positives, eleven true negatives, eight false positives, and one missing output. Only fourteen positive clips are detected within the annotated fall interval, distinguishing clip recall from timely event detection.",
    "zh": "完整树莓派流水线在无外部网络条件下完成测试。同一个 YOLOv8s-pose 使用 Hailo 为 20.56 fps，CPU ONNX 为 1.73 fps，约提升 11.9 倍；分类仍在 Pi CPU 上执行。四十段合成视频中三十九段有输出，包括二十个真阳性、十一个真阴性、八个误报，另有一段无输出。只有十四段正类视频在标注跌倒时段内检出，所以整段视频召回不等于及时检测。"
  },
  {
    "id": "cloud",
    "label": "Recovery and delivery",
    "title": "Records survive interruptions",
    "seconds": 40,
    "en": "A thirty-second upload-path outage retains seventeen records on the Pi. The queue is first observed empty 2.83 seconds after recovery. All eighty-five tested records match their identifiers and capture times. Replaying thirty-four records after a cloud restart creates no duplicates. Separately, one hundred committed writes survive forced writer termination. A ten-minute offline replay processes 11,016 frames without reported throttling. Receipt latency starts at the final captured frame, not at fall onset.",
    "zh": "上传链路中断三十秒时，本地保留十七条记录；恢复后约 2.83 秒首次观察到队列清空。八十五条测试记录的编号和原始时间均匹配，云服务重启后重放三十四条记录没有重复入库。强制终止写入进程后，一百条已提交记录全部恢复。十分钟离线回放处理 11,016 帧，没有报告降频。接收延迟从窗口末帧开始计算，不是从跌倒开始计算。"
  },
  {
    "id": "demo",
    "label": "Live demonstration",
    "title": "Show the device working independently",
    "seconds": 25,
    "en": "For the demonstration, connect the Pi directly to a display. Show valid poses and increasing classification counts, disconnect Wi-Fi and Ethernet, then show local records accumulating. Reconnect and show the same records in the cloud. A labeled public or synthetic video is the backup input. This presentation displays evidence; the local dashboard and real cloud backend provide the operational demonstration.",
    "zh": "树莓派直接连接显示器。先展示有效骨架与增长的分类计数，再断开 Wi-Fi 和网线，观察本地记录与积压数；恢复连接后，展示同一批记录进入真实云后端。备用输入使用明确标注来源的公开或合成视频。汇报网页是证据展示，实际演示使用本地检测页和云端监控页。"
  },
  {
    "id": "conclusion",
    "label": "Conclusions",
    "title": "What the project establishes",
    "seconds": 30,
    "en": "The project combines temporal modeling, independent edge inference, and persistent cloud delivery. MaskedBiMamba offers higher precision at the common threshold and stronger frame-loss tolerance than TCNTE; TE leads clean F1. The main remaining tasks are alert calibration on continuous recordings and longer camera tests. Our repository provides experiment code, manuscripts, and aggregate evidence. The appendix separates current evidence from excluded historical conditions. Thank you.",
    "zh": "本项目完成时序模型、本地推理和持久化云端补传。MaskedBiMamba 在共同阈值下精确率更高，相比 TCNTE 更能容忍缺帧；TE 的干净 F1 更好。下一步是用连续录像校准告警，并评价更长时间的摄像头运行。仓库提供代码、文稿与汇总结果，附录区分当前证据和已排除历史条件。谢谢。"
  },
  {
    "id": "evidence",
    "label": "Evidence appendix",
    "title": "Inspect the reported evidence",
    "seconds": 0,
    "en": "Use this appendix only when answering a relevant question. It is outside the timed twelve-slide talk.",
    "zh": "档案保留 1,853 行汇总结果，不是视频数或独立样本数。默认视图排除受归一化混淆影响的空间缺失条件；历史入口和 CSV 明确标记排除原因。确认告警回放单列，不能与原始预测事件混为一谈。\n\n- Window：一次分类使用的时间窗口。\n- Video：整段视频，可能包含多个窗口。\n- Event：按匹配规则合并与评价的事件。\n- Confirmed alert：经过部署确认规则产生的告警。\n- Mean ± SD：重复评价的均值与样本标准差，不是置信区间。"
  },
  {
    "id": "questions",
    "label": "Questions and answers",
    "title": "Questions the evidence can answer",
    "seconds": 0,
    "en": "Use this appendix only when answering a relevant question. It is outside the timed twelve-slide talk.",
    "zh": "此页用于答辩，不计入十二页正文的七分钟讲述。回答时明确区分已验证结果、历史记录与未测试范围。"
  }
];
