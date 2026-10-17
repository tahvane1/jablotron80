/* Optional local UI. PINs are never put in card config, entities or browser storage. */
const TEXT = {
  en: {
    manage: 'My Jablotron code', control: 'Disarm Jablotron',
    intro: 'Save an existing panel PIN for your signed-in Home Assistant account. This does not program or validate a code in the panel.',
    label: 'My panel PIN (4 digits)', save: 'Save my code', remove: 'Forget my code',
    refresh: 'Refresh', checking: 'Checking account settings…', saved: 'Your code is saved.',
    missing: 'No code saved for this account.', common: 'Personal codes are disabled in integration options.',
    encrypted: 'Codes are stored encrypted. The panel checks validity only when disarming.',
    plaintext: 'Codes are stored without encryption in a private HA file accessible to the server administrator and backups.',
    stored: 'Code saved. Nothing was sent to the panel.', removed: 'Saved code removed.',
    invalid: 'Enter exactly four digits.', error: 'Operation failed. Check your permissions, integration settings and code storage, then refresh.',
    confirm: 'Forget your saved code? Disarming will require manual entry.',
    disarm: 'Disarm with my code', commonDisarm: 'Disarm with common code', manual: 'Enter PIN manually',
    sent: 'Disarm request submitted. Check the alarm state.', idle: 'Already disarmed or disarming.',
    commonAutomatic: 'Using the common code configured by the administrator.',
    commonManual: 'Common mode requires manual PIN entry.', config: 'Select a Jablotron alarm_control_panel entity.'
  },
  cs: {
    manage: 'Můj kód Jablotronu', control: 'Odjištění Jablotronu',
    intro: 'Ulož existující PIN ústředny pro svůj přihlášený účet Home Assistant. Uložení kód v ústředně nemění ani neověřuje.',
    label: 'Můj PIN ústředny (4 číslice)', save: 'Uložit můj kód', remove: 'Zapomenout můj kód',
    refresh: 'Obnovit', checking: 'Ověřuji nastavení účtu…', saved: 'Tvůj kód je uložený.',
    missing: 'Tento účet nemá uložený kód.', common: 'Osobní kódy jsou v nastavení integrace vypnuté.',
    encrypted: 'Kódy se ukládají šifrovaně. Platnost ústředna ověří až při odjištění.',
    plaintext: 'Kódy se ukládají bez šifrování do chráněného souboru HA dostupného správci serveru a v zálohách.',
    stored: 'Kód je uložený. Ústředně nebyl odeslán.', removed: 'Uložený kód byl odstraněn.',
    invalid: 'Zadej přesně čtyři číslice.', error: 'Operace se nezdařila. Zkontroluj oprávnění, nastavení integrace a úložiště kódů a obnov stav.',
    confirm: 'Zapomenout tvůj uložený kód? Odjištění bude vyžadovat ruční zadání.',
    disarm: 'Odjistit mým kódem', commonDisarm: 'Odjistit společným kódem', manual: 'Zadat PIN ručně',
    sent: 'Požadavek na odjištění byl odeslán. Ověř stav alarmu.', idle: 'Alarm je již odjištěný nebo se odjišťuje.',
    commonAutomatic: 'Používá se společný kód nastavený správcem.',
    commonManual: 'Společný režim vyžaduje ruční zadání PINu.', config: 'Vyber alarmovou entitu Jablotronu z domény alarm_control_panel.'
  },
  fr: {
    manage: 'Mon code Jablotron', control: 'Désarmer Jablotron',
    intro: 'Enregistrez un code existant de la centrale pour votre compte Home Assistant connecté. Cela ne programme ni ne valide le code dans la centrale.',
    label: 'Mon code de la centrale (4 chiffres)', save: 'Enregistrer mon code', remove: 'Oublier mon code',
    refresh: 'Actualiser', checking: 'Vérification du compte…', saved: 'Votre code est enregistré.',
    missing: 'Aucun code enregistré pour ce compte.', common: 'Les codes personnels sont désactivés dans les options de l’intégration.',
    encrypted: 'Les codes sont stockés chiffrés. La centrale vérifie leur validité lors du désarmement.',
    plaintext: 'Les codes sont stockés sans chiffrement dans un fichier privé HA accessible à l’administrateur du serveur et dans les sauvegardes.',
    stored: 'Code enregistré. Rien n’a été envoyé à la centrale.', removed: 'Code enregistré supprimé.',
    invalid: 'Saisissez exactement quatre chiffres.', error: 'Échec de l’opération. Vérifiez vos droits, les options et le stockage des codes, puis actualisez.',
    confirm: 'Oublier votre code enregistré ? Le désarmement nécessitera une saisie manuelle.',
    disarm: 'Désarmer avec mon code', commonDisarm: 'Désarmer avec le code commun', manual: 'Saisir le code manuellement',
    sent: 'Demande de désarmement envoyée. Vérifiez l’état de l’alarme.', idle: 'Alarme déjà désarmée ou en cours de désarmement.',
    commonAutomatic: 'Utilisation du code commun configuré par l’administrateur.',
    commonManual: 'Le mode commun nécessite la saisie manuelle du code.', config: 'Sélectionnez une entité alarm_control_panel Jablotron.'
  }
};

class JablotronAccountCard extends HTMLElement {
  constructor(management) {
    super(); this._management = management; this._revision = 0; this._changeSource = Symbol();
    this._onCodeChanged = event => {
      if (event.detail?.source === this._changeSource) return;
      if (event.detail?.entity === this._config?.entity && event.detail?.account === this._hass?.user?.id) {
        if (this._busy) this._refreshPending = true;
        else this._load();
      }
    };
  }
  _t(key) { return (TEXT[this._hass?.language?.split('-')[0]] || TEXT.en)[key]; }
  setConfig(config) {
    if (typeof config?.entity !== 'string' || !config.entity.startsWith('alarm_control_panel.')) throw new Error(this._t('config'));
    const changed = this._config?.entity !== config.entity;
    this._config = {entity: config.entity};
    if (!this.shadowRoot) this.attachShadow({mode: 'open'});
    if (!this._built) this._build();
    if (changed) this._reset();
    if (this._hass?.user?.id && !this._loaded) { this._loaded = true; this._load(); }
    this._update();
  }
  set hass(hass) {
    const changed = this._hass?.user?.id !== hass.user?.id || this._hass?.connection !== hass.connection;
    this._hass = hass;
    if (changed) this._reset();
    if (this._config && hass.user?.id && !this._loaded) { this._loaded = true; this._load(); }
    this._update();
  }
  getCardSize() { return this._management ? 4 : 2; }
  disconnectedCallback() { window.removeEventListener('jablotron-user-code-changed', this._onCodeChanged); this._reset(); }
  connectedCallback() {
    window.addEventListener('jablotron-user-code-changed', this._onCodeChanged);
    if (this._built && this._hass?.user?.id && !this._loaded) { this._loaded = true; this._load(); }
  }
  _reset() {
    this._revision++; this._refreshPending = false; this._loaded = false; this._busy = false; this._saved = null;
    this._mode = null; this._encrypted = null; this._automatic = false; this._notice = null;
    if (this._input) this._input.value = '';
    this._update();
  }
  _build() {
    this.shadowRoot.innerHTML = `
      <style>
        ha-card { padding:16px; } h3 { margin:0 0 12px; font-size:18px; font-weight:500; }
        p { font-size:13px; color:var(--secondary-text-color); line-height:1.5; }
        button,input { font:inherit; border-radius:8px; padding:12px; }
        button { cursor:pointer; border:0; background:var(--secondary-background-color); color:var(--primary-text-color); }
        button:disabled { opacity:.5; cursor:default; } [hidden] { display:none !important; }
        button:focus-visible,input:focus-visible { outline:3px solid var(--primary-color); outline-offset:2px; }
        input { box-sizing:border-box; width:100%; background:var(--card-background-color); color:var(--primary-text-color); border:1px solid var(--divider-color); }
        label { display:block; margin:12px 0 6px; } .actions { display:flex; flex-wrap:wrap; gap:8px; margin-top:12px; }
        #message:empty { display:none; } #remove { color:var(--error-color); }
      </style>
      <ha-card><h3 id="title"></h3><p id="status" role="status" aria-live="polite"></p>
      ${this._management ? `<p id="intro"></p><form autocomplete="off" novalidate>
        <label id="label" for="pin"></label>
        <input id="pin" type="password" inputmode="numeric" pattern="[0-9]{4}" minlength="4" maxlength="4" autocomplete="off" required />
        <div class="actions"><button id="save" type="submit"></button><button id="remove" type="button"></button></div>
      </form><p id="storage"></p>` : '<div class="actions"><button id="disarm" type="button"></button><button id="manual" type="button"></button></div>'}
      <p id="message" role="status" aria-live="polite"></p><button id="refresh" type="button"></button></ha-card>`;
    this._input = this.shadowRoot.querySelector('#pin');
    const on = (id, fn) => this.shadowRoot.querySelector(id)?.addEventListener('click', fn);
    this.shadowRoot.querySelector('form')?.addEventListener('submit', e => { e.preventDefault(); this._save(); });
    on('#remove', () => this._remove()); on('#disarm', () => this._disarm());
    on('#manual', () => this._manual()); on('#refresh', () => this._load());
    this._built = true;
  }
  _update() {
    if (!this._built) return;
    const set = (id, text) => { const el = this.shadowRoot.querySelector(id); if (el) el.textContent = text; };
    const ready = this._saved !== null && !!this._hass?.user?.id;
    const personal = this._mode === 'personal';
    set('#title', this._t(this._management ? 'manage' : 'control'));
    set('#status', this._t(!ready ? 'checking' : this._management && !personal ? 'common' :
      !personal ? (this._automatic ? 'commonAutomatic' : 'commonManual') : this._saved ? 'saved' : 'missing'));
    set('#message', this._notice ? this._t(this._notice) : ''); set('#refresh', this._t('refresh'));
    this.shadowRoot.querySelector('#refresh').disabled = this._busy || !this._hass?.user?.id;
    if (this._management) {
      for (const key of ['intro', 'label', 'save', 'remove']) set('#' + key, this._t(key));
      set('#storage', ready ? this._t(this._encrypted ? 'encrypted' : 'plaintext') : '');
      this.shadowRoot.querySelector('form').hidden = !ready || !personal;
      this._input.disabled = !ready || !personal || this._busy;
      this.shadowRoot.querySelector('#save').disabled = !ready || !personal || this._busy;
      this.shadowRoot.querySelector('#remove').disabled = !ready || !personal || this._busy || !this._saved;
    } else {
      const automatic = personal ? this._saved : this._automatic;
      const state = this._hass?.states?.[this._config?.entity]?.state;
      set('#disarm', this._t(automatic ? (personal ? 'disarm' : 'commonDisarm') : 'manual'));
      set('#manual', this._t('manual'));
      const disabled = !ready || this._busy || !['armed_home', 'armed_night', 'armed_away', 'arming', 'pending', 'triggered'].includes(state);
      this.shadowRoot.querySelector('#disarm').disabled = disabled;
      this.shadowRoot.querySelector('#manual').disabled = disabled;
      this.shadowRoot.querySelector('#manual').hidden = !automatic;
    }
  }
  async _load() {
    if (!this._config || !this._hass?.user?.id || this._busy) return;
    const revision = this._revision, hass = this._hass, entity = this._config.entity;
    this._busy = true; this._notice = null; this._update();
    try {
      const result = await hass.callWS({type:'jablotron80/user_code/status', entity_id:entity});
      if (revision !== this._revision) return;
      this._saved = !!result.saved; this._mode = result.mode; this._automatic = !!result.automatic; this._encrypted = !!result.encrypted;
    } catch {
      if (revision === this._revision) { this._saved = null; this._notice = 'error'; }
    } finally {
      this._finish(revision);
    }
  }
  async _write(operation, code) {
    const revision = this._revision, hass = this._hass;
    const body = {entity_id:this._config.entity, operation};
    if (operation === 'save') body.code = code;
    this._busy = true; this._notice = null; this._update();
    try {
      await hass.callApi('POST', 'jablotron80/user_code', body);
      if (revision !== this._revision) return;
      this._saved = operation === 'save'; this._notice = operation === 'save' ? 'stored' : 'removed';
      window.dispatchEvent(new CustomEvent('jablotron-user-code-changed', {detail:{entity:body.entity_id, account:hass.user.id, source:this._changeSource}}));
    } catch {
      if (revision === this._revision) this._notice = 'error';
    } finally {
      if (revision === this._revision) this._input.value = '';
      this._finish(revision);
    }
  }
  _finish(revision) {
    if (revision !== this._revision) return;
    this._busy = false; this._update();
    if (this._refreshPending) { this._refreshPending = false; this._load(); }
  }
  async _save() {
    if (this._busy || !this._management || this._mode !== 'personal' || this._saved === null) return;
    const code = this._input.value; this._input.value = '';
    if (!/^[0-9]{4}$/.test(code)) { this._notice = 'invalid'; this._update(); return; }
    await this._write('save', code);
  }
  async _remove() {
    if (this._busy || !this._management || this._mode !== 'personal' || !this._saved || !window.confirm(this._t('confirm'))) return;
    this._input.value = ''; await this._write('remove');
  }
  _manual() {
    this.dispatchEvent(new CustomEvent('hass-more-info', {bubbles:true, composed:true, detail:{entityId:this._config.entity}}));
  }
  async _disarm() {
    if (this._management || this._busy || this._saved === null || !this._hass?.user?.id) return;
    if (!(this._mode === 'personal' ? this._saved : this._automatic)) { this._manual(); return; }
    const revision = this._revision, hass = this._hass, entity = this._config.entity;
    this._busy = true; this._notice = null; this._update();
    try {
      const result = await hass.callWS({type:'jablotron80/user_code/disarm', entity_id:entity});
      if (revision === this._revision) this._notice = result.sent ? 'sent' : 'idle';
    } catch {
      if (revision === this._revision) this._notice = 'error';
    } finally {
      this._finish(revision);
    }
  }
}
class JablotronUserCodeCard extends JablotronAccountCard { constructor() { super(true); } }
class JablotronDisarmCard extends JablotronAccountCard { constructor() { super(false); } }
if (!customElements.get('jablotron-user-code-card')) customElements.define('jablotron-user-code-card', JablotronUserCodeCard);
if (!customElements.get('jablotron-disarm-card')) customElements.define('jablotron-disarm-card', JablotronDisarmCard);
