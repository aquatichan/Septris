"""Step 8b: label-free sanity check of the eICU zero-shot test.

Does each frozen model rank stays with a recorded sepsis diagnosis above
other stays (maximum score in the first 24 ICU hours)? This does not depend
on the hand-built eICU onset label. Writes outputs/eicu/label_free_check.json.

    python scripts/08b_eicu_label_free.py /path/to/eicu-demo/data
"""
import sys, json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
EICU = sys.argv[1]
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.metrics import roc_auc_score
import importlib.util
spec=importlib.util.spec_from_file_location('e',str(ROOT/'scripts/08_eicu_external.py')); e=importlib.util.module_from_spec(spec); spec.loader.exec_module(e)
from src import features as F, labels as L
src=Path(EICU)
h,pt,_=e.convert(src); h,_,_=e.label(h,pt,src)
h['patient_id']='e'+h.patientunitstayid.astype(str); h['hospital']='E'; h=h.sort_values(['patient_id','hour'],kind='stable').reset_index(drop=True)
var=json.load(open(ROOT/'outputs/variables_used.json'))['used']
be=F.causal_base(h,var)
cov=pd.Series({v: be['observed'][:,j].mean()*100 for j,v in enumerate(var)})
ab=pd.read_csv(ROOT/'outputs/availability.csv').set_index('variable')
cov_tab=pd.DataFrame({'eICU_hours%':cov.round(2),'A_hours%':ab['A_hours_pct'].round(2),'B_hours%':ab['B_hours_pct'].round(2)}).loc[var]
cov_tab.to_csv(ROOT/'outputs/eicu/coverage.csv')
print(pd.DataFrame({'eICU_hours%':cov.round(1),'A_hours%':ab['A_hours_pct'].round(1),'B_hours%':ab['B_hours_pct'].round(1)}).loc[var].to_string())
print(h[['HR','MAP','Resp','Temp','O2Sat','WBC','Lactate','Creatinine','FiO2']].describe().loc[['50%','mean']].round(2).to_string())
# label-free check: max first-24h score vs recorded sepsis diagnosis (stay level)
dx=pd.read_csv(src/'diagnosis.csv.gz',usecols=['patientunitstayid','diagnosisstring'])
dxs=set(dx.loc[dx.diagnosisstring.str.contains('sepsis',case=False),'patientunitstayid'])
rows=pd.read_parquet(ROOT/'data/processed/rows.parquet'); hab=pd.read_parquet(ROOT/'data/processed/hourly.parquet').sort_values(['patient_id','hour'],kind='stable').reset_index(drop=True)
bab=F.causal_base(hab,var); del hab
tr=(rows.hospital=='A').to_numpy()&(rows.split=='train').to_numpy()&rows.in_training.to_numpy()
pools=F.fit_pools(bab,tr)
first24=(h.hour<24).to_numpy(); sid=h.patientunitstayid.to_numpy(); res={}
for fs in ('values','missing','combined'):
    b=lgb.Booster(model_file=str(ROOT/f'outputs/models/A_lgbm_{fs}.txt')); s=b.predict(F.assemble(be,pools,fs))
    m=pd.Series(s[first24]).groupby(sid[first24]).max()
    res[f'A:lgbm_{fs}']=round(roc_auc_score(m.index.isin(dxs), m.values),3); print(fs, res[f'A:lgbm_{fs}'])
s=F.news_score(be); m=pd.Series(s[first24]).groupby(sid[first24]).max(); res['news']=round(roc_auc_score(m.index.isin(dxs), m.values),3)
s=F.sirs_count(be); m=pd.Series(s[first24]).groupby(sid[first24]).max(); res['sirs']=round(roc_auc_score(m.index.isin(dxs), m.values),3)
res['stays_with_diagnosis']=int(m.index.isin(dxs).sum()); res['stays']=int(len(m))
(ROOT/'outputs/eicu/label_free_check.json').write_text(json.dumps(res, indent=1)); print(res)
