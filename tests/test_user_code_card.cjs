const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const classes = new Map();
const listeners = new Set();
const browserWindow = {confirm:()=>true,addEventListener:(_name,fn)=>listeners.add(fn),removeEventListener:(_name,fn)=>listeners.delete(fn),dispatchEvent:event=>{for(const fn of listeners)fn(event);}};
function element() { return {value:'', textContent:'', disabled:false, hidden:false, addEventListener(){}}; }
class FakeElement {
  attachShadow() {
    const nodes = new Map();
    this.shadowRoot = {innerHTML:'', querySelector(selector) {
      const management = this.innerHTML.includes('<form');
      if ((['#pin','form','#intro','#label','#save','#remove','#storage'].includes(selector) && !management) ||
          (['#disarm','#manual'].includes(selector) && management)) return null;
      if (!nodes.has(selector)) nodes.set(selector,element());
      return nodes.get(selector);
    }};
  }
  dispatchEvent(event) { this.lastEvent=event; }
}
vm.runInNewContext(fs.readFileSync('custom_components/jablotron80/frontend/jablotron-user-code-card.js','utf8'), {
  HTMLElement:FakeElement, customElements:{get:n=>classes.get(n),define:(n,k)=>classes.set(n,k)},
  window:browserWindow, CustomEvent:class { constructor(type,props){this.type=type;this.detail=props.detail;} }
});
const pause=()=>new Promise(resolve=>setImmediate(resolve));
const ALARM='alarm_control_panel.oasis';
function client(id='alice') {
  return {user:{id},connection:{},language:'en',states:{[ALARM]:{state:'armed_home'}},
    callWS:async ()=>({saved:false,mode:'personal',encrypted:true}),callApi:async ()=>({saved:true})};
}
function card(type,hass) { const c=new (classes.get(type))();c.setConfig({entity:ALARM});c.hass=hass;return c; }
(async ()=>{
  const hass=client(), requests=[];
  hass.callApi=async (...args)=>{requests.push(args);return {saved:true};};
  const manage=card('jablotron-user-code-card',hass); await pause();
  assert.equal(manage.shadowRoot.querySelector('#disarm'),null);
  assert.equal(manage.shadowRoot.querySelector('#title').textContent,'My Jablotron code');
  manage._input.value='0123';const save=manage._save();assert.equal(manage._input.value,'');await save;
  assert.equal(manage._saved,true);assert.equal(manage._notice,'stored');
  assert.equal(JSON.stringify(requests[0]),JSON.stringify(['POST','jablotron80/user_code',{entity_id:ALARM,operation:'save',code:'0123'}]));
  assert.equal(JSON.stringify(manage._config).includes('0123'),false);
  await manage._remove();assert.equal(manage._saved,false);
  assert.equal(Object.hasOwn(requests[1][2],'code'),false);
  hass.callApi=async ()=>{throw {message:'secret 0123'};};
  manage._input.value='0123';await manage._save();assert.equal(manage._input.value,'');
  assert.equal(manage.shadowRoot.querySelector('#message').textContent.includes('0123'),false);
  manage._input.value='12';await manage._save();assert.equal(manage._notice,'invalid');assert.equal(manage._input.value,'');
  // Delayed results must not affect another account or entity, even after switching back.
  let finish;hass.callApi=()=>new Promise(resolve=>{finish=resolve;});
  manage._input.value='0123';const oldSave=manage._save();
  manage.hass=client('bob');await pause();manage.hass=hass;await pause();
  finish({saved:true});await oldSave;assert.equal(manage._saved,false);assert.equal(manage._notice,null);
  let status;const delayed=client();delayed.callWS=()=>new Promise(resolve=>{status=resolve;});
  manage.hass=delayed;const oldStatus=status;manage.setConfig({entity:'alarm_control_panel.other'});
  oldStatus({saved:true,mode:'personal'});await pause();assert.equal(manage._saved,null);
  manage.hass=client();await pause();manage._input.value='0123';manage.hass={...client(),user:null};
  assert.equal(manage._input.value,'');assert.equal(manage._saved,null);
  const cs=client();cs.language='cs-CZ';manage.hass=cs;await pause();
  assert.equal(manage.shadowRoot.querySelector('#title').textContent,'Můj kód Jablotronu');
  const common=client();common.callWS=async ()=>({saved:true,mode:'common',encrypted:true});manage.hass=common;await pause();
  assert.equal(manage.shadowRoot.querySelector('form').hidden,true);
  const controlRequests=[],ctrl=client();ctrl.callWS=async msg=>{controlRequests.push(msg);return msg.type.endsWith('status')?{saved:true,mode:'personal',encrypted:true}:{sent:true};};
  const control=card('jablotron-disarm-card',ctrl);await pause();
  assert.equal(control.shadowRoot.querySelector('#pin'),null);
  await control._disarm();const disarm=controlRequests.find(m=>m.type.endsWith('/disarm'));
  assert.deepEqual(Object.keys(disarm).sort(),['entity_id','type']);assert.equal(control._notice,'sent');
  ctrl.callWS=async ()=>({saved:false,mode:'personal'});await control._load();await control._disarm();
  assert.equal(control.lastEvent.type,'hass-more-info');assert.equal(control.lastEvent.detail.entityId,ALARM);
  // A completion from the previous account cannot show a success to the new account.
  ctrl.callWS=async ()=>({saved:true,mode:'personal'});await control._load();
  ctrl.callWS=()=>new Promise(resolve=>{finish=resolve;});const sending=control._disarm();
  control.hass=client('bob');await pause();finish({sent:true});await sending;assert.equal(control._notice,null);
  let stored=false;const shared=client();shared.callWS=async ()=>({saved:stored,mode:'personal',encrypted:true});
  shared.callApi=async (_method,_path,body)=>{stored=body.operation==='save';return {saved:stored};};
  const editor=card('jablotron-user-code-card',shared),button=card('jablotron-disarm-card',shared);
  editor.connectedCallback();button.connectedCallback();await pause();
  editor._input.value='0123';await editor._save();await pause();assert.equal(button._saved,true);
  await editor._remove();await pause();assert.equal(button._saved,false);
  editor.disconnectedCallback();button.disconnectedCallback();assert.equal(listeners.size,0);
  // A credential change during a pending status read must queue a fresh read.
  editor.connectedCallback();await pause();
  const observer=card('jablotron-disarm-card',shared);observer.connectedCallback();await pause();
  let completeStatus;let first=true;
  shared.callWS=async ()=>first?(first=false,await new Promise(resolve=>{completeStatus=resolve;})):{saved:stored,mode:'personal',encrypted:true};
  const staleRead=observer._load();editor._input.value='0123';await editor._save();
  completeStatus({saved:false,mode:'personal',encrypted:true});await staleRead;await pause();
  assert.equal(observer._saved,true,'credential change during status refresh must not be lost');
  observer.disconnectedCallback();editor.disconnectedCallback();assert.equal(listeners.size,0);
  // Native HTML validation must not prevent our validator from clearing bad input.
  assert.match(manage.shadowRoot.innerHTML,/<form[^>]*novalidate/);
  console.log('Bundled frontend: separated controls, save/remove, PIN clearing, translations, stale-response isolation and secret-free disarm OK.');
})().catch(err=>{console.error(err);process.exitCode=1;});
