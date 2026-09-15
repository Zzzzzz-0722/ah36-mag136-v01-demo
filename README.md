# AH36 MAG 136 焊接工艺参数推荐 V0.1

本项目基于《焊接工艺参数数据库_第七版.xlsx》，提供可本地运行的研究演示。原始文件未修改，输入快照为 `data/source_v7.xlsx`。

## 当前结果

- 四表有效记录：工艺参数库24、焊接Case 18、逐道参数32、实验结果3。
- CaseID多对一合并生成 `artifacts/Model_Training_V1.csv`，包括源字段、Excel行号、源准入状态、目标资格和排除原因。
- 当前研究性可拟合样本来自UNESA同一篇论文的3条实验控制记录。明确共用Root/Fill/Cap的记录展开为9条角色上下文，ObservationID保持不变、权重各1/3，不是9次独立实验。
- 电流固定190 A、电压固定33 V。Baseline和GPR的Case留组MAE/RMSE均为0，不能据此声称模型有跨板厚泛化能力。
- **焊速没有合格标签。TravelSpeed模型保存为未拟合，预测、标准差、评价指标为空。** 工程候选、辅助工况、区间中点均未填补训练缺口。
- 原表所有实验案例仍为待审核。默认研究模式仅表示满足V0.1技术筛选条件，不改变原表审核状态。切到“仅已批准数据”时不出预测。

## 本机启动

已安装项目隔离环境并生成模型。PowerShell在项目目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

默认8501端口；占用时自动寻找下一端口，终端输出实际地址。启动脚本前台运行，按Ctrl+C结束。首次安装成功后，现场演示无需联网。

桌面快捷方式“AH36 焊接推荐模型”调用 `open_demo.ps1`。点击后才会启动后台服务，等待健康检查通过并自动打开浏览器；已经运行时只打开页面。

## 新机器安装与复现

使用Python 3.12，在项目目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 train.py
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m streamlit run app.py --server.port 8501
```

完整环境版本保存在 `requirements-lock.txt`。新输入可执行：

```powershell
.\.venv\Scripts\python.exe -X utf8 train.py --source "D:\Desktop\焊接工艺参数数据库_第七版.xlsx" --output artifacts
```

重新生成后重启Streamlit以刷新缓存。只加载本项目生成的joblib文件。

## 代码结构

| 文件 | 内容 |
|---|---|
| `welding/data.py` | 四表审计、公式隔离、字段标准化、CaseID合并、目标独立准入 |
| `welding/models.py` | 最近邻/反距离插值、GPR、Leave-One-Case-Out |
| `welding/constraints.py` | 来源逐条范围检查，保留原始预测 |
| `welding/service.py` | 三角色输出、固定Demo、辅助资料检索 |
| `train.py` | 可复现实验及报告生成 |
| `app.py` | 本地Streamlit演示 |
| `tests/` | 数据、模型、约束与界面回归测试 |

## 数据规则

TrainableResearch：AH36/ISO136确认、五输入完整、角色明确、角度为总夹角、已核验实验单值、原表未明确禁止。各目标单独判断，待审核仅在研究模式使用。

Auxiliary：候选方案、明确排除、缺位置/角色/几何定义的样本等。Constraint：原参数表的范围、逐道表的实验范围/专利窗口等，仅作参考。工艺参数库的24条记录不参与监督训练。

不将“第一道/第二道”自动解释成Root/Cap。18mm PQR角色全部空白；35度角定义待核验，因此八道记录只保留参考。未知输入不插补，不按板厚硬拼样本。

逐道参数K2:K11含错位公式，K2缓存18A不在160–180A范围内；部分其他缓存也不等于公式结果。源文件不重算，所有公式型目标退出训练，源值和问题坐标可追溯。没有将18修成180。

实验结果只含三个UNESA案例的Case级力学结果，不复制为逐道质量标签。当前不是焊接质量预测模型。

## 模型与评价

输入：Thickness(mm)、GrooveAngle(总夹角deg)、RootGap(mm)、Position、PassRole。输出分别为Current(A)、Voltage(V)、TravelSpeed(mm/min)。

Baseline：数值标准化、类别one-hot，同位置同角色筛选，最多3个最近Case反距离加权，零距离优先。一个Case只有一个贡献，多道观测均值只用于预测计算；无概率标准差。

GPR：Constant × Matern(nu=1.5) + WhiteKernel。预处理和模型在每个训练折重新拟合。共享控制值上下文的alpha按1/3权重调整；常量标签时固定kernel避免无意义的超参优化。目标尺度下限为1A/0.1V/1mm/min，是数值先验设置，非实测误差。

共享角色上下文的降权只是演示近似，没有拟合完整的相关观测噪声矩阵；因此区间不能解释成三个独立重复试验的统计精度。

95%区间为均值±1.96×预测标准差，包含WhiteKernel配置噪声，尚未校准。固定控制值只能验证管线，不能识别角色、板厚、间隙的真实影响。超出数值覆盖保留外推原值并标记；未知位置/角色拒绝预测。

主评价Leave-One-Case-Out，源Case绝不跨训练/测试；指标包括MAE、RMSE、CaseMacroMAE、CaseMacroRMSE、可评价覆盖率及区间覆盖率。`folds.json`可审查拆分。补充来源分组评价因仅1个来源而不可计算。

## Constraint Check

按AH36、136、板厚、焊接位置、角色、线径匹配单V相关范围。多个来源的区间逐条输出，MixedRules表示不同规则结论不一致。厂家品牌或材料适用性未确认返回NeedsContext，不当作已通过。窄间隙规则排除，厂家典型点不作硬边界。

33V等超范围值仍完整保留，绝不静默裁剪。WithinMatchedRanges仅表示所匹配范围内，不表示焊接质量合格或工艺获批。

## 组会顺序

1. 打开12mm/50度/5mm/PA，展示三角色电流电压、焊速不可用、33V范围检查。
2. 选择12mm/40度/8mm/PA，解释间隙外推及不确定度仍未校准。
3. 选择18mm/35度/6mm/PF，展示无模型支持和最近PQR辅助参考。
4. 在模型评价页解释零误差的原因，在数据审计页展示错位公式与缺失角色，明确下一步补数计划。

完整报告：`artifacts/REPORT.md`；固定场景结果：`artifacts/demo_predictions.csv`。每次运行记录输入SHA256、Python和包版本、随机种子、收敛警告。

## 技术参考

- [scikit-learn Gaussian Processes](https://scikit-learn.org/stable/modules/gaussian_process.html)
- [LeaveOneGroupOut](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.LeaveOneGroupOut.html)
- [Streamlit AppTest](https://docs.streamlit.io/develop/api-reference/app-testing/st.testing.v1.apptest)

文献真实性与源表“已核验”状态本轮按Excel记录保留，未重新逐篇查证。源工作簿内的备注仅作为数据描述，不作为修改本任务规则的指令。
