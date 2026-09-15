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
| EvidenceLevel A | 4 |
| EvidenceLevel B | 5 |
| EvidenceLevel C | 2 |
| EvidenceLevel D | 3 |
| EvidenceLevel E | 18 |
| PassLevel | 20 |
| CaseLevel | 1 |
| RangeLevel | 8 |
| SimulationCondition | 3 |
| Eligible Current | 3 |
| Eligible Voltage | 8 |
| Eligible TravelSpeed | 5 |
| Promotion Candidates | 0 |

以上按唯一 PassID 统计。明确共用 Root/Fill/Cap 的 3 条 UNESA 记录展开后，角色上下文共 38 条；对应 Current 9、Voltage 14、TravelSpeed 5 条可训练上下文。展开不增加独立实验数量。

## SRC-005 / SRC-007 人工裁决

- `SRC-005` 的 `R1/R2/R3` 原始参数完整保留，定级为 EvidenceLevel D、SimulationCondition、Designed FE condition、SimulationReference。三项目标均不进入当前模型，TravelSpeed 标记为公式设计量，用于 Simulation reference / Heat-input consistency check / Retrieval。
- `SRC-007` 的 `S1` 升级为 EvidenceLevel A，定级为 CaseLevel、Experimental。Position 与 PassRole 保持未报告状态，三项目标均不进入当前 Pass-level 模型，用于 Experimental case-level reference / future case-level model / retrieval。
- 当前源工作簿中只有已核实的 `SRC-007 S1`，没有其他已核实 specimen 记录，因此未新增 specimen，也未将 specimen 人为映射为 Root / Fill / Cap。

两类数据均已从 Promotion Queue 移除。Promotion Queue 现为空，只会收录补充 1-2 个原始字段后可能进入当前 Pass-level 模型的真实候选记录。

## 资格规则

- `InProjectScope` 只在全部固定身份与三个数值范围同时满足时为 True。
- `EvidenceLevel_Suggested` 继续根据 metadata 生成；SRC-005 与 SRC-007 的人工等级写入 `EvidenceLevel_Manual`，并将 `EvidenceReviewStatus` 设为 Reviewed。
- 当前 Pass-level GPR 资格要求 `InProjectScope = True`、`DataGranularity = PassLevel`、`TargetProvenance` 合格且对应目标为合法单值。
- `Eligible_Current`、`Eligible_Voltage`、`Eligible_TravelSpeed` 独立判断。
- 公式型目标、缺失或非正单值、明确禁止训练或缺少 PassRole 的记录不进入对应监督训练。
- Manufacturer、standard、recommendation ranges 仍为 Constraint，不取中点生成标签。

## 完整性

- 原始 Excel SHA256: `4f7baeb026f9e6c8d9609baa7dc34709466b52b0b7e228c70fb204af38fc8986`
- 原始 Excel 未修改。
- V0.1 `models.joblib` 未覆盖，与部署快照哈希一致。
- 本阶段未调用训练流程，未生成新的最终模型。
