"""SELECT-only order evidence. Never read user IDs, prices or message payloads."""
import time
from datetime import datetime, timezone

ORDER_STATUSES = frozenset({'CREATED', 'SUCCESS', 'PENDING_INVENTORY', 'CONFIRMED', 'REJECTED', 'PAYING', 'PAID', 'CANCELED', 'CANCELLED', 'FAILED'})


def recent_orders(connection, start, end, status='', order_id='', product_id='', before=''):
    start, end = int(start), int(end)
    if not 0 < start < end <= time.time() + 60 or status and status not in ORDER_STATUSES:
        raise ValueError('invalid order filter')
    for identifier in (order_id, product_id, before):
        if identifier and (not identifier.isdecimal() or not 0 < int(identifier) <= 9223372036854775807):
            raise ValueError('invalid identifier')
    clauses = ['created_at >= %s', 'created_at <= %s']
    values = [datetime.fromtimestamp(start, timezone.utc).replace(tzinfo=None), datetime.fromtimestamp(end, timezone.utc).replace(tzinfo=None)]
    for key, value in [('status', status), ('order_id', order_id), ('product_id', product_id)]:
        if value:
            clauses.append(key + '=%s')
            values.append(value if key == 'status' else int(value))
    if before:
        clauses.append('order_id < %s')
        values.append(int(before))
    orders = []
    try:
        with connection.cursor() as cursor:
            cursor.execute('SET SESSION MAX_EXECUTION_TIME=1500')
            cursor.execute("SET SESSION time_zone='+00:00'")
            cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
            cursor.execute('START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY')
            for table in ORDER_TABLES:
                cursor.execute(f"SELECT order_id, product_id, quantity, status, created_at, updated_at FROM {table} WHERE {' AND '.join(clauses)} ORDER BY order_id DESC LIMIT 51", tuple(values))
                orders.extend({'order_id': str(v[0]), 'product_id': str(v[1]), 'quantity': v[2], 'status': v[3],
                               'created_at': v[4].isoformat()+'Z', 'updated_at': v[5].isoformat()+'Z'} for v in cursor.fetchall())
        ids = [o['order_id'] for o in orders]
        if len(set(ids)) != len(ids):
            raise ValueError('conflicting order IDs')
        orders.sort(key=lambda v: int(v['order_id']), reverse=True)
        has_more = len(orders) > 50
        return {'orders': orders[:50], 'limit': 50, 'has_more': has_more,
                'next_cursor': orders[49]['order_id'] if has_more else None,
                'source': 'mysql_primary_read_only', 'sampled_at': time.time(), 'sort': 'order_id_desc'}
    finally:
        connection.rollback()

ORDER_TABLES = tuple(f"order_db_{db}.t_order_{table}" for db in range(2) for table in range(2))
OUTBOX_TABLES = tuple(f"order_db_{db}.t_order_outbox_event_{table}" for db in range(2) for table in range(2))


def read_order(connection, order_id):
    if not order_id.isdecimal() or not 0 < int(order_id) <= 9223372036854775807:
        raise ValueError("invalid order ID")
    def row(values, names):
        return {name: value.isoformat() + 'Z' if hasattr(value, 'isoformat') else str(value) if name in {'order_id', 'product_id', 'id'} else value
                for name, value in zip(names, values)}
    orders, events = [], []
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION MAX_EXECUTION_TIME=1500")
            cursor.execute("SET SESSION time_zone='+00:00'")
            cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            cursor.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            for table in ORDER_TABLES:
                cursor.execute(f"SELECT order_id, product_id, quantity, status, created_at, updated_at FROM {table} WHERE order_id=%s LIMIT 1", (int(order_id),))
                orders.extend(row(v, ('order_id', 'product_id', 'quantity', 'status', 'created_at', 'updated_at')) for v in cursor.fetchall())
            for table in OUTBOX_TABLES:
                cursor.execute(f"SELECT id, event_type, topic, status, retry_count, created_at, published_at FROM {table} WHERE aggregate_id=%s ORDER BY created_at, id LIMIT 26", (int(order_id),))
                events.extend(row(v, ('id', 'event_type', 'topic', 'status', 'retry_count', 'created_at', 'published_at')) for v in cursor.fetchall())
        events.sort(key=lambda v: (v['created_at'], v['id']))
        return {'availability': 'available', 'source': 'mysql_primary_read_only', 'sampled_at': time.time(),
                'order': orders[0] if len(orders) == 1 else None, 'found': len(orders) == 1,
                'conflicting_records': len(orders) > 1, 'outbox': events[:25], 'truncated': len(events) > 25,
                'history_complete': False}
    finally:
        connection.rollback()
