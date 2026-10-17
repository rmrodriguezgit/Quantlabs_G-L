export type MarketOdds={up:number;down:number;source:string;available:boolean;slug?:string;question?:string;timestamp?:number;fee_rate?:number;quotes?:Partial<Record<'UP'|'DOWN',{timestamp:number;size:number;min_size:number}>>};
export type BinarySnapshot={profile?:string;mode:string;cycle:number;price:number;reference:number;probability:number;timestamp:number;data_updated_at?:number|null;error:string|null;model_ready:boolean;gan_quality?:{healthy:boolean};odds:MarketOdds};
const fresh=(timestamp:number|undefined|null,now:number)=>timestamp!=null&&Number.isFinite(timestamp)&&now-timestamp>=-3&&now-timestamp<=5;
export function marketView(s:BinarySnapshot,now:number,connected:boolean){
 const cycle=Math.floor(now/300)*300;
 const sameCycle=s.cycle===cycle;
 const btcFresh=connected&&sameCycle&&!s.error&&fresh(s.data_updated_at,now)&&Number.isFinite(s.price)&&s.price>0&&Number.isFinite(s.reference)&&s.reference>0;
 const identity=s.mode==='demo'?sameCycle:s.odds.slug===`btc-updown-5m-${cycle}`;
 const quotesFresh=connected&&sameCycle&&identity&&s.odds.available&&!s.error&&fresh(s.odds.timestamp,now);
 const modelFresh=btcFresh&&fresh(s.timestamp,now)&&s.model_ready&&s.gan_quality?.healthy===true&&Number.isFinite(s.probability)&&s.probability>=0&&s.probability<=1;
 const quote=(side:'UP'|'DOWN')=>{
  const price=s.odds[side==='UP'?'up':'down'];const book=s.odds.quotes?.[side];
  return quotesFresh&&Number.isFinite(price)&&price>0&&price<=1&&(s.mode==='demo'||!!book&&fresh(book.timestamp,now))?price:null;
 };
 return {cycle,sameCycle,btcFresh,modelFresh,identity,quotesFresh,remaining:cycle+300-now,
  reference:btcFresh?s.reference:null,price:btcFresh?s.price:null,
  delta:btcFresh?s.price-s.reference:null,deltaPct:btcFresh?(s.price/s.reference-1)*100:null,
  up:quote('UP'),down:quote('DOWN'),pUp:modelFresh?s.probability:null,pDown:modelFresh?1-s.probability:null};
}
export function payoff(stake:number,ask:number|null,rate:number|undefined,size:number|undefined){
 if(!Number.isFinite(stake)||stake<=0||ask===null||!Number.isFinite(ask)||ask<=0||ask>1||rate===undefined||!Number.isFinite(rate)||rate<0)return null;
 const cost=ask*(1+rate*(1-ask));const tokens=stake/cost;
 return {tokens,fee:tokens*rate*ask*(1-ask),win:tokens-stake,loss:stake,depthEnough:size!==undefined&&Number.isFinite(size)&&size>=tokens};
}
