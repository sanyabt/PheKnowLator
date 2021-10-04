'''
Author: Sanya B Taneja
Date: 2021-09-29

KG path search functions to generate and save paths:
1. Single source shortest path: save_k_single_source_shortest_paths(G, source, k, filepath)
2. Bidirectional shortest path: get_bidirectional_shortest_paths(G, source, target)
3. k shortest paths: get_k_shortest_paths(G, source, target, k, weight='weight'), 
4. k simple paths (nodes and edges), with and without cutoff: 
	get_k_simple_paths(G, source, target, k, cutoff)
	save_k_simple_paths(G, source, target, k, cutoff, filepath)
5. print_graph_statistics(nx_graph): number of nodes, edges, average degree and density
'''

import os
import os.path
import networkx as nx
import json
import urllib
import traceback
from itertools import islice
from rdflib import Graph, URIRef, BNode, Namespace, Literal
from rdflib.namespace import RDF, OWL
from tqdm import tqdm

import pickle
import pandas as pd
import numpy as np
#import pheknowlator kg_utils 
import sys
sys.path.append('../')
from pkt_kg.utils import *

combine_graph = True
#change graph names and paths
KG_PATH = '/home/sanya/PheKnowLator/resources/knowledge_graphs/'
MR_PATH = '/home/sanya/PheKnowLator/machine_read/'
KG_NAME = 'PheKnowLator_v2.1.0_full_instance_inverseRelations_OWLNETS_NetworkxMultiDiGraph.gpickle'
MR_GRAPH_NAME = 'machineread_greentea_version1_belief.gpickle'
NodeLabelsFile = KG_PATH + 'nodeLabels_20210924.pickle'
DIR_OUT = '/home/sanya/PheKnowLator/output_files/'

#define namespaces
obo = Namespace('http://purl.obolibrary.org/obo/')
napdi = Namespace('http://napdi.org/napdi_srs_imports:')

#read nodeLabels dictionary
with open(NodeLabelsFile, 'rb') as filep:
	nodeLabels = pickle.load(filep)

def save_k_single_source_shortest_paths(G, source, k, filepath):
	paths = nx.single_source_shortest_path(G, source)
	#if returned paths are dictionary
	count = 0
	file_save = open(filepath, 'w')
	print('Saving path from {}'.format(str(source)))
	for target, node_list in paths.items():
		count += 1
		if target != source:
			if str(target) not in nodeLabels:
				target_label = str(target).split('/')[-1]
			else:
				target_label = nodeLabels[str(target)]
			file_save.write('\n{} - {} Path:\n'.format(str(source).split('/')[-1], target_label))
			path_labels = get_path_labels(node_list)
			for triples in path_labels:
				for item in triples:
					file_save.write(str(item)+' ')
				file_save.write('\n')
		if count == k:
			break
	file_save.close()

def get_bidirectional_shortest_paths(G, source, target):
	print('Searching for path from {} - {}'.format(str(source), str(target)))
	pathx = nx.bidirectional_shortest_path(G, source, target)

	path_labels = get_path_labels(pathx)
	for triples in path_labels:
		print(triples)

def get_k_simple_paths(G, source, target, k, cutoff):
	print('Searching for paths from {} - {}'.format(str(source), str(target)))
	paths = nx.all_simple_edge_paths(G, source, target, cutoff=cutoff)
	path_l = []
	path_n = []
	i = 0
	while i<k:
		try:
			print('[info] applying next operator to search for a simple path of max length {}'.format(cutoff))
			path = next(paths)
		except StopIteration:
			break
		print('[info] Simple path found of length {}'.format(len(path))) 
		if len(path) > cutoff:
			print('[info] Simple path length greater than shortest path length ({}) so adding to results'.format(cutoff))
			path_l.append(path)
		i += 1
	
	for path in path_l:
		triple_list = []
		for triple in path:
			subj_lab = ''
			pred_lab = ''
			obj_lab = ''
			subj = str(triple[0])
			pred = str(triple[2])
			obj = str(triple[1])
			if subj in nodeLabels:
				subj_lab = nodeLabels[subj]
			if obj in nodeLabels:
				obj_lab = nodeLabels[obj]
			if pred in nodeLabels:
				pred_lab = nodeLabels[pred]
			triple_labels = (subj_lab, pred_lab, obj_lab)
			triple_list.append(triple_labels)
		path_n.append(triple_list)
	return path_l, path_n

def get_k_shortest_paths(G, source, target, k, weight='weight'):
	#print()
	return list(islice(nx.all_shortest_paths(G, source, target, weight=weight), k))

def save_k_shortest_paths(G, source, target, k, filepath, weight='weight'):
	paths = get_k_shortest_paths(G, source, target, k, weight='weight')
	#print()
	file_save = open(filepath, 'w')
	source = str(source)
	target = str(target)
	source_label = source
	target_label = target
	if source in nodeLabels:
		source_label = nodeLabels[source]
	if target in nodeLabels:
		target_label = nodeLabels[target]
	file_save.write('\n{} - {} Shortest Path:\n'.format(source_label, target_label))
	i = 0
	for node_list in paths:
		file_save.write('\nPATH: '+str(i)+'\n')
		path_labels = get_path_labels(node_list)
		for triples in path_labels:
			for item in triples:
				file_save.write(str(item)+' ')
			file_save.write('\n')
		i += 1
	file_save.close()

def save_k_simple_paths(G, source, target, k, cutoff, filepath):
	path_l, path_n = get_k_simple_paths(G, source, target, k, cutoff)
	source = str(source)
	target = str(target)
	#print()
	file_save = open(filepath, 'w')
	
	if source in nodeLabels:
		source_label = nodeLabels[source]
	if target in nodeLabels:
		target_label = nodeLabels[target]
	file_save.write('\n{} - {} Simple Path (cutoff= {} ):\n'.format(source_label, target_label, cutoff))
	i = 0
	for path_list in path_n:
		file_save.write('\nPATH: '+str(i)+'\n')
		for triples in path_list:
			for item in triples:
				file_save.write(str(item)+' ')
			file_save.write('\n')
		i += 1
	file_save.close()

def get_path_labels(nx_graph, path):
	path_labels = []
	if len(path) < 1:
		print('Path length 1, skipping')
		return
	for edge in zip(path, path[1:]):
		data = nx_graph.get_edge_data(*edge)
		pred = list(data.keys())[0]
		node1_lab = str(edge[0])
		node2_lab = str(edge[1])
		if node1_lab in nodeLabels:
			node1_lab = nodeLabels[node1_lab]
		if node2_lab in nodeLabels:
			node2_lab = nodeLabels[node2_lab]
		pred_lab = nodeLabels[str(pred)]
		if list(data.values())[0]:
			if 'source_graph' in list(data.values())[0]:
				source_graph = 'machine_read'
			else:
				source_graph = ''
		else:
			source_graph = ''
		labels = [node1_lab, pred_lab, node2_lab, source_graph]
		path_labels.append(labels)
	return path_labels

def get_path_uri(nx_graph, path):
	path_uri = []
	if len(path) < 1:
		print('Path length 1, skipping')
		return
	for edge in zip(path, path[1:]):
		data = nx_graph.get_edge_data(*edge)
		pred = list(data.keys())[0]
		attribute = list(data.values())
		uri = [str(edge[0]), pred, str(edge[1]), attribute]
		path_uri.append(uri)
	return path_uri

def print_graph_statistics(nx_graph):
	# get the number of nodes, edges, and self-loops
	nodes = nx.number_of_nodes(nx_graph)
	edges = nx.number_of_edges(nx_graph)
	self_loops = nx.number_of_selfloops(nx_graph)

	print('There are {} nodes, {} edges, and {} self-loop(s)'.format(nodes, edges, self_loops))
	# get degree information
	avg_degree = float(edges) / nodes

	print('The Average Degree is {}'.format(avg_degree))
	# get 5 nodes with the highest degress
	n_deg = sorted([(str(x[0]), x[1]) for x in  nx_graph.degree], key=lambda x: x[1], reverse=1)[:6]

	for x in n_deg:
		print('{} (degree={})'.format(x[0], x[1]))
	# get network density
	density = nx.density(nx_graph)

	print('The density of the graph is: {}'.format(density))

if __name__ == '__main__':
	
	#read pheknowlator graph
	print('Loading PheKnowLator graph')
	pl_kg = nx.read_gpickle(KG_PATH+KG_NAME)
	#read machine reading graph
	print('Loading machine reading graph')
	mr_kg = nx.read_gpickle(MR_PATH+MR_GRAPH_NAME)
	if combine_graph:
		print('Combining graphs')
		nx_graph = nx.compose(pl_kg, mr_kg)

	EGCG = obo.CHEBI_4806
	catechin = obo.CHEBI_23053
	greentea = napdi.camellia_sinensis_leaf

	save1 = DIR_OUT + 'EGCG_dexamethasone_simple_path_20.txt'
	save2 = DIR_OUT + 'EGCG_bodyWeight_simple_path_20.txt'
	save3 = DIR_OUT + 'catechin_cyp3a4_simple_path_20.txt'
	save4 = DIR_OUT + 'catechin_hyperglycemia_simple_path_20.txt'

	save_k_simple_paths(nx_graph, EGCG, obo.CHEBI_41879, 20, 20, save1)
	save_k_simple_paths(nx_graph, EGCG, obo.UBERON_0000468, 20, 20, save2)
	save_k_simple_paths(nx_graph, catechin, obo.PR_P08684, 20, 20, save3)
	save_k_simple_paths(nx_graph, catechin, obo.HP_0003074, 20, 20, save4)
	
	'''catechin_list = ['ABCB1_gene', 'Anabolism', 'Biological_Transport', 'Apoptosis', 'Cell_Proliferation', 
				 'Coronary_Arteriosclerosis', 'Cholesterol', 'Cytochrome_P-450_CYP1A1', 'Cytochrome_P-450_CYP1A2',
				 'Cytochrome_P-450_CYP3A4', 'Insulin_Secretion', 'Cisplatin', 'Heart_Diseases', 'Glucose', 
				 'glucose_uptake', 'glucose_transport', 'Hyperglycemia', 'Obesity', 'P-Glycoprotein',
				'UGT1A1_gene', 'Weight_decreased']
	egcg_list = ['1,4-benzoquinone', 'ABCA1_gene', 'Acetaminophen', 'Adenosine_Triphosphatases', 'Autophagy',
			'Bile_Acids', 'Bilirubin', 'Biological_Transport', 'Body_Weight', 'BRCA1_protein,_human',
			 'Cell_Death', 'Cell_Proliferation', 'Cholesterol', 'Cisplatin', 'Collagen', 'Coronary_Arteriosclerosis',
			 'Cytochrome_P-450_CYP1A1', 'Cytochrome_P-450_CYP1A2', 'Cytochrome_P-450_CYP3A4', 'Cytochrome_P-450_CYP2D6',
			 'Cytochrome_P-450_CYP2C19', 'drug_metabolism', 'Dexamethasone', 'Diclofenac', 'Digoxin', 'Dopamine', 
			 'GA-Binding_Protein_Transcription_Factor', 'Gluconeogenesis', 'Glucose_Transporter', 
			 'glucose_transport', 'glucose_uptake', 'Glutathione', 'Glycogen', 'Erythromycin',  'Heart_failure', 
			 'Hemolysis_(disorder)', 'Inflammation', 'Hydrocortisone',
			 'Interleukin-1', 'Interleukin-6', 'Intestinal_Absorption', 'rosoxacin', 'UGT1A1_gene',
			  'Insulin_Secretion', 'Insulin_Resistance', 'Liver_Failure',
			 'Nadolol', 'Obesity', 'Quercetin', 'Tamoxifen', 'Verapamil']
	tea_list = ['ABCB1_gene', 'ABCG2_gene', 'Acetaminophen', 'Biological_Transport', 'Cardiovascular_Diseases',
			'Cerebrovascular_accident', 'Coronary_Arteriosclerosis', 'atorvastatin',  'Benzopyrenes', 'Cholesterol',
			'Cytochrome_P450', 'Cytochromes', 'Cytochrome_P-450_CYP1A1', 'Cytochrome_P-450_CYP1A2',
			'Cytochrome_P-450_CYP3A4', 'Diabetes_Mellitus', 'Diclofenac', 'Digoxin', 'Doxorubicin', 'glucose_transport',
			'Hypertensive_disease', 'Hay_fever', 'Interleukin-10', 'Lipid_Metabolism', 'Liver_diseases', 
			'Low-Density_Lipoproteins', 'Nadolol', 'Obesity', 'glucose_uptake', 'Glutathione',
			'SLC2A1_protein,_human', 'SLC5A1_gene', 'SLCO1A2_gene', 'SLCO2B1_gene', 'Warfarin',
			'rosuvastatin', 'rosoxacin', 'TNFSF11_protein,_human', 'TRPA1_gene', 'TRPV1_gene']'''





