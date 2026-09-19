# 跌倒检测数据集清单、格式与使用计划

> 文档状态：上传前说明稿（资料核对日期：2026-09-14）  
> 覆盖数据：GMDCSA-24、CAUCAFall v5、Le2i Fall Dataset（Kaggle 镜像）、OmniFall（Hugging Face 完整仓库）。  
> 重要说明：当前尚未读取即将上传到服务器的压缩包。本文件中的“已知内容”来自数据集论文、官方发布页和仓库说明；压缩包的实际目录、文件数、编码及校验值必须在上传后再次核验，不能把网页描述当作本地文件核验结果。
> 上传后的服务器实测结果、实际训练用途与最终来源链接见 [DATASET_PROVENANCE_AND_USAGE.md](DATASET_PROVENANCE_AND_USAGE.md)。本文件保留为上传前计划，不应再作为已完成实验的事实依据。

## 1. 已下载内容总览

| 数据集 | 下载来源/版本 | 主要内容 | 标注粒度 | 在本项目中的角色 |
|---|---|---|---|---|
| GMDCSA-24 | GitHub/Zenodo，建议确认是否为 v2.1 | 4 名受试者、160 个短视频，3 个家庭环境 | 视频级类别 + CSV 中的秒级动作区间 | 小规模真实数据；主体独立训练/验证；易混淆 ADL 测试 |
| CAUCAFall | Mendeley Data v5，DOI `10.17632/7w7fccy7ky.5` | 10 名受试者、100 个主动作视频，同时提供 AVI、PNG 帧及 TXT 标注 | 帧级 fall/no-fall 与人体区域标注；OmniFall 另给统一时间段标签 | 主要真实训练数据；主体独立评估；遮挡、光照和视角鲁棒性分析 |
| Le2i | Kaggle `tuyenldvn/falldataset-imvia`，镜像 v2 | 低分辨率、单摄像头、多场景监控视频；镜像约 17.44 GB | 原始数据含跌倒区间/位置类标注，具体文件需上传后核验 | 跨场景和外部测试集；主要检验真实监控场景泛化能力 |
| OmniFall | Hugging Face `simplexsigil2/omnifall` 完整仓库，约 9.76 GB | 统一标签、预定义划分、Parquet 配置，以及 12,000 个 OF-Syn 合成视频 | 统一的密集时间段标签；OF-Syn 还含人口属性和逐帧标签 | 统一标签与划分工具；OF-Syn 用于辅助预训练/增强及消融实验 |

这四项不是四份互不重叠的原始视频。OmniFall 对 GMDCSA-24、CAUCAFall、Le2i 等公开数据集进行了重新标注并提供统一划分，但 **Hugging Face 仓库不包含这些 staged 数据集的原始视频**。其中直接随仓库提供的主要视频内容是 OF-Syn 合成视频；因此前三个真实数据集仍需单独上传。

## 2. GMDCSA-24

### 2.1 数据内容

- 4 名受试者，合计 160 个 MP4 视频，来自 3 个自然家庭环境。
- 按发布论文列出的目录数量求和：81 个 ADL 视频、79 个跌倒视频。
- 论文摘要中出现过“81 falls、79 ADL”的相反写法，但逐受试者目录统计为：
  - Subject 1：16 ADL + 16 Fall；
  - Subject 2：23 ADL + 25 Fall；
  - Subject 3：22 ADL + 21 Fall；
  - Subject 4：20 ADL + 17 Fall。
- 包含前向、后向和侧向跌倒，也有睡觉、俯卧撑、弯腰捡物等容易被误判为跌倒的日常活动。
- 单摄像头、30 fps、H.264；视频分辨率包括 1280×720 和 640×480，总体积约 1.95 GB。

### 2.2 预期目录和格式

```text
GMDCSA24/
├── Subject 1/
│   ├── ADL/
│   │   └── *.mp4
│   ├── Fall/
│   │   └── *.mp4
│   ├── ADL.csv
│   └── Fall.csv
├── Subject 2/
├── Subject 3/
└── Subject 4/
```

CSV 主要字段包括：文件名、视频时长、录制时间、衣着、文字描述和 `Classes`。`Classes` 中用秒表示动作起止区间，例如：

```text
Falling (BW)[6.9 to 12]; Walking[0 to 3.6]
```

同一动作多次出现时会给出多段时间。CSV 解析时不能简单按逗号/分号盲目切割，必须先检查实际引号和分隔规则。

### 2.3 计划用途

1. 依据 `Subject 1–4` 做主体分组，禁止同一受试者的视频同时进入训练集和测试集。
2. 使用 MP4 提取人体姿态序列，并依据 CSV/OmniFall 标签生成固定长度时序窗口。
3. 将睡觉、俯卧撑、弯腰等作为 hard negatives，重点统计误报率。
4. 因只有 4 名受试者，单独结果波动会较大，报告逐折结果及均值±标准差，不把它作为唯一的论文证据。

### 2.4 版本和许可

- 建议优先确认数据是否对应 v2.1；该版本说明 CSV 已加入类别起止时间。
- 数据论文列出的 v2.1 Zenodo DOI 为 `10.5281/zenodo.13354453`。
- 数据论文采用 CC BY 4.0；GitHub 代码仓库许可证与数据许可证应分别记录。

## 3. CAUCAFall v5

### 3.1 数据内容

- Mendeley Data 页面标明：Version 5，发布于 2025-03-18，许可证 CC BY 4.0。
- 10 名受试者，每名受试者完成 10 类动作，共 100 个主动作视频。
- 5 类跌倒：向前、向后、向左、向右、从坐姿跌倒。
- 5 类 ADL：行走、跳跃、捡物、坐下、跪下。
- 在非受控家庭环境拍摄，包含自然光、人工光、弱光/无光、遮挡、背景运动、不同地面纹理、摄像机距离和跌倒角度。
- HIKVISION IR/RGB 摄像机，约 23 fps，1080×960。

### 3.2 预期目录和格式

官方说明为 10 个受试者主目录，每个目录含 10 个动作文件夹；每个动作文件夹中通常有：

```text
CAUCAFall/
├── Subject*/
│   ├── Activity*/
│   │   ├── *.avi       # 完整动作视频
│   │   ├── *.png       # 拆出的逐帧图像
│   │   └── *.txt       # 对应帧的人工标注
│   └── ...
├── classes.txt
└── Dataset_details.xlsx
```

- `.avi`：时序模型和姿态提取的首选输入。
- `.png`：已拆分的视频帧，适合训练/检查人体检测器，但不应与 AVI 再次重复计入样本数。
- `.txt`：帧级标签，`classes.txt` 中通常为 `0 = nofall`、`1 = fall`，并附人体区域信息。其列顺序和坐标是否归一化必须以实际文件抽样核验后再写解析器。
- `Dataset_details.xlsx`：记录受试者、动作、帧数，以及拍摄距离、角度、遮挡、光照等属性，可用于分层鲁棒性分析。

### 3.3 计划用途

1. 作为主要真实训练/验证数据之一，按受试者 ID 做 Group split 或 LOSO/交叉验证。
2. 时序分类从 AVI 提取姿态；PNG/TXT 只在需要微调人体检测器或分析漏检时使用。
3. 使用 `Dataset_details.xlsx` 分别报告正常光/弱光、无遮挡/遮挡、近/远距离等条件下的结果。
4. 原始 TXT 与 OmniFall 的时间段标签承担不同任务：前者偏向帧级检测，后者用于统一时序动作分类，不能混为同一种标签。

## 4. Le2i Fall Dataset（Kaggle 镜像）

### 4.1 数据内容

- 已下载来源：Kaggle `tuyenldvn/falldataset-imvia`。
- Kaggle API 显示该镜像为 version 2，更新于 2023-04-21，总大小 17,438,364,988 bytes（约 17.44 GB），但许可证字段为 `Unknown`。
- Le2i 官方/论文常见版本为 191 个单摄像头视频，25 fps，320×240，时长约 30 秒至 4 分钟，场景包括 Home、Coffee room、Office、Lecture room。
- OmniFall 实际统一了其中 190 个视频并产生 967 个时间段标签。

### 4.2 必须注意的版本差异

部分二手资料把 Kaggle 镜像描述为 222 个视频，而官方发布、论文和 OmniFall 分别常见 191 或 190 个视频。这个差异可能来自重复文件、额外 ADL、重打包或版本变化。因此：

- 上传后必须实际统计视频数量、扩展名、相对路径、时长和哈希；
- 不能仅凭文件名猜测，将 Kaggle 镜像全部套用 OmniFall 的 `labels/le2i.csv`；
- 只有与 OmniFall 路径和视频时长成功匹配的子集才使用其统一标签；
- 未匹配的视频需单独追溯原始标注，不能自动视为 no-fall；
- Kaggle 镜像未声明许可证，论文发表和数据共享应引用并遵循原始 Le2i/dataUBFC 发布条款，不应直接重新分发整个镜像。

### 4.3 预期格式

Le2i 常按场景组织视频和标注，可能见到类似目录名：

```text
Le2i/
├── Home_*/
├── Coffee_room_*/
├── Office_*/
└── Lecture_room_*/
```

具体视频容器、标注文件名和层级以 Kaggle 压缩包为准。OmniFall 标签中的示例路径类似 `Coffee_room_01/video_14`，统一标签字段为视频相对路径、类别、起止秒数等。

### 4.4 计划用途

1. 优先作为外部测试和跨场景测试数据，而不是与所有视频随机混洗后训练。
2. 若可靠受试者 ID 不完整，按场景/原始视频进行分组，保证同一视频切出的帧或窗口绝不跨集合。
3. 用于考察 320×240 低分辨率、遮挡和复杂背景下的泛化性能。
4. 若论文主任务是“动态跌倒过程检测”，使用跌倒起止区间生成正窗口；前后 ADL 生成负窗口，并保留事件级评价。

## 5. OmniFall 完整仓库

### 5.1 本次 `hf download` 实际得到什么

完整仓库约 9.76 GB，主要包含：

```text
omnifall_data/
├── data_files/
│   ├── omnifall-synthetic_av1.tar       # 12,000 个 AV1 编码的 OF-Syn MP4
│   ├── syn_frame_wise_labels.tar.zst    # OF-Syn 逐帧标签
│   └── oops_video_mapping.csv           # OOPS 文件名映射，不是 OOPS 原视频
├── labels/
│   ├── GMDCSA24.csv
│   ├── caucafall.csv
│   ├── le2i.csv
│   ├── cmdfall.csv / edf.csv / mcfd.csv / occu.csv / up_fall.csv
│   ├── OOPS.csv
│   ├── of-syn.csv
│   └── label2id.csv
├── parquet/                              # 70 余种可直接加载的配置
├── splits/
│   ├── cs/                               # cross-subject
│   ├── cv/                               # cross-view
│   └── syn/                              # 合成数据及人口属性划分
├── videos/metadata.csv                   # 12,000 个合成视频的元数据
├── omnifall_builder.py
├── generate_parquet.py
├── prepare_oops_videos.py
└── README.md / LABELS.md / STRUCTURE.md / CONFIGS.md / KNOWN_PITFALLS.md
```

关键边界：

- `omnifall-synthetic_av1.tar` 中才是随仓库提供的大规模视频，约 12,000 个合成 MP4。
- GMDCSA-24、CAUCAFall、Le2i 等 staged 数据集在仓库中主要是 CSV 标签、划分和 Parquet 元数据，不含其原视频。
- OOPS/OF-ItW 的原视频也不随仓库分发；`oops_video_mapping.csv` 只是文件名映射。
- AV1 视频需要服务器上的 FFmpeg/PyAV 支持 AV1 解码，上传后先做解码兼容性检查。

### 5.2 统一标签格式

staged 数据集的核心字段为：

```text
path,label,start,end,subject,cam,dataset
```

- `path`：不带统一根目录的视频相对路径；必须先映射到实际上传文件。
- `label`：统一动作类别编号。
- `start`、`end`：以秒为单位的时间段。
- `subject`：受试者编号；不能忽略，否则容易产生主体泄漏。
- `cam`：摄像机视角编号。
- `dataset`：数据集来源。

OmniFall 的 16 类标签为：

| ID | 类别 | 简要含义 |
|---:|---|---|
| 0 | walk | 行走/跑动 |
| 1 | fall | 正在发生的跌倒过程 |
| 2 | fallen | 跌倒后处于地面/床垫上的状态 |
| 3 | sit_down | 坐下过程 |
| 4 | sitting | 坐姿状态 |
| 5 | lie_down | 主动躺下过程 |
| 6 | lying | 主动躺下后的静态状态 |
| 7 | stand_up | 起身过程 |
| 8 | standing | 站立状态 |
| 9 | other | 其他活动 |
| 10–15 | kneel_down、kneeling、squat_down、squatting、crawl、jump | 扩展动作，主要出现在 OF-ItW/OF-Syn |

本项目的首要正类定义建议为 `label = 1 (fall)`，即真正的跌倒运动过程。`fallen` 是跌倒后的状态，`lying` 是主动躺下后的状态，二者不能在数据预处理阶段无说明地合并。可另做“fall + fallen”报警定义作为补充实验，但必须单独报告。

### 5.3 规模与本项目相关的标签数

根据 OmniFall 当前统计：

| 组成 | 视频数 | 单视角时间段数 | 时长 |
|---|---:|---:|---:|
| OF-Staged（8 个公开数据集） | 2,164 | 9,590 | 13.81 h |
| OF-ItW（OOPS） | 818 | 4,022 | 2.65 h |
| OF-Syn | 12,000 | 19,228 | 16.88 h |
| GMDCSA-24 子集 | 160 | 458 | 0.36 h |
| CAUCAFall 子集 | 100 | 258 | 0.28 h |
| Le2i 子集 | 190 | 967 | 0.79 h |

### 5.4 计划用途

1. 用 `labels/` 和 `splits/` 统一 GMDCSA-24、CAUCAFall、Le2i 的动作定义及训练/验证/测试划分。
2. 用 OF-Syn 做辅助预训练或训练增强，比较：
   - 真实数据训练；
   - OF-Syn 预训练后在真实数据微调；
   - 真实数据 + OF-Syn 混合训练。
3. 最终性能必须在未参与训练的真实数据上评价。合成数据上的高分不能代替真实场景证据。
4. OF-Syn 的 `subject=-1`，不能做 LOSO；应使用仓库预定义的随机或 cross-age、cross-BMI、cross-ethnicity 等划分。
5. 使用当前配置名，如 `of-sta-cs`、`of-sta-cv`、`of-syn`。裸名称 `le2i` 等可能只是旧别名，论文中应记录完整配置名和仓库 commit/hash。

## 6. 上传到服务器后的建议目录

为避免重复占用空间，保留原始文件只读，转换结果与原始包分开：

```text
$FALLGUARD_WORK_DIR/data/
├── raw/
│   ├── gmdcsa24/
│   ├── caucafall_v5/
│   ├── le2i_kaggle_v2/
│   └── omnifall/
├── manifests/
│   ├── inventory.csv
│   ├── path_mapping.csv
│   └── unified_segments.csv
├── poses/
└── cache/
```

不建议复制同一视频去迎合 OmniFall 的目录格式。更合适的做法是建立 `path_mapping.csv` 或软链接，把 OmniFall 的 `path` 映射到真实文件。

如果训练服务器区分系统盘和临时数据盘，应先确认当前实例的持久化规则和剩余容量。大文件上传后不要仅凭目录名称判断“不会丢失”，应以服务商控制台的磁盘类型为准。

## 7. 上传后必须完成的核验

上传完成后先做数据审计，不立即启动长时间训练：

1. 保存每个压缩包的文件名、字节数和 SHA-256。
2. 解压后统计视频、CSV、TXT、PNG、XLSX、Parquet 的数量。
3. 使用 `ffprobe` 读取每个视频的容器、编码、帧率、分辨率、时长和是否可解码。
4. 检查损坏视频、0 字节文件、重复哈希和大小异常文件。
5. 抽样解析每种标注文件，确认单位是秒还是帧、区间是否闭合、TXT 坐标列的定义。
6. 对 GMDCSA-24、CAUCAFall、Le2i 逐一匹配 OmniFall `path`；输出 matched、missing、extra 三张清单。
7. 所有切窗、数据增强和姿态提取必须在 train/validation/test 划分之后执行或严格继承原视频分组，防止同源窗口泄漏。
8. 固化数据清单、随机种子、划分文件和代码 commit，便于论文复现。

## 8. 拟采用的实验分工

### 8.1 主实验

- 训练：CAUCAFall + GMDCSA-24 的训练折；根据实验设计决定是否加入 Le2i 训练折。
- 主体独立测试：GMDCSA-24 和 CAUCAFall 按受试者分组。
- 跨数据集/跨场景测试：保留 Le2i 作为外部测试，或轮换数据集执行 leave-one-dataset-out。
- 合成数据实验：OF-Syn 只用于预训练/增强，最终比较落在相同真实测试集上。

### 8.2 建议至少报告的对照

| 实验 | 真实训练数据 | OF-Syn | 目的 |
|---|---|---|---|
| Real-only baseline | ✓ |  | 真实数据基线 |
| Synthetic only |  | ✓ | 测量合成到真实的域差距 |
| Synthetic pretrain → real finetune | ✓ | ✓ | 验证合成预训练是否有效 |
| Real + synthetic joint training | ✓ | ✓ | 验证混合训练是否有效 |
| Cross-dataset test | 训练集数据 | 可选 | 测量跨数据集泛化 |

模型结构、100 epoch、关闭早停、相同输入窗口、优化器和学习率等训练条件应在所有基线与改进模型间保持一致。是否使用 OF-Syn 必须作为明确的实验变量，不能在部分方法中悄悄加入。

### 8.3 评价指标

- 窗口级：Precision、Recall/Sensitivity、Specificity、F1、AUROC、混淆矩阵。
- 事件级：跌倒事件召回率、误报次数/小时、检测延迟。
- 统计方式：固定相同划分，建议至少 3 个随机种子；报告均值±标准差。
- 资源指标：参数量、FLOPs、推理延迟和显存占用，支撑物联网/边缘部署结论。

## 9. 论文使用时的引用与许可

1. 使用 OmniFall 的标签、划分或 OF-Syn 视频时，引用 OmniFall 论文和数据仓库；使用 staged 子集时还要分别引用原始数据集论文。
2. OmniFall 仓库标记为 CC BY-NC 4.0；CAUCAFall v5 为 CC BY 4.0；GMDCSA-24 按其数据发布条款署名。
3. Le2i Kaggle 镜像自身许可证显示 Unknown，发表前应按原始 Le2i/dataUBFC 条款确认使用许可，不以 Kaggle 页面替代原始授权。
4. 不在代码仓库重新上传受许可证限制的原视频；公开数据清单、转换脚本和路径映射模板即可。

## 10. 主要资料来源

- GMDCSA-24 数据论文：<https://doi.org/10.1016/j.dib.2024.110892>
- GMDCSA-24 v2.1：<https://doi.org/10.5281/zenodo.13354453>
- GMDCSA-24 GitHub：<https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos>
- CAUCAFall v5：<https://data.mendeley.com/datasets/7w7fccy7ky/5>
- CAUCAFall 数据论文：<https://doi.org/10.1016/j.dib.2022.108610>
- Le2i Kaggle 镜像：<https://www.kaggle.com/datasets/tuyenldvn/falldataset-imvia>
- Le2i/dataUBFC 记录：<https://doi.org/10.25666/DATAUBFC-2024-04-09>
- OmniFall Hugging Face：<https://huggingface.co/datasets/simplexsigil2/omnifall>
- OmniFall 论文：<https://arxiv.org/abs/2505.19889>
