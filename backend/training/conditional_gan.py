"""Conditional WGAN-GP challenger. Kept separate from the trading engine."""
import math
import numpy as np
import torch
from torch import nn
from .data import FEATURES


class ConditionalGenerator(nn.Module):
    def __init__(self,n_features):
        super().__init__()
        self.location=nn.Sequential(nn.Linear(n_features,32),nn.SiLU(),nn.Linear(32,1))
        self.log_scale=nn.Sequential(nn.Linear(n_features,32),nn.SiLU(),nn.Linear(32,1))
        self.residual=nn.Sequential(nn.Linear(n_features+8,64),nn.SiLU(),nn.Linear(64,32),nn.SiLU(),nn.Linear(32,1))
        nn.init.zeros_(self.location[-1].weight);nn.init.zeros_(self.location[-1].bias)
        nn.init.zeros_(self.log_scale[-1].weight);nn.init.zeros_(self.log_scale[-1].bias)
        nn.init.zeros_(self.residual[-1].weight);nn.init.zeros_(self.residual[-1].bias)
    def forward(self,c,z):
        scale=.1+torch.nn.functional.softplus(self.log_scale(c))
        return self.location(c)+scale*z[:,:1]+.1*self.residual(torch.cat([c,z],dim=1))


class ConditionalCritic(nn.Module):
    def __init__(self,n_features):
        super().__init__()
        self.net=nn.Sequential(nn.Linear(n_features+1,64),nn.LeakyReLU(.2),nn.Linear(64,32),nn.LeakyReLU(.2),nn.Linear(32,1))
    def forward(self,c,y):return self.net(torch.cat([c,y],dim=1))


def gradient_penalty(critic,c,real,fake):
    # Use one convex interpolation coefficient for both endpoints.
    alpha=torch.rand(len(c),1)
    mix=(alpha*real+(1-alpha)*fake).requires_grad_(True)
    score=critic(c,mix)
    gradient=torch.autograd.grad(score,mix,torch.ones_like(score),create_graph=True)[0]
    return (gradient.norm(2,dim=1)-1).square().mean()


class ConditionalEnsemble:
    def __init__(self):
        self.models=[];self.mean=None;self.std=None;self.calibration=(1.,0.);self.metadata={}
    def fit(self,records,seeds=(11,23,37),steps=800,batch_size=128):
        x=np.stack([r['x'] for r in records]);y=np.array([r['target'] for r in records],dtype=np.float32)
        self.mean=x.mean(axis=0);self.std=np.maximum(x.std(axis=0),1e-5)
        c=torch.tensor(np.clip((x-self.mean)/self.std,-8,8),dtype=torch.float32)
        limits=np.quantile(y,[.005,.995]);target=torch.tensor(np.clip(y,*limits),dtype=torch.float32).reshape(-1,1)
        history=[]
        for seed in seeds:
            torch.manual_seed(seed)
            g=ConditionalGenerator(c.shape[1]);d=ConditionalCritic(c.shape[1])
            go=torch.optim.Adam(g.parameters(),lr=.0002,betas=(0.,.9));do=torch.optim.Adam(d.parameters(),lr=.0002,betas=(0.,.9))
            for step in range(steps):
                for _ in range(3):
                    idx=torch.randint(len(c),(batch_size,));cb=c[idx];real=target[idx]
                    fake=g(cb,torch.randn(batch_size,8)).detach()
                    do.zero_grad();dl=d(cb,fake).mean()-d(cb,real).mean()+10*gradient_penalty(d,cb,real,fake)
                    dl.backward();do.step()
                idx=torch.randint(len(c),(batch_size,));cb=c[idx];real=target[idx]
                for p in d.parameters():p.requires_grad_(False)
                a=g(cb,torch.randn(batch_size,8));b=g(cb,torch.randn(batch_size,8))
                # Conditional CRPS sample estimator rewards distributional accuracy.
                crps=.5*((a-real).abs()+(b-real).abs()-(a-b).abs()).mean()
                go.zero_grad();gl=-d(cb,a).mean()+crps;gl.backward();go.step()
                for p in d.parameters():p.requires_grad_(True)
            g.eval();self.models.append(g)
            history.append(dict(seed=seed,critic_loss=float(dl.item()),generator_loss=float(gl.item()),crps_train_batch=float(crps.item())))
        self.metadata=dict(features=FEATURES,steps=steps,seeds=list(seeds),train_examples=len(records),target_clip=list(map(float,limits)),history=history)
        return history

    def probabilities(self,records,samples_per_model=128,seed=771):
        torch.manual_seed(seed)
        x=np.stack([r['x'] for r in records]);scale=np.array([r['scale'] for r in records]);distance=np.array([r['distance'] for r in records])
        output=[]
        with torch.no_grad():
            for begin in range(0,len(records),128):
                end=min(begin+128,len(records));c=torch.tensor(np.clip((x[begin:end]-self.mean)/self.std,-8,8),dtype=torch.float32)
                repeated=c.repeat_interleave(samples_per_model,dim=0)
                votes=np.zeros(len(c))
                for model in self.models:
                    future=model(repeated,torch.randn(len(repeated),8)).reshape(len(c),samples_per_model).numpy()
                    votes+=(future*scale[begin:end,None]+distance[begin:end,None]>=0).sum(axis=1)
                output.extend(votes/(len(self.models)*samples_per_model))
        return np.array(output)

    def fit_calibration(self,p,y):
        # Calibration sees only its own chronological segment, never test outcomes.
        x=torch.tensor(np.log(np.clip(p,.0001,.9999)/(1-np.clip(p,.0001,.9999))),dtype=torch.float32)
        labels=torch.tensor(y,dtype=torch.float32);params=torch.tensor([1.,0.],requires_grad=True)
        optim=torch.optim.LBFGS([params],lr=.3,max_iter=60)
        def closure():
            optim.zero_grad();slope=torch.nn.functional.softplus(params[0])
            logits=slope*x+params[1]
            loss=torch.nn.functional.binary_cross_entropy_with_logits(logits,labels)+.01*((slope-1)**2+params[1]**2)
            loss.backward();return loss
        optim.step(closure)
        self.calibration=(float(torch.nn.functional.softplus(params[0]).item()),float(params[1].item()))

    def calibrated(self,p):
        p=np.clip(p,.0001,.9999);a,b=self.calibration
        return 1/(1+np.exp(-np.clip(a*np.log(p/(1-p))+b,-40,40)))

    def save(self,path,metadata):
        torch.save(dict(format='conditional-wgan-gp-v1',features=FEATURES,models=[m.state_dict() for m in self.models],
                        mean=torch.tensor(self.mean),std=torch.tensor(self.std),calibration=self.calibration,
                        metadata={**self.metadata,**metadata}),path)

    @classmethod
    def load(cls,path):
        saved=torch.load(path,map_location='cpu',weights_only=True)
        if saved['format']!='conditional-wgan-gp-v1' or saved['features']!=FEATURES:raise ValueError('Incompatible checkpoint')
        self=cls();self.mean=saved['mean'].numpy();self.std=saved['std'].numpy();self.calibration=tuple(saved['calibration']);self.metadata=saved['metadata']
        for state in saved['models']:
            model=ConditionalGenerator(len(FEATURES));model.load_state_dict(state);model.eval();self.models.append(model)
        return self
