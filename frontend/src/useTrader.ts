import {useEffect,useState} from 'react';
import type {State} from './types';

/** Own the socket lifecycle independently of dashboard rendering. */
export function useTrader() {
  const [s,setS]=useState<State|null>(null);
  const [connected,setConnected]=useState(false);

  useEffect(()=>{
    let socket:WebSocket;
    let timer:ReturnType<typeof setTimeout>;
    let disposed=false;
    function connect() {
      socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws`);
      socket.onopen=()=>setConnected(true);
      socket.onmessage=e=>{
        const data=JSON.parse(e.data);
        if(data.account&&data.validator)setS(data);
      };
      socket.onclose=()=>{
        setConnected(false);
        if(!disposed)timer=setTimeout(connect,2000);
      };
    }
    connect();
    return ()=>{
      disposed=true;
      clearTimeout(timer);
      socket?.close();
    };
  },[]);

  return {s,setS,connected};
}
