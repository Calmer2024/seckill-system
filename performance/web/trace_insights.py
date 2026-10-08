"""Analysis of observed spans, without inferring authoritative order state."""
def analyze(spans, truncated=False):
    by_id = {s['span_id']: s for s in spans}
    children = {}
    missing = []
    skew = []
    for span in spans:
        parent = by_id.get(span['parent_span_id'])
        if parent:
            children.setdefault(parent['span_id'], []).append(span)
            if int(span['start_time_ns']) < int(parent['start_time_ns']):
                skew.append(span['span_id'])
        elif span['parent_span_id']:
            missing.append(span['span_id'])
    roots = [s for s in spans if s['parent_span_id'] not in by_id]
    root = next((s for s in roots if s['kind'] in ('SPAN_KIND_SERVER', '2')), (roots or spans)[0])
    services = {}
    for span in spans:
        start = int(span['start_time_ns'])
        end = start + int(span['duration_ms'] * 1e6)
        intervals = sorted((max(start, int(c['start_time_ns'])), min(end, int(c['start_time_ns']) + int(c['duration_ms'] * 1e6)))
                           for c in children.get(span['span_id'], []))
        covered, cursor = 0, start
        for a, b in intervals:
            if b > max(cursor, a):
                covered += b - max(cursor, a)
            cursor = max(cursor, b)
        span['self_duration_ms'] = max(0, span['duration_ms'] - covered / 1e6)
        service = services.setdefault(span['service'], {'service': span['service'], 'spans': 0, 'self_ms': 0, 'errors': 0})
        service['spans'] += 1
        service['self_ms'] += span['self_duration_ms']
        service['errors'] += span['status'] == 'error'
    slowest = sorted(spans, key=lambda s: s['self_duration_ms'], reverse=True)[:5]
    path, seen = [], set()
    current = slowest[0] if slowest else None
    while current and current['span_id'] not in seen:
        seen.add(current['span_id'])
        path.append(current['span_id'])
        current = by_id.get(current['parent_span_id'])
    start = min(int(s['start_time_ns']) for s in spans)
    end = max(int(s['start_time_ns']) + int(s['duration_ms'] * 1e6) for s in spans)
    return {'entry_span_id': root['span_id'], 'response_ms': root['duration_ms'], 'observed_span_ms': (end - start) / 1e6,
            'services': sorted(services.values(), key=lambda s: s['self_ms'], reverse=True),
            'slowest': [{'span_id': s['span_id'], 'name': s['name'], 'self_ms': s['self_duration_ms']} for s in slowest],
            'focus_path': path[::-1], 'quality': {'truncated': truncated, 'missing_parent_nodes': missing,
                'clock_order_nodes': skew, 'missing_version_services': sorted({s['service'] for s in spans if not s.get('resource', {}).get('service.version') or s['resource'].get('service.version') == 'unknown'}),
                'entry_scope': 'backend', 'completeness': 'not_proven'}}
