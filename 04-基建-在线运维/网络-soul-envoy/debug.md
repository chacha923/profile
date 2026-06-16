<pre>

sudo kubectl  -n envoy-gateway-system port-forward service/envoy-default-eg 8001:80 
sudo kubectl  -n kube-system port-forward service/ingress-nginx-lb 8002:80

sudo kubectl  -n envoy-gateway-system port-forward service/envoy-default-eg-admin 18000:19000
curl --verbose --header "Host: gray-sae.soulapp-inc.cn" http://127.0.0.1:8080/

curl --verbose --header "Host: gray-sae.soulapp-inc.cn"  http://10.30.14.12:30080/



curl --verbose --header "Host: pre-roi-db-service.soulapp-inc.cn" http://127.0.0.1:8080/health_check

curl --verbose --header "Host: logging-admin.soulapp-inc.cn" http://127.0.0.1:8080/health_check
curl --verbose --header "Host: sae.soulapp-inc.cn" http://127.0.0.1:8080/api/v1/deploy/list?appId=2065

</pre>
curl --verbose --header "Host: marketing-openapi.c.t.soulapp-inc.cn"   http://127.0.0.1:80/


curl --verbose --header "Host: demo.c.t.soulapp-inc.cn"   http://127.0.0.1:80/
curl --verbose --header "Host: marketing-openapi.c.t.soulapp-inc.cn"  http://10.50.49.141:80/


curl --verbose --header "Host: edas-demo.soulapp-inc.cn"  http://172.16.79.181:30080/

curl http://127.0.0.1:80/ -H "X-Forwarded-For: 99.3.105.241, 100.116.41.136, 192.168.18.209" -H "Host: demo.c.t.soulapp-inc.cn"
curl http://127.0.0.1:80/ -H "X-Forwarded-For: 112.224.143.110, 112.224.143.120" -H "Host: demo.c.t.soulapp-inc.cn"