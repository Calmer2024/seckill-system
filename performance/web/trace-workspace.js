// Business journeys and bounded execution views share the Trace investigation drawer.
window.traceWorkspace = (() => {
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const icon=n=>`<svg aria-hidden="true"><use href="/icons.svg#${n}"></use></svg>`;
  const $=s=>document.querySelector(s.startsWith('.tx')?'#workspace-traces '+s:s);
  let view='traces', records=[],queryState='',queryMessage='';
  const labels={api:'API 请求',message:'消息处理',task:'后台任务',unknown:'类型未确定'};
  function mount(){
    $('.tx-segment').outerHTML=`<nav class="tx-segment" aria-label="追踪数据视角">${[['orders','Orders'],['traces','Traces'],['spans','Spans'],['services','Services']].map(([v,label])=>`<button type="button" data-workspace-view="${v}" aria-pressed="${v==='traces'}">${label}</button>`).join('')}</nav>`;
    $('.tx-layout').insertAdjacentHTML('beforeend','<section id="tx-business-workspace" class="tx-records" hidden><div class="tx-table-scroll" id="tx-observed-view"></div><p class="ui-source-note" id="tx-observed-note"></p></section>');
    $('.tx-workspace').insertAdjacentHTML('beforeend','<aside id="tx-service-detail" class="tx-peek" aria-label="服务详情" hidden></aside>');
    window.traceOrders.mount();
    $('.tx-toolbar-end').insertAdjacentHTML('afterbegin',`<label id="tx-execution-filter"><select aria-label="执行类型"><option value="all">全部执行</option>${Object.entries(labels).map(([v,t])=>`<option value="${v}">${t}</option>`).join('')}</select></label>`);
    document.querySelectorAll('[data-workspace-view]').forEach(b=>b.onclick=()=>switchView(b.dataset.workspaceView));
    $('#tx-execution-filter select').onchange=()=>{persist();window.traceExplorer.renderRows();render();};
    $('#tx-business-workspace').onclick=e=>{const summary=e.target.closest('.tx-section>summary');if(summary){e.preventDefault();window.traceExplorer.toggleSection(summary.parentElement);return;}const service=e.target.closest('[data-inspect-service]');if(service){openService(service.dataset.inspectService);return;}const b=e.target.closest('[data-related]');if(b)window.traceExplorer.open(b.dataset.related,b.dataset.relatedSpan);};
    $('#tx-service-detail').onclick=e=>{const b=e.target.closest('button');if(!b)return;if(b.hasAttribute('data-service-close'))closeService();if(b.hasAttribute('data-service-wide'))$('#tx-service-detail').classList.toggle('tx-wide');const related=e.target.closest('[data-related]');if(related)window.traceExplorer.open(related.dataset.related,related.dataset.relatedSpan);};
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('#tx-service-detail').hidden&&$('#trace-detail').hidden)closeService();});
    const p=new URLSearchParams(location.search);
    if(Object.hasOwn(labels,p.get('trace_execution')))$('#tx-execution-filter select').value=p.get('trace_execution');
    switchView(p.get('trace_view')||'traces',false);
    window.workspaceControls.enhance($('#tx-execution-filter'));
  }
  function persist(){const u=new URL(location.href);u.searchParams.set('trace_view',view);u.searchParams.set('trace_execution',executionFilter());history.replaceState(null,'',u);}
  function switchView(next,close=true){
    if(next==='journeys')next='orders';view=['orders','traces','spans','services'].includes(next)?next:'traces';if(close){window.traceExplorer.close();closeService();}
    document.querySelectorAll('[data-workspace-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.workspaceView===view)));
    $('.tx-layout').hidden=view==='orders';$('.tx-layout>.tx-records:not(#tx-business-workspace)').hidden=view!=='traces';$('#tx-business-workspace').hidden=!['spans','services'].includes(view);
    $('.tx-query-area').hidden=false;$('#trace-lookup').hidden=view==='orders';$('#tx-active-filters').hidden=view==='orders';if(view==='orders')$('#tx-query-error').hidden=true;
    $('#tx-filter-toggle').hidden=view==='orders';$('#tx-execution-filter').hidden=view==='orders';
    for(const id of ['tx-save-view','tx-views-button','tx-sort','tx-columns-button']){const el=$('#'+id);(el.closest('.tx-sort-control')||el).hidden=view!=='traces';}
    window.traceOrders.setVisible(view==='orders',close);persist();render();
    if(close&&view!=='orders')window.traceExplorer.search();
  }
  function update(rows){records=rows;queryState='';queryMessage='';render();}
  function begin(){records=[];queryState='loading';queryMessage='正在查询采样执行证据…';closeService();render();}
  function fail(message){records=[];queryState='failed';queryMessage=message;render();}
  function observed(){return records.filter(r=>executionFilter()==='all'||r.execution_type===executionFilter()).flatMap(r=>(r.operations||[]).map(s=>({...s,trace_id:r.trace_id})));}
  function services(){const result=new Map();for(const s of observed()){const v=result.get(s.service)||{name:s.service,spans:[],traces:new Set(),errors:0};v.spans.push(s);v.traces.add(s.trace_id);v.errors+=s.status==='error'?1:0;result.set(s.service,v);}return result;}
  function closeService(){ $('#tx-service-detail').hidden=true; }
  function openService(name){
    const v=services().get(name);if(!v)return;
    const samples=[...v.traces].map(id=>records.find(r=>r.trace_id===id)).filter(Boolean);
    $('#tx-service-detail').hidden=false;
    $('#tx-service-detail').innerHTML=`<header class="tx-peek-header"><strong>${esc(name)}</strong><div><button data-service-wide aria-label="切换服务详情宽度">${icon('arrows-out')}</button><button data-service-close aria-label="关闭服务详情">${icon('x')}</button></div></header><div class="tx-detail-grid"><aside class="tx-chain"><div class="tx-chain-heading"><strong>关联执行</strong></div><div class="tx-summary">${v.traces.size} traces · ${v.spans.length} spans</div><div class="ui-sample-list">${samples.map(r=>{const span=v.spans.find(s=>s.trace_id===r.trace_id);return `<button class="tx-node-select" data-related="${esc(r.trace_id)}" data-related-span="${esc(span.span_id)}">${icon('tree-structure')}<span class="tx-node-label"><strong>${esc(r.name||r.trace_id)}</strong><small>${esc(r.trace_id)}</small></span></button>`;}).join('')}</div></aside><article class="tx-node-detail"><div class="tx-node-title">${icon('tree-structure')}<h2>${esc(name)}</h2></div><div class="tx-tabs"><span>Overview</span></div><div class="tx-fields"><div><dt>采样执行节点</dt><dd>${v.spans.length}</dd></div><div><dt>错误节点</dt><dd>${v.errors}</dd></div><div><dt>关联 Trace</dt><dd>${v.traces.size}</dd></div></div>${window.investigationNavigation.context({service:name,...window.investigationNavigation.traceRange()})}<h3>已观测执行节点</h3><table class="tx-table"><thead><tr><th>名称</th><th>状态</th><th>耗时</th></tr></thead><tbody>${v.spans.map(s=>`<tr data-related="${esc(s.trace_id)}" data-related-span="${esc(s.span_id)}"><td><button class="tx-record-name">${esc(s.name)}</button></td><td>${esc(s.status)}</td><td>${Number(s.duration_ms).toFixed(2)} ms</td></tr>`).join('')}</tbody></table><p class="ui-source-note">来自当前查询内的采样证据。并行节点耗时不能直接累加为响应时间；关联执行可打开同一 Trace 详情面板。</p></article></div>`;
    window.workspaceControls.enhance($('#tx-service-detail'));
  }
  function render(){
    if(view==='traces')return;
    if(view==='orders'){window.traceOrders.count();return;}
    const operations=observed(),loading=records.filter(r=>r.summary_state==='loading').length,failed=records.filter(r=>r.summary_state==='unavailable').length;
    $('#tx-observed-note').textContent=queryMessage||`仅汇总当前查询返回的最多 50 条采样 Trace，非全量统计。${loading?loading+' 条摘要读取中。':''}${failed?failed+' 条摘要暂不可用。':''}${records.some(r=>r.operations_truncated)?'部分 Trace 节点达到 200 个摘要上限。':''}`;
    let header,body,count;
    if(view==='spans'){
      count=operations.length;header='<th>状态</th><th>Name</th><th>Service</th><th>Kind</th><th>Latency</th><th>Span ID</th><th>Trace ID</th>';
      body=operations.map(s=>`<tr data-related="${esc(s.trace_id)}" data-related-span="${esc(s.span_id)}"><td><span class="tx-status-dot tx-${s.status==='error'?'error':s.status==='ok'?'ok':'unset'}" title="Span 状态：${esc(s.status)}">${icon(s.status==='error'?'x':s.status==='ok'?'check':'minus')}</span></td><td><button class="tx-record-name">${esc(s.name)}</button></td><td>${esc(s.service)}</td><td>${esc((s.kind||'').replace('SPAN_KIND_',''))}</td><td><span class="tx-latency">${icon('timer')}${Number(s.duration_ms).toFixed(2)} ms</span></td><td><code>${esc(s.span_id)}</code></td><td><code>${esc(s.trace_id)}</code></td></tr>`).join('');
    }else{
      const values=[...services().values()];count=values.length;header='<th>Service</th><th>Traces</th><th>Spans</th><th>Error spans</th><th>Slowest span</th><th>Sample latency</th>';
      body=values.map(v=>{const slow=[...v.spans].sort((a,b)=>b.duration_ms-a.duration_ms)[0];return `<tr data-inspect-service="${esc(v.name)}"><td><button class="tx-record-name">${esc(v.name)}</button></td><td>${v.traces.size}</td><td>${v.spans.length}</td><td class="tx-error-text">${v.errors}</td><td>${esc(slow.name)}</td><td><span class="tx-latency">${icon('timer')}${Number(slow.duration_ms).toFixed(2)} ms</span></td></tr>`;}).join('');
    }
    $('#tx-count').textContent=`Stats · ${count} ${view}`;
    $('#tx-observed-view').innerHTML=`<table class="tx-table"><thead><tr>${header}</tr></thead><tbody>${body||`<tr><td colspan="7" class="tx-empty">${queryState==='failed'?'查询失败，请刷新或缩小范围后重试。':queryState==='loading'?'正在查询采样执行证据…':loading?'正在读取执行摘要…':failed?'摘要查询失败，请刷新或缩小范围。':'没有匹配的采样证据，请调整时间与筛选条件。'}</td></tr>`}</tbody></table>`;
    window.workspaceControls.enhance($('#tx-observed-view'));
  }
  function openOrder(id){switchView('orders');window.traceOrders.openOrder(id);}
  function refresh(){if(view==='orders')window.traceOrders.refresh();}
  function cancel(){window.traceOrders.cancel();closeService();}
  function reset(){window.traceOrders.reset();setExecution('all');persist();render();}
  function setExecution(kind){$('#tx-execution-filter select').value=Object.hasOwn(labels,kind)?kind:'all';persist();window.workspaceControls.enhance($('#tx-execution-filter'));}
  const executionFilter=()=>$('#tx-execution-filter select')?.value||'all';
  return {mount,update,begin,fail,openOrder,refresh,cancel,executionFilter,reset,setExecution,isOrders:()=>view==='orders'};
})();
