import test from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
const temporary=await mkdtemp(join(tmpdir(),'laya-render-parity-'));
let compare;
try {
 await build({stdin:{contents:`
 import React from 'react';
 import {renderToStaticMarkup as render} from 'react-dom/server';
 import {PipelinePanel} from './src/PipelinePanel';
 import {PipelinePanel as OldPipeline} from './tests/fixtures/pipeline-baseline.tsx.txt';
 import {TradeHistory} from './src/TradeHistory';
 import {TradeHistory as OldHistory} from './tests/fixtures/history-baseline.tsx.txt';
 export function compare(s,filter='ALL',stale=false){
 const pipeline={s,stale,dataAge:2};const history={s,uiNow:900,filter,setFilter:()=>{}};
 return [[render(<OldPipeline {...pipeline}/>),render(<PipelinePanel {...pipeline}/>)],
 [render(<OldHistory {...history}/>),render(<TradeHistory {...history}/>)]];
 }`,resolveDir:root,loader:'tsx'},bundle:true,platform:'node',format:'cjs',jsx:'automatic',loader:{'.txt':'tsx'},outfile:join(temporary,'parity.cjs')});
 ({compare}=(await import(join(temporary,'parity.cjs'))).default);
}finally{await rm(temporary,{recursive:true,force:true});}
function snapshot(){return {profile:'gan_laya',probability:.2,estimator:'GAN',validator:{score:1,rsi:32,model_connected:true,model_probability:.9,approved:true,sides:{UP:{approved:false,model_probability:.1},DOWN:{approved:true,model_probability:.9}}},decision:{action:'WAIT',ev:.1,fraction:0,candidates:{UP:{ev:-.2},DOWN:{ev:.1}}},gan_quality:{healthy:true,scenarios:1000,up_scenarios:200,std_ratio:1},blockers:['Modelo en espera'],reason:'WAIT',account:{paused:false,trades:[]}};}
for(const profile of ['gan_laya','exploratory','strategy'])test(`same pipeline and empty history: ${profile}`,()=>{
 const s=snapshot();s.profile=profile;for(const [before,after] of compare(s))assert.equal(after,before);
});
test('same references, closing prices, outcomes and history filters',()=>{
 const s=snapshot();s.account.trades=[{id:1,timestamp:400,cycle:300,side:'DOWN',profile:'gan_laya',reference:100,closing_price:98,closing_time:600,closing_source:'BINANCE',price:.4,stake:1,status:'WON',pnl:1.4,laya_score:1,gan_probability:.2,laya_model_probability:.9,validator_status:'LAYA_APPROVED',official_outcome:'DOWN',fee:.03,below_minimum:true}];
 for(const filter of ['ALL','OPEN','WON','LOST'])for(const [before,after] of compare(s,filter))assert.equal(after,before);
});
test('same stale, paused and disconnected model states',()=>{
 const s=snapshot();s.account.paused=true;s.validator.model_connected=false;s.validator.model_probability=null;s.gan_quality.healthy=false;
 for(const [before,after] of compare(s,'ALL',true))assert.equal(after,before);
});
