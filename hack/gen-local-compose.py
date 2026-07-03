#!/usr/bin/env python3
"""Generate a local docker-compose stack for train-ticket 1.0 from the
quickstart-k8s deployment sample, so images/ports/env wiring stay in sync
with the k8s manifests."""
import yaml

SAMPLE = 'deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy.yaml.sample'
OUT = 'deployment/docker-compose-manifests/local/docker-compose.yml'

MYSQL_HOST, MYSQL_USER, MYSQL_PASS, MYSQL_DB = 'ts-mysql', 'ts', 'Ts_123456', 'ts'

docs = [d for d in yaml.safe_load_all(open(SAMPLE)) if d and d.get('kind') == 'Deployment']

services = {
    'ts-mysql': {
        'image': 'mysql:5.7',
        # utf8 (3-byte), not utf8mb4: the services create MyISAM tables with
        # varchar(255) primary keys, and 255*4 bytes would exceed MyISAM's
        # 1000-byte index key limit, failing DDL (and the data-seeding
        # CommandLineRunners) at startup.
        'command': ['--max_connections=1000', '--character-set-server=utf8',
                    '--collation-server=utf8_general_ci'],
        'environment': {
            'MYSQL_ROOT_PASSWORD': MYSQL_PASS,
            'MYSQL_DATABASE': MYSQL_DB,
            'MYSQL_USER': MYSQL_USER,
            'MYSQL_PASSWORD': MYSQL_PASS,
        },
        'healthcheck': {
            'test': ['CMD-SHELL', 'mysqladmin ping -h 127.0.0.1 -u root -p$$MYSQL_ROOT_PASSWORD'],
            'interval': '10s', 'timeout': '5s', 'retries': 30,
        },
        'mem_limit': '1g',
        'restart': 'unless-stopped',
        'networks': ['trainticket'],
    },
    'nacos': {
        'image': 'nacos/nacos-server:v2.1.0',
        'environment': {
            'MODE': 'standalone',
            'NACOS_AUTH_ENABLE': 'false',
            'JVM_XMS': '512m', 'JVM_XMX': '512m', 'JVM_XMN': '256m',
        },
        'ports': ['8848:8848'],
        'healthcheck': {
            'test': ['CMD-SHELL', 'curl -sf http://127.0.0.1:8848/nacos/v1/console/health/readiness'],
            'interval': '10s', 'timeout': '5s', 'retries': 30, 'start_period': '30s',
        },
        'mem_limit': '1g',
        'restart': 'unless-stopped',
        'networks': ['trainticket'],
    },
    'rabbitmq': {
        'image': 'rabbitmq:3.10',
        'healthcheck': {
            'test': ['CMD', 'rabbitmq-diagnostics', '-q', 'ping'],
            'interval': '15s', 'timeout': '10s', 'retries': 20, 'start_period': '30s',
        },
        'mem_limit': '512m',
        'restart': 'unless-stopped',
        'networks': ['trainticket'],
    },
}

for d in docs:
    name = d['metadata']['name']
    c = d['spec']['template']['spec']['containers'][0]
    port = c['ports'][0]['containerPort']
    env = {}
    depends = {}
    needs_nacos = needs_rabbit = False
    mysql_prefix = None
    for ef in c.get('envFrom', []):
        if 'configMapRef' in ef:
            if ef['configMapRef']['name'] == 'nacos':
                needs_nacos = True
            elif ef['configMapRef']['name'] == 'rabbitmq':
                needs_rabbit = True
        if 'secretRef' in ef:
            sec = ef['secretRef']['name']          # ts-<short>-mysql
            short = sec[len('ts-'):-len('-mysql')]
            mysql_prefix = short.replace('-', '_').upper()

    if needs_nacos:
        env['NACOS_ADDRS'] = 'nacos:8848'
        depends['nacos'] = {'condition': 'service_healthy'}
    if needs_rabbit:
        env['rabbitmq_host'] = 'rabbitmq'
        depends['rabbitmq'] = {'condition': 'service_healthy'}
    if mysql_prefix:
        env[f'{mysql_prefix}_MYSQL_HOST'] = MYSQL_HOST
        env[f'{mysql_prefix}_MYSQL_PORT'] = '3306'
        env[f'{mysql_prefix}_MYSQL_DATABASE'] = MYSQL_DB
        env[f'{mysql_prefix}_MYSQL_USER'] = MYSQL_USER
        env[f'{mysql_prefix}_MYSQL_PASSWORD'] = MYSQL_PASS
        depends['ts-mysql'] = {'condition': 'service_healthy'}

    svc = {
        'image': c['image'],
        'restart': 'unless-stopped',
        'mem_limit': '700m',
        'networks': ['trainticket'],
        'healthcheck': {
            'test': ['CMD-SHELL', f'bash -c "exec 3<>/dev/tcp/127.0.0.1/{port}" || exit 1'],
            'interval': '15s', 'timeout': '5s', 'retries': 40, 'start_period': '60s',
        },
    }
    if env:
        svc['environment'] = env
    if depends:
        svc['depends_on'] = depends

    if name == 'ts-ui-dashboard':
        svc['ports'] = ['8080:8080']
        svc['mem_limit'] = '256m'
        svc['depends_on'] = {'ts-gateway-service': {'condition': 'service_started'}}
    elif name == 'ts-gateway-service':
        svc['ports'] = ['18888:18888']
    elif name == 'ts-avatar-service':
        svc['mem_limit'] = '512m'

    services[name] = svc

compose = {
    'name': 'train-ticket',
    'services': services,
    'networks': {'trainticket': {'driver': 'bridge'}},
}

class Dumper(yaml.SafeDumper):
    pass

def str_presenter(dumper, data):
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

Dumper.add_representer(str, str_presenter)

header = (
    "# Local docker-compose deployment of train-ticket 1.0 (all services).\n"
    "# GENERATED from deployment/kubernetes-manifests/quickstart-k8s/yamls/deploy.yaml.sample\n"
    "# by hack/gen-local-compose.py -- edit that script, not this file.\n"
    "# Usage: see deployment/docker-compose-manifests/local/README.md (use up.sh, not a bare 'up').\n"
)
with open(OUT, 'w') as f:
    f.write(header)
    yaml.dump(compose, f, Dumper=Dumper, sort_keys=False, default_flow_style=False, width=120)
print(f'wrote {OUT} with {len(services)} services')
