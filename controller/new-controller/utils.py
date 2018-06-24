from collections import defaultdict

import time

# Cisco Reference bandwidth = 1 Gbps
REFERENCE_BW = 10000000

DEFAULT_BW = 10000000

class ControllerUtilities(object):

    def __init__(self, adjacency, datapath_list, bandwidths):
        self.adjacency = adjacency
        self.datapath_list = datapath_list         # dicionário cuja chave é o ID do switch e o valor é datapath correspondente
        self.bandwidths = bandwidths

    def getOptimalPaths(self, src, dst):
        # Retorna os 2 primeiros caminhos possiveis
        paths = self.getPaths(src, dst)
        optimal_paths = []

        optimal_paths.append(paths[0])
        optimal_paths.append(paths[1])

        return optimal_paths


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

    def getLinkCost(self, s1, s2):
        '''
        Get the link cost between two switches
        '''
        e1 = self.adjacency[s1][s2]
        e2 = self.adjacency[s2][s1]
        bl = min(self.bandwidths[s1][e1], self.bandwidths[s2][e2])
        ew = REFERENCE_BW/bl
        return ew

    def getPathCost(self, path):
        '''
        Get the path cost
        '''
        cost = 0
        for i in range(len(path) - 1):
            cost += self.getLinkCost(path[i], path[i+1])
        return cost


    def addPortsToPath(self, paths, first_port, last_port):
        '''
        Retorna uma lista com as portas associadas a cada switch no caminho
        '''
        p = {}
        in_port = first_port

        for s1, s2 in zip(path[:-1], path[1:]):
            out_port = self.adjacency[s1][s2]
            p[s1] = (in_port, out_port)
            in_port = self.adjacency[s2][s1]
            p[path[-1]] = (in_port, last_port)

        print('[addPortsToPaths] retornou p = {0}'.format(p))
        return p


    def choosePathAccordingToHeuristic(self, src, dst):
        paths = self.getOptimalPaths(src, dst)

        paths_cost = []

        for path in paths:
            paths_cost.append(self.getPathCost(path))
            print("Caminho: {0} custo = {1}".format(path, paths_cost[len(paths_cost) - 1]))

        print('paths_cost = {0}'.format(paths_cost))

        sum_of_paths_cost = sum(paths_cost) * 1.0

        # De acordo com a heuristica escolhida:
        # 1. Pega o primeiro caminho
        return path[0]

        # 2. Pega caminho randomico
        # 3. Pega caminho com menor numero de hops



    def getBestPath(self, src, dst):
        path = self.choosePathAccordingToHeuristic(src, dst)
        path_with_ports = self.addPortsToPath(path, first_port, last_port)

        # Lista de todos os switches que fazem parte do caminho ótimo
        switches_in_paths = set().union(*paths)

        print('[getBestPath] switches_in_paths = {0}'.format(switches_in_paths))


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
        chosen_path = self.getBestPath()

        exit(1)

        for node in switches_in_paths:
            # Para cada switch que faz parte de algum caminho:
            dp = self.datapath_list[node]
            ofp = dp.ofproto
            ofp_parser = dp.ofproto_parser

            # ports[in_port] = (out_port, custo associado) -> Se entrou pela in_port, pode sair pela out_port com custo X
            ports = defaultdict(list)
            actions = []
            i = 0

            # Para cada caminho entre os caminhos ótimos
            for path in paths_with_ports:
                if node in path:
                    # Se o switch em questão está no caminho ótimo atual, pega portas de entrada e saída do flow
                    in_port = path[node][0]
                    out_port = path[node][1]

                    if (out_port, paths_cost[i]) not in ports[in_port]:
                        ports[in_port].append((out_port, paths_cost[i]))
                i += 1

            # ports{} é um dicionário com chave in_port e o valor associado corresponde
            # a out_port e o custo do caminho que fará ao sair por essa porta.
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

                # out_ports contém as portas pelas quais pode sair e o custo do caminho associado
                out_ports = ports[in_port]

                print("out_ports = {0}".format(out_ports))

                if len(out_ports) == 1:
                    actions = [ofp_parser.OFPActionOutput(out_ports[0][0])]

                    self.add_flow(dp, 32768, match_ip, actions)
                    self.add_flow(dp, 1, match_arp, actions)


        print("Finished in {0}".format(time.time() - computation_start))
        exit(1)
