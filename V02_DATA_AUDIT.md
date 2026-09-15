# AH36 MAG 136 V0.2 数据资格审计

## 范围

- Material: AH36
- Process: MAG 136
- JointType: Single-V Butt Joint
- Position: PA
- Thickness: 10-20 mm
- GrooveAngle: 40-60 deg（总夹角）
- RootGap: 5-8 mm
- 后续模型输入: Thickness, GrooveAngle, RootGap, PassRole

数值范围来自当前项目已记录的 PA 单V工况覆盖，并集中保存在 `PROJECT_SCOPE`。非 PA、范围外和字段不完整记录均保留，用于 Retrieval、Future Expansion 或 Reference。

## 审计结果

| 指标 | 数量 |
| --- | ---: |
| Total Cases | 18 |
| Total Passes | 32 |
| InProjectScope Passes | 8 |
| EvidenceLevel A | 3 |
| EvidenceLevel B | 5 |
| EvidenceLevel C | 2 |
| EvidenceLevel D | 4 |
| EvidenceLevel E | 18 |
| Eligible Current | 3 |
| Eligible Voltage | 8 |
| Eligible TravelSpeed | 5 |
| Promotion Candidates | 4 |

以上按唯一 PassID 统计。明确共用 Root/Fill/Cap 的 3 条 UNESA 记录展开后，角色上下文共 38 条；对应 Current 9、Voltage 14、TravelSpeed 5 条可训练上下文。展开不增加独立实验数量。

## Promotion Queue

- `AH36-10-PA-CN-001` 的 `P10CN-R1/R2/R3`: 缺 Process 确认和 GrooveAngle 总夹角定义。三个目标均有单值，Priority 为 Medium。
- `AH36-10-S1-001` 的 `P10-S1`: 缺 Position 和 PassRole。三个目标均有单值，Priority 为 Medium。

建议只核验并补充缺失 metadata，不改写已有电流、电压或焊速。

## 资格规则

- `InProjectScope` 只在全部固定身份与三个数值范围同时满足时为 True。
- `EvidenceLevel_Suggested` 根据现有 metadata 生成；`EvidenceLevel_Manual` 保持空白，`EvidenceReviewStatus` 为 Pending。
- `Eligible_Current`、`Eligible_Voltage`、`Eligible_TravelSpeed` 独立判断。
- 公式型目标、缺失或非正单值、EvidenceLevel C/D/E、明确禁止训练或缺少 PassRole 的记录不进入对应监督训练。
- Manufacturer、standard、recommendation ranges 仍为 Constraint，不取中点生成标签。

## 完整性

- 原始 Excel SHA256: `4f7baeb026f9e6c8d9609baa7dc34709466b52b0b7e228c70fb204af38fc8986`
- 原始 Excel 未修改。
- V0.1 `models.joblib` 未覆盖，与部署快照哈希一致。
- 本阶段未调用训练流程，未生成新的最终模型。
