from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st
from data import ROLES
from models import fit_models
from service import DEMOS, recommend, nearest_references

ROOT = Path(__file__).resolve().parent
ART = ROOT
st.set_page_config(page_title='AH36 MAG 136 | V0.1', page_icon=':material/manufacturing:', layout='wide')


@st.cache_resource
def load_assets():
    frame = pd.read_csv(ART / 'Model_Training_V1.csv')
    return (frame, pd.read_csv(ART / '工艺参数库.csv'), joblib.load(ART / 'models.joblib'),
            json.loads((ART / 'audit.json').read_text(encoding='utf-8')), fit_models(frame, approved_only=True))


if not (ART / 'models.joblib').exists():
    st.error('模型文件缺失。请在项目目录运行 python train.py。')
    st.stop()
frame, constraints, research_models, audit, strict_models = load_assets()
st.title('AH36 MAG 136')
st.caption('V0.1 · 单V对接 · 板厚 / 坡口总夹角 / 根部间隙 / 焊接位置 / PassRole')
tabs = st.tabs(['工艺推荐', '模型评价', '数据审计', '组会演示'])

with tabs[0]:
    mode = st.radio('数据资格', ['研究模式（保留待审核状态）', '仅已批准数据'], horizontal=True)
    models = strict_models if mode == '仅已批准数据' else research_models
    st.warning('当前研究数据为同一文献的3个Case：电流190 A、电压33 V均为固定控制值；无合格焊速标签。模型区间尚未校准。')
    demo_names = list(DEMOS)
    initial = DEMOS[demo_names[0]]
    for key, value in initial.items():
        if key not in st.session_state:
            st.session_state[key] = value

    def apply_demo():
        for key, value in DEMOS[st.session_state['demo']].items():
            st.session_state[key] = value

    st.selectbox('固定场景', demo_names, key='demo', on_change=apply_demo)
    with st.form('query'):
        cols = st.columns(4)
        cols[0].number_input('板厚 (mm)', min_value=1., max_value=100., step=1., key='Thickness')
        cols[1].number_input('坡口总夹角 (°)', min_value=1., max_value=179., step=1., key='GrooveAngle')
        cols[2].number_input('根部间隙 (mm)', min_value=0., max_value=30., step=.5, key='RootGap')
        cols[3].selectbox('焊接位置', ['PA', 'PF', 'PC', 'PE', 'PG', 'Inclined45Up'], key='Position')
        method = st.radio('模型', ['GPR', 'Baseline'], horizontal=True)
        with st.expander('约束适用条件'):
            consumable = st.selectbox('焊材', ['T492T1-1C1A', 'Hyundai SF-71', 'Hyundai SF-71 eco', 'Hyundai Supercored 71H', '未确认'])
            diameter = st.number_input('焊丝直径 (mm)', min_value=.5, max_value=3., value=1.2, step=.1)
            st.caption('范围检查固定AH36、MAG 136、CO2、单V；不同资料的范围逐条显示，不能代替工艺评定。')
        st.form_submit_button('生成推荐', icon=':material/play_arrow:', type='primary')
    query = {k: st.session_state[k] for k in initial}
    result, checks = recommend(query, models, constraints, method, consumable, diameter)
    if result.Prediction.isna().all():
        st.info('当前数据资格或焊接位置没有模型支持，未生成推荐值。')
    elif result.Support.str.contains('Extrapolation').any():
        st.warning('输入超出训练数值覆盖，以下为模型原始外推值。')
    columns = ['PassRole', 'Target', 'Prediction', 'Std', 'Lower95', 'Upper95', 'ConstraintCheck', 'NearestCase']
    labels = {'Target': '目标', 'Prediction': '原始预测', 'Std': '标准差', 'Lower95': '95%下限', 'Upper95': '95%上限', 'ConstraintCheck': '范围检查', 'NearestCase': '最近训练Case'}
    st.subheader('Root / Fill / Cap')
    st.caption('Current: A · Voltage: V · TravelSpeed: mm/min。空白表示不可用；Baseline不提供概率区间。')
    st.dataframe(result[columns].rename(columns=labels), hide_index=True, width='stretch',
                 column_config={name: st.column_config.NumberColumn(format='%.3f')
                                for name in ['原始预测', '标准差', '95%下限', '95%上限']})
    st.download_button('下载预测 CSV', result.to_csv(index=False).encode('utf-8-sig'), 'prediction.csv', icon=':material/download:')
    with st.expander('预测依据与覆盖状态'):
        st.dataframe(result[['PassRole', 'Target', 'Support', 'Note', 'NearestPass', 'Distance']], hide_index=True, width='stretch')
    with st.expander('Constraint Check 明细', expanded=True):
        st.caption('MixedRules = 部分匹配范围内、部分范围外；NeedsContext = 焊材或适用条件仍需确认。预测值未经裁剪。')
        st.dataframe(checks, hide_index=True, width='stretch')

    st.subheader('最近辅助参考')
    st.caption('参考值保留源表性质；源值缺失、公式异常或工艺不匹配时不作为模型输出。距离只用于资料检索。')
    refs = nearest_references(query, frame[frame.DataClass != 'TrainableResearch'])
    st.dataframe(refs[['CaseID', 'PassID', 'Pass_焊道功能', 'DataClass', 'Current', 'Voltage', 'TravelSpeed', 'ReferenceDistance', 'ComparedInputs', 'ExclusionReason', 'Case_来源链接']], hide_index=True, width='stretch')
    with st.expander('坡口角度响应'):
        chart_target = st.selectbox('目标参数', ['Current', 'Voltage'])
        chart_role = st.selectbox('角色', ROLES)
        model = models[f'{chart_target}_{method}']
        curve = []
        for angle in np.linspace(30, 70, 41):
            p = model.predict({**query, 'GrooveAngle': float(angle), 'PassRole': chart_role})
            if p['Prediction'] is not None:
                curve.append({'Angle': angle, 'Mean': p['Prediction'], 'Low': p['Lower95'], 'High': p['Upper95']})
        if curve:
            points = frame.loc[frame[chart_target + '_Eligible'] & (frame.PassRole == chart_role)]
            base = alt.Chart(pd.DataFrame(curve)).encode(x=alt.X('Angle:Q', title='坡口总夹角 (°)'))
            line = base.mark_line(color='#17677a').encode(y=alt.Y('Mean:Q', title=chart_target, scale=alt.Scale(zero=False)))
            dots = alt.Chart(points).mark_point(color='#ba4934', filled=True, size=70).encode(x='GrooveAngle:Q', y=alt.Y(f'{chart_target}:Q'), tooltip=['CaseID', chart_target])
            chart = line + dots
            if method == 'GPR':
                chart = base.mark_area(opacity=.15, color='#17677a').encode(y='Low:Q', y2='High:Q') + chart
            st.altair_chart(chart, width='stretch')
            st.caption('点为源实验控制值；曲线为查询预测。30–70°含训练角度范围外的区域。')
        else:
            st.info('当前条件无响应曲线。')

with tabs[1]:
    st.subheader('Leave-One-Case-Out')
    st.warning('三个Case来自同一论文且标签固定。零误差仅表示复现固定电参，不能证明泛化性能。')
    st.dataframe(pd.read_csv(ART / 'metrics.csv'), hide_index=True, width='stretch')
    st.subheader('按来源分组')
    st.dataframe(pd.read_csv(ART / 'source_group_metrics.csv'), hide_index=True, width='stretch')
    with st.expander('逐折 Case 分配'):
        st.json(json.loads((ART / 'folds.json').read_text(encoding='utf-8')))
    st.download_button('下载评价指标', (ART / 'metrics.csv').read_bytes(), 'metrics.csv', icon=':material/download:')

with tabs[2]:
    st.subheader('数据资格与来源')
    st.dataframe(pd.DataFrame(audit['target_coverage']).T, width='stretch')
    st.caption(f"原始参数记录32条；角色上下文38条；已批准上下文{audit['approved_contexts']}条。工艺参数库24条独立保留。")
    group = st.selectbox('数据层', ['全部', 'TrainableResearch', 'Auxiliary', 'Constraint'])
    subset = frame if group == '全部' else frame[frame.DataClass == group]
    st.dataframe(subset[['ObservationID', 'CaseID', 'PassRole', 'DataClass', 'Case_训练准入', 'Current_Eligible', 'Voltage_Eligible', 'TravelSpeed_Eligible', 'ExclusionReason']], hide_index=True, width='stretch')
    st.subheader('源表问题')
    st.dataframe(pd.read_csv(ART / 'data_issues.csv'), hide_index=True, width='stretch')
    st.download_button('下载 Model_Training_V1', (ART / 'Model_Training_V1.csv').read_bytes(), 'Model_Training_V1.csv', icon=':material/download:')
    with st.expander('实验结果（独立保留）'):
        st.dataframe(pd.read_csv(ART / '实验结果.csv'), hide_index=True, width='stretch')

with tabs[3]:
    st.subheader('固定 Demo')
    st.dataframe(pd.DataFrame(DEMOS).T, width='stretch')
    st.markdown('''1. **已有文献工况**：展示190 A、33 V，解释共同控制参数和焊速缺失。
2. **间隙外推**：从5 mm改为8 mm，展示外推标记和未校准不确定度。
3. **立焊覆盖缺口**：切换18 mm、PF，展示无模型支持和PQR辅助参考。

V0.1已打通数据审计、分组训练、评价和范围检查。当前数据尚不足以建立可靠的跨板厚工艺推荐，也未建立焊接质量预测。''')
    st.download_button('下载组会报告', (ART / 'REPORT.md').read_bytes(), 'V01_REPORT.md', icon=':material/download:')
