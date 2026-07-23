---
title: "VORA：基于 Voronoi 镶嵌与发震时刻估计的快速地震震相关联方法"
tags:
  - 文献精读
  - 地震学
  - 地震目录构建
  - 相位关联
  - 深度学习
  - Voronoi
  - 无监督聚类
  - arXiv
  - JGR-SolidEarth
  - Song2026
  - Berkeley
  - 2019Ridgecrest
aliases:
  - VORA
  - Voronoi tessellation- and Origin-time-based Rapid Associator
authors:
  - Song, Junhao
  - Zhu, Weiqiang
  - Wang, Haoyu
  - Kumar, Utpal
  - Taira, Taka'aki
  - Allen, Richard M.
journal: JGR-Solid Earth
date: 2026-07-17
---


# VORA：基于 Voronoi 镶嵌与发震时刻估计的快速地震震相关联方法

#文献精读 #地震学 #地震目录构建 #相位关联 #Voronoi #深度学习 #无监督聚类 #arXiv #Song2026

## 1. 基本信息

- **题目**：VORA: Rapid Association of Earthquake Phases from Local to Global
- **作者**：Junhao Song, Weiqiang Zhu, Haoyu Wang, Utpal Kumar, Taka'aki Taira, Richard M. Allen
- **单位**：Department of Earth & Planetary Science, University of California, Berkeley；Berkeley Seismology Laboratory
- **期刊**：*Journal of Geophysical Research: Solid Earth*（JGR-Solid Earth，投稿中；arXiv 预印本）
- **DOI**：arXiv:2607.10450（DOI: 10.48550/arXiv.2607.10450）
- **发表日期**：2026-07-11（arXiv 预印本）
- **文章类型**：方法论文（method paper），开源代码将经审稿后公开
- **通讯作者**：Junhao Song, sjh2019@berkeley.edu
- **许可**：CC BY-NC-SA 4.0

## 2. 一句话总结

VORA 是一种**无需训练、面向任意台网几何的地震相位关联方法**，把每个台站由 P/S 到时反推出的"假想发震时刻"在 Voronoi 邻域内做时空聚类，从而在局部密集台阵到全球 4461 个台站的尺度上实现秒级、快速且高召回的自动目录构建。

## 3. 研究背景

地震监测工作流一般分两步：先用拾取算法（picking）从连续波形中识别 P/S 震相到达，再通过**相位关联**（phase association）将离散到时归并到同一震源。PhaseNet、EQT、GPD 等深度学习拾取模型已经能在区域台网下大幅降低完备震级，输出成百上千万的相位标签；分布式声学传感（DAS）让数据量再上几个数量级。

既有相位关联方法各有局限：

- **网格搜索类**（如 REAL、PyOcto）：要把每条相位反投影到候选源体上反复搜索；PyOcto 虽高度优化但仍依赖具体速度模型与网格。
- **监督深度学习类**（PhaseLink、GENIE）：需要大量标注数据训练，跨区域迁移性差。
- **无监督聚类**（GaMMA）：把关联视为 GMM + EM 聚类，同时反演震源位置、时刻和震级，但参数对区域与台网几何敏感，重新部署需要重新调参。

**核心 gap**：当台站规模从几十扩展到上千、从局部到全球时，传统方法在计算成本、跨区域泛化、对网络演化的鲁棒性上都吃紧。VORA 正是为了填补这个"训练免费、几何自适应、可在局部到全球尺度运行"的空缺而设计。

## 4. 数据与方法

### 4.1 数据
- **合成数据**：用于压力测试，模拟台网在不同事件密度、噪声水平、空间跨度下的关联效果。
- **2019 Ridgecrest 序列（局部尺度）**：6 天 PhaseNet 拾取数据（zhu2022gamma 提供），用于测试震群场景。
- **2019 Ridgecrest 序列（全球尺度）**：来自 *Ni et al. 2025* 的全球 PhaseNet 拾取数据集，2 周覆盖全球 4461 个台站。

### 4.2 方法亮点

**(1) 用 P-S 时刻对反推发震时刻（无需模型）**

由 V<sub>P</sub>/V<sub>S</sub> = T<sub>S</sub>/T<sub>P</sub> 的几何关系，任意一对同源 P、S 到时可立即给出一个"假想发震时刻"：

$$\frac{t_S}{t_P} = \frac{V_P}{V_S} \quad \Rightarrow \quad t_S = \frac{V_P}{V_S}\, t_P \tag{1}$$

$$
\Delta t \equiv T_S - T_P = t_S - t_P \tag{2}
$$

$$
t_P = \frac{T_S - T_P}{\frac{V_P}{V_S} - 1} \tag{3}
$$

$$
T_0 = T_P - t_P = T_P - \frac{T_S - T_P}{\frac{V_P}{V_S} - 1} \tag{4}
$$
T<sub>0</sub> 为发震时刻
T<sub>0</sub> 只依赖 **V<sub>P</sub>/V<sub>S</sub> 比值**，该比值在不同区域与深度远比绝对速度结构稳定，所以同一个 1.5–1.8 的合理区间就能在不同台网下通用。

**(2) Voronoi 镶嵌定义台站邻域**

用所有在线台站的位置构造球面 Voronoi 图，该图表示在多边形范围内的震源距离该多边形中心的台站最近，该中心台站会第一个收到震源信号，相邻 Voronoi cell 共享边/顶点的台站被定义为邻居。
**与 KNN 不同**，Voronoi 邻域反映"震源候选点与台站最近"的几何关系，对网络几何自适应；更高阶邻居通过"删去低阶邻居"逐级扩展，避免误差累积。

**(3) 无监督时空聚类**

- 对每个台站，把候选 P-S 对反推出的假想 T<sub>0</sub> 在容差窗口内与**邻居台站**的 T<sub>0</sub> 做时间聚类；通过邻居而非全局匹配，自然滤掉"远区误关联"。
- 可选步骤：对同一时空聚类中混杂的多个事件用 EM 算法再细分。

**(4) 关键设计**

- **零训练**：完全不依赖 GPU 训练。
- **少量物理可解释超参**：最小台站数、邻居阶数、V<sub>P</sub>/V<sub>S</sub> 区间。
- **几何自适应**：Voronoi 图每日更新，能应对台站增减。
- **不依赖绝对速度模型**，故对局部–全球、不同构造环境都通用。

### 流程
```
[台站位置]  ──预处理──▶  球面 Voronoi + 邻接表 + 走时窗
                                   │
[P/S 拾取流] ──在线处理──▶  每台站 P-S 配对 → 候选 T0
                                   │
                          Voronoi 邻居子图 + 走时窗
                                   │
                          时间聚类 + 关联打分
                                   │
                          候选事件列表 → 后处理 → 真实事件
```

## 5. 核心结果

### 5.1 聚类思路：假想发震时刻 + Voronoi 邻域 = 关联

![图1 假想发震时刻聚类](/images/obsidian/2026-07-17_arXiv_Song_VORA_精读/fig1_origin_time_clustering.png)

*图 1：在 Voronoi 邻域内对每个台站由 P-S 时刻对反推的"假想发震时刻"做时空聚类。同一事件的台站会给出相近的 T<sub>0</sub>，且其台站在空间上相邻，从而被归为一簇。*

### 5.2 Voronoi 邻域从局部密集台阵到全球 4461 台站自适应

![图2 Voronoi 镶嵌可扩展性](/images/obsidian/2026-07-17_arXiv_Song_VORA_精读/fig2_voronoi_scalability.png)

*图 2：相同 Voronoi 程序在加州密集台阵（左）、阿拉斯加稀疏台阵（中）和全球 4461 个台站（右）上都能直接生成有意义的多阶邻域，无需重训练或重新调参。*

### 5.3 合成压力测试：高速、强震群下仍稳健

![图3 合成测试](/images/obsidian/2026-07-17_arXiv_Song_VORA_精读/fig3_synthetic_test.png)

*图 3：合成实验中，VORA 在不同事件密度、噪声水平、关联误差窗口下的召回与精度显著优于 GaMMA 与 PyOcto，且在密集震群下不掉点。运行时间也是三者中最短。*

### 5.4 Ridgecrest 真实数据：与 GaMMA、PyOcto 在震群下的对比

![图4 Ridgecrest 对比](/images/obsidian/2026-07-17_arXiv_Song_VORA_精读/fig5_ridgecrest_comparison.png)

*图 4：2019 Ridgecrest 序列 6 天数据下，VORA 召回事件数显著多于 GaMMA 与 PyOcto，特别在主震后高密度余震阶段保持稳定，且定位更接近 USGS 参考目录。*

### 5.5 全球尺度：同一框架、同一套超参

![图5 全球应用](/images/obsidian/2026-07-17_arXiv_Song_VORA_精读/fig7_global_application.png)

*图 5：将同一 VORA 流程直接跑在两周的全球 PhaseNet 拾取（4461 个台站）上，检测到约 37800 次事件；插图显示 US West Coast、阿拉斯加、夏威夷、智利、新西兰等高密度台网区域都被同时识别。*

### 5.6 主震窗口的相位到时分布

![图6 主震 1 小时窗口](/images/obsidian/2026-07-17_arXiv_Song_VORA_精读/fig9_mainshock_picks.png)

*图 6：Ridgecrest 主震前后 1 小时的全部 PhaseNet 拾取（上）以及 VORA 聚类结果与 USGS 参考目录的对比（下）。VORA 几乎捕获全部参考目录事件，但主震本身因 S 波拾取缺失而漏检——这是 VORA 对 S 波质量依赖的局限。*

### 5.7 每日召回率随震群活动起伏

![图7 召回率变化](/images/obsidian/2026-07-17_arXiv_Song_VORA_精读/fig8_recall_rate.png)

*图 7：US West Coast 与 Ridgecrest 区域的每日召回率。在序列高峰期 Ridgecrest 内部召回率从 1.0 降到 0.6，约 3 天后恢复到 0.8；外围 US West Coast 区域始终在 0.85 以上。改用 Zhu et al. 2022 的 PhaseNet 拾取可将该数字再提高约 0.2。*

## 6. 作者结论 vs 我的判断

### 作者声称
- VORA 是**无训练、几何自适应、局部到全球**均可用的相位关联器，速度快、召回高。
- 唯一瓶颈是输入拾取质量（尤其 S 波），主震和强震群期间召回会因 S 拾取缺失而显著下降。
- 可作为统一不同区域、不同尺度台网的"一套流程"。

### 我的判断
**逻辑链**：
1. 把关联任务从"反投影到空间网格"或"训练序列分类器"重新定义为"在邻域内对假想发震时刻做无监督时空聚类"，思路简洁、几何意义清晰。
2. Voronoi 邻域是核心创新点：相比 KNN/距离图，它真正反映"震源候选点与台站最近"的几何关系，且能无重训跨尺度。
3. V<sub>P</sub>/V<sub>S</sub> 比值在 1.5–1.8 区间下表现稳健——这个比值范围在区域尺度确实是稳定的物理量，比依赖速度模型更可移植。

**优势**：
- 计算量小、几乎所有环节都是 NumPy/SciPy 友好的密集数组运算，普通 CPU 即可处理全球级数据。
- 零训练 + Voronoi 自动更新，是真正意义上的"plug-and-play"。
- 对全球级数据仍能保留高召回。

**过度解读或遗留问题**：
1. **依赖 S 波拾取质量**：作者自陈"主震漏检就是因 S 拾取缺失"——在 S 波密集的常规地震目录中表现优秀，但在 S 波不明显的区域（远震、火山深震）会显著退化。
2. **20 秒 P-S 上限 = 1.5° 探测范围**：论文承认无法处理区域/远震，这是 P-S 时窗假设决定的固有限制。文章标题虽写"local to global"，但严格说目前是 local-to-regional。
3. **时空聚类对短暂强震群仍可能分裂事件**：Discussion 中指出相邻 Voronoi 单元中多个紧邻事件是该方法最难的案例。
4. **EM 细分子聚类依赖超参**：当事件彼此混叠时仍需要手工调节子聚类数量；这一环节比起 PyOcto 的纯几何切分并未显式占优。
5. **回忆率 = 1.0 假设了 USGS 目录是完整真相**：实际 USGS 目录在 2019 Ridgecrest 期间就不完整；用机器学习拾取构建的新目录可能有更多"小震"在 USGS 中缺失，从而影响召回率比较。

总体评价：方法创新足够，写作扎实，工程可用性强；**长板在"零训练 + 几何自适应 + 全球级处理能力"**，**短板在"对 S 波质量的高度依赖"**。

## 7. 对我的启发

### 可借鉴的技术 / 方法
- **Voronoi 邻域 + 物理比值的 V<sub>P</sub>/V<sub>S</sub> 估计 T<sub>0</sub>**：这套思路可以无成本迁移到我的任何关联/定位流水线中，作为轻量级预筛选器。
- **无监督时空聚类作为关联 backbone**：比传统网格搜索更平滑，比监督学习更鲁棒。GaMMA 的 GMM+EM 思路也可以借鉴做更精细的二次分裂。
- **多尺度同一框架思想**：用"局部→全球同一套超参"作为可移植性指标，值得在我的多区域/多台网研究里复用。

### 可延伸的研究方向
- **加入 DAS**：DAS 通道的"假想台站"几何特性特殊，可以测试 Voronoi 在密集线性阵列下的退化与改进。
- **联合 P 波方位角/慢度估计**：用 T<sub>0</sub>+back-azimuth 同时约束，做更精确的初定位，再交给 hypoDD 等精定位算法。
- **近实时（< 1 s）扩展**：把分析窗压短到 1–3 s，结合 S 波拾取的多任务模型，尝试将 VORA 用于 EEW 后端。
- **基于 Voronoi 的不确定性估计**：同一事件在不同 Voronoi 邻域下应给出相似结果，离散度可作为关联置信度指标。

### 值得读的参考文献（按相关度排序）

1. **Ross, Z. E., Yue, Y., Meier, M., Hauksson, E., & Heaton, T. H. (2019).** PhaseLink: A deep learning approach to seismic phase association. *JGR Solid Earth*, 124. DOI: [10.1029/2018JB016674](https://doi.org/10.1029/2018JB016674) — 把深度学习引入关联的代表性工作。
2. **Münchmeyer, J., et al. (2023).** PyOcto: A high-throughput seismic phase associator. *Seismica*. DOI: [10.26443/seismica.v3i1.1058](https://doi.org/10.26443/seismica.v3i1.1058) — 空间切分派代表，与 VORA 形成方法学对照。
3. **Zhu, W., McBrearty, I. W., Mousavi, S. M., Beroza, G. C. (2022).** GaMMA: A deep-learning earthquake phase associator. *Geophysical Research Letters*. DOI: [10.1029/2022GL098394](https://doi.org/10.1029/2022GL098394) — 同思路的 GMM 版本，对照阅读价值高。
4. **McBrearty, I. W., et al. (2023).** GENIE: A Graph Neural Network for Seismic Event Location. *JGR Solid Earth*. DOI: [10.1029/2022JB024548](https://doi.org/10.1029/2022JB024548) — 图神经网络派代表，可对比"图 vs. Voronoi"。
5. **Satriano, C., Kiraly, E., Bernard, P., & Vilotte, J. P. (2012).** PISApA: A Real-Time and Selective ShakeMap Engine. *Seismological Research Letters*. DOI: [10.1785/gssrl.83.3.660](https://doi.org/10.1785/gssrl.83.3.660) — Voronoi 在地震预警/地震学中的早期应用，本文 Voronoi 用法的思想先导。

---

*笔记作者：Mavis | 精读日期：2026-07-17 | 文献来源：arXiv:2607.10450v1（已通过 arXiv e-print 获取源文件，已下载 PDF 与全部 9 张原图）*

