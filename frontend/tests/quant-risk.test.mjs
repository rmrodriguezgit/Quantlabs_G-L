import test from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
const temporary=await mkdtemp(join(tmpdir(),'laya-quant-render-'));
let panel,history;
try{
 await build({stdin:{contents:`import React from 'react';import {renderToStaticMarkup as render} from 'react-dom/server';import {QuantRiskPanel} from './src/QuantRiskPanel';import {TradeHistory} from './src/TradeHistory';export const panel=(s,stale=false)=>render(<QuantRiskPanel s={s} stale={stale}/>);export const history=(s)=>render(<TradeHistory s={s} uiNow={900} filter="ALL" setFilter={()=>{}}/>);`,resolveDir:root,loader:'tsx'},bundle:true,platform:'node',format:'cjs',jsx:'automatic',outfile:join(temporary,'quant.cjs')});
 ({panel,history}=(await import(join(temporary,'quant.cjs'))).default);
}finally{await rm(temporary,{recursive:true,force:true});}
function state(){return {profile:'quant_laya',probability:.6,validator:{rsi:50},decision:{candidates:{UP:{eligible:true,edge:.1,ev:1,rr:3,laya_pass:true,laya_probability:.7}}},account:{trades:[],performance:{sharpe:null,sortino:null}}};}
test('missing risk and performance never invent certified values',()=>{const html=panel(state());assert.match(html,/no estima drawdown/);assert.match(html,/Half-Kelly/);assert.doesNotMatch(html,/NaN|Infinity/);});
test('stale candidate explicitly not actionable',()=>{const html=panel(state(),true);assert.match(html,/NO ACCIONABLE/);assert.doesNotMatch(html,/CANDIDATO · faltan/);});
test('early sale stays distinct from official resolution and prints bid and trigger',()=>{const s=state();s.account.trades=[{id:1,timestamp:400,cycle:300,side:'UP',profile:'quant_laya',price:.2,stake:1,status:'EXITED',pnl:-.1,laya_score:.4,entry_spot:100,atr_at_entry:2,exit_price:.19,exit_spot:95,exit_time:401,exit_reason:'STOP_ATR',exit_fee:.03,risk_version:'quant-risk-v1',official_outcome:'UP'}];const html=history(s);assert.match(html,/VENDIDA PAPER/);assert.match(html,/STOP_ATR/);assert.match(html,/OFICIAL: UP/);assert.doesNotMatch(html,/>GANÓ</);});
