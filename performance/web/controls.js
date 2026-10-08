/* Shared Lucide-backed controls. Hidden native fields retain form semantics. */
window.workspaceControls = (() => {
  let sequence = 0;
  const selections = new WeakMap();
  const icon = name => `<svg aria-hidden="true" focusable="false"><use href="/icons.svg#${name}"></use></svg>`;
  const iconActions = [
    ['#tx-reset, [data-reset-query], #clear-run-filters', 'arrow-counter-clockwise', '重置筛选'],
    ['#reset-form', 'arrow-counter-clockwise', '恢复默认设置'],
    ['#tx-save-view, #tx-save-view-form button[type="submit"]', 'floppy-disk', '保存当前视图'],
    ['#tx-views-button', 'bookmark-simple', '已保存的视图'],
    ['#metrics-window>button, #refresh-alerts', 'arrow-clockwise', '刷新指标 / 告警'],
    ['#log-search button:not([type="button"])', 'magnifying-glass', '查询日志'],
    ['#clear-log-correlation', 'clock-counter-clockwise', '回到当前时间'],
    ['#refresh-observability, [data-retry-search], [data-retry], [data-order-retry], [data-order-detail-retry]', 'arrow-clockwise', '刷新 / 重试'],
    ['#open-new-run', 'plus', '新建压测任务'],
    ['[data-waterfall]', 'chart-bar-horizontal', '切换瀑布时间线'],
    ['[data-logs]', 'file-text', '查看关联日志'],
    ['[data-return-order]', 'arrow-left', '返回订单流程'],
    ['[data-order-journey]', 'tree-structure', '查看订单流程'],
    ['[data-order-trace]', 'arrow-square-out', '查看 Trace 与执行节点'],
    ['[data-copy-node]', 'copy', '复制节点 JSON'],
    ['#tx-return-trace', 'arrow-left', '返回链路调查'],
    ['#tx-order-prev', 'arrow-left', '上一页订单'],
    ['#tx-order-next', 'arrow-right', '下一页订单'],
    ['#trace-search button[type="submit"], #tx-orders-filters button[type="submit"]', 'funnel', '应用筛选'],
    ['#tx-lifecycle-form button[type="submit"]', 'tree-structure', '加载生命周期'],
    ['#tx-dates-form button[type="submit"]', 'check', '应用日期范围'],
    ['[data-time-back]', 'arrow-left', '返回时间范围'],
    ['.tx-set-default', 'bookmark-simple', '设为默认时间范围'],
    ['#tx-filter-toggle, #tx-order-filter-toggle', 'sidebar-simple', '展开 / 折叠筛选栏'],
  ];
  function actionButtons(container) {
    const buttons = [...container.querySelectorAll('button')];
    if (container.matches?.('button')) buttons.unshift(container);
    for (const button of buttons) {
      const action = iconActions.find(([selector]) => button.matches(selector));
      if (action && !button.dataset.actionIcon) {
        const [, glyph, label] = action;
        button.dataset.actionIcon = glyph;
        button.setAttribute('aria-label', label);
        button.dataset.tooltip = label;
        button.innerHTML = icon(glyph);
      }
      if ((action || (button.querySelector('svg') && !button.textContent.trim())) && !button.matches('.tx-fold,.select-trigger,.select-option')) {
        button.classList.add('ui-icon-button');
        const label = button.getAttribute('aria-label');
        if (label) button.dataset.tooltip = label;
      }
    }
  }
  function close(except = null) {
    document.querySelectorAll('.custom-select').forEach(root => {
      if (root === except) return;
      root.querySelector('.select-menu').hidden = true;
      root.querySelector('.select-trigger').setAttribute('aria-expanded', 'false');
    });
  }
  function bind(root) {
    if (root.dataset.controlReady) return;
    root.dataset.controlReady = 'true';
    const trigger = root.querySelector('.select-trigger');
    const menu = root.querySelector('.select-menu');
    const field = root.querySelector('select, input');
    const options = () => [...menu.querySelectorAll('[role="option"]')].filter(item => !item.disabled);
    menu.id ||= `workspace-options-${++sequence}`;
    menu.setAttribute('aria-label', trigger.getAttribute('aria-label') || field.name || '选项');
    trigger.setAttribute('aria-controls', menu.id);
    function open(direction = 1) {
      close(root);
      menu.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
      const items = options();
      items.forEach(item => {item.tabIndex = -1;});
      (items.find(item => item.getAttribute('aria-selected') === 'true') || (direction > 0 ? items[0] : items.at(-1)))?.focus();
    }
    function choose(option) {
      if (!option || option.disabled) return;
      field.value = option.dataset.value;
      trigger.querySelector('span').textContent = option.textContent;
      menu.querySelectorAll('[role="option"]').forEach(item => item.setAttribute('aria-selected', String(item === option)));
      close();
      trigger.focus();
      field.dispatchEvent(new Event('change', {bubbles:true}));
    }
    trigger.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      if (menu.hidden) open(); else close();
    });
    trigger.addEventListener('keydown', event => {
      if (['ArrowDown', 'ArrowUp'].includes(event.key)) {
        event.preventDefault(); open(event.key === 'ArrowDown' ? 1 : -1);
      }
    });
    menu.addEventListener('click', event => {
      const option = event.target.closest('[role="option"]');
      if (option) {event.preventDefault(); event.stopPropagation(); choose(option);}
    });
    let typed = '', lastTyped = 0;
    root.addEventListener('keydown', event => {
      if (menu.hidden) return;
      const items = options();
      const index = items.indexOf(document.activeElement);
      if (event.key === 'Escape') {
        event.preventDefault(); event.stopPropagation(); close(); trigger.focus();
      } else if (event.key === 'Tab') {
        close();
      } else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key) && event.target !== trigger) {
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length-1 : (index+(event.key === 'ArrowDown' ? 1 : -1)+items.length)%items.length;
        items[next]?.focus();
      } else if (event.key.length === 1 && event.key !== ' ' && !event.ctrlKey && !event.metaKey) {
        const now = Date.now(); typed = (now-lastTyped > 700 ? '' : typed)+event.key.toLocaleLowerCase(); lastTyped = now;
        items.find(item => item.textContent.toLocaleLowerCase().startsWith(typed))?.focus();
      }
    });
    root.addEventListener('focusout', event => {
      if (root.contains(event.relatedTarget)) return;
      queueMicrotask(() => {
      if (!root.contains(document.activeElement)) {
        menu.hidden = true; trigger.setAttribute('aria-expanded','false');
      }
      });
    });
  }
  function select(field) {
    if (selections.has(field)) return;
    const label = field.labels?.[0];
    const name = label ? [...label.childNodes].filter(node => node.nodeType === Node.TEXT_NODE).map(node => node.textContent).join('').trim() : field.name;
    const root = document.createElement('span');
    root.className = 'custom-select signal-select';
    root.innerHTML = `<button class="select-trigger" type="button" aria-haspopup="listbox" aria-expanded="false"><span></span>${icon('caret-down')}</button><span class="select-menu" role="listbox" hidden></span>`;
    field.before(root);
    root.prepend(field);
    field.hidden = true; field.tabIndex = -1; field.setAttribute('aria-hidden','true');
    const trigger = root.querySelector('.select-trigger');
    const menu = root.querySelector('.select-menu');
    menu.setAttribute('aria-label', name || '选项');
    function sync() {
      const fragment = document.createDocumentFragment();
      [...field.options].forEach(option => {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'select-option'; button.tabIndex = -1;
        button.setAttribute('role','option'); button.setAttribute('aria-selected', String(option.selected));
        button.dataset.value = option.value; button.textContent = option.textContent; button.disabled = option.disabled;
        fragment.append(button);
      });
      menu.replaceChildren(fragment);
      trigger.querySelector('span').textContent = field.selectedOptions[0]?.textContent || '请选择';
      trigger.setAttribute('aria-label', `${name}：${trigger.querySelector('span').textContent}`);
      trigger.disabled = field.disabled;
    }
    selections.set(field, {sync,trigger});
    field.addEventListener('change', sync);
    sync(); bind(root);
  }
  function clearError(field) {
    field.removeAttribute('aria-invalid');
    const error = document.getElementById(field.dataset.errorId || '');
    if (error) error.hidden = true;
  }
  function showError(field) {
    let error = document.getElementById(field.dataset.errorId || '');
    if (!error) {
      error = document.createElement('span'); error.className = 'field-error'; error.id = `workspace-error-${++sequence}`;
      field.dataset.errorId = error.id;
      field.setAttribute('aria-describedby', [field.getAttribute('aria-describedby'),error.id].filter(Boolean).join(' '));
      (selections.has(field) ? field.closest('.custom-select') : field).after(error);
    }
    const validity = field.validity;
    error.textContent = validity.valueMissing ? '请填写此项。' : validity.rangeUnderflow ? `不能小于 ${field.min}。` : validity.rangeOverflow ? `不能大于 ${field.max}。` : validity.tooLong ? `最多 ${field.maxLength} 个字符。` : '输入格式不正确，请检查后重试。';
    error.hidden = false; field.setAttribute('aria-invalid','true');
  }
  const copySelector='.tx-fields dd,.tx-table tbody td,.report-meta strong,#run-context-id,.active-run-id strong,.tx-peek-header code,.tx-node-meta code,.tx-related code';
  const copyKeys=new Set(['traceid','spanid','parentspanid','orderid','eventid','causationid','requestid','runid','messagingmessageid','订单id','订单编号','任务id','任务编号','事件id','事件编号','请求id','请求编号']);
  function copyLabel(target){
    if(target.matches('#run-context-id,.active-run-id strong'))return '任务 ID';
    if(target.matches('.tx-node-meta code'))return '节点 ID';
    if(target.matches('.tx-peek-header code'))return '订单 ID';
    if(target.matches('.tx-related code'))return 'Span ID';
    let label='';
    if(target.matches('dd'))label=target.parentElement.querySelector('dt')?.textContent||'';
    if(target.matches('td'))label=target.closest('table')?.querySelector('thead tr')?.children[target.cellIndex]?.textContent||'';
    if(target.matches('.report-meta strong'))label=target.parentElement.querySelector('.meta-label')?.textContent||'';
    const key=label.trim().toLowerCase().replace(/^seckill\./,'').replace(/[\s_.-]/g,'');
    return copyKeys.has(key)?label.trim():'';
  }
  const copyTimers=new WeakMap();let feedbackTimer;
  function valueText(target){const clone=target.cloneNode(true);clone.querySelectorAll('button[data-value-copy]').forEach(b=>b.remove());return clone.textContent.trim();}
  function copyValues(container){
    const targets=[...container.querySelectorAll(copySelector)];if(container.matches?.(copySelector))targets.unshift(container);
    for(const target of targets){
      const label=copyLabel(target);if(!label)continue;
      if(target.closest('button,a,summary,textarea,dialog:not([open])')||target.parentElement?.closest('[data-value-target]')||target.matches('td[colspan]')||target.closest('.tx-skeleton'))continue;
      const value=valueText(target);if(!value||['未采集','未提供','未采集或根节点','根节点','根节点或未采集','—','--'].includes(value))continue;
      if(target.querySelector(':scope>button[data-value-copy]'))continue;
      target.dataset.valueTarget='true';target.classList.add('ui-copy-value');
      const button=document.createElement('button');button.type='button';button.dataset.valueCopy='true';button.className='ui-value-copy ui-icon-button';button.setAttribute('aria-label','复制 '+label);button.dataset.tooltip='复制 '+label;button.innerHTML=icon('copy');target.append(button);
    }
  }
  async function copy(value,button){
    clearTimeout(copyTimers.get(button));const original=button.dataset.copyOriginalLabel||button.getAttribute('aria-label')||'复制';button.dataset.copyOriginalLabel=original;
    let notice=document.querySelector('#ui-copy-feedback');if(!notice){notice=document.createElement('div');notice.id='ui-copy-feedback';notice.setAttribute('role','status');notice.setAttribute('aria-live','polite');document.body.append(notice);}
    clearTimeout(feedbackTimer);button.setAttribute('aria-busy','true');
    try{
      if(!navigator.clipboard?.writeText)throw new Error('clipboard unavailable');await navigator.clipboard.writeText(String(value));
      button.dataset.copyState='success';const glyph=button.querySelector('svg use');if(glyph)glyph.setAttribute('href','/icons.svg#check');button.setAttribute('aria-label','已复制');button.dataset.tooltip='已复制';notice.replaceChildren(document.createTextNode('已复制到剪贴板'));notice.hidden=false;feedbackTimer=setTimeout(()=>notice.hidden=true,2200);
    }catch{
      button.dataset.copyState='error';button.setAttribute('aria-label','复制失败，点击重试');button.dataset.tooltip='复制失败，点击重试';notice.replaceChildren(document.createTextNode('复制失败，可重试或手动复制：'));
      const manual=document.createElement('textarea');manual.readOnly=true;manual.value=String(value);manual.setAttribute('aria-label','手动复制内容');notice.append(manual);manual.addEventListener('focus',()=>manual.select());
      const dismiss=document.createElement('button');dismiss.className='ui-icon-button';dismiss.setAttribute('aria-label','关闭复制提示');dismiss.innerHTML=icon('x');dismiss.onclick=()=>{notice.hidden=true;button.focus();};notice.append(dismiss);notice.hidden=false;manual.focus();manual.select();
    }finally{button.removeAttribute('aria-busy');copyTimers.set(button,setTimeout(()=>{delete button.dataset.copyState;button.setAttribute('aria-label',original);button.dataset.tooltip=original;const glyph=button.querySelector('svg use');if(glyph)glyph.setAttribute('href','/icons.svg#copy');},2200));}
  }
  document.addEventListener('click',event=>{
    const button=event.target.closest('button[data-value-copy],button[data-copy],button[data-order-copy],button[data-copy-node]');if(!button)return;
    event.preventDefault();event.stopImmediatePropagation();const value=button.dataset.valueCopy?valueText(button.parentElement):button.dataset.copy??button.dataset.orderCopy??valueText(button.closest('.tx-section').querySelector('pre'));copy(value,button);
  },true);
  document.addEventListener('pointerdown',event=>{
    if(event.button!==0||document.querySelector('dialog[open]')||event.target.closest('.select-menu,.tx-small-menu,.tx-query-menu,#ui-copy-feedback'))return;
    const panes=[...document.querySelectorAll('.tx-peek')].filter(pane=>!pane.hidden&&pane.getClientRects().length);
    if(!panes.length)return;
    const focused=document.activeElement?.closest('.tx-peek');
    const top=panes.includes(focused)?focused:panes.map((pane,index)=>({pane,index,z:Number(getComputedStyle(pane).zIndex)||0})).sort((a,b)=>a.z-b.z||a.index-b.index).at(-1).pane;
    if(top.contains(event.target))return;
    top.querySelector('[data-close],[data-order-close],[data-service-close],[data-ui-close],#close-run-detail')?.click();
  },true);
  document.addEventListener('click',event=>{
    const row=event.target.closest('.ui-sample-list .tx-node-select');if(!row)return;
    row.closest('.ui-sample-list').querySelectorAll('.tx-node-select').forEach(item=>{item.classList.toggle('is-selected',item===row);item.setAttribute('aria-pressed',String(item===row));});
  });
  // Animate deliberate view changes only; polling and query typing stay stable.
  const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
  const contentMotions=new Map();
  reducedMotion.addEventListener('change',()=>{
    if(reducedMotion.matches){contentMotions.forEach(animation=>animation.cancel());contentMotions.clear();}
  });
  const motionTargets=[
    ['[data-tab]','#tx-node-body'],
    ['[data-span],[data-root-span]','#tx-node-body'],
    ['[data-order-tab]','#tx-order-node-body'],
    ['[data-order-node]','#tx-order-node-body'],
    ['[data-order-view]','#tx-order-tree'],
    ['[data-waterfall]','#tx-tree'],
    ['[data-workspace-view]','#tx-orders-layout:not([hidden]),#workspace-traces .tx-layout:not([hidden])'],
    ['[data-monitor-tab]','[data-monitor-panel]:not([hidden])'],
    ['[data-detail-tab]','[data-detail-view]:not([hidden])'],
    ['[data-chart-category]','#environment-charts:not([hidden]),#ui-metric-table:not([hidden])'],
    ['.side-nav a','[data-workspace-page]:not([hidden])'],
  ];
  document.addEventListener('click',event=>{
    if(reducedMotion.matches)return;
    const match=motionTargets.find(([selector])=>event.target.closest(selector));
    if(!match)return;
    const control=event.target.closest(match[0]);
    if(control.disabled || (control.getAttribute('aria-pressed')==='true' && !control.matches('[data-waterfall]')))return;
    requestAnimationFrame(()=>{
      if(reducedMotion.matches)return;
      document.querySelectorAll(match[1]).forEach(element=>{
        if(!element.getClientRects().length || !element.animate)return;
        contentMotions.get(element)?.cancel();
        // Transforming a page containing fixed drawers would change their containing block.
        const frames=element.querySelector('.tx-peek')?[{opacity:.65},{opacity:1}]:
          [{opacity:.65,transform:'translateY(3px)'},{opacity:1,transform:'translateY(0)'}];
        const animation=element.animate(frames,
          {duration:160,easing:'cubic-bezier(.2,.8,.2,1)'});
        contentMotions.set(element,animation);
        const cleanup=()=>{if(contentMotions.get(element)===animation)contentMotions.delete(element);};
        animation.onfinish=cleanup;animation.oncancel=cleanup;
      });
    });
  },true);
  function enhance(container = document) {
    copyValues(container);
    actionButtons(container);
    const titled = [...container.querySelectorAll('[title]')];
    if (container.matches?.('[title]')) titled.unshift(container);
    titled.forEach(element => {
      element.dataset.tooltip = element.getAttribute('title'); element.removeAttribute('title');
      if (!element.hasAttribute('aria-label')) element.setAttribute('aria-label',element.dataset.tooltip);
    });
    container.querySelectorAll('select').forEach(select);
    container.querySelectorAll('.custom-select').forEach(bind);
    container.querySelectorAll('form').forEach(form => {form.noValidate = true;});
    container.querySelectorAll('input[type="checkbox"]').forEach(field => {
      if (field.closest('.switch-row,.confirm-row,.ui-check-control')) return;
      const root = document.createElement('span'); root.className = 'ui-check-control';
      field.before(root); root.append(field); root.insertAdjacentHTML('beforeend',icon('check'));
      field.closest('label')?.classList.add('ui-check-label');
    });
    container.querySelectorAll('summary').forEach(summary => {
      if (!summary.querySelector('.disclosure-icon')) summary.insertAdjacentHTML('afterbegin',`<span class="disclosure-icon">${icon('caret-right')}</span>`);
    });
  }
  document.addEventListener('click', event => {if (!event.target.closest('.custom-select')) close();});
  document.addEventListener('invalid', event => {event.preventDefault(); showError(event.target);},true);
  document.addEventListener('submit', event => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (!form.checkValidity()) {
      event.preventDefault(); event.stopImmediatePropagation();
      const invalid = [...form.elements].find(field => field.validity && !field.validity.valid);
      (selections.get(invalid)?.trigger || invalid)?.focus();
    }
  },true);
  for (const event of ['input','change']) document.addEventListener(event, event => clearError(event.target));
  document.addEventListener('reset', event => queueMicrotask(() => {
    event.target.querySelectorAll('select').forEach(field => selections.get(field)?.sync());
    event.target.querySelectorAll('[aria-invalid]').forEach(clearError);
  }));
  window.addEventListener('popstate', () => close());
  window.addEventListener('hashchange', () => close());
  new MutationObserver(records => {
    for(const record of records)if(record.target.nodeType===Node.ELEMENT_NODE&&record.target.matches(copySelector)&&[...record.addedNodes].some(n=>n.nodeType===Node.TEXT_NODE))copyValues(record.target);
    for (const record of records) for (const node of record.addedNodes) {
      if (node.nodeType === Node.ELEMENT_NODE) {
        if (node.matches('summary')) enhance(node.parentElement);
        else if (node.matches('select')) select(node);
        else if (node.matches('button,[title],'+copySelector) || node.querySelector('button,select,summary,[title],'+copySelector)) enhance(node);
      }
    }
  }).observe(document.documentElement,{childList:true,subtree:true});
  return {enhance,close,icon,copy,syncSelect:field=>selections.get(field)?.sync()};
})();

// Cross-workspace investigation keeps a bounded return trail across reloads.
window.investigationNavigation = (() => {
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const key='seckill.investigation.trail';
  function read(){try{const frames=JSON.parse(sessionStorage.getItem(key)||'[]');return Array.isArray(frames)?frames.filter(frame=>frame&&new URL(frame.url).origin===location.origin).slice(-8):[];}catch{return [];}}
  function save(stack){try{sessionStorage.setItem(key,JSON.stringify(stack.slice(-8)));}catch{}}
  function sameLocation(a,b){const left=new URL(a),right=new URL(b);left.searchParams.sort();right.searchParams.sort();return left.href===right.href;}
  function action(label,target,icon='arrow-square-out'){return `<button type="button" class="ui-investigation-link" data-investigate="${esc(JSON.stringify(target))}" aria-label="${esc(label)}">${window.workspaceControls.icon(icon)}<span>${esc(label)}</span></button>`;}
  function range(at,seconds=1800){const now=Math.floor(Date.now()/1000),center=Number(at)||now;return {start:Math.max(1,Math.floor(center-seconds)),end:Math.min(now,Math.ceil(center+seconds))};}
  function traceRange(){const snapshot=window.traceControls.snapshot(),now=Math.floor(Date.now()/1000);if(snapshot.range==='custom')return {start:Number(snapshot.start),end:Number(snapshot.end)};const match=snapshot.range.match(/^(\d+)(m|h|d)$/);return {start:now-(match?Number(match[1])*({m:60,h:3600,d:86400})[match[2]]:30*86400),end:now};}
  function context(data){
    const time=data.start&&data.end?{start:data.start,end:data.end}:range(data.at);
    const links=[];
    if(data.order_id)links.push(action('查看关联订单',{page:'traces',order_id:data.order_id,...time}));
    if(data.trace_id)links.push(action('查看关联 Trace',{page:'traces',trace_id:data.trace_id,span_id:data.span_id,...time}));
    if(data.event_id){links.push(action('查看事件执行',{page:'traces',event_id:data.event_id,...time}));links.push(action('查看后续事件执行',{page:'traces',causation_id:data.event_id,...time}));}
    if(data.causation_id)links.push(action('查看来源事件执行',{page:'traces',event_id:data.causation_id,...time}));
    if(data.request_id)links.push(action('查看请求执行',{page:'traces',request_id:data.request_id,...time}));
    if(data.service){links.push(action('查看服务 Traces',{page:'traces',service:data.service,...time}));links.push(action('查看服务日志',{page:'logs',service:data.service,...time}));links.push(action('查看服务监控',{page:'monitoring',service:data.service,...time}));}
    return `<nav class="ui-investigation-actions" aria-label="关联调查">${links.join('')||'<span class="tx-no-data">未采集可跳转的关联标识。</span>'}</nav>`;
  }
  function navigate(target){
    const url=new URL(location.origin+'/');
    const start=Math.floor(Number(target.start)),end=Math.floor(Number(target.end));
    const validRange=start>0&&end>start;
    if(target.page==='logs'){
      const filters=new URLSearchParams();
      for(const field of ['service','trace_id','order_id','event_id','request_id','level'])if(target[field])filters.set(field,target[field]);
      if(validRange){filters.set('start',start);filters.set('end',end);filters.set('window','60');}
      else if(target.at)filters.set('at',Math.floor(target.at));
      url.searchParams.set('log_filters',filters.toString());url.hash='logs';
    }else if(target.page==='monitoring'){
      if(target.service)url.searchParams.set('monitor_query',target.service);
      if(validRange){url.searchParams.set('monitor_start',start);url.searchParams.set('monitor_end',end);}
      url.hash='monitoring';
    }else{
      url.hash='traces';url.searchParams.set('trace_view',target.order_id?'orders':'traces');
      url.searchParams.set('trace_range',validRange?'custom':'7d');
      if(validRange){url.searchParams.set('trace_start',start);url.searchParams.set('trace_end',end);}
      if(target.order_id){url.searchParams.set('trace_order',target.order_id);url.searchParams.set('orders_query','order_id:'+target.order_id);}
      else if(target.trace_id){url.searchParams.set('trace',target.trace_id);if(target.span_id)url.searchParams.set('span',target.span_id);}
      else{const query=target.query||[['service',target.service],['event_id',target.event_id],['causation_id',target.causation_id],['request_id',target.request_id]].filter(([,v])=>v).map(([k,v])=>k+':'+JSON.stringify(String(v))).join(' ');if(query)url.searchParams.set('trace_query',query);url.searchParams.set('trace_query_scope','all');if(target.errors)url.searchParams.set('trace_filters',JSON.stringify([['errors','on']]));}
    }
    const scroll=[...document.querySelectorAll('[id]')].filter(el=>el.scrollTop||el.scrollLeft).map(el=>[el.id,el.scrollTop,el.scrollLeft]);
    const stack=read();stack.push({url:location.href,label:({logs:'日志调查',monitoring:'监控调查',traces:'链路调查',runs:'压测报告'})[location.hash.slice(1)]||'原调查',scroll});save(stack);location.assign(url.href);
  }
  document.addEventListener('click',event=>{const button=event.target.closest('[data-investigate]');if(!button)return;event.preventDefault();event.stopImmediatePropagation();try{navigate(JSON.parse(button.dataset.investigate));}catch{}},true);
  document.addEventListener('DOMContentLoaded',()=>{
    const stack=read();let frame=stack.at(-1);if(!frame)return;
    const url=new URL(location.href),returning=url.searchParams.get('investigation_return')==='1';if(returning){url.searchParams.delete('investigation_return');history.replaceState(null,'',url);}
    if(returning||sameLocation(frame.url,location.href)){const restored=frame;stack.pop();save(stack);let attempts=0;const timer=setInterval(()=>{for(const [id,top,left] of restored.scroll||[]){const el=document.getElementById(id);if(el){el.scrollTop=top;el.scrollLeft=left;}}if(++attempts===30)clearInterval(timer);},200);frame=stack.at(-1);if(!frame)return;}
    const page=document.querySelector('#workspace-'+location.hash.slice(1));if(!page)return;
    const bar=document.createElement('div');bar.className='ui-investigation-return';bar.innerHTML=`<button type="button" class="ui-investigation-link" aria-label="返回${esc(frame.label)}">${window.workspaceControls.icon('arrow-left')}<span>返回${esc(frame.label)}</span></button><span>保留原筛选与所选记录</span>`;page.prepend(bar);bar.querySelector('button').onclick=()=>{const url=new URL(frame.url);url.searchParams.set('investigation_return','1');location.assign(url);};window.workspaceControls.enhance(bar);
  });
  return {action,navigate,range,traceRange,context};
})();
