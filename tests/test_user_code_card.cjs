const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const elements = new Map();
function element() { return {value: '', textContent: '', disabled: false, addEventListener() {}}; }
let Card;
class FakeElement {
  attachShadow() { this.shadowRoot = {innerHTML: '', querySelector(selector) { if (!elements.has(selector)) elements.set(selector, element()); return elements.get(selector); }}; }
  dispatchEvent(event) { this.lastEvent = event; }
}
const context = vm.createContext({HTMLElement: FakeElement, customElements: {get: () => null, define: (_name, klass) => {Card = klass;}}, window: {confirm: () => true}, CustomEvent: class {constructor(type, props) {this.type = type; this.detail = props.detail;}}, console});
vm.runInContext(fs.readFileSync('www/jablotron-user-code-card.js', 'utf8'), context);
const pause = () => new Promise(resolve => setImmediate(resolve));
(async () => {
 const card = new Card();
 const requests = [];
 const hass = {user: {id: 'alice'}, states: {'alarm_control_panel.oasis': {state: 'armed_home'}},
  callWS: async msg => {requests.push(msg); return msg.type.endsWith('status') ? {saved: false} : {sent: true};},
  callApi: async (...args) => {requests.push(args); return {saved: true};}};
 card.setConfig({entity: 'alarm_control_panel.oasis'}); card.hass = hass; await pause();
 card._input.value = '0123'; await card._save();
 assert.equal(card._input.value, '');
 assert.equal(card._saved, true);
 assert.equal(JSON.stringify(card._config).includes('0123'), false);
 await card._disarm();
 const disarm = requests.find(x => x.type?.endsWith('/disarm'));
 assert.equal(Object.hasOwn(disarm, 'code'), false);
 assert.equal(Object.hasOwn(disarm, 'user_id'), false);
 hass.callApi = async () => {throw {message: 'Zápis se nezdařil.'};};
 card._input.value = '5678'; await card._save();
 assert.equal(card._input.value, '');
 card._input.value = '3456'; card.disconnectedCallback(); assert.equal(card._input.value, '');
 // An old account's delayed response must never mark the new account as saved.
 let finish;
 hass.callApi = () => new Promise(resolve => {finish = resolve;});
 card._input.value = '0123'; const saving = card._save();
 const bob = {...hass, user: {id: 'bob'}}; card.hass = bob; await pause();
 assert.equal(card._input.value, '');
 finish({saved: true}); await saving;
 assert.equal(card._saved, false);
 assert.equal(card._message.textContent, '');
 card._manual(); assert.equal(card.lastEvent.type, 'hass-more-info');
 assert.equal(card.lastEvent.detail.entityId, 'alarm_control_panel.oasis');
 console.log('Frontend: secret-free disarm, cleared inputs, account-switch isolation and manual fallback verified.');
})().catch(err => {console.error(err); process.exitCode = 1;});
