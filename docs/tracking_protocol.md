# 跟踪流程记录

跟踪阶段只使用 fish 类，不使用 reflection 类。

设计原因：

- reflection 是鱼缸壁上的镜像，不是真实个体；
- 若 reflection 进入 ByteTrack，会增加虚假轨迹和身份混淆；
- fish-only tracking 能减少反射对后续轨迹分析的干扰。

ByteTrack 可用于初步轨迹提取，但 crossing、occlusion 和 close interaction 片段仍需要人工复核或后处理。
