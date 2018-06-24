from collections import defaultdict

import time

class ControllerUtilities(object):
    def __init__(self, adjacency, datapath_list):
        self.adjacency = adjacency
        self.datapath_list = datapath_list         # dicionário cuja chave é o ID do switch e o valor é datapath correspondente


    def getPaths(self, src, dst):
        '''
        Get all paths from src to dst using DFS algorithm
        '''
        if src == dst:
            # Significa que o host e o destino estão conectados ao mesmo switch.
            return [[src]]

        paths = []
        stack = [(src, [src])]

        while stack:
            (node, path) = stack.pop()
            for next in set(self.adjacency[node].keys()) - set(path):
                if next is dst:
                    paths.append(path + [next])
                else:
                    stack.append((next, path + [next]))

        print("Caminhos disponiveis de {0} para {1}: {2}".format(src, dst, paths))
        return paths


    def addPortsToPaths(self, paths, first_port, last_port):
        '''
        Retorna uma lista com as portas associadas a cada switch nos caminhos
        '''
        paths_p = []

        for path in paths:
            p = {}
            in_port = first_port

            for s1, s2 in zip(path[:-1], path[1:]):
                out_port = self.adjacency[s1][s2]
                p[s1] = (in_port, out_port)
                in_port = self.adjacency[s2][s1]
            p[path[-1]] = (in_port, last_port)
            paths_p.append(p)

        return paths_p


    # Instala todos os caminhos possíveis, de uma só vez.
    def installPaths(self, src, first_port, dst, last_port, ip_src, ip_dst):
        '''
        src = switch de origem
        first_port = porta que conecta o switch de origem ao host de origem
        dst = switch de destino
        last_port = porta que conecta o switch de destino ao host de destino
        ip_src = IP do host de origem
        ip_dst = IP do host de destino
        '''
        computation_start = time.time()
        paths = self.getPaths(src, dst)
        paths_with_ports = self.addPortsToPaths(paths, first_port, last_port)
        pw = []

        for path in paths:
            pw.append(self.get_path_cost(path))
            print("{0} cost = {1}".format(path, pw[len(pw) - 1]))
        sum_of_pw = sum(pw) * 1.0

        # Seleciona todos os switches que estão nos caminhos disponíveis
        switches_in_paths = set().union(*paths)

        for node in switches_in_paths:
            dp = self.datapath_list[node]
            ofp = dp.ofproto
            ofp_parser = dp.ofproto_parser

            ports = defaultdict(list)
            actions = []
            i = 0

            for path in paths_with_ports:
                if node in path:
                    # Se o switch está neste caminho, pega as portas de saída e entrada
                    in_port = path[node][0]
                    out_port = path[node][1]

                    print("pw[{0}] = {1}".format(i, pw[i]))
                    print("ports[] = {0}".format(ports))

                    if (out_port, pw[i]) not in ports[in_port]:
                        ports[in_port].append((out_port, pw[i]))
                i += 1

            print("----------------------")
            exit(1)

            for in_port in ports:
                match_ip = ofp_parser.OFPMatch(
                    eth_type=0x0800,
                    ipv4_src=ip_src,
                    ipv4_dst=ip_dst
                )
                match_arp = ofp_parser.OFPMatch(
                    eth_type=0x0806,
                    arp_spa=ip_src,
                    arp_tpa=ip_dst
                )

                out_ports = ports[in_port]
                # print out_ports

                if len(out_ports) > 1:
                    group_id = None
                    group_new = False

                    if (node, src, dst) not in self.multipath_group_ids:
                        group_new = True
                        self.multipath_group_ids[
                            node, src, dst] = self.generate_openflow_gid()
                    group_id = self.multipath_group_ids[node, src, dst]

                    buckets = []
                    # print "node at ",node," out ports : ",out_ports
                    for port, weight in out_ports:
                        bucket_weight = int(round((1 - weight/sum_of_pw) * 10))
                        bucket_action = [ofp_parser.OFPActionOutput(port)]
                        buckets.append(
                            ofp_parser.OFPBucket(
                                weight=bucket_weight,
                                watch_port=port,
                                watch_group=ofp.OFPG_ANY,
                                actions=bucket_action
                            )
                        )

                    if group_new:
                        req = ofp_parser.OFPGroupMod(
                            dp, ofp.OFPGC_ADD, ofp.OFPGT_SELECT, group_id,
                            buckets
                        )
                        dp.send_msg(req)
                    else:
                        req = ofp_parser.OFPGroupMod(
                            dp, ofp.OFPGC_MODIFY, ofp.OFPGT_SELECT,
                            group_id, buckets)
                        dp.send_msg(req)

                    actions = [ofp_parser.OFPActionGroup(group_id)]

                    self.add_flow(dp, 32768, match_ip, actions)
                    self.add_flow(dp, 1, match_arp, actions)

                elif len(out_ports) == 1:
                    actions = [ofp_parser.OFPActionOutput(out_ports[0][0])]

                    self.add_flow(dp, 32768, match_ip, actions)
                    self.add_flow(dp, 1, match_arp, actions)
        print("Path installation finished in {0}".format(time.time() - computation_start))
        return paths_with_ports[0][src][1]
