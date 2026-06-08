## Htproute 
add annotations upgrade-websocket
<pre>
apiVersion: gateway.networking.k8s.io/v1beta1
kind: HTTPRoute
metadata:
  annotations:
    envoy-gateway/upgrade-websocket: 'true'
  name: sae-console
  namespace: kube-system
</pre>
