# ID switch 错误类型记录

当前观察到的主要身份错误类型包括：

- self ID jump：同一条鱼自身 ID 跳变；
- two-fish ID swap：两条鱼交叉后 ID 互换；
- three-fish cyclic permutation：三条鱼发生循环标签错配；
- false box：虚框进入轨迹；
- missing box：某条鱼短时间漏检；
- occlusion-uncertain：遮挡严重，身份无法可靠判定。

对于外观高度相似的三条眼斑双锯鱼，ByteTrack 原始 ID 不能直接视为最终生物学个体身份。
