// Environment traces: a bounded list, a causal tree, and progressively disclosed evidence.
window.traceExplorer = (() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const icon = name => `<svg aria-hidden="true"><use href="/icons.svg#${name}"></use></svg>`;
  const services = ['user','product','order-api','inventory-api','order-worker','inventory-worker'];
  const ms = value => value == null ? '未采集' : Number(value) >= 1000 ? `${(Number(value)/1000).toFixed(2)} s` : `${Number(value).toFixed(2)} ms`;
  const time = ns => ns ? new Date(Number(ns)/1e6).toLocaleString('zh-CN', {hour12:false}) : '未采集';
  const $ = selector => document.querySelector(selector.startsWith('.tx')?'#workspace-traces '+selector:selector);
  let rows = [], payload = null, selected = '', selectedSpan = '', tab = 'overview', treeQuery = '', waterfall = true;
  let searchGeneration = 0, detailGeneration = 0, collapsed = new Set(), opener = null;
  const nodeStates=new Map(), trail=[], pending={};
  let summaryBatch=null;
  const summaryLabels={accepted:'接口已受理，订单最终结果尚未确认',ok:'成功：HTTP 或业务结果确认',rejected:'业务拒绝，请查看状态码和业务代码',error:'技术错误',unknown:'尚无结果证据'};
  function summaryStatus(r){const loading=r.summary_state==='loading',label=loading?'正在读取链路摘要':r.summary_state==='unavailable'?'摘要读取失败，刷新可重试':summaryLabels[r.status]||summaryLabels.unknown;return `<span class="tx-status-dot tx-${esc(r.status||'unknown')}" title="${esc(label)}" aria-label="${esc(label)}">${icon(loading?'hourglass':r.status==='error'?'x':r.status==='ok'?'check':r.status==='rejected'?'warning-circle':r.status==='accepted'?'arrow-right':'minus')}</span>`;}
  const apiLabel=value=>({success:'接口成功',accepted:'已受理',rejected:'已拒绝',error:'接口错误',unknown:'未提供'}[value]||'读取中…');
  const businessLabel=row=>row.business?.business_state||({not_created:'本次未创建订单',list_query:'不适用：列表查询',read_query:'不适用：读取操作'}[row.business_state_reason]||'未采集');
  function updateSummaryRow(row){renderRows();}
  async function hydrateSummaries(generation){
    summaryBatch?.abort();const batch=new AbortController();summaryBatch=batch;const queue=rows.slice();
    await Promise.all(Array.from({length:Math.min(4,queue.length)},async()=>{while(queue.length&&!batch.signal.aborted){const row=queue.shift(),controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000),abort=()=>controller.abort();batch.signal.addEventListener('abort',abort,{once:true});try{const response=await fetch(`/api/observability/traces/${row.trace_id}/summary`,{signal:controller.signal,cache:'no-store'});if(!response.ok)throw new Error('summary unavailable');const summary=await response.json();if(generation!==searchGeneration)return;Object.assign(row,summary,{summary_state:'ready'});}catch{if(batch.signal.aborted||generation!==searchGeneration)return;row.summary_state='unavailable';row.input='摘要暂不可用';row.output='刷新后重试';}finally{clearTimeout(timer);batch.signal.removeEventListener('abort',abort);}updateSummaryRow(row);}}));
  }
  const status = value => `<span class="tx-status tx-${esc(value || 'unknown')}">${value === 'error' ? '错误' : value === 'ok' ? 'Span OK' : value === 'unset' ? 'Span UNSET' : '状态未知'}</span>`;
  function locationState() {
    const url = new URL(location.href);
    for (const key of ['trace','span','trace_tab']) url.searchParams.delete(key);
    if (selected) {url.searchParams.set('trace', selected); if(selectedSpan) url.searchParams.set('span',selectedSpan); url.searchParams.set('trace_tab',tab);}
    history.replaceState(null,'',url);
  }
  async function read(path) {
    const kind=path.startsWith('/lifecycle')?'lifecycle':path.startsWith('?')?'search':'detail';pending[kind]?.abort();
    const controller = new AbortController(), timer = setTimeout(()=>controller.abort(),20000);
    pending[kind]=controller;
    try {
      const response = await fetch('/api/observability/traces'+path,{signal:controller.signal,cache:'no-store'});
      if(!response.ok) throw new Error(response.status===404?'链路尚未入库、已过期或不属于本地环境。':response.status===400?'查询条件无效。':'追踪查询不可用，请检查 Tempo。');
      return await response.json();
    } finally {clearTimeout(timer);if(pending[kind]===controller)delete pending[kind];}
  }
  function mount() {
    $('#workspace-traces').setAttribute('aria-label','Tracing');
    $('#workspace-traces').removeAttribute('aria-labelledby');
    $('#workspace-traces .workspace-heading').remove();
    $('#traces-content').innerHTML = `<section class="tx-workspace" aria-label="分布式追踪">
      <div class="tx-query-area"><form id="trace-lookup" class="tx-search">${icon('magnifying-glass')}<label class="tx-scope"><select id="tx-query-scope" aria-label="名称与服务搜索范围"><option value="root">in root run</option><option value="all">in all spans</option></select></label><input id="tx-query" name="query" role="combobox" aria-autocomplete="list" aria-expanded="false" aria-controls="tx-query-menu" autocomplete="off" spellcheck="false" aria-label="搜索 Tracing" placeholder="Search…" maxlength="512"><button type="submit" class="tx-search-submit" aria-label="执行查询">${icon('arrow-right')}</button><button type="button" id="tx-add-filter" aria-label="添加查询条件">${icon('plus')}</button><div id="tx-query-menu" class="tx-query-menu" role="listbox" aria-label="查询字段与运算符" hidden></div></form><p id="tx-query-error" class="tx-control-error" role="alert" hidden></p></div>
      <div class="tx-toolbar"><button type="button" class="tx-shortcuts" id="tx-filter-toggle" aria-expanded="true">${icon('sliders-horizontal')}Shortcuts ${icon('sidebar-simple')}</button><div class="tx-time-control"><button type="button" id="tx-time-button" class="button button-quiet" aria-expanded="false" aria-haspopup="menu">${icon('hourglass')}<span id="tx-time-label">Last 7 days</span></button><div id="tx-time-menu" class="tx-time-menu" role="menu" aria-label="选择时间范围" hidden></div></div><span class="tx-segment"><span>Traces</span></span><div class="tx-toolbar-end"><button id="tx-reset" type="button" class="tx-text-button">Reset</button><button id="tx-save-view" type="button" class="button tx-save-view">Save View</button><div class="tx-view-control"><button id="tx-views-button" type="button" class="button button-quiet" aria-expanded="false">${icon('bookmark-simple')}Views</button><div id="tx-views-menu" class="tx-small-menu" hidden></div></div><label class="tx-sort-control"><select id="tx-sort" aria-label="记录排序"><option value="time">最新优先</option><option value="duration">耗时最长</option></select></label><div class="tx-columns-control"><button id="tx-columns-button" class="button button-quiet" type="button" aria-label="配置表格列" aria-expanded="false">${icon('columns')}</button><div id="tx-columns-menu" class="tx-small-menu" hidden>${[['service','服务'],['api','接口结果'],['business','业务状态'],['identity','业务标识'],['input','Input'],['output','Output'],['error','Error'],['time','开始时间'],['duration','耗时'],['id','Trace ID']].map(([key,label])=>`<label><input type="checkbox" data-column="${key}" checked>${label}</label>`).join('')}</div></div><span id="tx-count">Stats · 0 traces</span><button id="tx-refresh" type="button" class="button button-quiet" aria-label="刷新链路">${icon('arrow-clockwise')}</button></div></div>
      <div class="tx-layout"><aside class="tx-facets" aria-label="链路筛选"><form id="trace-search">
        <h3>Status</h3><label class="tx-checkbox"><input name="errors" type="checkbox">error <small>错误 span</small></label>
        <h3>Service</h3>${services.map(s=>`<label class="tx-checkbox"><input name="services" type="checkbox" value="${s}">${s}</label>`).join('')}
        <h3>Run Name</h3><div id="tx-name-facets"><p class="tx-facet-note">查询后显示入口名称。</p></div>
        <h3>Latency</h3><input name="min_duration_ms" type="hidden" value="0">${[100,500,1000,5000].map(ms=>`<label class="tx-checkbox"><input type="checkbox" data-duration="${ms}"><span>至少 ${ms} ms</span></label>`).join('')}
        <input name="order_id" type="hidden"><input name="event_id" type="hidden">
        <p>Tempo · 本地环境<br>仅展示采样并导出的链路。</p></form></aside>
        <section class="tx-records" aria-label="Tracing 记录"><input id="tx-list-query" type="hidden" value="">
        <div class="tx-table-scroll"><table class="tx-table"><thead><tr><th class="tx-status-column" aria-label="状态">${icon('check')}</th><th>Name</th><th data-col="service">Service</th><th data-col="api">接口结果</th><th data-col="business">业务状态</th><th data-col="identity">业务标识</th><th data-col="input">Input</th><th data-col="output">Output</th><th data-col="error">Error</th><th data-col="time">Start Time</th><th data-col="duration">Latency</th><th data-col="id">Trace ID</th></tr></thead><tbody id="trace-results"></tbody></table></div><p id="trace-message" role="status"></p></section></div>
      <section id="trace-detail" class="tx-peek" aria-label="执行链路详情" hidden></section></section>`;
    $('.tx-query-area').insertAdjacentHTML('beforeend','<div id="tx-active-filters" class="tx-active-filters" aria-label="已应用筛选"></div>');
    restoreWorkspace();
    $('#trace-search').addEventListener('submit',e=>{e.preventDefault();search();});
    window.traceControls.mount(search,open);
    $('#tx-refresh').onclick = search;
    $('#tx-reset').onclick = ()=>{window.traceWorkspace.reset();applyFilters([]);window.traceControls.reset();$('#tx-list-query').value='';$('#tx-sort').value='time';$('#tx-sort').dispatchEvent(new Event('change'));search();};
    $('#tx-filter-toggle').onclick = e=>{const button=e.currentTarget,hidden=button.getAttribute('aria-expanded')==='true';button.setAttribute('aria-expanded',String(!hidden));$('.tx-facets').inert=hidden;$('.tx-facets').setAttribute('aria-hidden',String(hidden));$('.tx-layout').classList.toggle('tx-no-facets',hidden);};
    $('#tx-list-query').oninput = renderRows;
    $('#tx-sort').onchange = renderRows;
    $('#trace-search').addEventListener('change',event=>{if(event.target.dataset.duration){formDuration(event.target);}search();});
    mountViews();
    $('#trace-results').addEventListener('click',e=>{if(e.target.closest('[data-retry-search]')){search();return;}if(e.target.closest('[data-reset-query]')){$('#tx-reset').click();return;}const row=e.target.closest('[data-trace]');if(row){opener=row.querySelector('button');trail.length=0;open(row.dataset.trace);}});
    $('#tx-active-filters').onclick=e=>{const button=e.target.closest('[data-clear-filter]');if(!button)return;const inputs=[...$('#trace-search').querySelectorAll('input')].filter(input=>input.name===button.dataset.clearFilter);for(const input of inputs){if(input.type==='checkbox'&&(!button.dataset.value||input.value===button.dataset.value))input.checked=false;else if(input.type!=='checkbox')input.value=input.name==='min_duration_ms'?'0':'';}search();};
    $('#trace-detail').addEventListener('click',handleDetail);
    $('#trace-detail').addEventListener('submit',e=>{if(e.target.id==='tx-lifecycle-form'){e.preventDefault();loadLifecycle(e.target);}});
    $('#trace-detail').addEventListener('input',e=>{if(e.target.id==='tx-tree-query'){treeQuery=e.target.value;renderTree();}});
    document.addEventListener('keydown',e=>{if(e.key==='Escape' && document.body.classList.contains('tx-active') && !$('#trace-detail').hidden && !e.target.closest('.signal-select')){e.stopImmediatePropagation();close();}});
    window.traceWorkspace.mount();
    window.workspaceControls?.enhance?.($('#traces-content'));
  }
  function formDuration(input){const form=$('#trace-search');form.elements.min_duration_ms.value=input.checked?input.dataset.duration:'0';}
  async function search() {
    window.traceWorkspace?.refresh();
    if(window.traceWorkspace?.isOrders())return;
    const form=$('#trace-search');
    if(!form || !form.reportValidity())return;
    const query=window.traceControls.params();if(!query)return;const generation=++searchGeneration;summaryBatch?.abort();for(const [key,value] of new FormData(form))query.append(key,value);query.set('errors',form.elements.errors.checked?'true':'false');
    window.traceControls.persist();
    persistWorkspace();renderFilterChips();
    $('.tx-records').setAttribute('aria-busy','true');
    rows=[];window.traceWorkspace?.update(rows);
    window.traceWorkspace.begin();$('#trace-message').textContent='正在查询已采样链路…';
    $('#trace-results').innerHTML=Array.from({length:8},()=>'<tr class="tx-skeleton"><td colspan="12"><span></span></td></tr>').join('');
    try {
      const data=await read('?'+query);if(generation!==searchGeneration)return;
      rows=data.traces.map(row=>({...row,summary_state:'loading',input:'读取中…',output:'读取中…'}));renderRows();renderNameFacets();
      $('#trace-message').textContent=`${window.traceControls.label()}${data.retention_seconds?' · 当前保留 '+(data.retention_seconds/3600).toFixed(0)+'h':''} · 最多 ${data.limit} 条${data.truncated?'，已达上限，请缩小范围':''} · ${data.sampling_note} · ${new Date(data.sampled_at*1000).toLocaleTimeString('zh-CN')}`;
      void hydrateSummaries(generation);
    }catch(error){if(generation!==searchGeneration)return;rows=[];window.traceWorkspace.fail(error.name==='AbortError'?'查询超时，请缩小范围后重试。':error.message);$('#tx-count').textContent='查询失败';$('#trace-message').textContent=error.name==='AbortError'?'查询超时，请缩小范围后重试。':error.message;$('#trace-results').innerHTML='<tr><td colspan="12" class="tx-empty">查询失败，请检查查询语法或采集组件。<p><button class="button button-quiet" data-retry-search>重试查询</button></p></td></tr>';}
    finally{if(generation===searchGeneration)$('.tx-records').setAttribute('aria-busy','false');}
  }
  function renderRows() {
    const query=$('#tx-list-query').value.toLowerCase();
    const kind=window.traceWorkspace?.executionFilter()||'all';
    const visible=rows.filter(r=>[r.name,r.service,r.trace_id].join(' ').toLowerCase().includes(query)&&(kind==='all'||r.execution_type===kind)).sort((a,b)=>$('#tx-sort').value==='duration'?Number(b.duration_ms)-Number(a.duration_ms):Number(b.start_time_ns)-Number(a.start_time_ns));
    $('#tx-count').textContent=`Stats · ${visible.length} traces`;
    $('#trace-results').innerHTML=visible.length?visible.map(r=>`<tr data-trace="${esc(r.trace_id)}" class="${selected===r.trace_id?'is-selected':''}"><td class="tx-status-column">${summaryStatus(r)}</td><td><button type="button" class="tx-record-name" aria-label="查看 ${esc(r.name || r.trace_id)}">${esc(r.name || '未命名入口')}</button></td><td data-col="service">${esc(r.service || '未采集')}</td><td data-col="api">${esc(apiLabel(r.api_result))}</td><td data-col="business">${esc(businessLabel(r))}</td><td data-col="identity">${r.business?.order_id?window.investigationNavigation.action('Order '+r.business.order_id,{page:'traces',order_id:r.business.order_id}):esc(r.business?.product_id?'Product '+r.business.product_id:'未采集')}</td><td data-col="input" class="tx-preview">${esc(r.input||'未提供')}</td><td data-col="output" class="tx-preview">${esc(r.output||'未提供')}</td><td data-col="error" class="tx-error-text">${esc(r.error||'')}</td><td data-col="time" class="tx-number">${esc(time(r.start_time_ns))}</td><td data-col="duration"><span class="tx-latency ${Number(r.duration_ms)>1000?'tx-slow':''}">${icon('timer')}${ms(r.duration_ms)}</span></td><td data-col="id"><code>${esc(r.trace_id)}</code></td></tr>`).join(''):'<tr><td colspan="12" class="tx-empty"><strong>没有匹配的已采样链路</strong><p>调整时间、服务或业务关联条件。没有结果不代表没有请求。</p><button class="button button-quiet" data-reset-query>重置查询范围</button></td></tr>';
    applyColumns();
    for(const row of document.querySelectorAll('#trace-results [data-trace]')){const record=rows.find(r=>r.trace_id===row.dataset.trace),name=row.querySelector('.tx-record-name');name.insertAdjacentHTML('afterend',`<small class="tx-record-context">${esc(({api:'API 请求',message:'消息处理',task:'后台任务',unknown:'类型未确定'})[record.execution_type]||'类型读取中')} · ${record.span_count??'…'} spans</small>`);const cell=row.querySelector('[data-col=service]');cell.textContent=(record.services||[record.service]).join(', ');cell.title='涉及的服务；入口服务：'+record.service;}
    window.traceWorkspace?.update(rows);
  }
  function renderNameFacets(){
    const checked=[...$('#tx-name-facets').querySelectorAll('input:checked')].map(input=>input.value);
    const names=[...new Set([...checked,...rows.map(r=>r.name).filter(Boolean)])].slice(0,20);
    $('#tx-name-facets').innerHTML=names.length?names.map(name=>`<label class="tx-checkbox"><input type="checkbox" name="names" value="${esc(name)}" ${checked.includes(name)?'checked':''} ${checked.length>=8&&!checked.includes(name)?'disabled':''}><span title="${esc(name)}">${esc(name)}</span></label>`).join(''):'<p class="tx-facet-note">此范围暂无入口名称。</p>';
    window.workspaceControls.enhance($('#tx-name-facets'));
  }
  function applyColumns(){for(const control of document.querySelectorAll('[data-column]'))document.querySelectorAll(`[data-col="${control.dataset.column}"]`).forEach(cell=>cell.hidden=!control.checked);persistWorkspace();}
  function persistWorkspace(){const url=new URL(location.href);url.searchParams.set('trace_filters',JSON.stringify([...new FormData($('#trace-search'))]));url.searchParams.set('trace_sort',$('#tx-sort').value);url.searchParams.set('trace_columns',[...document.querySelectorAll('[data-column]:checked')].map(c=>c.dataset.column).join(','));history.replaceState(null,'',url);}
  function restoreWorkspace(){const params=new URLSearchParams(location.search);try{applyFilters(JSON.parse(params.get('trace_filters')||'[]'));}catch{/* Invalid shared filter state leaves the default query usable. */}$('#tx-sort').value=params.get('trace_sort')==='duration'?'duration':'time';if(params.has('trace_columns')){const columns=params.get('trace_columns').split(',');document.querySelectorAll('[data-column]').forEach(c=>c.checked=columns.includes(c.dataset.column));}}
  function applyFilters(filters){const form=$('#trace-search');form.reset();form.querySelectorAll('input[type=checkbox]').forEach(i=>i.checked=false);$('#tx-name-facets').innerHTML='';if(!Array.isArray(filters))return;let nameCount=0;for(const item of filters.slice(0,20)){if(!Array.isArray(item)||item.length!==2)continue;const [name,value]=item;if(typeof value!=='string')continue;if(name==='errors')form.elements.errors.checked=true;else if(name==='services'){const input=[...form.querySelectorAll('[name=services]')].find(i=>i.value===value);if(input)input.checked=true;}else if(name==='names'&&value&&value.length<=160&&nameCount++<8){$('#tx-name-facets').insertAdjacentHTML('beforeend',`<label class="tx-checkbox"><input type="checkbox" name="names" value="${esc(value)}" checked><span>${esc(value)}</span></label>`);}else if(['min_duration_ms','order_id','event_id'].includes(name))form.elements[name].value=value;}}
  function renderFilterChips(){document.querySelectorAll('[data-duration]').forEach(input=>input.checked=input.dataset.duration===$('#trace-search').elements.min_duration_ms.value);const labels={services:'服务',names:'入口',errors:'错误 span',min_duration_ms:'最短耗时',order_id:'订单',event_id:'事件'};$('#tx-active-filters').innerHTML=[...new FormData($('#trace-search'))].filter(([name,value])=>value&&(name!=='min_duration_ms'||value!=='0')).map(([name,value])=>`<button type="button" data-clear-filter="${esc(name)}" data-value="${esc(value)}" aria-label="移除 ${esc(labels[name]||name)} 筛选">${esc(labels[name]||name)}${name==='errors'?'':': '+esc(value)}${icon('x')}</button>`).join('');}
  function viewStore(value){if(value!==undefined){localStorage.setItem('seckill.trace.views',JSON.stringify(value));return value;}try{const entries=JSON.parse(localStorage.getItem('seckill.trace.views')||'[]');return Array.isArray(entries)?entries.filter(v=>typeof v?.name==='string'&&v.state).slice(0,12):[];}catch{return [];}}
  function viewSnapshot(){return {execution:window.traceWorkspace.executionFilter(),query:window.traceControls.snapshot(),filters:[...new FormData($('#trace-search'))],columns:[...document.querySelectorAll('[data-column]:checked')].map(c=>c.dataset.column),sort:$('#tx-sort').value};}
  function mountViews(){
    const viewMenu=$('#tx-views-menu'),columnsMenu=$('#tx-columns-menu');
    function showViews(){const entries=viewStore();viewMenu.innerHTML=`<h4>Saved views <small>此浏览器</small></h4>${entries.length?entries.map((v,i)=>`<div class="tx-saved-view"><button type="button" data-load-view="${i}">${esc(v.name)}</button><button type="button" data-delete-view="${i}" aria-label="删除视图 ${esc(v.name)}">${icon('x')}</button></div>`).join(''):'<p>暂无保存的查询视图。</p>'}`;}
    $('#tx-save-view').onclick=()=>{viewMenu.hidden=false;$('#tx-views-button').setAttribute('aria-expanded','true');viewMenu.innerHTML='<form id="tx-save-view-form"><label>视图名称<input name="name" required maxlength="40" placeholder="例如：订单错误链路"></label><button type="submit" class="button button-primary">保存当前查询</button><p>时间、筛选、排序和显示列保存到此浏览器。</p></form>';viewMenu.querySelector('input').focus();viewMenu.querySelector('form').onsubmit=e=>{e.preventDefault();if(!e.target.checkValidity())return;const name=e.target.elements.name.value.trim();if(!name)return;const entries=viewStore().filter(v=>v.name!==name);entries.unshift({name,state:viewSnapshot()});try{viewStore(entries.slice(0,12));showViews();}catch{const message=e.target.querySelector("p");message.textContent="无法保存视图，请检查浏览器存储权限。";message.setAttribute("role","alert");}};};
    $('#tx-views-button').onclick=()=>{viewMenu.hidden=!viewMenu.hidden;$('#tx-views-button').setAttribute('aria-expanded',String(!viewMenu.hidden));if(!viewMenu.hidden)showViews();};
    $('#tx-columns-button').onclick=()=>{columnsMenu.hidden=!columnsMenu.hidden;$('#tx-columns-button').setAttribute('aria-expanded',String(!columnsMenu.hidden));};
    columnsMenu.onchange=applyColumns;
    viewMenu.onclick=e=>{const b=e.target.closest('button');if(!b)return;const entries=viewStore();if(b.dataset.deleteView!==undefined){entries.splice(Number(b.dataset.deleteView),1);try{viewStore(entries);showViews();}catch{viewMenu.insertAdjacentHTML('beforeend','<p role="alert">无法删除视图，请检查浏览器存储权限。</p>');}}if(b.dataset.loadView!==undefined){const state=entries[Number(b.dataset.loadView)]?.state;if(!state)return;applyFilters(state.filters);window.traceControls.restore(state.query||{});
      window.traceWorkspace.setExecution(state.execution);if(Array.isArray(state.columns))document.querySelectorAll('[data-column]').forEach(c=>c.checked=state.columns.includes(c.dataset.column));$('#tx-sort').value=['time','duration'].includes(state.sort)?state.sort:'time';$('#tx-sort').dispatchEvent(new Event('change'));window.workspaceControls.enhance($('#trace-search'));applyColumns();viewMenu.hidden=true;$('#tx-views-button').setAttribute('aria-expanded','false');search();}};
    document.addEventListener('pointerdown',e=>{if(!e.target.closest('.tx-view-control')&&!e.target.closest('#tx-save-view')){viewMenu.hidden=true;$('#tx-views-button').setAttribute('aria-expanded','false');}if(!e.target.closest('.tx-columns-control')){columnsMenu.hidden=true;$('#tx-columns-button').setAttribute('aria-expanded','false');}});
  }
  function rememberNode(){if(payload&&selected)nodeStates.set(selected,{span:selectedSpan,tab,collapsed:[...collapsed],query:treeQuery,waterfall,scroll:$('#tx-tree')?.scrollTop||0});if(nodeStates.size>30)nodeStates.delete(nodeStates.keys().next().value);}
  function close() {rememberNode();const id=selected;++detailGeneration;pending.detail?.abort();pending.lifecycle?.abort();selected='';selectedSpan='';payload=null;$('#trace-detail').hidden=true;$('.tx-workspace').classList.remove('tx-peeking');locationState();renderRows();document.querySelector(`[data-trace="${id}"] .tx-record-name`)?.focus({preventScroll:true});}
  async function open(id, preferredSpan='', preferredTab='overview') {
    if(!/^[0-9a-f]{32}$/.test(id))return;
    rememberNode();const saved=nodeStates.get(id);preferredSpan=preferredSpan||saved?.span||'';preferredTab=saved?.tab||preferredTab;
    const generation=++detailGeneration;selected=id;selectedSpan='';payload=null;collapsed=new Set();treeQuery='';tab=['overview','input','output','attributes','links','analysis','events','runtime','lifecycle'].includes(preferredTab)?preferredTab:'overview';
    const target=$('#trace-detail');target.hidden=false;$('.tx-workspace').classList.add('tx-peeking');renderRows();locationState();
    target.innerHTML=`<header class="tx-peek-header"><strong>Trace 详情</strong><button type="button" class="icon-button" data-close aria-label="关闭详情">${icon('x')}</button></header><div class="tx-empty" role="status">正在读取执行链路…</div>`;
    target.querySelector('[data-close]').focus();
    try {
      const data=await read('/'+id);if(generation!==detailGeneration)return;
      if(!data.spans?.length)throw new Error('该链路没有可展示的 span。');
      payload=data;selectedSpan=data.spans.some(s=>s.span_id===preferredSpan)?preferredSpan:data.spans[0].span_id;
      const record=rows.find(r=>r.trace_id===id);
      if(record && data.summary){Object.assign(record,data.summary,{summary_state:'ready'});updateSummaryRow(record);}else if(record){record.status=data.spans.some(s=>s.status==='error')?'error':'ok';const root=data.spans.find(s=>!data.spans.some(p=>p.span_id===s.parent_span_id))||data.spans[0],a=root.attributes||{};record.input=[a['http.request.method']||a['http.method'],a['http.route']||a['messaging.destination.name']||a['db.operation']].filter(Boolean).join(' ');record.output=String(a['http.response.status_code']||a['http.status_code']||a['seckill.outcome']||'未提供');record.error=data.spans.filter(s=>s.status==='error').map(s=>s.attributes?.['seckill.error_code']||s.name).join(' · ');renderRows();}
      // Expand the root and its direct children first; deeper branches disclose on demand.
      const byId=new Map(data.spans.map(s=>[s.span_id,s]));
      data.spans.forEach(s=>{if(byId.has(s.parent_span_id) && byId.has(byId.get(s.parent_span_id).parent_span_id))collapsed.add(s.span_id);});
      let ancestor=byId.get(selectedSpan)?.parent_span_id;
      const seen=new Set();
      while(byId.has(ancestor)&&!seen.has(ancestor)){seen.add(ancestor);collapsed.delete(ancestor);ancestor=byId.get(ancestor).parent_span_id;}
      if(saved){collapsed=new Set(saved.collapsed);treeQuery=saved.query;waterfall=saved.waterfall;}
      renderDetail();if(saved)$('#tx-tree').scrollTop=saved.scroll;locationState();
    }catch(error){if(generation!==detailGeneration)return;target.innerHTML=`<header class="tx-peek-header"><strong>Trace 详情</strong><button type="button" class="icon-button" data-close aria-label="关闭详情">${icon('x')}</button></header><div class="tx-empty" role="alert">${esc(error.message)}<p><button class="button button-quiet" data-retry>重试</button></p></div>`;}
  }
  function bounds() {const start=Math.min(...payload.spans.map(s=>Number(s.start_time_ns))),end=Math.max(...payload.spans.map(s=>Number(s.start_time_ns)+s.duration_ms*1e6));return {start,total:Math.max(.001,(end-start)/1e6)};}
  function renderDetail() {
    const {start,total}=bounds();
    const ids=[...document.querySelectorAll('#trace-results [data-trace]')].map(r=>r.dataset.trace),index=ids.indexOf(selected);
    $('#trace-detail').innerHTML=`<header class="tx-peek-header"><div>${trail.length?`<button class="button button-quiet" data-back-trace aria-label="返回上一条关联链路">${icon('arrow-left')}</button>`:''}<strong>Trace</strong><button class="tx-copy" data-copy="${esc(selected)}" aria-label="复制 Trace ID"><code>${esc(selected)}</code>${icon('copy')}</button></div><div><button class="button button-quiet tx-request-step" data-step="-1" aria-label="上一个请求" ${index<=0?'disabled':''}>${icon('arrow-up')}</button><button class="button button-quiet tx-request-step" data-step="1" aria-label="下一个请求" ${index<0||index>=ids.length-1?'disabled':''}>${icon('arrow-down')}</button><button class="button button-quiet" data-logs>关联日志</button><button class="button button-quiet" data-expand-peek aria-label="切换详情宽度">${icon('arrows-out')}</button><button class="icon-button" data-close aria-label="关闭详情">${icon('x')}</button></div></header>
      <div class="tx-detail-grid"><aside class="tx-chain" aria-label="执行链路树"><div class="tx-chain-heading"><strong>执行链路</strong><button class="button button-quiet" data-waterfall aria-pressed="${waterfall}">Waterfall</button></div><label class="tx-tree-search">${icon('magnifying-glass')}<input id="tx-tree-query" placeholder="筛选节点…" aria-label="筛选链路节点"></label><div class="tx-summary"><span>${payload.spans.length} spans</span><span>${ms(total)}</span><span>${new Set(payload.spans.map(s=>s.service)).size} 服务</span><span class="tx-error-text">${payload.spans.filter(s=>s.status==='error').length} 错误</span></div><div id="tx-tree"></div><p class="tx-chain-note">${esc(time(start))}<br>并行 span 耗时不可直接相加。缺失的父节点会作为独立分支展示。</p></aside><article class="tx-node-detail" aria-label="所选节点详情"><div id="tx-node-header"></div><nav class="tx-tabs" aria-label="节点详情视角">${[['overview','概览'],['input','Input'],['output','Output'],['attributes','Attributes'],['links','关联链路'],['analysis','耗时'],['events','事件'],['runtime','运行环境'],['lifecycle','生命周期']].map(([key,label])=>`<button type="button" data-tab="${key}" aria-pressed="${tab===key}">${label}</button>`).join('')}</nav><div id="tx-node-body"></div><p id="tx-copy-message" role="status"></p></article></div>`;
    if(window.traceOrders.hasSelection())$('#trace-detail .tx-peek-header>div:last-child').insertAdjacentHTML('afterbegin',`<button class="button button-quiet" data-return-order>${icon('arrow-left')}返回订单</button>`);
    const order=payload.summary?.business?.order_id;if(order)$('#trace-detail .tx-peek-header>div:last-child').insertAdjacentHTML('afterbegin',`<button class="button button-quiet" data-order-journey="${esc(order)}">${icon('tree-structure')}订单流程</button>`);
    $('#tx-tree-query').value=treeQuery;renderTree();renderNode();
  }
  function treeModel() {
    const byId=new Map(payload.spans.map(s=>[s.span_id,s])),children=new Map(),roots=[];
    // Detect corrupt parent cycles so no node silently disappears from the tree.
    for(const s of payload.spans){let parent=s.parent_span_id,seen=new Set([s.span_id]),cycle=false;while(byId.has(parent)){if(seen.has(parent)){cycle=true;break;}seen.add(parent);parent=byId.get(parent).parent_span_id;}
      if(!byId.has(s.parent_span_id)||cycle)roots.push(s);else {if(!children.has(s.parent_span_id))children.set(s.parent_span_id,[]);children.get(s.parent_span_id).push(s);}}
    return {byId,children,roots};
  }
  function renderTree() {
    if(!payload)return;
    if(waterfall){
      const model=window.orderInvestigation.build({executions:[{trace_id:selected,name:payload.summary?.name||payload.spans[0]?.name||'Trace',start_time_ns:payload.spans[0]?.start_time_ns,duration_ms:bounds().total,spans:payload.spans}]}).filter(n=>n.type==='trace');
      const folds=new Set([...collapsed].map(id=>'span:'+selected+':'+id));
      const root=$('#tx-tree');root.innerHTML=window.orderInvestigation.tree(model,'span:'+selected+':'+selectedSpan,folds,treeQuery,'waterfall');
      root.querySelectorAll('[data-order-node]').forEach(button=>{if(button.dataset.orderNode.startsWith('span:'))button.dataset.span=button.dataset.orderNode.split(':')[2];else button.dataset.rootSpan=payload.spans[0].span_id;delete button.dataset.orderNode;});
      root.querySelectorAll('[data-order-fold]').forEach(button=>{if(button.dataset.orderFold.startsWith('trace:'))button.remove();else{button.dataset.fold=button.dataset.orderFold.split(':')[2];delete button.dataset.orderFold;}});
      root.querySelectorAll('[data-order-branch]').forEach(branch=>{if(branch.dataset.orderBranch.startsWith('span:'))branch.dataset.parent=branch.dataset.orderBranch.split(':')[2];delete branch.dataset.orderBranch;});window.workspaceControls.enhance(root);return;
    }
    const {byId,children,roots}=treeModel(),{start,total}=bounds(),query=treeQuery.trim().toLowerCase(),keep=new Set();
    if(query)for(const s of payload.spans){if(![s.name,s.service,s.span_id].join(' ').toLowerCase().includes(query))continue;keep.add(s.span_id);let parent=s.parent_span_id;while(byId.has(parent)&&!keep.has(parent)){keep.add(parent);parent=byId.get(parent).parent_span_id;}}
    const rendered=new Set();
    function node(s,depth){if(rendered.has(s.span_id)||(query&&!keep.has(s.span_id)))return '';rendered.add(s.span_id);const kids=children.get(s.span_id)||[],folded=!query&&collapsed.has(s.span_id),offset=(Number(s.start_time_ns)-start)/1e6;
      return `<div class="tx-tree-item"><div class="tx-tree-node" style="--depth:${Math.min(depth,20)}"><div class="tx-tree-row ${s.span_id===selectedSpan?'is-selected':''}">${kids.length?`<button class="tx-fold" data-fold="${esc(s.span_id)}" aria-expanded="${!folded}" aria-label="${folded?'展开':'折叠'} ${esc(s.name)}">${icon('caret-right')}</button>`:'<span class="tx-fold-space"></span>'}<button class="tx-node-select" data-span="${esc(s.span_id)}"><span class="tx-kind tx-kind-${s.attributes?.['db.system']?'db':s.attributes?.['messaging.system']?'message':'service'}">${icon(s.attributes?.['db.system']?'database':s.attributes?.['messaging.system']?'queue':'tree-structure')}</span><span class="tx-node-label"><strong>${esc(s.name)}</strong><small>${esc(s.service)} · ${ms(s.duration_ms)}${s.self_duration_ms==null?'':' / 自身 '+ms(s.self_duration_ms)}${s.status==='error'?' · 错误':''}</small></span></button></div><div class="tx-timeline" ${waterfall?'':'hidden'} aria-label="开始偏移 ${ms(offset)}，耗时 ${ms(s.duration_ms)}"><span class="${s.status==='error'?'tx-bar-error':''}" style="left:${Math.max(0,offset/total*100)}%;width:${Math.max(.6,Math.min(100,s.duration_ms/total*100))}%"></span></div></div>${kids.length?`<div class="tx-tree-branch ${folded?'is-collapsed':''}" data-parent="${esc(s.span_id)}" aria-hidden="${folded}" ${folded?'inert':''}><div class="tx-branch-content">${kids.map(child=>node(child,depth+1)).join('')}</div></div>`:''}</div>`;
    }
    $('#tx-tree').innerHTML=roots.map(s=>node(s,0)).join('')||'<p class="tx-empty">没有匹配节点。</p>';
  }
  function updateTreeExpansion(){for(const branch of document.querySelectorAll('#trace-detail .tx-tree-branch')){const folded=!treeQuery.trim()&&collapsed.has(branch.dataset.parent);branch.classList.toggle('is-collapsed',folded);branch.inert=folded;branch.setAttribute('aria-hidden',String(folded));const button=document.querySelector(`#trace-detail [data-fold="${branch.dataset.parent}"]`);button?.setAttribute('aria-expanded',String(!folded));if(button)button.setAttribute('aria-label',button.getAttribute('aria-label').replace(/^(展开|折叠)/,folded?'展开':'折叠'));}}
  function fields(object) {const entries=Object.entries(object);return entries.length?`<dl class="tx-fields">${entries.map(([k,v])=>`<div><dt>${esc(k)}</dt><dd>${esc(typeof v==='object'?JSON.stringify(v):v)}</dd></div>`).join('')}</dl>`:'<p class="tx-no-data">没有采集这些字段。</p>';}
  function section(title,content,expanded=true){return `<details class="tx-section" data-expanded="${expanded}" ${expanded?'open':''}><summary aria-expanded="${expanded}"><span class="disclosure-icon">${icon('caret-right')}</span>${esc(title)}</summary><div class="tx-disclosure-body ${expanded?'':'is-collapsed'}"><div class="tx-disclosure-content">${content}</div></div></details>`;}
  const disclosureTimers=new WeakMap();
  function toggleSection(details){const expanding=details.dataset.expanded!=='true',body=details.querySelector('.tx-disclosure-body');clearTimeout(disclosureTimers.get(details));details.dataset.expanded=String(expanding);details.querySelector('summary').setAttribute('aria-expanded',String(expanding));body.inert=!expanding;
    if(expanding){details.open=true;body.classList.add('is-collapsed');void body.offsetWidth;body.classList.remove('is-collapsed');}
    else {body.classList.add('is-collapsed');const delay=matchMedia('(prefers-reduced-motion: reduce)').matches?0:190;disclosureTimers.set(details,setTimeout(()=>{if(details.dataset.expanded==='false')details.open=false;},delay));}}
  function renderNode() {
    const s=payload.spans.find(s=>s.span_id===selectedSpan),a=s.attributes||{}, {start}=bounds();
    const input=Object.fromEntries(Object.entries(a).filter(([k])=>/^(http\.(method|request.method|route)|db\.|messaging\.|server\.|net\.|seckill\.(product_id|order_id|campaign_id|quantity|request_id|page|page_size)$)/.test(k)));
    const output=Object.fromEntries(Object.entries(a).filter(([k])=>/^(http\.(status_code|response.status_code)|seckill\.)/.test(k)));
    $('#tx-node-header').innerHTML=`<div class="tx-node-title"><span class="tx-kind">${icon('tree-structure')}</span><h2>${esc(s.name)}</h2>${status(s.status)}</div><div class="tx-node-meta"><span>${esc(s.service)}</span><span>${esc(s.kind.replace('SPAN_KIND_',''))}</span><span class="tx-latency">${ms(s.duration_ms)}</span></div>`;
    $('#tx-node-header').insertAdjacentHTML('beforeend',window.investigationNavigation.context({order_id:a['seckill.order_id']||payload.summary?.business?.order_id,event_id:a['messaging.message.id'],causation_id:a['seckill.causation_id'],request_id:a['seckill.request_id'],service:s.service,at:Number(s.start_time_ns)/1e9}));
    const context=fields({'Trace ID':selected,'Span ID':s.span_id,'Parent span ID':s.parent_span_id||'根节点','开始时间':time(s.start_time_ns),'相对开始':ms((Number(s.start_time_ns)-start)/1e6),'耗时':ms(s.duration_ms),'自身耗时':ms(s.self_duration_ms),'接口结果':payload.summary?.api_result||'unknown','业务状态':window.tracePanels.stateLabel(payload,s)});
    const note='<p class="tx-no-data">当前采集提供协议、依赖与业务字段。请求正文和响应正文未采集。</p>';
    const links=(s.links||[]).length?s.links.map(l=>`<div class="tx-related"><span>${esc(l.reason)} · Span <code>${esc(l.span_id)}</code></span><button class="trace-link" data-related="${esc(l.trace_id)}" data-related-span="${esc(l.span_id)}">${esc(l.trace_id)}</button><button data-copy="${esc(l.trace_id)}" aria-label="复制关联 Trace ID">${icon('copy')}</button></div>`).join(''):'<p class="tx-no-data">无关联链路。延迟或重试消息若提供 span link，将在这里展示。</p>';
    const content={overview:section('执行信息',context)+section('Input · 请求与依赖',fields({...input,...Object.fromEntries(Object.entries(a).filter(([k])=>/^seckill\.(product_id|campaign_id|quantity|order_id|request_id)$/.test(k)))})+note)+section('Output · 结果与状态',fields(output))+section(`Attributes · ${Object.keys(a).length} 个字段`,fields(a),false)+section(`关联链路 · ${(s.links||[]).length}`,links,false),input:section('Input · 请求与依赖',fields({...input,...Object.fromEntries(Object.entries(a).filter(([k])=>/^seckill\.(product_id|campaign_id|quantity|order_id|request_id)$/.test(k)))})+note),output:section('Output · 结果与状态',fields(output)+note),attributes:section('Attributes',fields(a))+section('原始节点 JSON',`<pre>${esc(JSON.stringify(s,null,2))}</pre>`,false),links:section('关联链路',links)};
    $('#tx-node-body').innerHTML=content[tab]||window.tracePanels.render(payload,s,tab);window.workspaceControls.enhance($('#tx-node-body'));
    document.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tab===tab)));
    locationState();
  }
  async function handleDetail(e) {
    const zoom=e.target.closest('[data-order-zoom]');if(zoom){window.orderInvestigation.zoom(zoom.dataset.orderZoomTrace,Number(zoom.dataset.orderZoom));renderTree();return;}
    const summary=e.target.closest('.tx-section>summary');if(summary){e.preventDefault();toggleSection(summary.parentElement);return;}
    const b=e.target.closest('button');if(!b)return;
    if(b.dataset.focusSpan){selectedSpan=b.dataset.focusSpan;treeQuery='';$('#tx-tree-query').value='';let current=payload.spans.find(s=>s.span_id===selectedSpan);const seen=new Set();while(current&&!seen.has(current.span_id)){seen.add(current.span_id);collapsed.delete(current.span_id);current=payload.spans.find(s=>s.span_id===current.parent_span_id);}renderTree();tab='overview';renderNode();document.querySelector(`[data-span="${selectedSpan}"]`)?.scrollIntoView({block:'nearest'});}
    if(b.hasAttribute('data-close')||b.hasAttribute('data-return-order'))close();
    if(b.dataset.orderJourney){window.traceWorkspace.openOrder(b.dataset.orderJourney);return;}
    if(b.hasAttribute('data-retry'))open(selected);
    if(b.dataset.span||b.dataset.rootSpan){selectedSpan=b.dataset.span||b.dataset.rootSpan;if(waterfall)renderTree();else document.querySelectorAll('#trace-detail .tx-tree-row').forEach(row=>row.classList.toggle('is-selected',row.querySelector('[data-span]')?.dataset.span===selectedSpan));renderNode();}
    if(b.dataset.fold){collapsed.has(b.dataset.fold)?collapsed.delete(b.dataset.fold):collapsed.add(b.dataset.fold);updateTreeExpansion();}
    if(b.dataset.tab){tab=b.dataset.tab;renderNode();}
    if(b.hasAttribute('data-waterfall')){waterfall=!waterfall;b.setAttribute('aria-pressed',String(waterfall));renderTree();}
    if(b.hasAttribute('data-expand-peek'))$('#trace-detail').classList.toggle('tx-wide');
    if(b.hasAttribute('data-logs')){rememberNode();if(!$('#tx-return-trace'))$('#logs-content').insertAdjacentHTML('afterbegin',`<button id="tx-return-trace" class="button button-quiet tx-return-trace">${icon('arrow-left')}返回链路调查</button>`);$('#tx-return-trace').onclick=()=>{location.hash='#traces';};window.dispatchEvent(new CustomEvent('observability:open',{detail:{page:'logs',trace_id:selected,at:Math.floor(bounds().start/1e9)}}));}
    if(b.dataset.related){trail.push(selected);open(b.dataset.related,b.dataset.relatedSpan);}
    if(b.hasAttribute('data-back-trace'))open(trail.pop());
    if(b.dataset.step){const ids=[...document.querySelectorAll('#trace-results [data-trace]')].map(row=>row.dataset.trace);const id=ids[ids.indexOf(selected)+Number(b.dataset.step)];if(id){trail.length=0;open(id);}}
    if(b.dataset.copy||b.hasAttribute('data-copy-node')){const notice=$('#tx-copy-message');try{await navigator.clipboard.writeText(b.dataset.copy||JSON.stringify(payload.spans.find(s=>s.span_id===selectedSpan),null,2));if(notice?.isConnected)notice.textContent='已复制。';}catch{if(notice?.isConnected)notice.textContent='无法复制，请手动选择文本。';}}
  }
  async function loadLifecycle(form){
    if(!form.reportValidity())return;const key=form.elements.kind.value,id=form.elements.identifier.value.trim(),target=$('#tx-lifecycle-result');
    if(key==='order_id'?!/^[1-9][0-9]{0,18}$/.test(id)||BigInt(id)>9223372036854775807n:!/^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$/.test(id)){target.textContent='请输入有效的订单 ID 或事件 UUID。';return;}
    const range=window.traceControls.params();if(!range)return;const query=new URLSearchParams({[key]:id,window:range.get('window')});for(const name of ['start','end'])if(range.has(name))query.set(name,range.get(name));
    target.textContent='正在关联生命周期…';form.querySelector('[type=submit]').disabled=true;
    try{const data=await read('/lifecycle?'+query);if(target.isConnected)target.innerHTML=window.tracePanels.lifecycle(data);}catch(error){if(target.isConnected)target.textContent=error.name==='AbortError'?'生命周期查询已取消或超时，请重试。':error.message;}finally{if(form.isConnected)form.querySelector('[type=submit]').disabled=false;}
  }
  function activate(){document.body.classList.add('tx-active');search();const p=new URLSearchParams(location.search);if(p.get('trace')&&p.get('trace')!==selected)open(p.get('trace'),p.get('span'),p.get('trace_tab'));}
  function deactivate(){document.body.classList.remove('tx-active');++searchGeneration;pending.search?.abort();summaryBatch?.abort();pending.lifecycle?.abort();window.traceWorkspace.cancel();}
  return {mount,activate,deactivate,open,close,renderRows,toggleSection,search};
})();
