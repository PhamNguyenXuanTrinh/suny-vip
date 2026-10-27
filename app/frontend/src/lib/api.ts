import {create} from 'zustand';
export type Row=Record<string,any>;
type Session={access:string|null;refresh:string|null;profile:Row|null;set:(tokens:Row)=>void;clear:()=>void;setProfile:(p:Row)=>void};
export const useSession=create<Session>((set)=>({access:sessionStorage.getItem('sunny_access'),refresh:sessionStorage.getItem('sunny_refresh'),profile:null,set:(tokens)=>{sessionStorage.setItem('sunny_access',tokens.access_token);sessionStorage.setItem('sunny_refresh',tokens.refresh_token);set({access:tokens.access_token,refresh:tokens.refresh_token,profile:null})},clear:()=>{sessionStorage.removeItem('sunny_access');sessionStorage.removeItem('sunny_refresh');set({access:null,refresh:null,profile:null})},setProfile:(profile)=>set({profile})}));
export class ApiError extends Error {constructor(message:string,public status:number,public fields:Row[]=[]){super(message)}}
let refreshing:Promise<void>|null=null;
export async function request(path:string,options:RequestInit={},retried=false):Promise<Response>{
  const state=useSession.getState();const headers=new Headers(options.headers);
  if(state.access)headers.set('Authorization','Bearer '+state.access);
  if(options.body&&!(options.body instanceof FormData))headers.set('Content-Type','application/json');
  let response=await fetch(path,{...options,headers});
  if(response.status===401&&state.refresh&&!retried&&!path.startsWith('/api/v1/auth/')){
    if(!refreshing)refreshing=(async()=>{const r=await fetch('/api/v1/auth/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({refresh_token:state.refresh})});if(!r.ok){if(useSession.getState().refresh===state.refresh)useSession.getState().clear();throw new ApiError('Phiên đăng nhập đã hết hạn',401)}const tokens=await r.json();if(useSession.getState().refresh!==state.refresh||useSession.getState().access!==state.access)throw new ApiError('Phiên đăng nhập đã thay đổi',401);useSession.getState().set(tokens)})().finally(()=>{refreshing=null});
    await refreshing;return request(path,options,true);
  }
  if(!response.ok){let data:Row={};try{data=await response.json()}catch{}if(response.status===401&&!path.endsWith('/login'))useSession.getState().clear();throw new ApiError(data.error?.message||'Không xử lý được yêu cầu',response.status,data.error?.fields||[])}
  return response;
}
export async function api(path:string,options:RequestInit={}):Promise<any>{return (await request(path,options)).json()}
export const formatMoney=(n:any)=>new Intl.NumberFormat('vi-VN',{style:'currency',currency:'VND',maximumFractionDigits:0}).format(Number(n||0));
export const formatQuantity=(n:any)=>new Intl.NumberFormat('vi-VN',{maximumFractionDigits:6}).format(Number(n||0));
export function dateLabel(s:any){if(!s)return '—';try{return new Intl.DateTimeFormat('vi-VN',{dateStyle:'short',...(String(s).includes('T')?{timeStyle:'short' as const}:{})}).format(new Date(s))}catch{return String(s)}}
