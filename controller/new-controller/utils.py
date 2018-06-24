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

        print("paths_with_ports = {0}".format(paths_with_ports))
        exit(1)
