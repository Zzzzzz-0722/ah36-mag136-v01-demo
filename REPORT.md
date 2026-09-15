# V0.1 数据与模型运行报告

输入SHA256：4f7baeb026f9e6c8d9609baa7dc34709466b52b0b7e228c70fb204af38fc8986

四表有效记录：24条工艺参数、18个Case、32条参数、3条实验结果。原始Excel只读。
CaseID多对一合并后为38条角色上下文，来自32条源记录。UNESA明确共用固定电参的3条记录展开为9条角色上下文，保留ObservationID和1/3权重；独立实验记录仍为3。

## 数据资格

{
  "Current": {
    "contexts": 9,
    "observations": 3,
    "cases": 3,
    "sources": 1
  },
  "Voltage": {
    "contexts": 9,
    "observations": 3,
    "cases": 3,
    "sources": 1
  },
  "TravelSpeed": {
    "contexts": 0,
    "observations": 0,
    "cases": 0,
    "sources": 0
  }
}

严格已批准样本：0。演示使用TrainableResearch研究模式，保留源表待审核状态。
电流与电压分别只有3个Case，全部来自同一论文，同为12mm、PA、5mm间隙，角度40/50/60度；标签固定190A与33V。
TravelSpeed没有符合五输入与数据资格要求的标签，保存为未拟合状态，模型和评价均返回不可用，不以范围中点或候选参数补齐。
P18的8道没有角色，且35度定义不明；不会猜测道次功能或角度。P12PA为工程候选且电流列含错位公式。

## 源表问题

逐道参数K2:K11存在电流上限除以10的错位公式，缓存与表达式存在不一致。K2缓存18A且不在自身160至180A范围内。
所有公式型目标隔离，源值、公式、坐标保留在Model_Training_V1.csv和data_issues.csv。原表未经重算，以免覆盖可追溯缓存。
实验结果是三个UNESA Case的拉伸/弯曲结果，未复制成逐道质量标签，也未用于工艺回归输入。

## 评价

Grouping      Target    Model  Cases  Sources  N  EligibleContexts  Coverage  MAE  RMSE  CaseMacroMAE  CaseMacroRMSE  Coverage95                                            Status
  CaseID     Current Baseline      3        1  9                 9       1.0  0.0   0.0           0.0            0.0         NaN Descriptive only: single source, constant targets
  CaseID     Current      GPR      3        1  9                 9       1.0  0.0   0.0           0.0            0.0         1.0 Descriptive only: single source, constant targets
  CaseID     Voltage Baseline      3        1  9                 9       1.0  0.0   0.0           0.0            0.0         NaN Descriptive only: single source, constant targets
  CaseID     Voltage      GPR      3        1  9                 9       1.0  0.0   0.0           0.0            0.0         1.0 Descriptive only: single source, constant targets
  CaseID TravelSpeed Baseline      0        0  0                 0       0.0  NaN   NaN           NaN            NaN         NaN          Insufficient independent groups / labels
  CaseID TravelSpeed      GPR      0        0  0                 0       0.0  NaN   NaN           NaN            NaN         NaN          Insufficient independent groups / labels

Leave-One-Case-Out，3个Case分别留出，预处理只拟合训练折。folds.json可逐折检查Case隔离。
零误差仅表明复现同一文献的固定控制值，不能证实板厚、角色或位置泛化。来源分组只有1组，无法评估跨来源泛化。
GPR的95%区间是未校准模型区间；常量标签下采用固定先验尺度，不是实验测量不确定度。Baseline无概率区间。

## 约束及演示

所有预测保留原始值；33V会超出匹配的通用约束。多条范围分别展示，不合并成伪标准。
厂家品牌、材料、线径未确认的规则只标NeedsContext。窄间隙规则不用于单V，Consistency Check典型点不当边界。
Demo 1为12/50/5/PA；Demo 2为12/40/8/PA，明确间隙外推；Demo 3为18/35/6/PF，缺少位置支持而不出模型值。
辅助参考独立列示，不能解释成焊速模型预测。

## 下一阶段

优先核对K列公式和P18角色/角度定义；补充不同板厚、位置、角色的完整实测单值、原始来源和审核结果。
至少需要多个独立Case及来源的焊速标签才能对TravelSpeed做可信的留组评价。增加重复试验后才能校准不确定度。
