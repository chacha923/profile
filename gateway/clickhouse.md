## 登录机器， 进入docker， 
<pre>
sudo docker exec -it clickhouse-server /bin/bash 
</pre>

## 进入ck 
<pre>
clickhouse-client -h 127.0.0.1 -d default -m -u default --password 'soul@123'
</pre>

## cfg
<pre>
172.16.67.95   default  ZBBuVdQQ 
</pre>


## 创建数据库
<pre>
envoy_logs.t_infra_envoy_logs_kubeflow ON CLUSTER cluster_emr
(
    `timestamp` UInt64 CODEC(DoubleDelta,LZ4),
    `startTime` DateTime64(3) CODEC(DoubleDelta,LZ4),
    `k8s_cluster` LowCardinality(String) CODEC(ZSTD(1)),
    `pod_ip` String CODEC(ZSTD(1)),
    `host_ip` String CODEC(ZSTD(1)),
    `pod_name` String CODEC(ZSTD(1)),
    `x_request_id` String CODEC(ZSTD(1)),
    `protocol` LowCardinality(String) CODEC(ZSTD(1)),
    `authority` String CODEC(ZSTD(1)),
    `x_forwarded_for` String CODEC(ZSTD(1)),
    `x_original_forwarded_for` String CODEC(ZSTD(1)),
    `method` LowCardinality(String) CODEC(ZSTD(1)),
    `path` String CODEC(ZSTD(1)),
    `duration` UInt64 CODEC(T64,ZSTD(1)),
    `downstream_local_address` String CODEC(ZSTD(1)),
    `downstream_remote_address` String CODEC(ZSTD(1)),
    `upstream_host` String CODEC(ZSTD(1)),
    `upstream_local_address` String CODEC(ZSTD(1)),
    `upstream_cluster` LowCardinality(String) CODEC(ZSTD(1)),
    `response_code` LowCardinality(String) CODEC(ZSTD(1)),
    `response_code_details` String CODEC(ZSTD(1)),
    `upstream_transport_failure_reason` String CODEC(ZSTD(1)),
    `connection_termination_details` String CODEC(ZSTD(1)),
    `body` String CODEC(ZSTD(2)),
    INDEX idx_body body TYPE tokenbf_v1(10240,3,0) GRANULARITY 4,
    INDEX idx_x_request_id x_request_id TYPE bloom_filter GRANULARITY 4,
    INDEX idx_downstream_local_address downstream_local_address TYPE bloom_filter GRANULARITY 4,
    INDEX idx_downstream_remote_address downstream_remote_address TYPE bloom_filter GRANULARITY 4,
    INDEX idx_upstream_host upstream_host TYPE bloom_filter GRANULARITY 4,
    INDEX idx_upstream_local_address upstream_local_address TYPE bloom_filter GRANULARITY 4,
    INDEX idx_upstream_cluster upstream_cluster TYPE bloom_filter GRANULARITY 4,
    INDEX idx_x_forwarded_for x_forwarded_for TYPE bloom_filter GRANULARITY 4,
    INDEX idx_x_original_forwarded_for x_original_forwarded_for TYPE bloom_filter GRANULARITY 4,
    INDEX idx_method method TYPE set(25) GRANULARITY 4,
    INDEX idx_duration duration TYPE minmax GRANULARITY 1,
    INDEX idx_timestamp timestamp TYPE minmax GRANULARITY 1,
    INDEX idx_response_code response_code TYPE set(0) GRANULARITY 1
)ENGINE = MergeTree
PARTITION BY toDate(timestamp / 1000)
ORDER BY (timestamp,authority,pod_ip,pod_name,method)
TTL toDateTime(timestamp / 1000) + toIntervalSecond(43200)
SETTINGS index_granularity = 8192,ttl_only_drop_parts = 1;
</pre>

# 异常pod
<pre>
SELECT t.upstream_host, count(), avg(t.duration), t.response_code
FROM envoy_logs.infra_envoy_logs_kubeflow_d t
WHERE authority = 'mm-post-check-trt.soulapp-inc.cn'
  and response_code != '200'
group by upstream_host, response_code
</pre>