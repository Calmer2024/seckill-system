// LangSmith-style query and time popovers, backed by the existing Tempo facade.
window.traceControls = (() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  const icon = name => `<svg aria-hidden="true"><use href="/icons.svg#${name}"></use></svg>`;
  const $ = s => document.querySelector(s);
  const presets = [['1h','Last 1 hour'],['3h','Last 3 hours'],['6h','Last 6 hours'],['12h','Last 12 hours'],['1d','Last 1 day'],['2d','Last 2 days'],['7d','Last 7 days'],['14d','Last 14 days'],['30d','Last 30 days'],['all','All time']];
  const fields = [['Run attributes', [['name','名称 / 入口'],['service','服务'],['status','原始 Span 状态（不等于业务结果）'],['version','服务版本'],['instance','服务实例']]],['Content',[['method','HTTP 方法'],['route','路由'],['db_system','数据库类型'],['topic','消息主题'],['outcome','业务执行结果'],['business_state','已观测业务状态'],['error','业务错误代码']]],['Identity',[['trace_id','Trace ID'],['request_id','Request ID'],['order_id','订单 ID'],['product_id','商品 ID'],['campaign_id','活动 ID（若业务提供）'],['event_id','消息事件 ID'],['causation_id','来源事件 ID']]]];
  let range='7d', start='', end='', defaultRange='1d', onSearch, onOpen, menuIndex=0, syncing=false;
  function stored(key,fallback) {try{return JSON.parse(localStorage.getItem(key)) ?? fallback;}catch{return fallback;}}
  function save(key,value){try{localStorage.setItem(key,JSON.stringify(value));return true;}catch{return false;}}
  function validateQuery(query){
    if(query.length>512)return '查询最多 512 个字符。';
    if(/[\x00-\x1f]/.test(query))return '查询不能包含换行或控制字符。';
    const tokens=[];let token='',quote='',escape=false;
    for(const c of query){if(escape){token+=c;escape=false;}else if(c==='\\'&&quote!=="'"){escape=true;}else if(quote){if(c===quote)quote='';else token+=c;}else if(c==='"'||c==="'")quote=c;else if(/\s/.test(c)){if(token){tokens.push(token);token='';}}else token+=c;}
    if(quote||escape)return '引号或转义未闭合，例如 name:"POST /api/orders"。';
    if(token)tokens.push(token);
    if(tokens.length>16)return '最多组合 16 个查询条件。';
    const allowed=fields.flatMap(([,items])=>items.map(([name])=>name));
    for(const item of tokens){if(!item.includes(':'))continue;const index=item.indexOf(':'),key=item.slice(0,index).replace(/^-/,'');const value=item.slice(index+1);
      if(!allowed.includes(key))return `不支持字段 ${key}，请从字段建议中选择。`;
      if(!value)return `${key} 缺少值，例如 ${key==='status'?'status:error':key==='name'?'name:"POST /api/orders"':key+':value'}。`;
      if(value.length>160)return `${key} 的值最多 160 个字符。`;
      if(key==='status'&&!['error','ok','unset'].includes(value))return 'status 支持 error、ok、unset。';
      if(key==='trace_id'&&!/^[0-9a-fA-F]{32}$/.test(value))return 'trace_id 应为 32 位十六进制 ID。';
      if(key==='service'&&!['user','product','order-api','inventory-api','order-worker','inventory-worker'].includes(value))return 'service 请使用筛选区列出的服务名称。';
      if(['order_id','product_id','campaign_id'].includes(key)&&(!/^[1-9][0-9]{0,18}$/.test(value)||BigInt(value)>9223372036854775807n))return `${key} 应为有效的正整数 ID。`;
      if(key==='event_id'&&!/^[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}$/.test(value))return 'event_id 应为 UUID。';
    }
    return '';
  }
  function showQueryError(message){const target=$('#tx-query-error');target.hidden=!message;target.textContent=message;$('#tx-query').setAttribute('aria-invalid',String(Boolean(message)));}
  function validRelative(value){const m=/^([1-9][0-9]{0,4})(m|h|d)$/.exec(value);return m && Number(m[1])*({m:60,h:3600,d:86400}[m[2]])<=2592000;}
  function label(){if(range==='custom')return `${new Date(Number(start)*1000).toLocaleDateString('zh-CN')} – ${new Date(Number(end)*1000).toLocaleDateString('zh-CN')}`;return presets.find(p=>p[0]===range)?.[1]||`Last ${range}`;}
  function setRange(value){range=value;$('#tx-time-label').textContent=label();$('#tx-time-label').title=range==='custom'?`${new Date(Number(start)*1000).toLocaleString('zh-CN')} – ${new Date(Number(end)*1000).toLocaleString('zh-CN')}`:label();}
  function closeTime(focus=false){$('#tx-time-menu').hidden=true;$('#tx-time-button').setAttribute('aria-expanded','false');if(focus)$('#tx-time-button').focus();}
  function timeMenu(){
    $('#tx-time-menu').innerHTML=`<form id="tx-relative-form" class="tx-relative-form"><label>${icon('hourglass')}<input id="tx-relative" aria-label="Relative time" placeholder="Relative time (Ex: 15h, 1d)" maxlength="6"></label></form><div class="tx-time-presets" role="group" aria-label="时间范围">${presets.map(([value,text])=>`<div class="tx-time-option ${range===value?'is-selected':''}"><button type="button" role="menuitemradio" aria-checked="${range===value}" data-range="${value}"><span>${text}</span><small>${value==='all'?'':value}</small></button>${defaultRange===value?'<span class="tx-default-label">Default</span>':`<button type="button" class="tx-set-default" data-default="${value}">Set as default</button>`}</div>`).join('')}</div><button type="button" class="tx-choose-dates" data-choose-dates>${icon('calendar')}<span>Choose dates</span>${icon('caret-right')}</button><p id="tx-time-error" class="tx-control-error" role="alert"></p>`;
    $('#tx-relative-form').onsubmit=e=>{e.preventDefault();const value=$('#tx-relative').value.trim();if(!validRelative(value)){$('#tx-time-error').textContent='请输入 1m 至 30d 的相对时间，例如 15h、1d。';return;}setRange(value);closeTime(true);onSearch();};
  }
  function datesMenu(){
    const local = seconds=>{const date=new Date(Number(seconds)*1000);return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16);};
    $('#tx-time-menu').innerHTML=`<form id="tx-dates-form" class="tx-dates-form"><button type="button" class="tx-text-button" data-time-back>${icon('caret-right')}时间范围</button><label>开始时间<span class="tx-date-field"><input type="datetime-local" name="start" value="${local(start||Date.now()/1000-86400)}" required><button type="button" data-calendar="start" aria-label="选择开始日期">${icon('calendar')}</button></span></label><label>结束时间<span class="tx-date-field"><input type="datetime-local" name="end" value="${local(end||Date.now()/1000)}" required><button type="button" data-calendar="end" aria-label="选择结束日期">${icon('calendar')}</button></span></label><div id="tx-calendar" hidden></div><p>本地时间 · ${esc(Intl.DateTimeFormat().resolvedOptions().timeZone)}</p><p id="tx-time-error" class="tx-control-error" role="alert"></p><button class="button button-primary" type="submit">应用日期范围</button></form>`;
    $('#tx-dates-form').onsubmit=e=>{e.preventDefault();const form=e.target;if(!form.checkValidity())return;const a=Math.floor(new Date(form.elements.start.value).getTime()/1000),b=Math.floor(new Date(form.elements.end.value).getTime()/1000);if(!Number.isFinite(a)||!Number.isFinite(b)||a<=0||a>=b||b>Date.now()/1000+60){$('#tx-time-error').textContent='开始时间应早于结束时间，结束时间不能晚于当前时间。';return;}start=String(a);end=String(b);setRange('custom');closeTime(true);onSearch();};
  }
  function calendar(field,year,month){
    const input=$('#tx-dates-form').elements[field],date=new Date(input.value||Date.now());
    const base=year===undefined?new Date(date.getFullYear(),date.getMonth(),1):new Date(year,month,1),y=base.getFullYear(),m=base.getMonth(),first=new Date(y,m,1).getDay(),count=new Date(y,m+1,0).getDate(),today=new Date();today.setHours(23,59,59,999);
    const target=$('#tx-calendar');target.hidden=false;
    target.innerHTML=`<div class="tx-calendar-heading"><button type="button" data-month="-1" aria-label="上个月">${icon('arrow-left')}</button><strong>${y}年 ${m+1}月</strong><button type="button" data-month="1" aria-label="下个月">${icon('arrow-right')}</button><button type="button" data-calendar-close aria-label="关闭日历">${icon('x')}</button></div><div class="tx-calendar-grid" role="group" aria-label="选择日期">${['日','一','二','三','四','五','六'].map(day=>`<span>${day}</span>`).join('')}${Array.from({length:first},()=>'<span></span>').join('')}${Array.from({length:count},(_,i)=>{const d=i+1,selected=y===date.getFullYear()&&m===date.getMonth()&&d===date.getDate();return `<button type="button" data-day="${d}" aria-label="${y}年${m+1}月${d}日" aria-pressed="${selected}" ${new Date(y,m,d)>today?'disabled':''}>${d}</button>`;}).join('')}</div>`;
    target.onclick=e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.month){calendar(field,y,m+Number(b.dataset.month));return;}if(b.dataset.day){input.value=`${y}-${String(m+1).padStart(2,'0')}-${String(b.dataset.day).padStart(2,'0')}T${input.value.slice(11)||'00:00'}`;input.dispatchEvent(new Event('change',{bubbles:true}));target.hidden=true;input.focus();}if(b.hasAttribute('data-calendar-close')){target.hidden=true;input.focus();}};
    target.onkeydown=e=>{if(e.key==='Escape'){e.preventDefault();e.stopPropagation();target.hidden=true;input.focus();}if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key)&&e.target.dataset.day){e.preventDefault();const day=Number(e.target.dataset.day)+({ArrowLeft:-1,ArrowRight:1,ArrowUp:-7,ArrowDown:7}[e.key]);target.querySelector(`[data-day="${day}"]:not(:disabled)`)?.focus();}};
    (target.querySelector('[aria-pressed=true]:not(:disabled)')||target.querySelector('[data-day]:not(:disabled)'))?.focus();
  }
  function currentToken(){const input=$('#tx-query'),before=input.value.slice(0,input.selectionStart);return {prefix:before.replace(/\S*$/,''),token:before.match(/\S*$/)?.[0]||'',suffix:input.value.slice(input.selectionStart)};}
  function suggestions(){
    const {token}=currentToken(), menu=$('#tx-query-menu');menuIndex=0;
    const match=/^(-?)([a-z_]+):$/.exec(token);
    if(match){menu.innerHTML=`<div class="tx-query-options"><h4>Comparison operators</h4><button type="button" role="option" data-operator="equals"><code>equals</code><kbd>foo:bar</kbd></button><button type="button" role="option" data-operator="not"><code>not equals</code><kbd>-foo:bar</kbd></button></div><footer><span><kbd>${icon('arrow-up')}</kbd> <kbd>${icon('arrow-down')}</kbd> Navigate <kbd>${icon('arrow-elbow-down-left')}</kbd> Select</span></footer>`;}
    else if(token.includes(':')){menu.hidden=true;$('#tx-query').setAttribute('aria-expanded','false');return;}
    else {const needle=token.replace(/^-/,'').toLowerCase();menu.innerHTML=`<div class="tx-query-options">${fields.map(([group,items])=>{const visible=items.filter(([name,desc])=>name.includes(needle)||desc.includes(needle));return visible.length?`<h4>${group}</h4>${visible.map(([name,desc])=>`<button type="button" role="option" data-query-field="${name}"><span class="tx-field-icon">${icon(group==='Identity'?'hash':group==='Content'?'brackets-curly':'tree-structure')}</span><span>${name}</span><small>${desc}</small></button>`).join('')}`:'';}).join('')}</div><footer><span><kbd>${icon('arrow-up')}</kbd> <kbd>${icon('arrow-down')}</kbd> Navigate <kbd>${icon('arrow-elbow-down-left')}</kbd> Select</span><span>field:value · -field:value</span></footer>`;}
    menu.hidden=!menu.querySelector('[role=option]');$('#tx-query').setAttribute('aria-expanded',String(!menu.hidden));highlight();
  }
  function highlight(){const options=[...$('#tx-query-menu').querySelectorAll('[role=option]')];options.forEach((o,i)=>{o.classList.toggle('is-active',i===menuIndex);o.setAttribute('aria-selected',String(i===menuIndex));o.id=`tx-query-option-${i}`;});if(options[menuIndex]){$('#tx-query').setAttribute('aria-activedescendant',options[menuIndex].id);options[menuIndex].scrollIntoView({block:'nearest'});}}
  function chooseSuggestion(button){
    const input=$('#tx-query'),{prefix,token,suffix}=currentToken();
    if(button.dataset.queryField){input.value=prefix+button.dataset.queryField+':'+suffix;input.focus();input.setSelectionRange((prefix+button.dataset.queryField+':').length,(prefix+button.dataset.queryField+':').length);suggestions();}
    else {input.value=prefix+(button.dataset.operator==='not'?'-':'')+token.replace(/^-/,'')+suffix;input.focus();$('#tx-query-menu').hidden=true;input.setAttribute('aria-expanded','false');}
  }
  function submit(){const query=$('#tx-query').value.trim();$('#tx-query-menu').hidden=true;$('#tx-query').setAttribute('aria-expanded','false');if(/^[0-9a-fA-F]{32}$/.test(query)){onOpen(query.toLowerCase());return;}onSearch();}
  function mount(search,open){
    onSearch=search;onOpen=open;
    defaultRange=stored('seckill.trace.defaultRange','1d');if(defaultRange!=='all'&&!validRelative(defaultRange))defaultRange='1d';
    const params=new URLSearchParams(location.search),requested=params.get('trace_range');range=requested&&(requested==='all'||requested==='custom'||validRelative(requested))?requested:defaultRange;
    start=params.get('trace_start')||'';end=params.get('trace_end')||'';if(range==='custom'&&(!/^\d+$/.test(start)||!/^\d+$/.test(end)))range=defaultRange;
    $('#tx-query').value=params.get('trace_query')||'';$('#tx-query-scope').value=params.get('trace_query_scope')==='all'?'all':'root';setRange(range);
    $('#trace-lookup').onsubmit=e=>{e.preventDefault();submit();};
    $('#tx-query').addEventListener('focus',suggestions);$('#tx-query').addEventListener('input',()=>{showQueryError('');suggestions();});
    $('#tx-query').addEventListener('keydown',e=>{const menu=$('#tx-query-menu');if(e.key==='Escape'){menu.hidden=true;e.stopPropagation();$('#tx-query').setAttribute('aria-expanded','false');return;}if(e.key==='Enter'&&(e.ctrlKey||e.metaKey||!$('#tx-query').value.trim())){e.preventDefault();submit();return;}if(menu.hidden)return;const options=[...menu.querySelectorAll('[role=option]')];if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();menuIndex=(menuIndex+(e.key==='ArrowDown'?1:-1)+options.length)%options.length;highlight();}if(e.key==='Enter'&&options[menuIndex]){e.preventDefault();chooseSuggestion(options[menuIndex]);}if(e.key==='Tab'){menu.hidden=true;$('#tx-query').setAttribute('aria-expanded','false');}});
    $('#tx-query-menu').addEventListener('mousedown',e=>e.preventDefault());$('#tx-query-menu').addEventListener('click',e=>{const b=e.target.closest('[role=option]');if(b)chooseSuggestion(b);});
    $('#tx-add-filter').onclick=()=>{$('#tx-query').focus();suggestions();};
    $('#tx-time-button').onclick=()=>{const menu=$('#tx-time-menu'),show=menu.hidden;menu.hidden=!show;$('#tx-time-button').setAttribute('aria-expanded',String(show));if(show){timeMenu();menu.querySelector('[data-range="'+range+'"]')?.focus();}};
    $('#tx-time-menu').addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.range){setRange(b.dataset.range);closeTime(true);onSearch();}if(b.dataset.default){defaultRange=b.dataset.default;if(save('seckill.trace.defaultRange',defaultRange)){timeMenu();}else $('#tx-time-error').textContent='无法保存默认时间。';}if(b.dataset.calendar)calendar(b.dataset.calendar);if(b.hasAttribute('data-choose-dates'))datesMenu();if(b.hasAttribute('data-time-back'))timeMenu();});
    $('#tx-time-menu').addEventListener('keydown',e=>{if(e.key==='Escape'){e.stopPropagation();closeTime(true);}if(e.key==='ArrowDown'||e.key==='ArrowUp'){const items=[...$('#tx-time-menu').querySelectorAll('[data-range],[data-choose-dates]')],index=items.indexOf(document.activeElement);if(index>=0){e.preventDefault();items[(index+(e.key==='ArrowDown'?1:-1)+items.length)%items.length].focus();}}});
    document.addEventListener('pointerdown',e=>{if(!e.target.closest('.tx-time-control'))closeTime();if(!e.target.closest('.tx-search')){$('#tx-query-menu').hidden=true;$('#tx-query').setAttribute('aria-expanded','false');}});
    $('#tx-query-scope').onchange=()=>{if(!syncing&&$('#tx-query').value.trim())onSearch();};
  }
  function params(){const error=validateQuery($('#tx-query').value.trim());showQueryError(error);if(error)return null;const p=new URLSearchParams({window:range,query:$('#tx-query').value.trim(),query_scope:$('#tx-query-scope').value});if(range==='custom'){p.set('start',start);p.set('end',end);}return p;}
  function persist(){const url=new URL(location.href);url.searchParams.set('trace_range',range);url.searchParams.set('trace_query_scope',$('#tx-query-scope').value);for(const key of ['trace_start','trace_end','trace_query'])url.searchParams.delete(key);if(range==='custom'){url.searchParams.set('trace_start',start);url.searchParams.set('trace_end',end);}if($('#tx-query').value.trim())url.searchParams.set('trace_query',$('#tx-query').value.trim());history.replaceState(null,'',url);}
  function reset(){start='';end='';setRange(defaultRange);$('#tx-query').value='';$('#tx-query-scope').value='root';$('#tx-query-scope').dispatchEvent(new Event('change'));showQueryError('');closeTime();}
  function snapshot(){return {range,start,end,query:$('#tx-query').value,scope:$('#tx-query-scope').value};}
  function restore(s){range=s.range==='all'||s.range==='custom'||validRelative(s.range)?s.range:defaultRange;start=s.start||'';end=s.end||'';$('#tx-query').value=s.query||'';$('#tx-query-scope').value=s.scope==='all'?'all':'root';syncing=true;$('#tx-query-scope').dispatchEvent(new Event('change'));syncing=false;setRange(range);}
  return {mount,params,persist,reset,label,snapshot,restore};
})();
