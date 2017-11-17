#!/usr/bin/python3.6
import consul
import time
from subprocess import getoutput
from subprocess import getstatusoutput
from subprocess import Popen
import json
import argh
c = consul.Consul()


localcost = 2
defaul_node_status_dict = {'node': None,
                           'cost': 1, 'role': None, 'status': None}


class dhcp_failower():
    def __init__(self):
        self.iam = self.whoiam()
        self.now_node_list = dict()
        self.prev_node_list = dict()

    def isconsulup(self):
        """Checks the status of the consul, if not available, then tries to restart it"""
        self.consulstatus = 4
        while self.consulstatus > 2:
            try:
                self.master = c.kv.get('master')[1]['Value']
            except:
                self.systemd('consul', 'restart')
                time.sleep(3)
                self.consulstatus = self.consulstatus - 1
            else:
                self.consulstatus = 1
        return self.consulstatus


    def whoiam(self):
        """Return node name as str"""
        self.iam = c.agent.self()['Member']['Name']
        return self.iam

    def systemd(self, service, action):
        """Is user for work with systemd units.
        Sends command to systemctl. I' can't find good module for systemd
        """
        unitstatus = None
        if action == 'restart':
            Popen('systemctl ' + 'restart ' + service + '.service', shell=True)
        elif action == 'stop':
            Popen('systemctl ' + 'stop ' + service + '.service', shell=True)
        elif action == 'start':
            Popen('systemctl ' + 'start ' + service + '.service', shell=True)
        elif action == 'status':
            unitstatus = getstatusoutput(
                'systemctl ' + 'status ' + service + '.service')[0]
            return unitstatus

    def check(self, host, role):
        """Receives checks data from consul and return dict.
        Host can be dhcp.iam or other host from dhcp.node_status_list().
        Role can be 'master' or 'standby'
        """
        self.members = c.agent.members()
        status = []
        for i in self.members:
            if i['Name'] == host and role == 'master':
                checks = c.health.node(host)[1]
                status.append(all(j['Status'] == 'passing' for j in checks))
                checks_dict = dict()
                for i in checks[1::]:
                    checks_dict[i['ServiceID']] = i['Status']
                status.append(checks_dict)

            elif i['Name'] == host and role == 'standby':
                checks = c.health.node(host)[1]
                for j in checks:
                    if j['ServiceID'] in ('kea', 'dhcp-client-test'):
                        checks.remove(j)
                status.append(all(j['Status'] == 'passing' for j in checks))
                checks_dict = dict()
                for i in checks[1::]:
                    checks_dict[i['ServiceID']] = i['Status']
                status.append(checks_dict)
        return status

    def node_status_get(self, node):
        """Get node status dict from consul"""
        node_status_dict = c.kv.get('dhcp/nodes/{}'.format(node))[1]
        if node_status_dict:
            node_status_dict = json.loads(node_status_dict['Value'].decode())
        return node_status_dict

    def node_status_put(self, node, node_status_dict):
        """Put node status dict in consul"""
        c.kv.put('dhcp/nodes/{}'.format(node), json.dumps(node_status_dict))

    def node_status_list(self):
        """Get list of nodes in cluster """
        node_status_list = [x['Key'].split(
            '/')[2] for x in c.kv.get('dhcp/nodes', recurse=True)[1]]
        return node_status_list


    def dhcp_cluster_status(self, action, status=None):
        if action == 'get':
            status = c.kv.get('dhcp/status')[1]['Value'].decode('utf-8')
            return status
        elif action == 'put':
            c.kv.put('dhcp/status', status)

    def tik(self):
        """Send date to consul. Need to determine if a node is alive or not.
        If node not alive, he don't send any date"""
        c.kv.put("dhcp/tiks/{}".format(self.iam), str(time.time()))

    def repair(self, checks_dict, role):
        """Trying repair node. Check dict can be recived from dhcp.check(), 
        role must be 'master' or standby'"""
        if role == 'master':
            print('Checking master')
            '''
            проверяем:
            dhcp-client-test
            gateway
            kea
            postgres
            '''
            if checks_dict['postgres'] != 'passing':
                print('The problem with postgres...')
                proxy = self.systemd('stolon-proxy', 'status')
                keeper = self.systemd('stolon-keeper', 'status')
                sentinel = self.systemd('stolon-sentinel', 'status')

                def a(x): return 'OK' if x == 0 else 'BOK'
                print('''Stolon services status
                proxy {:>5}
                keeper {:>4}
                sentinel {:>1}
                '''.format(a(proxy), a(keeper), a(sentinel))
                      )
                if proxy != 0:
                    self.systemd('stolon-proxy', 'restart')
                elif keeper != keeper:
                    self.systemd('stolon-keeper', 'restart')
                elif keeper != keeper:
                    self.systemd('stolon-sentinel', 'restart')

            # or checks_dict['dhcp-client-test'] != 'passing':
            elif checks_dict['kea'] != 'passing':
                print('kea BOK')

                def a(x): return 'OK' if x == 'active' else 'BOK'
                print('Killing kea services')
                Popen('pkill -9 kea', shell=True)
                print('runing dhcp')
                Popen('/sbin/keactrl start', shell=True)
                time.sleep(1)
                Popen('/sbin/keactrl start', shell=True)
                time.sleep(3)
                dhcpstatus = getoutput('keactrl status').split()
                print('''суть:
                dhcp4 {:>5}
                dhcp6 {:>5}
                '''.format(a(dhcpstatus[2]), a(dhcpstatus[5])))
        else:
            print('Checking standby')
            if checks_dict['postgres'] != 'passing':
                print('The problem with postgres...')
                proxy = self.systemd('stolon-proxy', 'status')
                keeper = self.systemd('stolon-keeper', 'status')
                sentinel = self.systemd('stolon-sentinel', 'status')

                def a(x): return 'OK' if x == 0 else 'BOK'
                print('''Stolon services status
                proxy {:>5}
                keeper {:>4}
                sentinel {:>1}
                '''.format(a(proxy), a(keeper), a(sentinel))
                      )
                if proxy != 0:
                    self.systemd('stolon-proxy', 'restart')
                elif keeper != keeper:
                    self.systemd('stolon-keeper', 'restart')
                elif keeper != keeper:
                    self.systemd('stolon-sentinel', 'restart')

    def elect_master(self):
        """Electing master from nodelist """
        members = dict()
        for node in self.node_status_list():
            node_status_dict = self.node_status_get(node)
            if node_status_dict['status'] == True:
                members[node] = node_status_dict['cost']
        print("Healthy cluster members: {}".format(members))
        self.dhcp_cluster_status('put', status='election')
        print('Start master electtion')
        if len(members) != 0:
            master = min(members, key=members.get)
            print('new master {}'.format(master))
            node_status_dict = self.node_status_get(master)
            node_status_dict['role'] = 'master'
            self.node_status_put(master, node_status_dict)
        else:
            print('no healthy nodes')

    def dhcp_node_init(self):
        """ Init node in cluster"""
        print('I am new node in cluster, initialized...')
        status = self.check(self.whoiam(), 'standby')
        cost = 1 + localcost
        node_status_dict = defaul_node_status_dict
        node_status_dict['cost'] = cost
        node_status_dict['status'] = status[0]
        node_status_dict['role'] = 'standby'
        node_status_dict['node'] = self.iam
        self.node_status_put(self.iam, node_status_dict)

    def monkeybusiness(self):
        """Main worker"""
        if self.isconsulup() == True:
            if not self.node_status_get(self.iam):
                self.dhcp_node_init()
            # consul is up we'r beggining main loop
            else:
                if dhcp.node_status_get(dhcp.iam) == None:
                    dhcp.dhcp_node_init()
                status = dhcp.node_status_get(dhcp.iam)
                role = status['role']
                check = self.check(self.iam, role)

                if role == 'master':
                    print("I'm master")
                    if check[0] != True:
                        print("I'm master, my status is False, try repair")
                        self.repair(check[1], role)
                        time.sleep(5)
                        newcheck = self.check(self.iam, role)
                        if newcheck[0] != True:
                            print("repair failed")
                            status['status'] = False
                            status['role'] = 'standby'
                            print("My new status: {}".format(status))
                            self.node_status_put(self.iam, status)
                            self.dhcp_cluster_status('put', 'election')

                elif role == 'standby':
                    print("I'm standby")

                    if len(getoutput("pgrep kea")) != 0:
                        print("I'm standby, but kea is running. Kill all kea")
                        Popen('pkill -9 kea', shell=True)

                    if check[0] != True:
                        print("I'm standby, my status is False, try repair")
                        self.repair(check[1], role)
                        time.sleep(5)
                        newcheck = self.check(self.iam, role)
                        print("Second check: {}".foramt(newcheck))
                        if newcheck[0] != True:
                            print("repair failed")
                            status['status'] = False
                            status['role'] = 'standby'
                            print("My new status: {}".format(status))
                            self.node_status_put(self.iam, status)
                    elif check[0] == True:
                        print("I'm OK")
                        status['status'] = True
                        self.node_status_put(self.iam, status)

                    master = [self.node_status_get(x) for x in self.node_status_list(
                    ) if self.node_status_get(x)['role'] == 'master']

                    if len(master) == 0:
                        print('no master, begin election')
                        self.elect_master()

                    elif len(master) > 1:
                        print("To many masters!")

                    elif master[0]['status'] != True:
                        print('Master failed status: {}'.fromat(master))
                        self.elect_master()
        else:
            print("Consul is dead")
        self.tik()

    def diag(self):
        if self.isconsulup() != 1:
            print("consul is dead, no cluster, please try repair it!")
        else:
            print("i am {}\n".format(self.iam))
            nodes = self.node_status_list()
            print("Nodes in cluster: {}\n".format(nodes))
            for node in nodes:
                print("""{}
                ckuster data: {}
                check: {}\n"""
                      .format(node, self.node_status_get(node), self.check(node, self.node_status_get(node)['role'])))

    def re_init(self):
        c.kv.delet('dhcp', recurse=True)

    def kill_unhealthy(self):
        node_list = self.node_status_list()
        if len(node_list) >= 1:
            for node in node_list:
                self.now_node_list[node] = c.kv.get(
                    'dhcp/tiks/{}'.format(node))[0]
            kills = list(dict(set(dhcp.prev_node_list.items()) &
                              set(dhcp.now_node_list .items())).keys())
            for kill in kills:
                print(kill)
                c.kv.delete('dhcp/nodes/{}'.format(kill))
            self.prev_node_list = self.now_node_list.copy()


dhcp = dhcp_failower()





if __name__ == "__main__":
   
    def diag():
        dhcp.diag()


    def daemon():
        while True:
            dhcp.monkeybusiness()
            time.sleep(5)
            dhcp.monkeybusiness()
            time.sleep(5)
            dhcp.kill_unhealthy()

    parser = argh.ArghParser()
    parser.add_commands([diag, daemon])
    parser.dispatch()
