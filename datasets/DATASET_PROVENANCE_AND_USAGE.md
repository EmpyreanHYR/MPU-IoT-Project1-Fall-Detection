# 跌倒检测项目数据来源与实际使用说明

> 文档用途：记录数据的来源、版本、许可、服务器实测清单、路径映射、派生数据和训练使用边界。  
> 核验日期：2026-09-17（Asia/Shanghai）。  
> 核验对象：隔离的 RTX 3090 训练环境（公开文档中以 `$FALLGUARD_WORK_DIR` 代指工作目录），以及本项目训练配置与结果目录。

## 1. 本文档与结项报告的分工

结项报告面向课程评审，正文只保留理解实验结论所必需的信息：用了哪些真实视频、如何标注与切窗、如何避免数据泄漏、哪些数据没有进入实验，以及这些选择如何影响结果。结项报告不承担文件级资产台账的职责。

本说明文档面向复现、交接和数据治理，保留下载入口、版本、服务器目录、文件和视频数量、映射关系、标签定义、派生缓存、许可限制及未使用数据。以后更换镜像、增加数据集或重新生成清单时，应先更新本文件，再把与实验结论有关的变化同步到结项报告。

## 2. 服务器实测结论

训练实例在本次核验时已切换为 RTX 3090 有卡模式。GMDCSA-24 全量姿态提取、统一缓存审计和正式切窗已完成，主实验矩阵正在运行。公开文档中统一使用 `$FALLGUARD_WORK_DIR` 表示项目数据工作目录。

| 数据或派生物 | 服务器路径 | 实测规模 | 是否进入已报告实验 | 实际作用 |
|---|---|---:|---|---|
| CAUCAFall v5 | `data/raw/caucafall_v5` | 7.9 GB；40,209 个文件；100 个视频 | 是，新主实验 | 与 GMDCSA-24 组成受试者隔离四折；OmniFall 标签映射为 258 条片段 |
| Le2i Kaggle 镜像 v2 | `data/raw/le2i` | 17 GB；321 个文件；190 个视频 | 是，复现和外部测试 | 不参与 CAUCAFall--GMDCSA-24 拟合；OmniFall 标签映射为 967 条片段 |
| OmniFall 完整下载 | `data/raw/omnifall` | 9.3 GB；24,589 个文件；其中 12,000 个 OF-Syn 视频 | 只使用标签；OF-Syn 未用于训练 | 使用 Le2i、CAUCAFall 和 GMDCSA-24 的统一动作区间标签；合成视频未出现在任何训练清单中 |
| 统一片段与划分清单 | `data/manifests` | 226 MB（含派生窗口张量缓存） | 是 | 保存路径映射、1,683 条真实片段、冻结的 fold、窗口清单和可复用预处理结果 |
| 姿态缓存 | `data/poses/real_combined` | 126 MB；450 个 `.npz` | 是 | 每个真实视频一份缓存，450 行索引均通过形状与有限数审计 |
| GMDCSA-24 | `data/raw/gmdcsa24_v2_1` | 1.1 GB；170 个文件；160 个 MP4、8 个 CSV | 已进入正式 GPU 实验；结果待完成 | 458 条 OmniFall 片段全部映射；160 份姿态缓存已新建；与 CAUCAFall 组成 7,869 窗口主实验 |

服务器上的一对一路径映射已经完成：`caucafall_path_mapping.csv` 有 100 行，`le2i_path_mapping.csv` 有 190 行，`gmdcsa24_path_mapping.csv` 有 160 行；对应片段清单分别为 258、967 和 458 行。正式姿态目录现有 450 个 `.npz`；索引状态为既有 290、新建 160，无缺失、重复或损坏缓存。

## 3. 数据来源与可访问链接

### 3.1 Le2i Fall Detection Dataset

- 原始数据目录记录：[dataUBFC Fall Detection Dataset](https://search-data.ubfc.fr/imvia/FR-13002091000019-2024-04-09_Fall-Detection-Dataset.html)
- 数据目录 DOI：[10.25666/DATAUBFC-2024-04-09](https://doi.org/10.25666/DATAUBFC-2024-04-09)
- 本项目实际下载镜像：[Kaggle Le2i Fall Dataset](https://www.kaggle.com/datasets/tuyenldvn/falldataset-imvia)
- 原始方法论文：[10.1109/SITIS.2012.155](https://doi.org/10.1109/SITIS.2012.155)
- 本项目版本证据：Kaggle 页面标记为 version 2，镜像总大小约 17.44 GB；服务器解包后为 321 个文件、190 个可用视频。
- 许可边界：Kaggle 镜像的许可证字段为 `Unknown`。论文或代码仓库不得把该镜像当作已获开放再分发授权；应引用原始 dataUBFC 记录和论文，并仅公开清单、路径映射模板及处理脚本。

### 3.2 CAUCAFall v5

- 官方数据页：[Mendeley Data CAUCAFall Version 5](https://data.mendeley.com/datasets/7w7fccy7ky/5)
- 数据 DOI：[10.17632/7w7fccy7ky.5](https://doi.org/10.17632/7w7fccy7ky.5)
- 数据论文：[10.1016/j.dib.2022.108610](https://doi.org/10.1016/j.dib.2022.108610)
- 官方页面信息：Version 5，发布于 2025-03-18，CC BY 4.0；10 名受试者，每人完成 5 类跌倒和 5 类日常活动，目录中同时提供 AVI、逐帧 PNG 和 TXT 标注。
- 本项目版本证据：服务器目录占用 7.9 GB，含 100 个动作视频；100 个视频全部与统一时间段标签成功匹配。

### 3.3 OmniFall

- 数据仓库：[Hugging Face simplexsigil2/omnifall](https://huggingface.co/datasets/simplexsigil2/omnifall)
- 论文：[arXiv 2505.19889](https://arxiv.org/abs/2505.19889)
- 项目页：[OmniFall Project](https://dsch.ai/omnifall/)
- 实验代码：[simplexsigil/omnifall-experiments](https://github.com/simplexsigil/omnifall-experiments)
- 许可：Hugging Face 数据页标记为 CC BY-NC 4.0。OmniFall 不能替代各 staged 子数据集的原始引用或授权。
- 本项目下载修订：本地 Hugging Face tree 缓存记录为 `83572a37b9e3081df8c06a56874b1d1f2a19386c`。若重新下载，应记录新的修订号并重新核对标签行数与路径。

OmniFall 在本项目中只承担标签规范化作用：读取 `labels/le2i.csv`、`labels/caucafall.csv` 和 `labels/GMDCSA24.csv`，再通过显式的 `path,video_path` 映射连接到本地真实视频。服务器上虽然存在 12,000 个 OF-Syn 合成视频，但主实验、复现实验和外部测试清单均未混入 OF-Syn。因此不能把 OF-Syn 写成已参与训练的数据。

### 3.4 GMDCSA-24

- 数据论文：[10.1016/j.dib.2024.110892](https://doi.org/10.1016/j.dib.2024.110892)
- Zenodo v2.1：[10.5281/zenodo.13354453](https://doi.org/10.5281/zenodo.13354453)
- GitHub：[GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos](https://github.com/ekramalam/GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos)

本项目收到的压缩包为 `GMDCSA24-A-Dataset-for-Human-Fall-Detection-in-Videos-master.zip`，大小 1,107,541,589 字节，SHA-256 为 `b8ac1dcbe35402e1daa8c4505efacf4f016aba6703673767cf5f3a6a281443cb`。ZIP CRC 与路径穿越检查通过；解压后有 4 名受试者、81 个 ADL 视频、79 个 Fall 视频，共 160 个 MP4 和 8 个 CSV。

服务器对 160 个视频进行了首末帧读取和完整逐帧解码：视频均为 1280×720、`mp4v`，共读取 34,172 帧，零字节、重复哈希、损坏或帧数不一致的视频均为 0；路径匹配为 160/160，额外或缺失视频为 0；458 条 OmniFall 片段全部映射成功，时间区间越界为 0。生成文件包括：

- `gmdcsa24_raw_audit.json`：压缩包哈希、视频/标签数量、区间检查；
- `gmdcsa24_full_decode_audit.json`：全量解码结果；
- `gmdcsa24_path_mapping.csv` 与 `gmdcsa24_segments.csv`：160 条路径映射和 458 条标准化片段；
- `gmdcsa24_folds/fold_0.csv` 至 `fold_3.csv`：4 折受试者隔离划分；
- `caucafall_gmdcsa24_segments.csv`：正式真实训练清单，260 个视频、716 条片段、14 个跨数据集唯一受试者组；
- `real_all_segments.csv`：450 个真实视频、1,683 条片段，用于有卡模式下安全更新统一姿态缓存索引，Le2i 仍保留为外部评估数据。

无卡模式下的单视频 CPU smoke test 仅用于验证数据链路，不进入结果表。有卡模式已完成 160/160 个 GMDCSA-24 视频的全量姿态提取，并生成四份各 7,869 行的冻结窗口清单（6,498 负类、1,371 正类）。目前正式 100-epoch GPU 训练已启动；只有提交完整 `metrics.json` 的运行才能进入性能表。

## 4. 数据进入模型前的处理链

### 4.1 原视频与统一标签

原视频来自 Le2i、CAUCAFall 和新接入的 GMDCSA-24。OmniFall 的统一标签包含 `path`、`label`、`start`、`end`、`subject`、`cam` 和 `dataset`。项目脚本先把 OmniFall 相对路径与服务器上的视频绝对路径做 many-to-one 合并；存在未映射路径时脚本会直接报错，而不会把缺失视频默认为负样本。

最终统一片段表为：

| 数据集 | 视频数 | 片段数 | 片段标签分布 |
|---|---:|---:|---|
| Le2i | 190 | 967 | fall 130；fallen 123；lie_down 1；other 128；sit_down 52；sitting 124；stand_up 108；standing 37；walk 264 |
| CAUCAFall | 100 | 258 | fall 50；fallen 48；lie_down 1；lying 1；other 33；sit_down 10；sitting 20；stand_up 16；standing 32；walk 47 |
| GMDCSA-24 | 160 | 458 | fall 78；fallen 77；lie_down 13；lying 14；other 72；sit_down 22；sitting 63；stand_up 17；standing 37；walk 65 |
| 当前服务器真实数据合计 | 450 | 1,683 | fall 258；fallen 248；lie_down 15；lying 15；other 233；sit_down 84；sitting 207；stand_up 141；standing 106；walk 376。只有动态 `fall` 区间被定义为正类 |

### 4.2 姿态提取与缓存

每个视频只进行一次 YOLOv8s-pose + BoT-SORT 推理，选择主要人物轨迹并写入一个压缩 NPZ。缓存包含：

```text
timestamps      [frames]
keypoints       [frames, 17, 3]   # x, y, confidence
bbox            [frames, 5]       # cx, cy, w, h, detector confidence
track_id        [frames]
video_id, dataset, subject, source_path, pose_model
```

原始 RGB 只在姿态提取阶段被读取；时序模型训练读取的是姿态缓存，不复制 RGB 帧到训练样本。450 个源视频对应 450 个缓存文件，多个模型和随机种子复用同一份缓存。

### 4.3 关节、特征和窗口

- 只保留 12 个非面部身体关节。
- TCNTE 复现使用每关节 `(x,y)`，每帧 24 维。
- 主实验使用 `(x,y,confidence)`，每帧 36 维，并额外保留平均关键点置信度、有效关节比例和人体框置信度作为质量特征。
- 坐标按帧在保留关节上做 min-max 归一化。
- 每个窗口 1.0 秒，步长 0.2 秒，线性重采样到 30 个时间步。
- 与 `fall` 区间重叠至少 50% 的窗口为正类；重叠大于 0 但不足 50% 的模糊窗口被丢弃。
- 启用 `exclude_after_fall`：窗口起点位于最后一个跌倒区间之后时不进入样本。

## 5. 两套实验协议如何使用数据

| 协议 | 视频数据 | 分组方式 | 窗口规模 | 模型与随机种子 |
|---|---|---|---:|---|
| TCNTE 复现 | 仅 Le2i 的 190 个视频 | 3 个按视频分组的 fold；非测试视频中 15% 用于验证 | 每个 fold 使用同一组 12,650 个窗口：1,338 正、11,312 负 | TCN、TE、TCNTE；seed 42 |
| 早期比较（保留审计） | Le2i 190 + CAUCAFall 100 | 4 个 group-disjoint fold；Le2i 按 scene 代理分组 | 每 fold 15,836 个窗口：1,955 正、13,881 负 | 已完成的旧表，不当作 GMDCSA-24 结果 |
| 新主实验（GPU 运行中） | CAUCAFall 100 + GMDCSA-24 160；Le2i 仅外部测试 | 14 个带数据集前缀的 subject，4 个 subject-disjoint fold；每个 split 均含两种数据 | 每 fold 7,869 个窗口：1,371 正、6,498 负 | TCN、TE、TCNTE、UniMamba、MaskedBiMamba；seeds 42、3407、2026；100 epochs |

fold 在切窗之前冻结；同一视频、同一受试者或同一场景的片段不会跨 train/validation/test。每个 fold 的窗口总数相同，变化的是分组后的 split 归属。模型权重按验证集 F1 选择，测试集只用于最终评价。

## 6. 哪些数据没有被使用

- OF-Syn 的 12,000 个合成视频：已下载，但没有进入任何已报告的清单或训练。
- GMDCSA-24 的 smoke 指标：不使用。全量数据已进入正式 GPU 实验，但在 60 个主运行完成前仍不报告性能数值。
- CAUCAFall 的 PNG/TXT：保存在原始发布内容中，但当前时序分类实验没有用它们微调人体检测器；实验使用 AVI 视频和 OmniFall 时间段标签。
- Le2i、CAUCAFall 或 GMDCSA-24 的 RGB 外观：只用于离线姿态提取，不作为 TCN、Transformer 或 Mamba 分类器的输入。

## 7. 复现与变更要求

1. 保留 `/data/raw` 只读；清单、姿态和模型输出写到独立目录。
2. 重新下载数据时记录来源 URL、版本、下载日期、字节数和校验值。
3. OmniFall 修订变化后，重新生成并审计路径映射；不得复用旧清单假定标签未变。
4. 任何新增数据必须先进入 segment manifest，再生成 group-disjoint fold，最后切窗；禁止把同一视频切出的窗口随机分到不同集合。
5. 如果以后启用 OF-Syn，应单独命名实验，并报告 real-only、synthetic-only、synthetic pretrain 后 real finetune 或 real+synthetic 的对照；不得把新结果与当前 real-only 结果混写。
6. 公开仓库只提交代码、配置、清单模式和不受限的统计结果，不重新分发 Le2i 镜像或其他受限制原视频。

## 8. 与结项报告保持一致的最小事实集

结项报告中关于数据的陈述应始终与以下事实一致：

- 当前真实数据池为 450 个视频：Le2i 190、CAUCAFall 100、GMDCSA-24 160。
- OmniFall 只提供统一时间段标签；OF-Syn 没有参与训练。
- 统一片段共 1,683 条：Le2i 967、CAUCAFall 258、GMDCSA-24 458。
- 姿态缓存共 450 份；模型输入是 12 关节时序，不是原始 RGB。
- 正类只定义为动态 `fall`；`fallen` 不并入正类。
- TCNTE 复现为 Le2i-only；新主实验为 CAUCAFall+GMDCSA-24 受试者隔离四折、三随机种子，Le2i 只做外部测试。
- 训练、验证和测试按视频/受试者/场景分组，先分组后切窗。
- GMDCSA-24 已完成全量姿态提取并正在训练；在完整性审计通过前，不得把部分运行、smoke 或估算值写进结果表。
