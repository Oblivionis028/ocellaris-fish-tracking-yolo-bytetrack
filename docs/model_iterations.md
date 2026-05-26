# 模型迭代记录

主要模型阶段：

- Baseline：初始 fish / reflection 检测模型；
- V3：加入 TOP_test_2min 人工标注帧；
- V4：加入 TOP_test_5min 的 300 张人工修正样本；
- V5：新增 train200 + val100；
- V6：新增 train300 + val100；
- TOP_v7_scene_adapt：面向双视角 MVP 的顶视角场景适配模型；
- LEFT_v1_scene_adapt：面向双视角 MVP 的侧视角场景适配模型。

模型迭代目标从单纯提升 mAP，逐步转向为三维重建提供稳定的鱼体中心点输入。
