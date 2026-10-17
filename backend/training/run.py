"""Reproducible offline experiment. Never promotes weights to live trading."""
import argparse
import json
import math
from pathlib import Path
import numpy as np
import torch
from .data import build_examples, temporal_split
from .conditional_gan import ConditionalEnsemble
from backend.gan import GANEstimator


def metrics(p,y):
    p=np.clip(p,1e-6,1-1e-6)
    return dict(brier=float(np.mean((p-y)**2)),log_loss=float(-np.mean(y*np.log(p)+(1-y)*np.log(1-p))),accuracy=float(np.mean((p>=.5)==y)))


def clustered_interval(records, difference):
    cycles=np.array([r['cycle'] for r in records]);unique=np.unique(cycles)
    grouped=np.array([difference[cycles==c].mean() for c in unique])
    rng=np.random.default_rng(93)
    means=np.array([rng.choice(grouped,len(grouped),replace=True).mean() for _ in range(1000)])
    return list(map(float,np.quantile(means,[.025,.975])))


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--data',required=True);parser.add_argument('--out',required=True);parser.add_argument('--steps',type=int,default=800)
    args=parser.parse_args();out=Path(args.out);out.mkdir(parents=True,exist_ok=True)
    torch.set_num_threads(2);torch.manual_seed(19)
    records=build_examples(json.loads(Path(args.data).read_text()));train,cal,test=temporal_split(records)
    print(f'Examples train={len(train)}, calibration={len(cal)}, test={len(test)}',flush=True)
    model=ConditionalEnsemble();model.fit(train,steps=args.steps)
    print('Ensemble trained; evaluating untouched test segment',flush=True)
    cp=model.probabilities(cal);model.fit_calibration(cp,np.array([r['label'] for r in cal]))
    raw=model.probabilities(test);pred=model.calibrated(raw);y=np.array([r['label'] for r in test])
    diffusion=np.array([.5*(1+math.erf(r['distance']/r['scale']/math.sqrt(2))) for r in test])
    old=GANEstimator();old.device='cpu'
    returns=[math.log(r['final']/r['reference']) for r in train if r['cutoff']==r['cycle']]
    old.train(returns,steps=args.steps)
    with torch.no_grad():draws=(old.g(torch.randn(4096,8))*old.scale+old.mean).numpy().ravel()
    legacy=np.array([np.mean((draws-old.mean)*math.sqrt((r['label_time']-r['cutoff'])/300)+old.mean*((r['label_time']-r['cutoff'])/300)+r['distance']>=0) for r in test])
    predictions={'conditional_raw':raw,'conditional_calibrated':pred,'diffusion':diffusion,'legacy_retrained':legacy,'constant_50':np.full(len(test),.5)}
    report=dict(data_source='Binance BTCUSDT closed 1m; binary labels from Binance 5m, not official Chainlink settlement',steps=args.steps,
                segments={name:dict(examples=len(part),cycles=len({r['cycle'] for r in part}),start=part[0]['cutoff'],end=part[-1]['label_time']) for name,part in [('train',train),('calibration',cal),('test',test)]},
                metrics={name:metrics(p,y) for name,p in predictions.items()},calibration=list(model.calibration),
                brier_difference_95ci={name:clustered_interval(test,(pred-y)**2-(p-y)**2) for name,p in [('diffusion',diffusion),('legacy_retrained',legacy)]},
                by_elapsed={str(elapsed):{name:metrics(p[np.array([r['cutoff']-r['cycle']==elapsed for r in test])],y[np.array([r['cutoff']-r['cycle']==elapsed for r in test])]) for name,p in predictions.items()} for elapsed in [0,60,120,180,240]},
                promoted=False,reason='Offline challenger only. Requires prospective evaluation against official settlement and executable quotes. No historical order books: no profit claim.',
                legacy_note='Retrained frozen legacy architecture, not reconstruction of historical live weights.',limitations=['Single chronological holdout; no walk-forward or regime replication yet.','Minute-boundary observations do not validate the live 15–30-second entry window.','Calibration and model selection need a new future holdout after this report.'])
    checkpoint=Path(args.data).parent/'conditional-wgan-gp-v1.pt';model.save(checkpoint,{'segments':report['segments'],'evaluation':report['metrics'],'promoted':False})
    (out/'evaluation.json').write_text(json.dumps(report,indent=2))
    Path(__file__).with_name('latest_evaluation.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)

if __name__=='__main__':main()
