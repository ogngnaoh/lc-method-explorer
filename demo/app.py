"""Local interface to frozen models; run from demo/ for Streamlit config."""
from io import BytesIO
import altair as alt
import pandas as pd
import streamlit as st
from rdkit.Chem import Draw
from service import ROOT, RESULTS, LABELS, load_bundle, predict, export_frame
from chromrt.chemistry import parse_smiles

st.set_page_config(page_title='LC Method Explorer', page_icon='🧪', layout='wide')
st.markdown('''<style>
.block-container {max-width:1200px;padding-top:1rem;padding-bottom:2rem;padding-left:2.5rem;padding-right:2.5rem;}
h1 {font-size:2.25rem!important;letter-spacing:-.035em;}
h2 {font-size:1.5rem!important;letter-spacing:-.02em;}
h3 {font-size:1.4rem!important;}
[data-testid="stSidebar"] {min-width:280px;max-width:280px;}
[data-testid="stSidebar"] .block-container {padding-top:2rem;}
[data-testid="stMetricValue"] {font-size:1.9rem;}
@media(max-width:640px) {.block-container{padding:1rem;}h1{font-size:1.9rem!important;}}
</style>''', unsafe_allow_html=True)

@st.cache_resource
def resources():
    return load_bundle()

try:
    bundle = resources()
except (ValueError, FileNotFoundError) as error:
    st.error(f'Cannot load the verified experiment: {error}')
    st.info('Follow the model-artifact setup in README.md, then restart the demo.')
    st.stop()

st.title('LC Method Explorer')
st.markdown('Predict retention. Compare measured methods.')

with st.sidebar:
    st.header('Explore')
    source = st.radio('Input', ['Held-out example', 'New SMILES'])
    examples = bundle['compounds'].merge(bundle['splits'][['compound_id','partition']], on='compound_id').query("partition == 'holdout'")
    ids = examples.compound_id.tolist()
    names = examples.set_index('compound_id').name.to_dict()
    compound_id = None
    smiles = None
    if source == 'Held-out example':
        compound_id = st.selectbox('Compound', ids, index=ids.index(52), format_func=lambda cid: f'{names[cid]} · {cid}')
    else:
        smiles = st.text_area('SMILES', value='CCO', help='Enter a molecular structure. No measured outcome is assumed.')
    model_id = st.selectbox('Model', list(LABELS), format_func=LABELS.get)
    st.caption('XGBoost was selected in development. Other models are comparisons.')
    st.markdown('**Target window (min)**')
    left, right = st.columns(2)
    low = left.number_input('Lower', min_value=0.0, value=5.0, step=0.5)
    high = right.number_input('Upper', min_value=0.0, value=10.0, step=0.5)
    reveal = st.checkbox('Reveal measurements', disabled=compound_id is None) and compound_id is not None
    st.divider()
    st.caption('MCMRT V3 · 30 measured methods\n\nLocal inference · no retraining')


def prediction_chart(ranked):
    shown = ranked.head(10)
    order = shown.method_id.tolist()
    points = alt.Chart(shown).mark_point(filled=True, size=85).encode(
        x=alt.X('prediction_min:Q', title='Retention time (min)', scale=alt.Scale(zero=True)),
        y=alt.Y('method_id:N', sort=order, title=None, axis=alt.Axis(labelOverlap=False)),
        color=alt.Color('physical_status:N', scale=alt.Scale(domain=['Within run','Invalid time'], range=['#00857b','#b42318']), legend=None),
        tooltip=['method_id', alt.Tooltip('prediction_min:Q', title='Predicted (min)', format='.2f'), 'column_name', 'physical_status'])
    band = alt.Chart(pd.DataFrame({'low':[low], 'high':[high]})).mark_rect(color='#00857b', opacity=.10).encode(x='low:Q',x2='high:Q')
    chart = band + points
    if reveal:
        observed = alt.Chart(shown.dropna(subset=['rt_min'])).mark_point(shape='diamond', size=110, color='#405d58', filled=False).encode(
            x='rt_min:Q', y=alt.Y('method_id:N', sort=order), tooltip=['method_id', alt.Tooltip('rt_min:Q', title='Measured (min)', format='.2f')])
        chart += observed
    return chart.properties(height=220).configure_view(stroke=None).configure_axis(labelFontSize=12,titleFontSize=13,gridColor='#e8edf2')


def recommendations():
    if low >= high:
        st.error('The upper limit must be greater than the lower limit.')
        return
    try:
        molecular, ranked = predict(bundle, model_id, low, high, compound_id=compound_id, smiles=smiles)
    except (ValueError, RuntimeError) as error:
        st.error(f'Unable to predict: {error}')
        return
    st.subheader(names[compound_id] if compound_id is not None else 'Your molecule')
    drawing, description = st.columns([1,3])
    mol = parse_smiles(molecular.get('source_smiles', molecular['canonical_smiles']))
    picture = BytesIO()
    Draw.MolToImage(mol, size=(420,210)).save(picture, format='PNG')
    drawing.image(picture.getvalue(), width=250)
    with description:
        if compound_id is not None:
            n = ranked.rt_min.notna().sum()
            st.write(f'Held-out example · {n}/30 methods measured')
            st.caption('This compound group was excluded from model fitting. Reveal outcomes to inspect the recommendation.')
        else:
            st.write('New input · unmeasured predictions')
            st.caption('Performance on this molecule is unknown. The model supports only the 30 listed methods.')
            groups = bundle['splits'].loc[bundle['splits'].compound_group == molecular['compound_group'], 'partition'].unique()
            if len(groups):
                st.info(f'This structure group is already in the dataset ({", ".join(groups)}). It is not a novel-compound demonstration.')
        st.caption(f"Formula: {molecular['rdkit_formula']} · Molecular weight: {molecular['mol_MolWt']:.1f} · TPSA: {molecular['mol_TPSA']:.1f} Å²")
    bad = (ranked.physical_status == 'Invalid time').sum()
    if bad:
        st.warning(f'{bad} physically invalid prediction(s): below zero or after the run. Raw values remain visible and affect the frozen ranking; do not interpret them as credible retention times.')
    st.subheader('Ranked predictions')
    st.caption('Top 10 of 30 methods. Shaded band: target window. Points: model predictions.' + (' Dark diamonds: measurements.' if reveal else ''))
    st.altair_chart(prediction_chart(ranked), width='stretch')
    if reveal:
        first = ranked.iloc[0]
        if pd.isna(first.rt_min):
            st.info(f"Rank 1, {first.method_id}: no measured outcome available. Missing is not failure.")
        else:
            hit = low <= first.rt_min <= high
            st.info(f"Rank 1, {first.method_id}: measured {first.rt_min:.2f} min — {'inside' if hit else 'outside'} the target window.")
    st.subheader('Supported methods')
    columns = ['rank','method_id','prediction_min','physical_status','run_time_min','column_name']
    if reveal:
        columns += ['rt_min']
    titles = {'rank':'Rank','method_id':'Method','prediction_min':'Predicted RT (min)','physical_status':'Time check',
              'run_time_min':'Run time (min)','column_name':'Column','rt_min':'Measured RT (min)'}
    table = ranked[columns].rename(columns=titles)
    st.dataframe(table, hide_index=True, height=350, width='stretch', column_config={
        titles[c]: st.column_config.NumberColumn(format='%.2f') for c in ['prediction_min','rt_min'] if c in columns})
    st.caption('Ordered by distance to the window, then its center, run duration, and method ID. Missing measurements appear as empty cells.')
    with st.expander('Inspect a method'):
        chosen = st.selectbox('Method settings', ranked.method_id.tolist())
        method = ranked.set_index('method_id').loc[chosen]
        st.write(f"**{chosen} · {method.column_name}**")
        st.write(f"{method.column_dimensions_raw} · Column {method.column_temperature_c:g} °C · Run {method.run_time_min:g} min")
        st.write(f'**Mobile phase A:** {method.mobile_phase_a_raw}')
        st.write(f'**Mobile phase B:** {method.mobile_phase_b_raw}')
        gradient = bundle['gradients'].query('method_id == @chosen')
        st.altair_chart(alt.Chart(gradient).mark_line(point=True,color='#00857b').encode(
            x=alt.X('time_min:Q',title='Time (min)'),y=alt.Y('percent_b:Q',title='B (%)',scale=alt.Scale(domain=[0,100])),
            tooltip=['time_min','percent_b','flow_ml_min']).properties(height=180), width='stretch')
        st.dataframe(gradient[['time_min','percent_b','flow_ml_min']], hide_index=True, width='stretch')
    exported = export_frame(ranked, model_id, low, high, reveal)
    exported['input_smiles'] = molecular.get('source_smiles', molecular['canonical_smiles'])
    exported['source_compound_id'] = compound_id
    st.download_button('Download ranking', exported.to_csv(index=False).encode(), file_name=f'chromrt-{model_id}-ranking.csv', mime='text/csv')
    st.caption('Retention-window fit does not establish separation quality. Point predictions have no calibrated uncertainty intervals.')


def evidence():
    st.subheader('What the holdout shows')
    st.caption('70 compounds · 69 compound groups · 2,047 observations. The evaluated holdout is not available for further tuning.')
    for column, key in zip(st.columns(3), ['median','rf_leaf1','xgb_depth5']):
        column.metric(f'{LABELS[key]} · MAE', f"{bundle['metrics']['models'][key]['retention']['mae_min']:.2f} min")
    st.write('XGBoost remains the demo default because it won development validation. Random Forest performed better on the final holdout.')
    st.image(str(ROOT/'reports/figures/retention_evaluation.png'), width='stretch')
    st.subheader('Does personalization help?')
    st.write('XGBoost hit the target in **172/268 cases (64.2%)**, versus **169/268 (63.1%)** for the fixed-method rule: three additional hits. This is a modest descriptive difference; significance and laboratory time savings have not been established.')
    st.caption('Four prespecified windows × 67 fully measured compounds. Three incomplete compounds are excluded from ranking evaluation only. Changing the sidebar window does not change these frozen results.')
    st.image(str(ROOT/'reports/figures/recommendation_evaluation.png'), width='stretch')
    with st.expander('Errors by method and held-out failures'):
        st.dataframe(pd.read_csv(RESULTS/'holdout/xgb_depth5_by_method.csv'), hide_index=True, width='stretch')
        predictions = pd.read_csv(RESULTS/'holdout/xgb_depth5_predictions.csv')
        invalid = predictions.query('prediction_min < 0 or prediction_min > run_time_min')
        st.write(f'**{len(invalid)} physically invalid XGBoost predictions** remain in the reported scores.')
        st.dataframe(invalid[['compound_id','method_id','rt_min','prediction_min']], hide_index=True, width='stretch')
        cases = pd.read_csv(RESULTS/'holdout/xgb_depth5_ranking_cases.csv')
        st.write('Successes and failures across every evaluated compound/window:')
        st.dataframe(cases, hide_index=True, width='stretch')
    st.subheader('Boundaries of the evidence')
    st.write('This experiment tests unseen compound groups under familiar methods. It does not test unseen columns, new gradients, scaffold extrapolation, mixtures, external laboratories, or separation quality. Chemical grouping reduces related-structure leakage; it is not a scaffold split.')
    st.markdown('[MCMRT V3 dataset](https://doi.org/10.57760/sciencedb.15823) · CC0 dataset record. Source structures and identifier caveats are documented in the repository.')
    st.download_button('Download evaluation report', (ROOT/'reports/MODEL_RESULTS.md').read_bytes(), file_name='MODEL_RESULTS.md',mime='text/markdown')

recommendation_tab, evidence_tab = st.tabs(['Recommendations','Evidence'])
with recommendation_tab:
    recommendations()
with evidence_tab:
    evidence()
