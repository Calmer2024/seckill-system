/* Shared table, drawer and dashboard patterns; queries remain owned by the signal facade. */
window.unifiedWorkspace = (() => {
  const $ = selector => document.querySelector(selector);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const icon = name => window.workspaceControls.icon(name);
  const date = seconds => new Date(seconds * 1000).toLocaleString('zh-CN', {hour12:false});
  const windows = [[60,'Last 1 hour'],[180,'Last 3 hours'],[360,'Last 6 hours'],[720,'Last 12 hours'],[1440,'Last 1 day'],[2880,'Last 2 days'],[10080,'Last 7 days'],[20160,'Last 14 days'],[43200,'Last 30 days']];
  let logRows = [], chartRows = [], alertRows = [], monitorTab = 'dashboards', metricRange={};
  function parseQuery(value, allowed) {
    const fields={}, text=[];let error='';
    const tokens=[];let token='',quote='',escaped=false;
    for(const char of String(value)){if(escaped){token+=char;escaped=false;}else if(quote){if(char==='\\')escaped=true;else if(char===quote)quote='';else token+=char;}else if((char==='"'||char==="'")&&(!token||token.endsWith(':')))quote=char;else if(/\s/.test(char)){if(token)tokens.push(token);token='';}else token+=char;}
    if(token)tokens.push(token);if(quote||escaped)error='引号或转义未闭合。';
    if(String(value).length>512||tokens.length>16)error='最多 512 个字符、16 个查询条件。';
    for(const token of tokens){const match=token.match(/^([a-z_]+):(.*)$/i);if(!match){text.push(token.replace(/^(["'])(.*)\1$/,'$2'));continue;}
      const key=match[1].toLowerCase(),val=match[2].replace(/^(["'])(.*)\1$/,'$2');
      if(!allowed.includes(key))error='不支持查询字段 '+key+'。';else if(!val)error=key+' 缺少查询值。';else if(key in fields)error=key+' 只能指定一个值。';else fields[key]=val;
    }return {fields,text:text.join(' '),error};
  }
  function queryValue(value){return /\s/.test(value)?JSON.stringify(value):value;}
  function setQueryField(input,key,value){const parsed=parseQuery(input.value,['status','scenario','mode','run_id']);delete parsed.fields[key];if(value)parsed.fields[key]=value;input.value=[...Object.entries(parsed.fields).map(([k,v])=>k+':'+queryValue(v)),parsed.text].filter(Boolean).join(' ');}
  function runFacets(selected,error){
    const pane=$('#ui-run-facets');if(!pane)return;
    pane.innerHTML=['status','scenario','mode'].map(key=>`<section class="ui-facet-group"><h3>${({status:'Status',scenario:'Scenario',mode:'Mode'})[key]}</h3>${[...document.querySelectorAll('[data-select="filter-'+key+'"] [data-value]')].filter(b=>b.dataset.value).map(b=>`<label class="tx-checkbox"><input type="checkbox" data-run-facet="${key}" value="${esc(b.dataset.value)}" ${selected[key]===b.dataset.value?'checked':''}><span>${esc(b.textContent.trim())}</span></label>`).join('')}</section>`).join('');
    pane.querySelectorAll('input').forEach(input=>input.onchange=()=>{const key=input.dataset.runFacet,value=input.checked?input.value:'';$('#run-'+key).value=value;setQueryField($('#run-search'),key,value);$('#run-search').dispatchEvent(new Event('input'));});
    $('#run-search').setCustomValidity(error);$('#run-search').setAttribute('aria-invalid',String(!!error));
    $('#run-filter-count').textContent=error||$('#run-filter-count').textContent;
    $('#run-search').placeholder='Search runs… status:completed mode:baseline run_id:…';window.workspaceControls.enhance(pane);
  }
  function section(title, html) { return `<details class="tx-section" open data-expanded="true"><summary aria-expanded="true">${esc(title)}</summary><div class="tx-disclosure-body"><div class="tx-disclosure-content">${html}</div></div></details>`; }
  function fields(values) { return `<dl class="tx-fields">${Object.entries(values).map(([key,value])=>`<div><dt>${esc(key)}</dt><dd class="ui-field-${value==null?'missing':/id$/i.test(key)?'identity':typeof value}">${value!=null&&typeof value==='object'?`<pre class="ui-structured-value">${esc(JSON.stringify(value,null,2))}</pre>`:esc(value==null?'未采集':value)}</dd></div>`).join('')}</dl>`; }
  function drawer(id, label) { return `<aside id="${id}" class="tx-peek" aria-label="${label}" hidden></aside>`; }
  function openDrawer(id, title, chain, content) {
    const pane=$('#'+id);pane.hidden=false;
    pane.innerHTML=`<header class="tx-peek-header"><strong>${esc(title)}</strong><div><button data-ui-wide aria-label="切换详情宽度">${icon('arrows-out')}</button><button data-ui-close aria-label="关闭详情">${icon('x')}</button></div></header><div class="tx-detail-grid"><aside class="tx-chain"><div class="tx-chain-heading"><strong>关联记录</strong></div><div class="ui-sample-list">${chain}</div></aside><article class="tx-node-detail"><div class="tx-node-title"><h2>${esc(title)}</h2></div>${content}</article></div>`;
    window.workspaceControls.enhance(pane);
    pane.querySelector('[data-ui-close]').focus();
  }
  function persist(key,value) { const url=new URL(location.href);url.searchParams.set(key,value);history.replaceState(null,'',url); }
  function chooseMonitor(tab) {
    monitorTab=['dashboards','alerts','services'].includes(tab)?tab:'dashboards';persist('monitor_tab',monitorTab);
    document.querySelectorAll('[data-monitor-tab]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.monitorTab===monitorTab)));
    document.querySelectorAll('[data-monitor-panel]').forEach(panel=>panel.hidden=panel.dataset.monitorPanel!==monitorTab);
    $('#metrics-window').hidden=monitorTab!=='dashboards';
    $('#ui-chart-detail').hidden=true;$('#ui-alert-detail').hidden=true;
    filterMonitorTables();
  }
  function timeOptions(field) {
    field.innerHTML=windows.map(([value,label])=>`<option value="${value}">${label}</option>`).join('');field.value='60';
    field.dispatchEvent(new Event('change'));
  }
  function mount() {
    const monitoring=$('#workspace-monitoring');monitoring.classList.add('tx-workspace','ui-workspace');
    const panels=[...monitoring.querySelectorAll('.signal-panel')], services=$('#monitoring');
    const heading=monitoring.querySelector('.workspace-heading');
    const toolbar=document.createElement('div');toolbar.className='tx-toolbar ui-monitor-toolbar';
    const form=$('#metrics-window');timeOptions(form.elements.window);form.querySelector('label').firstChild.textContent='';
    toolbar.innerHTML='<nav class="tx-segment" aria-label="监控视角">'+[['dashboards','Dashboards'],['alerts','Alerts'],['services','Services']].map(([key,label])=>`<button data-monitor-tab="${key}" aria-pressed="false">${label}</button>`).join('')+'</nav>';
    const query=document.createElement('div');query.className='tx-query-area';query.innerHTML=`<div class="tx-search">${icon('magnifying-glass')}<span class="tx-orders-scope">in monitoring</span><input id="ui-monitor-query" aria-label="搜索监控数据" placeholder="Search metrics, alerts or services…"><button id="ui-monitor-clear" aria-label="清除监控搜索">${icon('x')}</button></div>`;
    toolbar.append(form);heading.replaceWith(query,toolbar);
    $('#ui-monitor-query').value=new URLSearchParams(location.search).get('monitor_query')||'';
    $('#ui-monitor-query').oninput=()=>{persist('monitor_query',$('#ui-monitor-query').value);renderDashboard();filterMonitorTables();};$('#ui-monitor-clear').onclick=()=>{$('#ui-monitor-query').value='';$('#ui-monitor-query').dispatchEvent(new Event('input'));};
    const dashboard=panels[0];dashboard.className='ui-dashboard';dashboard.dataset.monitorPanel='dashboards';dashboard.querySelector('.p0-heading').remove();
    dashboard.insertAdjacentHTML('afterbegin',`<div class="ui-dashboard-controls"><nav class="ui-category-tabs" aria-label="指标分类">${[['all','Overview'],['http','HTTP'],['dependencies','Dependencies'],['business','Business'],['slo','SLO']].map(([key,label])=>`<button data-chart-category="${key}" aria-pressed="${key==='all'}">${label}</button>`).join('')}</nav><label><select id="ui-chart-view" aria-label="指标展示方式"><option value="chart">Charts</option><option value="table">Data table</option></select></label></div><div id="ui-metric-table" class="tx-table-scroll" hidden></div>`);
    const alertsPanel=panels[1];alertsPanel.className='ui-dashboard';alertsPanel.dataset.monitorPanel='alerts';alertsPanel.querySelector('.p0-heading h2').textContent='Active alerts';alertsPanel.querySelector('.p0-heading p').remove();
    services.dataset.monitorPanel='services';services.className='ui-dashboard';services.querySelector('.domain-heading').remove();
    const scroll=document.createElement('div');scroll.className='ui-content-scroll';scroll.append(dashboard,alertsPanel,services);monitoring.append(scroll);
    monitoring.insertAdjacentHTML('beforeend',drawer('ui-chart-detail','指标详情')+drawer('ui-alert-detail','告警详情'));
    $('#ui-chart-view').onchange=()=>{persist('monitor_display',$('#ui-chart-view').value);renderDashboard();};form.elements.window.onchange=()=>{const url=new URL(location.href);url.searchParams.delete('monitor_start');url.searchParams.delete('monitor_end');history.replaceState(null,'',url);timeOptionsLabel(form.elements.window);form.requestSubmit();};
    monitoring.addEventListener('click',event=>{
      const tab=event.target.closest('[data-monitor-tab]');if(tab)chooseMonitor(tab.dataset.monitorTab);
      const category=event.target.closest('[data-chart-category]');if(category){persist('monitor_category',category.dataset.chartCategory);document.querySelectorAll('[data-chart-category]').forEach(b=>b.setAttribute('aria-pressed',String(b===category)));renderDashboard();}
      const chart=event.target.closest('[data-expand-chart]');if(chart)openChart(chart.dataset.expandChart);
      const alert=event.target.closest('[data-alert-row]');if(alert)openAlert(Number(alert.dataset.alertRow));
    });
    const url=new URLSearchParams(location.search);if(windows.some(([n])=>String(n)===url.get('monitor_window'))){form.elements.window.value=url.get('monitor_window');form.elements.window.dispatchEvent(new Event('change'));}
    form.elements.window.addEventListener('change',()=>persist('monitor_window',form.elements.window.value));
    if(['chart','table'].includes(url.get('monitor_display')))$('#ui-chart-view').value=url.get('monitor_display');
    const category=document.querySelector('[data-chart-category="'+(url.get('monitor_category')||'all').replace(/[^a-z]/g,'')+'"]');
    if(category)document.querySelectorAll('[data-chart-category]').forEach(b=>b.setAttribute('aria-pressed',String(b===category)));
    chooseMonitor(url.get('monitor_tab'));renderDashboard();new MutationObserver(filterMonitorTables).observe($('#p0-service-status'),{childList:true,subtree:true});
    mountLogs();window.workspaceControls.enhance(monitoring);
    document.addEventListener('click',event=>{
      const close=event.target.closest('[data-ui-close]');if(close){const pane=close.closest('.tx-peek');pane.hidden=true;const url=new URL(location.href);if(pane.id==='ui-log-detail')url.searchParams.delete('log_record');if(pane.id==='ui-chart-detail')url.searchParams.delete('monitor_chart');if(pane.id==='ui-alert-detail')url.searchParams.delete('monitor_alert');history.replaceState(null,'',url);}
      const wide=event.target.closest('[data-ui-wide]');if(wide)wide.closest('.tx-peek').classList.toggle('tx-wide');
      const summary=event.target.closest('#ui-log-detail .tx-section>summary,#ui-alert-detail .tx-section>summary');if(summary){event.preventDefault();window.traceExplorer.toggleSection(summary.parentElement);}
    });
    document.addEventListener('keydown',event=>{if(event.key==='Escape')document.querySelectorAll('#ui-log-detail,#ui-chart-detail,#ui-alert-detail').forEach(pane=>pane.hidden=true);});
  }
  function mountLogs() {
    const page=$('#workspace-logs');page.classList.add('tx-workspace','ui-workspace');page.querySelector('.workspace-heading').remove();
    const content=$('#logs-content'),panel=content.querySelector('.signal-panel'),form=$('#log-search'),results=$('#log-results'),message=$('#logs-message');
    const text=document.createElement('input');text.id='ui-log-query';text.setAttribute('aria-label','搜索日志和查询条件');text.placeholder='Search logs… service:order-api level:ERROR trace_id:…';
    const query=document.createElement('div');query.className='tx-query-area';query.innerHTML=`<div class="tx-search">${icon('magnifying-glass')}<span class="tx-orders-scope">in logs</span></div>`;query.firstChild.append(text);query.firstChild.insertAdjacentHTML('beforeend',`<button form="log-search" type="submit" aria-label="查询日志">${icon('arrow-right')}</button>`);
    const toolbar=document.createElement('div');toolbar.className='tx-toolbar';toolbar.innerHTML='<nav class="tx-segment"><span>Logs</span></nav>';
    const time=form.elements.window,timeLabel=time.closest('label');time.setAttribute('form','log-search');timeOptions(time);timeLabel.firstChild.textContent='';toolbar.append(timeLabel,$('#clear-log-correlation'));time.onchange=()=>form.requestSubmit();
    const layout=document.createElement('div');layout.className='tx-layout';layout.innerHTML='<aside class="tx-facets" aria-label="日志筛选"></aside><section class="tx-records"><div class="tx-table-scroll"></div></section>';
    form.hidden=true;layout.querySelector('.tx-facets').append(form);layout.querySelector('.tx-facets').insertAdjacentHTML('beforeend','<div id="ui-log-facets"></div>');layout.querySelector('.tx-table-scroll').append(results);layout.querySelector('.tx-records').append(message);message.className='ui-source-note';
    panel.replaceWith(query,toolbar,layout);content.insertAdjacentHTML('beforeend',drawer('ui-log-detail','日志详情'));
    form.querySelectorAll('input[name=event_id]')[0].pattern='[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}';
    page.addEventListener('click',event=>{const row=event.target.closest('[data-log-row]');if(row)openLog(Number(row.dataset.logRow));const trace=event.target.closest('#ui-log-detail [data-open-trace]');if(trace)window.dispatchEvent(new CustomEvent('observability:open',{detail:{page:'traces',trace_id:trace.dataset.openTrace}}));});
    form.insertAdjacentHTML('beforeend','<input type="hidden" name="start"><input type="hidden" name="end">');
    const stored=new URLSearchParams(new URLSearchParams(location.search).get('log_filters')||'');for(const [name,value] of stored){const field=form.elements.namedItem(name);if(field && typeof field.value==='string')field.value=value;}
    form.querySelectorAll('select').forEach(field=>field.dispatchEvent(new Event('change')));time.dispatchEvent(new Event('change'));
    form.addEventListener('submit',event=>{if(!applyLogQuery()){event.preventDefault();event.stopImmediatePropagation();}},true);
    text.onkeydown=event=>{if(event.key==='Enter'){event.preventDefault();if(applyLogQuery())form.requestSubmit();}};
    if(stored.has('start')){const option=time.querySelector('option[value="60"]');if(option)option.textContent='指定时间段';window.workspaceControls.syncSelect(time);}
    time.onchange=()=>{form.elements.start.value='';form.elements.end.value='';form.elements.at.value='';timeOptionsLabel(time);form.requestSubmit();};
    syncLogQuery();
    window.workspaceControls.enhance(page);form.requestSubmit();
  }
  function logs(rows) {
    logRows=rows;$('#ui-log-detail').hidden=true;syncLogQuery();
    $('#log-results').innerHTML=`<table class="tx-table"><thead><tr><th>Level</th><th>Message</th><th>Service</th><th>Instance</th><th>Time</th><th>Trace ID</th><th>Order ID</th></tr></thead><tbody>${rows.length?rows.map((row,index)=>{const f=row.fields;return `<tr data-log-row="${index}" class="ui-log-row level-${esc(String(f.level||"unknown").toLowerCase())}"><td><span class="ui-log-level level-${esc(String(f.level||"unknown").toLowerCase())}">${esc(f.level||'未采集')}</span></td><td class="ui-message-cell"><button class="tx-record-name">${esc(f.message||f.event||f.route_template||'结构化日志')}</button></td><td>${esc(row.service)}</td><td>${esc(row.instance)}</td><td class="tx-number">${esc(date(Number(row.timestamp_ns)/1e9))}</td><td><code>${esc(f.trace_id)}</code></td><td>${esc(f.order_id)}</td></tr>`;}).join(''):'<tr><td colspan="7" class="tx-empty">此范围内无日志，请调整时间与筛选条件。</td></tr>'}</tbody></table>`;
    const query=new URLSearchParams(new FormData($('#log-search')));persist('log_filters',query.toString());const selected=new URLSearchParams(location.search).get('log_record'),index=rows.findIndex(row=>String(row.timestamp_ns)===selected);if(index>=0)openLog(index);
  }
  function openLog(index) {
    const row=logRows[index];if(!row)return;const f=row.fields;persist('log_record',row.timestamp_ns);document.querySelectorAll('#log-results [data-log-row]').forEach(item=>item.classList.toggle('is-selected',Number(item.dataset.logRow)===index));
    const chain=logRows.map((r,i)=>`<button class="tx-node-select ${index===i?'is-selected':''}" data-log-row="${i}">${icon('file-text')}<span class="tx-node-label"><strong>${esc(r.fields.message||r.fields.event||'日志记录')}</strong><small>${esc(r.service)} · <span class="ui-log-level level-${esc(String(r.fields.level||"unknown").toLowerCase())}">${esc(r.fields.level)}</span></small></span></button>`).join('');
    openDrawer('ui-log-detail',f.event||f.route_template||'Log record',chain,`<nav class="tx-tabs"><span>Details</span></nav>${section('Message',`<pre class="ui-log-message level-${esc(String(f.level||"unknown").toLowerCase())}">${esc(f.message||'未采集')}</pre>`)}${section('Context',fields({Service:row.service,Instance:row.instance,Time:date(Number(row.timestamp_ns)/1e9),Level:f.level,'Trace ID':f.trace_id,'Span ID':f.span_id,'Order ID':f.order_id,'Event ID':f.event_id}))}${window.investigationNavigation.context({trace_id:f.trace_id,span_id:f.span_id,order_id:f.order_id,event_id:f.event_id,causation_id:f.causation_id,request_id:f.request_id,service:row.service,at:Number(row.timestamp_ns)/1e9})}${section('Structured fields',fields(f))}<p class="ui-source-note">集中日志 · 已按后端白名单过滤与脱敏。</p>`);
  }
  function syncLogQuery(){const form=$('#log-search');if(!$('#ui-log-query'))return;$('#ui-log-query').value=[...['service','level','trace_id','order_id','event_id','request_id'].map(key=>form.elements[key].value?key+':'+queryValue(form.elements[key].value):''),form.elements.text.value?'text:'+queryValue(form.elements.text.value):''].filter(Boolean).join(' ');renderLogFacets();}
  function renderLogFacets(){const form=$('#log-search');$('#ui-log-facets').innerHTML=['service','level'].map(key=>`<section class="ui-facet-group"><h3>${key==='service'?'Service':'Level'}</h3>${[...form.elements[key].options].filter(o=>o.value).map(o=>`<label class="tx-checkbox"><input type="checkbox" data-log-facet="${key}" value="${esc(o.value)}" ${form.elements[key].value===o.value?'checked':''}><span class="${key==='level'?'ui-log-level level-'+o.value.toLowerCase():''}">${esc(o.text)}</span></label>`).join('')}</section>`).join('');$('#ui-log-facets').querySelectorAll('input').forEach(input=>input.onchange=()=>{if(!applyLogQuery())return;form.elements[input.dataset.logFacet].value=input.checked?input.value:'';syncLogQuery();form.requestSubmit();});window.workspaceControls.enhance($('#ui-log-facets'));}
  function applyLogQuery(){const form=$('#log-search'),input=$('#ui-log-query'),parsed=parseQuery(input.value,['service','level','trace_id','order_id','event_id','request_id','text']);let error=parsed.error;for(const [key,value] of Object.entries(parsed.fields)){const field=form.elements[key];if(field.tagName==='SELECT'&&![...field.options].some(o=>o.value===value))error=key+' 的值无效。';if(key==='trace_id'&&!/^[0-9a-fA-F]{32}$/.test(value))error='Trace ID 应为 32 位十六进制。';if(key==='order_id'&&(!/^[1-9][0-9]{0,18}$/.test(value)||BigInt(value)>9223372036854775807n))error='订单 ID 无效。';if(key==='event_id'&&!/^[0-9a-fA-F]{8}(-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$/.test(value))error='事件 ID 应为 UUID。';}if(parsed.fields.request_id?.length>64)error='Request ID 最多 64 个字符。';if((parsed.fields.text||parsed.text).length>80)error='日志正文查询最多 80 个字符。';input.setCustomValidity(error);input.setAttribute('aria-invalid',String(!!error));if(error){$('#logs-message').textContent=error;input.reportValidity();return false;}if(form.elements.trace_id.value!==(parsed.fields.trace_id||''))form.elements.at.value='';for(const key of ['service','level','trace_id','order_id','event_id','request_id'])form.elements[key].value=parsed.fields[key]||'';form.elements.text.value=parsed.fields.text||parsed.text;renderLogFacets();return true;}
  function timeOptionsLabel(field){for(const [value,label] of windows){const option=field.querySelector('option[value="'+value+'"]');if(option)option.textContent=label;}window.workspaceControls.syncSelect(field);}
  function filterMonitorTables(){const query=$('#ui-monitor-query').value.trim().toLocaleLowerCase();document.querySelectorAll('#active-alerts tbody tr,#p0-service-status tr').forEach(row=>row.hidden=!!query&&!row.textContent.toLocaleLowerCase().includes(query));}
  function metrics(payload) { chartRows=payload.charts;metricRange={start:payload.start||payload.sampled_at-payload.window_minutes*60,end:payload.end||payload.sampled_at};if(new URLSearchParams(location.search).has('monitor_start')){const field=$('#metrics-window').elements.window;field.selectedOptions[0].textContent='指定时间段';window.workspaceControls.syncSelect(field);}renderDashboard();filterMonitorTables();if(new URLSearchParams(location.search).has('monitor_chart'))openChart(new URLSearchParams(location.search).get('monitor_chart')); }
  function metricsFailed(){chartRows=chartRows.map(row=>({...row,status:'unavailable',series:[]}));renderDashboard();$('#ui-chart-detail').hidden=true;}
  function renderDashboard() {
    if(!$('#ui-chart-view'))return;
    const category=$('[data-chart-category][aria-pressed=true]')?.dataset.chartCategory||'all';
    const groups={http:['http_rate','http_p95'],dependencies:['kafka_lag','db_connections'],business:['outbox_pending','negative_stock'],slo:['slo_burn_fast','slo_burn_slow']};
    const query=$('#ui-monitor-query')?.value.trim().toLocaleLowerCase()||'';
    const rows=chartRows.filter(item=>(category==='all'||groups[category]?.includes(item.id))&&(!query||JSON.stringify(item).toLocaleLowerCase().includes(query)));const table=$('#ui-chart-view').value==='table';
    $('#environment-charts').hidden=table;$('#ui-metric-table').hidden=!table;
    $('#environment-charts').innerHTML=rows.map(window.workspaceSignals.renderChart).join('');
    if(!rows.length)$('#environment-charts').innerHTML='<p class="tx-empty">没有匹配的指标，请调整搜索内容或指标分类。</p>';
    $('#ui-metric-table').innerHTML=`<table class="tx-table"><thead><tr><th>Metric</th><th>Series</th><th>Latest value</th><th>Unit</th><th>Collection status</th></tr></thead><tbody>${rows.map(item=>(item.series.length?item.series:[{labels:{},points:[]}]).map(series=>`<tr data-expand-chart="${esc(item.id)}"><td><button class="tx-record-name">${esc(item.title)}</button></td><td>${esc(Object.values(series.labels).join(' · ')||'环境')}</td><td>${series.points.at(-1)?.[1]??'未采集'}</td><td>${esc(item.unit)}</td><td>${esc(item.status)}</td></tr>`).join('')).join('')}</tbody></table>`;
    window.workspaceControls.enhance($('#environment-charts'));
  }
  function openChart(id) {
    const item=chartRows.find(row=>row.id===id);if(!item)return;persist('monitor_chart',id);
    const chain=chartRows.map(row=>`<button class="tx-node-select ${row.id===id?'is-selected':''}" aria-pressed="${row.id===id}" data-expand-chart="${esc(row.id)}">${icon('chart-line-up')}<span class="tx-node-label"><strong>${esc(row.title)}</strong><small>${esc(row.status)}</small></span></button>`).join('');
    const data=`<table class="tx-table"><thead><tr><th>Series</th><th>Time</th><th>Value (${esc(item.unit)})</th><th>调查</th></tr></thead><tbody>${item.series.flatMap(series=>series.points.map(([time,value])=>`<tr><td>${esc(Object.values(series.labels).join(' · ')||'环境')}</td><td>${esc(date(time))}</td><td>${value??'未采集'}</td><td>${window.investigationNavigation.action('该时刻 Traces',{page:'traces',service:series.labels.service,...window.investigationNavigation.range(time,300)})}${window.investigationNavigation.action('该时刻日志',{page:'logs',service:series.labels.service,...window.investigationNavigation.range(time,300)})}</td></tr>`)).join('')||'<tr><td colspan="3">无有效采集数据。</td></tr>'}</tbody></table>`;
    openDrawer('ui-chart-detail',item.title,chain,window.workspaceSignals.renderChart(item)+`<div class="ui-investigation-actions">${window.investigationNavigation.action('查看此时段 Traces',{page:'traces',...metricRange})}${window.investigationNavigation.action('查看此时段日志',{page:'logs',...metricRange})}${item.series.map(series=>series.labels.service).filter((v,i,a)=>v&&a.indexOf(v)===i).map(service=>window.investigationNavigation.action(service+' · Traces',{page:'traces',service,...metricRange})).join('')}</div>`+data+'<p class="ui-source-note">Prometheus · 每个指标最多 16 条序列、每序列 121 个点。历史范围受实际保留策略影响，无数据不视为零。</p>');
    $('#ui-chart-detail .signal-chart [data-expand-chart]')?.remove();
  }
  function alerts(payload) {
    alertRows=payload.alerts;
    $('#active-alerts').innerHTML=payload.alert_status!=='ok'?'<p class="tx-empty">告警查询失败，不能认定无告警。</p>':`<div class="tx-table-scroll"><table class="tx-table"><thead><tr><th>Severity</th><th>Name</th><th>Service</th><th>Summary</th><th>Started</th></tr></thead><tbody>${payload.alerts.length?payload.alerts.map((row,index)=>`<tr data-alert-row="${index}"><td>${esc(row.labels.severity)}</td><td><button class="tx-record-name">${esc(row.labels.alertname)}</button></td><td>${esc(row.labels.service||row.labels.job)}</td><td>${esc(row.annotations.summary)}</td><td>${esc(row.starts_at)}</td></tr>`).join(''):'<tr><td colspan="5" class="tx-empty">当前无未抑制的活动告警。</td></tr>'}</tbody></table></div>`;
    filterMonitorTables();
    const selected=new URLSearchParams(location.search).get('monitor_alert');if(selected&&monitorTab==='alerts'){const index=alertRows.findIndex(row=>JSON.stringify([row.labels.alertname,row.starts_at])===selected);if(index>=0)openAlert(index);}
  }
  function openAlert(index) {
    const row=alertRows[index];if(!row)return;
    persist('monitor_alert',JSON.stringify([row.labels.alertname,row.starts_at]));
    openDrawer('ui-alert-detail',row.labels.alertname,alertRows.map((item,i)=>`<button class="tx-node-select ${i===index?'is-selected':''}" aria-pressed="${i===index}" data-alert-row="${i}">${icon('warning-circle')}<span>${esc(item.labels.alertname)}</span></button>`).join(''),section('Summary',fields(row.annotations))+section('Labels',fields(row.labels))+section('Started',fields({started_at:row.starts_at}))+window.investigationNavigation.context({service:row.labels.service,at:Date.parse(row.starts_at)/1000})+window.investigationNavigation.action('查看告警时段错误 Traces',{page:'traces',service:row.labels.service,errors:true,...window.investigationNavigation.range(Date.parse(row.starts_at)/1000)})+`<a href="/docs/observability/p3-runbooks.md" target="_blank" rel="noreferrer">排障手册</a>`);
  }
  document.addEventListener('DOMContentLoaded',mount);
  return {metrics,metricsFailed,alerts,logs,parseQuery,runFacets,syncLogQuery};
})();
