"""Regularized return-distribution GAN; forecasts remain experimental, not calibrated."""
import math
import time
import torch
from torch import nn


class Generator(nn.Module):
    def __init__(self):
        super().__init__()
        self.net=nn.Sequential(nn.Linear(8,32),nn.LeakyReLU(.2),nn.Linear(32,16),nn.LeakyReLU(.2),nn.Linear(16,1))
        # Start with a dispersed Gaussian and learn a residual transformation.
        # Unlike a narrow randomly initialized MLP, the initial output has variance.
        nn.init.zeros_(self.net[-1].weight)
        nn.init.zeros_(self.net[-1].bias)

    def forward(self,z):
        return z[:,:1]+.25*self.net(z)


class Discriminator(nn.Module):
    def __init__(self):
        super().__init__()
        self.net=nn.Sequential(nn.Linear(1,32),nn.LeakyReLU(.2),nn.Linear(32,1))

    def forward(self,x):
        return self.net(x)


class GANEstimator:
    def __init__(self):
        self.device='mps' if torch.backends.mps.is_available() else 'cpu'
        self.g=Generator().to(self.device)
        self.d=Discriminator().to(self.device)
        self.go=torch.optim.Adam(self.g.parameters(),lr=.001)
        self.do=torch.optim.Adam(self.d.parameters(),lr=.001)
        self.ready=False
        self.scale=1.
        self.mean=0.
        self.quality={'healthy':False,'reason':'GAN sin entrenar'}
        self.steps_total=0
        self.last_scenario_count=0
        self.last_up_scenarios=0

    def train(self,returns,steps=80):
        x=torch.tensor(returns,dtype=torch.float32,device=self.device).reshape(-1,1)
        if len(x)<30 or not bool(torch.isfinite(x).all().item()):
            self.ready=False
            raise ValueError('GAN requiere al menos 30 retornos finitos')
        self.mean=float(x.mean().item())
        self.scale=float(x.std(unbiased=False).item())
        if self.scale<1e-8:
            self.ready=False
            self.quality={'healthy':False,'reason':'Retornos sin variación suficiente'}
            return self.quality
        x=(x-self.mean)/self.scale
        target=x.sort(dim=0).values
        quantiles=torch.tensor([.05,.25,.5,.75,.95],device=self.device)
        target_q=target[(quantiles*(len(x)-1)).long()]
        loss=nn.BCEWithLogitsLoss()
        for _ in range(steps):
            real=x[torch.randint(len(x),(64,),device=self.device)]
            fake=self.g(torch.randn(64,8,device=self.device))
            self.do.zero_grad()
            dl=loss(self.d(real),torch.ones_like(real))+loss(self.d(fake.detach()),torch.zeros_like(fake))
            dl.backward()
            self.do.step()
            # Independent noise for the generator step; discriminator is frozen.
            for parameter in self.d.parameters(): parameter.requires_grad_(False)
            self.go.zero_grad()
            fake=self.g(torch.randn(64,8,device=self.device))
            adversarial=loss(self.d(fake),torch.ones_like(fake))
            fake_q=fake.sort(dim=0).values[(quantiles*63).long()]
            moment_penalty=2*fake.mean().square()+2*(fake.std(unbiased=False)-1).square()
            quantile_penalty=.5*(fake_q-target_q).square().mean()
            gl=adversarial+moment_penalty+quantile_penalty
            gl.backward()
            self.go.step()
            for parameter in self.d.parameters(): parameter.requires_grad_(True)
        self.steps_total+=steps
        self.ready=True
        self.quality=self.assess_quality()
        return self.quality

    def assess_quality(self):
        with torch.no_grad():
            samples=self.g(torch.randn(4096,8,device=self.device))
            mean=float(samples.mean().item())
            std=float(samples.std(unbiased=False).item())
        healthy=math.isfinite(mean) and math.isfinite(std) and abs(mean)<.35 and .5<std<1.8
        return dict(healthy=healthy,normalized_mean=mean,std_ratio=std,
                    reason='Dispersión y media dentro de tolerancias' if healthy else 'GAN degradada: sesgo o colapso de dispersión',
                    trained_at=time.time(),steps_total=self.steps_total,
                    note='Control de distribución; no acredita precisión predictiva')

    def predict(self,current_return=0.,remaining=300.):
        if not self.ready:
            raise ValueError('GAN sin entrenamiento válido')
        with torch.no_grad():
            scenarios=self.g(torch.randn(1000,8,device=self.device))*self.scale+self.mean
            # Experimental remaining-horizon approximation; not Chainlink TWAP.
            fraction=max(0.,min(1.,remaining/300.))
            future=(scenarios-self.mean)*fraction**.5+self.mean*fraction
            self.last_up_scenarios=int((future+current_return>=0).sum().item())
            self.last_scenario_count=1000
            return self.last_up_scenarios/1000
