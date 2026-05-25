# fish / reflection 标注规则

## 类别定义

- fish：真实鱼体；
- reflection：鱼缸壁上的完整鱼形镜像。

## 标注规则

- 真实鱼体标注为 fish；
- 鱼缸壁上完整、容易被误识别为鱼体的鱼形镜像标注为 reflection；
- 普通光斑、水流纹理和气泡不标注；
- 严重遮挡、轮廓不清或无法判断的鱼不标注；
- 鱼体重叠但仍能区分个体时，分别标注为多个 fish；
- 标注目标是为后续 fish-only tracking 提供干净输入，降低 reflection 对轨迹分析的干扰。
