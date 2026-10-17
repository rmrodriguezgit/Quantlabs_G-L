import test from 'node:test';
import assert from 'node:assert/strict';
import {marketView,payoff,type BinarySnapshot} from '../src/binaryMarket.ts';
const fixture=():BinarySnapshot=>({mode:'live',cycle:300,price:101,reference:100,probability:.63,timestamp:400,data_updated_at:400,error:null,model_ready:true,gan_quality:{healthy:true},odds:{up:.4,down:.61,source:'POLYMARKET',available:true,slug:'btc-updown-5m-300',timestamp:400,fee_rate:.07,quotes:{UP:{timestamp:400,size:100,min_size:5},DOWN:{timestamp:400,size:100,min_size:5}}}});
test('current window keeps reference, spot, asks and complementary model probabilities distinct',()=>{
 const v=marketView(fixture(),401,true);assert.equal(v.cycle,300);assert.equal(v.remaining,199);assert.equal(v.reference,100);assert.equal(v.price,101);assert.equal(v.delta,1);assert.equal(v.up,.4);assert.equal(v.pUp,.63);assert.equal(v.pDown,.37);
});
test('boundary never shows the previous market prices or probabilities as current',()=>{
 const s=fixture();s.timestamp=599;s.data_updated_at=599;s.odds.timestamp=599;
 const v=marketView(s,600,true);assert.equal(v.cycle,600);assert.equal(v.sameCycle,false);assert.equal(v.reference,null);assert.equal(v.price,null);assert.equal(v.up,null);assert.equal(v.pUp,null);
});
test('wrong slug cannot label an ask as current',()=>{
 const s=fixture();s.odds.slug='btc-updown-5m-0';const v=marketView(s,401,true);assert.equal(v.identity,false);assert.equal(v.up,null);
});
test('stale token quote is independently hidden without inventing its complement',()=>{
 const s=fixture();s.odds.quotes!.DOWN!.timestamp=380;const v=marketView(s,401,true);assert.equal(v.up,.4);assert.equal(v.down,null);
 s.odds.up=0;assert.equal(marketView(s,401,true).up,null);
});
test('disconnection and old data suppress actionable values',()=>{
 assert.equal(marketView(fixture(),401,false).pUp,null);
 assert.equal(marketView(fixture(),410,true).up,null);
 assert.equal(marketView(fixture(),410,true).reference,null);
});
test('unhealthy or unready GAN never appears as a valid 50-percent estimate',()=>{
 const s=fixture();s.model_ready=false;assert.equal(marketView(s,401,true).pUp,null);
 s.model_ready=true;s.gan_quality!.healthy=false;assert.equal(marketView(s,401,true).pDown,null);
});
test('one-dollar payoff includes fees and checks visible depth',()=>{
 const p=payoff(1,.5,.07,1)!;assert.ok(Math.abs(p.tokens-1/.5175)<1e-10);assert.ok(Math.abs(p.tokens*.5+p.fee-1)<1e-10);assert.equal(p.loss,1);assert.equal(p.depthEnough,false);
 assert.equal(payoff(1,.5,.07,10)!.depthEnough,true);
});
test('invalid calculator inputs cannot fabricate a payoff',()=>{
 for(const amount of [NaN,Infinity,-1,0])assert.equal(payoff(amount,.5,.07,10),null);
 assert.equal(payoff(1,null,.07,10),null);assert.equal(payoff(1,.5,undefined,10),null);
});
