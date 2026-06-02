# 点位导出与 QC 记录

模型输出被转换为点位 CSV 和 QC CSV。

QC 状态包括：

- ok；
- auto_keep_top3；
- need_manual_or_interpolation。

9:00-10:00 片段中：

- TOP 需要人工或插值处理的帧数为 38；
- LEFT 在选定 conf 下需要人工或插值处理的帧数为 225。

合并 TOP/LEFT QC 后，选择了可用率最高的 30 秒窗口作为 3D MVP 片段。
