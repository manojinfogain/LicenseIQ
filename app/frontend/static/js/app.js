// ─────────── CURRENCY HELPER ────────────────────────────
// All raw cost values are stored in USD cents equivalent (as plain numbers).
// fmt(n) formats a number as $X,XXX
function fmt(n){
  if(n===undefined||n===null)return '$0';
  const rounded=Math.round(Number(n)||0);
  return '$'+rounded.toLocaleString('en-US');
}
function roundCost(n){
  return Math.round(Number(n)||0);
}
function trunc(str,max=15){
  if(!str)return '';
  const s=String(str);
  if(s.length<=max)return s;
  const safe=s.replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  return `<span class="iqtt" data-tip="${safe}">${s.slice(0,max)}&hellip;</span>`;
}
(function(){
  const TT=document.createElement('div');TT.id='iq-tooltip';document.body.appendChild(TT);
  let _tid=null;
  document.addEventListener('mouseover',e=>{
    const el=e.target.closest('.iqtt,[data-tip]');
    if(!el)return;
    clearTimeout(_tid);
    TT.textContent=el.dataset.tip||'';
    TT.style.display='block';
    _tid=setTimeout(()=>TT.style.opacity='1',10);
  });
  document.addEventListener('mousemove',e=>{
    if(TT.style.display==='none')return;
    const x=e.clientX,y=e.clientY;
    const tw=TT.offsetWidth,th=TT.offsetHeight;
    const vw=window.innerWidth,vh=window.innerHeight;
    let left=x+14,top=y-th-10;
    if(left+tw>vw-8)left=x-tw-14;
    if(top<8)top=y+18;
    TT.style.left=left+'px';
    TT.style.top=top+'px';
  });
  document.addEventListener('mouseout',e=>{
    const el=e.target.closest('.iqtt,[data-tip]');
    if(!el)return;
    TT.style.opacity='0';
    clearTimeout(_tid);
    _tid=setTimeout(()=>{TT.style.display='none';},120);
  });
})();
function fmtDateInStr(s){return (s||'').replace(/(\d{4})-(\d{2})-(\d{2})/g,(_,y,m,d)=>d+'/'+m+'/'+y);}
function fmtK(n){if(n===undefined||n===null||n===0)return'$0K';if(n<1000)return'$'+Math.round(n);return '$'+Math.round(n/1000)+'K';}
// ─────────── DATE HELPER ─────────────────────────────────
// Convert YYYY-MM-DD or Date object to DD/MM/YYYY format
function fmtRequestDate(dateInput){
  if(!dateInput) return '';
  const monthNames=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const fromDate=(dateObj)=>{
    if(!(dateObj instanceof Date) || Number.isNaN(dateObj.getTime())) return '';
    const day=String(dateObj.getDate()).padStart(2,'0');
    const mon=monthNames[dateObj.getMonth()];
    const yr=String(dateObj.getFullYear()).slice(-2);
    return `${day}-${mon}-${yr}`;
  };
  if(dateInput instanceof Date) return fromDate(dateInput);
  const raw=String(dateInput).trim();
  if(!raw) return '';

  const isoDateOnly = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if(isoDateOnly){
    const [,y,m,d]=isoDateOnly;
    return `${d}-${monthNames[Number(m)-1]}-${String(y).slice(-2)}`;
  }

  const weirdSlash = raw.match(/^(\d{2})T\d{2}:\d{2}:\d{2}(?:\.\d+)?\/(\d{2})\/(\d{4})$/);
  if(weirdSlash){
    const [,d,m,y]=weirdSlash;
    return `${d}-${monthNames[Number(m)-1]}-${String(y).slice(-2)}`;
  }

  const isoStamp = raw.match(/^(\d{4})-(\d{2})-(\d{2})[T\s].*$/);
  if(isoStamp){
    const [,y,m,d]=isoStamp;
    return `${d}-${monthNames[Number(m)-1]}-${String(y).slice(-2)}`;
  }

  const slashDate = raw.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if(slashDate){
    const [,d,m,y]=slashDate;
    return `${d}-${monthNames[Number(m)-1]}-${String(y).slice(-2)}`;
  }

  return fromDate(new Date(raw)) || raw;
}

function fmtDate(dateInput){
  if(!dateInput)return '';
  if(typeof dateInput==='string'){
    const parts=dateInput.split('-');
    if(parts.length===3)return `${parts[2]}/${parts[1]}/${parts[0]}`;
    return dateInput;
  }
  if(dateInput instanceof Date){
    const d=dateInput.getDate().toString().padStart(2,'0');
    const m=(dateInput.getMonth()+1).toString().padStart(2,'0');
    const y=dateInput.getFullYear();
    return `${d}/${m}/${y}`;
  }
  return '';
}

// ─────────── API INITIALIZATION ─────────────────────────
// API base URL — configure via window.API_BASE if needed, defaults to current origin
// For development: set window.API_BASE before loading this script
const API_BASE = window.API_BASE || (window.location.origin + '/api/v1');

// ─────────── SIDEBAR TOGGLE ──────────────────────────────
function toggleSidebar(){
  const sidebar = document.getElementById('sidebar');
  const hamburger = document.getElementById('hamburger');
  const isCollapsed = sidebar.classList.toggle('collapsed');
  // Expanded = show X (active); Collapsed = show hamburger (not active)
  if(isCollapsed){
    hamburger.classList.remove('active');
    hamburger.dataset.tip = 'Expand';
  } else {
    hamburger.classList.add('active');
    hamburger.dataset.tip = 'Collapse';
  }
  localStorage.setItem('sidebarCollapsed', isCollapsed);
}

// Restore sidebar state from localStorage on page load
function initSidebarState(){
  const sidebar = document.getElementById('sidebar');
  const hamburger = document.getElementById('hamburger');
  const isCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
  if(isCollapsed){
    sidebar.classList.add('collapsed');
    hamburger.classList.remove('active'); // collapsed = hamburger icon
    hamburger.dataset.tip = 'Expand';
  } else {
    hamburger.classList.add('active'); // expanded = X icon
    hamburger.dataset.tip = 'Collapse';
  }
}

async function readApiError(response, fallbackMessage){
  try{
    const contentType=response.headers.get('content-type')||'';
    if(contentType.includes('application/json')){
      const body=await response.json();
      if(typeof licenseiqIsDev==='function'&&licenseiqIsDev()){
        if(body?.detail)return typeof body.detail==='string'?body.detail:fallbackMessage;
        if(body?.message)return body.message;
      }
    }
    return fallbackMessage;
  }catch(e){
    return fallbackMessage;
  }
}

function persistUserSession(data){
  if(!data||typeof data!=='object')return;
  sessionStorage.setItem('licenseiq_session',JSON.stringify({
    role:data.role,
    name:data.name,
    ini:data.ini,
    dept:data.dept,
  }));
  if(data.staffid)sessionStorage.setItem('staffid',String(data.staffid).trim());
}

async function fetchJson(url, options={}, fallbackMessage='Request failed'){
  let response;
  try{
    response=await fetch(url, options);
  }catch(e){
    throw new Error('Network error. Please check the server connection.');
  }
  if(!response.ok){
    throw new Error(await readApiError(response, fallbackMessage));
  }
  if(response.status===204)return null;
  const contentType=response.headers.get('content-type')||'';
  if(!contentType.includes('application/json'))return null;
  try{
    return await response.json();
  }catch(e){
    throw new Error('Server returned an invalid response.');
  }
}

// Global data containers (will be populated from API)
let PLATFORMS = [];
let selectedPlatformManual=null,selectedPlatformRequest=null,selectedEmployeeRequest=null,selectedProjectRequest=null,selectedAccountRequest=null;
let currentEmployeeAccounts=[];
let licExpandedEmployeeId=null,licSelectedLicenseKey='',licenseRegisterContext=null,pendingRequestPrefill=null;
let EMPS = [];
let REQUEST_EMPLOYEES = [];
let FINANCE_EMPS = [];  // Org-level employees for Finance view calculations
let ALERTS = [];
let MANUAL_ALERTS = [];
let SEAT_SNAPSHOTS = {};
let MONTHLY_SPEND = {};
let MONTHLY_PROJ = {};
let FINANCE_MONTHLY_SPEND = {};
let FINANCE_MONTHLY_PROJ = {};
let FINANCE_PROJ_META = {};
let ALLOC_HIST = {};
let PROJ_META = {};
let UNITS = [];
let ACCOUNTS = [];
let PROJECTS = [];
let GDLS = [];
let queue = [];
let currentDashboardData = {};
let LAST_LIVE_SUMMARY = null;

function getCurrentStaffId(){
  const fromSessionStorage = sessionStorage.getItem('staffid');
  const fromSessionObject = currentSessionUser()?.staffid;
  const fromDashboardUser = currentDashboardData?.user?.staffid;
  const staffid = String(fromSessionStorage || fromSessionObject || fromDashboardUser || '').trim();
  if(staffid) sessionStorage.setItem('staffid', staffid);
  return staffid;
}

async function fetchLiveSummary(accountName, gdlCode, projectName){
  const params = new URLSearchParams();
  const staffid = getCurrentStaffId();
  if (staffid) params.set('staffid', staffid);
  if (accountName) params.set('account_name', accountName);
  if (gdlCode)     params.set('gdl_code', gdlCode);
  if (projectName) params.set('project_name', projectName);
  params.set('_t', String(Date.now()));
  const url = `${API_BASE}/dashboard/summary` + (params.toString() ? '?' + params : '');
  const s = await fetchJson(url, { cache: 'no-store' }, 'Failed to load dashboard summary.');
  LAST_LIVE_SUMMARY = s;
  return s;
}

function setSelectOptions(id, label, values){
  const el=document.getElementById(id);
  if(!el)return;
  const current=el.value;
  const counts=new Map();
  (values||[]).filter(Boolean).forEach(v=>{
    const key=String(v);
    counts.set(key,(counts.get(key)||0)+1);
  });
  const items=[...counts.keys()].sort((a,b)=>String(a).localeCompare(String(b)));
  const labelWithCount=`${label}${items.length?` (${items.length})`:''}`;
  el.innerHTML=`<option value="">${labelWithCount}</option>`+items.map(v=>`<option value="${v}">${v} (${counts.get(v)||0})</option>`).join('');
  if(items.includes(current))el.value=current;
}

function populateDataDrivenOptions(){
  const scopedEmps=empsFor(role);
  const scopedLics=scopedEmps.flatMap(e=>currentLicenses(e));
  setSelectOptions('df-account','All accounts',scopedEmps.map(e=>e.acct));
  setSelectOptions('df-gdl','All GDL',scopedEmps.map(e=>e.gdl));
  setSelectOptions('df-proj','All projects',scopedEmps.map(e=>e.proj));
  setSelectOptions('facct','All accounts',scopedEmps.map(e=>e.acct));
  setSelectOptions('fu','All units',scopedEmps.map(e=>e.unit));
  setSelectOptions('psu','All units',scopedEmps.map(e=>e.unit));
  setSelectOptions('psa','All accounts',scopedEmps.map(e=>e.acct));
  setSelectOptions('fp','All platforms',scopedLics.map(l=>l.plat));
  setSelectOptions('pss','— select platform —',scopedLics.map(l=>l.plat));

  const trend=document.getElementById('trend-unit');
  if(trend){
    const current=trend.value;
    const names=PLATFORMS.map(p=>p.name);
    const trendCounts=new Map();
    scopedLics.forEach(l=>{
      const k=String(l.plat);
      trendCounts.set(k,(trendCounts.get(k)||0)+1);
    });
    trend.innerHTML='<option value="total">Total spend</option>'+names.map(name=>`<option value="${name}">${name} (${trendCounts.get(String(name))||0})</option>`).join('');
    if(current && (current==='total' || names.includes(current)))trend.value=current;
  }

  const costView=document.getElementById('cost-view');
  if(costView){
    const current=costView.value;
    const names=PLATFORMS.map(p=>p.name);
    const viewCounts=new Map();
    scopedLics.forEach(l=>{
      const k=String(l.plat);
      viewCounts.set(k,(viewCounts.get(k)||0)+1);
    });
    costView.innerHTML='<option value="all">All platforms</option>'+names.map(name=>`<option value="${name}">${name} (${viewCounts.get(String(name))||0})</option>`).join('');
    if(current && (current==='all' || names.includes(current)))costView.value=current;
  }

  const costYear=document.getElementById('cost-year');
  if(costYear){
    const current=costYear.value;
    const years=Object.keys(MONTHLY_SPEND).sort((a,b)=>Number(b)-Number(a));
    costYear.innerHTML=years.map(year=>`<option value="${year}">${year}</option>`).join('');
    if(current && years.includes(current))costYear.value=current;
    else if(years.length)costYear.value=years[0];
  }
}

async function loadBackendData(forceRefresh=false) {
  try {
    console.log('Loading backend data...');
    const staffid = getCurrentStaffId();
    const useOrgLevelBootstrap = role === 'admin' || role === 'finance';
    let bootstrapUrl = useOrgLevelBootstrap
      ? `${API_BASE}/dashboard/bootstrap?org_level=true`
      : (staffid ? `${API_BASE}/dashboard/bootstrap?staffid=${encodeURIComponent(staffid)}` : `${API_BASE}/dashboard/bootstrap`);
    if(forceRefresh){
      const sep = bootstrapUrl.includes('?') ? '&' : '?';
      bootstrapUrl = `${bootstrapUrl}${sep}_t=${Date.now()}`;
    }
    const response = await fetch(bootstrapUrl, forceRefresh ? {cache:'no-store'} : {});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    currentDashboardData = await response.json();
    
    PLATFORMS = currentDashboardData.platforms || [];
    EMPS = currentDashboardData.employees || [];
    syncLicenseCostsFromPlatforms();
    ALERTS = (currentDashboardData.alerts || [])
      .filter(a => ['exit','bench','project_change'].includes(a.type))
      .map(a => ({
        ...a,
        empName: a.empName || null,
        type: a.type === 'project_change' ? 'project' : a.type,
        reason: cleanSmartAlertText(a.reason),
        detail: cleanSmartAlertText(a.detail),
      }));
    MANUAL_ALERTS = [];
    SEAT_SNAPSHOTS = currentDashboardData.seat_snapshots || {};
    MONTHLY_SPEND = currentDashboardData.monthly_spend || {};
    MONTHLY_PROJ = currentDashboardData.monthly_project || {};
    ALLOC_HIST = currentDashboardData.alloc_hist || {};
    PROJ_META = currentDashboardData.project_meta || {};
    UNITS = currentDashboardData.units || [];
    ACCOUNTS = currentDashboardData.accounts || [];
    PROJECTS = currentDashboardData.projects || [];
    GDLS = currentDashboardData.gdls || [];
    queue = currentDashboardData.queue || [];
    
    // Finance/Admin use the same employee list (costs already synced from Platform master).
    FINANCE_EMPS = EMPS;
    FINANCE_MONTHLY_SPEND = currentDashboardData.monthly_spend || {};
    FINANCE_MONTHLY_PROJ = currentDashboardData.monthly_project || {};
    FINANCE_PROJ_META = currentDashboardData.project_meta || {};

    // Prime summary before first render so analytics KPI starts with live value (no 38X flash)
    try {
      await fetchLiveSummary();
    } catch (summaryError) {
      console.warn('Live summary preload failed:', summaryError);
    }

    populateDataDrivenOptions();
    updateNavBadges();

    console.log('Loaded platforms:', PLATFORMS.length);
    console.log('Loaded employees:', EMPS.length);
    console.log('Loaded alerts:', ALERTS.length);
    return true;
  } catch (e) {
    console.error('Failed to load backend data:', e);
    toast(licenseiqUserError(e,'Failed to load backend data.'),'var(--red)');
    return false;
  }
}

// ─────────── DATA ───────────────────────────────────────
const ROLES={
  admin:  {name:'License Admin',ini:'LA',dept:'IT Dept',desc:'Full access — alerts, queue, search, distribution, platforms, cost, reports.'},
  gdl:    {name:'Rajan Mehta', ini:'RM',dept:'GDL',desc:'All accounts under your GDL. View project-wise consumption. Raise requests.'},
  account:{name:'Sunita Rao',  ini:'SR',dept:'Acct Owner',desc:'Your accounts and projects only. Raise requests.'},
  pm:     {name:'Vikram Joshi',ini:'VJ',dept:'PM',desc:'Your project only. Raise requests for your employees.'},
  finance:{name:'Preethi Das', ini:'PD',dept:'Finance/CFO',desc:'CFO view — monthly spend, trend analysis, distribution, reports. Read only.'},
};

const MONTHS=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];



const NAV_CFG={
  admin:  [{k:'analytics',l:'Analytics'},{k:'alerts',l:'Smart alerts',b:'alerts'},{k:'queue',l:'Action queue',b:'queue'},{k:'search',l:'Search'},{k:'licenses',l:'License register'},{k:'platforms',l:'Platform master'},{k:'reports',l:'Reports & KPIs'}],
  gdl:    [{k:'analytics',l:'Analytics'},{k:'request',l:'Raise request'},{k:'licenses',l:'License register'}],
  account:[{k:'analytics',l:'Analytics'},{k:'approvals',l:'Approvals',b:'approvals'},{k:'request',l:'Raise request'},{k:'licenses',l:'License register'}],
  pm:     [{k:'analytics',l:'Analytics'},{k:'request',l:'Raise request'},{k:'licenses',l:'License register'}],
  finance:[{k:'analytics',l:'Analytics'},{k:'reports',l:'Reports & KPIs'}],
};

const SCOPE={admin:'All units · All accounts · All projects',gdl:'GDL-01 · Alpha Corp, Beta Solutions',account:'Alpha Corp · Proj-Falcon, Proj-Storm',pm:'Proj-Falcon · Alpha Corp',finance:'Read only — cost & distribution'};

const PAGE={
  analytics:{title:'Analytics',sub:'License intelligence — scoped to your access level'},
  dashboard:{title:'Dashboard',sub:'License and cost overview — filtered by account, GDL, project'},
  alerts:{title:'Smart alerts',sub:'HRMS events — Exit · Corporate Pool · Project change'},
  queue:{title:'Action queue',sub:'Approved requests awaiting execution — confirm with requester if needed'},
  approvals:{title:'Pending Approvals',sub:'License requests awaiting your approval'},
  search:{title:'Search',sub:'Find all licenses for an employee, or all employees for a platform'},
  distribution:{title:'Distribution',sub:'License count by unit, account owner, and platform'},
  licenses:{title:'License register',sub:'All licenses with allocation history'},
  request:{title:'Raise a request',sub:'Assign or revoke — self-approved, sent to admin queue'},
  platforms:{title:'Platform master',sub:'Add platforms, define agreement type, cost model and seat history'},
  cost:{title:'Cost analysis',sub:'Monthly spend trends, project aggregates, quarter-wise breakdown'},
  reports:{title:'Reports & KPIs',sub:'Export reports and review performance metrics'},
};

const ICONS={
  analytics:'<rect x="1" y="1" width="6" height="6" rx="1.5" fill="currentColor"/><rect x="9" y="1" width="6" height="6" rx="1.5" fill="currentColor" opacity=".5"/><rect x="1" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".5"/><rect x="9" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".3"/>',
  dashboard:'<rect x="1" y="1" width="6" height="6" rx="1.5" fill="currentColor"/><rect x="9" y="1" width="6" height="6" rx="1.5" fill="currentColor" opacity=".5"/><rect x="1" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".5"/><rect x="9" y="9" width="6" height="6" rx="1.5" fill="currentColor" opacity=".3"/>',
  alerts:'<path d="M8 2a5 5 0 0 0-5 5v2L1.5 11h13L13 9V7a5 5 0 0 0-5-5Z" stroke="currentColor" stroke-width="1.4" fill="none"/><circle cx="11" cy="4" r="2.5" fill="#b6f000"/>',
  queue:'<path d="M2 4h12M2 8h8M2 12h5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="13" cy="11" r="2.5" stroke="currentColor" stroke-width="1.2"/><path d="M11.8 11l.8.8 1.4-1.4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
  approvals:'<path d="M2 4h12M2 8h8M2 12h5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><circle cx="12" cy="5" r="3" stroke="currentColor" stroke-width="1.2"/><path d="M10.8 5l.8.8 1.8-1.8" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
  search:'<circle cx="6.5" cy="6.5" r="4.5" stroke="currentColor" stroke-width="1.5"/><path d="M10 10l3.5 3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
  distribution:'<rect x="1" y="8" width="3" height="7" rx="1" fill="currentColor"/><rect x="6" y="4" width="3" height="11" rx="1" fill="currentColor" opacity=".7"/><rect x="11" y="1" width="3" height="14" rx="1" fill="currentColor" opacity=".4"/>',
  licenses:'<rect x="1" y="2" width="14" height="2.5" rx="1" fill="currentColor"/><rect x="1" y="6.5" width="14" height="2.5" rx="1" fill="currentColor" opacity=".5"/><rect x="1" y="11" width="14" height="2.5" rx="1" fill="currentColor" opacity=".3"/>',
  request:'<circle cx="8" cy="5" r="3" stroke="currentColor" stroke-width="1.5"/><path d="M2 14c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>',
  platforms:'<rect x="1" y="1" width="14" height="9" rx="2" stroke="currentColor" stroke-width="1.5"/><rect x="5" y="12" width="6" height="2" rx="1" fill="currentColor" opacity=".5"/>',
  cost:'<path d="M1 12L5 7l3 3 3-4 3 2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>',
  reports:'<rect x="3" y="1" width="10" height="14" rx="1.5" stroke="currentColor" stroke-width="1.5"/><path d="M6 5h4M6 8h4M6 11h2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>',
};

// ─────────── STATE ──────────────────────────────────────
let role='',myReqs=[],altFilter='all',alertSearchFilter='',expanded={},distTab='unit',srchTab='emp',alertView='sep',editPFid=null;
let approvalHistory=[];
const DISMISSED_ALERTS_KEY='licenseiq_dismissed_alerts';
let dismissedAlertKeys=new Set();
let licSortKey='id',licSortDir='asc';
let licPage=1;
let licPageSize=10;
let notificationCheckInterval=null;
let lastNotificationCheck=0;
let notificationPermissionRequested=false;
const POLL_LOCK_KEY='licenseiq_poll_lock';
const POLL_LOCK_TTL_MS=35000;
const POLL_TAB_ID=`tab_${Math.random().toString(36).slice(2)}`;
let hasPollingLock=false;

// ─────────── NOTIFICATION HELPERS ────────────────────────────────────
// Request browser notification permission
async function requestNotificationPermission(){
  if(notificationPermissionRequested)return;
  if(!('Notification' in window))return;
  if(Notification.permission==='granted'||Notification.permission==='denied')return;
  notificationPermissionRequested=true;
  try{
    const perm=await Notification.requestPermission();
    if(perm==='granted')console.log('Notifications enabled');
  }catch(e){console.log('Notification permission request failed');}
}

// Play notification sound
function playNotificationSound(){
  try{
    const audioContext=new(window.AudioContext||window.webkitAudioContext)();
    const oscillator=audioContext.createOscillator();
    const gainNode=audioContext.createGain();
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    oscillator.frequency.value=800;
    oscillator.type='sine';
    gainNode.gain.setValueAtTime(0.3,audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01,audioContext.currentTime+0.5);
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime+0.5);
  }catch(e){console.log('Audio notification unavailable');}
}

// Send browser notification
function sendBrowserNotification(title,options={}){
  if(!('Notification' in window)||Notification.permission!=='granted')return;
  try{
    new Notification(title,{
      icon:'/static/assets/logo.png',
      badge:'/static/assets/badge.png',
      ...options
    });
  }catch(e){console.log('Browser notification failed');}
}

// Enhanced toast with notifications
function toast(msg,bg){
  const t=document.getElementById('toast');
  t.style.background=bg||'#0F6E56';
  t.innerHTML=`<div style="display:flex;align-items:flex-start;gap:10px;"><div class="toast-msg" style="flex:1;">${msg}</div><span onclick="this.closest('.toast').style.display='none'" style="cursor:pointer;font-size:16px;line-height:1;opacity:0.8;flex-shrink:0;margin-top:-1px;">X</span></div><div class="toast-bar-wrap"><div class="toast-bar" id="toast-bar"></div></div>`;
  t.style.display='block';
  const bar=document.getElementById('toast-bar');
  bar.style.transition='none';
  bar.style.transform='scaleX(1)';
  requestAnimationFrame(()=>{
    requestAnimationFrame(()=>{
      bar.style.transition='transform 10s linear';
      bar.style.transform='scaleX(0)';
    });
  });
  clearTimeout(t._toastTimer);
  t._toastTimer=setTimeout(()=>t.style.display='none',10000);
  
  // Play sound for important notifications
  if(bg&&(bg.includes('c0392b')||bg.includes('red')||msg.includes('Approved')||msg.includes('Rejected'))){
    playNotificationSound();
  }
}

// Notification with browser push
function notifyWithPush(title,body='',options={}){
  toast(title);
  playNotificationSound();
  sendBrowserNotification(title,{body,...options});
}
function currentSessionUser(){
  try{return JSON.parse(sessionStorage.getItem('licenseiq_session')||'{}');}catch(e){return {};}
}
function empsFor(r){
  const currentName=String(currentSessionUser().name||'').trim();
  if(r==='account'&&currentName){
    const scoped=EMPS.filter(e=>e.acctOwner===currentName);
    return scoped.length?scoped:EMPS;
  }
  if(r==='pm'&&currentName){
    const me=EMPS.find(e=>e.name===currentName);
    return me?EMPS.filter(e=>e.proj===me.proj):EMPS;
  }
  return EMPS;
}
function displayEmpId(employee){
  return String(employee?.code||employee?.id||'').trim();
}
function matchesEmployeeRef(employee, ref){
  const refStr=String(ref??'').trim();
  if(!refStr)return false;
  return String(employee?.id??'').trim()===refStr||displayEmpId(employee)===refStr;
}
function findEmployeeByRef(ref){
  const refStr=String(ref??'').trim();
  if(!refStr)return null;
  return EMPS.find(e=>matchesEmployeeRef(e,refStr))||REQUEST_EMPLOYEES.find(e=>matchesEmployeeRef(e,refStr))||null;
}
function displayEmpIdByRef(ref){
  const employee=findEmployeeByRef(ref);
  return employee?displayEmpId(employee):String(ref??'').trim();
}
function requestUsesRoleScopedAccountProject(){
  return ['gdl','account','pm'].includes(role);
}
function requestScopeEmployees(){
  return empsFor(role).filter(Boolean);
}
function requestScopedAccountNames(){
  return [...new Set(requestScopeEmployees().map(e=>e.acct).filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b)));
}
function requestScopedProjectNames(accountName){
  return [...new Set(requestScopeEmployees()
    .filter(e=>!accountName||String(e.acct)===String(accountName))
    .map(e=>e.proj)
    .filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b)));
}
async function ensureRequestEmployeesLoaded(){
  if(REQUEST_EMPLOYEES.length) return;
  try{
    const apiEmps=await fetchJson(`${API_BASE}/employees/all`, {}, 'Failed to load employees.');
    REQUEST_EMPLOYEES=apiEmps.map(employee=>({
      id:String(employee.id),
      code:employee.employee_code||'',
      name:employee.full_name||'',
      unit:employee.unit||'',
      status:employee.employment_status||'active',
      acct:'',
      proj:'',
      assignments:[],
      lics:[]
    }));
  }catch(e){
    console.warn('Request employee load failed, falling back to scoped employees:', e);
    REQUEST_EMPLOYEES=[];
  }
}
function requestEmployeePool(){
  const pool=REQUEST_EMPLOYEES.length?REQUEST_EMPLOYEES:EMPS;
  return (pool||[]).filter(employee=>employee.name&&String(employee.status||employee.employment_status||'').toLowerCase()==='active');
}
function platformTypeLabel(type){
  return ({per_user:'Per user',enterprise:'Enterprise',usage_based:'Usage based',perpetual:'Perpetual',pay_as_you_go:'Pay as you go'})[type]||type||'—';
}
function platformTypePill(type){
  if(type==='enterprise')return 'pent';
  if(type==='usage_based')return 'pub';
  return 'ppu';
}
function platPoolSeats(p){
  const pool=Number(p.poolActiveSeats);
  if(Number.isFinite(pool)&&pool>0)return pool;
  return Number(p.activeSeats)||1;
}
function platUC(p){
  if(p.type==='per_user')return p.billing==='annual'?Math.round(p.seatCost/12):p.seatCost;
  if(p.type==='usage_based'){
    return Math.round(p.entCost/(p.billing==='annual'?12:1));
  }
  const mo=Math.round(p.entCost/(p.billing==='annual'?12:1));
  return p.alloc==='equal'?Math.round(mo/Math.max(p.entSeats,1)):Math.round(mo/platPoolSeats(p));
}
function licenseDisplayCost(lic){
  const platform=PLATFORMS.find(p=>p.name===lic.plat);
  if(platform){
    if(platform.type==='usage_based'){
      const mo=Math.round(platform.entCost/(platform.billing==='annual'?12:1));
      const pool=platPoolSeats(platform);
      return Math.round(mo/Math.max(pool,1));
    }
    return platUC(platform);
  }
  return roundCost(lic.cost||0);
}
function syncLicenseCostsFromPlatforms(){
  if(!Array.isArray(EMPS)||!Array.isArray(PLATFORMS))return;
  EMPS.forEach(employee=>{
    if(!Array.isArray(employee.lics))return;
    employee.lics.forEach(lic=>{lic.cost=licenseDisplayCost(lic);});
  });
}
function scopeBanner(extra){return '';}function barHtml(label,valStr,valNum,max){return `<div class="bw"><div class="bwr"><span>${label}</span><span>${valStr}</span></div><div class="btr"><div class="bfill" style="width:${Math.round(valNum/Math.max(max,1)*100)}%"></div></div></div>`;}
function notif(){return `<div style="width:30px;height:30px;border-radius:7px;background:var(--tan);display:flex;align-items:center;justify-content:center;cursor:pointer;position:relative;border:1px solid var(--border);"><svg width="13" height="13" viewBox="0 0 16 16" fill="none"><path d="M8 1.5A4.5 4.5 0 0 0 3.5 6v2.5L2 10h12l-1.5-1.5V6A4.5 4.5 0 0 0 8 1.5Z" stroke="#1a1a18" stroke-width="1.5" fill="none"/><path d="M6.5 12.5a1.5 1.5 0 0 0 3 0" stroke="#1a1a18" stroke-width="1.5" fill="none"/></svg><div style="position:absolute;top:5px;right:5px;width:5px;height:5px;background:var(--lime);border-radius:50%;border:1.5px solid var(--white);"></div></div>`;}
function employeeStatusDisplay(e){
  const empStatus=String(e?.status||'').toLowerCase();
  if(empStatus==='exited')return {key:'Exited',label:'Exit',pill:'ph'};
  if(empStatus==='bench')return {key:'Corporate Pool',label:'Corporate Pool',pill:'ph'};
  if(empStatus==='inactive')return {key:'Inactive',label:'Inactive',pill:'pi'};
  return {key:'Active',label:'Active',pill:'pa'};
}
function licenseStatusDisplay(e){
  const current=currentLicenses(e);
  const currentStatuses=current.map(l=>String(l.st||'').toLowerCase());
  if(currentStatuses.some(st=>st==='flagged'))return {key:'flagged',label:'Proj change',pill:'pmd'};
  if(currentStatuses.some(st=>st!=='active'))return {key:'inactive',label:'Inactive',pill:'pmd'};
  return {key:'active',label:'Active',pill:'pa'};
}
function licenseDisplayStatus(e){return licenseStatusDisplay(e).label;}
function licenseLastUsed(e){return e.lics.length?e.lics.reduce((d,l)=>l.last>d?l.last:d,e.lics[0].last||''):'';}
function setLicSort(key){if(licSortKey===key)licSortDir=licSortDir==='asc'?'desc':'asc';else{licSortKey=key;licSortDir=(key==='cost'||key==='lastUsed')?'desc':'asc';}renderLic();}
function toggleLicSortDir(){licSortDir=licSortDir==='asc'?'desc':'asc';renderLic();}
function setLicPage(page){
  const next=Math.max(1,Number(page)||1);
  if(next===licPage)return;
  licPage=next;
  renderLic();
}
function setLicPageSize(size){
  const next=Math.max(1,Number(size)||25);
  if(next===licPageSize)return;
  licPageSize=next;
  licPage=1;
  renderLic();
}
function updateLicSortButtons(){
  ['id','name','cost','status','lastUsed'].forEach(key=>{
    const el=document.getElementById('lsort-'+key);
    if(!el)return;
    if(licSortKey===key){el.textContent=licSortDir==='asc'?'↑':'↓';el.style.color='var(--black)';}
    else{el.textContent='>';el.style.color='#bbb';}
  });
}

function trendChart(data,container,colors){
  if(!container)return;
  const max=Math.max(...data,1);
  const bars=data.map((v,i)=>`<div class="tcbar" style="height:${Math.round(v/max*76)}px;background:${colors&&colors[i]?colors[i]:'var(--lime)'};opacity:${i===data.length-1?1:.75};" data-tip="${MONTHS[i]}: ${fmt(v)}"></div>`).join('');
  const lbls=MONTHS.map(m=>`<div class="tl">${m}</div>`).join('');
  container.innerHTML=`<div class="trend-chart">${bars}</div><div class="trend-labels">${lbls}</div>`;
}

function setContentLoading(isLoading){
  const content=document.getElementById('content');
  if(!content)return;
  let overlay=document.getElementById('content-loading');
  if(isLoading){
    if(!overlay){
      content.style.position='relative';
      content.insertAdjacentHTML('beforeend','<div id="content-loading" style="position:absolute;inset:22px;background:rgba(245,240,232,.96);display:flex;align-items:center;justify-content:center;z-index:20;border-radius:10px;"><div style="text-align:center;"><div style="width:48px;height:48px;border:4px solid #e0d9cc;border-top:4px solid #7cb518;border-radius:50%;animation:licenseiq-spin 0.8s linear infinite;margin:0 auto 16px;"></div><div style="font-size:15px;font-weight:600;color:#333;">Loading data...</div></div></div><style>@keyframes licenseiq-spin{to{transform:rotate(360deg);}}</style>');
    }
    return;
  }
  if(overlay)overlay.remove();
}
function currentLicenses(employee){return (employee?.lics||[]).filter(l=>l.isCurrent!==false);}
function activeCurrentLicenses(employee){return currentLicenses(employee).filter(l=>String(l.st||'').toLowerCase()==='active');}
function platformAllocatedSeats(platformName){
  const name=String(platformName||'').trim();
  if(!name)return 0;
  const holders=new Set();
  (EMPS||[]).forEach(employee=>{
    const holderKey=displayEmpId(employee)||String(employee.name||'').trim();
    if(!holderKey)return;
    const hasPlatform=currentLicenses(employee).some(license=>String(license.plat||'')===name);
    if(hasPlatform)holders.add(holderKey);
  });
  return holders.size;
}
/** Allocated seats for Platform master — prefer bootstrap activeSeats (DB allocation rows). */
function platformActiveSeatCount(platform){
  const bootstrap=Number(platform?.activeSeats);
  if(Number.isFinite(bootstrap)&&bootstrap>=0)return bootstrap;
  return platformAllocatedSeats(platform?.name);
}
function latestSpendYear(){const years=Object.keys(MONTHLY_SPEND||{}).sort((a,b)=>Number(a)-Number(b));return years.length?years[years.length-1]:String(new Date().getFullYear());}
function spendDataForYear(year){return MONTHLY_SPEND[String(year)]||{};}
function projectDataForYear(year){return MONTHLY_PROJ[String(year)]||{};}
function alertKey(alert){return [String(alert?.empId??''),alert?.type||'',alert?.reason||'',alert?.detail||''].join('||');}
function cleanSmartAlertText(text){
  return String(text||'')
    .replace(/\s+from Aspire\b/g,'')
    .replace(/\bAspire\s+HRMS\b/g,'HRMS')
    .replace(/\bAspire\b/g,'')
    .replace(/\s{2,}/g,' ')
    .trim();
}
function loadDismissedAlerts(){
  try{dismissedAlertKeys=new Set(JSON.parse(localStorage.getItem(DISMISSED_ALERTS_KEY)||'[]'));}
  catch(e){dismissedAlertKeys=new Set();}
}
function persistDismissedAlerts(){localStorage.setItem(DISMISSED_ALERTS_KEY,JSON.stringify([...dismissedAlertKeys]));}
function isDismissedAlert(alert){return dismissedAlertKeys.has(alertKey(alert));}
function activeAlerts(){return ALERTS.filter(a=>!isDismissedAlert(a));}
function dismissAlert(empId,type,reason,detail){
  const key=alertKey({empId,type,reason,detail});
  dismissedAlertKeys.add(key);
  persistDismissedAlerts();
  delete expanded[String(empId)+String(type)];
  renderAlerts();
  renderDash();
  notifyWithPush('⊟ Alert Dismissed','The HRMS alert has been acknowledged.');
}
loadDismissedAlerts();

// ─────────── LOGIN ──────────────────────────────────────
function _restoreSession(){
  try{
    const s=sessionStorage.getItem('licenseiq_session');
    if(!s)return false;
    const data=JSON.parse(s);
    if(!data.role||!data.name)return false;
    role=data.role;
    persistUserSession(data);
    const info={name:data.name,ini:data.ini,dept:data.dept};
    document.getElementById('login').style.display='none';
    document.getElementById('main').style.display='flex';
    document.getElementById('sidebar').style.display='flex';
    initSidebarState();
    document.getElementById('sav').textContent=info.ini;
    document.getElementById('sname').textContent=info.name;
    document.getElementById('srole').textContent=info.dept;
    document.getElementById('aspire-wrap').style.display=role==='admin'?'block':'none';
    return true;
  }catch(e){return false;}
}
async function doLogin(){
  const email=document.getElementById('lstaffid').value.trim();
  const pwd=document.getElementById('lpwd').value;
  const errEl=document.getElementById('lerr');
  const btn=document.getElementById('lbtn');
  errEl.textContent='';
  if(!email){errEl.textContent='Enter your email.';return;}
  if(!pwd){errEl.textContent='Enter your password.';return;}
  btn.disabled=true;btn.textContent='Signing in...';
  try{
    const data=await fetchJson(`${API_BASE}/auth/login`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email,password:pwd})
    },'Login failed.');
    role=data.role;
    persistUserSession(data);
    document.getElementById('login').style.display='none';
    document.getElementById('main').style.display='flex';
    setContentLoading(true);
    const loaded=await loadBackendData();
    if(!loaded){
      setContentLoading(false);
      errEl.textContent='Backend unavailable. Make sure the server is running.';
      document.getElementById('login').style.display='flex';
      document.getElementById('main').style.display='none';
      role='';
      return;
    }
    document.getElementById('sidebar').style.display='flex';
    document.getElementById('sav').textContent=data.ini;
    document.getElementById('sname').textContent=data.name;
    document.getElementById('srole').textContent=data.dept;
    document.getElementById('aspire-wrap').style.display=role==='admin'?'block':'none';
    setContentLoading(false);
    buildNav();setupReqForm();show('analytics');initSidebarState();
  }catch(e){
    errEl.textContent=licenseiqUserError(e,'Sign in failed. Check your email and password.');
  }finally{
    btn.disabled=false;btn.textContent='Sign in >';
  }
}
function doLogout(){
  stopNotificationPolling();
  role='';
  REQUEST_EMPLOYEES=[];
  sessionStorage.removeItem('licenseiq_session');
  sessionStorage.removeItem('staffid');
  setContentLoading(false);
  document.getElementById('sidebar').style.display='none';
  document.getElementById('main').style.display='none';
  document.getElementById('login').style.display='flex';
  document.getElementById('lstaffid').value='';
  document.getElementById('lpwd').value='';
  document.getElementById('lerr').textContent='';
}
function navBadgeCount(key){
  if(key==='alerts') return ALERTS.length||'';
  if(key==='queue') return queue.filter(q=>q.status==='pending').length||'';
  if(key==='approvals') return queue.filter(q=>q.approval_stage==='pending_account_owner').length||'';
  return '';
}
function buildNav(){
  document.getElementById('nav').innerHTML=NAV_CFG[role].map(n=>{
    const badge=n.b?navBadgeCount(n.b):'';
    return `<div class="ni" id="ni-${n.k}" onclick="show('${n.k}')"><svg viewBox="0 0 16 16" fill="none">${ICONS[n.k]||''}</svg><span class="ni-label">${n.l}</span><span class="nbadge" id="badge-${n.k}" style="display:${badge?'':'none'}">${badge}</span></div>`;
  }).join('');
}
function updateNavBadges(){
  const alertCount=ALERTS.length;
  const queueCount=queue.filter(q=>q.status==='pending').length;
  const approvalsCount=queue.filter(q=>q.approval_stage==='pending_account_owner').length;
  const ab=document.getElementById('badge-alerts');
  const qb=document.getElementById('badge-queue');
  const apb=document.getElementById('badge-approvals');
  if(ab){ab.textContent=alertCount||'';ab.style.display=alertCount?'':'none';}
  if(qb){qb.textContent=queueCount||'';qb.style.display=queueCount?'':'none';}
  if(apb){apb.textContent=approvalsCount||'';apb.style.display=approvalsCount?'':'none';}
  refreshTopBar();
}
let _currentPage='';
async function refreshCurrentPage(reloadData=true){
  const k=_currentPage;
  if(!k)return;
  if(reloadData){
    setContentLoading(true);
    const loaded=await loadBackendData(true);
    setContentLoading(false);
    if(!loaded)return;
  }

  refreshTopBar();
  if(k==='analytics')  renderAnalytics();
  if(k==='dashboard')  renderDash();
  if(k==='licenses')   renderLic();
  if(k==='queue')      renderQueue();
  if(k==='alerts')     renderAlerts();
  if(k==='search')     initSearch();
  if(k==='cost')       renderCost();
  if(k==='distribution'){renderDist();setDT(distTab||'unit');}
  if(k==='platforms')  renderPlats();
  if(k==='request')    setupReqForm();
  if(k==='approvals'){renderApprovals();await loadApprovalHistory();}
  if(k==='reports')    renderReports();
}
function refreshTopBar(){
  if(!_currentPage)return;
  const k=_currentPage;
  const pendingCount=queue.filter(q=>q.status==='pending').length;
  let btns='';
  if(role!=='finance'&&['analytics','dashboard'].includes(k))btns+=`<button class="btn blm" onclick="show('request')">+ Raise request</button>`;
  if(role!=='finance'&&k==='licenses')btns+=`<button class="btn blm" onclick="openAddLicenseFromRegister()">+ Add license</button>`;

  if(role==='admin'&&k==='platforms')btns+=`<button class="btn blm" onclick="showPF()">+ Add platform</button>`;
  if(role==='admin'&&k==='queue')btns+=`<span id="pending-count" style="font-size:12px;color:var(--gray2);">${pendingCount} pending</span>`;
  if(k==='approvals'){const cnt=queue.filter(q=>q.approval_stage==='pending_account_owner').length;if(cnt>0)btns+=`<span class="nbadge" style="font-size:10px;">${cnt}</span>`;}
  document.getElementById('tba').innerHTML=btns;
}

// Fetch fresh queue data from API and update in-memory queue
async function refreshQueueFromAPI(){
  try{
    const dashboardData=await fetchJson(`${API_BASE}/dashboard`,{},'Failed to load queue.');
    queue=dashboardData.queue||[];
    renderQueue();
  }catch(e){
    console.warn('Failed to refresh queue from API:',e);
    renderQueue();
  }
}

// ─────────── LIVE API HELPERS ───────────────────────────
// Fetches server-authoritative summary for the dashboard metric cards
async function fetchAndUpdateDashboardSummary(accountName, gdlCode, projectName) {
  try {
    const s = await fetchLiveSummary(accountName, gdlCode, projectName);
    const dm = document.getElementById('dm');
    if (dm) dm.innerHTML = [
      {l:'Total licenses', v:s.total_licenses, acc:true},
      {l:'Active',          v:s.active_licenses},
      {l:'Flagged', v:s.flagged_licenses, c:'color:var(--red)'},
      {l:'Monthly spend',  v:fmt(s.monthly_spend)},
    ].map(m=>`<div class="met${m.acc?' macc':''}"><div class="mlb">${m.l}</div><div class="mval" style="${m.c||''}">${m.v}</div></div>`).join('');
    const scope = document.getElementById('df-scope');
    if (scope) scope.textContent = `${s.employee_count} employees${s.open_alerts > 0 ? ' · ' + s.open_alerts + ' alerts' : ''}`;
  } catch(e) { console.warn('Dashboard summary refresh failed:',e); }
}

async function fetchAndUpdateAnalyticsTotalLicenses() {
  try {
    const s = await fetchLiveSummary();
    const totalEl = document.getElementById('an-kpi-total-licenses');
    if (totalEl) totalEl.textContent = s.total_licenses;
    const sub2El = document.getElementById('an-kpi-total-licenses-sub2');
    if (sub2El) sub2El.textContent = `${s.employee_count} employees assigned`;
  } catch(e) { console.warn('Analytics summary refresh failed:', e); }
}

// Fetches fresh alerts from /alerts and updates globals + sync banner
async function refreshAlerts() {
  try {
    const apiAlerts = await fetchJson(`${API_BASE}/alerts`, {}, 'Failed to load alerts.');
    ALERTS = apiAlerts
      .filter(a => a.status === 'open' && ['exit','bench','project_change'].includes(a.alert_type))
      .map(a => ({
        empId: a.employee_code || String(a.employee_id || ''),
        empName: a.employee_name || a.employee_code || String(a.employee_id || ''),
        type:   a.alert_type === 'project_change' ? 'project' : a.alert_type,
        pri:    a.priority,
        reason: cleanSmartAlertText(a.reason),
        detail: cleanSmartAlertText(a.detail || ''),
      }));
    updateNavBadges();
    // Update sync banner with live count + current time
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', {hour:'2-digit', minute:'2-digit'});
    const syncEl = document.getElementById('alert-sync-banner');
    if (syncEl) syncEl.textContent = `Last sync: Today ${timeStr} · ${ALERTS.length} events`;
  } catch(e) { console.warn('Alert refresh failed:',e); }
}

// ─────────── ASPIRE SYNC ────────────────────────────────
let _isSyncing=false;
let lastSyncTime=null;

async function syncFromAspire(){
  if(_isSyncing)return;
  _isSyncing=true;
  
  // Update banner to show "Synchronizing..."
  const banner=document.getElementById('alert-sync-banner');
  if(banner) banner.textContent='Synchronizing...';
  
  // Show loading spinner in alerts container
  const alc=document.getElementById('alc');
  if(alc)alc.innerHTML='<div style="display:flex;align-items:center;justify-content:center;padding:60px 0;"><div style="text-align:center;"><div style="width:44px;height:44px;border:4px solid #e0d9cc;border-top:4px solid #7cb518;border-radius:50%;animation:licenseiq-spin 0.8s linear infinite;margin:0 auto 14px;"></div><div style="font-size:14px;font-weight:600;color:#333;">Loading alerts...</div></div></div>';
  // Fallback: always render after 15s even if API hangs
  const fallback=setTimeout(()=>{_isSyncing=false;renderAlerts();},15000);
  try{
    const result=await fetchJson(`${API_BASE}/alerts/aspire-sync?lookback_days=30`,{method:'POST'},'Aspire sync failed.');
    await refreshAlerts();
    lastSyncTime=new Date();
  }catch(e){
    console.warn('Aspire auto-sync failed:',e.message);
  }finally{
    clearTimeout(fallback);
    _isSyncing=false;
    renderAlerts();
  }
}

// ─────────── SHOW ───────────────────────────────────────
function show(k){
  document.querySelectorAll('.sec').forEach(s=>s.classList.remove('on'));
  const sec=document.getElementById('sec-'+k);if(sec)sec.classList.add('on');
  document.querySelectorAll('.ni').forEach(n=>n.classList.remove('on'));
  const ni=document.getElementById('ni-'+k);if(ni)ni.classList.add('on');
  const pm=PAGE[k]||{title:k,sub:''};
  document.getElementById('ptitle').textContent=pm.title;
  document.getElementById('psub').textContent=pm.sub;
  _currentPage=k;
  refreshTopBar();
  const topbar=document.getElementById('topbar');
  if(topbar) topbar.classList.toggle('topbar-hidden', ['dashboard','cost','distribution'].includes(k));
  if(k==='analytics'){renderAnalytics();}
  if(k==='dashboard'){renderDash();}
  if(k==='alerts')   { syncFromAspire(); }
  if(k==='licenses') renderLic();
  if(k==='request')  setupReqForm();
  if(k==='cost')     renderCost();
  if(k==='queue')    renderQueue();
  if(k==='approvals'){renderApprovals();loadApprovalHistory();}
  if(k==='distribution'){renderDist();setDT('unit');}
  if(k==='search')   initSearch();
  if(k==='platforms')renderPlats();
  if(k==='reports')  renderReports();
}

// ─────────── DASHBOARD ──────────────────────────────────
function clearDF(){['df-account','df-gdl','df-proj'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});renderDash();}
function renderDash(){
  const da=document.getElementById('df-account')?.value||'';
  const dg=document.getElementById('df-gdl')?.value||'';
  const dp=document.getElementById('df-proj')?.value||'';
  let emps=empsFor(role);
  if(da) emps=emps.filter(e=>e.acct===da);
  if(dg) emps=emps.filter(e=>e.gdl===dg);
  if(dp) emps=emps.filter(e=>e.proj===dp);
  const scope=document.getElementById('df-scope');
  const openAlerts=activeAlerts().filter(a=>emps.some(e=>matchesEmployeeRef(e,a.empId))).length;
  if(scope) scope.textContent=(da||dg||dp)?'Filtered view':`${emps.length} employees${openAlerts>0?' · '+openAlerts+' alerts':''}`;
  const allL=emps.flatMap(e=>currentLicenses(e));
  const active=allL.filter(l=>l.st==='active').length;
  const flagged=allL.filter(l=>l.st!=='active').length;
  const spend=allL.reduce((s,l)=>s+l.cost,0);
  const dm=document.getElementById('dm');
  if(dm)dm.innerHTML=[
    {l:'Total licenses',v:allL.length,acc:true},{l:'Active',v:active},
    {l:'Flagged',v:flagged,c:'color:var(--red)'},{l:'Monthly spend',v:fmt(spend)},
  ].map(m=>`<div class="met${m.acc?' macc':''}"><div class="mlb">${m.l}</div><div class="mval" style="${m.c||''}">${m.v}</div></div>`).join('');

  const cfo=document.getElementById('cfo-strip');
  if(cfo){
    if(role==='finance'){
      const year=latestSpendYear();
      const yearSpend=spendDataForYear(year);
      cfo.style.display='grid';
      const totalSpend=Object.values(yearSpend).flatMap(v=>v).reduce((s,v)=>s+v,0);
      const q1=Object.values(yearSpend).reduce((s,arr)=>s+(arr[3]+arr[4]+arr[5]),0);
      const q4=Object.values(yearSpend).reduce((s,arr)=>s+(arr[0]+arr[1]+arr[2]),0);
      const trendPct=q1===0?null:Math.round((q4-q1)/q1*100);
      cfo.innerHTML=[
        {l:`Annual spend ${year}`,v:fmt(totalSpend)},{l:`Q1 spend ${year}<br>Apr – Jun`,v:q1===0?'—':fmt(q1)},
        {l:`Q4 spend ${year}<br>Jan – Mar`,v:fmt(q4)},{l:'Q4 vs Q1 trend',v:trendPct===null?'—':`${trendPct>=0?'+':''}${trendPct}%`,c:'color:var(--amber)'},
      ].map(m=>`<div class="cfo-stat"><div class="cfo-num" style="${m.c||''}">${m.v}</div><div class="cfo-lbl">${m.l}</div></div>`).join('');
    } else {cfo.style.display='none';}
  }

  const pc={};emps.forEach(e=>currentLicenses(e).forEach(l=>{pc[l.plat]=(pc[l.plat]||0)+1;}));
  const maxP=Math.max(...Object.values(pc),1);
  const dpb=document.getElementById('dpb');if(dpb)dpb.innerHTML=Object.entries(pc).map(([p,c])=>barHtml(p,c+' seats',c,maxP)).join('');
  const ac={};emps.forEach(e=>currentLicenses(e).forEach(l=>{ac[e.acct]=(ac[e.acct]||0)+l.cost;}));
  const maxA=Math.max(...Object.values(ac),1);
  const dab=document.getElementById('dab');if(dab)dab.innerHTML=Object.entries(ac).map(([a,c])=>barHtml(a,fmt(c),c,maxA)).join('');
  renderTrend();
  const dat=document.getElementById('dat');
  if(dat){
    const empMap={};
    emps.forEach(e=>{
      empMap[String(e.id)]=e;
      const code=displayEmpId(e);
      if(code)empMap[code]=e;
    });
    // Deduplicate: sort consistently, keep only the first alert per employee+type, then take first 6
    const sortedAlerts=activeAlerts().filter(a=>empMap[a.empId]).sort((a,b)=>{
      // Sort by priority (high first), then by employee ID
      if((a.pri||'medium')==='high' && (b.pri||'medium')!=='high')return -1;
      if((a.pri||'medium')!=='high' && (b.pri||'medium')==='high')return 1;
      return (a.empId||'').localeCompare(b.empId||'');
    });
    const seen=new Set();
    const ae=sortedAlerts.filter(a=>{
      const key=a.empId+'|'+(a.type||'');
      if(seen.has(key))return false;
      seen.add(key);
      return true;
    }).slice(0,6);
    dat.innerHTML=ae.length===0?'<tr><td colspan="6" style="text-align:center;color:var(--gray2);padding:16px;">No alerts in your scope</td></tr>':ae.map(a=>{
      const e=empMap[a.empId];
      const licenses=currentLicenses(e);
      const tags=licenses.map(l=>`<span class="ltag${l.st!=='active'?' ltwarn':''}">${l.plat}</span>`).join('');
      const pri=a.pri==='high'?'<span class="pill ph">High</span>':'<span class="pill pmd">Medium</span>';
      const since=licenses.length?licenses.reduce((d,l)=>l.last<d?l.last:d,licenses[0].last):'—';
      return `<tr><td><strong>${e.name}</strong><div style="font-size:10px;color:var(--gray2);">${displayEmpId(e)}</div></td><td>${tags||'—'}</td><td>${fmtDateInStr(a.reason)}</td><td>${pri}</td><td style="font-size:11px;color:var(--gray2);">${since}</td>
      <td>${role==='admin'?`<button class="btn bdk" style="font-size:11px;padding:3px 8px;" onclick="show('alerts')">View</button>`:role!=='finance'?`<button class="btn blm" style="font-size:11px;padding:3px 8px;" onclick="show('request')">Request</button>`:''}</td></tr>`;
    }).join('');
  }
  // When no filters are active, refresh metrics from the API for accurate totals
  if(!da && !dg && !dp) fetchAndUpdateDashboardSummary();
}
function renderTrend(){
  const sel=document.getElementById('trend-unit')?.value||'total';
  const yr=latestSpendYear();
  const yearSpend=spendDataForYear(yr);
  let data;
  if(sel==='total') data=MONTHS.map((_,i)=>Object.values(yearSpend).reduce((s,arr)=>s+(arr?.[i]||0),0));
  else data=yearSpend[sel]||Array(12).fill(0);
  const colors=data.map((_,i)=>i===data.length-1?'var(--lime)':'#b6f00088');
  trendChart(data,document.getElementById('trend-chart'),colors);
}

// ─────────── ALERTS ─────────────────────────────────────
const ATYPE={exit:{bar:'var(--red)',label:'Employee exit',pill:'pe'},bench:{bar:'#7c3aed',label:'In Corporate Pool',pill:'pb'},project:{bar:'var(--blue)',label:'Project change',pill:'pm'}};
function setAV(v){alertView=v;['sep','comb'].forEach(k=>{const b=document.getElementById('av-'+k);if(b)b.className='stab'+(k===v?' on':'');});renderAlerts();}
function falt(f){altFilter=f;['all','exit','bench','project'].forEach(k=>{const b=document.getElementById('af-'+k);if(b)b.className='btn'+(k===f?' bdk':'');});renderAlerts();}
function togExp(uid){expanded[uid]=!expanded[uid];renderAlerts();}
function filterAlerts(){
  const searchInput=document.getElementById('alerts-search');
  alertSearchFilter=searchInput?searchInput.value.toLowerCase():'';
  renderAlerts();
}
function renderAlerts(){
  // Update sync banner with last sync time
  const banner=document.getElementById('alert-sync-banner');
  if(banner){
    if(_isSyncing){
      banner.textContent='Synchronizing...';
    } else if(lastSyncTime){
      const hrs=lastSyncTime.getHours();
      const mins=String(lastSyncTime.getMinutes()).padStart(2,'0');
      const ampm=hrs>=12?'PM':'AM';
      const hrs12=hrs%12||12;
      const timeStr=hrs12+':'+mins+' '+ampm;
      const dateStr=lastSyncTime.toDateString().split(' ').slice(1).join(' ');  // Format: "May 04, 2026"
      const eventCount=activeAlerts().length;
      banner.textContent=`Last sync: ${dateStr} ${timeStr} · ${eventCount} events`;
    }
  }
  
  // Deduplicate: keep only the first (most recent) alert per employee+type
  const seen=new Set();
  const backendAlerts=activeAlerts().filter(a=>{
    if(!['exit','bench','project'].includes(a.type))return false;
    // Exit/bench alerts: allow even if employee not in EMPS (they may be inactive/departed)
    if(a.type==='exit' || a.type==='bench'){
      if(!String(a.empId||'').trim() && !String(a.empName||'').trim())return false;
    }else{
      // Project alerts: require active licenses
      if(!EMPS.some(e=>matchesEmployeeRef(e,a.empId) && currentLicenses(e).length>0))return false;
    }
    const key=a.empId+'|'+a.type;
    if(seen.has(key))return false;
    seen.add(key);return true;
  });
  const allItems=[...backendAlerts];
  const counts={all:allItems.length,exit:backendAlerts.filter(a=>a.type==='exit').length,bench:backendAlerts.filter(a=>a.type==='bench').length,project:backendAlerts.filter(a=>a.type==='project').length};
  ['all','exit','bench','project'].forEach(k=>{
    const id={all:'ca',exit:'ce',bench:'cb',project:'cp'}[k];
    const el=document.getElementById(id);if(el)el.textContent='('+counts[k]+')';
  });
  let list=altFilter==='all'?allItems:allItems.filter(a=>a.type===altFilter);
  
  // Apply search filter
  if(alertSearchFilter){
    const search=alertSearchFilter;
    list=list.filter(a=>{
      // Try to find employee in EMPS for additional details (project, account)
      // Try both by numeric ID and by code match
      let emp=null;
      emp=EMPS.find(e=>matchesEmployeeRef(e,a.empId));
      const empId=String(a.empId||'').toLowerCase();
      const empName=((a.empName||(emp&&emp.name)||'')).toLowerCase();
      const empProj=(emp?emp.proj:'').toLowerCase();
      const empAcct=(emp?emp.acct:'').toLowerCase();
      const reason=(a.reason||'').toLowerCase();
      const detail=(a.detail||'').toLowerCase();
      return empId.includes(search)||empName.includes(search)||empProj.includes(search)||empAcct.includes(search)||reason.includes(search)||detail.includes(search);
    });
  }
  
  const afl=document.getElementById('afl');if(afl)afl.textContent='Showing '+list.length;
  const alc=document.getElementById('alc');if(!alc)return;
  alc.innerHTML=list.map(a=>{
    const cfg=ATYPE[a.type]||ATYPE.exit;
    const emp=EMPS.find(e=>matchesEmployeeRef(e,a.empId));
    // For exit/bench alerts: allow emp to be null (employee may be inactive), render minimal card
    if(!emp && a.type!=='exit' && a.type!=='bench') return '';
    const uid=a.empId+a.type;const open=expanded[uid];
    
    if(!emp){
      // Render minimal card for inactive employees (exit/bench alerts)
      const empName = a.empName || `Employee ID: ${a.empId}`;
      return `<div style="border-radius:9px;border:1px solid var(--border);background:var(--white);margin-bottom:10px;overflow:hidden;">
        <div style="display:flex;align-items:center;gap:12px;padding:12px 16px;cursor:pointer;" onclick='togExp(${JSON.stringify(uid)})'>
          <div style="width:4px;border-radius:2px;align-self:stretch;background:${cfg.bar};flex-shrink:0;"></div>
          <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:3px;">
              <span style="font-size:13px;font-weight:700;">${empName}</span>
              <span class="pill ${cfg.pill}">${cfg.label}</span>
              <span class="pill p${a.pri==='high'?'h':'md'}">${a.pri}</span>
            </div>
            <div style="font-size:12px;margin-top:3px;">${fmtDateInStr(a.reason)}</div>
          </div>
          <div style="font-size:11px;color:var(--gray2);">${open?'▲':'▼'}</div>
        </div>
        ${open?`<div style="border-top:1px solid var(--tan);padding:12px 16px;background:var(--tan);">
          <div style="background:var(--white);border-radius:7px;border:1px solid var(--border);padding:9px;font-size:11px;color:var(--gray2);">${fmtDateInStr(a.detail)}</div>
          <div style="margin-top:8px;"><button class="btn" style="font-size:11px;padding:3px 9px;" onclick='dismissAlert(${JSON.stringify(String(a.empId))},${JSON.stringify(a.type||"")},${JSON.stringify(a.reason||"")},${JSON.stringify(a.detail||"")})'>Dismiss</button></div>
        </div>`:''}</div>`;
    }
    
    const total=emp.lics.reduce((s,l)=>s+l.cost,0);
    const lrows=emp.lics.map(l=>`<div style="display:flex;align-items:center;gap:10px;padding:7px 10px;background:var(--white);border-radius:7px;margin-bottom:5px;border:1px solid var(--border);flex-wrap:wrap;">
      <div style="min-width:120px;font-size:12px;font-weight:600;">${l.plat}</div>
      <div style="min-width:80px;font-size:12px;color:var(--gray);">${fmt(l.cost)}/Mth</div>
      <div><span class="pill ${l.type==='Enterprise'?'pent':'ppu'}" style="font-size:9px;">${l.type}</span></div>
      <div style="flex:1;font-size:11px;color:var(--gray2);">Last: ${l.last}</div>
      <div style="display:flex;gap:6px;">
        <button class="btn bred" style="font-size:11px;padding:3px 9px;" onclick='addQ(${JSON.stringify(emp.name)},${JSON.stringify(l.plat)},${l.cost},${JSON.stringify(emp.proj)})'>Add to queue</button>
        <button class="btn" style="font-size:11px;padding:3px 9px;" onclick='dismissAlert(${JSON.stringify(String(a.empId))},${JSON.stringify(a.type||"")},${JSON.stringify(a.reason||"")},${JSON.stringify(a.detail||"")})'>Dismiss</button>
      </div></div>`).join('');
    return `<div style="border-radius:9px;border:1px solid var(--border);background:var(--white);margin-bottom:10px;overflow:hidden;">
      <div style="display:flex;align-items:center;gap:12px;padding:12px 16px;cursor:pointer;" onclick='togExp(${JSON.stringify(uid)})'>
        <div style="width:4px;border-radius:2px;align-self:stretch;background:${cfg.bar};flex-shrink:0;"></div>
        <div style="flex:1;">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:3px;">
            <span style="font-size:13px;font-weight:700;">${emp.name}</span>
            <span class="pill ${cfg.pill}">${cfg.label}</span>
            <span class="pill p${a.pri==='high'?'h':'md'}">${a.pri}</span>
            <span class="pill punit">${emp.unit}</span>
            <span style="background:var(--tan2);color:var(--gray);font-size:10px;font-weight:600;padding:2px 7px;border-radius:9px;">${emp.lics.length} lic ~ ${fmt(total)}/Mth</span>
          </div>
          <div style="font-size:11px;color:var(--gray2);">${emp.id} ~ ${trunc(emp.proj)} ~ ${trunc(emp.acct)}</div>
          <div style="font-size:12px;margin-top:3px;">${fmtDateInStr(a.reason)}</div>
        </div>
        <div style="font-size:11px;color:var(--gray2);">${open?'▲':'▼'}</div>
      </div>
      ${open?`<div style="border-top:1px solid var(--tan);padding:12px 16px;background:var(--tan);">${lrows}
        <div style="margin-top:8px;background:var(--white);border-radius:7px;border:1px solid var(--border);padding:9px;font-size:11px;color:var(--gray2);">${fmtDateInStr(a.detail)}</div>
        <div style="margin-top:8px;"><button class="btn bdk" style="font-size:11px;" onclick='addAllQ(${JSON.stringify(emp.id)})'>Add all ${emp.lics.length} to queue</button></div>
      </div>`:''}
    </div>`;
  }).join('')||'<div style="text-align:center;color:var(--gray2);padding:36px;background:var(--white);border-radius:9px;border:1px solid var(--border);">No alerts in this category</div>';
}

  function resolveQueueProjectId(employeeRecord, projName){
    if(employeeRecord && employeeRecord.proj===projName && employeeRecord.proj_id) return employeeRecord.proj_id;
    if(employeeRecord && Array.isArray(employeeRecord.assignments)){
      const assignment=employeeRecord.assignments.find(a=>a.proj===projName&&a.proj_id);
      if(assignment && assignment.proj_id) return assignment.proj_id;
    }
    const projectRecord=(PROJECTS||[]).find(p=>p.name===projName);
    return projectRecord?projectRecord.id:null;
  }

async function addQ(emp,plat,cost,proj){
    const employeeRecord=EMPS.find(e=>e.name===emp&&e.proj===proj)||EMPS.find(e=>e.name===emp);
    const projectId=resolveQueueProjectId(employeeRecord, proj);
    if(!employeeRecord||!projectId){
      toast('Unable to resolve employee or project for queue action.', '#c0392b');
      return;
    }
  try {
      await fetchJson(`${API_BASE}/queue`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({employee_id:employeeRecord.id,employee_name:emp,platform_name:plat,action_type:'revoke',project_id:projectId,project_name:proj,created_by:'Aspire > Admin',effective_date:new Date().toISOString().slice(0,10),source_type:'aspire'})}, 'Failed to add to queue.');
    queue.push({id:Date.now(),emp,plat,type:'revoke',proj,by:'Aspire > Admin',date:'Today',cost,status:'pending',manual:false});
    notifyWithPush('> Added to Queue',`${emp} > ${plat} license revocation added.`);
    await loadBackendData();
    refreshCurrentPage(false);
  } catch(e) { toast(licenseiqUserError(e,'Could not add to queue.'), '#c0392b'); }
}
async function addAllQ(eid){
  const e=EMPS.find(x=>x.id===eid);if(!e)return;
  let added=0;
  for(const l of e.lics){
      const projectId=resolveQueueProjectId(e, e.proj);
      if(!projectId){
        toast('Skipped '+l.plat+': missing project id', '#c0392b');
        continue;
      }
    try{
        await fetchJson(`${API_BASE}/queue`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({employee_id:e.id,employee_name:e.name,platform_name:l.plat,action_type:'revoke',project_id:projectId,project_name:e.proj,created_by:'Aspire > Admin',effective_date:new Date().toISOString().slice(0,10),source_type:'aspire'})}, 'Failed to add to queue.');
      queue.push({id:Date.now()+Math.random(),emp:e.name,plat:l.plat,type:'revoke',proj:e.proj,by:'Aspire > Admin',date:'Today',cost:l.cost,status:'pending',manual:false});
      added++;
    } catch(err){ toast('Skipped '+l.plat+': '+err.message, '#c0392b'); console.error('addAllQ error:', err); }
  }
  if(added>0) { 
    notifyWithPush('> Licenses Added to Queue',`${added} of ${e.lics.length} licenses queued for revocation.`);
    await loadBackendData();
    refreshCurrentPage(false);
  }
}
async function addManualQ(emp,plat,type,proj,cost){
    const employeeRecord=EMPS.find(e=>e.name===emp&&e.proj===proj)||EMPS.find(e=>e.name===emp);
    const projectId=resolveQueueProjectId(employeeRecord, proj);
    if(!employeeRecord||!projectId){
      toast('Unable to resolve employee or project for queue action.', '#c0392b');
      return;
    }
  try {
      await fetchJson(`${API_BASE}/queue`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({employee_id:employeeRecord.id,employee_name:emp,platform_name:plat,action_type:type,project_id:projectId,project_name:proj,created_by:'Manual request > Admin',effective_date:new Date().toISOString().slice(0,10),source_type:'manual'})}, 'Failed to add to queue.');
    queue.push({id:Date.now(),emp,plat,type,proj,by:'Manual request > Admin',date:'Today',cost,status:'pending',manual:true});
    notifyWithPush('> Manual Request Queued',`${emp} > ${plat} ${type} request added.`);
    await loadBackendData();
    refreshCurrentPage(false);
  } catch(e) { toast(licenseiqUserError(e,'Request failed.'), '#c0392b'); }
}

// ─────────── LICENSE REGISTER ───────────────────────────
function getEmployeeShortStatus(e){
  return licenseStatusDisplay(e).key;
}

function getEmployeeLifecycleStatus(e){
  return employeeStatusDisplay(e).key;
}

function getStatusSortValue(status){
  const order={'Active':0,'Inactive':1,'flagged':2,'Corporate Pool':3,'Exited':4};
  return order[status]||5;
}

function licenseRegisterKey(employeeId, platformName){
  return `${employeeId}::${platformName}`;
}

function licenseRegisterDomId(employeeId, platformName){
  const slug=String(platformName||'license').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'')||'license';
  return `licreg-${employeeId}-${slug}`;
}

function setLicenseRegisterContext(employee, platformName=''){
  if(!employee){
    licenseRegisterContext=null;
    return;
  }
  const meta=PROJ_META[employee.proj]||{};
  licenseRegisterContext={
    employeeId:employee.id,
    employeeName:employee.name,
    accountName:employee.acct||'',
    projectName:employee.proj||'',
    gdl:meta.gdl||'',
    platformName:platformName||''
  };
}

function toggleLicenseRegisterRow(employeeId){
  if(licExpandedEmployeeId===employeeId){
    licExpandedEmployeeId=null;
    licSelectedLicenseKey='';
  }else{
    licExpandedEmployeeId=employeeId;
    licSelectedLicenseKey='';
    const employee=EMPS.find(e=>String(e.id)===String(employeeId));
    setLicenseRegisterContext(employee);
  }
  renderLic();
}

function selectLicenseRegisterLicense(employeeId, platformName){
  licExpandedEmployeeId=employeeId;
  licSelectedLicenseKey=licenseRegisterKey(employeeId, platformName);
  const employee=EMPS.find(e=>String(e.id)===String(employeeId));
  setLicenseRegisterContext(employee, platformName);
  renderLic();
}

function openAddLicenseFromRegister(){
  const context=licenseRegisterContext||null;
  pendingRequestPrefill={
    source:'licenses',
    requestType:'assign',
    employeeId:context?.employeeId||null,
    employeeName:context?.employeeName||'',
    accountName:context?.accountName||'',
    projectName:context?.projectName||'',
    gdl:context?.gdl||'',
    platformName:''
  };
  show('request');
}

function applyPendingRequestPrefill(){
  if(!pendingRequestPrefill)return;
  const context=pendingRequestPrefill;
  pendingRequestPrefill=null;
  const employee=context.employeeId?EMPS.find(e=>String(e.id)===String(context.employeeId)):null;
  const typeEl=document.getElementById('rqt');
  const empEl=document.getElementById('rqe');
  const acctEl=document.getElementById('rqacct');
  const projEl=document.getElementById('rqproj');
  const gdlEl=document.getElementById('rqgdl');
  const platEl=document.getElementById('rqp');
  if(typeEl)typeEl.value=context.requestType||'assign';
  if(employee&&empEl){
    selectedEmployeeRequest={id:employee.id,name:employee.name,projectName:context.projectName||employee.proj||''};
    empEl.value=employee.name;
    populateAccountDropdownRequest(employee);
  }
  if(context.accountName&&acctEl){
    selectedAccountRequest={name:context.accountName};
    acctEl.value=context.accountName;
  }
  if(employee&&context.accountName){
    populateProjectsForAccountRequest(employee, context.accountName);
  }
  if(context.projectName&&projEl){
    selectedProjectRequest={name:context.projectName};
    projEl.value=context.projectName;
  }
  if(context.gdl&&gdlEl)gdlEl.value=context.gdl;
  if(context.platformName&&platEl){
    selectedPlatformRequest={name:context.platformName};
    platEl.value=context.platformName;
  }
}

async function submitLicenseRegisterRevoke(employeeId, platformName){
  const employee=EMPS.find(e=>String(e.id)===String(employeeId));
  const platform=PLATFORMS.find(p=>p.name===platformName);
  if(!employee||!platform){
    toast('Unable to resolve employee or platform for revoke request.','var(--red)');
    return;
  }
  const justificationId=`${licenseRegisterDomId(employeeId, platformName)}-just`;
  const justificationEl=document.getElementById(justificationId);
  const justification=(justificationEl?.value||'').trim()||'License revoke request raised';
  try{
    setContentLoading(true);
    await fetchJson(`${API_BASE}/requests`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        request_type:'revoke',
        employee_id:Number(employee.id),
        platform_id:Number(platform.id),
        project_id:employee.project_id||null,
        account_id:employee.account_id||null,
        requested_by_user_id:null,
        requested_by_staffid:sessionStorage.getItem('staffid')||null,
        justification,
        effective_date:new Date().toISOString().slice(0,10)
      })
    },'Failed to submit revoke request.');
    toast(`Revoke request raised for ${employee.name} > ${platformName}.`,'#0F6E56');
    licSelectedLicenseKey='';
    await loadBackendData();
    refreshCurrentPage(false);
  }catch(e){
    toast(licenseiqUserError(e,'Failed to submit revoke request.'),'var(--red)');
  }finally{
    setContentLoading(false);
  }
}

function renderLic(){
  const emps=empsFor(role);

  // ── Cascade: keep only valid project selections when account filter changes ──
  const projScopeForLic = AN_SEL.licAcct.size
    ? emps.filter(e => AN_SEL.licAcct.has(e.acct))
    : emps;
  const validProjs = [...new Set(projScopeForLic.map(e=>e.proj).filter(Boolean))].sort();
  anKeepOnlyValidSelections('licProj', validProjs);

  // ── Build option lists ──
  const _licPlats = PLATFORMS.map(p=>p.name);
  const _licEsts  = ['Active','Inactive','Corporate Pool','Exited'];
  const _licLsts  = ['active','inactive','flagged'];
  const _licUnits = [...new Set(emps.map(e=>e.unit).filter(Boolean))].sort();
  const _licAccts = [...new Set(emps.map(e=>e.acct).filter(Boolean))].sort();
  anKeepOnlyValidSelections('licAcct', _licAccts);

  // ── Read text search ──
  const fq = (document.getElementById('fq')?.value||'').trim().toLowerCase();
  const fqRaw = document.getElementById('fq')?.value || '';
  const fqWasFocused = document.activeElement?.id === 'fq';
  const fqSelStart = document.getElementById('fq')?.selectionStart ?? fqRaw.length;

  // ── Rebuild filter bar ──
  const fbar = document.getElementById('lic-fbar');
  if(fbar){
    fbar.innerHTML = `
      <div class="lic-search-wrap">
        <input id="fq" type="text" placeholder="Search name or ID\u2026" value="${fqRaw.replace(/"/g,'&quot;')}"
          oninput="licPage=1;renderLic()" style="width:160px;font-size:12px;padding:5px 24px 5px 8px;border:1px solid var(--border);border-radius:6px;"/>
        ${fqRaw ? `<button class="lic-search-clear" onclick="document.getElementById('fq').value='';licPage=1;renderLic()" title="Clear search">\u00d7</button>` : ''}
      </div>
      ${anMsBuild('licPlat', 'All Platforms',        _licPlats)}
      ${anMsBuild('licEst',  'All Emp. Statuses',    _licEsts)}
      ${anMsBuild('licLst',  'All License Statuses', _licLsts)}
      ${anMsBuild('licUnit', 'All Units',            _licUnits)}
      ${anMsBuild('licAcct', 'All Accounts',         _licAccts)}
      ${anMsBuild('licProj', 'All Projects',         validProjs)}
      <button class="btn" style="font-size:11px;" onclick="licClearFilters()">Clear</button>
      <div class="lic-actions">
        <div style="font-size:11px;color:var(--gray2);" id="lc"></div>
        <img src="/static/img/sheets.png" alt="Export" style="cursor:pointer;width:20px;height:20px;opacity:0.8;" onclick="exportLicenseRegisterToExcel()" title="Export to Excel"/>
      </div>`;
    if(fqWasFocused){
      const fqEl = document.getElementById('fq');
      if(fqEl){ fqEl.focus(); fqEl.setSelectionRange(fqSelStart, fqSelStart); }
    }
  }

  // ── Apply filters ──
  let list = emps.filter(e=>currentLicenses(e).length>0);
  if(fq)                    list = list.filter(e=>e.name.toLowerCase().includes(fq)||displayEmpId(e).toLowerCase().includes(fq));
  if(AN_SEL.licPlat.size)   list = list.filter(e=>currentLicenses(e).some(l=>AN_SEL.licPlat.has(l.plat)));
  if(AN_SEL.licEst.size)    list = list.filter(e=>AN_SEL.licEst.has(getEmployeeLifecycleStatus(e)));
  if(AN_SEL.licLst.size)    list = list.filter(e=>AN_SEL.licLst.has(getEmployeeShortStatus(e)));
  if(AN_SEL.licUnit.size)   list = list.filter(e=>AN_SEL.licUnit.has(e.unit));
  if(AN_SEL.licAcct.size)   list = list.filter(e=>AN_SEL.licAcct.has(e.acct));
  if(AN_SEL.licProj.size)   list = list.filter(e=>AN_SEL.licProj.has(e.proj));
  if(licExpandedEmployeeId && !list.some(e=>String(e.id)===String(licExpandedEmployeeId))){
    licExpandedEmployeeId=null;
    licSelectedLicenseKey='';
  }

  list=[...list].sort((a,b)=>{
    let av='',bv='';
    if(licSortKey==='id'){av=Number(displayEmpId(a))||0;bv=Number(displayEmpId(b))||0;}
    else if(licSortKey==='name'){av=String(a.name||'').toLowerCase();bv=String(b.name||'').toLowerCase();}
    else if(licSortKey==='cost'){av=activeCurrentLicenses(a).reduce((s,l)=>s+licenseDisplayCost(l),0);bv=activeCurrentLicenses(b).reduce((s,l)=>s+licenseDisplayCost(l),0);}
    else if(licSortKey==='status'){av=getStatusSortValue(getEmployeeShortStatus(a));bv=getStatusSortValue(getEmployeeShortStatus(b));}
    else if(licSortKey==='lastUsed'){av=licenseLastUsed(a);bv=licenseLastUsed(b);}
    let cmp=0;
    if(typeof av==='number'&&typeof bv==='number')cmp=av-bv;
    else cmp=String(av).localeCompare(String(bv));
    return licSortDir==='asc'?cmp:-cmp;
  });
  const licensedEmps=emps.filter(e=>currentLicenses(e).length>0);
  const totalCurrentLicenses=licensedEmps.reduce((sum,e)=>sum+currentLicenses(e).length,0);
  const filteredCurrentLicenses=list.reduce((sum,e)=>sum+currentLicenses(e).length,0);
  const hasLicFilter=AN_SEL.licPlat.size||AN_SEL.licEst.size||AN_SEL.licLst.size||AN_SEL.licUnit.size||AN_SEL.licAcct.size||AN_SEL.licProj.size;
  const hasAnyFilter=hasLicFilter||!!fq;
  const useDbSummary=!hasAnyFilter && LAST_LIVE_SUMMARY?.total_licenses != null;
  const displayEmpCount   = useDbSummary ? LAST_LIVE_SUMMARY.employee_count    : list.length;
  const displayTotalEmps  = useDbSummary ? LAST_LIVE_SUMMARY.employee_count    : licensedEmps.length;
  const displayLicCount   = useDbSummary ? LAST_LIVE_SUMMARY.total_licenses    : filteredCurrentLicenses;
  const displayTotalLics  = useDbSummary ? LAST_LIVE_SUMMARY.total_licenses    : totalCurrentLicenses;
  const totalRows=list.length;
  const totalPages=Math.max(1,Math.ceil(totalRows/licPageSize));
  if(licPage>totalPages)licPage=totalPages;
  const pageStart=(licPage-1)*licPageSize;
  const pageEnd=Math.min(pageStart+licPageSize,totalRows);
  const pagedList=list.slice(pageStart,pageEnd);
  const ls=document.getElementById('ls');if(ls)ls.innerHTML=scopeBanner(list.length+' employees');
  const lc=document.getElementById('lc');if(lc)lc.textContent='Employees '+displayEmpCount+' of '+displayTotalEmps+' | Current licenses '+displayLicCount+' of '+displayTotalLics;
  const lpagerBottom=document.getElementById('lpager-bottom');
  if(lpagerBottom){
    lpagerBottom.innerHTML=totalPages<=1&&totalRows===0?'':`
      <label class="lic-pager-size">Rows per page
        <select onchange="setLicPageSize(this.value)">
          ${[10,25,50,100].map(size=>`<option value="${size}" ${licPageSize===size?'selected':''}>${size}</option>`).join('')}
        </select>
      </label>
      <span class="lic-pager-meta">${totalRows===0?'0':pageStart+1}–${pageEnd} of ${totalRows} results</span>
      <div class="lic-pager-nav">
        <button class="btn" onclick="setLicPage(1)" ${licPage<=1?'disabled':''}>«</button>
        <button class="btn" onclick="setLicPage(${licPage-1})" ${licPage<=1?'disabled':''}>Prev</button>
        <span class="lic-pager-page">Page ${licPage} of ${totalPages}</span>
        <button class="btn" onclick="setLicPage(${licPage+1})" ${licPage>=totalPages?'disabled':''}>Next</button>
        <button class="btn" onclick="setLicPage(${totalPages})" ${licPage>=totalPages?'disabled':''}>»</button>
      </div>`;
  }
  const sc={active:'pa',inactive:'pi',flagged:'pf',exited:'pe',bench:'pb'};
  updateLicSortButtons();
  const ltb=document.getElementById('ltb');
  if(!ltb)return;
  if(totalRows === 0){
    ltb.innerHTML = `<tr><td colspan="11" style="text-align:center;color:var(--gray2);padding:40px 0;font-size:14px;">No results found</td></tr>`;
    return;
  }
  ltb.innerHTML=pagedList.map((e,i)=>{
    const current=currentLicenses(e);
    const activeCurrent=activeCurrentLicenses(e);
    const total=activeCurrent.reduce((s,l)=>s+licenseDisplayCost(l),0);
    const employeeStatus=employeeStatusDisplay(e);
    const licenseStatus=licenseStatusDisplay(e);
    const isExpanded=String(licExpandedEmployeeId)===String(e.id);
    const pendingRevokePlats=(queue||[])
      .filter(q=>q.status==='pending'&&q.type==='revoke'&&(q.emp===e.name||String(q.emp_id)===String(e.id)))
      .map(q=>q.plat);
    const tags=current.map(l=>{
      const status=String(l.st||'').toLowerCase();
      const cls=status==='active'?'ltok':(status==='inactive'||status==='revoked'?'ltrevoked':'ltwarn');
      return `<span class="ltag ${cls}">${l.plat}</span>`;
    }).join(' ');
    const detailRows=current.map(l=>{
      const status=String(l.st||'').toLowerCase();
      const hasPendingRevoke=pendingRevokePlats.includes(l.plat);
      const canRevoke=role!=='finance'&&status==='active'&&!hasPendingRevoke;
      const key=licenseRegisterKey(e.id, l.plat);
      const isSelected=licSelectedLicenseKey===key;
      const domId=licenseRegisterDomId(e.id, l.plat);
      const safePlat=String(l.plat).replace(/'/g,"\\'");
      const statusCls=status==='active'?'pa':(status==='inactive'||status==='revoked'?'pi':'pf');
      return `<div class="licreg-item ${isSelected?'on':''}">
        <div class="licreg-item-main">
          <button class="licreg-license-btn is-static" type="button" disabled>${l.plat}</button>
          <span class="pill ${statusCls}">${status||'unknown'}</span>
          ${hasPendingRevoke?'<span class="lic-revoke-pending-badge">⏳ Revoke pending</span>':''}
          ${canRevoke?`<button class="licreg-revoke-btn" onclick="selectLicenseRegisterLicense(${e.id},'${safePlat}')">X Revoke</button>`:''}
          <span class="licreg-cost">${fmt(licenseDisplayCost(l))}/mo</span>
          <span class="licreg-last">${l.last?`Last used ${l.last}`:'No recent usage'}</span>
        </div>
        ${canRevoke&&isSelected?`<div class="licreg-revoke-box">
          <div class="licreg-revoke-meta">Effective date: Today</div>
          <textarea id="${domId}-just" rows="2">License revoke request raised</textarea>
          <div class="licreg-revoke-actions">
            <button class="btn bred" onclick="submitLicenseRegisterRevoke(${e.id},'${safePlat}')">Revoke</button>
          </div>
        </div>`:''}
      </div>`;
    }).join('');
    const displayId=displayEmpId(e);
    const hist=ALLOC_HIST[e.id];
    const isExited = employeeStatus.key === 'Exited';
    const rowBg = isExited ? '#fff0ee' : ((pageStart+i)%2===0?'transparent':'#faf8f4');
    const exitedStyle = isExited ? 'border-left:3px solid var(--red);' : '';
    return `<tr style="background:${rowBg};${exitedStyle}">
      <td style="color:var(--gray2);font-size:11px;">${displayId}</td>
      <td><strong style="${isExited?'color:var(--red);':''}">${e.name}</strong>${pendingRevokePlats.length>0?`<div style="margin-top:3px;">${pendingRevokePlats.map(plat=>`<span class="lic-revoke-pending-badge">⏳ ${plat} revoke pending</span>`).join('')}</div>`:''}</td>
      <td><span class="pill punit">${e.unit}</span></td>
      <td style="max-width:160px;">${tags}</td>
      <td>${trunc(e.proj)}<div style="font-size:10px;color:var(--gray2);">${trunc(e.acct)}</div></td>
      <td style="font-size:11px;color:var(--gray2);">${e.oracle_id||'\u2014'}</td>
      <td><strong>${fmt(total)}</strong><div style="font-size:10px;color:var(--gray2);">${activeCurrent.length} lic</div></td>
      <td><span class="pill ${employeeStatus.pill}">${employeeStatus.label}</span></td>
      <td><span class="pill ${licenseStatus.pill}">${licenseStatus.label}</span></td>
      <td>${hist?`<button class="btn" style="font-size:11px;padding:3px 8px;" onclick="showHist('${e.id}','${e.name}')">History</button>`:'<span style="font-size:11px;color:var(--gray3);">—</span>'}</td>
      <td><button class="btn" style="font-size:11px;padding:3px 8px;" onclick="toggleLicenseRegisterRow(${e.id})">${isExpanded?'Collapse':'Expand'}</button></td>
    </tr>
    ${isExpanded?`<tr class="licreg-expand-row"><td colspan="11"><div class="licreg-expand-panel"><div class="licreg-expand-title">Assigned licenses</div>${detailRows||'<div class="licreg-empty">No current licenses.</div>'}</div></td></tr>`:''}`;
  }).join('');
}
function showHist(eid,ename){
  const hist=ALLOC_HIST[eid]||[];
  document.getElementById('hist-emp').textContent=ename;
  const histColors={Assigned:'var(--green)',Flagged:'var(--amber)',Revoked:'var(--red)'};
  document.getElementById('hist-content').innerHTML=hist.map(h=>{
    const col=Object.entries(histColors).find(([k])=>h.action.includes(k))?.[1]||'var(--gray2)';
    const dateLabel=h.action.includes('Revoked')||h.action.includes('Deactivated')?'Revoked Date':h.action.includes('Assigned')?'Assigned Date':'Date';
    return `<div class="hist-item"><div class="hdot" style="background:${col};"></div><div><div style="font-size:12px;font-weight:600;">${h.action} > ${h.plat}</div><div style="font-size:11px;color:var(--gray2);">${h.proj} ~ ${dateLabel}: ${h.date} ~ by ${h.by}</div></div></div>`;
  }).join('');
  document.getElementById('hist-panel').style.display='block';
  document.getElementById('hist-panel').scrollIntoView({behavior:'smooth'});
}

function licClearFilters(){
  ['licPlat','licEst','licLst','licUnit','licAcct','licProj'].forEach(k => {
    if(AN_SEL[k]) AN_SEL[k].clear();
  });
  const fqEl = document.getElementById('fq');
  if(fqEl) fqEl.value = '';
  licPage=1;
  renderLic();
}

// ─────────── REQUEST ────────────────────────────────────
function currentSessionStaffId(){
  return currentSessionUser().staffid||null;
}
async function loadMyRecentRequests(){
  try{
    const staffid=sessionStorage.getItem('staffid');
    // Load employee data to resolve names
    await ensureRequestEmployeesLoaded();
    // IT Admin sees ALL requests (for approval), others see their own
    const url=role==='admin'?`${API_BASE}/requests`:`${API_BASE}/requests?staffid=${encodeURIComponent(staffid)}`;
    const all=await fetchJson(url, {}, 'Failed to load recent requests.');
    renderMyRequests(all);
  }catch(e){
    renderMyRequests([]);
  }
}
function renderMyRequests(reqs){
  const tbody=document.getElementById('mrb');
  if(!tbody)return;
  if(!reqs||!reqs.length){
    tbody.innerHTML='<tr><td colspan="5" style="color:var(--gray2);text-align:center;padding:18px;">No requests yet</td></tr>';
    return;
  }
  const statusLabel=s=>{
    if(s==='executed')return 'Executed';
    if(s==='rejected')return 'Rejected';
    if(s==='self_approved')return 'Self-Approved';
    if(s==='pending_it_admin')return 'Pending IT Admin';
    if(s==='pending_approval'||s==='submitted')return 'Pending Approval';
    return 'Requested';
  };
  const statusCls=s=>s==='executed'?'pa':s==='rejected'?'pi':s==='self_approved'?'psa':'pm';
  tbody.innerHTML=reqs.slice(0,10).map(r=>{
    // Try to find employee in EMPS first, then REQUEST_EMPLOYEES
    let emp=EMPS.find(e=>Number(e.id)===r.employee_id);
    if(!emp && REQUEST_EMPLOYEES.length>0){
      emp=REQUEST_EMPLOYEES.find(e=>Number(e.id)===r.employee_id);
    }
    const plat=PLATFORMS.find(p=>p.id===r.platform_id);
    const empName=emp?emp.name:`Employee #${displayEmpIdByRef(r.employee_id) || r.employee_id}`;
    return `<tr>
      <td>${empName}</td>
      <td>${plat?plat.name:r.platform_id}</td>
      <td style="text-transform:capitalize;">${r.request_type}</td>
      <td><span class="pill ${statusCls(r.approval_status)}">${statusLabel(r.approval_status)}</span></td>
      <td style="font-size:11px;color:var(--gray2);">${fmtRequestDate(r.created_at||r.effective_date||'')}</td>
    </tr>`;
  }).join('');
}
function updateSubmitButtonLabel(){
  const btn=document.getElementById('submit-req-btn');
  if(!btn)return;
  const selfApproveRoles=['admin','it_admin','account','account_owner','gdl'];
  btn.textContent=selfApproveRoles.includes(role)?'Submit & self-approve':'Submit Request';
}
function setupReqForm(){
  updateSubmitButtonLabel();
  const empSelect=document.getElementById('rqe');
  const projSelect=document.getElementById('rqproj');
  const dateInput=document.getElementById('rqdt');
  const platformSelect=document.getElementById('rqp');
  const rqs=document.getElementById('rqs');
  if(!empSelect||!projSelect||!dateInput||!platformSelect){
    if(rqs)rqs.innerHTML=scopeBanner('');
    return;
  }
  const today=new Date().toISOString().slice(0,10);
  empSelect.value='';
  projSelect.value='';
  document.getElementById('rqacct').value='';
  platformSelect.value='';
  dateInput.min=today;
  dateInput.value=today;
  selectedEmployeeRequest=null;
  selectedPlatformRequest=null;
  selectedAccountRequest=null;
  selectedProjectRequest=null;
  currentEmployeeAccounts=[];
  ensureRequestEmployeesLoaded().then(()=>populateEmployeeDropdownRequest()).catch(()=>{});
  if(rqs)rqs.innerHTML=scopeBanner('');
  loadMyRecentRequests();
  applyPendingRequestPrefill();
}
function employeeHasActiveLicense(employee, platformName){
  return !!employee&&Array.isArray(employee.lics)&&employee.lics.some(l=>l.plat===platformName&&String(l.st||'').toLowerCase()==='active');
}

function setRequestGdlValue(value){
  const requestGdlField=document.getElementById('rqgdl');
  if(requestGdlField) requestGdlField.value=value||'';
}

function autoFill(){
  const meta=PROJ_META[document.getElementById('rqproj').value]||{};
  document.getElementById('rqacct').value=meta.acct||'';
  setRequestGdlValue(meta.gdl||'');
}

function hasPendingAssignInQueue(employeeName, platformName){
  return Array.isArray(queue)&&queue.some(q=>q.emp===employeeName&&q.plat===platformName&&String(q.type||'').toLowerCase()==='assign');
}

async function submitReq(){
  const empName=document.getElementById('rqe').value;
  const platName=document.getElementById('rqp').value;
  const acctName=document.getElementById('rqacct').value;
  const projName=document.getElementById('rqproj').value;
  const type=document.getElementById('rqt').value;
  const effDate=document.getElementById('rqdt').value;
  const justif=document.getElementById('rqj').value.trim();
  const today=new Date().toISOString().slice(0,10);
  
  if(!empName){toast('Select an employee','var(--red)');return;}
  if(!platName){toast('Select a platform','var(--red)');return;}
  if(!acctName){toast('Select an account','var(--red)');return;}
  if(!projName){toast('Select a project','var(--red)');return;}
  if(!effDate){toast('Select effective date','var(--red)');return;}
  if(effDate<today){toast('Effective date cannot be in the past','var(--red)');return;}
  if(!justif){toast('Add justification','var(--red)');return;}
  if(!selectedEmployeeRequest){toast('Please select an employee from the dropdown','var(--red)');return;}
  if(!selectedPlatformRequest){toast('Please select a platform from the dropdown','var(--red)');return;}
  if(!selectedAccountRequest){toast('Please select an account from the dropdown','var(--red)');return;}
  if(!selectedProjectRequest){toast('Please select a project from the dropdown','var(--red)');return;}
  
  const emp=EMPS.find(e=>String(e.id)===String(selectedEmployeeRequest.id))||requestEmployeePool().find(e=>String(e.id)===String(selectedEmployeeRequest.id))||{id:selectedEmployeeRequest.id,name:empName,lics:[]};
  const plat=PLATFORMS.find(p=>p.name===selectedPlatformRequest.name);
  if(!plat){toast('Platform not found in list','var(--red)');return;}
  if(type==='assign'&&employeeHasActiveLicense(emp,platName)){
    toast(`${empName} already has ${platName} assigned.`,'var(--red)');
    return;
  }
  if(type==='assign'&&hasPendingAssignInQueue(empName,platName)){
    toast(`An assign request for ${empName} and ${platName} is already pending.`,'var(--red)');
    return;
  }
  
  try{
    setContentLoading(true);
    // Use the selected account and project from dropdowns
    // Try to find their IDs from PROJECTS array, otherwise use names
    let projectId=null;
    let accountId=null;
    const projectMatch=(PROJECTS||[]).find(p=>String(p.name||p)===projName);
    if(projectMatch){
      projectId=typeof projectMatch==='object'?projectMatch.id:null;
    }
    // For accountId, we might not have it in the dropdown, send account name to backend to resolve
    
    const payload={
      request_type:type,
      employee_id:Number(emp.id),
      platform_id:plat.id,
      project_id:projectId,
      project_name:projName,
      account_name:acctName,
      account_id:accountId,
      requested_by_user_id:null,
      requested_by_staffid:sessionStorage.getItem('staffid')||null,
      justification:justif,
      effective_date:effDate
    };
    
    await fetchJson(`${API_BASE}/requests`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(payload)
    },'Failed to submit request.');
    
    await loadBackendData();
    document.getElementById('rqe').value='';
    document.getElementById('rqp').value='';
    document.getElementById('rqacct').value='';
    document.getElementById('rqproj').value='';
    setRequestGdlValue('');
    document.getElementById('rqj').value='';
    document.getElementById('rqdt').value=new Date().toISOString().slice(0,10);
    selectedEmployeeRequest=null;
    selectedPlatformRequest=null;
    selectedAccountRequest=null;
    selectedProjectRequest=null;
    
    notifyWithPush('! Request Submitted','Your license request has been submitted for approval.',`${empName} - ${platName}`);
    refreshCurrentPage(false);
    await loadMyRecentRequests();
  }catch(e){
    console.error('submitReq error:',e);
    toast(licenseiqUserError(e,'Failed to submit request.'),'var(--red)');
  }finally{
    setContentLoading(false);
  }
}

// ─────────── ACTION QUEUE ───────────────────────────────
let mrOpen=false;
let selectedEmployee=null;
let selectedProject=null;
let queueSearchFilter='';

function filterQueue(){
  const searchInput=document.getElementById('queue-search');
  queueSearchFilter=searchInput?searchInput.value.toLowerCase():'';
  renderQueue();
}

function closeMRDropdowns(){
  const empDropdown=document.getElementById('emp-dropdown');
  if(empDropdown) empDropdown.classList.remove('open');
  const mrAcctDD=document.getElementById('mr-acct-dropdown');
  if(mrAcctDD) mrAcctDD.classList.remove('open');
  const mrProjDD=document.getElementById('mr-proj-dropdown');
  if(mrProjDD) mrProjDD.classList.remove('open');
  const platDropdownManual=document.getElementById('plat-dropdown-manual');
  if(platDropdownManual) platDropdownManual.classList.remove('open');
}

function togMR(){
  mrOpen=!mrOpen;
  document.getElementById('mreq-form').style.display=mrOpen?'block':'none';
  document.getElementById('mr-dt').value=new Date().toISOString().slice(0,10);
  try{const s=JSON.parse(sessionStorage.getItem('licenseiq_session')||'{}');document.getElementById('mr-by').value=s.name||'';} catch(e){}
  if(mrOpen){
    // Reset form state
    selectedEmployee=null;
    selectedPlatformManual=null;
    selectedProject=null;
    selectedAccountRequest=null;
    selectedProjectRequest=null;
    document.getElementById('mr-emp').value='';
    document.getElementById('mr-plat').value='';
    document.getElementById('mr-proj').value='';
    document.getElementById('mr-acct').value='';
    document.getElementById('mr-gdl').value='';
    
    populateEmployeeDropdown();
    populatePlatformDropdownManual();
    // Don't pre-populate account/project dropdowns - let user select employee first
    document.getElementById('mr-acct-list').innerHTML='<div class="searchable-dropdown-empty">Select an employee first</div>';
    document.getElementById('mr-proj-list').innerHTML='<div class="searchable-dropdown-empty">Select an employee first</div>';
  }else{
    closeMRDropdowns();
    document.getElementById('mr-emp').value='';
    document.getElementById('mr-plat').value='';
    document.getElementById('mr-proj').value='';
    document.getElementById('mr-acct').value='';
    document.getElementById('mr-gdl').value='';
    selectedEmployee=null;
    selectedPlatformManual=null;
    selectedProject=null;
    selectedAccountRequest=null;
    selectedProjectRequest=null;
  }
}

function autoFillManual(){
  const projectName=document.getElementById('mr-proj')?.value||'';
  const meta=PROJ_META[projectName]||{};
  const employee=selectedEmployee?EMPS.find(e=>String(e.id)===String(selectedEmployee.id)):null;
  document.getElementById('mr-acct').value=meta.acct||employee?.acct||'';
  document.getElementById('mr-gdl').value=meta.gdl||employee?.gdl||'';
}

function populateEmployeeDropdown(){
  const input=document.getElementById('mr-emp');
  const list=document.getElementById('emp-dropdown-list');
  const filtered=EMPS.filter(e=>e.name);
  const sorted=[...filtered].sort((a,b)=>eSafeName(a).localeCompare(eSafeName(b)));
  const search=input.value.toLowerCase();
  const results=sorted.filter(e=>{
    const employeeName=eSafeName(e).toLowerCase();
    const employeeId=displayEmpId(e).toLowerCase();
    return employeeName.includes(search)||employeeId.includes(search);
  });
  
  if(results.length===0){
    list.innerHTML='<div class="searchable-dropdown-empty">No employees found</div>';
  }else{
    list.innerHTML=results.map(e=>{
      const employeeName=eSafeName(e);
      const projectName=String(e.proj||'');
      const projectId=e.proj_id??null;
      const safeEmployeeName=employeeName.replace(/'/g,"\\'");
      const safeProjectName=projectName.replace(/'/g,"\\'");
      const empStatus=String(e.status||'').toLowerCase();
      const statusDisplay=empStatus==='active'?'':'<span style="color:var(--gray2);">'+empStatus+'</span> ';
      return `<div class="searchable-dropdown-item" onclick="selectEmployee('${e.id}','${safeEmployeeName}','${safeProjectName}',${projectId===null?'null':projectId})">${employeeName} <span style="color:var(--gray2);">(#${displayEmpId(e)})</span> ${statusDisplay}</div>`;
    }).join('');
  }
}

function populateProjectDropdown(){
  const input=document.getElementById('mr-proj');
  const list=document.getElementById('mr-proj-list');
  const search=input.value.toLowerCase();
  
  let projectsToShow=(PROJECTS||[]);
  if(selectedEmployee || selectedEmployeeRequest){
    const empId=selectedEmployee?.id||selectedEmployeeRequest?.id;
    const employeeObj=EMPS.find(e=>String(e.id)===String(empId));
    const accountName=document.getElementById('mr-acct')?.value||'';
    
    if(employeeObj && Array.isArray(employeeObj.assignments) && employeeObj.assignments.length > 0){
      projectsToShow=[];
      employeeObj.assignments.forEach(a => {
        if(!accountName || a.acct === accountName){
          if(!projectsToShow.find(p => String((typeof p === 'object' ? p.name : p)) === a.proj)){
            projectsToShow.push({name: a.proj});
          }
        }
      });
    }
  }
  
  const filtered=projectsToShow.filter(Boolean);
  const sorted=[...filtered].sort((a,b)=>String((typeof a==='object'?a.name:a)||'').localeCompare(String((typeof b==='object'?b.name:b)||'')));
  const results=sorted.filter(p=>String((typeof p==='object'?p.name:p)||'').toLowerCase().includes(search));
  
  if(results.length===0){
    list.innerHTML='<div class="searchable-dropdown-empty">No active projects found</div>';
  }else{
    list.innerHTML=results.map(p=>{
      const projectName=String((typeof p==='object'?p.name:p)||'');
      const projectId=(typeof p==='object'?p.id:null);
      const safeProjectName=projectName.replace(/'/g,"\\'");
      return `<div class="searchable-dropdown-item" onclick="selectProject('${safeProjectName}',${projectId||'null'})">${projectName}</div>`;
    }).join('');
  }
}

function filterEmployees(){
  selectedEmployee=null;
  document.getElementById('emp-dropdown').classList.add('open');
  populateEmployeeDropdown();
}

function filterProjects(){
  selectedProject=null;
  document.getElementById('proj-dropdown').classList.add('open');
  populateProjectDropdown();
}

// Dedicated filter functions for the manual request form (unique IDs mr-acct, mr-proj)
function filterAccountsManual(){
  if(!selectedEmployee){
    toast('Select an employee first','var(--red)');
    return;
  }
  selectedAccountRequest=null;
  document.getElementById('mr-acct-dropdown').classList.add('open');
  const employeeObj=EMPS.find(e=>String(e.id)===String(selectedEmployee.id));
  const list=document.getElementById('mr-acct-list');
  const input=document.getElementById('mr-acct');
  const search=input.value.toLowerCase();
  const accounts=new Set();
  if(employeeObj){
    if(employeeObj.acct) accounts.add(employeeObj.acct);
    (employeeObj.assignments||[]).forEach(a=>{ if(a.acct) accounts.add(a.acct); });
  }
  const results=Array.from(accounts).sort().filter(a=>a.toLowerCase().includes(search));
  if(results.length===0){
    list.innerHTML='<div class="searchable-dropdown-empty">No accounts found</div>';
  }else{
    list.innerHTML=results.map(a=>{
      const safe=a.replace(/'/g,"\\'");
      return `<div class="searchable-dropdown-item" onclick="selectAccountRequest('${safe}')">${a}</div>`;
    }).join('');
  }
}

function filterProjectsManual(){
  if(!selectedEmployee){
    toast('Select an employee first','var(--red)');
    return;
  }
  selectedProjectRequest=null;
  selectedProject=null;
  document.getElementById('mr-proj-dropdown').classList.add('open');
  const employeeObj=EMPS.find(e=>String(e.id)===String(selectedEmployee.id));
  const accountName=document.getElementById('mr-acct')?.value||'';
  const input=document.getElementById('mr-proj');
  const search=input.value.toLowerCase();
  const list=document.getElementById('mr-proj-list');
  let projectsToShow=[];
  if(employeeObj && Array.isArray(employeeObj.assignments) && employeeObj.assignments.length>0){
    employeeObj.assignments.forEach(a=>{
      if(!accountName||a.acct===accountName){
        if(!projectsToShow.find(p=>p.name===a.proj)) projectsToShow.push({name:a.proj,id:a.proj_id||null});
      }
    });
  }
  // fallback to primary proj
  if(projectsToShow.length===0 && employeeObj && employeeObj.proj){
    projectsToShow=[{name:employeeObj.proj,id:employeeObj.proj_id||null}];
  }
  const results=projectsToShow.filter(p=>p.name.toLowerCase().includes(search)).sort((a,b)=>a.name.localeCompare(b.name));
  if(results.length===0){
    list.innerHTML='<div class="searchable-dropdown-empty">No projects found</div>';
  }else{
    list.innerHTML=results.map(p=>{
      const safe=p.name.replace(/'/g,"\\'");
      return `<div class="searchable-dropdown-item" onclick="selectProject('${safe}',${p.id||'null'})">${p.name}</div>`;
    }).join('');
  }
}

function filterPlatformsManual(){
  selectedPlatformManual=null;
  document.getElementById('plat-dropdown-manual').classList.add('open');
  populatePlatformDropdownManual();
}

function filterPlatformsRequest(){
  selectedPlatformRequest=null;
  document.getElementById('plat-dropdown-request').classList.add('open');
  populatePlatformDropdownRequest();
}

async function filterEmployeesRequest(){
  selectedEmployeeRequest=null;
  document.getElementById('emp-dropdown-request').classList.add('open');
  await populateEmployeeDropdownRequest();
}

function filterProjectsRequest(){
  selectedProjectRequest=null;
  document.getElementById('proj-dropdown-request').classList.add('open');
  
  // Determine which form context we're in
  if(selectedEmployeeRequest){
    // Raise request form context
    if(selectedAccountRequest && selectedAccountRequest.name){
      populateProjectsForAccountRequest(null, selectedAccountRequest.name);
    } else {
      const employeeObj=EMPS.find(e=>String(e.id)===String(selectedEmployeeRequest.id));
      populateProjectDropdownRequestForEmployee(employeeObj);
    }
  } else if(selectedEmployee){
    // Manual request form context - delegate to the dedicated manual filter
    filterProjectsManual();
    return;
    const list=document.getElementById('proj-dropdown-list-request');
    list.innerHTML='<div class="searchable-dropdown-empty">Select an employee first</div>';
  }
}

// Close dropdowns when clicking outside
document.addEventListener('click',function(e){
  const closeDropdown=(id)=>{const el=document.getElementById(id);if(el)el.classList.remove('open');};
  if(!e.target.closest('#emp-dropdown'))closeDropdown('emp-dropdown');
  if(!e.target.closest('#proj-dropdown'))closeDropdown('proj-dropdown');
  if(!e.target.closest('#plat-dropdown-manual'))closeDropdown('plat-dropdown-manual');
  if(!e.target.closest('#plat-dropdown-request'))closeDropdown('plat-dropdown-request');
  if(!e.target.closest('#emp-dropdown-request'))closeDropdown('emp-dropdown-request');
  if(!e.target.closest('#acct-dropdown-request'))closeDropdown('acct-dropdown-request');
  if(!e.target.closest('#proj-dropdown-request'))closeDropdown('proj-dropdown-request');
  if(!e.target.closest('#mr-acct-dropdown'))closeDropdown('mr-acct-dropdown');
  if(!e.target.closest('#mr-proj-dropdown'))closeDropdown('mr-proj-dropdown');
});

function eSafeName(employee){
  return String(employee?.name||'');
}

function selectEmployee(id, name, projectName='', projectId=null){
  selectedEmployee={id,name,projectName,projectId};
  document.getElementById('mr-emp').value=name;
  document.getElementById('emp-dropdown').classList.remove('open');
  
  if(projectName){
    selectedProject=projectId?{name:projectName,id:projectId}:{name:projectName};
    document.getElementById('mr-proj').value=projectName;
  }else{
    selectedProject=null;
    document.getElementById('mr-proj').value='';
  }
  
  // Populate and auto-fill account dropdown for manual request form
  const employeeObj=EMPS.find(e=>String(e.id)===String(id));
  if(employeeObj && Array.isArray(employeeObj.assignments) && employeeObj.assignments.length > 0){
    const accounts=new Set();
    employeeObj.assignments.forEach(a => { if(a.acct) accounts.add(a.acct); });
    if(accounts.size > 0){
      const firstAccount=Array.from(accounts).sort()[0];
      document.getElementById('mr-acct').value=firstAccount;
      selectedAccountRequest={name:firstAccount};
      selectAccountRequest(firstAccount);
    }
  }else{
    autoFillManual();
  }
}

function selectProject(name,id){
  selectedProject={name,id};
  document.getElementById('mr-proj').value=name;
  document.getElementById('mr-proj-dropdown').classList.remove('open');
  autoFillManual();
}

function populatePlatformDropdownManual(){
  const input=document.getElementById('mr-plat');
  const list=document.getElementById('plat-dropdown-list-manual');
  const filtered=(PLATFORMS||[]).filter(Boolean);
  const sorted=[...filtered].sort((a,b)=>String(a.name||'').localeCompare(String(b.name||'')));
  const search=input.value.toLowerCase();
  const results=sorted.filter(p=>String(p.name||'').toLowerCase().includes(search));
  
  if(results.length===0){
    list.innerHTML='<div class="searchable-dropdown-empty">No platforms found</div>';
  }else{
    list.innerHTML=results.map(p=>{
      const safeName=String(p.name).replace(/'/g,"\\'");
      return `<div class="searchable-dropdown-item" onclick="selectPlatformManual('${safeName}')">${p.name}</div>`;
    }).join('');
  }
}

function selectPlatformManual(name){
  selectedPlatformManual={name};
  document.getElementById('mr-plat').value=name;
  document.getElementById('plat-dropdown-manual').classList.remove('open');
}

function populatePlatformDropdownRequest(){
  const input=document.getElementById('rqp');
  const list=document.getElementById('plat-dropdown-list-request');
  const filtered=(PLATFORMS||[]).filter(Boolean);
  const sorted=[...filtered].sort((a,b)=>String(a.name||'').localeCompare(String(b.name||'')));
  const search=input.value.toLowerCase();
  const results=sorted.filter(p=>String(p.name||'').toLowerCase().includes(search));
  
  if(results.length===0){
    list.innerHTML='<div class="searchable-dropdown-empty">No platforms found</div>';
  }else{
    list.innerHTML=results.map(p=>{
      const safeName=String(p.name).replace(/'/g,"\\'");
      return `<div class="searchable-dropdown-item" onclick="selectPlatformRequest('${safeName}')">${p.name}</div>`;
    }).join('');
  }
}

function selectPlatformRequest(name){
  selectedPlatformRequest={name};
  document.getElementById('rqp').value=name;
  document.getElementById('plat-dropdown-request').classList.remove('open');
}

async function populateEmployeeDropdownRequest(){
  await ensureRequestEmployeesLoaded();
  const input=document.getElementById('rqe');
  const list=document.getElementById('emp-dropdown-list-request');
  const filtered=requestEmployeePool();
  const sorted=[...filtered].sort((a,b)=>eSafeName(a).localeCompare(eSafeName(b)));
  const search=input.value.toLowerCase();
  const results=sorted.filter(e=>{
    const employeeName=eSafeName(e).toLowerCase();
    const employeeId=displayEmpId(e).toLowerCase();
    const projectName=String(e.proj||'').toLowerCase();
    return employeeName.includes(search)||employeeId.includes(search)||projectName.includes(search);
  });
  
  if(results.length===0){
    list.innerHTML='<div class="searchable-dropdown-empty">No active employees found</div>';
  }else{
    list.innerHTML=results.map(e=>{
      const employeeName=eSafeName(e);
      const projectName=String(e.proj||'');
      const safeEmployeeName=employeeName.replace(/'/g,"\\'");
      const safeProjectName=projectName.replace(/'/g,"\\'");
      const detail=projectName?`<span style="color:var(--gray2);"> ~ ${projectName}</span>`:'';
      return `<div class="searchable-dropdown-item" onclick="selectEmployeeRequest('${e.id}','${safeEmployeeName}','${safeProjectName}')">${employeeName} <span style="color:var(--gray2);">(#${displayEmpId(e)})</span>${detail}</div>`;
    }).join('');
  }
}

function selectEmployeeRequest(id,name,projectName=''){
  selectedEmployeeRequest={id,name,projectName};
  document.getElementById('rqe').value=name;
  document.getElementById('emp-dropdown-request').classList.remove('open');
  
  // Get the full employee object
  const employeeObj=EMPS.find(e=>String(e.id)===String(id));
  
  // Build available accounts for the request form.
  if(requestUsesRoleScopedAccountProject()){
    currentEmployeeAccounts=requestScopedAccountNames();
  }else{
    currentEmployeeAccounts=[];
    if(employeeObj && employeeObj.acct){
      currentEmployeeAccounts.push(employeeObj.acct);
    }
    if(employeeObj && Array.isArray(employeeObj.assignments) && employeeObj.assignments.length > 0){
      employeeObj.assignments.forEach(a => {
        if(a.acct && !currentEmployeeAccounts.includes(a.acct)) currentEmployeeAccounts.push(a.acct);
      });
    }else{
      EMPS.forEach(emp => {
        if(String(emp.id) === String(id) && emp.acct && !currentEmployeeAccounts.includes(emp.acct)){
          currentEmployeeAccounts.push(emp.acct);
        }
      });
    }
  }
  
  // Reset account and project selections
  selectedAccountRequest=null;
  selectedProjectRequest=null;
  document.getElementById('rqacct').value='';
  document.getElementById('rqproj').value='';
  setRequestGdlValue('');
  
  // Show account dropdown
  populateAccountDropdownRequest(employeeObj);
  
  // If only one account is available, auto-select it.
  if(currentEmployeeAccounts.length===1){
    const onlyAccount=currentEmployeeAccounts[0];
    selectedAccountRequest={name:onlyAccount};
    document.getElementById('rqacct').value=onlyAccount;
    populateProjectsForAccountRequest(employeeObj, onlyAccount);
    if(!requestUsesRoleScopedAccountProject() && projectName){
      selectedProjectRequest={name:projectName};
      document.getElementById('rqproj').value=projectName;
      const meta=PROJ_META[projectName]||{};
      setRequestGdlValue(meta.gdl||'');
    }
  }
}

function populateProjectDropdownRequestForEmployee(employee){
  const input=document.getElementById('rqproj');
  const list=document.getElementById('proj-dropdown-list-request');
  
  if(!employee||!employee.proj){
    list.innerHTML='<div class="searchable-dropdown-empty">No projects for this employee</div>';
    return;
  }
  
  // Get all unique projects for this employee
  // PROJECTS may contain strings or {id,name} objects depending on bootstrap shape.
  const employeeProjects=(PROJECTS||[])
    .filter(projectItem=>String(projectItem?.name||projectItem||'')===String(employee.proj||''))
    .map(projectItem=>String(projectItem?.name||projectItem||''));
  
  if(employeeProjects.length===0){
    list.innerHTML='<div class="searchable-dropdown-empty">No projects for this employee</div>';
    return;
  }
  
  const search=input.value.toLowerCase();
  const results=employeeProjects.filter(p=>String(p).toLowerCase().includes(search));
  
  if(results.length===0){
    list.innerHTML='<div class="searchable-dropdown-empty">No matching projects</div>';
  }else{
    list.innerHTML=results.map(projectName=>{
      const safeProjectName=String(projectName).replace(/'/g,"\\'");
      return `<div class="searchable-dropdown-item" onclick="selectProjectRequest('${safeProjectName}')">${projectName}</div>`;
    }).join('');
  }
}

function filterAccountsRequest(){
  // Check both form contexts
  if(!requestUsesRoleScopedAccountProject() && !selectedEmployeeRequest && !selectedEmployee){
    toast('Select an employee first','var(--red)');
    return;
  }
  selectedAccountRequest=null;
  document.getElementById('acct-dropdown-request').classList.add('open');
  populateAccountDropdownRequest();
}

function populateAccountDropdownRequest(employeeObj){
  const input=document.getElementById('rqacct');
  const list=document.getElementById('acct-dropdown-list-request');

  if(requestUsesRoleScopedAccountProject()){
    const search=input.value.toLowerCase();
    const accounts=requestScopedAccountNames();
    const results=accounts.filter(a=>String(a).toLowerCase().includes(search));
    if(results.length===0){
      list.innerHTML='<div class="searchable-dropdown-empty">No accounts found in your scope</div>';
    }else{
      list.innerHTML=results.map(acctName=>{
        const safeAcctName=String(acctName).replace(/'/g,"\\'");
        return `<div class="searchable-dropdown-item" onclick="selectAccountRequest('${safeAcctName}')">${acctName}</div>`;
      }).join('');
    }
    return;
  }
  
  // Check both form contexts
  if(!employeeObj){
    if(selectedEmployeeRequest){
      employeeObj=EMPS.find(e=>String(e.id)===String(selectedEmployeeRequest.id));
    } else if(selectedEmployee){
      employeeObj=EMPS.find(e=>String(e.id)===String(selectedEmployee.id));
    }
  }
  
  if(!employeeObj){
    list.innerHTML='<div class="searchable-dropdown-empty">Select an employee first</div>';
    return;
  }
  
  // Get unique accounts that THIS EMPLOYEE is assigned to
  // Check for multiple EMPS records with same employee ID (different accounts/projects)
  const employeeAccounts=new Set();
  const empId=String(employeeObj.id);
  
  // First, add the employee's primary account
  if(employeeObj.acct){
    employeeAccounts.add(employeeObj.acct);
  }
  
  // Use the dedicated assignments array if available (includes all account/project combos)
  if(Array.isArray(employeeObj.assignments) && employeeObj.assignments.length > 0){
    employeeObj.assignments.forEach(a => {
      if(a.acct) employeeAccounts.add(a.acct);
    });
  } else {
    // Fallback: scan all EMPS entries for the same employee (legacy path)
    EMPS.forEach(emp => {
      if(String(emp.id) === empId && emp.acct){
        employeeAccounts.add(emp.acct);
      }
    });
  }
  
  // If no accounts found in EMPS, try to infer from projects
  if(employeeAccounts.size === 0){
    // Fallback: get all accounts from PROJ_META
    Object.keys(PROJ_META).forEach(projName=>{
      const meta=PROJ_META[projName]||{};
      if(meta.acct)employeeAccounts.add(meta.acct);
    });
  }
  
  const accounts=Array.from(employeeAccounts).sort();
  const search=input.value.toLowerCase();
  const results=accounts.filter(a=>String(a).toLowerCase().includes(search));
  
  if(results.length===0){
    list.innerHTML='<div class="searchable-dropdown-empty">No accounts found for this employee</div>';
  }else{
    list.innerHTML=results.map(acctName=>{
      const safeAcctName=String(acctName).replace(/'/g,"\\'");
      return `<div class="searchable-dropdown-item" onclick="selectAccountRequest('${safeAcctName}')">${acctName}</div>`;
    }).join('');
  }
}

function selectAccountRequest(acctName){
  selectedAccountRequest={name:acctName};
  selectedProject=null;
  
  const isMRForm = !selectedEmployeeRequest && !!selectedEmployee;
  if(isMRForm){
    document.getElementById('mr-acct').value=acctName;
    document.getElementById('mr-acct-dropdown').classList.remove('open');
    selectedProjectRequest=null;
    document.getElementById('mr-proj').value='';
    document.getElementById('mr-gdl').value='';
    // Populate projects for the selected account in MR form and return
    filterProjectsManual();
    return;
  }
  
  document.getElementById('rqacct').value=acctName;
  document.getElementById('acct-dropdown-request').classList.remove('open');
  selectedProjectRequest=null;
  document.getElementById('rqproj').value='';
  setRequestGdlValue('');
  
  // Check both form contexts for the employee object
  let employeeObj=null;
  if(selectedEmployeeRequest){
    employeeObj=EMPS.find(e=>String(e.id)===String(selectedEmployeeRequest.id));
  } else if(selectedEmployee){
    employeeObj=EMPS.find(e=>String(e.id)===String(selectedEmployee.id));
  }
  
  populateProjectsForAccountRequest(employeeObj, acctName);
  
  // Auto-select first available project for this account
  if(requestUsesRoleScopedAccountProject()){
    const scopedProjects=requestScopedProjectNames(acctName);
    if(scopedProjects.length > 0){
      selectProjectRequestWithAccount(scopedProjects[0]);
    }
  } else if(employeeObj && Array.isArray(employeeObj.assignments) && employeeObj.assignments.length > 0){
    const projectsForAccount = new Set();
    employeeObj.assignments.forEach(a => {
      if(a.acct === acctName && a.proj) projectsForAccount.add(a.proj);
    });
    if(projectsForAccount.size > 0){
      const firstProject = Array.from(projectsForAccount).sort()[0];
      selectProjectRequestWithAccount(firstProject);
    }
  }
}

function populateProjectsForAccountRequest(employeeObj, accountName){
  const list=document.getElementById('proj-dropdown-list-request');
  
  if(!accountName){
    list.innerHTML='<div class="searchable-dropdown-empty">Select an account first</div>';
    return;
  }
  
  let accountProjects=[];
  if(requestUsesRoleScopedAccountProject()){
    accountProjects=requestScopedProjectNames(accountName);
  }else{
    const employeeId = selectedEmployeeRequest ? selectedEmployeeRequest.id : (employeeObj ? employeeObj.id : null);
    const empRecord = employeeId ? EMPS.find(e => String(e.id) === String(employeeId)) : null;
    const employeeProjectsForAccount = new Set();
    if(empRecord && Array.isArray(empRecord.assignments) && empRecord.assignments.length > 0){
      empRecord.assignments.forEach(a => {
        if(a.acct === accountName && a.proj) employeeProjectsForAccount.add(a.proj);
      });
      if(empRecord.acct === accountName && empRecord.proj) employeeProjectsForAccount.add(empRecord.proj);
    } else if(employeeId){
      EMPS.forEach(emp => {
        if(String(emp.id) === String(employeeId) && String(emp.acct) === String(accountName) && emp.proj){
          employeeProjectsForAccount.add(emp.proj);
        }
      });
    }
    accountProjects=Array.from(employeeProjectsForAccount).sort();
  }
  
  if(accountProjects.length===0){
    list.innerHTML='<div class="searchable-dropdown-empty">No projects for this account</div>';
    return;
  }
  
  const input=document.getElementById('rqproj');
  const search=input.value.toLowerCase();
  const results=accountProjects.filter(p=>String(p).toLowerCase().includes(search));
  
  if(results.length===0){
    list.innerHTML='<div class="searchable-dropdown-empty">No matching projects</div>';
  }else{
    list.innerHTML=results.map(projName=>{
      const safeProjName=String(projName).replace(/'/g,"\\'");
      return `<div class="searchable-dropdown-item" onclick="selectProjectRequestWithAccount('${safeProjName}')">${projName}</div>`;
    }).join('');
  }
}

function selectProjectRequestWithAccount(projName){
  // Look up project ID: first try PROJECTS array, then PROJ_META, then employee's proj_id
  const projRecord=Array.isArray(window.PROJECTS)?window.PROJECTS.find(p=>p.name===projName):null;
  let projId=projRecord?projRecord.id:(PROJ_META[projName]?PROJ_META[projName].id:null);
  // Fallback: check employee's own proj_id if project name matches
  if(!projId){
    const empObj=selectedEmployee?EMPS.find(e=>String(e.id)===String(selectedEmployee.id)):
                 (selectedEmployeeRequest?EMPS.find(e=>String(e.id)===String(selectedEmployeeRequest.id)):null);
    if(empObj && empObj.proj===projName && empObj.proj_id) projId=empObj.proj_id;
    // Also check assignments array for proj_id
    if(!projId && empObj && Array.isArray(empObj.assignments)){
      const asgn=empObj.assignments.find(a=>a.proj===projName);
      if(asgn && asgn.proj_id) projId=asgn.proj_id;
    }
  }
  selectedProjectRequest={name:projName,id:projId};
  selectedProject={name:projName,id:projId};  // Also set for manual request form context
  
  // Determine which form is active and update the correct element
  const isMRForm = !selectedEmployeeRequest && !!selectedEmployee;
  if(isMRForm){
    document.getElementById('mr-proj').value=projName;
    document.getElementById('mr-proj-dropdown').classList.remove('open');
    const mrGdlField=document.getElementById('mr-gdl');
    if(mrGdlField) mrGdlField.value=(PROJ_META[projName]||{}).gdl||'';
  } else {
    document.getElementById('rqproj').value=projName;
    document.getElementById('proj-dropdown-request').classList.remove('open');
    setRequestGdlValue((PROJ_META[projName]||{}).gdl||'');
  }
}

function populateProjectDropdownRequest(){
  if(!selectedAccountRequest){
    const list=document.getElementById('proj-dropdown-list-request');
    list.innerHTML='<div class="searchable-dropdown-empty">Select an account first</div>';
    return;
  }
  populateProjectsForAccountRequest(null, selectedAccountRequest.name);
}

function selectProjectRequest(name){
  selectedProjectRequest={name};
  selectedProject={name};  // Also set for manual request form context
  document.getElementById('rqproj').value=name;
  document.getElementById('proj-dropdown-request').classList.remove('open');
  // Update GDL from PROJ_META based on selected project
  const meta=PROJ_META[name]||{};
  // Update GDL in both forms (they have different field IDs)
  setRequestGdlValue(meta.gdl||'');
  const mrGdlField=document.getElementById('mr-gdl');
  if(mrGdlField) mrGdlField.value=meta.gdl||'';
}

async function addMR(){
  const emp=document.getElementById('mr-emp').value.trim();
  const plat=document.getElementById('mr-plat').value;
  const type=document.getElementById('mr-type').value.toLowerCase();
  const proj=document.getElementById('mr-proj').value.trim();
  const by=document.getElementById('mr-by').value.trim()||(JSON.parse(sessionStorage.getItem('licenseiq_session')||'{}').name)||'License Admin';
  const dt=document.getElementById('mr-dt').value;
  const reason=document.getElementById('mr-reason').value.trim();
  
  if(!emp||!plat||!proj){toast('Employee, platform and project are required','var(--red)');return;}
  if(!selectedEmployee){toast('Please select an employee from the dropdown','var(--red)');return;}
  if(!selectedPlatformManual){toast('Please select a platform from the dropdown','var(--red)');return;}
  if(!selectedProject||!selectedProject.name){toast('Please select a project from the dropdown','var(--red)');return;}
  if(!dt){toast('Select effective date','var(--red)');return;}
  const employeeRecord=EMPS.find(e=>String(e.id)===String(selectedEmployee.id));
  if(type==='assign'&&employeeHasActiveLicense(employeeRecord,plat)){
    toast(`${emp} already has ${plat} assigned.`,'var(--red)');
    return;
  }
  if(type==='assign'&&hasPendingAssignInQueue(emp,plat)){
    toast(`An assign request for ${emp} and ${plat} is already pending.`,'var(--red)');
    return;
  }
  
  try{
    setContentLoading(true);
    await fetchJson(`${API_BASE}/queue`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({
        employee_id:parseInt(selectedEmployee.id)||selectedEmployee.id,
        employee_name:emp,
        platform_name:plat,
        action_type:type,
        project_id:parseInt(selectedProject.id)||selectedProject.id,
        project_name:proj,
        created_by:by,
        effective_date:dt,
        source_type:'manual',
        execution_notes:reason
      })
    },'Failed to add manual request.');
    
    await loadBackendData();
    renderQueue();
    document.getElementById('mr-emp').value='';
    document.getElementById('mr-plat').value='';
    document.getElementById('mr-proj').value='';
    document.getElementById('mr-acct').value='';
    document.getElementById('mr-gdl').value='';
    try{const s=JSON.parse(sessionStorage.getItem('licenseiq_session')||'{}');document.getElementById('mr-by').value=s.name||'';}catch(e){}
    document.getElementById('mr-dt').value=new Date().toISOString().slice(0,10);
    document.getElementById('mr-reason').value='';
    selectedEmployee=null;
    selectedPlatformManual=null;
    selectedProject=null;
    
    togMR();
    toast('! Manual request saved to DB!','#0F6E56');
  }catch(e){
    console.error('Error:',e);
    toast(licenseiqUserError(e,'Failed to save manual request.'),'var(--red)');
  }finally{
    setContentLoading(false);
  }
}
function renderQueue(){
  const ql=document.getElementById('ql');if(!ql)return;
  let pendingQueue=queue.filter(q=>q.status!=='executed'&&q.status!=='rejected'&&(q.status==='pending'||q.approval_stage==='pending_account_owner'||q.approval_stage==='pending_it_admin'));
  
  // Apply search filter
  if(queueSearchFilter){
    const search=queueSearchFilter;
    pendingQueue=pendingQueue.filter(q=>{
      const emp=(q.emp||'').toLowerCase();
      const empId=String(q.emp_id||'').toLowerCase();
      const empDisplayId=displayEmpIdByRef(q.emp_id||'').toLowerCase();
      const plat=(q.plat||'').toLowerCase();
      const proj=(q.proj||'').toLowerCase();
      const by=(q.by||'').toLowerCase();
      return emp.includes(search)||empId.includes(search)||empDisplayId.includes(search)||plat.includes(search)||proj.includes(search)||by.includes(search);
    });
  }
  
  ql.innerHTML=pendingQueue.length===0?'<div style="text-align:center;color:var(--gray2);padding:36px;background:var(--white);border-radius:9px;border:1px solid var(--border);">Queue is clear - all done!</div>'
    :pendingQueue.map(q=>{
      // Determine approval status badge
      let approvalBadge='';
      if(q.approval_stage==='self_approved'||q.status==='completed'){
        approvalBadge='<span class="pill psa">Self-approved !</span>';
      }else if(q.approval_stage==='pending_account_owner'){
        approvalBadge='<span class="pill prev" style="background:#fff3cd;color:#856404;">Pending Account Owner</span>';
      }else if(q.approval_stage==='pending_it_admin'){
        approvalBadge='<span class="pill prev" style="background:#cfe2ff;color:#084298;">Pending IT Admin</span>';
      }else if(q.approval_stage==='approved'){
        approvalBadge='<span class="pill pass">Approved !</span>';
      }else if(q.approval_stage==='rejected'){
        approvalBadge='<span class="pill" style="background:#f8d7da;color:#842029;">Rejected</span>';
      }else{
        approvalBadge='<span class="pill psa">Self-approved !</span>';
      }
      
      // Determine if current user can approve at this stage
      const isItAdmin=(role==='admin'||role==='it_admin');
      const canApproveAtStage=(q.approval_stage==='pending_account_owner'&&(role==='account_owner'||isItAdmin))||(q.approval_stage==='pending_it_admin'&&isItAdmin);
      
      // Render approval buttons (right-side)
      let approvalButtons='';
      if(canApproveAtStage){
        approvalButtons=`
          <div style="display:flex;flex-direction:row;gap:8px;align-items:center;flex-shrink:0;">
            <button class="btn" style="font-size:11px;white-space:nowrap;font-weight:600;background:#1e7e45;color:#fff;border:1.5px solid #176338;border-radius:7px;padding:6px 14px;box-shadow:0 2px 5px rgba(30,126,69,.3);transition:background .15s,box-shadow .15s,transform .1s;" onmouseover="this.style.background='#176338';this.style.boxShadow='0 3px 10px rgba(30,126,69,.45)';this.style.transform='scale(1.03)'" onmouseout="this.style.background='#1e7e45';this.style.boxShadow='0 2px 5px rgba(30,126,69,.3)';this.style.transform='scale(1)'" onclick="approveRequest(${q.source_id},'approved')">&#10003; Approve</button>
            <button class="btn" style="font-size:11px;white-space:nowrap;font-weight:600;background:#c0392b;color:#fff;border:1.5px solid #a93226;border-radius:7px;padding:6px 14px;box-shadow:0 2px 5px rgba(192,57,43,.3);transition:background .15s,box-shadow .15s,transform .1s;" onmouseover="this.style.background='#a93226';this.style.boxShadow='0 3px 10px rgba(192,57,43,.45)';this.style.transform='scale(1.03)'" onmouseout="this.style.background='#c0392b';this.style.boxShadow='0 2px 5px rgba(192,57,43,.3)';this.style.transform='scale(1)'" onclick="approveRequest(${q.source_id},'rejected')">&#10005; Reject</button>
          </div>
        `;
      }else if(q.approval_stage==='approved'||q.approval_stage==='self_approved'||!q.approval_stage||q.status==='completed'){
        approvalButtons=`
          <div style="display:flex;flex-direction:row;gap:8px;align-items:center;flex-shrink:0;">
            <button class="btn" style="font-size:11px;white-space:nowrap;font-weight:600;background:#1e7e45;color:#fff;border:1.5px solid #176338;border-radius:7px;padding:6px 14px;box-shadow:0 2px 5px rgba(30,126,69,.3);transition:background .15s,box-shadow .15s,transform .1s;" onmouseover="this.style.background='#176338';this.style.boxShadow='0 3px 10px rgba(30,126,69,.45)';this.style.transform='scale(1.03)'" onmouseout="this.style.background='#1e7e45';this.style.boxShadow='0 2px 5px rgba(30,126,69,.3)';this.style.transform='scale(1)'" onclick="markDone(${q.id})">&#10003; Approve</button>
            <button class="btn" style="font-size:11px;white-space:nowrap;font-weight:600;background:#c0392b;color:#fff;border:1.5px solid #a93226;border-radius:7px;padding:6px 14px;box-shadow:0 2px 5px rgba(192,57,43,.3);transition:background .15s,box-shadow .15s,transform .1s;" onmouseover="this.style.background='#a93226';this.style.boxShadow='0 3px 10px rgba(192,57,43,.45)';this.style.transform='scale(1.03)'" onmouseout="this.style.background='#c0392b';this.style.boxShadow='0 2px 5px rgba(192,57,43,.3)';this.style.transform='scale(1)'" onclick="rejectQueueItem(${q.id})">&#10005; Reject</button>
          </div>
        `;
      }
      
      // Resolve employee name: server name or lookup from EMPS/REQUEST_EMPLOYEES by emp_id
      const qEmpFromEmps=q.emp_id?findEmployeeByRef(q.emp_id):null;
      const qEmpName=(qEmpFromEmps&&qEmpFromEmps.name&&qEmpFromEmps.name!=='Unknown')?qEmpFromEmps.name:(q.emp||'Unknown');
      const qEmpDisplayId=q.emp_id?displayEmpIdByRef(q.emp_id):'';
      return `<div class="queue-card" data-queue-id="${q.id}" style="background:var(--white);border:1px solid var(--border);border-radius:9px;padding:12px 15px;margin-bottom:9px;">
        <div style="display:flex;align-items:center;gap:12px;">
          <div style="flex:1;">
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:3px;">
              <span style="font-size:13px;font-weight:700;">${qEmpName}${qEmpDisplayId?` <span style="color:var(--gray2);">(#${qEmpDisplayId})</span>`:''} > ${q.plat}</span>
              <span class="pill ${q.type==='assign'?'pass':'prev'}">${q.type}</span>
              ${approvalBadge}
              ${q.manual?'<span class="pill pmd">Manual</span>':''}
            </div>
            <div style="font-size:11px;color:var(--gray2);">By: <strong style="color:var(--black);">${q.by}</strong> ~ ${q.date}${q.cost?` ~ ${fmt(q.cost)}/Mth`:''} ~ ${q.proj}</div>
          </div>
          ${approvalButtons}
        </div>
      </div>`;
    }).join('');
}

let approvalsSearchFilter='';
function filterApprovals(){approvalsSearchFilter=(document.getElementById('approvals-search')?.value||'').toLowerCase().trim();renderApprovals();}

async function loadApprovalHistory(){
  try{
    // Ensure employee pool is loaded so names resolve in the table
    await ensureRequestEmployeesLoaded();
    const staffid=sessionStorage.getItem('staffid')||'';
    const url=staffid?`${API_BASE}/requests/history?staffid=${encodeURIComponent(staffid)}`:`${API_BASE}/requests/history`;
    approvalHistory=await fetchJson(url,{},'');
  }catch(e){
    approvalHistory=[];
  }
  renderApprovalsHistory();
}

function exportApprovalHistory(format){
  if(!approvalHistory||approvalHistory.length===0){
    toast('No approval history to export','var(--red)');
    return;
  }
  const empPool=[...(REQUEST_EMPLOYEES||[]),...(EMPS||[])];
  const resolveName=(staffid)=>{
    if(!staffid)return'—';
    const sid=String(staffid);
    const found=empPool.find(e=>String(e.id)===sid||String(e.code||'')===sid);
    return found?.name||null;
  };
  const resolveDisplayId=(staffid)=>{
    if(!staffid)return'';
    return displayEmpIdByRef(staffid);
  };
  const fmt_date=iso=>{
    if(!iso)return'—';
    const d=new Date(iso);
    const day=String(d.getDate()).padStart(2,'0');
    const mon=d.toLocaleString('en-GB',{month:'short'});
    const yr=String(d.getFullYear()).slice(2);
    let h=d.getHours(),m=String(d.getMinutes()).padStart(2,'0'),ampm=h>=12?'PM':'AM';
    h=h%12||12;
    return `${day}-${mon}-${yr} ${h}:${m} ${ampm}`;
  };
  if(format==='csv'){
    const headers=['Emp ID','Employee','Platform','Type','Request Raised On','Raised By','Your Action','Status','Notes'];
    const rows=approvalHistory.map(h=>{
      const empName=resolveName(h.employee_id)||h.employee_name||`#${resolveDisplayId(h.employee_id) || h.employee_id}`;
      const raisedBy=resolveName(h.requested_by)||h.raised_by||(h.requested_by?`Staff ${h.requested_by}`:'—');
      const statusLabel=h.current_stage==='approved'||h.current_status==='executed'?'Executed':h.current_stage==='pending_it_admin'?'IT Admin pending':'Rejected';
      return[
        resolveDisplayId(h.employee_id)||h.employee_id||'',
        empName,
        h.platform_name||'',
        h.request_type||'',
        fmt_date(h.raised_on),
        raisedBy,
        h.action==='approved'?'Approved':'Rejected',
        statusLabel,
        h.notes||''
      ].map(v=>`"${String(v).replace(/"/g,'""')}"`).join(',');
    });
    const csv=[headers.join(','),...rows].join('\n');
    const blob=new Blob([csv],{type:'text/csv;charset=utf-8;'});
    const link=document.createElement('a');
    link.href=URL.createObjectURL(blob);
    link.download=`approval_history_${new Date().toISOString().slice(0,10)}.csv`;
    link.click();
    toast('! CSV exported','#0F6E56');
  }else if(format==='pdf'){
    try{
      const {jsPDF}=window.jspdf;
      const doc=new jsPDF();
      const pageWidth=doc.internal.pageSize.getWidth();
      const pageHeight=doc.internal.pageSize.getHeight();
      const margin=10;
      let yPos=margin;
      doc.setFontSize(16);
      doc.text('Approval History Report',margin,yPos);
      yPos+=10;
      doc.setFontSize(10);
      doc.setTextColor(100);
      doc.text(`Generated: ${new Date().toLocaleString()}`,margin,yPos);
      yPos+=10;
      doc.setDrawColor(200);
      doc.line(margin,yPos,pageWidth-margin,yPos);
      yPos+=8;
      const tableData=approvalHistory.map(h=>{
        const empName=resolveName(h.employee_id)||h.employee_name||`#${resolveDisplayId(h.employee_id) || h.employee_id}`;
        const raisedBy=resolveName(h.requested_by)||h.raised_by||(h.requested_by?`Staff ${h.requested_by}`:'—');
        const statusLabel=h.current_stage==='approved'||h.current_status==='executed'?'Executed':h.current_stage==='pending_it_admin'?'IT Admin pending':'Rejected';
        return[resolveDisplayId(h.employee_id)||h.employee_id||'',empName,h.platform_name||'',h.request_type||'',fmt_date(h.raised_on),raisedBy,h.action==='approved'?'Approved':'Rejected',statusLabel,h.notes||''];
      });
      doc.autoTable({
        head:[['Emp ID','Employee','Platform','Type','Raised On','Raised By','Action','Status','Notes']],
        body:tableData,
        startY:yPos,
        margin:margin,
        styles:{fontSize:9,cellPadding:3,halign:'left',valign:'top',textColor:30},
        headStyles:{fillColor:102,textColor:255,fontStyle:'bold'},
        alternateRowStyles:{fillColor:245},
        columnStyles:{0:{halign:'center',cellWidth:12},3:{halign:'center',cellWidth:12},6:{halign:'center',cellWidth:12},7:{halign:'center',cellWidth:20}},
        didDrawPage:(data)=>{
          doc.setFontSize(8);
          doc.setTextColor(150);
          doc.text(`Page ${data.pageCount}`,pageWidth-margin-10,pageHeight-5);
        }
      });
      doc.save(`approval_history_${new Date().toISOString().slice(0,10)}.pdf`);
      toast('! PDF exported','#0F6E56');
    }catch(e){
      if(!window.jspdf){
        toast('PDF library not available. Install jsPDF to enable PDF export.','var(--red)');
      }else{
        toast(licenseiqUserError(e,'Failed to generate PDF.'),'var(--red)');
      }
    }
  }
}

function renderApprovalsHistory(){
  const el=document.getElementById('approvals-history');if(!el)return;
  if(!approvalHistory||approvalHistory.length===0){el.innerHTML='';return;}
  const fmt_date=iso=>{
    if(!iso)return'—';
    const d=new Date(iso);
    const day=String(d.getDate()).padStart(2,'0');
    const mon=d.toLocaleString('en-GB',{month:'short'});
    const yr=String(d.getFullYear()).slice(2);
    let h=d.getHours(),m=String(d.getMinutes()).padStart(2,'0'),ampm=h>=12?'PM':'AM';
    h=h%12||12;
    return `${day}-${mon}-${yr} ${h}:${m} ${ampm}`;
  };
  // Build a staffid→name lookup from all available employee pools
  // REQUEST_EMPLOYEES uses Aspire staff ID as `id`; EMPS uses DB PK as `id` but has `code`
  const empPool=[...(REQUEST_EMPLOYEES||[]),...(EMPS||[])];
  const resolveName=(staffid)=>{
    if(!staffid)return'—';
    const sid=String(staffid);
    const found=empPool.find(e=>String(e.id)===sid||String(e.code||'')===sid);
    return found?.name||null;
  };
  const resolveDisplayId=(staffid)=>{
    if(!staffid)return'—';
    return displayEmpIdByRef(staffid)||'—';
  };
  const rows=approvalHistory.map(h=>{
    const actionCls=h.action==='approved'?'pass':'prev';
    const actionLabel=h.action==='approved'?'Approved':'Rejected';
    const stagePill=h.current_stage==='approved'||h.current_status==='executed'
      ?`<span class="pill pa" style="font-size:10px;">Executed</span>`
      :h.current_stage==='pending_it_admin'
        ?`<span class="pill pm" style="font-size:10px;">IT Admin pending</span>`
        :`<span class="pill pi" style="font-size:10px;">Rejected</span>`;
    const empName=resolveName(h.employee_id)||h.employee_name||`#${resolveDisplayId(h.employee_id) || h.employee_id}`;
    const raisedBy=resolveName(h.requested_by)||h.raised_by||(h.requested_by?`Staff ${h.requested_by}`:'—');
    return `<tr>
      <td style="font-size:11px;color:var(--gray2);">${resolveDisplayId(h.employee_id)}</td>
      <td style="font-size:12px;font-weight:600;">${empName}</td>
      <td style="font-size:12px;">${h.platform_name}</td>
      <td style="font-size:12px;"><span class="pill ${h.request_type==='assign'?'pass':'prev'}">${h.request_type}</span></td>
      <td style="font-size:11px;color:var(--gray2);">${fmt_date(h.raised_on)}</td>
      <td style="font-size:12px;">${raisedBy}</td>
      <td><span class="pill ${actionCls}" style="font-size:10px;">${actionLabel}</span></td>
      <td>${stagePill}</td>
      <td style="font-size:11px;color:var(--gray2);">${h.notes||'—'}</td>
    </tr>`;
  }).join('');
  el.innerHTML=`
    <div style="margin-top:28px;">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:15px;">
        <div style="font-size:12px;font-weight:700;color:var(--gray2);text-transform:uppercase;letter-spacing:.5px;">History - your past decisions</div>
        <div style="display:flex;gap:8px;">
          <button onclick="exportApprovalHistory('csv')" style="display:flex;align-items:center;gap:6px;padding:6px 12px;background:#f0f0f0;border:1px solid #ddd;border-radius:4px;cursor:pointer;font-size:11px;font-weight:600;" title="Export as CSV">
            <img src="/static/img/sheets.png" alt="CSV" style="width:16px;height:16px;">
            CSV
          </button>
          <button onclick="exportApprovalHistory('pdf')" style="display:flex;align-items:center;gap:6px;padding:6px 12px;background:#f0f0f0;border:1px solid #ddd;border-radius:4px;cursor:pointer;font-size:11px;font-weight:600;" title="Export as PDF">
            <img src="/static/img/pdfepx.jpg" alt="PDF" style="width:16px;height:16px;">
            PDF
          </button>
        </div>
      </div>
      <div style="background:var(--white);border:1px solid var(--border);border-radius:9px;overflow:hidden;">
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr style="background:var(--tan2);">
              <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:700;color:var(--gray2);">Emp ID</th>
              <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:700;color:var(--gray2);">Employee</th>
              <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:700;color:var(--gray2);">Platform</th>
              <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:700;color:var(--gray2);">Type</th>
              <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:700;color:var(--gray2);">Request raised on</th>
              <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:700;color:var(--gray2);">Raised by</th>
              <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:700;color:var(--gray2);">Your action</th>
              <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:700;color:var(--gray2);">Status</th>
              <th style="padding:9px 12px;text-align:left;font-size:11px;font-weight:700;color:var(--gray2);">Notes</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </div>`;
}

function renderApprovals(){
  const el=document.getElementById('approvals-list');if(!el)return;
  let pending=queue.filter(q=>q.approval_stage==='pending_account_owner');
  if(approvalsSearchFilter){
    const s=approvalsSearchFilter;
    pending=pending.filter(q=>(q.emp||'').toLowerCase().includes(s)||(q.plat||'').toLowerCase().includes(s)||(q.proj||'').toLowerCase().includes(s)||(q.by||'').toLowerCase().includes(s));
  }
  if(pending.length===0){
    el.innerHTML='<div style="text-align:center;color:var(--gray2);padding:36px;background:var(--white);border-radius:9px;border:1px solid var(--border);">No pending approvals - you\'re all caught up!</div>';
    return;
  }
  el.innerHTML=pending.map(q=>{
    const aEmpFromEmps=q.emp_id?findEmployeeByRef(q.emp_id):null;
    const aEmpName=(aEmpFromEmps&&aEmpFromEmps.name&&aEmpFromEmps.name!=='Unknown')?aEmpFromEmps.name:(q.emp||'Unknown');
    const aEmpDisplayId=q.emp_id?displayEmpIdByRef(q.emp_id):'';
    return `
    <div class="queue-card" data-queue-id="${q.id}" style="background:var(--white);border:1px solid #ffc10740;border-radius:9px;padding:14px 16px;margin-bottom:10px;border-left:4px solid #ffc107;">
      <div style="display:flex;align-items:flex-start;gap:12px;">
        <div style="flex:1;">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px;">
            <span style="font-size:13px;font-weight:700;">${aEmpName}${aEmpDisplayId?` <span style="color:var(--gray2);">(#${aEmpDisplayId})</span>`:''}</span>
            <span style="font-size:13px;"> - ${q.plat}</span>
            <span class="pill ${q.type==='assign'?'pass':'prev'}">${q.type}</span>
            <span class="pill" style="background:#fff3cd;color:#856404;font-size:10px;">Awaiting your approval</span>
          </div>
          <div style="font-size:11px;color:var(--gray2);margin-bottom:10px;">
            Raised by: <strong style="color:var(--black);">${q.by}</strong> ~ ${q.date}${q.cost?` ~ ${fmt(q.cost)}/Mth`:''} ~ ${q.proj}
          </div>
          <div style="display:flex;gap:8px;">
            <button class="btn blm" style="font-size:11px;padding:5px 14px;" onclick="approveRequest(${q.source_id},'approved')">> Approve</button>
            <button class="btn" style="font-size:11px;padding:5px 14px;background:#fff0f0;color:#c0392b;border-color:#f5c6cb;" onclick="approveRequest(${q.source_id},'rejected')">X Reject</button>
          </div>
          <div style="font-size:11px;color:var(--gray2);">By: <strong style="color:var(--black);">${q.by}</strong> ~ ${q.date}${q.cost?` ~ ${fmt(q.cost)}/mo`:''} ~ ${trunc(q.proj)}</div>
        </div>
      </div>
    </div>`;
  }).join('');
}

function animateQueueRemoval(id){
  const card=document.querySelector(`[data-queue-id="${id}"]`);
  if(!card)return Promise.resolve();
  return new Promise(resolve=>{
    card.classList.add('fade-out');
    setTimeout(resolve,260);
  });
}
async function markDone(id){
  try{
    await fetchJson(`${API_BASE}/queue/${id}/execute`,{
      method:'PATCH',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({executed_by_user_id:null,execution_notes:'Executed via admin queue'})
    },'Failed to execute queue item.');
    await animateQueueRemoval(id);
    queue=queue.filter(q=>q.id!==id);
    renderQueue();
    updateNavBadges();
    toast('! License action executed and saved to DB','#0F6E56');
    await loadBackendData();
    refreshCurrentPage(false);
  }catch(e){
    toast(licenseiqUserError(e,'Failed to execute queue item.'),'var(--red)');
  }
}

async function rejectQueueItem(id){
  const notes=prompt('Reason for rejection:');
  if(!notes){
    toast('Rejection reason is required','var(--red)');
    return;
  }
  try{
    await fetchJson(`${API_BASE}/queue/${id}/reject`,{
      method:'PATCH',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({rejected_by_user_id:null,rejection_notes:notes})
    },'Failed to reject queue item.');
    queue=queue.filter(q=>q.id!==id);
    renderQueue();
    updateNavBadges();
    notifyWithPush('X Request Rejected','The license request has been rejected.','var(--red)');
  }catch(e){
    toast(licenseiqUserError(e,'Failed to reject queue item.'),'var(--red)');
  }
}

async function approveRequest(id, action){
  const notes=action==='rejected'?prompt('Reason for rejection:'):'Approved';
  if(action==='rejected'&&!notes){
    toast('Rejection reason is required','var(--red)');
    return;
  }
  
  try{
    const response=await fetchJson(`${API_BASE}/requests/${id}/approve`,{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action:action,notes:notes})
    },`Failed to ${action} request.`);
    
    // Show a persistent loading hint while the heavy data reload runs
    const loadingToast = document.getElementById('toast');
    if(loadingToast){
      loadingToast.style.background='#475569';
      loadingToast.style.display='block';
      loadingToast.innerHTML=`<div style="display:flex;align-items:center;gap:10px;">
        <span style="display:inline-block;width:15px;height:15px;border:2.5px solid rgba(255,255,255,0.3);border-top-color:#fff;border-radius:50%;animation:licenseiq-spin 0.7s linear infinite;flex-shrink:0;"></span>
        <div class="toast-msg" style="flex:1;">Updating license register — please wait...</div>
      </div>`;
      clearTimeout(loadingToast._toastTimer);
    }

    // Reload full backend data — always correct scope (org_level for admin),
    // syncs queue, EMPS, and license register in one shot.
    // forceRefresh=true bypasses browser cache so the new allocation is visible immediately.
    await loadBackendData(true);
    renderQueue();
    if(typeof renderApprovals==='function') renderApprovals();
    loadApprovalHistory();
    updateNavBadges();
    refreshCurrentPage(false);
    
    if(action==='approved'){
      const msg=response.approval_status==='executed'
        ?'! Approved and executed! License has been added to the register.'
        :'! Approved > moved to IT Admin for final sign-off.';
      notifyWithPush('! Request Approved',msg,'#0F6E56');
    } else {
      notifyWithPush('X Request Rejected','The license request has been rejected.','var(--red)');
    }
  }catch(e){
    toast(licenseiqUserError(e,`Failed to ${action} request.`),'var(--red)');
  }
}

// ─────────── DISTRIBUTION ───────────────────────────────
function renderDist(){}
function setDT(t){
  distTab=t;['unit','account','platform'].forEach(k=>{const b=document.getElementById('dt-'+k);if(b)b.className='stab'+(k===t?' on':'');const p=document.getElementById('dp-'+k);if(p)p.style.display=k===t?'block':'none';});
  if(t==='unit')renderUnitDist();if(t==='account')renderAcctDist();if(t==='platform')renderPlatDist();
}
function renderUnitDist(){
  const totals={};UNITS.forEach(u=>{totals[u]={count:0,cost:0,emps:0};});
  EMPS.forEach(e=>{if(!totals[e.unit])return;totals[e.unit].emps++;e.lics.forEach(l=>{totals[e.unit].count++;totals[e.unit].cost+=l.cost;});});
  const maxC=Math.max(...Object.values(totals).map(t=>t.count),1);
  const cards=UNITS.map(u=>{const t=totals[u];return `<div style="background:var(--white);border:1px solid var(--border);border-radius:9px;padding:12px;text-align:center;"><div style="font-size:11px;font-weight:700;color:var(--gray2);text-transform:uppercase;letter-spacing:.4px;margin-bottom:7px;">${u}</div><div style="font-size:24px;font-weight:700;">${t.count}</div><div style="font-size:10px;color:var(--gray2);margin-top:3px;">${t.emps} employees</div><div style="font-size:10px;color:var(--gray2);">${fmt(t.cost)}/Mth</div><div style="height:3px;background:var(--lime);border-radius:2px;margin-top:8px;width:${Math.round(t.count/maxC*100)}%;min-width:4px;"></div></div>`;}).join('');
  const matrix={};PLATFORMS.forEach(p=>{matrix[p.name]={};UNITS.forEach(u=>{matrix[p.name][u]=0;});});
  EMPS.forEach(e=>e.lics.forEach(l=>{if(matrix[l.plat]&&matrix[l.plat][e.unit]!==undefined)matrix[l.plat][e.unit]++;}));
  const rows=PLATFORMS.map(p=>`<tr><td><strong>${p.name}</strong></td>${UNITS.map(u=>`<td style="text-align:center;">${matrix[p.name][u]>0?`<span style="background:var(--tan2);font-size:11px;font-weight:600;padding:2px 8px;border-radius:5px;">${matrix[p.name][u]}</span>`:'<span style="color:var(--tan3);">—</span>'}</td>`).join('')}<td style="text-align:center;font-weight:700;">${UNITS.reduce((s,u)=>s+(matrix[p.name][u]||0),0)}</td></tr>`).join('');
  const dp=document.getElementById('dp-unit');if(!dp)return;
  dp.innerHTML=`<div class="g5">${cards}</div><div class="card" style="padding:0;overflow-x:auto;"><table><thead><tr><th>Platform</th>${UNITS.map(u=>`<th style="text-align:center;">${u}</th>`).join('')}<th style="text-align:center;">Total</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
function renderAcctDist(){
  const acctMap={};EMPS.forEach(e=>{if(!acctMap[e.acctOwner])acctMap[e.acctOwner]={owner:e.acctOwner,accts:new Set(),emps:0,total:0,active:0,flagged:0,cost:0};acctMap[e.acctOwner].accts.add(e.acct);acctMap[e.acctOwner].emps++;e.lics.forEach(l=>{acctMap[e.acctOwner].total++;acctMap[e.acctOwner].cost+=l.cost;if(l.st==='active')acctMap[e.acctOwner].active++;else acctMap[e.acctOwner].flagged++;});});
  const rows=Object.values(acctMap).map((a,i)=>`<tr style="background:${i%2===0?'transparent':'#faf8f4'}"><td><strong>${a.owner}</strong></td><td style="color:var(--gray2);">${[...a.accts].join(', ')}</td><td>${a.emps}</td><td><strong>${a.total}</strong></td><td style="color:var(--green);font-weight:600;">${a.active}</td><td>${a.flagged>0?`<span style="color:var(--red);font-weight:600;">${a.flagged}</span>`:'0'}</td><td><strong>${fmt(a.cost)}</strong></td></tr>`).join('');
  const dp=document.getElementById('dp-account');if(!dp)return;
  dp.innerHTML=`<div class="card" style="padding:0;overflow-x:auto;"><table><thead><tr><th>Account owner</th><th>Account(s)</th><th>Employees</th><th>Total licenses</th><th>Active</th><th>Flagged</th><th>Monthly cost</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}
function renderPlatDist(){
  const content=PLATFORMS.map(p=>{const holders=EMPS.filter(e=>e.lics.some(l=>l.plat===p.name));const total=holders.length;const cost=holders.flatMap(e=>e.lics.filter(l=>l.plat===p.name)).reduce((s,l)=>s+l.cost,0);const bars=UNITS.filter(u=>holders.filter(e=>e.unit===u).length>0).map(u=>{const c=holders.filter(e=>e.unit===u).length;return `<div style="display:flex;align-items:center;gap:8px;margin-bottom:3px;"><span style="font-size:11px;color:var(--gray2);min-width:75px;">${u}</span><div style="flex:1;background:var(--tan2);border-radius:3px;height:4px;"><div style="width:${Math.round(c/Math.max(total,1)*100)}%;background:var(--lime);border-radius:3px;height:4px;"></div></div><span style="font-size:11px;font-weight:600;min-width:18px;text-align:right;">${c}</span></div>`;}).join('');
  return `<div style="padding:12px 0;border-bottom:1px solid var(--tan);"><div style="display:flex;align-items:center;gap:12px;margin-bottom:9px;"><span style="font-size:13px;font-weight:700;flex:1;">${p.name}</span><span style="font-size:18px;font-weight:700;">${total}</span><span style="font-size:11px;color:var(--gray2);">employees</span><span style="font-size:12px;font-weight:600;color:var(--gray);margin-left:8px;">${fmt(cost)}/Mth</span></div>${bars}</div>`;}).join('');
  const dp=document.getElementById('dp-platform');if(!dp)return;dp.innerHTML=`<div class="card"><div class="ctitle">Platform distribution by unit</div>${content}</div>`;
}

// ─────────── SEARCH ─────────────────────────────────────
function initSearch(){
  const pss=document.getElementById('pss');if(pss)pss.innerHTML='<option value="">— select platform —</option>'+PLATFORMS.map(p=>`<option>${p.name}</option>`).join('');
  const er=document.getElementById('er');if(er)er.innerHTML='<div style="text-align:center;color:var(--gray2);padding:28px;background:var(--white);border-radius:9px;border:1px solid var(--border);">Type an employee name or ID to search</div>';
  setST('emp');
}
function setST(t){srchTab=t;['emp','plat'].forEach(k=>{const b=document.getElementById('st-'+k);if(b)b.className='stab'+(k===t?' on':'');});document.getElementById('sp-emp').style.display=t==='emp'?'block':'none';document.getElementById('sp-plat').style.display=t==='plat'?'block':'none';}
async function srchEmp(){
  const q=document.getElementById('esrch').value.trim();const er=document.getElementById('er');
  if(!q){er.innerHTML='<div style="text-align:center;color:var(--gray2);padding:28px;background:var(--white);border-radius:9px;border:1px solid var(--border);">Type an employee name or ID to search</div>';return;}
  er.innerHTML='<div style="text-align:center;color:var(--gray2);padding:28px;background:var(--white);border-radius:9px;border:1px solid var(--border);">Searching...</div>';
  const ql=q.toLowerCase();
  const matches=EMPS.filter(e=>
    (e.name||'').toLowerCase().includes(ql)||
    String(e.code||'').toLowerCase().includes(ql)||
    String(e.id||'').toLowerCase().includes(ql)
  );
  if(!matches.length){er.innerHTML='<div style="text-align:center;color:var(--gray2);padding:28px;background:var(--white);border-radius:9px;border:1px solid var(--border);">No employees found</div>';return;}
  const sc={active:'pa',inactive:'pi',flagged:'pf',exited:'pe',bench:'pb'};
  er.innerHTML=matches.map(e=>{const total=e.lics.reduce((s,l)=>s+licenseDisplayCost(l),0);const lrows=e.lics.map(l=>`<div style="display:flex;align-items:center;gap:10px;padding:7px 10px;background:var(--white);border-radius:7px;margin-bottom:5px;border:1px solid var(--border);flex-wrap:wrap;"><div style="min-width:120px;font-size:12px;font-weight:600;">${l.plat}</div><div><span class="pill ${l.type==='Enterprise'?'pent':'ppu'}" style="font-size:9px;">${l.type}</span></div><div style="font-size:12px;color:var(--gray);">${fmt(licenseDisplayCost(l))}/mo</div><div><span class="pill ${sc[l.st]||'pf'}">${l.st}</span></div><div style="flex:1;font-size:11px;color:var(--gray2);">Last: ${l.last}</div></div>`).join('');
  return `<div style="background:var(--white);border:1px solid var(--border);border-radius:9px;overflow:hidden;margin-bottom:10px;"><div style="padding:11px 15px;display:flex;align-items:center;gap:11px;"><div style="width:34px;height:34px;border-radius:50%;background:var(--tan2);display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;">${e.name.split(' ').map(n=>n[0]).join('')}</div><div style="flex:1;"><div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;"><span style="font-size:14px;font-weight:700;">${e.name}</span><span class="pill punit">${e.unit}</span><span class="pill ${sc[e.status]||'pf'}">${e.status}</span><span style="background:var(--tan2);color:var(--gray);font-size:10px;font-weight:600;padding:2px 7px;border-radius:9px;">${e.lics.length} lic · ${fmt(total)}/mo</span></div><div style="font-size:11px;color:var(--gray2);margin-top:2px;">${displayEmpId(e)} · ${trunc(e.proj)} · ${trunc(e.acct)}</div></div></div><div style="border-top:1px solid var(--tan);padding:11px 15px;background:var(--tan);">${lrows}</div></div>`;}).join('');
}
function srchPlat(){
  const plat=document.getElementById('pss').value,unit=document.getElementById('psu').value,acct=document.getElementById('psa').value;
  const pr=document.getElementById('pr'),prc=document.getElementById('prc');
  if(!plat){pr.innerHTML='<div style="text-align:center;color:var(--gray2);padding:28px;background:var(--white);border-radius:9px;border:1px solid var(--border);">Select a platform</div>';prc.textContent='';return;}
  let matches=EMPS.filter(e=>e.lics.some(l=>l.plat===plat));
  if(unit)matches=matches.filter(e=>e.unit===unit);if(acct)matches=matches.filter(e=>e.acct===acct);
  prc.textContent=matches.length+' employees';
  const sc={active:'pa',inactive:'pi',flagged:'pf',exited:'pe',bench:'pb'};
  const totalCost=matches.flatMap(e=>e.lics.filter(l=>l.plat===plat)).reduce((s,l)=>s+licenseDisplayCost(l),0);
  const summary=`<div class="card" style="margin-bottom:11px;"><div style="display:flex;gap:14px;flex-wrap:wrap;"><div><div style="font-size:10px;color:var(--gray2);text-transform:uppercase;letter-spacing:.4px;">Platform</div><div style="font-size:14px;font-weight:700;">${plat}</div></div><div><div style="font-size:10px;color:var(--gray2);text-transform:uppercase;letter-spacing:.4px;">Holders</div><div style="font-size:14px;font-weight:700;">${matches.length}</div></div><div><div style="font-size:10px;color:var(--gray2);text-transform:uppercase;letter-spacing:.4px;">Monthly cost</div><div style="font-size:14px;font-weight:700;">${fmt(totalCost)}</div></div><div><div style="font-size:10px;color:var(--gray2);text-transform:uppercase;letter-spacing:.4px;">Active</div><div style="font-size:14px;font-weight:700;color:var(--green);">${matches.filter(e=>e.lics.some(l=>l.plat===plat&&l.st==='active')).length}</div></div><div><div style="font-size:10px;color:var(--gray2);text-transform:uppercase;letter-spacing:.4px;">Flagged</div><div style="font-size:14px;font-weight:700;color:var(--red);">${matches.filter(e=>e.lics.some(l=>l.plat===plat&&l.st!=='active')).length}</div></div></div></div>`;
  const tbl=matches.length===0?'<div style="text-align:center;color:var(--gray2);padding:28px;background:var(--white);border-radius:9px;border:1px solid var(--border);">No results</div>':`<div class="card" style="padding:0;overflow-x:auto;"><table><thead><tr><th>Employee</th><th>Unit</th><th>Account</th><th>Project</th><th>Cost/mo</th><th>Status</th><th>Last used</th></tr></thead><tbody>${matches.map((e,i)=>{const lic=e.lics.find(l=>l.plat===plat);return `<tr style="background:${i%2===0?'transparent':'#faf8f4'}"><td><strong>${e.name}</strong><div style="font-size:10px;color:var(--gray2);">${displayEmpId(e)}</div></td><td><span class="pill punit">${e.unit}</span></td><td>${trunc(e.acct)}<div style="font-size:10px;color:var(--gray2);">${e.acctOwner}</div></td><td style="color:var(--gray2);">${trunc(e.proj)}</td><td>${lic?fmt(licenseDisplayCost(lic)):'—'}</td><td><span class="pill ${lic?sc[lic.st]||'pf':'pf'}">${lic?lic.st:'—'}</span></td><td style="color:var(--gray2);font-size:11px;">${lic?lic.last:'—'}</td></tr>`;}).join('')}</tbody></table></div>`;
  pr.innerHTML=summary+tbl;
}

// ─────────── PLATFORM MASTER ────────────────────────────
function renderPlats(){
  const today=new Date();
  const ent=PLATFORMS.filter(p=>p.type==='enterprise').length;
  const soon=PLATFORMS.filter(p=>{if(!p.renewal)return false;const d=Math.round((new Date(p.renewal)-today)/86400000);return d>=0&&d<=60;}).length;
  const psum=document.getElementById('psum');
  if(psum)psum.innerHTML=[{l:'Total platforms',v:PLATFORMS.length,acc:true},{l:'Enterprise licenses',v:ent,s:'Flat fee cost model'},{l:'Renewal within 60d',v:soon,warn:soon>0,s:soon>0?'Action required':'All clear'}].map(m=>`<div class="met${m.acc?' macc':''}"><div class="mlb">${m.l}</div><div class="mval" style="${m.warn?'color:var(--amber)':''}">${m.v}</div>${m.s?`<div class="msub">${m.s}</div>`:''}</div>`).join('');
  const ptb=document.getElementById('ptb');if(!ptb)return;
  ptb.innerHTML=PLATFORMS.map((p,i)=>{
    const uc=platUC(p);
    const allocated=platformActiveSeatCount(p);
    const seatCap=p.type==='enterprise'?p.entSeats:p.purchasedSeats;
    const hasSeatCap=!!seatCap;
    const avail=hasSeatCap?seatCap-allocated:null;
    const pct=hasSeatCap?Math.round(allocated/seatCap*100):0;
    const isUsageBased=p.type==='usage_based';
    const atIndexLimit=isUsageBased&&hasSeatCap&&allocated>=seatCap;
    const seatDisplay=hasSeatCap
      ?`<strong style="color:${atIndexLimit?'var(--red)':'inherit'}">${allocated}/${seatCap}</strong>${atIndexLimit?`<div style="font-size:10px;color:var(--red);font-weight:600;margin-top:2px;">${seatCap} indexes full</div>`:''}`
      :`<strong>${allocated}</strong>`;
    const availDisplay=hasSeatCap
      ?(atIndexLimit&&avail<=0?'Indexes full':avail>0?avail:avail===0?'0':'Over by '+Math.abs(avail))
      :'—';
    const availColor=hasSeatCap
      ?(avail<0||atIndexLimit?'var(--red)':avail===0?'var(--amber)':'var(--green)')
      :'var(--gray2)';
    const seatBarClass=avail<0?'seat-over':atIndexLimit?'seat-full':'seat-used';
    const seatBar=hasSeatCap
      ?`<div class="seat-bar"><div class="${seatBarClass}" style="width:${Math.min(pct,100)}%"></div></div>`
      :'';
    const dL=p.renewal?Math.round((new Date(p.renewal)-today)/86400000):null;
    const rTd=dL!==null?(dL<=30?`<span style="color:var(--red);font-weight:600;">${dL}d</span>`:dL<=60?`<span style="color:var(--amber);font-weight:600;">${dL}d</span>`:`<span style="font-size:11px;color:var(--gray2);">${p.renewal}</span>`):'—';
    return `<tr style="background:${i%2===0?'transparent':'#faf8f4'}">
      <td><strong>${p.name}</strong><div style="font-size:10px;color:var(--gray2);">${p.cat}</div></td>
      <td style="color:var(--gray2);">${p.vendor}</td>
      <td><span class="pill ${p.agr==='enterprise'?'pea':'psa2'}">${p.agr==='enterprise'?'EA':'SA'}</span></td>
      <td><span class="pill ${platformTypePill(p.type)}">${platformTypeLabel(p.type)}</span></td>
      <td style="font-size:11px;color:var(--gray2);">${p.currency}</td>
      <td>${seatDisplay}${seatBar}</td>
      <td style="font-weight:600;color:${availColor};">${availDisplay}</td>
      <td><strong>${fmt(uc)}</strong><div style="font-size:10px;color:var(--gray2);">${p.type==='usage_based'?'fixed / mo':p.type==='enterprise'?p.alloc+' alloc':'per seat'}</div></td>
      <td style="font-size:11px;color:var(--gray2);">${p.effectiveDate||'—'}</td>
      <td>${rTd}</td>
      <td style="white-space:nowrap;">
        <button class="btn" style="font-size:11px;padding:3px 8px;margin-right:3px;" onclick="editPF(${p.id})">Edit</button>
        <button class="btn" style="font-size:11px;padding:3px 8px;margin-right:3px;" onclick="showSeatHist(${p.id},'${p.name}')">Seats</button>
        <button class="btn bred" style="font-size:11px;padding:3px 8px;" onclick="delPF(${p.id})">Remove</button>
      </td>
    </tr>`;
  }).join('');
  const puL=PLATFORMS.filter(p=>p.type==='per_user'),entL=PLATFORMS.filter(p=>p.type==='enterprise');
  const pusel=document.getElementById('pusel'),entsel=document.getElementById('entsel');
  if(pusel)pusel.innerHTML='<option value="">Select</option>'+puL.map(p=>`<option value="${p.id}">${p.name} — ${fmt(p.billing==='annual'?Math.round(p.seatCost/12):p.seatCost)}/seat/Mth</option>`).join('');
  if(entsel)entsel.innerHTML='<option value="">Select</option>'+entL.map(p=>`<option value="${p.id}">${p.name}</option>`).join('');
}
function showSeatHist(id,name){
  const snaps=SEAT_SNAPSHOTS[id]||[];
  document.getElementById('seat-hist-name').textContent=name;
  document.getElementById('seat-hist-content').innerHTML=`<table><thead><tr><th>Date</th><th>Seat count</th><th>Change</th><th>Cost impact</th></tr></thead><tbody>${snaps.map((s,i)=>{const prev=snaps[i-1];const diff=prev?s.seats-prev.seats:0;const p=PLATFORMS.find(x=>x.id===id);const uc=p?platUC(p):0;return `<tr><td>${s.date}</td><td><strong>${s.seats}</strong></td><td>${diff===0?'—':diff>0?`<span style="color:var(--green);">+${diff}</span>`:`<span style="color:var(--red);">${diff}</span>`}</td><td style="font-size:11px;color:var(--gray2);">${fmt(s.seats*uc)}/Mth</td></tr>`;}).join('')}</tbody></table><div style="margin-top:10px;padding:9px;background:var(--tan);border-radius:7px;font-size:11px;color:var(--gray);">Prorated cost = (seats × unit cost × days active) ÷ days in month. Effective date on platform master controls mid-cycle cost change calculation.</div>`;
  document.getElementById('seat-hist-panel').style.display='block';
}
function showPF(){editPFid=null;document.getElementById('pfh').textContent='Add new platform';['pfn','pfv','pfsc','pfmax','pfec','pfes','pfubec','pfubmax','pfurl','pfnotes'].forEach(id=>{const el=document.getElementById(id);if(el)el.value='';});document.getElementById('pfcat').value='AI / ML';document.getElementById('pftype').value='per_user';document.getElementById('pfbill').value='monthly';document.getElementById('pfagr').value='standard';document.getElementById('pfal').value='equal';document.getElementById('pfid').value='30';document.getElementById('pfid2').value='30';document.getElementById('pfubid').value='30';document.getElementById('pfubmax').value='20';document.getElementById('pfcur').value='USD';document.getElementById('pfcon').value='yes';document.getElementById('pfsh').value='no';document.getElementById('pfapi').value='no';document.getElementById('pfren').value='';document.getElementById('pfeff').value='';const today=new Date().toISOString().split('T')[0];document.getElementById('pfeff').min=today;document.getElementById('pfren').min=today;togPFtype();document.getElementById('pform').style.display='block';document.getElementById('pform').scrollIntoView({behavior:'smooth'});}
function hidePF(){document.getElementById('pform').style.display='none';editPFid=null;}
function togPFtype(){
  const t=document.getElementById('pftype').value;
  document.getElementById('pfpu').style.display=t==='per_user'?'grid':'none';
  document.getElementById('pfent').style.display=t==='enterprise'?'block':'none';
  document.getElementById('pfub').style.display=t==='usage_based'?'block':'none';
  pfPrev();
}
function pfPrev(){
  const t=document.getElementById('pftype').value,bill=document.getElementById('pfbill').value;
  const prev=document.getElementById('pfprev'),prevs=document.getElementById('pfprevs');if(!prev||!prevs)return;
  if(t==='per_user'){
    const sc=parseFloat(document.getElementById('pfsc').value)||0;
    const mo=bill==='annual'?Math.round(sc/12):sc;
    prev.textContent=sc?fmt(mo)+'/seat/month':'Fill in cost per seat';
    prevs.textContent=sc?'Annual per seat: '+fmt(sc):'';
  }else if(t==='usage_based'){
    const ec=parseFloat(document.getElementById('pfubec').value)||0;
    const es=parseInt(document.getElementById('pfubmax').value)||20;
    const mo=bill==='annual'?Math.round(ec/12):ec;
    prev.textContent=ec?fmt(mo)+'/month (fixed)':'Fill in fixed monthly cost';
    prevs.textContent=ec?`Flat fee — up to ${es} seats · does not increase with more users`:'';
  }else{
    const ec=parseFloat(document.getElementById('pfec').value)||0,es=parseInt(document.getElementById('pfes').value)||1,al=document.getElementById('pfal').value,mo=bill==='annual'?Math.round(ec/12):ec,unit=al==='equal'?Math.round(mo/Math.max(es,1)):Math.round(mo/(Math.max(es,1)*0.8));
    prev.textContent=(ec&&es)?fmt(unit)+'/user/month':'Fill in contract cost and seats';
    prevs.textContent=(ec&&es)?'Total monthly: '+fmt(mo)+' · '+al+' across '+es+' seats':'';
  }
}
function editPF(id){
  const p=PLATFORMS.find(x=>x.id===id);if(!p)return;editPFid=id;
  document.getElementById('pfh').textContent='Edit — '+p.name;
  document.getElementById('pfn').value=p.name;document.getElementById('pfv').value=p.vendor;document.getElementById('pfcat').value=p.cat;document.getElementById('pfagr').value=p.agr||'standard';document.getElementById('pftype').value=p.type;document.getElementById('pfbill').value=p.billing;document.getElementById('pfcur').value=p.currency||'USD';document.getElementById('pfsc').value=p.seatCost||'';document.getElementById('pfmax').value=p.purchasedSeats||'';document.getElementById('pfid').value=p.inactiveDays||30;document.getElementById('pfec').value=p.entCost||'';document.getElementById('pfes').value=p.entSeats||p.purchasedSeats||'';document.getElementById('pfubec').value=p.type==='usage_based'?(p.entCost||''):'';document.getElementById('pfubmax').value=p.type==='usage_based'?(p.purchasedSeats||p.entSeats||20):20;document.getElementById('pfubid').value=p.inactiveDays||30;document.getElementById('pfal').value=p.alloc;document.getElementById('pfid2').value=p.inactiveDays||30;document.getElementById('pfren').value=p.renewal||'';document.getElementById('pfeff').value=p.effectiveDate||'';document.getElementById('pfcon').value=p.contractor||'yes';document.getElementById('pfsh').value=p.shared||'no';document.getElementById('pfapi').value=p.api||'no';document.getElementById('pfnotes').value=p.notes||'';const today=new Date().toISOString().split('T')[0];document.getElementById('pfeff').min=today;togPFtype();document.getElementById('pform').style.display='block';document.getElementById('pform').scrollIntoView({behavior:'smooth'});
}
async function delPF(id){
  const p=PLATFORMS.find(x=>x.id===id);
  if(!p||!confirm('Remove '+p.name+'?'))return;
  try{
    await fetchJson(`${API_BASE}/platforms/${id}`,{method:'DELETE'},'Failed to delete platform.');
    PLATFORMS=PLATFORMS.filter(x=>x.id!==id);
    renderPlats();
    toast('Platform removed.');
  }catch(err){
    console.error('Delete error:',err);
    toast('Failed to delete platform: '+err.message,'var(--red)');
  }
}
async function savePF(){
  const name=document.getElementById('pfn').value.trim(),vendor=document.getElementById('pfv').value.trim();
  if(!name){toast('Platform name required','var(--red)');return;}if(!vendor){toast('Vendor required','var(--red)');return;}
  const type=document.getElementById('pftype').value;
  const sc=parseFloat(document.getElementById('pfsc').value)||0;
  const ec=type==='usage_based'?(parseFloat(document.getElementById('pfubec').value)||0):(parseFloat(document.getElementById('pfec').value)||0);
  const es=type==='usage_based'?(parseInt(document.getElementById('pfubmax').value)||0):(parseInt(document.getElementById('pfes').value)||0);
  if(type==='per_user'&&!sc){toast('Cost per seat required','var(--red)');return;}
  if(type==='enterprise'&&(!ec||!es)){toast('Contract cost and seat count required','var(--red)');return;}
  if(type==='usage_based'&&!ec){toast('Fixed monthly cost required','var(--red)');return;}
  if(type==='usage_based'&&(!es||es>20)){toast('Max seats required (1–20)','var(--red)');return;}
  const idDays=parseInt(type==='per_user'?document.getElementById('pfid').value:type==='usage_based'?document.getElementById('pfubid').value:document.getElementById('pfid2').value)||30;
  const prevPlatform=editPFid?PLATFORMS.find(p=>p.id===editPFid):null;
  const allocatedSeats=prevPlatform?.activeSeats??platformActiveSeatCount(prevPlatform)??0;
  const rec={name,vendor,cat:document.getElementById('pfcat').value,agr:document.getElementById('pfagr').value,type,billing:document.getElementById('pfbill').value,currency:document.getElementById('pfcur').value,seatCost:sc,entCost:ec,entSeats:es,purchasedSeats:type==='per_user'?(parseInt(document.getElementById('pfmax').value)||0):es,alloc:type==='usage_based'?'equal':document.getElementById('pfal').value,effectiveDate:document.getElementById('pfeff').value,renewal:document.getElementById('pfren').value,activeSeats:allocatedSeats,inactiveDays:idDays,contractor:document.getElementById('pfcon').value,shared:document.getElementById('pfsh').value,api:document.getElementById('pfapi').value,url:'',notes:document.getElementById('pfnotes').value};
  
  // Build API payload with backend schema field names
  const payload={
    name:rec.name,
    vendor:rec.vendor,
    category:rec.cat,
    agreement_type:rec.agr,
    license_type:rec.type,
    billing_period:rec.billing,
    currency:rec.currency,
    inactivity_days:rec.inactiveDays,
    contractor_allowed:rec.contractor==='yes',
    shared_allowed:rec.shared==='yes',
    api_available:rec.api==='yes',
    notes:rec.notes,
    effective_date:rec.effectiveDate?rec.effectiveDate:null,
    renewal_date:rec.renewal?rec.renewal:null,
    seat_cost:rec.type==='per_user'?rec.seatCost:null,
    enterprise_cost:rec.type==='enterprise'||rec.type==='usage_based'?rec.entCost:null,
    contracted_seats:rec.type==='enterprise'||rec.type==='usage_based'?rec.entSeats:null,
    allocation_method:rec.alloc
  };
  
  if(editPFid){
    try{
      const apiData=await fetchJson(`${API_BASE}/platforms/${editPFid}`,{
        method:'PUT',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(payload)
      },'Failed to update platform.');
      // Transform API response to internal format
      const data={
        id:apiData.id,
        name:apiData.name,
        vendor:apiData.vendor,
        cat:apiData.category,
        agr:apiData.agreement_type,
        type:apiData.license_type,
        billing:apiData.billing_period,
        currency:apiData.currency,
        seatCost:payload.seat_cost,
        entCost:payload.enterprise_cost,
        entSeats:payload.contracted_seats,
        purchasedSeats:payload.contracted_seats||0,
        alloc:payload.allocation_method,
        effectiveDate:apiData.effective_date,
        renewal:apiData.renewal_date,
        activeSeats:prevPlatform?.activeSeats??0,
        inactiveDays:apiData.inactivity_days,
        contractor:payload.contractor_allowed?'yes':'no',
        shared:payload.shared_allowed?'yes':'no',
        api:payload.api_available?'yes':'no',
        url:'',
        notes:apiData.notes
      };
      PLATFORMS=PLATFORMS.map(p=>p.id===editPFid?data:p);
      toast('Platform updated.');
      hidePF();
      renderPlats();
    }catch(err){
      console.error('Platform update error:',err);
      toast('Failed to update platform: '+err.message,'var(--red)');
    }
    return;
  }else{
    try{
      const apiData=await fetchJson(`${API_BASE}/platforms`,{
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(payload)
      },'Failed to save platform.');
      // Transform API response to internal format
      const data={
        id:apiData.id,
        name:apiData.name,
        vendor:apiData.vendor,
        cat:apiData.category,
        agr:apiData.agreement_type,
        type:apiData.license_type,
        billing:apiData.billing_period,
        currency:apiData.currency,
        seatCost:payload.seat_cost,
        entCost:payload.enterprise_cost,
        entSeats:payload.contracted_seats,
        purchasedSeats:payload.contracted_seats||0,
        alloc:payload.allocation_method,
        effectiveDate:apiData.effective_date,
        renewal:apiData.renewal_date,
        activeSeats:platformAllocatedSeats(apiData.name)||0,
        inactiveDays:apiData.inactivity_days,
        contractor:payload.contractor_allowed?'yes':'no',
        shared:payload.shared_allowed?'yes':'no',
        api:payload.api_available?'yes':'no',
        url:'',
        notes:apiData.notes
      };
      PLATFORMS.push(data);
      toast('"'+name+'" added. Available for license assignment.');
      hidePF();
      renderPlats();
    }catch(err){
      console.error('Platform creation error:',err);
      toast('Failed to save platform: '+err.message,'var(--red)');
    }
    return;
  }
  
  hidePF();renderPlats();
}
function calcPU(){const id=document.getElementById('pusel').value,p=PLATFORMS.find(x=>x.id==id),s=parseInt(document.getElementById('pus').value)||0;if(!p){document.getElementById('puout').textContent='—';document.getElementById('puann').textContent='Select a platform';return;}const mo=p.billing==='annual'?Math.round(p.seatCost/12):p.seatCost;document.getElementById('puout').textContent=fmt(mo*s)+'/Mth';document.getElementById('puann').textContent='Annual: '+fmt(mo*s*12);}
function calcEnt(){const id=document.getElementById('entsel').value,p=PLATFORMS.find(x=>x.id==id);if(!p){document.getElementById('entout').textContent='—';document.getElementById('entinfo').textContent='';return;}const active=parseInt(document.getElementById('enta').value)||1,method=document.getElementById('entm').value,moTotal=Math.round(p.entCost/(p.billing==='annual'?12:1)),unit=method==='equal'?Math.round(moTotal/Math.max(p.entSeats,1)):Math.round(moTotal/active);document.getElementById('entout').textContent=fmt(unit)+'/user/Mth';const wasted=method==='equal'?Math.round(moTotal/Math.max(p.entSeats,1))*(p.entSeats-active):0;document.getElementById('entinfo').textContent=wasted>0?fmt(wasted)+'/Mth wasted on '+(p.entSeats-active)+' unused seats':'Monthly total: '+fmt(moTotal);}

// ─────────── ANALYTICS ──────────────────────────────────

/* ── Shared helpers ── */
function anKpiCard(accent, label, val, valColor, sub, sub2){
  return `<div class="an-kpi">
    <div class="an-kpi-accent" style="background:${accent}"></div>
    <div class="an-kpi-lbl">${label}</div>
    <div class="an-kpi-val" style="color:${valColor||'var(--black)'}">${val}</div>
    <div class="an-kpi-sub">${sub}${sub2 ? '<div class="an-kpi-sub2">' + sub2 + '</div>' : ''}</div>
  </div>`;
}

function anBar(label, pct, valStr, color){
  color = color || 'var(--lime)';
  return `<div class="an-bc-row">
    <div class="an-bc-lbl">${label}</div>
    <div class="an-bc-track"><div class="an-bc-fill" style="width:${pct}%;background:${color}">
      <span class="an-bc-inline">${pct>20?valStr:''}</span>
    </div></div>
    <div class="an-bc-val">${valStr}</div>
  </div>`;
}

function anSec(label){
  return `<div class="an-sec">${label}</div>`;
}

function anSecAction(label, actionHtml){
  return `<div class="an-sec"><span>${label}</span>${actionHtml || ''}</div>`;
}

// GDL view expand/collapse state
let gdlAcctExpanded = false;
let gdlProjExpanded = false;

function toggleGdlAcctExpand(){ gdlAcctExpanded = !gdlAcctExpanded; renderAnalytics(); }
function toggleGdlProjExpand(){ gdlProjExpanded = !gdlProjExpanded; renderAnalytics(); }

function anSortRollupEntries(entries){
  return [...entries].sort((a,b) => {
    const aCost = a.stats.find(s => s.l === 'Spend')?.v || 0;
    const bCost = b.stats.find(s => s.l === 'Spend')?.v || 0;
    const aVal = parseFloat(String(aCost).replace(/[^0-9.-]/g, '')) || 0;
    const bVal = parseFloat(String(bCost).replace(/[^0-9.-]/g, '')) || 0;
    return bVal - aVal;
  });
}

function anRollupRowList(entries, showAll){
  const sorted = anSortRollupEntries(entries);
  const limit = showAll ? sorted.length : 3;
  return sorted.slice(0, limit).map(e => anRollupRow(e.name, e.sub, e.stats)).join('');
}

function anRollupRow(name, sub, stats){
  const statsHtml = stats.map(s => `<div class="an-rr-stat">
    <div class="an-rr-v" style="color:${s.c||'var(--black)'}">${s.v}</div>
    <div class="an-rr-l">${s.l}</div>
  </div>`).join('');
  return `<div class="an-rr">
    <div class="an-rr-left"><div class="an-rr-name">${name}</div><div class="an-rr-sub">${sub}</div></div>
    <div class="an-rr-stats">${statsHtml}</div>
  </div>`;
}

function anTrendMeta(spendArr, emps){
  const totalCurrentLic   = emps.reduce((s,e) => s + currentLicenses(e).length, 0);
  const totalCurrentSpend = emps.flatMap(e => currentLicenses(e)).reduce((s,l) => s + (l.cost||0), 0);
  const avgCostPerLic     = (totalCurrentSpend > 0 && totalCurrentLic > 0) ? totalCurrentSpend / totalCurrentLic : 0;
  
  // Count employees who have at least one license
  const empsWithLicenses  = emps.filter(e => currentLicenses(e).length > 0).length;
  
  return spendArr.map(v => {
    if (!v || v === 0) return {lic:0, emp:0};
    const licEst = avgCostPerLic > 0 ? Math.round(v / avgCostPerLic) : 0;
    return {lic: licEst, emp: empsWithLicenses};  // Count of employees with licenses
  });
}

function anTrendHtml(data, color, meta){
  const max = Math.max(...data, 1);
  const lblColor = (color && color.includes('lime')) ? 'rgba(0,0,0,0.82)' : 'rgba(255,255,255,0.92)';
  const bars = data.map((v, i) => {
    const heightPx = Math.round(v/max*96);
    const m   = meta && meta[i];
    const tip = `${MONTHS[i]}: ${fmt(v)}${m && m.lic > 0 ? ' · ' + m.lic + ' lic / ' + m.emp + ' emp' : ''}`;
    const lbl = (m && m.lic > 0 && heightPx >= 22)
      ? `<span class="tcbar-lbl" style="color:${lblColor}">${m.lic} lic<br>${m.emp} emp</span>` : '';
    return `<div class="tcbar" style="height:${heightPx}px;background:${color||'var(--lime)'};opacity:${i===data.length-1?1:.75};" data-tip="${tip}">${lbl}</div>`;
  }).join('');
  const lbls = MONTHS.map(m => `<div class="tl">${m}</div>`).join('');
  return `<div class="trend-chart-wrap"><div class="trend-chart">${bars}</div><div class="trend-labels">${lbls}</div></div>`;
}

function anBarsFromMap(map, colorFn){
  const entries = Object.entries(map).filter(([,v]) => v > 0).sort((a,b) => b[1]-a[1]);
  const max = Math.max(...entries.map(e=>e[1]), 1);
  const colors = ['#1a5fa8','#5a2db5','#2d7a3a','#9a6200','#c0392b','var(--lime)','#1a5fa8'];
  return entries.map(([k,v], i) => anBar(k, Math.round(v/max*100), fmt(v), colorFn ? colorFn(k,i) : colors[i%colors.length])).join('');
}

function anBuildPlatformCostMap(emps){
  const platMap = {};
  emps.forEach(e => currentLicenses(e).forEach(l => {
    const plat = l.plat || 'Unknown';
    const cost = Number(l.cost || 0);
    if(!platMap[plat]) platMap[plat] = { total: 0, seats: 0, costCounts: {} };
    platMap[plat].total += cost;
    platMap[plat].seats += 1;
    platMap[plat].costCounts[cost] = (platMap[plat].costCounts[cost] || 0) + 1;
  }));
  return platMap;
}


function anBarsFromPlatformCostMap(map, colorFn){
  const entries = Object.entries(map).filter(([,meta]) => meta.total > 0).sort((a,b) => b[1].total-a[1].total);
  const max = Math.max(...entries.map(([,meta])=>meta.total), 1);
  const colors = ['#1a5fa8','#5a2db5','#2d7a3a','#9a6200','#c0392b','var(--lime)','#1a5fa8'];
  return entries.map(([platform, meta], i) => {
    const color = colorFn ? colorFn(platform,i) : colors[i%colors.length];
    const valStr = meta.seats + ' lic · ' + fmt(meta.total) + '/Mth';
    return `<div class="an-bc-row">
      <div class="an-bc-lbl">${platform}</div>
      <div class="an-bc-track"><div class="an-bc-fill" style="width:${Math.round(meta.total/max*100)}%;background:${color}">
        <span class="an-bc-inline">${Math.round(meta.total/max*100)>28?fmt(meta.total):''}</span>
      </div></div>
      <div class="an-bc-val" style="width:200px;">${valStr}</div>
    </div>`;
  }).join('');
}

function anBarsCountFromMap(map){
  const entries = Object.entries(map).sort((a,b) => b[1]-a[1]);
  const max = Math.max(...entries.map(e=>e[1]), 1);
  const colors = ['#1a5fa8','#5a2db5','#2d7a3a','#9a6200','#c0392b','var(--lime)'];
  return entries.map(([k,v], i) => anBar(k, Math.round(v/max*100), v+' seats', colors[i%colors.length])).join('');
}

/* anComputeTrend — context-aware monthly spend array for trend charts.
   - fPlat set: use MONTHLY_SPEND[yr][fPlat] (single-platform historical data)
   - filteredEmps === full EMPS (no filter): sum all MONTHLY_SPEND platforms
   - filteredEmps is a subset: sum MONTHLY_PROJ rows whose project appears in filteredEmps
     (MONTHLY_PROJ is the most granular breakdown available without extra API calls)
*/
function anComputeTrend(yr, filteredEmps, fPlatArg){
  // fPlatArg can be a string or a Set
  const platSet = fPlatArg instanceof Set ? fPlatArg : (fPlatArg ? new Set([fPlatArg]) : new Set());
  const yearSpend = spendDataForYear(yr);
  if(platSet.size === 1){
    const platName = [...platSet][0];
    return (yearSpend[platName] || Array(12).fill(0)).map(Number);
  }
  let series;
  if(filteredEmps.length === EMPS.length && platSet.size === 0){
    series = MONTHS.map((_,i) => Object.values(yearSpend).reduce((s,arr) => s+(arr[i]||0), 0));
  } else {
    // Filtered view — derive from per-project monthly data
    const projSet = new Set(filteredEmps.map(e=>e.proj).filter(Boolean));
    const yearProj = projectDataForYear(yr);
    series = MONTHS.map((_,i) =>
      Object.entries(yearProj)
        .filter(([proj]) => projSet.has(proj))
        .reduce((s,[,arr]) => s + (arr[i]||0), 0)
    );
  }
  // Fallback: if current month shows 0 but employees have current licenses, use actual license cost.
  // This handles scoped views (PM, Account, GDL) where backend allocation series may be empty.
  const today = new Date();
  if(String(yr) === String(today.getFullYear())){
    const mi = today.getMonth();
    if(series[mi] === 0 && filteredEmps.length > 0){
      const actualCost = filteredEmps.flatMap(e => currentLicenses(e)).reduce((s,l) => s + l.cost, 0);
      if(actualCost > 0){
        // Fill all months up to and including current with the actual cost (best estimate for missing historical data)
        for(let i = 0; i <= mi; i++) if(series[i] === 0) series[i] = actualCost;
      }
    }
  }
  return series;
}

function anComputeTrendMulti(years, filteredEmps, fPlatArg){
  const yearList = Array.isArray(years) && years.length ? years : [latestSpendYear()];
  const totals = Array(12).fill(0);
  yearList.forEach(yr => {
    anComputeTrend(String(yr), filteredEmps, fPlatArg).forEach((v,i) => {
      totals[i] += Number(v || 0);
    });
  });
  return totals;
}

function anAggregateProjectData(years){
  const yearList = Array.isArray(years) && years.length ? years : [latestSpendYear()];
  const aggregated = {};
  yearList.forEach(yr => {
    Object.entries(projectDataForYear(String(yr))).forEach(([proj, arr]) => {
      if(!aggregated[proj]) aggregated[proj] = Array(12).fill(0);
      arr.forEach((v,i) => { aggregated[proj][i] += Number(v || 0); });
    });
  });
  return aggregated;
}

function anScopeBanner(scopeText, rolePill, levelPill){
  return `<div class="an-scope">
    <div class="an-scope-l">Viewing:<span class="an-scope-val">${scopeText}</span></div>
    <div class="an-scope-r">
      ${levelPill ? `<span class="an-pill">${levelPill}</span>` : ''}
      ${rolePill  ? `<span class="an-pill">${rolePill}</span>`  : ''}
    </div>
  </div>`;
}

function anPageHeader(){
  const title = document.getElementById('ptitle')?.textContent || 'Analytics';
  const sub = document.getElementById('psub')?.textContent || '';
  const actions = document.getElementById('tba')?.innerHTML || '';
  return `<div class="an-page-head">
    <div>
      <div class="an-page-title">${title}</div>
      <div class="an-page-sub">${sub}</div>
    </div>
    <div class="an-page-actions">${actions}</div>
  </div>`;
}

function anStickyHead(){
  return `<div class="an-sticky-head">${Array.from(arguments).join('')}</div>`;
}

function anPlatformSeatSummary(emps, selectedPlatforms){
  const selectedSet = selectedPlatforms && selectedPlatforms.size ? selectedPlatforms : null;
  return PLATFORMS.map(platform => {
    const name = String(platform.name || '').trim();
    const rawPurchased = platform.type === 'enterprise' ? platform.entSeats : platform.purchasedSeats;
    const purchased = Number(rawPurchased || 0);
    return {
      name,
      purchased,
      hasPurchasedConfig: rawPurchased !== null && rawPurchased !== undefined && String(rawPurchased).trim() !== '' && Number(rawPurchased)>0,
      active: platformActiveSeatCount(platform),
      unitCost: Number(platUC(platform) || 0),
      type: platform.type,
      cat: platform.cat,
      renewal: platform.renewal || null,
    };
  }).filter(platform => {
    if(selectedSet && !selectedSet.has(platform.name)) return false;
    return platform.active > 0;
  }).sort((a,b) => b.active - a.active || b.purchased - a.purchased || a.name.localeCompare(b.name));
}

function anScopedAlertStats(emps){
  const alertEmpIds = new Set();
  emps.forEach(e => {
    if(activeAlerts().some(a => matchesEmployeeRef(e, a.empId))) {
      alertEmpIds.add(String(e.id));
    }
  });
  const alertLicenses = emps
    .filter(e => alertEmpIds.has(String(e.id)))
    .flatMap(e => currentLicenses(e));
  return {
    alertEmpIds,
    flaggedLicenses: alertLicenses.length,
    recoverableCost: alertLicenses.reduce((sum, license) => sum + license.cost, 0),
  };
}

/* ── Main dispatch ── */
function renderAnalytics(){
  if(role==='admin')   renderAnalyticsAdmin();
  else if(role==='gdl')      renderAnalyticsGdl();
  else if(role==='account')  renderAnalyticsAccount();
  else if(role==='pm')       renderAnalyticsPm();
  else if(role==='finance')  renderAnalyticsFinance();
}

/* ════════════════════════════════════
   MULTI-SELECT FILTER COMPONENT
   AN_SEL[key] = Set of selected values
   (empty Set = "All" / no filter)
════════════════════════════════════ */
const AN_SEL = {
  gdl:new Set(), acct:new Set(), acctOwner:new Set(), proj:new Set(), unit:new Set(), plat:new Set(),
  acct2:new Set(), proj2:new Set(), plat2:new Set(),
  acctProj:new Set(), acctPlat:new Set(),
  pmPlat:new Set(),
  finYr:new Set(), finGdl:new Set(), finOwner:new Set(), finAcct:new Set(), finPlat:new Set(),
  // License register
  licPlat:new Set(), licEst:new Set(), licLst:new Set(), licUnit:new Set(), licAcct:new Set(), licProj:new Set()
};

/** Build HTML for one multi-select dropdown */
function anMsBuild(key, placeholder, options){
  const sel = AN_SEL[key] || new Set();
  const count = sel.size;
  const optionCounts = new Map();
  (options || []).forEach(v=>{
    const keyStr=String(v);
    optionCounts.set(keyStr,(optionCounts.get(keyStr)||0)+1);
  });
  const uniqueOptions = [...optionCounts.keys()];
  const breakdownMap = anBuildOptionBreakdownMap(key, uniqueOptions);
  const placeholderWithCount = `${placeholder}${uniqueOptions.length?` (${uniqueOptions.length})`:''}`;
  const btnLabel = count === 0 ? placeholderWithCount : placeholderWithCount.replace(/^All /,'') + ` <span class="an-ms-badge">${count}</span>`;
  const activeClass = count > 0 ? ' an-ms-active' : '';
  const rows = uniqueOptions.map(v => {
    const checked = sel.has(v) ? ' checked' : '';
    const safeV = encodeURIComponent(v);
    const safeTitle = String(v).replace(/"/g,'&quot;');
    const breakdown = breakdownMap.get(String(v)) || {active:0,total:optionCounts.get(v)||0,totalEmployees:0};
    const inactive = Math.max(0, (breakdown.total || 0) - (breakdown.active || 0));
    const chipLabel = inactive > 0 ? `${breakdown.active}/${inactive}` : `${breakdown.active}`;
    return `<label class="an-ms-item"><input type="checkbox"${checked} onchange="anMsCheck('${key}','${safeV}',this)"><span class="an-ms-opt-label">${v}</span><span class="an-ms-opt-meta"><span class="an-ms-opt-chip">${chipLabel}</span></span></label>`;
  }).join('');
  return `<div class="an-ms" id="an-ms-${key}">
    <button type="button" class="an-ms-btn${activeClass}" data-placeholder="${placeholderWithCount.replace(/"/g,'&quot;')}" onclick="anMsToggle('${key}')">${btnLabel}<span class="an-ms-arrow">▾</span></button>
    <div class="an-ms-panel" id="an-ms-panel-${key}" style="display:none">
      <input class="an-ms-search" type="text" placeholder="Search…" oninput="anMsSearch('${key}',this.value)">
      <div class="an-ms-list" id="an-ms-list-${key}">
        ${uniqueOptions.length ? rows : '<div class="an-ms-empty">No options</div>'}
      </div>
      <div class="an-ms-footer">
        <button type="button" class="btn" onclick="anMsClose()">Close</button>
      </div>
    </div>
  </div>`;
}

/** Toggle open/close */
function anMsToggle(key){
  const panel = document.getElementById('an-ms-panel-'+key);
  const wrap  = document.getElementById('an-ms-'+key);
  if(!panel) return;
  const opening = panel.style.display === 'none';
  // Close all others first
  document.querySelectorAll('.an-ms-panel').forEach(p => { p.style.display='none'; });
  document.querySelectorAll('.an-ms').forEach(w => w.classList.remove('open'));
  if(opening){
    panel.style.display = 'block';
    wrap.classList.add('open');
    panel.querySelector('.an-ms-search')?.focus();
  }
}

/** Live search — hide non-matching items */
function anMsSearch(key, q){
  const list = document.getElementById('an-ms-list-'+key);
  if(!list) return;
  const lq = q.toLowerCase();
  list.querySelectorAll('.an-ms-item').forEach(item => {
    const txt = item.querySelector('span')?.textContent || '';
    item.style.display = txt.toLowerCase().includes(lq) ? '' : 'none';
  });
}

function anSelectedValues(key){
  return [...(AN_SEL[key] || new Set())];
}

function anSortedUnique(values){
  return [...new Set((values || []).filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b)));
}

function anSortedValues(values){
  return (values || []).filter(Boolean).sort((a,b)=>String(a).localeCompare(String(b)));
}

function anPlatformOptionsForEmps(emps){
  return anSortedValues((emps || []).flatMap(e => currentLicenses(e).map(l => l.plat)));
}

function anRowsMatchKeyValue(row, key, value){
  if(key==='gdl' || key==='finGdl') return String(row.gdl||'')===String(value);
  if(key==='acctOwner' || key==='finOwner') return String(row.acctOwner||'')===String(value);
  if(key==='acct' || key==='acct2' || key==='finAcct' || key==='licAcct') return String(row.acct||'')===String(value);
  if(key==='proj' || key==='proj2' || key==='acctProj' || key==='licProj') return String(row.proj||'')===String(value);
  if(key==='unit' || key==='licUnit') return String(row.unit||'')===String(value);
  return false;
}

function anBuildOptionBreakdownMap(key, uniqueOptions){
  const map = new Map();
  const isPlatformKey = new Set(['plat','plat2','acctPlat','pmPlat','finPlat','licPlat']).has(key);
  const rows = (key.startsWith('lic') ? empsFor(role) : EMPS).slice();

  if(isPlatformKey){
    const lics = rows.flatMap(e=>currentLicenses(e));
    uniqueOptions.forEach(option=>{
      const opt = String(option);
      const byPlat = lics.filter(l=>String(l.plat||'')===opt);
      const totalEmployees = rows.filter(r => currentLicenses(r).some(l => String(l.plat||'')===opt)).length;
      map.set(opt, {
        active: byPlat.filter(l=>String(l.st||'').toLowerCase()==='active').length,
        total: byPlat.length,
        totalEmployees,
      });
    });
    return map;
  }

  uniqueOptions.forEach(option=>{
    const opt = String(option);
    const matched = rows.filter(r=>anRowsMatchKeyValue(r,key,opt));
    const matchedLicenses = matched.flatMap(r => currentLicenses(r));
    const activeLicenses = matchedLicenses.filter(l => String(l.st||'').toLowerCase()==='active').length;
    map.set(opt, {
      active: activeLicenses,
      total: matchedLicenses.length,
      totalEmployees: matched.length,
    });
  });
  return map;
}

function anFilterEmpsBySelections(baseEmps, defs, excludeKey){
  let scoped = (baseEmps || []).slice();
  defs.forEach(def => {
    if(def.key === excludeKey) return;
    const sel = AN_SEL[def.key];
    if(sel && sel.size) scoped = scoped.filter(e => def.matches(e, sel));
  });
  return scoped;
}

function anBuildProgressiveOptions(baseEmps, defs){
  const optionsByKey = {};
  defs.forEach(def => {
    const scoped = anFilterEmpsBySelections(baseEmps, defs, def.key);
    const options = def.options(scoped);
    optionsByKey[def.key] = options;
    anKeepOnlyValidSelections(def.key, options);
  });
  return optionsByKey;
}

function anKeepOnlyValidSelections(key, validOptions){
  const valid = new Set(validOptions || []);
  const sel = AN_SEL[key] || (AN_SEL[key] = new Set());
  [...sel].forEach(v => { if(!valid.has(v)) sel.delete(v); });
  return sel;
}

/** Checkbox change — update AN_SEL and badge, but don't render until Filter clicked */
function anMsCheck(key, val, cb){
  val = decodeURIComponent(val);
  const s = AN_SEL[key] || (AN_SEL[key] = new Set());
  cb.checked ? s.add(val) : s.delete(val);

  // Update badge on button
  const btn = document.querySelector(`#an-ms-${key} .an-ms-btn`);
  if(btn){
    const placeholder = btn.getAttribute('data-placeholder') || btn.textContent.replace(/▾.*/,'').replace(/\s*\d+\s*$/,'').trim();
    if(!btn.hasAttribute('data-placeholder')) btn.setAttribute('data-placeholder', placeholder);
    const count = s.size;
    btn.classList.toggle('an-ms-active', count > 0);
    btn.innerHTML = (count === 0 ? placeholder : placeholder.replace(/^All /,'') + ` <span class="an-ms-badge">${count}</span>`) + '<span class="an-ms-arrow">▾</span>';
  }
  // Apply filter immediately on checkbox change
  anMsApply(key);
  // Re-open the panel since anMsApply closes all panels
  const panel = document.getElementById('an-ms-panel-'+key);
  const wrap  = document.getElementById('an-ms-'+key);
  if(panel){ panel.style.display='block'; wrap && wrap.classList.add('open'); }
}

/** Apply filter — render analytics or license register */
function anMsApply(key){
  if(key === 'licAcct') AN_SEL.licProj.clear();
  const licKeys = new Set(['licPlat','licEst','licLst','licUnit','licAcct','licProj']);
  if(licKeys.has(key)){
    licPage=1;
    renderLic();
  }
  else renderAnalytics();
}

/** Close all filter panels */
function anMsClose(){
  document.querySelectorAll('.an-ms-panel').forEach(p => { p.style.display='none'; });
  document.querySelectorAll('.an-ms').forEach(w => w.classList.remove('open'));
}

/** Close all panels when clicking outside */
document.addEventListener('click', function(e){
  if(!e.target.closest('.an-ms')){
    document.querySelectorAll('.an-ms-panel').forEach(p => { p.style.display='none'; });
    document.querySelectorAll('.an-ms').forEach(w => w.classList.remove('open'));
  }
});

/* ════════════════════════════════════
   ADMIN VIEW
════════════════════════════════════ */
function renderAnalyticsAdmin(){
  const sec = document.getElementById('sec-analytics');
  if(!sec) return;

  // Read filters from AN_SEL multi-select state
  const fGdl       = AN_SEL.gdl;
  const fAcct      = AN_SEL.acct;
  const fAcctOwner = AN_SEL.acctOwner;
  const fProj      = AN_SEL.proj;
  const fUnit      = AN_SEL.unit;
  const fPlat      = AN_SEL.plat;

  let emps = EMPS.slice();
  if(fGdl.size)       emps = emps.filter(e => fGdl.has(e.gdl));
  if(fAcct.size)      emps = emps.filter(e => fAcct.has(e.acct));
  if(fAcctOwner.size) emps = emps.filter(e => fAcctOwner.has(e.acctOwner));
  if(fProj.size)      emps = emps.filter(e => fProj.has(e.proj));
  if(fUnit.size)      emps = emps.filter(e => fUnit.has(e.unit));
  if(fPlat.size)      emps = emps.filter(e => currentLicenses(e).some(l => fPlat.has(l.plat)));

  let allL     = emps.flatMap(e => currentLicenses(e));
  if(fPlat.size) allL = allL.filter(l => fPlat.has(l.plat));
  const spend    = allL.reduce((s,l) => s+l.cost, 0);
  const empsWithLicenses = emps.filter(e => currentLicenses(e).length > 0).length;

  // Open alerts count — employees flagged by HRMS events
  const alertEmpIds = new Set();
  activeAlerts().filter(a => emps.some(e => matchesEmployeeRef(e, a.empId))).forEach(a => alertEmpIds.add(String(a.empId)));
  const openAlerts = alertEmpIds.size;

  // Pending revocation = employees with open alerts; Recoverable = their total license cost
  const pendingRevoc = openAlerts;
  const recover = emps.filter(e => alertEmpIds.has(String(e.id)) || alertEmpIds.has(displayEmpId(e))).flatMap(e => currentLicenses(e)).reduce((s,l) => s+l.cost, 0);

  // Renewal within 60d
  const today = new Date();
  const renewSoon = PLATFORMS.filter(p => {
    if(!p.renewal) return false;
    const d = Math.round((new Date(p.renewal)-today)/86400000);
    return d >= 0 && d <= 60;
  }).length;

  // Scope label
  const scopeParts = [];
  if(fAcct.size)      scopeParts.push([...fAcct].join(', '));
  if(fAcctOwner.size) scopeParts.push([...fAcctOwner].join(', '));
  if(fProj.size)      scopeParts.push([...fProj].join(', '));
  if(fUnit.size)      scopeParts.push([...fUnit].join(', '));
  const scopeLabel = scopeParts.length ? scopeParts.join(' · ') : 'All accounts · All projects · All units';
  const levelLabel = fProj.size ? 'Project level' : fAcct.size ? 'Account level' : fAcctOwner.size ? 'Account Owner level' : fGdl.size ? 'GDL level' : 'Org level';
  const hasAnyFilter = fGdl.size || fAcct.size || fAcctOwner.size || fProj.size || fUnit.size || fPlat.size;
  const displayTotalLicenses = !hasAnyFilter && LAST_LIVE_SUMMARY?.total_licenses != null ? LAST_LIVE_SUMMARY.total_licenses : allL.length;
  const displayEmployeesAssigned = !hasAnyFilter && LAST_LIVE_SUMMARY?.employee_count != null ? `${LAST_LIVE_SUMMARY.employee_count} employees assigned` : `${empsWithLicenses} employees assigned`;

  const adminOptions = anBuildProgressiveOptions(EMPS, [
    { key:'gdl',       matches:(e, sel)=>sel.has(e.gdl),       options:(rows)=>anSortedValues(rows.map(e=>e.gdl)) },
    { key:'acctOwner', matches:(e, sel)=>sel.has(e.acctOwner), options:(rows)=>anSortedValues(rows.map(e=>e.acctOwner)) },
    { key:'acct',      matches:(e, sel)=>sel.has(e.acct),      options:(rows)=>anSortedValues(rows.map(e=>e.acct)) },
    { key:'proj',      matches:(e, sel)=>sel.has(e.proj),      options:(rows)=>anSortedValues(rows.map(e=>e.proj)) },
    { key:'unit',      matches:(e, sel)=>sel.has(e.unit),      options:(rows)=>anSortedValues(rows.map(e=>e.unit)) },
    { key:'plat',      matches:(e, sel)=>currentLicenses(e).some(l => sel.has(l.plat)), options:(rows)=>anPlatformOptionsForEmps(rows) }
  ]);
  const _allGdls       = adminOptions.gdl;
  const _allAcctOwners = adminOptions.acctOwner;
  const _allAccts      = adminOptions.acct;
  const _allProjs      = adminOptions.proj;
  const _allUnits      = adminOptions.unit;
  const _allPlats      = adminOptions.plat;

  // Alert panel rows (top 3)
  const alertEmps = {};
  emps.forEach(e=>{
    alertEmps[String(e.id)] = e;
    const code = displayEmpId(e);
    if(code) alertEmps[code] = e;
  });
  const alertRows  = activeAlerts().filter(a => alertEmps[a.empId]).slice(0,3);
  const alertPanel = alertRows.length === 0 ? '' : `
  <div class="an-ap">
    <div class="an-ap-head">
      <div class="an-ap-title">Smart alerts <span class="an-ap-note">· pending review</span></div>
      <span class="an-ap-count">${openAlerts} open</span>
    </div>
    ${alertRows.map(a => {
      const e = alertEmps[a.empId];
      if(!e) return '';
      const totalCost = currentLicenses(e).reduce((s,l)=>s+l.cost,0);
      const barColor = a.type==='exit'?'var(--red)':a.type==='bench'?'#7c3aed':'var(--amber)';
      return `<div class="an-ap-row">
        <div class="an-ap-bar" style="background:${barColor}"></div>
        <div class="an-ap-emp">${e.name} <span class="an-ap-code">${displayEmpId(e)}</span></div>
        <div class="an-ap-detail">${fmtDateInStr(a.reason)}</div>
        <div class="an-ap-cost">${fmt(totalCost)}/Mth</div>
        <button class="btn bdk" style="font-size:11px;padding:3px 9px;margin-left:10px;flex-shrink:0;" onclick="show('alerts')">View alerts</button>
      </div>`;
    }).join('')}
  </div>`;

  // Revoke summary
  const exitedCount  = EMPS.filter(e=>String(e.status||'').toLowerCase()==='exited' && currentLicenses(e).length>0).length;
  const benchCount   = EMPS.filter(e=>String(e.status||'').toLowerCase()==='bench'  && currentLicenses(e).length>0).length;
  const flaggedCount = EMPS.filter(e=>currentLicenses(e).some(l=>l.st!=='active')).length;
  const revoke = (exitedCount+benchCount+flaggedCount) === 0 ? '' : `
  <div class="an-revoke">
    <div class="an-revoke-title">Licenses pending revocation <span class="an-revoke-note">Action needed</span></div>
    <div class="an-rc-tiles">
      <div class="an-rc-tile"><div class="an-rc-num" style="color:var(--red)">${exitedCount}</div><div class="an-rc-lbl">Exited employees</div></div>
      <div class="an-rc-tile"><div class="an-rc-num" style="color:#5a2db5">${benchCount}</div><div class="an-rc-lbl">Corporate Pool employees</div></div>
      <div class="an-rc-tile"><div class="an-rc-num" style="color:var(--amber)">${flaggedCount}</div><div class="an-rc-lbl">Flagged inactive</div></div>
    </div>
    ${recover>0?`<div class="an-rc-warn">! &nbsp;Recoverable: <strong>${fmt(recover)}/Mth &nbsp;~&nbsp; ${fmt(recover*12)}/yr</strong></div>`:''}
  </div>`;

  // Platform distribution seats — purchased seats from master data, active seats from the filtered employee scope
  const platSeatColorMap = {
    github: '#2b6cb0',
    cursor: '#6b3dc8',
    openai: '#b67800',
    'openai teams': '#b67800',
    'vis. studio': '#2f7d3f',
    'visual studio': '#2f7d3f',
    docker: '#c74634'
  };
  const platSeatsColors = ['#2b6cb0','#6b3dc8','#b67800','#2f7d3f','#c74634','var(--lime)'];
  const platSeatsData = anPlatformSeatSummary(emps, fPlat);
  const platSeatsHtml = platSeatsData.map((p,i) => {
    const color = platSeatColorMap[String(p.name || '').toLowerCase()] || platSeatsColors[i % platSeatsColors.length];
    const activePct = p.purchased > 0 ? Math.min(100, Math.round(p.active / p.purchased * 100)) : 0;
    const smallFill = activePct <= 14;
    const label = (p.hasPurchasedConfig
      ? '<span style="color:#f0b24d;font-weight:700;">' + p.purchased + ' purchased</span>'
      : '<span style="color:var(--amber);font-weight:700;">seat total not set</span>')
      + '<span style="color:#4b5563;"> - </span>'
      + '<span style="color:#111827;font-weight:700;">' + p.active + ' active</span>';
    const labelStyle = smallFill
      ? 'position:absolute;left:calc(' + activePct + '% + 8px);top:50%;transform:translateY(-50%);z-index:1;white-space:nowrap;mix-blend-mode:normal;'
      : 'position:absolute;left:12px;top:50%;transform:translateY(-50%);z-index:1;white-space:nowrap;mix-blend-mode:normal;';
    return '<div class="an-bc-row">'
      + '<div class="an-bc-lbl">' + p.name + '</div>'
      + '<div class="an-bc-track" style="position:relative;overflow:visible;">'
      +   '<div class="an-bc-fill" style="width:' + activePct + '%;background:' + color + ';position:relative;"></div>'
      +   '<span class="an-bc-inline" style="' + labelStyle + '">' + label + '</span>'
      + '</div>'
        + '<div class="an-bc-val" style="min-width:140px;white-space:nowrap;">' + (p.hasPurchasedConfig ? (p.purchased + ' purchased') : 'Seat total not set') + '<br><span style="color:var(--gray2);">\u00b7 ' + p.active + ' active</span></div>'
      + '</div>';
  }).join('');

  // Cost by account
  const acctCost = {};
  emps.forEach(e => currentLicenses(e).forEach(l => { acctCost[e.acct]=(acctCost[e.acct]||0)+l.cost; }));
  const acctCostHtml = '<div class="an-bar-scroll">' + anBarsFromMap(acctCost) + '</div>';

  // Distribution by unit (count + cost)
  const unitCount = {};
  const unitCost = {};
  emps.forEach(e => {
    if(e.unit) {
      unitCount[e.unit]=(unitCount[e.unit]||0)+currentLicenses(e).length;
      currentLicenses(e).forEach(l => { unitCost[e.unit]=(unitCost[e.unit]||0)+l.cost; });
    }
  });
  const maxUC = Math.max(...Object.values(unitCount),1);
  const unitHtml = Object.entries(unitCount).sort((a,b)=>b[1]-a[1]).map(([k,v],i)=>anBar(k,Math.round(v/maxUC*100),v+' lic · '+fmt(unitCost[k]||0)+'/Mth',platSeatsColors[i%platSeatsColors.length])).join('');

  // Trend — respects active filters (platform → single-platform history; account/unit/project → project-level rollup)
  const yr = latestSpendYear();
  const trendData = anComputeTrend(yr, emps, fPlat);

  // Platform seat utilization table rows
  const ptRows = platSeatsData.map((p,i) => {
    const avail = p.purchased - p.active;
    const uc = p.unitCost;
    const dL = p.renewal ? Math.round((new Date(p.renewal)-today)/86400000) : null;
    const rTd = dL!==null ? (dL<=30?`<span style="color:var(--red);font-weight:600;">${dL}d</span>`:dL<=60?`<span style="color:var(--amber);font-weight:600;">${dL}d</span>`:`<span style="font-size:11px;color:var(--gray2);">${p.renewal}</span>`) : '—';
    const seatDisplay = p.hasPurchasedConfig ? `${p.active}/${p.purchased}` : `${p.active}/unconfigured`;
    const availDisplay = p.hasPurchasedConfig ? (avail>=0 ? avail : 'Over by ' + Math.abs(avail)) : 'Not set';
    const availColor = p.hasPurchasedConfig ? (avail<0?'var(--red)':avail===0?'var(--amber)':'var(--green)') : 'var(--amber)';
    return `<tr style="background:${i%2===0?'transparent':'#faf8f4'}">
      <td><strong>${p.name}</strong><div style="font-size:10px;color:var(--gray2);">${p.cat}</div></td>
      <td style="font-size:11px;color:var(--gray2);">${platformTypeLabel(p.type)}</td>
      <td>${seatDisplay}</td>
      <td style="font-weight:600;color:${availColor};">${availDisplay}</td>
      <td>${fmt(uc)}/seat</td>
      <td>${fmt(p.active*uc)}/Mth</td>
      <td>${rTd}</td>
    </tr>`;
  }).join('');

  sec.innerHTML = `
    ${anStickyHead(
      anScopeBanner(scopeLabel, 'License Admin', levelLabel),
      `<div class="an-fbar">
      <span class="fbar-label">Filter by</span>
      ${anMsBuild('gdl',       'All GDLs',            _allGdls)}
      ${anMsBuild('acctOwner', 'All Account Owners',  _allAcctOwners)}
      ${anMsBuild('acct',      'All Accounts',        _allAccts)}
      ${anMsBuild('proj',      'All Projects',        _allProjs)}
      ${anMsBuild('unit',      'All Units',           _allUnits)}
      ${anMsBuild('plat',      'All Platforms',       _allPlats)}
      <button class="btn" style="font-size:11px;" onclick="anClearFilters()">Clear</button>
      <span class="an-roll" id="an-roll-tag">${levelLabel}</span>
    </div>`
    )}
    <div class="an-g5">
      <div class="an-kpi">
        <div class="an-kpi-accent" style="background:var(--green)"></div>
        <div class="an-kpi-lbl">Total licenses</div>
        <div class="an-kpi-val" id="an-kpi-total-licenses" style="color:var(--green)">${displayTotalLicenses}</div>
        <div class="an-kpi-sub">${scopeLabel}<div class="an-kpi-sub2" id="an-kpi-total-licenses-sub2">${displayEmployeesAssigned}</div></div>
      </div>
      ${anKpiCard('var(--blue)',   'Monthly spend',      fmt(spend),       'var(--blue)',   'Annual: '+fmt(spend*12))}
      ${anKpiCard('var(--red)',    'Pending revocation', pendingRevoc,     pendingRevoc>0?'var(--red)':'var(--black)', pendingRevoc>0?'<a href="#" onclick="show(\'alerts\'); return false;" style="color:inherit;text-decoration:underline;cursor:pointer;">> Smart Alerts for detail</a>':'All licenses accounted for')}
      ${anKpiCard('var(--amber)',  'Recoverable / Mth',   fmt(recover),     recover>0?'var(--amber)':'var(--black)', recover>0?fmt(recover*12)+'/yr saving':'Nothing recoverable')}
      ${anKpiCard('var(--border)', 'Renewals ≤ 60d',    renewSoon,        renewSoon>0?'var(--amber)':'var(--black)', renewSoon>0?'Action required':'All clear')}
    </div>
    <div class="an-g2">
      <div class="an-card">
        <div class="an-card-title">Platform distribution — seats <span class="an-card-note">${scopeLabel}</span></div>
        ${platSeatsHtml || '<div style="color:var(--gray2);font-size:12px;">No data</div>'}
      </div>
      <div class="an-card">
        <div class="an-card-title">Cost by account <span class="an-card-note">Monthly</span></div>
        ${acctCostHtml || '<div style="color:var(--gray2);font-size:12px;">No data</div>'}
      </div>
    </div>
    <div class="an-g2">
      <div class="an-card">
        <div class="an-card-title">Distribution by unit <span class="an-card-note">License count</span></div>
        <div class="an-bar-scroll an-unit-scroll">${unitHtml || '<div style="color:var(--gray2);font-size:12px;">No data</div>'}</div>
      </div>
      <div class="an-card">
        <div class="an-card-title">Month-on-month spend <span class="an-card-note">${scopeLabel} ${yr}</span></div>
        ${anTrendHtml(trendData, 'var(--lime)', anTrendMeta(trendData, emps))}
      </div>
    </div>
    <div class="an-gfull an-card">
      <div class="an-card-title">Platform seat utilisation <span class="an-card-note">${scopeLabel}</span></div>
      <div style="overflow-x:auto;">
        <table class="tbl">
          <thead><tr><th>Platform</th><th>Type</th><th>Seats (active/total)</th><th>Available</th><th>Unit cost</th><th>Monthly total</th><th>Renewal</th></tr></thead>
          <tbody>${ptRows}</tbody>
        </table>
      </div>
    </div>`;

  if(!hasAnyFilter) fetchAndUpdateAnalyticsTotalLicenses();
}

function anClearFilters(){
  // Clear multi-select state (admin filters)
  Object.keys(AN_SEL).forEach(k => AN_SEL[k].clear());
  // Clear legacy <select> filters used by other role views
  ['an-f-gdl2','an-f-acct2','an-f-proj2','an-f-plat2','an-f-yr','an-f-acct3','an-f-plat3'].forEach(id=>{
    const el=document.getElementById(id); if(el) el.value='';
  });
  renderAnalytics();
}

/* ════════════════════════════════════
   GDL VIEW
════════════════════════════════════ */
function renderAnalyticsGdl(){
  const sec = document.getElementById('sec-analytics');
  if(!sec) return;

  const fAcct  = AN_SEL.acct2;
  const fProj  = AN_SEL.proj2;
  const fPlat  = AN_SEL.plat2;

  const sess = currentSessionUser();
  const gdlOptions = anBuildProgressiveOptions(EMPS, [
    { key:'acct2', matches:(e, sel)=>sel.has(e.acct), options:(rows)=>anSortedValues(rows.map(e=>e.acct)) },
    { key:'proj2', matches:(e, sel)=>sel.has(e.proj), options:(rows)=>anSortedValues(rows.map(e=>e.proj)) },
    { key:'plat2', matches:(e, sel)=>currentLicenses(e).some(l => sel.has(l.plat)), options:(rows)=>anPlatformOptionsForEmps(rows) }
  ]);
  const myAccounts = gdlOptions.acct2;
  const myProjects = gdlOptions.proj2;
  const myPlatforms = gdlOptions.plat2;
  let emps = EMPS.slice(); // backend already scopes to GDL
  if(fAcct.size) emps = emps.filter(e => fAcct.has(e.acct));
  if(fProj.size) emps = emps.filter(e => fProj.has(e.proj));
  if(fPlat.size) emps = emps.filter(e => currentLicenses(e).some(l => fPlat.has(l.plat)));

  let allL   = emps.flatMap(e => currentLicenses(e));
  if(fPlat.size) allL = allL.filter(l => fPlat.has(l.plat));
  const activeLicenses = allL.filter(l => String(l.st || '').toLowerCase() === 'active').length;
  const flagged = allL.filter(l => l.st !== 'active');
  const spend  = allL.reduce((s,l) => s+l.cost, 0);
  const recover= flagged.reduce((s,l) => s+l.cost, 0);
  const openAlerts = activeAlerts().filter(a => emps.some(e => matchesEmployeeRef(e, a.empId))).length;

  const scopeLabel = fProj.size ? anSelectedValues('proj2').join(', ') : fAcct.size ? anSelectedValues('acct2').join(', ') : (sess.dept || 'GDL scope');
  const levelLabel = fProj.size ? 'Project level' : fAcct.size ? 'Account level' : 'GDL level';

  // Account rollup rows — reflect current filter scope
  const acctMap = {};
  emps.forEach(e => {
    if(!acctMap[e.acct]) acctMap[e.acct]={emps:0,lic:0,cost:0,flagged:0};
    acctMap[e.acct].emps++;
    currentLicenses(e).forEach(l=>{acctMap[e.acct].lic++;acctMap[e.acct].cost+=l.cost;if(l.st!=='active')acctMap[e.acct].flagged++;});
  });
  const acctEntries = Object.entries(acctMap).filter(([,d]) => d.cost > 0).map(([acct,d]) => ({
    name: acct,
    sub: `${d.emps} employees`,
    stats: [
      {v: d.lic,          l:'Licenses'},
      {v: fmt(d.cost)+'/mo', l:'Spend', c:'var(--blue)'},
      {v: d.flagged>0?d.flagged+' flagged':'Clear', l:'Alerts', c:d.flagged>0?'var(--amber)':'var(--green)'},
    ]
  }));
  const acctHidden = Math.max(0, acctEntries.length - 3);
  const acctRows = anRollupRowList(acctEntries, gdlAcctExpanded);
  const acctToggle = acctHidden > 0 ? `<button class="an-sec-btn" onclick="toggleGdlAcctExpand()">${gdlAcctExpanded ? 'Show less' : `Show ${acctHidden} more`} <span class="an-sec-btn-arrow">${gdlAcctExpanded ? '▲' : '▼'}</span></button>` : '';

  // Project rollup rows
  const projMap = {};
  emps.forEach(e => {
    if(!projMap[e.proj]) projMap[e.proj]={acct:e.acct,emps:0,lic:0,cost:0,flagged:0};
    projMap[e.proj].emps++;
    currentLicenses(e).forEach(l=>{projMap[e.proj].lic++;projMap[e.proj].cost+=l.cost;if(l.st!=='active')projMap[e.proj].flagged++;});
  });
  const projEntries = Object.entries(projMap).filter(([,d]) => d.cost > 0).map(([proj,d]) => ({
    name: proj,
    sub: `${d.acct} · ${d.emps} employees`,
    stats: [
      {v: d.lic,          l:'Licenses'},
      {v: fmt(d.cost)+'/mo', l:'Spend', c:'var(--blue)'},
      {v: d.flagged>0?d.flagged+' flagged':'Clear', l:'', c:d.flagged>0?'var(--amber)':'var(--green)'},
    ]
  }));
  const projHidden = Math.max(0, projEntries.length - 3);
  const projRows = projEntries.length > 0 ? anRollupRowList(projEntries, gdlProjExpanded) : '<div style="color:var(--gray2);font-size:12px;padding:8px 0;">No projects match.</div>';
  const projToggle = projHidden > 0 ? `<button class="an-sec-btn" onclick="toggleGdlProjExpand()">${gdlProjExpanded ? 'Show less' : `Show ${projHidden} more`} <span class="an-sec-btn-arrow">${gdlProjExpanded ? '▲' : '▼'}</span></button>` : '';

  // Cost by platform with per-license breakup
  const platCost = anBuildPlatformCostMap(emps);
  const platCostHtml = anBarsFromPlatformCostMap(platCost);

  // Trend — respects account/project/platform filters
  const yr = latestSpendYear();
  const trendData = anComputeTrend(yr, emps, fPlat);

  // Account comparison table
  const acctTableRows = Object.entries(acctMap).filter(([,d]) => d.cost > 0).map(([ acct, d], i) => {
    const acctProjects = Object.entries(projMap).filter(([, p]) => p.acct === acct && p.lic > 0);
    const projHeaderRow = acctProjects.length > 0 ? `<tr style="background:#f5f3f0;display:none;" class="acct-expand-row-${acct.replace(/\s+/g, '_')}">
      <td colspan="5" style="padding:0;">
        <table style="width:100%;border:none;">
          <tr style="background:#eae8e4;border-bottom:1px solid var(--tan2);">
            <th style="padding:8px 12px;color:var(--gray2);font-size:10px;font-weight:600;text-align:left;width:35%;">PROJECT</th>
            <th style="padding:8px 12px;color:var(--gray2);font-size:10px;font-weight:600;text-align:center;width:15%;">LICENSES</th>
            <th style="padding:8px 12px;color:var(--gray2);font-size:10px;font-weight:600;text-align:center;width:15%;">LICENSED EMPS</th>
            <th style="padding:8px 12px;color:var(--gray2);font-size:10px;font-weight:600;text-align:center;width:35%;">% LICENSED</th>
          </tr>
        </table>
      </td>
    </tr>` : '';
    const projTableHtml = acctProjects.map(([proj, p], j) => {
      const totalEmps = emps.filter(e => e.proj === proj).length;
      const licensedEmps = emps.filter(e => e.proj === proj && currentLicenses(e).length > 0).length;
      const pct = totalEmps > 0 ? Math.round(licensedEmps / totalEmps * 100) : 0;
      return `<tr style="background:#f5f3f0;display:none;" class="acct-expand-row-${acct.replace(/\s+/g, '_')}">
        <td colspan="5" style="padding:0;">
          <table style="width:100%;border:none;">
            <tr style="background:transparent;border-bottom:1px solid var(--tan2);">
              <td style="padding:8px 12px;color:var(--gray2);font-size:11px;width:35%;"><strong>${proj}</strong></td>
              <td style="padding:8px 12px;text-align:center;color:var(--gray2);font-size:11px;width:15%;">${p.lic}</td>
              <td style="padding:8px 12px;text-align:center;color:var(--gray2);font-size:11px;width:15%;">${licensedEmps}</td>
              <td style="padding:8px 12px;width:35%;">
                <div style="display:flex;align-items:center;gap:6px;">
                  <div style="flex:1;background:var(--tan2);border-radius:4px;height:6px;overflow:hidden;min-width:60px;">
                    <div style="width:${pct}%;background:var(--blue);height:100%;border-radius:4px;"></div>
                  </div>
                  <span style="font-size:11px;font-weight:600;min-width:32px;">${pct}%</span>
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>`;
    }).join('');

    return `<tr style="background:${i%2===0?'transparent':'#faf8f4'}" data-acct="${acct}">
      <td>
        <button class="acct-expand-btn" style="background:none;border:none;padding:0 6px 0 0;cursor:pointer;color:var(--gray2);font-size:10px;vertical-align:middle;" onclick="toggleAcctExpand(this)" data-acct="${acct.replace(/\s+/g, '_')}">${acctProjects.length > 0 ? '▼' : '—'}</button><strong>${acct}</strong>
      </td>
      <td>${[...new Set(emps.filter(e=>e.acct===acct).map(e=>e.proj))].length}</td>
      <td>${d.emps}</td>
      <td class="mono">${fmt(d.cost)}</td>
      <td style="font-weight:600;color:${d.flagged>0?'var(--amber)':'var(--green)'};">${d.flagged>0?d.flagged+' flagged':'Clear'}</td>
    </tr>
    ${projHeaderRow}
    ${projTableHtml}`;
  }).join('');

  sec.innerHTML = `
    ${anStickyHead(
      anScopeBanner(scopeLabel, sess.dept || 'GDL', levelLabel),
      `<div class="an-fbar">
      <span class="fbar-label">Filter by</span>
      ${anMsBuild('acct2', 'All Accounts', myAccounts)}
      ${anMsBuild('proj2', 'All Projects', myProjects)}
      ${anMsBuild('plat2', 'All Platforms', myPlatforms)}
      <button class="btn" style="font-size:11px;" onclick="anClearFilters()">Clear</button>
      <span class="an-roll">${levelLabel}</span>
    </div>`
    )}
    <div class="an-g5">
      ${anKpiCard('var(--green)',  'Active licenses',    activeLicenses,   'var(--green)',  scopeLabel)}
      ${anKpiCard('var(--blue)',   'Monthly spend',      fmt(spend),       'var(--blue)',   'Annual: '+fmt(spend*12))}
      ${anKpiCard('var(--amber)',  'Flagged', flagged.length,   flagged.length>0?'var(--amber)':'var(--black)', flagged.length>0?'Needs review':'All licenses active')}
      ${anKpiCard('var(--red)',    'Recoverable / Mth',   fmt(recover),     recover>0?'var(--red)':'var(--black)',   recover>0?'Idle licenses':'Nothing recoverable')}
      ${anKpiCard('var(--border)', 'Annual projection',  fmt(spend*12),    '',              'At current spend rate')}
    </div>
    ${anSecAction('By account — roll-up', acctToggle)}
    ${acctRows}
    ${anSecAction('By project — use account filter above to drill down', projToggle)}
    ${projRows}
    <div class="an-g2" style="margin-top:12px;">
      <div class="an-card">
        <div class="an-card-title">Cost by platform <span class="an-card-note">${scopeLabel}</span></div>
        ${platCostHtml || '<div style="color:var(--gray2);font-size:12px;">No data</div>'}
      </div>
      <div class="an-card">
        <div class="an-card-title">Monthly spend trend <span class="an-card-note">${yr}</span></div>
        ${anTrendHtml(trendData, '#1a5fa8', anTrendMeta(trendData, emps))}
      </div>
    </div>
    <div class="an-gfull an-card">
      <div class="an-card-title">Account comparison — monthly cost</div>
      <div style="overflow-x:auto;">
        <table class="tbl">
          <thead><tr><th>Account</th><th>Projects</th><th>Employees</th><th>Monthly cost</th><th>Status</th></tr></thead>
          <tbody>${acctTableRows}</tbody>
        </table>
      </div>
      <div style="font-size:11px;color:var(--gray2);padding:8px 0;margin-top:8px;">Click the expand arrow (▼) next to account names to view project-wise license breakdown.</div>
    </div>`;
}

function toggleAcctExpand(btn){
  const acct = btn.getAttribute('data-acct');
  const rows = document.querySelectorAll(`.acct-expand-row-${acct}`);
  const isExpanded = rows[0]?.style.display !== 'none';
  rows.forEach(row => {
    row.style.display = isExpanded ? 'none' : 'table-row';
  });
  btn.textContent = isExpanded ? '▼' : '▲';
}

function anGdlAcctChange(){
  AN_SEL.proj2.clear();
  renderAnalytics();
}

/* ════════════════════════════════════
   ACCOUNT OWNER VIEW
════════════════════════════════════ */
function renderAnalyticsAccount(){
  const sec = document.getElementById('sec-analytics');
  if(!sec) return;

  const fProj = AN_SEL.acctProj;
  const fPlat = AN_SEL.acctPlat;
  const sess  = currentSessionUser();

  let emps = EMPS.slice(); // already scoped to account by backend
  if(fProj.size) emps = emps.filter(e => fProj.has(e.proj));
  if(fPlat.size) emps = emps.filter(e => currentLicenses(e).some(l => fPlat.has(l.plat)));

  const myAccount  = [...new Set(EMPS.map(e=>e.acct).filter(Boolean))][0] || 'Your account';
  let allL       = emps.flatMap(e => currentLicenses(e));
  if(fPlat.size) allL = allL.filter(l => fPlat.has(l.plat));
  const activeLicenses = allL.filter(l => String(l.st || '').toLowerCase() === 'active').length;
  const spend      = allL.reduce((s,l)=>s+l.cost,0);
  const alertStats = anScopedAlertStats(emps);
  const flagged    = alertStats.flaggedLicenses;
  const recover    = alertStats.recoverableCost;

  const scopeLabel = fProj.size ? `${myAccount} · ${anSelectedValues('acctProj').join(', ')}` : `${myAccount} — All projects`;
  const levelLabel = fProj.size ? 'Project level' : 'Account level';

  const accountOptions = anBuildProgressiveOptions(EMPS, [
    { key:'acctProj', matches:(e, sel)=>sel.has(e.proj), options:(rows)=>anSortedValues(rows.map(e=>e.proj)) },
    { key:'acctPlat', matches:(e, sel)=>currentLicenses(e).some(l => sel.has(l.plat)), options:(rows)=>anPlatformOptionsForEmps(rows) }
  ]);
  const myProjects = accountOptions.acctProj;
  const myPlatforms = accountOptions.acctPlat;

  // Project rollup rows — reflect current filter scope
  const projMap = {};
  emps.forEach(e=>{
    if(!projMap[e.proj]) projMap[e.proj]={emps:0,lic:0,cost:0,flagged:0};
    projMap[e.proj].emps++;
    currentLicenses(e).forEach(l=>{projMap[e.proj].lic++;projMap[e.proj].cost+=l.cost;if(l.st!=='active')projMap[e.proj].flagged++;});
  });
  const projRows = Object.entries(projMap).filter(([,d]) => d.cost > 0).map(([proj,d]) => anRollupRow(proj, `${myAccount} · ${d.emps} employees`, [
    {v: d.lic,          l:'Licenses'},
    {v: fmt(d.cost)+'/mo', l:'Spend', c:'var(--blue)'},
    {v: d.flagged>0?d.flagged+' flagged':'Clear', l:'', c:d.flagged>0?'var(--amber)':'var(--green)'},
  ])).join('');

  // Cost by platform with per-license breakup
  const platCost = anBuildPlatformCostMap(emps);
  const platCostHtml = anBarsFromPlatformCostMap(platCost);

  // Trend — respects project/platform filters
  const yr = latestSpendYear();
  const trendData = anComputeTrend(yr, emps, fPlat);

  // Project comparison table
  const projTableRows = Object.entries(projMap).filter(([,d]) => d.cost > 0).map(([proj,d],i) => `<tr style="background:${i%2===0?'transparent':'#faf8f4'}">
    <td><strong>${proj}</strong></td>
    <td>${myAccount}</td>
    <td>${d.emps}</td>
    <td>${d.lic}</td>
    <td class="mono">${fmt(d.cost)}</td>
    <td style="color:${d.flagged>0?'var(--amber)':'var(--green)'};">${d.flagged>0?d.flagged+' flagged':'Clear'}</td>
  </tr>`).join('');

  sec.innerHTML = `
    ${anStickyHead(
      anScopeBanner(scopeLabel, 'Account Owner', levelLabel),
      `<div class="an-fbar">
      <span class="fbar-label">Filter by</span>
      <span class="an-roll" style="margin-left:0;background:#f5efe4;color:var(--gray);">${myAccount}</span>
      ${anMsBuild('acctProj', 'All Projects', myProjects)}
      ${anMsBuild('acctPlat', 'All Platforms', myPlatforms)}
      <button class="btn" style="font-size:11px;" onclick="anClearFilters()">Clear</button>
      <span class="an-roll">${levelLabel}</span>
    </div>`
    )}
    <div class="an-g5">
      ${anKpiCard('var(--green)',  'Active licenses',    activeLicenses,   'var(--green)',  scopeLabel)}
      ${anKpiCard('var(--blue)',   'Monthly spend',      fmt(spend),       'var(--blue)',   'Annual: '+fmt(spend*12))}
      ${anKpiCard('var(--amber)',  'Flagged', flagged,          flagged>0?'var(--amber)':'var(--black)', flagged>0?'Needs review':'All licenses active')}
      ${anKpiCard('var(--red)',    'Recoverable / Mth',   fmt(recover),     recover>0?'var(--red)':'var(--black)',   recover>0?'Idle licenses':'Nothing recoverable')}
      ${anKpiCard('var(--border)', 'Annual projection',  fmt(spend*12),    '',              'At current spend rate')}
    </div>
    ${anSec('By project — drill down using filter above')}
    ${projRows}
    <div class="an-g2" style="margin-top:12px;">
      <div class="an-card">
        <div class="an-card-title">Cost by platform <span class="an-card-note">${scopeLabel}</span></div>
        ${platCostHtml || '<div style="color:var(--gray2);font-size:12px;">No data</div>'}
      </div>
      <div class="an-card">
        <div class="an-card-title">Monthly spend trend <span class="an-card-note">${yr}</span></div>
        ${anTrendHtml(trendData, '#1a5fa8', anTrendMeta(trendData, emps))}
      </div>
    </div>
    <div class="an-gfull an-card">
      <div class="an-card-title">Project cost comparison — monthly</div>
      <div style="overflow-x:auto;">
        <table class="tbl">
          <thead><tr><th>Project</th><th>Account</th><th>Employees</th><th>Licenses</th><th>Monthly cost</th><th>Status</th></tr></thead>
          <tbody>${projTableRows}</tbody>
        </table>
      </div>
    </div>`;
}

/* ════════════════════════════════════
   PM VIEW
════════════════════════════════════ */
function renderAnalyticsPm(){
  const sec = document.getElementById('sec-analytics');
  if(!sec) return;

  const fPlat = AN_SEL.pmPlat;
  const sess  = currentSessionUser();

  let emps = EMPS.slice(); // backend scopes to project
  if(fPlat.size) emps = emps.filter(e => currentLicenses(e).some(l => fPlat.has(l.plat)));

  const myProject  = [...new Set(EMPS.map(e=>e.proj).filter(Boolean))][0] || 'Your project';
  const myAccount  = [...new Set(EMPS.map(e=>e.acct).filter(Boolean))][0] || '';
  let allL       = emps.flatMap(e => currentLicenses(e));
  if(fPlat.size) allL = allL.filter(l => fPlat.has(l.plat));
  const activeLicenses = allL.filter(l => String(l.st || '').toLowerCase() === 'active').length;
  const spend      = allL.reduce((s,l)=>s+l.cost,0);
  const alertStats = anScopedAlertStats(emps);
  const flagged    = alertStats.flaggedLicenses;
  const recover    = alertStats.recoverableCost;

  const scopeLabel = `${myProject} · ${myAccount}`;

  const pmOptions = anBuildProgressiveOptions(EMPS, [
    { key:'pmPlat', matches:(e, sel)=>currentLicenses(e).some(l => sel.has(l.plat)), options:(rows)=>anPlatformOptionsForEmps(rows) }
  ]);
  const myPlatforms = pmOptions.pmPlat;

  // Licenses by platform
  const platCost = {};
  emps.forEach(e => currentLicenses(e).forEach(l=>{platCost[l.plat]=(platCost[l.plat]||0)+l.cost;}));
  const platCostHtml = anBarsFromMap(platCost);

  // Platform seats
  const platSeats = {};
  emps.forEach(e => currentLicenses(e).forEach(l=>{platSeats[l.plat]=(platSeats[l.plat]||0)+1;}));
  const maxPS = Math.max(...Object.values(platSeats),1);
  const platSeatsColors = ['#1a5fa8','#5a2db5','#2d7a3a','#9a6200','#c0392b'];
  const platSeatsHtml  = Object.entries(platSeats).sort((a,b)=>b[1]-a[1]).map(([k,v],i)=>anBar(k,Math.round(v/maxPS*100),v+' seats · '+fmt(platCost[k]||0)+'/mo',platSeatsColors[i%platSeatsColors.length])).join('');

  // Trend — respects platform filter
  const yr = latestSpendYear();
  const trendData = anComputeTrend(yr, emps, fPlat);

  // Team table
  const scMap = {active:'pa',inactive:'pi',flagged:'pf',exited:'pe',bench:'pb'};
  const teamRows = emps.filter(e => activeCurrentLicenses(e).reduce((s,l)=>s+l.cost,0) > 0).map((e,i) => {
    const current = currentLicenses(e);
    const empStatus = employeeStatusDisplay(e);
    const licStatus = licenseStatusDisplay(e);
    const cost = activeCurrentLicenses(e).reduce((s,l)=>s+l.cost,0);
    const tags = current.map(l=>`<span class="ltag ${l.st==='active'?'ltok':'ltwarn'}">${l.plat}</span>`).join(' ');
    return `<tr style="background:${i%2===0?'transparent':'#faf8f4'}">
      <td><strong>${e.name}</strong><div style="font-size:10px;color:var(--gray2);">${displayEmpId(e)}</div></td>
      <td><span class="pill punit">${e.unit}</span></td>
      <td style="max-width:160px;">${tags||'—'}</td>
      <td><span class="pill ${empStatus.pill}">${empStatus.label}</span></td>
      <td style="font-size:11px;color:var(--gray2);">${licenseLastUsed(e)||'—'}</td>
      <td class="mono"><strong>${fmt(cost)}</strong></td>
    </tr>`;
  }).join('');

  sec.innerHTML = `
    ${anStickyHead(
      anScopeBanner(scopeLabel, 'Project Manager', 'Project level'),
      `<div class="an-fbar">
      <span class="fbar-label">Filter by</span>
      <span class="an-roll" style="margin-left:0;background:#f5efe4;color:var(--gray);">${myProject}</span>
      ${anMsBuild('pmPlat', 'All Platforms', myPlatforms)}
      <button class="btn" style="font-size:11px;" onclick="anClearFilters()">Clear</button>
      <span class="an-roll">Project level</span>
    </div>`
    )}
    <div class="an-g5">
      ${anKpiCard('var(--green)',  'Active licenses',    activeLicenses,   'var(--green)',  scopeLabel)}
      ${anKpiCard('var(--blue)',   'Monthly spend',      fmt(spend),       'var(--blue)',   'Annual: '+fmt(spend*12))}
      ${anKpiCard('var(--amber)',  'Flagged', flagged,          flagged>0?'var(--amber)':'var(--black)', flagged>0?'Needs review':'All licenses active')}
      ${anKpiCard('var(--red)',    'Recoverable / Mth',   fmt(recover),     recover>0?'var(--red)':'var(--black)',   recover>0?'Idle licenses':'Nothing recoverable')}
      ${anKpiCard('var(--border)', 'Annual projection',  fmt(spend*12),    '',              'At current spend rate')}
    </div>
    <div class="an-g2">
      <div class="an-card">
        <div class="an-card-title">Licenses by platform <span class="an-card-note">${myProject}</span></div>
        ${platSeatsHtml || '<div style="color:var(--gray2);font-size:12px;">No data</div>'}
      </div>
      <div class="an-card">
        <div class="an-card-title">Monthly spend trend <span class="an-card-note">${myProject} ${yr}</span></div>
        ${anTrendHtml(trendData, 'var(--lime)', anTrendMeta(trendData, emps))}
      </div>
    </div>
    <div class="an-gfull an-card">
      <div class="an-card-title">Team license detail</div>
      <div style="overflow-x:auto;">
        <table class="tbl">
          <thead><tr><th>Employee</th><th>Unit</th><th>Platforms</th><th>Status</th><th>Last used</th><th>Cost/mo</th></tr></thead>
          <tbody>${teamRows || '<tr><td colspan="6" style="text-align:center;color:var(--gray2);padding:16px;">No license data</td></tr>'}</tbody>
        </table>
      </div>
    </div>`;
}

/* ════════════════════════════════════
   FINANCE VIEW
════════════════════════════════════ */
function anProjGrpToggle(hdrRow){
  const id = hdrRow.dataset.acctId;
  const tgl = hdrRow.querySelector('.ptgl');
  const children = hdrRow.closest('tbody').querySelectorAll('[data-parent="'+id+'"]');
  const collapsed = children.length > 0 && children[0].style.display === 'none';
  children.forEach(r => { r.style.display = collapsed ? '' : 'none'; });
  if(tgl) tgl.textContent = collapsed ? '▼' : '▶';
}

function renderAnalyticsFinance(){
  const sec = document.getElementById('sec-analytics');
  if(!sec) return;

  const years  = Object.keys(MONTHLY_SPEND).sort((a,b)=>Number(b)-Number(a));
  anKeepOnlyValidSelections('finYr', years);
  let yearsInUse = anSelectedValues('finYr').filter(y => years.includes(y));
  if(yearsInUse.length === 0 && years.length > 0) {
    const latestYear = years[0];
    AN_SEL.finYr.add(latestYear);
    yearsInUse = [latestYear];
  }
  const selectedYears = yearsInUse.length ? yearsInUse : [latestSpendYear()];
  const yearLabel = selectedYears.join(', ');
  const fAcct = AN_SEL.finAcct;
  const fPlat = AN_SEL.finPlat;
  const fGdl  = AN_SEL.finGdl;
  const fOwner = AN_SEL.finOwner;

  let financeEmps = EMPS.slice();
  if(fGdl.size)   financeEmps = financeEmps.filter(e => fGdl.has(e.gdl||''));
  if(fOwner.size) financeEmps = financeEmps.filter(e => fOwner.has(e.acctOwner||''));
  if(fAcct.size)  financeEmps = financeEmps.filter(e => fAcct.has(e.acct));
  if(fPlat.size)  financeEmps = financeEmps.filter(e => currentLicenses(e).some(l => fPlat.has(l.plat)));

  const allL = financeEmps.flatMap(e => currentLicenses(e));
  const spend = allL.reduce((s,l)=>s+Number(l.cost||0),0);
  const empsWithLicenses = financeEmps.filter(e => currentLicenses(e).length > 0).length;
  const hasAnyFinanceFilter = fGdl.size || fOwner.size || fAcct.size || fPlat.size;
  const displayTotalLicenses = !hasAnyFinanceFilter && LAST_LIVE_SUMMARY?.total_licenses != null ? LAST_LIVE_SUMMARY.total_licenses : allL.length;
  const displayEmployeesAssigned = !hasAnyFinanceFilter && LAST_LIVE_SUMMARY?.employee_count != null ? LAST_LIVE_SUMMARY.employee_count : empsWithLicenses;

  const financeAlertEmpIds = new Set();
  activeAlerts().forEach(a => {
    if(financeEmps.some(e => matchesEmployeeRef(e, a.empId))) financeAlertEmpIds.add(String(a.empId));
  });
  const recover = financeEmps
    .filter(e => financeAlertEmpIds.has(String(e.id)) || financeAlertEmpIds.has(displayEmpId(e)))
    .flatMap(e => currentLicenses(e))
    .reduce((s,l)=>s+Number(l.cost||0),0);

  const gdlOptions = anSortedValues(EMPS.map(e=>e.gdl||'').filter(Boolean));
  const financeOptions = anBuildProgressiveOptions(EMPS, [
    { key:'finGdl',   matches:(e, sel)=>sel.has(e.gdl||''),  options:(rows)=>anSortedValues(rows.map(e=>e.gdl||'').filter(Boolean)) },
    { key:'finOwner', matches:(e, sel)=>sel.has(e.acctOwner||''),    options:(rows)=>anSortedValues(rows.map(e=>e.acctOwner||'').filter(Boolean)) },
    { key:'finAcct',  matches:(e, sel)=>sel.has(e.acct),             options:(rows)=>anSortedValues(rows.map(e=>e.acct)) },
    { key:'finPlat',  matches:(e, sel)=>currentLicenses(e).some(l => sel.has(l.plat)), options:(rows)=>anPlatformOptionsForEmps(rows) }
  ]);
  const acctOptions = financeOptions.finAcct;
  const platOptions = financeOptions.finPlat;
  const ownerOptions = financeOptions.finOwner;

  const trendData = anComputeTrendMulti(selectedYears, financeEmps, fPlat.size > 0 ? fPlat : null);
  const totalAnnual = Array.isArray(trendData) ? trendData.reduce((s,v)=>s+(Number(v)||0),0) : 0;
  const q1 = Array.isArray(trendData) ? (Number(trendData[3]||0)+Number(trendData[4]||0)+Number(trendData[5]||0)) : 0;
  const q4 = Array.isArray(trendData) ? (Number(trendData[0]||0)+Number(trendData[1]||0)+Number(trendData[2]||0)) : 0;
  const trendPct = q1===0 ? 0 : Math.round((q4-q1)/q1*100);

  const acctCost = {};
  financeEmps.forEach(e => currentLicenses(e).forEach(l=>{acctCost[e.acct]=(acctCost[e.acct]||0)+Number(l.cost||0);}));
  const acctCostHtml = '<div class="an-bar-scroll">' + anBarsFromMap(acctCost) + '</div>';

  const platCost = anBuildPlatformCostMap(financeEmps);
  const platCostHtml = anBarsFromPlatformCostMap(platCost);

  const yearProj = anAggregateProjectData(selectedYears);
  const empProjSet = new Set(financeEmps.map(e=>e.proj).filter(Boolean));
  const filteredYearProj = empProjSet.size > 0
    ? Object.fromEntries(Object.entries(yearProj).filter(([proj]) => empProjSet.has(proj)))
    : yearProj;
  
  const projLicCounts={};
  financeEmps.forEach(e=>{if(e.proj) projLicCounts[e.proj]=(projLicCounts[e.proj]||0)+currentLicenses(e).length;});
  
  // Group projects by account, sorted by total annual spend descending
  const projsByAcct = {};
  Object.entries(filteredYearProj).filter(([,arr]) => arr.reduce((s,v)=>s+v,0) > 0).forEach(([proj,arr]) => {
    const acctRow = financeEmps.find(e=>e.proj===proj);
    const acct = acctRow ? acctRow.acct : ((PROJ_META[proj]&&PROJ_META[proj].acct)||'—');
    if(!projsByAcct[acct]) projsByAcct[acct] = [];
    projsByAcct[acct].push({proj, arr, total: arr.reduce((s,v)=>s+v,0), licCount: projLicCounts[proj]||0});
  });
  const acctGroups = Object.entries(projsByAcct).sort((a,b) => {
    const sumA = a[1].reduce((s,p)=>s+p.total,0);
    const sumB = b[1].reduce((s,p)=>s+p.total,0);
    return sumB - sumA;
  });
  let projTableRows = '';
  if(acctGroups.length === 0) {
    projTableRows = '<tr><td colspan="17" style="text-align:center;color:var(--gray2);padding:16px;">No project data for this year</td></tr>';
  } else {
    acctGroups.forEach(([acct, projs]) => {
      const acctTotal = projs.reduce((s,p)=>s+p.total,0);
      const acctLic   = projs.reduce((s,p)=>s+p.licCount,0);
      const acctId    = 'ag_' + acct.replace(/\W+/g,'_');
      projTableRows += `<tr class="proj-acct-hdr" data-acct-id="${acctId}" onclick="anProjGrpToggle(this)" style="cursor:pointer;background:#f0ede6;font-weight:600;">
        <td><span class="ptgl">▶</span>&nbsp;<strong>${acct}</strong></td>
        <td style="color:var(--gray2);">${projs.length} project${projs.length!==1?'s':''}</td>
        <td style="text-align:center;">${acctLic}</td>
        ${MONTHS.map((_,mi)=>{const mv=projs.reduce((s,p)=>s+(p.arr[mi]||0),0);return `<td class="mono" style="font-size:11px;text-align:right;font-weight:600;">${mv>0?fmtK(mv):'-'}</td>`;}).join('')}
        <td class="mono" style="text-align:right;font-weight:700;">${fmt(acctTotal)}</td>
        <td class="mono" style="text-align:right;color:var(--gray);">${fmtK(acctTotal/12)}</td>
      </tr>`;
      projs.sort((a,b)=>b.total-a.total).slice(0,15).forEach((p,i) => {
        projTableRows += `<tr data-parent="${acctId}" style="display:none;background:${i%2===0?'transparent':'#faf8f4'}">
          <td style="padding-left:24px;">${p.proj}</td>
          <td style="color:var(--gray2);">${acct}</td>
          <td style="text-align:center;">${p.licCount}</td>
          ${p.arr.map(v=>`<td class="mono" style="font-size:11px;text-align:right;color:var(--gray);">${v>0?fmtK(v):'-'}</td>`).join('')}
          <td class="mono" style="text-align:right;font-weight:700;">${fmt(p.total)}</td>
          <td class="mono" style="text-align:right;color:var(--gray);">${fmtK(p.total/12)}</td>
        </tr>`;
      });
    });
  }

  const cfoScopeLabel = fAcct.size ? `${anSelectedValues('finAcct').join(', ')} — Read only` : 'All accounts — Read only';
  const cfoLevelLabel = fAcct.size ? 'Account level' : fPlat.size ? 'Platform view' : 'Org level';
  const cfoGrid = `grid-template-columns:1fr 1px 1fr 1px 1fr 1px 1fr`;

  sec.innerHTML = `
    ${anStickyHead(
      anScopeBanner(cfoScopeLabel, 'Finance / CFO', cfoLevelLabel),
      `<div class="an-fbar">
      <span class="fbar-label">Filter by</span>
      ${anMsBuild('finYr', 'All Years', years)}
      ${anMsBuild('finGdl', 'All GDLs', gdlOptions)}
      ${anMsBuild('finOwner', 'All Account Owners', ownerOptions)}
      ${anMsBuild('finAcct', 'All Accounts', acctOptions)}
      ${anMsBuild('finPlat', 'All Platforms', platOptions)}
      <button class="btn" style="font-size:11px;" onclick="anClearFilters()">Clear</button>
      <span class="an-roll">Org level</span>
    </div>`
    )}
    <div class="an-cfo" style="${cfoGrid}">
      <div class="an-cfo-item"><div class="an-cfo-lbl">Annual spend ${yearLabel}</div><div class="an-cfo-val">${totalAnnual>0?fmtK(totalAnnual):'—'}</div><div class="an-cfo-sub">${fAcct.size ? anSelectedValues('finAcct').join(', ') : 'All platforms · all accounts'}</div></div>
      <div class="an-cfo-divider"></div>
      <div class="an-cfo-item"><div class="an-cfo-lbl">Q1 spend ${yearLabel}</div><div class="an-cfo-val">${q1>0?fmtK(q1):'—'}</div><div class="an-cfo-sub">Apr – Jun ${yearLabel}</div></div>
      <div class="an-cfo-divider"></div>
      <div class="an-cfo-item"><div class="an-cfo-lbl">Q4 spend ${yearLabel}</div><div class="an-cfo-val">${q4>0?fmtK(q4):'—'}</div><div class="an-cfo-sub">Jan – Mar ${yearLabel}</div></div>
      <div class="an-cfo-divider"></div>
      <div class="an-cfo-item"><div class="an-cfo-lbl">Q4 vs Q1</div><div class="an-cfo-val" style="color:${trendPct>=0?'var(--lime)':'#ff6b6b'}">${q1>0?(trendPct>=0?'+':'')+trendPct+'%':'—'}</div><div class="an-cfo-sub">Spend trend ${yearLabel}</div></div>
    </div>
    <div class="an-g4">
      <div class="an-kpi">
        <div class="an-kpi-accent" style="background:var(--green)"></div>
        <div class="an-kpi-lbl">Total licenses</div>
        <div class="an-kpi-val" id="an-kpi-total-licenses" style="color:var(--green)">${displayTotalLicenses}</div>
        <div class="an-kpi-sub">${fAcct.size ? anSelectedValues('finAcct').join(', ') : 'All platforms · all accounts'}<div class="an-kpi-sub2" id="an-kpi-total-licenses-sub2">${displayEmployeesAssigned} employees assigned</div></div>
      </div>
      ${anKpiCard('var(--blue)',   'Monthly spend',       fmt(spend),     'var(--blue)',   'Annual: '+fmt(spend*12))}
      ${anKpiCard('var(--red)',    'Recoverable / Mth',    fmt(recover),   recover>0?'var(--red)':'var(--black)',   recover>0?'Idle licenses':'Nothing recoverable')}
      ${anKpiCard('var(--amber)',  'Saving potential / yr', fmt(recover*12), recover>0?'var(--amber)':'var(--black)', recover>0?'If all idle revoked':'On track')}
    </div>
    <div class="an-g2">
      <div class="an-card">
        <div class="an-card-title">Spend by account <span class="an-card-note">Monthly · ${yearLabel}</span></div>
        ${acctCostHtml || '<div style="color:var(--gray2);font-size:12px;">No data</div>'}
      </div>
      <div class="an-card">
        <div class="an-card-title">Spend by platform <span class="an-card-note">Monthly · ${yearLabel}</span></div>
        ${platCostHtml || '<div style="color:var(--gray2);font-size:12px;">No data</div>'}
      </div>
    </div>
    <div class="an-gfull an-card">
      <div class="an-card-title">Month-on-month spend${fAcct.size?' — '+anSelectedValues('finAcct').join(', '):''} ${yearLabel}</div>
      ${anTrendHtml(trendData, 'var(--lime)', anTrendMeta(trendData, financeEmps))}
    </div>
    ${anSec('Project cost split — ' + yearLabel)}
    <div class="an-gfull an-card">
      <div style="overflow-x:auto;max-height:500px;overflow-y:auto;">
        <table class="tbl">
          <thead style="position:sticky;top:0;z-index:1;background:var(--tan2);"><tr><th>Project / Account</th><th>Account</th><th>Licenses</th>${MONTHS.map(m=>`<th style="text-align:right;min-width:60px;">${m}</th>`).join('')}<th style="text-align:right;">Annual Est.</th><th style="text-align:right;">Monthly Avg</th></tr></thead>
          <tbody>${projTableRows}</tbody>
        </table>
      </div>
    </div>`;

  if(!hasAnyFinanceFilter) fetchAndUpdateAnalyticsTotalLicenses();
}

// ─────────── COST ANALYSIS ──────────────────────────────
function renderCost(){
  const emps=empsFor(role);const allL=emps.flatMap(e=>currentLicenses(e));
  const total=allL.reduce((s,l)=>s+l.cost,0),waste=allL.filter(l=>l.st!=='active').reduce((s,l)=>s+l.cost,0);
  const css=document.getElementById('css');if(css)css.innerHTML=scopeBanner('');
  const cm=document.getElementById('cost-metrics');
  if(cm)cm.innerHTML=[{l:'Monthly spend',v:fmt(total),acc:true},{l:'Recoverable',v:fmt(waste),c:'color:var(--red)'},{l:'Annual projection',v:fmt(total*12)},{l:'Saving potential',v:fmt(waste*12),c:'color:var(--green)'}].map(m=>`<div class="met${m.acc?' macc':''}"><div class="mlb">${m.l}</div><div class="mval" style="${m.c||''}">${m.v}</div></div>`).join('');
  const yr=document.getElementById('cost-year')?.value||latestSpendYear();const cv=document.getElementById('cost-view')?.value||'all';
  const yearSpend=spendDataForYear(yr);
  const yearProjects=projectDataForYear(yr);
  let tdata;
  if(cv==='all')tdata=MONTHS.map((_,i)=>Object.values(yearSpend).reduce((s,arr)=>s+arr[i],0));
  else tdata=yearSpend[cv]||Array(12).fill(0);
  trendChart(tdata,document.getElementById('cost-trend-chart'),null);
  const trendTitle=document.getElementById('cost-trend-title');if(trendTitle)trendTitle.textContent=`Spend trend — Jan to Dec ${yr}`;
  const projectTitle=document.getElementById('cost-project-title');if(projectTitle)projectTitle.textContent=`Monthly cost per project — ${yr}`;
  const diff=document.getElementById('cost-trend-diff');
  if(diff&&tdata.length>=2){const last=tdata[tdata.length-1],prev=tdata[tdata.length-2];const pct=Math.round((last-prev)/Math.max(prev,1)*100);diff.innerHTML=`vs prev month: <span style="color:${pct>=0?'var(--red)':'var(--green)'};">${pct>=0?'+':''}${pct}%</span> · <span style="color:${pct>=0?'var(--red)':'var(--green)'};">${fmt(Math.abs(last-prev))}</span>`;}
  const tbl=document.getElementById('monthly-proj-table');
  if(tbl){
    const projs=Object.keys(yearProjects);
    const projLicCounts={};
    emps.forEach(e=>{if(e.proj) projLicCounts[e.proj]=(projLicCounts[e.proj]||0)+currentLicenses(e).length;});
    const header=`<tr><th>Project</th><th>Account</th><th>Licenses</th>${MONTHS.map(m=>`<th style="text-align:right;min-width:60px;">${m}</th>`).join('')}<th style="text-align:right;">Monthly Avg</th><th style="text-align:right;">Annual Est.</th></tr>`;
    const rows=projs.map((p,i)=>{
      const costs=yearProjects[p];
      const total=costs.reduce((s,v)=>s+v,0);
      const avg=total/12;
      const acct=(PROJ_META[p]?.acct||'—');
      const licCount=projLicCounts[p]||0;
      return `<tr style="background:${i%2===0?'transparent':'#faf8f4'}"><td><strong>${p}</strong></td><td>${acct}</td><td style="text-align:center;">${licCount}</td>${costs.map(v=>`<td style="text-align:right;font-size:11px;color:var(--gray);">${fmtK(v)}</td>`).join('')}<td style="text-align:right;font-size:11px;color:var(--gray);">${fmtK(avg)}</td><td style="text-align:right;font-weight:700;">${fmt(total)}</td></tr>`;
    }).join('');
    tbl.innerHTML=`<thead>${header}</thead><tbody>${rows}</tbody>`;
  }
  const pc={};emps.forEach(e=>currentLicenses(e).forEach(l=>{pc[e.proj]=(pc[e.proj]||0)+l.cost;}));const maxP=Math.max(...Object.values(pc),1);const cproj=document.getElementById('cproj');if(cproj)cproj.innerHTML=Object.entries(pc).map(([p,c])=>barHtml(p,fmt(c),c,maxP)).join('');
  const pl={};emps.forEach(e=>currentLicenses(e).forEach(l=>{pl[l.plat]=(pl[l.plat]||0)+l.cost;}));const maxL=Math.max(...Object.values(pl),1);const cplat=document.getElementById('cplat');if(cplat)cplat.innerHTML=Object.entries(pl).map(([p,c])=>barHtml(p,fmt(c),c,maxL)).join('');
}

// ─────────── REPORTS ────────────────────────────────────
function renderReports(){
  const rpts=[{l:'License utilisation report',s:'Active vs inactive by platform and unit',lime:false},{l:'Distribution by unit & account owner',s:'License count matrix',lime:true},{l:'Project-wise cost split — monthly',s:'For finance / accounts receivable',lime:true},{l:'Month-on-month trend report',s:'Jan–Dec spend per platform',lime:true},{l:'Aspire event audit trail',s:'All events received with action taken',lime:false},{l:'SLA compliance report',s:'Revocation turnaround vs SLA',lime:false}];
  const rl=document.getElementById('rlist');if(!rl)return;
    rl.innerHTML=rpts.map(r=>`<div style="display:flex;align-items:center;justify-content:space-between;padding:9px 11px;background:var(--tan);border-radius:7px;"><div><div style="font-size:13px;font-weight:500;">${r.l}</div><div style="font-size:11px;color:var(--gray2);margin-top:1px;">${r.s}</div></div><img src="/static/img/sheets.png" alt="Export" style="cursor:pointer;width:20px;height:20px;opacity:0.8;" onclick="exportReport('${r.l}')" title="${r.lime?'Export for Finance':'Export'}"></div>`).join('<div style="height:6px;"></div>');
}

// ─────────── EXCEL EXPORT ───────────────────────────────
function exportLicenseRegisterToExcel(){
  try{
    if(typeof XLSX==='undefined'){toast('Excel library not loaded. Please refresh and try again.','var(--red)');return;}
    if(!Array.isArray(EMPS)||!EMPS.length){toast('No data to export','var(--red)');return;}
    const emps=empsFor(role);
    const rows=emps.map(e=>{
      const current=currentLicenses(e);
      const activeCurrent=activeCurrentLicenses(e);
      const total=activeCurrent.reduce((s,l)=>s+l.cost,0);
      const employeeStatus=employeeStatusDisplay(e);
      const licenseStatus=licenseStatusDisplay(e);
      const platStr=current.map(l=>l.plat).join('; ');
      return{'Employee ID':displayEmpId(e),'Employee':e.name,'Unit':e.unit,'Platforms':platStr,'Project':e.proj,'Account':e.acct,'Total Cost/mo':total,'License Count':current.length,'Employee Status':employeeStatus.label,'License Status':licenseStatus.label,'Last Used':licenseLastUsed(e)};
    });
    const ws=XLSX.utils.json_to_sheet(rows);
    const wb=XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb,ws,'License Register');
    const fn=`LicenseIQ_Register_${new Date().toISOString().split('T')[0]}.xlsx`;
    XLSX.writeFile(wb,fn);
    toast('License register exported: '+fn);
  }catch(err){
    console.error('Export error:',err);
    toast('Export failed: '+err.message,'var(--red)');
  }
}

function exportReport(reportName){
  try{
    if(typeof XLSX==='undefined'){toast('Excel library not loaded. Please refresh and try again.','var(--red)');return;}
    const emps=empsFor(role);
    let rows=[];
    if(reportName.includes('utilisation')){
      const platData={};
      emps.forEach(e=>currentLicenses(e).forEach(l=>{if(!platData[l.plat])platData[l.plat]={total:0,active:0,inactive:0};platData[l.plat].total++;if(String(l.st||'').toLowerCase()==='active')platData[l.plat].active++;else platData[l.plat].inactive++;}));
      rows=Object.entries(platData).map(([p,d])=>({Platform:p,'Total Licenses':d.total,'Active':d.active,'Inactive':d.inactive,'Utilisation %':Math.round(d.active/Math.max(d.total,1)*100)}));
    }else if(reportName.includes('Distribution')){
      const matrix={};
      emps.forEach(e=>{
        const owner=e.acctOwner||'Unassigned';
        const unit=e.unit||'Unassigned';
        const account=e.acct||'Unassigned';
        const k=owner+'|'+unit+'|'+account;
        if(!matrix[k])matrix[k]={owner,unit,account,count:0};
        matrix[k].count+=e.lics.length;
      });
      rows=Object.values(matrix).map(m=>({
        'Account Owner':m.owner,
        'Unit':m.unit,
        'Account':m.account,
        'License Count':m.count
      }));
    }else if(reportName.includes('Project-wise')){
      const projs={};
      emps.forEach(e=>{if(!projs[e.proj])projs[e.proj]=0;projs[e.proj]+=activeCurrentLicenses(e).reduce((s,l)=>s+l.cost,0);});
      rows=Object.entries(projs).map(([p,c])=>({Project:p,'Monthly Cost':c,'Annual Cost':c*12}));
    }else if(reportName.includes('trend')){
      const yr=document.getElementById('cost-year')?.value||latestSpendYear();
      const yearSpend=spendDataForYear(yr);
      rows=MONTHS.map((m,i)=>({Month:m,Spend:Object.values(yearSpend).reduce((s,arr)=>s+arr[i],0)}));
    }else if(reportName.includes('Aspire event audit')||reportName.includes('audit trail')){
      const allAlerts=[...ALERTS,...(MANUAL_ALERTS||[])];
      rows=allAlerts.map(a=>{
        const emp=EMPS.find(e=>matchesEmployeeRef(e,a.empId));
        return{
          'Employee ID':(emp?displayEmpId(emp):(a.empId||'')),
          'Employee Name':a.empName||(emp&&emp.name)||'',
          'Event Type':(a.type||'').toUpperCase(),
          'Priority':a.pri||'',
          'Reason / Detail':a.reason||'',
          'Additional Info':a.detail||'',
          'Project':emp?emp.proj:'',
          'Account':emp?emp.acct:'',
          'Unit':emp?emp.unit:'',
          'Status':isDismissedAlert(a)?'Dismissed':'Active'
        };
      });
    }else if(reportName.includes('SLA compliance')||reportName.includes('Revocation turnaround')){
      const revokeItems=queue.filter(q=>String(q.type||'').toLowerCase()==='revoke');
      rows=revokeItems.map(q=>{
        const emp=q.emp_id?findEmployeeByRef(q.emp_id):null;
        const empName=(emp&&emp.name&&emp.name!=='Unknown')?emp.name:(q.emp||'');
        return{
          'Employee ID':(emp?displayEmpId(emp):(q.emp_id||'')),
          'Employee Name':empName,
          'Platform':q.plat||'',
          'Project':q.proj||'',
          'Requested By':q.by||'',
          'Request Date':q.date||'',
          'Status':q.status||'',
          'Approval Stage':q.approval_stage||'',
          'Monthly Cost':q.cost||0,
          'SLA Status':q.status==='completed'?'Completed':q.status==='pending'?'Pending':'In Progress'
        };
      });
    }else{
      rows=[{Status:'Report export not yet configured for this report type'}];
    }
    if(!rows.length){toast('No data to export','var(--red)');return;}
    const ws=XLSX.utils.json_to_sheet(rows);
    const wb=XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb,ws,'Report');
    const fn=`LicenseIQ_${reportName.replace(/[^a-z0-9]/gi,'_')}_${new Date().toISOString().split('T')[0]}.xlsx`;
    XLSX.writeFile(wb,fn);
    toast('Report exported: '+fn);
  }catch(err){
    console.error('Report export error:',err);
    toast('Export failed: '+err.message,'var(--red)');
  }
}

// ─────────── STARTUP ────────────────────────────────────
// Start real-time notification checking
function startNotificationPolling(){
  if(notificationCheckInterval)clearInterval(notificationCheckInterval);
  notificationCheckInterval=setInterval(checkForQueueUpdates,30000);// Check every 30 seconds
  checkForQueueUpdates();// Check immediately on start
}

function stopNotificationPolling(){
  if(notificationCheckInterval){
    clearInterval(notificationCheckInterval);
    notificationCheckInterval=null;
  }
  releasePollingLock();
}

function acquirePollingLock(){
  try{
    const now=Date.now();
    const raw=localStorage.getItem(POLL_LOCK_KEY);
    const lock=raw?JSON.parse(raw):null;
    if(lock&&lock.id!==POLL_TAB_ID&&now-lock.ts<POLL_LOCK_TTL_MS){
      hasPollingLock=false;
      return false;
    }
    localStorage.setItem(POLL_LOCK_KEY,JSON.stringify({id:POLL_TAB_ID,ts:now}));
    hasPollingLock=true;
    return true;
  }catch(e){
    // Keep polling functional even if localStorage is unavailable.
    hasPollingLock=true;
    return true;
  }
}

function releasePollingLock(){
  if(!hasPollingLock)return;
  try{
    const raw=localStorage.getItem(POLL_LOCK_KEY);
    const lock=raw?JSON.parse(raw):null;
    if(lock&&lock.id===POLL_TAB_ID)localStorage.removeItem(POLL_LOCK_KEY);
  }catch(e){}
  hasPollingLock=false;
}

async function checkForQueueUpdates(){
  if(!role||role==='finance')return;
  if(document.visibilityState!=='visible')return;
  if(!acquirePollingLock())return;
  try{
    const data=await fetchJson(`${API_BASE}/dashboard/bootstrap`,{},'');
    if(data&&data.queue){
      const newCount=(data.queue||[]).length;
      const oldCount=queue.length;
      if(newCount>oldCount&&oldCount>0){
        const newItems=newCount-oldCount;
        notifyWithPush(`> New Queue Items`,`${newItems} new request${newItems>1?'s':''} waiting for approval`);
      }
      // Check for new approvals
      if(data.approvals){
        const newAppCount=(data.approvals||[]).length;
        const oldAppCount=document.querySelectorAll('[data-approvals-item]')?.length||0;
        if(newAppCount>oldAppCount&&oldAppCount>0){
          notifyWithPush('! New Approval Request','You have a new approval to review');
        }
      }
    }
  }catch(e){
    // Silent fail for polling
  }
}

window.addEventListener('beforeunload',releasePollingLock);

(async function init(){
  const sessionRestored = _restoreSession();
  if(sessionRestored){
    // Request notification permission early
    requestNotificationPermission();
    
    setContentLoading(true);
    const loaded = await loadBackendData();
    setContentLoading(false);
    if(loaded){
      buildNav();setupReqForm();show('analytics');initSidebarState();
      // Start notification polling for eligible users
      if(role&&role!=='finance')startNotificationPolling();
    } else {
      doLogout();
    }
  }
})();
