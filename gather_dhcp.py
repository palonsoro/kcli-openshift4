import sys
import yaml

paramfile = sys.argv[1]


def get_values(data, element, field):
    results = []
    if '%s_%s' % (element, field) in data:
        new = data['%s_%s' % (element, field)]
        results.extend(new)
    return results


with open(paramfile) as entries:
    data = yaml.safe_load(entries)
    cluster = data.get('cluster', 'testk')
    masters = data.get('masters', 1)
    workers = data.get('workers', 0)
    bootstrap_name = "%s-bootstrap" % cluster
    bootstrap_mac = data.get('bootstrap_mac')
    bootstrap_ip = data.get('bootstrap_ip')
    dhcp_ip = data.get('dhcp_ip')
    dhcp_netmask = data.get('dhcp_netmask')
    dhcp_gateway = data.get('dhcp_gateway')
    dhcp_dns = data.get('dhcp_dns')
    if bootstrap_mac is None or bootstrap_ip is None or dhcp_ip is None or dhcp_netmask is None\
            or dhcp_gateway is None or dhcp_dns is None:
        print("")
        sys.exit(0)
    master_names = ['%s-master-%s' % (cluster, num) for num in range(masters)]
    worker_names = ['%s-worker-%s' % (cluster, num) for num in range(workers)]
    node_names = master_names + worker_names
    master_macs = get_values(data, 'master', 'macs')
    worker_macs = get_values(data, 'worker', 'macs')
    node_macs = master_macs + worker_macs
    master_ips = get_values(data, 'master', 'ips')
    worker_ips = get_values(data, 'worker', 'ips')
    node_ips = master_ips + worker_ips
    if node_macs and node_ips and len(node_macs) == len(node_ips) and len(node_names) == len(node_macs):
        nodes = len(node_macs)
        node_names.insert(0, bootstrap_name)
        node_names = ','.join(node_names)
        node_macs.insert(0, bootstrap_mac)
        node_macs = ','.join(node_macs)
        node_ips.insert(0, bootstrap_ip)
        node_ips = ','.join(node_ips)
        results = " -P node_macs=[%s] -P node_ips=[%s] -P nodes=%s" % (node_macs, node_ips, nodes)
        print(results)