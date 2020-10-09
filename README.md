# harporias

K8s controller to generate ha_proxy configurations dinamically

<img src="https://github.com/felix-dpg/harporias/blob/main/logo.jpg" width="100">

----

A lot of users has ha_proxy as the loadbalancer in front of their kubernetes services. The configuration of the ha_proxy when you have a lot of k8s services could be a pain because you need to do it manually. That is when harporias could time save, generating the configuration of these services dynamically in the ha_proxy when services are created in the k8s cluster and are NodePort service type.

harporias -- Well, Im a fan of Dark Souls saga, artorias is my prefered character.

----

## What you need to use harporias

You need to install de Data Plane API in the ha_proxy server. For more info check this link:  https://www.haproxy.com/documentation/hapee/1-9r1/reference/dataplaneapi/

## To start using harporias

harporias is written in python3. As a k8s controller you need to run it as a Deployment inside your k8s cluster.

You can use this Dockerfile to build harporias image:

```
FROM python:latest
RUN mkdir /app
WORKDIR /app
COPY readservice.py /app/readservice.py
COPY haproxy_backend_server_tmpl.json /tmp/haproxy_backend_server_tmpl.json
COPY haproxy_backend_tmpl.json /tmp/haproxy_backend_tmpl.json
COPY haproxy_frontend_bind_tmpl.json /tmp/haproxy_frontend_bind_tmpl.json
COPY haproxy_frontend_tmpl.json /tmp/haproxy_frontend_tmpl.json
RUN pip install kubernetes pytz requests
CMD ["python","-u","harporias.py"]
```

...or use my image in Dockerhub: https://hub.docker.com/r/felixdpg/harporias

The json files of the Docker image are templates of the configuration of backend, frontend, and a bind respectively. Feel free to modify it as your needs, according to the parameters of the Data Plane API. Check this: https://www.haproxy.com/documentation/dataplaneapi/latest/

By default these templates will create the following configuration in the ha_proxy server:

```
backend test
  mode tcp
  balance roundrobin
  option redispatch 0
  timeout server 1
  timeout connect 10
  server server10.10.10.1 10.10.10.1:32084 check weight 100
  server server10.10.10.2 10.10.10.2:32084 check weight 100
  server server10.10.10.3 10.10.10.3:32084 check weight 100
```

```
frontend test
  mode tcp
  maxconn 2000
  bind *:32084 name test
  default_backend test
```
Once you have the image, you need a Deployment resource to run harporias. You could use this yaml, modify it as your needs:

```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: harporias
  namespace: test
spec:
  replicas: 1
  selector:
    matchLabels:
      app: harporias
  template:
    metadata:
      labels:
        app: harporias
      annotations:
    spec:
      serviceAccountName: harporias-sa
      containers:
      - image: 127.0.0.1:5000/harporias
        imagePullPolicy: Always
        name: harporias
        env:
          - name: HA_PROXY_API_URL
            value: "http://127.0.0.1"
          - name: HA_PROXY_PORT
            value: "3000"
          - name: HA_PROXY_API_USERNAME
            value: "admin"
          - name: HA_PROXY_API_PASSWORD
            value: "password"
          - name: HA_PROXY_BACKENDS
            value: "10.10.10.1,10.10.10.2,10.10.10.3"
```

There are some env variables in the yaml:

1. HA_PROXY_API_URL  - Is the IP address or DNS name of your ha_proxy server
2. HA_PROXY_PORT - Is the port of your ha_proxy server
3. HA_PROXY_API_USERNAME - Is the username of the Data Plane API
4. HA_PROXY_API_PASSWORD - Is the password of the Data Plane API
5. HA_PROXY_BACKENDS - Are the IP of your k8s workers nodes, where NodePort service are exposed.

##### Dont use plain username/password in the yaml of the deployment (here are for demo purpose), its a security risk. Please, use secrets instead: https://kubernetes.io/docs/concepts/configuration/secret/#using-secrets-as-environment-variables

In orther to watch the NodePort services created by kubernetes, you will need a service account with the appropriate permissions (harporias-sa).

```
apiVersion: v1
kind: ServiceAccount
metadata:
  name: harporias-sa
  namespace: test
  labels:
    app.kubernetes.io/name: test

---

kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: harporias-cr
rules:
- apiGroups: [""]
  resources: ["services"]
  verbs: ["watch"]

---

kind: ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: harporias-crb
subjects:
- kind: ServiceAccount
  name: harporias-sa
  namespace: test
roleRef:
  kind: ClusterRole
  name: harporias-cr
  apiGroup: rbac.authorization.k8s.io
```

Its all, lets deploy harporias

## Deploy harporias

With all the yamls files in place, deploy them with

```
kubectl apply -f harporias-sa.yaml
kubectl apply -f harporias-deployment.yaml
```

## License

MIT License. 
Feel free to fork, modify and distribute harporias.

## Support

If you need support, please open an issue,
I will reply according to my free time.
