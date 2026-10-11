/* Jablotron 80: account-scoped code management. No credential in card config/state. */
class JablotronUserCodeCard extends HTMLElement {
  setConfig(config) {
    if (typeof config.entity !== 'string' || !config.entity.startsWith('alarm_control_panel.')) {
      throw new Error('Nastav entity na alarm Jablotronu.');
    }
    const changed = this._config?.entity !== config.entity;
    this._config = {entity: config.entity};
    if (!this.shadowRoot) this.attachShadow({mode: 'open'});
    if (!this._built) this._build();
    if (changed) { this._saved = null; this._account = null; }
    this._update();
  }
  set hass(hass) {
    this._hass = hass;
    const account = hass.user?.id;
    if (account && this._config && account !== this._account) {
      this._account = account;
      this._saved = null;
      this._input.value = '';
      this._message.textContent = '';
      this.shadowRoot.querySelector('#save-message').textContent = '';
      this._load(account);
    }
    this._update();
  }
  getCardSize() { return 3; }
  disconnectedCallback() { if (this._input) this._input.value = ''; }
  _build() {
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding: 16px; }
        h3 { margin: 0 0 12px; font-size: 18px; font-weight: 500; }
        button { font: inherit; cursor: pointer; border: 0; border-radius: 12px; padding: 12px 16px; }
        button:focus-visible, input:focus-visible { outline: 3px solid var(--primary-color); outline-offset: 2px; }
        button:disabled { opacity: .5; cursor: default; }
        #disarm { background: var(--primary-color); color: var(--text-primary-color, white); width: 100%; }
        #status, #message, p { font-size: 13px; color: var(--secondary-text-color); line-height: 1.5; }
        #message:empty { display: none; }
        summary { cursor: pointer; margin-top: 14px; }
        label { display: block; margin: 12px 0 6px; }
        input { box-sizing: border-box; width: 100%; background: var(--card-background-color); color: var(--primary-text-color); border: 1px solid var(--divider-color); padding: 12px; border-radius: 8px; font: inherit; }
        .actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .actions button { background: var(--secondary-background-color); color: var(--primary-text-color); }
        #remove { color: var(--error-color); }
      </style>
      <ha-card>
        <h3>Odjištění Jablotronu</h3>
        <p id="status"></p>
        <button id="disarm" type="button" disabled>Odjistit</button>
        <p id="message" role="status" aria-live="polite"></p>
        <details id="personal">
          <summary>Můj osobní kód Jablotronu</summary>
          <p>Zadej svůj existující kód ústředny. Uložení nemění kód v Jablotronu; přiřadí jej pouze k právě přihlášenému účtu HA.</p>
          <form autocomplete="off">
            <label for="pin">Můj kód pro odjištění (4 číslice)</label>
            <input id="pin" type="password" inputmode="numeric" pattern="[0-9]{4}" minlength="4" maxlength="4" autocomplete="off" required />
            <div class="actions">
              <button id="save" type="submit">Uložit můj kód</button>
              <button id="remove" type="button" disabled>Zapomenout můj kód</button>
              <button id="manual" type="button">Odjistit zadáním kódu</button>
            </div>
            <p id="save-message" role="status" aria-live="polite"></p>
          </form>
          <p>Uložený kód se nezobrazuje. Platnost se ověří až při odjištění. Kód je v chráněném souboru na serveru, přístupném správci serveru a v zálohách.</p>
        </details>
      </ha-card>`;
    const root = this.shadowRoot;
    this._input = root.querySelector('#pin');
    this._message = root.querySelector('#message');
    root.querySelector('form').addEventListener('submit', e => { e.preventDefault(); this._save(); });
    root.querySelector('#disarm').addEventListener('click', () => this._disarm());
    root.querySelector('#manual').addEventListener('click', () => this._manual());
    root.querySelector('#remove').addEventListener('click', () => this._remove());
    root.querySelector('summary').addEventListener('click', () => this._load(this._account));
    this._built = true;
  }
  _error(err) { this._message.textContent = typeof err?.message === 'string' ? err.message : 'Operace se nezdařila.'; this.shadowRoot.querySelector('#save-message').textContent = this._message.textContent; }
  async _load(account) {
    if (!account || !this._hass) return;
    try {
      const result = await this._hass.callWS({type: 'jablotron80/user_code/status', entity_id: this._config.entity});
      if (account === this._account) { this._saved = result.saved; this._mode = result.mode || 'personal'; this._automatic = result.automatic ?? result.saved; this._update(); }
    } catch (err) { if (account === this._account) { this._saved = null; this._error(err); this._update(); } }
  }
  _update() {
    if (!this._built || !this._hass || !this._config) return;
    const state = this._hass.states[this._config.entity]?.state;
    const common = this._mode === 'common';
    this.shadowRoot.querySelector('#personal').hidden = common;
    const automatic = common ? this._automatic : this._saved;
    this.shadowRoot.querySelector('#status').textContent = this._saved === null ? 'Ověřuji osobní nastavení…' : this._saved ? 'Můj kód je uložený. Odjištění nevyžaduje jeho opakované zadání.' : 'Nemáš uložený kód. Odjištění bude s ručním PINem.';
    const button = this.shadowRoot.querySelector('#disarm');
    if (common) this.shadowRoot.querySelector('#status').textContent = automatic ? 'Používá se společný kód nastavený správcem.' : 'Společný režim vyžaduje zadání kódu při odjištění.';
    button.textContent = state === 'disarmed' ? 'Již odjištěno' : automatic ? (common ? 'Odjistit společným kódem' : 'Odjistit mým kódem') : 'Odjistit zadáním kódu';
    button.disabled = this._busy || this._saved === null || !['armed_home', 'armed_night', 'armed_away', 'arming', 'pending', 'triggered'].includes(state);
    this.shadowRoot.querySelector('#save').disabled = !!this._busy;
    this.shadowRoot.querySelector('#remove').disabled = this._busy || this._saved !== true;
  }
  async _save() {
    if (this._busy) return;
    const account = this._account;
    const code = this._input.value;
    if (!/^[0-9]{4}$/.test(code)) { this._message.textContent = 'Kód musí mít přesně čtyři číslice.'; return; }
    this._busy = true; this._update();
    try {
      await this._hass.callApi('POST', 'jablotron80/user_code', {entity_id: this._config.entity, operation: 'save', code});
      if (account !== this._account) return;
      this._saved = true;
      this._message.textContent = 'Tvůj kód je uložený. Ústředně zatím nebyl odeslán.';
      this.shadowRoot.querySelector('#save-message').textContent = this._message.textContent;
    } catch (err) { if (account === this._account) this._error(err); }
    finally { this._input.value = ''; this._busy = false; this._update(); }
  }
  async _remove() {
    if (this._busy || !window.confirm('Zapomenout tvůj uložený kód? Další odjištění bude vyžadovat ruční PIN.')) return;
    const account = this._account;
    this._busy = true; this._update();
    try {
      await this._hass.callApi('POST', 'jablotron80/user_code', {entity_id: this._config.entity, operation: 'remove'});
      if (account !== this._account) return;
      this._saved = false; this._input.value = ''; this._message.textContent = 'Tvůj uložený kód byl odstraněn.';
    } catch (err) { if (account === this._account) this._error(err); }
    finally { this._busy = false; this._update(); }
  }
  _manual() {
    this.dispatchEvent(new CustomEvent('hass-more-info', {bubbles: true, composed: true, detail: {entityId: this._config.entity}}));
  }
  async _disarm() {
    if (this._busy) return;
    if (!(this._mode === 'common' ? this._automatic : this._saved)) { this._manual(); return; }
    this._busy = true; this._update();
    try {
      const result = await this._hass.callWS({type: 'jablotron80/user_code/disarm', entity_id: this._config.entity});
      this._message.textContent = result.sent ? 'Požadavek na odjištění byl odeslán. Ověř stav zón.' : 'Alarm už je odjištěný nebo se odjišťuje.';
    } catch (err) { this._error(err); }
    finally { this._busy = false; this._update(); }
  }
}
if (!customElements.get('jablotron-user-code-card')) customElements.define('jablotron-user-code-card', JablotronUserCodeCard);
