# Reference verification record

Checked: 2026-09-10 (Asia/Shanghai)

The proposal requirements were checked against the two local COMP6131 guideline PDFs. Bibliographic metadata below was checked against an official dataset/project page, the publisher PDF/page, or Crossref. Repository availability was checked separately from paper existence.

## Sources cited in the proposal

| BibTeX key | Verified source | Identifier / locator | Claim used |
|---|---|---|---|
| `martinez2019upfall` | [MDPI article](https://www.mdpi.com/1424-8220/19/9/1988) | DOI `10.3390/s19091988` | UP-Fall is a multimodal fall/ADL dataset with 17 participants. |
| `alam2024gmdcsa` | Local Elsevier publisher PDF `1-s2.0-S2352340924008552-main.pdf` | DOI `10.1016/j.dib.2024.110892` | GMDCSA-24 provides multiple home settings, varied lighting, falls, ADLs, and challenging daily-activity examples. |
| `kwolek2014urfd` | [University of Rzeszow dataset page](https://fenix.ur.edu.pl/~mkepski/ds/uf.html) and Crossref | DOI `10.1016/j.cmpb.2014.09.005` | UR Fall has 70 sequences, including RGB streams, and an academic-use licence. |
| `jocher2026yolo26` | [Official Ultralytics YOLO26 documentation](https://docs.ultralytics.com/models/yolo26/) | arXiv `2606.03748`; DOI `10.48550/arXiv.2606.03748` | YOLO26 model family, authorship, and YOLO26n scale. |
| `hailo_yolo26_pose` | [Official Hailo YOLO26 pose example](https://github.com/hailo-ai/hailo-apps/tree/main/hailo_apps/python/standalone_apps/yolo26/pose_estimation) | Hailo Apps repository | YOLO26n-pose on Hailo-10H with HEF plus lightweight ONNX post-processing and live-camera input. |
| `yu2025tcnte` | Local Elsevier publisher PDF `1-s2.0-S1574119225000057-main.pdf` and [authors' repository](https://github.com/SomeOtherScenery/fall_detection) | DOI `10.1016/j.pmcj.2025.102016` | Skeleton temporal baseline; the repository contains dataset, network, loss, training, and demonstration code. |
| `zhang2025fallmamba` | Local IEEE publisher PDF `Fall-Mamba_A_Multimodal_Fusion_and_Masked_Mamba-Based_Approach_for_Fall_Detection.pdf` and Crossref | DOI `10.1109/JIOT.2024.3510712` | Masked temporal learning motivates controlled joint/frame masking in robustness training. |
| `mobsite2024aiot` | Crossref metadata and IEEE bibliographic record | DOI `10.1109/JIOT.2024.3398782` | Privacy-aware AIoT partitioning and multilevel feature fusion provide related system-design precedent. |

## Additional verified resources considered

| Resource | Availability finding | Decision |
|---|---|---|
| [MUVIM dataset and sample code](https://github.com/MUVIM/FallDetection) | RGB, depth, infrared, and thermal data; access requires an author request and privacy waiver. Paper DOI: `10.48550/arXiv.2206.12740`. | Kept in `references.bib` as a future extension; omitted from the four-week core plan because access is not immediate. |
| [Hailo Model Zoo](https://github.com/hailo-ai/hailo_model_zoo) | Official Hailo compilation/evaluation environment with Hailo-10H and YOLO26 entries. | Useful if the team later compiles a custom HEF; official pose application is the Week 1 starting point. |
| [Raspberry Pi AI HAT documentation](https://www.raspberrypi.com/documentation/accessories/ai-hat-plus.html) | Official AI HAT+ 2 / Hailo-10H hardware documentation. | Kept in `references.bib` and project records; the proposal measures actual speed instead of relying on a nominal throughput claim. |
| [Fall-Mamba repository](https://github.com/DHUspeech/fall-mamba) | Repository exists, but its README states that the complete code is still being prepared for upload. | Paper is cited for the masking idea; repository is not used as the implementation baseline. |

## Proposal compliance checks

- Topic, care scenario, Advanced/Highest target, team roles, system architecture, cloud service, datasets/open-source resources, four-week plan, and expected evaluation are all present.
- The cloud path is functional by design: MQTT broker, inference worker, FastAPI, PostgreSQL, dashboard, alert acknowledgement, and operating evidence.
- The proposal PDF is A4 and two pages.
- Dataset, model, hardware/runtime code, and research-method sources are separated and traceable.
