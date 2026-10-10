"""Comparable weighted searches with a consistent, dimensionally valid heuristic."""
import heapq
import math
import time
from collections import deque
if __package__:
    from .data import EDGES,NODES,PROFILES,haversine
    from .prediction import predict
else:
    from data import EDGES,NODES,PROFILES,haversine
    from prediction import predict

def build_graph(state,emergency='urgent'):
    graph={n:[] for n in NODES}
    weighted={}
    settings=state['settings']
    for edge in EDGES:
        override=state['roads'].get(edge['id'],{})
        if override.get('closed'):
            continue
        congestion=override.get('congestion',PROFILES[settings['traffic']][edge['corridor']])
        minutes,source=predict(edge,settings,congestion)
        penalty=edge['rough']*(.8 if emergency=='critical' else .25)
        value={**edge,'minutes':minutes,'penalty':penalty,'cost':minutes+penalty,'congestion':congestion,'prediction_source':source}
        weighted[edge['id']]=value
        graph[edge['a']].append((edge['b'],value));graph[edge['b']].append((edge['a'],value))
    lower=min((e['cost']/haversine(NODES[e['a']],NODES[e['b']]) for e in weighted.values()),default=0)
    return graph,weighted,lower

def search(bundle,start,end,algorithm='astar',objective='cost'):
    graph,weighted,lower=bundle
    started=time.perf_counter()
    previous={};best={start:0.};expanded=0
    if algorithm=='bfs':
        queue=deque([start]);seen={start}
        while queue:
            node=queue.popleft();expanded+=1
            if node==end:break
            for nxt,e in graph.get(node,[]):
                if nxt not in seen:
                    seen.add(nxt);previous[nxt]=(node,e);best[nxt]=best[node]+1;queue.append(nxt)
    else:
        scale=lower if objective=='cost' else min((e[objective]/haversine(NODES[e['a']],NODES[e['b']]) for e in weighted.values()),default=0)
        heuristic=lambda n: haversine(NODES[n],NODES[end])*scale if algorithm=='astar' else 0
        heap=[(heuristic(start),0.,start)]
        while heap:
            _,cost,node=heapq.heappop(heap)
            if cost>best[node]+1e-12:continue
            expanded+=1
            if node==end:break
            for nxt,e in graph.get(node,[]):
                new=cost+e[objective]
                if new<best.get(nxt,math.inf)-1e-12:
                    best[nxt]=new;previous[nxt]=(node,e);heapq.heappush(heap,(new+heuristic(nxt),new,nxt))
    if end not in best:return None
    nodes=[end];roads=[];minutes=km=cost=penalty=0.
    while nodes[-1]!=start:
        parent,e=previous[nodes[-1]]
        nodes.append(parent);roads.append(e['id']);minutes+=e['minutes'];km+=e['km'];cost+=e['cost'];penalty+=e['penalty']
    return {'nodes':nodes[::-1],'roads':roads[::-1],'minutes':minutes,'km':km,'cost':cost,'penalty':penalty,
            'expanded':expanded,'runtime_ms':(time.perf_counter()-started)*1000,'algorithm':algorithm}

def compare(bundle,start,end):
    rows=[]
    for algorithm,objective,label in [('astar','cost','A*'),('dijkstra','cost','Dijkstra'),('bfs','cost','BFS / fewest roads'),('dijkstra','km','Shortest distance')]:
        result=search(bundle,start,end,algorithm,objective)
        if result:rows.append({**result,'label':label,'cost_min':result['cost']})
    return rows
