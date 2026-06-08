#!/usr/bin/env python3
"""Feishu (Lark) alarm-card text parser for Soul bigeyes alerts.

Used by alarm-diagnosis when the user @-mentions the Lobster bot in a Feishu
alarm group and pastes the card text directly (no EVT-ID). The skill normally
calls `bigeyes_admin_api_client.py alarm-event-detail <EVT-ID>` to get
structured alarm data; this parser is the **card-text fallback** for when:

  1. No EVT-ID is present in the message (user pastes card body only).
  2. INTERNAL_TOKEN is missing/expired, so bigeyes API is unreachable.
  3. Quick triage before paying the bigeyes round-trip.

Extracts these fields from common bigeyes Feishu card templates:

    event_id            EVT-XXXXX (if present)
    rule_name           告警规则名称
    resource            原始资源名（保留 prod- 前缀）
    service             映射后的 OTel service.name（调用 alarm_resource_mapper）
    trigger_time        ISO-8601 (Asia/Shanghai)
    trigger_time_end    告警窗口 end（如卡片含窗口）
    level               P0/P1/P2/P3（多种同义命名归一）
    category            Application / NginxDomain / Redis / KafkaTopic / ...
    threshold           阈值 / 触发条件
    actual_value        当前值
    receivers           接收人/责任人
    top_exception       Top1 异常类
    sample_log          示例日志/堆栈片段
    detail_url          飞书卡片"查看详情"链接
    raw_keywords        其它命中关键词（trace_id、IP、错误码等）

Stdlib only. Outputs JSON or markdown summary.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

# Allow direct import when invoked as script or as module
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
try:
    from alarm_resource_mapper import resource_to_service  # type: ignore
except ImportError:
    def resource_to_service(resource: str) -> str:  # type: ignore
        return resource


CST = timezone(timedelta(hours=8))


# ─── Field regexes (order matters — synonyms tried top-to-bottom) ────────────

RE_EVENT_ID = re.compile(r"(?:事件\s*[:：]?\s*)?(EVT-[A-Z0-9]+)", re.IGNORECASE)

# rule name: try labeled forms first; fallback to first ** bold ** heading
_RULE_LABELS = (
    r"告警规则(?:名称|名)?",
    r"规则(?:名称|名)?",
    r"Rule\s*Name",
    r"告警名称",
    r"alert\s*name",
)
RE_RULE_NAME = re.compile(
    r"(?:%s)\s*[:：]\s*([^\n\|]+?)(?:\n|$|\||\s\s)" % "|".join(_RULE_LABELS),
    re.IGNORECASE,
)

# resource — could be 应用名称 / 服务名 / 资源 / 实例 / 主机
# 长形式（带"名称"后缀）必须放在短形式之前，因为正则按顺序尝试
_RESOURCE_LABELS = (
    r"应用名称",
    r"服务名称",
    r"资源名称",
    r"实例名称",
    r"主机名称",
    r"应用名",
    r"服务名",
    r"资源名",
    r"应用",
    r"服务",
    r"资源",
    r"实例",
    r"主机",
    r"application",
    r"service\s*name",
    r"resource",
    r"service",
)
RE_RESOURCE = re.compile(
    r"(?:%s)\s*[:：]\s*([^\n\|\s,，]+)" % "|".join(_RESOURCE_LABELS),
    re.IGNORECASE,
)

# 资源值后缀：bigeyes 卡片有 `prod-xxx/(error.log)` / `prod-xxx/error.log` 这种
# k8s deployment + 日志路径混排。提取后必须 strip 第一个 `/` 及之后内容。
RE_RESOURCE_TRAIL = re.compile(r"^([^/]+)")

# triggered timestamp — many formats
_TIME_LABELS = (
    r"触发时间",
    r"告警时间",
    r"发生时间",
    r"开始时间",
    r"时间",
    r"trigger\s*time",
    r"firing\s*at",
)
RE_TRIGGER_TIME = re.compile(
    r"(?:%s)\s*[:：]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}[\sT]+\d{1,2}:\d{2}(?::\d{2})?)"
    % "|".join(_TIME_LABELS),
    re.IGNORECASE,
)
# bare timestamp fallback — first ISO-ish timestamp on the card
RE_BARE_TIME = re.compile(r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}[\sT]+\d{1,2}:\d{2}(?::\d{2})?)\b")

# end time
_END_TIME_LABELS = (r"结束时间", r"恢复时间", r"end\s*time")
RE_END_TIME = re.compile(
    r"(?:%s)\s*[:：]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}[\sT]+\d{1,2}:\d{2}(?::\d{2})?)"
    % "|".join(_END_TIME_LABELS),
    re.IGNORECASE,
)

# level / 严重度
_LEVEL_LABELS = (
    r"级别",
    r"严重度",
    r"严重等级",
    r"等级",
    r"priority",
    r"severity",
    r"level",
)
RE_LEVEL = re.compile(
    r"(?:%s)\s*[:：]\s*([Pp][0-3]|[Ww]arning|[Cc]ritical|[Ii]nfo|高|中|低|严重|警告|信息)"
    % "|".join(_LEVEL_LABELS),
)

# category
_CATEGORY_LABELS = (r"告警类别", r"告警类型", r"类别", r"category", r"type")
RE_CATEGORY = re.compile(
    r"(?:%s)\s*[:：]\s*([A-Za-z][\w]+)" % "|".join(_CATEGORY_LABELS),
    re.IGNORECASE,
)

# threshold / actual
_THRESHOLD_LABELS = (r"阈值", r"触发条件", r"条件", r"threshold")
RE_THRESHOLD = re.compile(
    r"(?:%s)\s*[:：]\s*([^\n\|]+?)(?:\n|$|\|)" % "|".join(_THRESHOLD_LABELS),
    re.IGNORECASE,
)
_ACTUAL_LABELS = (r"当前值", r"实际值", r"触发值", r"当前", r"value", r"actual")
RE_ACTUAL = re.compile(
    r"(?:%s)\s*[:：]\s*([^\n\|]+?)(?:\n|$|\|)" % "|".join(_ACTUAL_LABELS),
    re.IGNORECASE,
)

# receivers — @ list or labeled list
_RECEIVER_LABELS = (r"接收人", r"责任人", r"通知到", r"recipients", r"receiver")
RE_RECEIVER = re.compile(
    r"(?:%s)\s*[:：]\s*([^\n\|]+?)(?:\n|$|\|)" % "|".join(_RECEIVER_LABELS),
    re.IGNORECASE,
)
# RE_AT_MENTIONS moved below — see strict version that rejects hex-hash junk (v3.0.2)

# exception / top error
# 标签必须以 word boundary 开头/结尾，避免 `RpcException: Failed` 里的 "exception" 被当成标签命中。
# 同样不收 `error type` 这种过于通用的英文 label。
_EXCEPTION_LABELS = (r"Top\s*1?\s*异常", r"主要异常", r"异常类型", r"alert\s*exception\s*type")
RE_EXCEPTION = re.compile(
    r"(?:^|[\s\*])(?:%s)\s*[:：]\s*([\w.$]+(?:Exception|Error|Timeout|Throwable)?)" % "|".join(_EXCEPTION_LABELS),
    re.IGNORECASE | re.MULTILINE,
)
# 非标签 inline 匹配：找 fully-qualified Exception/Error 类名
RE_INLINE_EXC = re.compile(r"\b([\w.$]+(?:Exception|Error|TimeoutException|Throwable))\b")

# detail URL — bigeyes / lark internal
RE_URL = re.compile(r"(https?://[\w\-.]+(?:/[^\s\)）\]]*)?)")

# trace id
RE_TRACE_ID = re.compile(r"\b(?:trace[_-]?id|traceId)\s*[:：=]?\s*([0-9a-f]{16,32})", re.IGNORECASE)
RE_BARE_TRACE = re.compile(r"\b([0-9a-f]{32})\b")

# Dubbo SO-TraceId 格式（v3.0.4 新增）：
# 业务通过 MDC 透传 Dubbo traceId 到日志，OTel logs 里字段是 logback.mdc.SO-TraceId。
# 两种常见格式：
#   - 长 base64-encoded:  f17791804963150481L2pod2VhcW5uVDIvb3lLbWNoZUE9PQ==
#   - 短 TE:hex:TE 包裹:    TE:b1779039036806ac10e86345391:TE
#   - 短 hex (不带 TE 包裹): 41779117281679ac1008ca37641
RE_SO_TRACE_ID = re.compile(
    r"(?:SO-TraceId|MDC\.SO-TraceId|logback\.mdc\.SO-TraceId|TraceId)"
    r"\s*[=:：]?\s*([\w+/=]{16,80})",
    re.IGNORECASE,
)
RE_TE_WRAPPED_TRACE = re.compile(r"TE:([0-9a-z]{16,40}):TE")


def is_dubbo_trace_id(s: str) -> bool:
    """Return True if `s` looks like Dubbo SO-TraceId (not OTel 32-hex)."""
    if not s:
        return False
    s = s.strip()
    # OTel 标准: 32 lowercase hex
    if re.fullmatch(r"[0-9a-f]{32}", s):
        return False
    # Dubbo SO-TraceId 常见: 17-20 数字开头 + base64 body
    if re.match(r"^\d{14,20}[A-Za-z0-9+/=]{4,}$", s):
        return True
    # 含大写字母 + 总长 > 20 = base64-encoded
    if len(s) > 20 and re.search(r"[A-Z+/=]", s):
        return True
    # 长 hex 但不是标准 32 位（如 41779117281679ac1008ca37641 = 27 hex）
    if re.fullmatch(r"[0-9a-f]{17,31}", s) or re.fullmatch(r"[0-9a-f]{33,}", s):
        return True
    return False


def classify_trace_id(s: str) -> str:
    """Return one of: 'otel' (32 hex), 'dubbo' (SO-TraceId), 'unknown'."""
    if not s:
        return "unknown"
    if re.fullmatch(r"[0-9a-f]{32}", s.strip()):
        return "otel"
    if is_dubbo_trace_id(s):
        return "dubbo"
    return "unknown"

# @-mention: must start with a letter, ≥3 chars, can contain dots / dashes / underscores.
# Strict patterns reject hex-hash junk like `LockOption@aab320a`, `@FFFF`, etc.
RE_AT_MENTIONS = re.compile(r"(?<![\w])@([A-Za-z][\w.\-]{2,})")
# Filter helper: reject mentions that look like hex (length 6-32, all hex chars)
_HEX_PATTERN = re.compile(r"^[0-9a-fA-F]{6,32}$")

def _is_real_mention(name: str) -> bool:
    """Return False for hash-like junk (e.g. LockOption@aab320a → 'aab320a')."""
    if not name or len(name) < 3:
        return False
    if _HEX_PATTERN.match(name):  # pure hex of plausible hash length
        return False
    # short all-lowercase mostly-numeric tokens are also suspicious (e.g. uuid fragments)
    if len(name) <= 8 and sum(1 for c in name if c.isdigit()) >= len(name) // 2:
        return False
    return True

# IP:port
RE_IP_PORT = re.compile(r"\b((?:\d{1,3}\.){3}\d{1,3}(?::\d{2,5})?)\b")

# Scenario signals — detected on raw text post-markdown-strip
# Used by alarm-diagnosis to tailor analysis (RocketMQ vs Dubbo vs lock vs DB etc.)
RE_SCENARIO_MQ_CONSUMER = re.compile(
    r"MessageListenerSoTraceDecorator|ConsumeMessageThread|RocketMQ.*consumer|RocketMQ.*Listener|"
    r"consumer message was error|消费消息.*失败",
    re.IGNORECASE,
)
RE_SCENARIO_LOCK_FAILURE = re.compile(
    r"Failed to obtain the distributed lock|LockOption|DistributedLock|RedissonLock|getLock.*fail|"
    r"获取分布式锁失败|加锁失败",
    re.IGNORECASE,
)
RE_SCENARIO_DUBBO_RPC = re.compile(
    r"org\.apache\.dubbo\.rpc\.RpcException|Invoke remote method timeout|dubbo://|providers \[",
)
RE_SCENARIO_DB = re.compile(
    r"jdbc:mysql|DataAccessException|SQLException|deadlock|Lock wait timeout|connection pool",
    re.IGNORECASE,
)
RE_SCENARIO_REDIS = re.compile(
    r"RedisCommandTimeout|JedisConnection|LettuceConnection|Redis.*timeout|CLUSTERDOWN|MOVED|"
    r"redis.*connection.*refused",
    re.IGNORECASE,
)

# 错误关键字 / 错误统计 / 错误分类 — bigeyes ERROR 告警卡片的专有字段
_ERR_KEYWORD_LABELS = (r"错误关键字", r"关键字", r"keyword")
RE_ERR_KEYWORD = re.compile(
    r"(?:%s)\s*[:：]\s*([^\n\|]+?)(?:\n|$|\|)" % "|".join(_ERR_KEYWORD_LABELS),
    re.IGNORECASE,
)
_ERR_COUNT_LABELS = (r"错误统计", r"错误数", r"error\s*count")
RE_ERR_COUNT = re.compile(
    r"(?:%s)\s*[:：]\s*([^\n\|]+?)(?:\n|$|\|)" % "|".join(_ERR_COUNT_LABELS),
    re.IGNORECASE,
)
_ERR_TOPN_LABELS = (
    r"错误分类\s*Top\s*\d*",
    r"Top\s*\d*\s*错误",
    r"Top\s*\d*\s*异常",
    r"top\s*errors",
)
RE_ERR_TOPN = re.compile(
    r"(?:%s)\s*[:：]\s*([\s\S]+?)(?=\n\s*\n|\n\s*\*\*|$)" % "|".join(_ERR_TOPN_LABELS),
    re.IGNORECASE,
)
# 错误内容（典型字段名 in bigeyes 卡片）
_ERR_BODY_LABELS = (r"错误内容", r"错误样例", r"sample\s*error", r"sample\s*log")
RE_ERR_BODY = re.compile(
    r"(?:%s)\s*[:：]\s*([\s\S]+?)(?=\n\s*\*\*|$)" % "|".join(_ERR_BODY_LABELS),
    re.IGNORECASE,
)
# IP 分布（bigeyes 字段：`IP分布: 总量: 57 / 172.16.x.x(2.4%), ...`）
_IP_DIST_LABELS = (r"IP\s*分布", r"Pod\s*分布", r"ip\s*distribution")
RE_IP_DIST = re.compile(
    r"(?:%s)\s*[:：]\s*([^\n\|]+?)(?:\n|$|\|)" % "|".join(_IP_DIST_LABELS),
    re.IGNORECASE,
)
# 报警时间段（窗口式：start~end）
_TIME_WINDOW_LABELS = (r"报警时间段", r"告警时间段", r"窗口时间", r"time\s*window")
RE_TIME_WINDOW = re.compile(
    r"(?:%s)\s*[:：]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}[\sT]+\d{1,2}:\d{2}(?::\d{2})?)\s*[~～\-]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}[\sT]+\d{1,2}:\d{2}(?::\d{2})?)"
    % "|".join(_TIME_WINDOW_LABELS),
    re.IGNORECASE,
)

# bigeyes 日志查询深链 — 包含 app= bizTenant= 等参数，可用于反向验证 service.name
RE_LOG_URL = re.compile(r"https?://[^\s\)）\]]*\?[^\s\)）\]]*\bapp=([\w\-]+)")


def _strip_markdown(text: str) -> str:
    """Strip Feishu markdown bold/italic markers so label/value regex can match.

    Feishu 卡片大量使用 `**xxx：**` 形式包裹标签。直接用 ** 残留会导致正则 `应用名称：` 后面接 `**` 不被识别为冒号尾部。
    本函数把 `**` 整体删除（保守做法，文本语义不丢）。
    单下划线 `_value_` 保留（用户名可能含下划线，全删风险大）。
    """
    if not text:
        return text
    # 删除成对的 ** 加粗标记
    cleaned = re.sub(r"\*\*", "", text)
    # 去掉空标签 `__` 占位 (Feishu 偶现)
    cleaned = re.sub(r"\b__\b", "", cleaned)
    return cleaned


# ─── Normalizers ─────────────────────────────────────────────────────────────

def _norm_time(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip().replace("/", "-").replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=CST).isoformat()
        except ValueError:
            continue
    return None


_LEVEL_NORM = {
    "p0": "P0", "p1": "P1", "p2": "P2", "p3": "P3",
    "critical": "P0", "严重": "P0",
    "warning": "P1", "警告": "P1", "高": "P1",
    "info": "P3", "信息": "P3", "低": "P3",
    "中": "P2",
}

def _norm_level(raw: str | None) -> str | None:
    if not raw:
        return None
    return _LEVEL_NORM.get(raw.strip().lower())


def _trim(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().strip("`*_ ").strip()
    return v or None


# ─── Main parser ─────────────────────────────────────────────────────────────

def parse_feishu_card(text: str) -> dict:
    """Extract structured alarm fields from a Feishu alarm card body.

    Returns a dict with all known fields (None when not found) plus a
    `confidence` integer (0-7) signaling how much was parsed.

    Handles two card body styles:
      - 标准飞书卡片正文（Feishu rich-text 渲染后）：标签后跟值
      - bigeyes ERROR 告警 markdown：`**应用名称：** prod-xxx-k8s/(error.log)`
        ↑ markdown 加粗包裹标签，值带 `/path` 后缀（k8s deploy + 日志文件）
    """
    raw_text = text or ""
    # ★ 预处理：先 strip markdown 加粗，让标签正则能命中
    text = _strip_markdown(raw_text)

    def _first(pattern: re.Pattern, group: int = 1) -> str | None:
        m = pattern.search(text)
        return _trim(m.group(group)) if m else None

    event_id = _first(RE_EVENT_ID)
    rule_name = _first(RE_RULE_NAME)
    resource = _first(RE_RESOURCE)
    # ★ Strip k8s deploy 路径后缀（`prod-xxx-k8s/(error.log)` → `prod-xxx-k8s`）
    if resource:
        m = RE_RESOURCE_TRAIL.match(resource)
        if m:
            resource = m.group(1).strip()

    # 时间窗 → 优先识别 `报警时间段：YYYY-MM-DD HH:MM:SS~YYYY-MM-DD HH:MM:SS`
    window_match = RE_TIME_WINDOW.search(text)
    if window_match:
        trigger_raw = window_match.group(1)
        end_raw_window = window_match.group(2)
    else:
        trigger_raw = _first(RE_TRIGGER_TIME) or _first(RE_BARE_TIME)
        end_raw_window = None
    trigger_time = _norm_time(trigger_raw or "")
    end_raw = end_raw_window or _first(RE_END_TIME)
    end_time = _norm_time(end_raw or "")
    level = _norm_level(_first(RE_LEVEL))
    category = _first(RE_CATEGORY)
    threshold = _first(RE_THRESHOLD)
    actual = _first(RE_ACTUAL)

    # 错误关键字 / 统计 / Top 分类 / 内容（bigeyes ERROR 告警专有）
    err_keyword = _first(RE_ERR_KEYWORD)
    err_count = _first(RE_ERR_COUNT)
    err_topn_raw = _first(RE_ERR_TOPN)
    err_body = _first(RE_ERR_BODY)
    ip_dist_raw = _first(RE_IP_DIST)

    # 当 threshold 字段缺失但有"错误统计"时，回填阈值（如"1分钟报错5254次,超过阀值:4000"）
    if not threshold and err_count:
        m_thr = re.search(r"超过[阀阈]值\s*[:：]?\s*(\d+)", err_count)
        if m_thr:
            threshold = f"> {m_thr.group(1)}"

    # 当 resource 仍未拿到时，尝试从日志深链 `?app=xxx` 抽
    if not resource:
        url_match = RE_LOG_URL.search(raw_text)
        if url_match:
            resource = url_match.group(1).strip()

    # Receivers: combine labeled + @-mentions (filter out hex-hash junk)
    receiver_str = _first(RE_RECEIVER)
    at_mentions = [m for m in RE_AT_MENTIONS.findall(text) if _is_real_mention(m)]
    receivers: list[str] = []
    if receiver_str:
        for r in re.split(r"[,\s，、]+", receiver_str):
            r = r.strip().lstrip("@").strip()
            if r and _is_real_mention(r):
                receivers.append(r)
    for r in at_mentions:
        if r and r not in receivers:
            receivers.append(r)

    # Exception: labeled first, then top_errors[0], then inline scan
    top_exception = _first(RE_EXCEPTION)
    if not top_exception:
        # 先从"错误分类Top3"第一条里抽（最准 — 是真正占比最高的异常）
        if err_topn_raw:
            first_top_match = RE_INLINE_EXC.search(err_topn_raw)
            if first_top_match:
                top_exception = first_top_match.group(1)
        # 仍未拿到，全文扫
        if not top_exception:
            inline = RE_INLINE_EXC.findall(text)
            if inline:
                top_exception = inline[0]

    detail_url = _first(RE_URL)
    trace_id = _first(RE_TRACE_ID) or (
        _trim(RE_BARE_TRACE.search(text).group(1)) if RE_BARE_TRACE.search(text) else None
    )

    # v3.0.4 新增：单独抽 SO-TraceId（Dubbo 格式）+ classification
    so_trace_ids: list[str] = []
    for m in RE_TE_WRAPPED_TRACE.finditer(raw_text):
        if m.group(1) not in so_trace_ids:
            so_trace_ids.append(m.group(1))
    for m in RE_SO_TRACE_ID.finditer(raw_text):
        cand = m.group(1)
        if cand and cand not in so_trace_ids and is_dubbo_trace_id(cand):
            so_trace_ids.append(cand)
    trace_id_format = classify_trace_id(trace_id) if trace_id else (
        "dubbo" if so_trace_ids else "unknown"
    )
    # 若 trace_id 抽到的是 Dubbo 格式，把它也加进 so_trace_ids
    if trace_id and trace_id_format == "dubbo" and trace_id not in so_trace_ids:
        so_trace_ids.insert(0, trace_id)

    # Service mapping — preserve original resource, derive service.name
    service = resource_to_service(resource) if resource else None

    # Heuristic confidence: count non-null essential fields
    essentials = [event_id, rule_name, resource, trigger_time, level, top_exception, threshold]
    confidence = sum(1 for x in essentials if x)

    # If no labeled exception/top-error and no level but text mentions ERROR / 报错 / 超时,
    # extract a sample log line as fallback context. 优先用 "错误内容" 字段。
    sample_log = err_body
    if not sample_log:
        for line in text.splitlines():
            if any(kw in line for kw in ("Exception", "ERROR", "报错", "超时", "timeout", "RpcException")):
                sample_log = _trim(line)
                if sample_log and len(sample_log) > 20:
                    break

    # 把"错误分类Top3"解析成结构化条目
    top_errors: list[dict] = []
    if err_topn_raw:
        for chunk in re.split(r"\n", err_topn_raw):
            chunk = chunk.strip()
            if not chunk:
                continue
            cm = re.match(r"【(.+?)】\s*[:：]?\s*(\d+)\s*次?", chunk)
            if cm:
                top_errors.append({"pattern": cm.group(1).strip(), "count": int(cm.group(2))})

    # 解析 IP 分布字段（bigeyes 格式：`总量: 57 / 1.2.3.4(2.4%), 5.6.7.8(2.3%)`）
    ip_distribution: list[dict] = []
    if ip_dist_raw:
        for ipm in re.finditer(r"((?:\d{1,3}\.){3}\d{1,3})\s*\(?\s*([\d.]+)\s*%?\)?", ip_dist_raw):
            ip_distribution.append({"ip": ipm.group(1), "pct": float(ipm.group(2))})

    # Collect extra IPs / keywords for debug
    raw_keywords = {
        "ips": list(dict.fromkeys(RE_IP_PORT.findall(text)))[:10],
        "trace_ids": list(dict.fromkeys(RE_BARE_TRACE.findall(text)))[:5],
    }

    # 重新计算 confidence: essentials + 新增 sample 字段
    essentials = [event_id, rule_name, resource, trigger_time, level, top_exception, threshold]
    confidence = sum(1 for x in essentials if x)
    # 即使 level / event_id 缺失，只要 sample_log + top_errors + ip_distribution 三选二命中，
    # 视为高置信（bigeyes ERROR 告警通知就是这种格式）
    bonus_signals = [sample_log, top_errors, ip_distribution, err_count]
    if sum(1 for x in bonus_signals if x) >= 2 and confidence < 4:
        confidence = max(confidence, 4)

    # Scenario detection — used by alarm-diagnosis to tailor pod-distribution
    # interpretation and standard fix-suggestions per scenario type.
    scenarios = {
        "is_mq_consumer_scenario": bool(RE_SCENARIO_MQ_CONSUMER.search(raw_text)),
        "is_lock_failure_scenario": bool(RE_SCENARIO_LOCK_FAILURE.search(raw_text)),
        "is_dubbo_rpc_scenario": bool(RE_SCENARIO_DUBBO_RPC.search(raw_text)),
        "is_db_scenario": bool(RE_SCENARIO_DB.search(raw_text)),
        "is_redis_scenario": bool(RE_SCENARIO_REDIS.search(raw_text)),
    }
    # Primary scenario (first match in priority order — most specific wins)
    primary = None
    for k in ("is_lock_failure_scenario", "is_mq_consumer_scenario", "is_dubbo_rpc_scenario",
              "is_db_scenario", "is_redis_scenario"):
        if scenarios[k]:
            primary = k[3:-9]  # strip "is_" prefix and "_scenario" suffix
            break

    return {
        "event_id": event_id,
        "rule_name": rule_name,
        "resource": resource,
        "service": service,
        "trigger_time": trigger_time,
        "trigger_time_end": end_time,
        "level": level,
        "category": category,
        "threshold": threshold,
        "actual_value": actual,
        "receivers": receivers,
        "top_exception": top_exception,
        "sample_log": sample_log,
        "detail_url": detail_url,
        "trace_id": trace_id,
        "trace_id_format": trace_id_format,
        "so_trace_ids": so_trace_ids[:5],
        "error_keyword": err_keyword,
        "error_count_text": err_count,
        "top_errors": top_errors,
        "ip_distribution": ip_distribution,
        "raw_keywords": raw_keywords,
        "confidence": confidence,
        "needs_fallback_extraction": confidence < 4,
        "scenarios": scenarios,
        "primary_scenario": primary,
    }


def render_summary(parsed: dict) -> str:
    """Markdown summary for human / LLM consumption."""
    lines = [
        "# 飞书告警卡片解析结果",
        "",
        f"- 事件 ID: {parsed.get('event_id') or '—'}",
        f"- 规则名: {parsed.get('rule_name') or '—'}",
        f"- 原始资源: {parsed.get('resource') or '—'}",
        f"- OTel service.name: {parsed.get('service') or '—'}",
        f"- 触发时间: {parsed.get('trigger_time') or '—'}",
        f"- 结束时间: {parsed.get('trigger_time_end') or '—'}",
        f"- 级别: {parsed.get('level') or '—'}",
        f"- 类别: {parsed.get('category') or '—'}",
        f"- 阈值: {parsed.get('threshold') or '—'}",
        f"- 当前值: {parsed.get('actual_value') or '—'}",
        f"- 接收人: {', '.join(parsed.get('receivers') or []) or '—'}",
        f"- Top 异常: {parsed.get('top_exception') or '—'}",
        f"- 示例日志: {parsed.get('sample_log') or '—'}",
        f"- 详情链接: {parsed.get('detail_url') or '—'}",
        f"- TraceId: {parsed.get('trace_id') or '—'}",
        "",
        f"解析置信度: {parsed.get('confidence', 0)} / 7",
    ]
    if parsed.get("needs_fallback_extraction"):
        lines.append(
            "\n> ⚠️ 关键字段缺失（confidence < 4），需要 LLM 在卡片正文里二次抽取。"
            "建议主 agent 把卡片原文也保留在 context 里。"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse Feishu (Lark) alarm card text into structured fields.",
    )
    parser.add_argument(
        "--input",
        help="File path to read card body; '-' for stdin (default).",
        default="-",
    )
    parser.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="json",
        help="Output format. Default JSON for AI agent consumption.",
    )
    args = parser.parse_args()

    if args.input == "-":
        text = sys.stdin.read()
    else:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()

    parsed = parse_feishu_card(text)

    if args.format == "json":
        json.dump(parsed, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_summary(parsed))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())