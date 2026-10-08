function workspaceIcon(name) {
  return '<svg aria-hidden="true"><use href="/icons.svg#' + name + '"></use></svg>';
}

function workspaceFilter(name, label) {
  return '<label class="filter-field"><span>' + label + '</span><span class="custom-select filter-select" data-select="filter-' + name + '">' +
    '<input id="run-' + name + '" type="hidden">' +
    '<button class="select-trigger" type="button" aria-haspopup="listbox" aria-expanded="false" aria-label="' + label + '">' +
    '<span>全部' + label + '</span>' + workspaceIcon('caret-down') + '</button>' +
    '<span class="select-menu" role="listbox" hidden></span></span></label>';
}

function mountWorkspace() {
  const main = document.querySelector('.page-shell');
  const toast = main.querySelector('#toast');
  const nodes = {
    strip: main.querySelector('.overview-strip'),
    form: main.querySelector('.control-panel'),
    active: main.querySelector('.active-panel'),
    history: main.querySelector('.history-panel'),
    report: main.querySelector('.report-panel'),
    observability: main.querySelector('#observability'),
    monitoring: main.querySelector('#monitoring'),
    eval: main.querySelector('#eval'),
  };

  document.querySelector('.brand').href = '#runs';
  document.querySelector('.side-nav').innerHTML =
    '<a class="is-current" data-nav="runs" href="#runs" aria-current="page">' +
      workspaceIcon('chart-line-up') + '<span>压测</span></a>' +
    '<a data-nav="monitoring" href="#monitoring">' + workspaceIcon('pulse') + '<span>监控</span></a>' +
    '<a data-nav="traces" href="#traces">' + workspaceIcon('magnifying-glass') + '<span>Trace</span></a>' +
    '<a data-nav="logs" href="#logs">' + workspaceIcon('file-text') + '<span>日志</span></a>';
  document.querySelector('.top-actions').remove();
  document.querySelector('#current-location').textContent = '压测';
  nodes.strip.querySelector('.overview-link').remove();
  nodes.form.querySelector('h2').textContent = '压测配置';
  nodes.history.querySelector('h2').textContent = '运行记录';
  nodes.active.querySelector('h2').textContent = '运行过程';
  nodes.report.querySelector('h2').textContent = '压测报告';
  nodes.report.querySelector('.section-index').textContent = '报告';
  nodes.observability.querySelector('h2').textContent = '指标快照';
  nodes.monitoring.querySelector('h2').textContent = '监控服务';
  nodes.monitoring.insertAdjacentHTML('afterbegin',
    '<section class="p0-observability" aria-labelledby="p0-observability-title">' +
      '<div class="p0-heading"><div><h2 id="p0-observability-title">环境当前状态</h2>' +
      '<p>服务与后台任务的实时采集状态。</p></div>' +
      '<button id="refresh-observability" class="button button-quiet" type="button">刷新状态</button></div>' +
      '<p id="p0-source" class="domain-note" aria-live="polite">尚未查询 Prometheus。</p>' +
      '<div id="p0-capabilities" class="p0-capabilities"></div>' +
      '<div class="table-wrap"><table class="p0-status-table"><thead><tr><th>服务 / 实例</th><th>状态</th><th>后台任务</th><th>轮询 / 业务进度</th><th>异常退出</th></tr></thead>' +
      '<tbody id="p0-service-status"><tr><td colspan="5" class="table-empty">正在查询服务状态。</td></tr></tbody></table></div>' +
      '<p class="domain-note">成功的空闲轮询也会更新健康时间；没有业务进度不代表线程故障。</p>' +
    '</section>'
  );
  nodes.eval.querySelector('h2').textContent = '业务一致性';
  nodes.eval.querySelector('.domain-note').textContent = '此处只展示当前压测报告内的一致性规则。';
  nodes.history.querySelector('.table-wrap').outerHTML = '<div class="tx-table-scroll"><table class="tx-table"><thead><tr><th>状态</th><th>Name</th><th>Run ID</th><th>Mode</th><th>Start Time</th><th>Report</th></tr></thead><tbody id="runs-body"></tbody></table></div>';
  nodes.history.querySelector('.panel-heading').remove();
  nodes.monitoring.querySelectorAll('.tool-icon').forEach((item, index) => {
    item.innerHTML = workspaceIcon(index === 0 ? 'chart-line-up' : 'pulse');
  });

  main.replaceChildren(toast);
  main.id = 'main-content';
  main.tabIndex = -1;
  main.insertAdjacentHTML('beforeend',
    '<div class="workspace-heading"><div><p class="eyebrow">PERFORMANCE</p><h1>压测</h1><p>查看运行记录与报告，或启动新任务。</p></div>' +
      '<button id="open-new-run" class="button button-primary" type="button">' + workspaceIcon('plus') + '新建任务</button></div>' +
    '<div data-slot="strip"></div>' +
    '<div class="performance-layout">' +
      '<section class="runs-pane" aria-label="压测运行列表">' +
        '<div class="runs-pane-header"><div><span class="section-index">运行记录</span><h2>压测列表</h2></div><span id="run-filter-count" class="filter-count"></span></div>' +
        '<div class="list-toolbar"><label class="search-field"><span>搜索任务或场景</span><span class="search-control">' +
          workspaceIcon('magnifying-glass') + '<input id="run-search" type="text" autocomplete="off" placeholder="任务编号、场景"></span></label>' +
          workspaceFilter('status', '状态') + workspaceFilter('scenario', '场景') + workspaceFilter('mode', '模式') +
          '<button id="clear-run-filters" class="clear-filters" type="button" hidden>清除筛选</button></div>' +
        '<div data-slot="history"></div>' +
      '</section>' +
      '<section class="detail-pane" aria-label="压测报告详情">' +
        '<div id="detail-placeholder" class="detail-placeholder"><span class="placeholder-icon">' + workspaceIcon('file-text') +
          '</span><h2>选择一条压测记录</h2><p>报告、指标、业务校验和运行日志将在这里显示。</p></div>' +
        '<div id="detail-body" hidden>' +
          '<div class="detail-heading"><div><span class="section-index">压测结果</span><h2 id="run-title">任务详情</h2><p id="run-subtitle"></p></div>' +
            '<span id="run-context-status" class="status-badge"></span></div>' +
          '<div class="resource-context"><span>任务 ID <strong id="run-context-id"></strong></span><span>场景 <strong id="run-context-scenario"></strong></span></div>' +
          '<nav class="resource-tabs" aria-label="压测详情视角">' +
            '<button type="button" data-detail-tab="report">报告</button>' +
            '<button type="button" data-detail-tab="metrics">压测指标</button>' +
            '<button type="button" data-detail-tab="validation">业务校验</button>' +
            '<button type="button" data-detail-tab="run">运行日志</button></nav>' +
          '<div data-detail-view="report" data-slot="report"></div>' +
          '<div data-detail-view="metrics"><div class="scope-note">任务 <strong id="observability-run-id"></strong></div><div data-slot="observability"></div></div>' +
          '<div data-detail-view="validation"><div class="scope-note">任务 <strong id="eval-run-id"></strong></div><div data-slot="eval"></div></div>' +
          '<div data-detail-view="run" data-slot="active"></div>' +
        '</div>' +
      '</section>' +
    '</div>' +
    '<dialog id="new-run-dialog" class="new-run-dialog" aria-labelledby="new-run-dialog-title">' +
      '<div class="dialog-heading"><div><span class="section-index">新建压测</span><h2 id="new-run-dialog-title">配置运行任务</h2></div>' +
        '<button id="close-new-run" class="icon-button" type="button" aria-label="关闭新建任务弹窗">' + workspaceIcon('x') + '</button></div>' +
      '<div class="config-layout"><div data-slot="form"></div><aside class="panel config-preview"><div class="panel-heading"><div><span class="section-index">提交前核对</span><h2>任务摘要</h2></div></div>' +
        '<div id="config-summary" class="config-summary"></div><p class="preview-note">启动后会对目标环境产生真实压测流量。每次提交都需确认目标授权。</p></aside></div></dialog>' +
    '<dialog id="stop-confirmation" class="action-dialog" aria-labelledby="stop-confirmation-title">' +
      '<h2 id="stop-confirmation-title">停止当前任务？</h2><p>控制器会停止压测进程。未完成的流量将中断，已生成的日志和报告仍可查看。</p>' +
      '<div class="dialog-actions"><button id="cancel-stop" class="button button-quiet" type="button">继续运行</button>' +
        '<button id="confirm-stop" class="button button-danger" type="button">停止任务</button></div></dialog>'
  );

  const runPage = document.createElement('section');
  runPage.id = 'workspace-runs';
  runPage.dataset.workspacePage = 'runs';
  main.querySelector('.workspace-heading').before(runPage);
  [main.querySelector('.workspace-heading'), main.querySelector('[data-slot="strip"]'), main.querySelector('.performance-layout')].forEach(node => runPage.append(node));
  main.insertAdjacentHTML('beforeend',
    '<section id="workspace-monitoring" data-workspace-page="monitoring" hidden aria-labelledby="monitoring-page-title">' +
      '<div class="workspace-heading"><div><p class="eyebrow">METRICS</p><h1 id="monitoring-page-title">监控</h1><p>查看服务、实例和后台任务的实时状态。</p></div></div><div data-slot="monitoring"></div></section>' +
    '<section id="workspace-traces" data-workspace-page="traces" hidden aria-labelledby="traces-page-title">' +
      '<div class="workspace-heading"><div><p class="eyebrow">DISTRIBUTED TRACING</p><h1 id="traces-page-title">Trace</h1><p>检索请求与消息链路，定位错误、耗时和异步调用关系。</p></div></div><div id="traces-content"></div></section>' +
    '<section id="workspace-logs" data-workspace-page="logs" hidden aria-labelledby="logs-page-title">' +
      '<div class="workspace-heading"><div><p class="eyebrow">LOGS</p><h1 id="logs-page-title">日志</h1><p>按服务、时间和业务标识检索环境日志，关联请求与异步链路。</p></div></div><div id="logs-content"></div></section>'
  );

  Object.entries(nodes).forEach(([name, node]) => {
    main.querySelector('[data-slot="' + name + '"]').append(node);
  });
  main.querySelector('.runs-pane-header').insertAdjacentHTML('beforeend',
    '<button id="refresh-runs" class="icon-button" type="button" aria-label="刷新运行记录">' + workspaceIcon('arrow-clockwise') + '</button>'
  );
  main.querySelectorAll('[data-slot]').forEach((slot) => {
    if (!slot.hasAttribute('data-detail-view')) slot.replaceWith(...slot.childNodes);
  });
  const runs = document.querySelector('#workspace-runs');
  runs.classList.add('tx-workspace','ui-workspace');
  const heading=runs.querySelector('.workspace-heading');
  const create=heading.querySelector('#open-new-run');
  const pane=runs.querySelector('.runs-pane');
  const listToolbar=pane.querySelector('.list-toolbar');
  const search=listToolbar.querySelector('.search-field');
  search.className='ui-run-search';
  search.querySelector('span').hidden=true;
  const query=document.createElement('div');query.className='tx-query-area';query.append(search);heading.after(query);
  const tools=document.createElement('div');tools.className='tx-toolbar';tools.innerHTML='<nav class="tx-segment"><span>Runs</span></nav>';
  tools.append(document.querySelector('#run-filter-count'),document.querySelector('#clear-run-filters'),document.querySelector('#refresh-runs'),create);query.after(tools);heading.remove();
  const layout=runs.querySelector('.performance-layout');layout.className='tx-layout ui-runs-layout';
  const facets=document.createElement('aside');facets.className='tx-facets';facets.setAttribute('aria-label','压测标签筛选');listToolbar.hidden=true;facets.append(listToolbar);facets.insertAdjacentHTML('beforeend','<div id="ui-run-facets"></div>');layout.prepend(facets);
  pane.className='tx-records';pane.querySelector('.runs-pane-header').remove();
  nodes.history.className='ui-run-records';
  const detail=runs.querySelector('.detail-pane');detail.className='tx-peek ui-run-detail';detail.hidden=true;
  detail.insertAdjacentHTML('afterbegin','<header class="tx-peek-header"><div class="ui-run-header-context"><strong>Run</strong></div><div><button data-run-wide aria-label="切换任务详情宽度">'+workspaceIcon('arrows-out')+'</button><button id="close-run-detail" aria-label="关闭任务详情">'+workspaceIcon('x')+'</button></div></header>');
  const grid=document.createElement('div');grid.className='tx-detail-grid';
  detail.querySelector('.ui-run-header-context').append(runs.querySelector('.overview-strip'));
  detail.querySelector('.ui-run-header-context').append(detail.querySelector('.resource-context'),detail.querySelector('#run-context-status'));
  const content=document.createElement('article');content.className='tx-node-detail';content.append(detail.querySelector('#detail-placeholder'),detail.querySelector('#detail-body'));grid.append(content);detail.append(grid);runs.append(detail);
  document.querySelector('#close-run-detail').onclick=()=>{const u=new URL(location.href);u.searchParams.delete('run');history.replaceState(null,'',u);detail.hidden=true;};
  detail.querySelector('[data-run-wide]').onclick=()=>detail.classList.toggle('tx-wide');
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!detail.hidden&&!document.querySelector('dialog[open]'))document.querySelector('#close-run-detail').click();});
  nodes.observability.querySelector('.text-action').remove();
  nodes.eval.querySelector('.text-action').remove();
  document.querySelectorAll('.domain-section .section-kicker').forEach((item) => item.remove());
}
