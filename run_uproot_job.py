import argparse
import os
from datetime import datetime
import json
import time
import sqlite3
import tqdm

import numpy as np

from coffea.util import save, load
from coffea import hist
from coffea.processor import funcx_executor, run_uproot_job, futures_executor

import parsl
from parsl.channels import LocalChannel
from parsl.configs.htex_local import config

from parsl.providers import LocalProvider
from parsl.channels import LocalChannel

from parsl.config import Config
from parsl.executors import HighThroughputExecutor

import funcx
funcx.set_file_logger('funcx.log')

parser = argparse.ArgumentParser()
parser.add_argument("connected_managers", help="number of connected managers")
parser.add_argument("--analyses", default=1, help="number of concurrent analyses")
# parser.add_argument("--tag", default='xrootd_stageout', help="any extra info to save to DB")
parser.add_argument("--tag", default='file_stageout', help="any extra info to save to DB")
parser.add_argument("--cores_per_manager", default=28)
parser.add_argument("--chunksize", default=200000)
# parser.add_argument("--chunksize", default=75000)
parser.add_argument("--test", default=False, action="store_true", help='only dispatch a small test')
args = parser.parse_args()

ndt3_cuid = '1c0434db-1e2d-43c1-86ae-e2c80b6d25ae'
ndcrc_uuid = '8bd5cb36-1eec-4769-b001-6b34fa8f9dc7'
wisconsin_uuid = 'af21d0db-27f2-4906-beba-6baffac18393'
midway_uuid = 'aebefb11-9a24-4912-96ff-d03c4f551802'

db = sqlite3.connect('coffea.db')
db.execute("""create table if not exists analyses(
    tag text,
    returned int,
    submitted int,
    chunksize int,
    chunks int,
    connected_managers int,
    cores_per_manager int,
    concurrent_analyses int
    )""")
db.commit()
db.close()

metadata_cache = {}
if os.path.isfile('metadata.cache'):
    metadata_cache = load('metadata.cache')

with open('samplefiles.json') as f:
    datasets = json.load(f)
    # dataset = datasets['Hbb_2017']
    dataset = datasets["Hbb_2017_ndscratch"]
if args.test:
    dataset = dict((k, v) for k, v in list(dataset.items())[:3])

submitted = time.time()

print('[{}] starting submission'.format(datetime.now().strftime("%H:%M:%S")))
final_accumulator, metrics = run_uproot_job(
    dataset,
    'otree',
    load('boostedHbbProcessor.coffea'),
    funcx_executor,
    executor_args={
        # 'local_path': '/hadoop/store/user/awoodard/data',
        # 'stageout_url': 'root://deepthought.crc.nd.edu://store/user/awoodard/data',
        # 'local_path': '/scratch365/awoodard/funcx',
        # 'stageout_url': 'file:///scratch365/awoodard/funcx',
        'local_path': '/scratch/midway2/annawoodard/funcx/results',
        'stageout_url': 'file:///scratch/midway2/annawoodard/funcx/results',
        'endpoints': [midway_uuid],
        'skipbadfiles': True,
        'savemetrics': True,
        'xrootdtimeout': 20,
        # 'poll_period': 5,
        'poll_period': 30,
        # 'tailtimeout': 500,
        # 'tailretry': 90,
        # 'batch_size': 500,
        'funcx_service_address': 'https://dev.funcx.org/api/v1'
        # 'funcx_service_address': 'https://funcx.org/api/v1'
    },
    pre_executor=futures_executor,
    chunksize=args.chunksize,
    metadata_cache=metadata_cache
)
returned = time.time()
print(metrics)
print(final_accumulator)
print('job returned in {:.1f}s'.format(returned - submitted))

save(metadata_cache, 'metadata.cache')

db = sqlite3.connect('coffea.db')
db.execute("""insert into analyses(
    tag,
    returned,
    submitted,
    chunksize,
    chunks,
    connected_managers,
    cores_per_manager,
    concurrent_analyses
    )
    values (?, ?, ?, ?, ?, ?, ?, ?)""", (
        args.tag,
        returned,
        submitted,
        args.chunksize,
        metrics['chunks'].value,
        args.connected_managers,
        args.cores_per_manager,
        args.analyses
    )
)
db.commit()
db.close()
