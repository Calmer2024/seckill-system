"""Render a measured trial without equating local evidence with production readiness."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import statistics

def render(report):
    rows=[]
    for run in report['runs']:
        rows.append(f"| {run['name']} | {run['requests']} | {run['rps']:.2f} | {run['p95_ms']:.2f} | {run['p99_ms']:.2f} | {run['cpu_cores_mean']:.3f} | {run['memory_bytes']/1024**2:.1f} | {run['docker_log_utf8_bytes']/max(run['requests'],1):.1f} | {run['error_rate']:.2%} |")
    gate=report.get('gates',{})
    loss=gate.get('median_rps_loss'); latency=gate.get('median_p95_increase')
    return '\n'.join([
        '# P4 本地隔离实测', '',f"范围：{report['scope']}",
        f"商品接口 GET /api/products，4 个 Uvicorn 进程，4 VUs；每轮 {report.get('duration_seconds',20)} 秒，三组交替比较。此结果不是生产容量或 HA 验收。", '',
        '| 轮次 | 请求 | RPS | P95 ms | P99 ms | 平均 CPU 核 | 末尾内存 MiB | 日志输出 B/请求 | 错误率 |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |',*rows,'',
        f"配对吞吐损失中位数：{loss:.2%}。配对 P95 增幅中位数：{latency:.2%}。" if loss is not None and latency is not None else '测量未完成。',
        f"5% 开销门禁：{'通过' if gate.get('overhead_within_5_percent') else '未通过'}。生产门禁：未通过。",'',
        'CPU 取 cgroup usage_usec 增量 / 执行墙钟时间（含 k6 启动与收尾），内存为 cgroup memory.current；峰值另见 JSON。日志字节为 docker compose logs 的 UTF-8 输出，含 Compose 前缀，不是 Loki 压缩存储成本。',
        '冷状态指进程重启后的首次负载，缓存关闭；数据库 buffer pool 与宿主机页缓存未强制清空。off 关闭共享 HTTP 遥测、SDK 导出和 INFO 日志，保留请求上下文、框架已有 Trace ID 及既有业务计数器。',
        'on 使用 10% ParentBased head sampling。预算化与 hotpath 试验对成功且未采样请求的 access log 再抽样 10%；错误/拒绝、已采样 Trace 的关联日志与业务状态日志全部保留。hotpath 把商品成功 DB 读取日志降为 DEBUG，计数器和 Trace 保留。各轮镜像及策略不同，原始结果均保留。',
        '这里测量应用侧观测开销与异步 Trace 导出，没有为隔离项目接入完整 Prometheus/Alloy/Loki 链路，不代表整个观测集群的资源开销。宿主机同时运行原业务与 P3 组件，噪声尚未隔离；20 秒试验不能替代长时间稳定性测试。', '',
        '## 故障与契约', '',
        '```json',json.dumps({'fault':report.get('fault',{}),'contracts':report.get('contracts',{}),'gates':gate},ensure_ascii=False,indent=2),'```','',
        '恢复后新 Trace 可查不等于停机期间无丢失。SDK 超出有界队列会丢弃；初轮未专门计数 overflow 日志，预算化轮次记录的 overflow_messages 只覆盖本轮仍可读取的日志。没有进行磁盘耗尽、对象存储故障、多节点切换或外部通知验收。', '',
        'JSON、逐轮 k6 原始结果与 Docker 资源数据为验收依据。生产验收仍需要同构环境、真实通知渠道、认证、保留恢复与多节点演练。',''])

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--validation',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args(); data=json.loads(Path(args.validation).read_text(encoding='utf-8'))
    Path(args.output).write_text(render(data),encoding='utf-8')

if __name__=='__main__': main()
