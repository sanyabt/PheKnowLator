#!/usr/bin/env python
# -*- coding: utf-8 -*-

# import needed libraries
import click
import fnmatch
import glob
import logging.config
import networkx  # type: ignore
import os
import ray
import re
import shutil
import subprocess
import traceback

from datetime import datetime
from google.cloud import storage  # type: ignore

from builds.build_utilities import *  # type: ignore
from builds.phase3_log_daemon import PKTLogUploader  # type: ignore
from pkt_kg.__version__ import __version__  # type: ignore
from pkt_kg.utils import *  # type: ignore

# set environment variables
# os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'resources/project_keys/pheknowlator-6cc612b4cbee.json'
# logging
log_dir, log, log_config = 'builds/logs', 'pkt_build_log.log', glob.glob('**/logging.ini', recursive=True)
if os.path.exists(log_dir): shutil.rmtree(log_dir)
os.mkdir(log_dir)
logger = logging.getLogger(__name__)
logging.config.fileConfig(log_config[0], disable_existing_loggers=False, defaults={'log_file': log_dir + '/' + log})


def derives_networkx_graph_statistics(graph) -> str:
    """Derives statistics from an input knowledge graph and prints them to the console. Note that we are not
    converting each node to a string before deriving our counts. This is purposeful as the number of unique nodes is
    altered when you it converted to a string. For example, in the HPO when honoring the RDF type of each node
    there are 406,717 unique nodes versus 406,331 unique nodes when ignoring the RDF type of each node.

    Args:
        graph: An networkx.MultiDiGraph object.

    Returns:
        stats: A formatted string containing descriptive statistics.
    """

    # derive statistics
    nx_graph_und = graph.to_undirected()
    nodes = networkx.number_of_nodes(graph)
    edges = networkx.number_of_edges(graph)
    self_loops = networkx.number_of_selfloops(graph)
    ce = sorted(Counter([str(x[2]) for x in graph.edges(keys=True)]).items(),  # type: ignore
                key=lambda x: x[1],  # type: ignore
                reverse=1)[:6]  # type: ignore
    avg_degree = float(edges) / nodes
    n_deg = sorted([(str(x[0]), x[1]) for x in graph.degree()],  # type: ignore
                   key=lambda x: x[1],  # type: ignore
                   reverse=1)[:6]  # type: ignore
    density = networkx.density(graph)
    components = sorted(list(networkx.connected_components(nx_graph_und)), key=len, reverse=True)
    cc_sizes = {x: len(components[x]) for x in range(len(components))}
    x = '{} nodes, {} edges, {} self-loops, 5 most most common edges: {}, average degree {}, 5 highest degree '\
        'nodes: {}, density: {}, {} component(s) and size(s): {}'
    stats = 'Graph Stats: ' + x.format(nodes, edges, self_loops, ', '.join([x[0] + ':' + str(x[1]) for x in ce]),
                                       avg_degree, ', '.join([x[0] + ':' + str(x[1]) for x in n_deg]),
                                       density, len(components), cc_sizes)

    return stats


def uploads_build_data(bucket, gcs_location) -> None:
    """Methods moves data generated by the knowledge graph construction process from within the docker container to the
    dedicated Google Cloud Storage Bucket for the current build.

    Args:
        bucket: A storage bucket object specifying a Google Cloud Storage bucket.
        gcs_location: A string containing the location for the archive build in the current release directory
            within the dedicated project Google Cloud Storage Bucket.

    Returns:
        None.
    """

    # create variables to store source directory locations
    resources_loc = 'resources/'
    kg_loc = resources_loc + 'knowledge_graphs/'
    metadata_loc = resources_loc + 'node_data/'
    construct_app = resources_loc + 'construction_approach/'

    # move knowledge graph data
    for kg_file in [x for x in glob.glob(kg_loc + '*') if 'README.md' not in x]:
        uploads_data_to_gcs_bucket(bucket, gcs_location, kg_loc, kg_file.split('/')[-1])
    uploads_data_to_gcs_bucket(bucket, gcs_location, resources_loc, 'Master_Edge_List_Dict.json')
    uploads_data_to_gcs_bucket(bucket, gcs_location, resources_loc + 'edge_data/', 'edge_source_metadata.txt')
    uploads_data_to_gcs_bucket(bucket, gcs_location, resources_loc + 'ontologies/', 'ontology_source_metadata.txt')
    uploads_data_to_gcs_bucket(bucket, gcs_location, metadata_loc, 'node_metadata_dict.pkl')
    uploads_data_to_gcs_bucket(bucket, gcs_location, construct_app, 'subclass_map_missing_node_log.json')

    return None


@click.command()
@click.option('--app', prompt='construction approach to use (i.e. instance or subclass)')
@click.option('--rel', prompt='yes/no - adding inverse relations to knowledge graph')
@click.option('--owl', prompt='yes/no - removing OWL Semantics from knowledge graph')
def main(app, rel, owl):

    print('#' * 35 + '\nBUILD PHASE 3: DATA PRE-PROCESSING\n' + '#' * 35)
    logger.info('#' * 5 + 'BUILD PHASE 3: DATA PRE-PROCESSING' + '#' * 5)
    start_time = datetime.now()

    #############################################################################
    # STEP 1 - INITIALIZE GOOGLE STORAGE BUCKET OBJECTS
    print('\nSTEP 1: INITIALIZE GOOGLE STORAGE BUCKET AND REFORMAT INPUT ARGUMENTS')
    logger.info('STEP 1: INITIALIZE GOOGLE STORAGE BUCKET AND REFORMAT INPUT ARGUMENTS')

    # set bucket information and find current archived build directory - chunk gets build name from archived_builds
    release = 'release_v' + __version__
    bucket = storage.Client().get_bucket('pheknowlator')
    bucket_files = [file.name.split('/')[2] for file in bucket.list_blobs(prefix='archived_builds/' + release + '/')]
    builds = [x[0] for x in [re.findall(r'(?<=_)\d.*', x) for x in bucket_files] if len(x) > 0]
    sorted_dates = sorted([datetime.strftime(datetime.strptime(str(x), '%d%b%Y'), '%Y-%m-%d').upper() for x in builds])
    build = 'build_' + datetime.strftime(datetime.strptime(sorted_dates[-1], '%Y-%m-%d'), '%d%b%Y').upper()

    # reformat input arguments and create gcs directory variables
    build_app = 'instance_builds' if app == 'instance' else 'subclass_builds'
    rel_type = 'relations_only' if rel == 'no' else 'inverse_relations'
    owl_decoding = 'owl' if owl == 'no' else 'owlnets'
    arch_string = 'archived_builds/{}/{}/knowledge_graphs/{}/{}/{}/'
    gcs_archive_loc = arch_string.format(release, build, build_app, rel_type, owl_decoding)
    gcs_current_root = 'current_build/'
    gcs_current_loc = '{}knowledge_graphs/{}/{}/{}/'.format(gcs_current_root, build_app, rel_type, owl_decoding)
    gcs_log_root = 'temp_build_inprogress/'
    gcs_log_location = '{}knowledge_graphs/{}/{}/{}/'.format(gcs_log_root, build_app, rel_type, owl_decoding)

    uploads_data_to_gcs_bucket(bucket, gcs_log_location, log_dir, log)  # uploads log to gcs bucket

    #############################################################################
    # STEP 2 - CONSTRUCT KNOWLEDGE GRAPH
    print('\nSTEP 2: CONSTRUCT KNOWLEDGE GRAPH')
    print('Knowledge Graph Build: {} + {} + {}.txt'.format(app, rel_type.lower(), owl_decoding.lower()))
    logger.info('STEP 2: CONSTRUCT KNOWLEDGE GRAPH')
    logger.info('Knowledge Graph Build: {} + {} + {}.txt'.format(app, rel_type.lower(), owl_decoding.lower()))

    ray.init()  # start background process to upload logs while the pkt main knowledge graph function runs
    background_task = PKTLogUploader.remote('pheknowlator', gcs_log_location, log_dir, 90)
    logger.info('RAN THE CONSTRUCT KNOWLEDGE GRAPH CODE')
    # run the pkt_kg main method
    command = 'python Main.py --onts resources/ontology_source_list.txt --edg resources/edge_source_list.txt ' \
              '--res resources/resource_info.txt --out ./resources/knowledge_graphs --nde yes --kg full ' \
              '--app {} --rel {} --owl {}'
    try:
        return_code = os.system(command.format(app, rel, owl))
        if return_code != 0:
            logger.error('ERROR: Program Finished with Errors: {}'.format(return_code))
            raise Exception('ERROR: Program Finished with Errors: {}'.format(return_code))
    except: logger.error('ERROR: Uncaught Exception: {}'.format(traceback.format_exc()))
    background_task.__ray_terminate__.remote()  # kills the process with an `exit(0)`
    ray.shutdown()

    uploads_data_to_gcs_bucket(bucket, gcs_log_location, log_dir, log)  # uploads log to gcs bucket

    #############################################################################
    # STEP 3 - UPLOAD BUILD DATA TO GOOGLE CLOUD STORAGE
    print('\nSTEP 3: UPLOAD KNOWLEDGE GRAPH DATA TO GOOGLE CLOUD STORAGE')
    logger.info('STEP 3: UPLOAD KNOWLEDGE GRAPH DATA TO GOOGLE CLOUD STORAGE')

    # remove data from current_build directory before writing new data
    print('Removing Existing Data from Current Build Directory on Google Cloud Storage')
    logging.info('Removing Existing Data from Current Build Directory on Google Cloud Storage')
    # data directories
    deletes_bucket_files(bucket, gcs_current_root + 'data/')
    bucket.blob(gcs_current_root + 'data/original_data/').upload_from_string('')
    bucket.blob(gcs_current_root + 'data/processed_data/').upload_from_string('')
    # knowledge graph directories -- clearing data for a particular build
    deletes_bucket_files(bucket, gcs_current_loc)
    bucket.blob(gcs_current_loc).upload_from_string('')

    # move Docker data to current_builds Google Cloud Storage Bucket
    print('Uploading Knowledge Graph Data from Docker to the current_build Directory')
    logger.info('Uploading Knowledge Graph Data from Docker to the current_build Directory')
    uploads_build_data(bucket, gcs_current_loc)
    uploads_data_to_gcs_bucket(bucket, gcs_log_location, log_dir, log)  # uploads log to gcs bucket
    # copy data from the current_builds Google Cloud Storage Bucket to the archived_builds Google Cloud Storage Bucket
    print('Copying Knowledge Graph Data from the current_build Directory to the archived_builds Directory')
    logger.info('Copying Knowledge Graph Data from the current_build Directory to the archived_builds Directory')
    source_data = [_.name.split('/')[-1] for _ in bucket.list_blobs(prefix=gcs_current_loc)]
    copies_data_between_gcs_bucket_directories(bucket, gcs_current_loc, gcs_archive_loc, source_data)
    uploads_data_to_gcs_bucket(bucket, gcs_log_location, log_dir, log)  # uploads log to gcs bucket

    # copy archived_data/data to current_build/data
    source_dir, destination_dir = 'archived_builds/{}/{}/data/'.format(release, build), gcs_current_root + 'data/'
    source_data = ['/'.join(_.name.split('/')[-2:]) for _ in bucket.list_blobs(prefix=source_dir)]
    print('Copying Data FROM: {} TO: {}'.format(source_dir, destination_dir))
    logger.info('Copying Data FROM: {} TO: {}'.format(source_dir, destination_dir))
    copies_data_between_gcs_bucket_directories(bucket, source_dir, destination_dir, source_data)
    uploads_data_to_gcs_bucket(bucket, gcs_log_location, log_dir, log)

    #############################################################################
    # STEP 4 - PRINT BUILD STATISTICS
    print('\nSTEP 4: DERIVING NETWORK STATISTICS FOR BUILD KNOWLEDGE GRAPHS')
    logger.info('STEP 4: DERIVING NETWORK STATISTICS FOR BUILD KNOWLEDGE GRAPHS')

    # find Networkx MultiDiGraph files in Google Cloud Storage Bucket for build
    try:
        kg_files = [f.name for f in bucket.list_blobs(prefix=gcs_current_loc) if f.name.endswith('gpickle')]
        for f in kg_files:
            print('Loading graph data: {}'.format(f.split('/')[-1]))
            logger.info('Loading graph data: {}'.format(f.split('/')[-1]))
            # download and load graph file
            f_name = f.split('/')[-1]
            graph = networkx.read_gpickle(downloads_data_from_gcs_bucket(bucket, None, gcs_current_loc, f_name, ''))
            stats = derives_networkx_graph_statistics(graph)
            print(stats)
            logger.info(stats)
    except: logger.error('ERROR: Uncaught Exception: {}'.format(traceback.format_exc()))

    uploads_data_to_gcs_bucket(bucket, gcs_log_location, log_dir, log)  # uploads log to gcs bucket

    #############################################################################
    # STEP 5 - CLEAN UP BUILD ENVIRONMENT + LOG EXIT STATUS TO FINISH RUN
    print('\nSTEP 5: BUILD CLEAN-UP')
    logger.info('STEP 5: BUILD CLEAN-UP')
    runtime = round((datetime.now() - start_time).total_seconds() / 60, 3)
    print('\n\n' + '*' * 5 + ' COMPLETED BUILD PHASE 3: {} MINUTES '.format(runtime) + '*' * 5)
    logger.info('COMPLETED BUILD PHASE 3: {} MINUTES'.format(runtime))  # don't delete needed for build monitoring
    logger.info('EXIT BUILD PHASE 3')  # don't delete needed for build monitoring
    uploads_data_to_gcs_bucket(bucket, gcs_current_loc, log_dir, log)  # to store final log in current_build dir

    # copy build logs
    print('Copying Logs from the current_build Directory to the archived_builds Directory')
    logger.info('Copying Logs from the current_build Directory to the archived_builds Directory')
    log_1 = [x for x in [_.name for _ in bucket.list_blobs(prefix=gcs_log_root)] if x.endswith('phases12_log.log')]
    copies_data_between_gcs_bucket_directories(bucket, gcs_log_root, gcs_archive_loc, [log_1[0].split('/')[-1]])
    copies_data_between_gcs_bucket_directories(bucket, gcs_log_root, gcs_current_root, [log_1[0].split('/')[-1]])
    copies_data_between_gcs_bucket_directories(bucket, gcs_current_loc, gcs_archive_loc, [log])

    # exit build
    uploads_data_to_gcs_bucket(bucket, gcs_log_location, log_dir, log)  # uploads log to gcs bucket

    return None


if __name__ == '__main__':
    main()
