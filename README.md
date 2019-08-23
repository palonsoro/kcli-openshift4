This repo provides a way for deploying ocp4 using an alternative approach to ipi, and by heavily leveraging kcli.

It's of course not supported in anyway by Red Hat.

The initial target is ovirt/rhev and libvirt although the approach aims to be independent of the platform.

This was also tested on kubevirt, openstack, aws and gcp.

The main features are:

- No need to control dns. Those elements are hosted as static pods on the master nodes. (For cloud platforms, we do use cloud public dns)
- Easily customize the vms.
- Multiple clusters can live on the same network.
- Single procedure for libvirt, ovirt, openstack or kubevirt.
- No need to compile the installer
- No need to tweak libvirtd.
- Vms can be connected to a real bridge

## Requirements

- openshift-install binary installed (get it at https://mirror.openshift.com/pub/openshift-v4/clients/ocp)
- valid pull secret
- ssh public key
- kcli >= 14.12 (container or pip version if deploying on something else than libvirt)
- direct access to the deployed vms. Use something like this otherwise `sshuttle -r your_hypervisor 192.168.122.0/24 -v`)
- Target platform needs:
  - rhcos image ( *kcli download rhcosootpa* ). To test latest image, use instead *kcli download rhcoslatest* and set template variable in your parameter file
  - centos image ( *kcli download centos7* )
- For libvirt, support for fw_cfg in qemu (install qemu-kvm-ev on centos for instance)
- Target platform needs ignition support. 
  - For ovirt/rhv, this either requires ovirt >= 4.3.4
- On openstack, you will need to create a network with port security disabled (as we need a vip to be reachable on the masters). You will also need to create a port on this network and map it to a floating ip. Put the corresponding api_ip, dns_ip and public_api_ip in your parameter file. You can use [openstack.sh.sample](openstack.sh.sample) as a starting point. Finally, you will need to open relevant ports (80, 443, 6443 and 22623) in your security groups.
- If defining yourself the vip to use, make sure it's excluded from your dhcp server.

## How to Use

### Setting your environment

if you create a file called *env.sh*, it will be sourced during deployment. You can put a specific kcli alias there if you're using the container version, or otherwise let the deployment script figure out the alias to use.

You can either use default values that can be checked in the parameters section of the file `ocp.yml` or by running `kcli plan -i ocp.yml`

If you want to tweak them, create a parameter file similar to [*parameters.yml.sample*](parameters.yml.sample) and edit:

- *cluster* name. Defaults to `testk`
- *domain* name. For cloud platforms, it should point to a domain name you have access toº. `Defaults to karmalabs.com`
- *pub_key* location. Defaults to `$HOME/.ssh/id_rsa.pub`
- *pull_secret* location. Defaults to `./openshift_pull.json`
- *template* rhcos template to use (should be an openstack one for ovirt/openstack and qemu for libvirt/kubevirt or on ovirt with ignition hook).
- *helper_template* which template to use when deploying temporary vms (defaults to `CentOS-7-x86_64-GenericCloud.qcow2`)
- *helper_sleep*. Defaults to `15`. Number of seconds to wait when deploying the bootstrap helper node on openstack/kubevirt before sshing into it
- *masters* number of masters. Defaults to `1`
- *workers* number of workers. Defaults to `1`
- *network*. Defaults to `default`
- *master_memory*. Defaults to `8192Mi`
- *worker_memory*. Defaults to `8192Mi`
- *bootstrap_memory*. Defaults to `4096Mi`
- *numcpus*. Defaults to `4`
- *disk size* default disk size for final nodes. Defaults to `30Gb`
- *extra_disk* whether to create a secondary disk (to use with rook, for instance). Defaults to `false`
- *extra\_disk_size* size for secondary disk. Defaults to `30Gb`
- *use_br* whether to create a bridge on top of the nics of the nodes (useful if planning to deploy kubevirt on top). Defaults to `false`
- *api_ip* the ip to use for api ip. Defaults to `none`, in which case a temporary vm will be launched to gather a free one.
- *dns_ip* the ip to use for dns ip. Defaults to `none`, in which case a temporary vm will be launched to gather a free one.

### Deploying

- `./ocp.sh` or `ocp.sh your_parameter_file` if you have created one.

- You will be asked for your sudo password in order to create a /etc/hosts entry for the api vip.

- once that finishes, set the following environment variable in order to use oc commands `export KUBECONFIG=clusters/$cluster/auth/kubeconfig`

- for dns access to your app, you can create a conf file in /etc/NetworkManager/dnsmasq.d with the following line `server=/apps.$cluster.$domain/$api_ip` where api_ip is displayed during the install and added to your /etc/hosts

### Adding more workers

- with default settings, relaunch the plan with `kcli plan -f ocp.yml -P workers=new_number_of_workers -P scale=true $cluster`
- with a parameters file, relaunch the plan with `kcli plan -f ocp.yml -P workers=new_number_of_workers -P scale=true --paramfile=your_parameter_file $cluster`

### Using a custom openshift image

You can put the following lines in your *env.sh* to achieve this:

```
export PULL_SECRET="xxx"
export PATH=.:$PATH
export OPENSHIFT_RELEASE_IMAGE="registry.svc.ci.openshift.org/ocp/release:4.2"
oc adm release extract --registry-config $PULL_SECRET --command=openshift-install --to . $OPENSHIFT_RELEASE_IMAGE
```

### Cleaning up an install

if you named your cluster xx, the following will delete all the vms and the generated directory 

```
cluster=xx ; kcli plan -d $cluster --yes; rm -rf clusters/$cluster
```

## architecture

### On ovirt/libvirt/kubevirt

We deploy :

- an arbitrary number of masters.
- an arbitrary number of workers.
- a bootstrap node removed during the install.
- on kubevirt, an additional bootstrap helper node removeed during the install. It serves ignition data to the bootstrap node, as the field used to store userdata can't handle the many caracters of the bootstrap ignition file.

We first generate all the ignition files needed for the install.

Then, if no api ip has been specified, we do a temporary deployment of a single vm using a centos7 template to gather a free ip.

We then launch the deployment

Keepalived and Coredns with mdns are created on the fly on the bootstrap and master nodes as static pods. Initially, the api vip runs on the bootstrap node.

Nginx is created as static pod on the bootstrap node to serve as a http only web server for some additional ignition files needed on the nodes and which can't get injected (they are generated on the bootstrap node).

Haproxy is created as static pod on the master nodes to load balance traffic to the routers. When there are no workers, routers are instead scheduled on the master nodes and the haproxy static pod isn't created, so routers are simply accessed through the vip without load balancing in this case.

Once bootstrap step is finished, the corresponding vm gets deleted, causing keepalived to migrate the api vip to one of the masters.

Also note that for bootstrap, masters and workers nodes, we merge the ignition data generated by the openshift installer with the ones generated by kcli, in particular we prepend dns server on those nodes to point to our keepalived vip, force hostnames and inject static pods.

### On aws/gcp

On those platform, we can't host a private vip on the nodes, so we rely exclusively on dns (with no load balancing at the moment)

For aws, you can use the rhcos-* ami images

For gcp, you will need to get the rhcos image, move it to a google bucket and import the image (this will soon be automated in kcli download)

An extra temporary node is deployed to serve ignition data to the bootstrap node, as those platforms use userdata field to pass ignition, and the bootstrap has too many characters.

Additionally, we automatically create the following dns records:

- api.$cluster.$domain initially pointing to the public ip of the bootstrap node, and later on changed to point to the public ip of the first master node
- *.apps.$cluster.$domain pointing to the public ip of the first master node ( or the first worker node if present)
- etcd-$num and default fqdn entries pointing to the private ip for the corresponding masters
- the proper srv dns entries.