import argparse
import os
import time
import sqlite3
from tqdm.auto import tqdm

import funcx
from coffea.processor.funcx.detail import FuncXFuture
funcx.set_file_logger('funcx.log')

client = funcx.sdk.client.FuncXClient(funcx_service_address='https://dev.funcx.org/api/v1')

parser = argparse.ArgumentParser()
parser.add_argument("--tasks_per_core", default=10, help="number of cores per task")
parser.add_argument("--sleep", default=60, help="number of cores per task")
parser.add_argument("--tag", default='after yadu updates', help="any extra info to save to DB")
parser.add_argument("--cores_per_manager", default=16)
parser.add_argument("--endpoint", default='fccc596c-762b-4a00-a642-ecafda1b982f')
args = parser.parse_args()

db = sqlite3.connect('data.db')
db.execute("""create table if not exists analyses(
    tag text,
    start_submit,
    end_submit,
    returned int,
    tasks int,
    connected_managers int,
    cores_per_manager int,
    sleep_seconds int
    )""")
db.commit()
db.close()

def sleep(seconds, fake_args):
    import time
    import random
    import string

    time.sleep(seconds)

    return ''.join(random.choice(string.ascii_lowercase) for i in range(10))

if not os.path.isfile('sleep_uuid.txt'):
    sleep_uuid = client.register_function(sleep)
    with open('sleep_uuid.txt', 'w') as f:
        print(sleep_uuid, file=f)
else:
    with open('sleep_uuid.txt', 'r') as f:
        sleep_uuid = f.read().strip()

fake_args = [
        ('VBFHToBB_M_125_13TeV_powheg_pythia8_weightfix',
        'root://cmseos.fnal.gov//eos/uscms/store/user/lpcbacon/dazsle/zprimebits-v15.01/skim/VBFHToBB_M_125_13TeV_powheg_pythia8_weightfix_0.root',
        'otree',
        59309,
        0),
        'file:///scratch365/awoodard/funcx'
]

with open(os.path.expanduser('~/connected_managers'), 'r') as f:
    connected_managers = int(f.read())

cores = connected_managers * args.cores_per_manager
tasks = int(args.tasks_per_core * cores)

start_submit = time.time()

futures = []
for t in tqdm(range(tasks), unit='tasks', total=tasks, desc='submission'):
    try:
        futures += [FuncXFuture(client.run(
                args.sleep,
                fake_args,
                endpoint_id=args.endpoint,
                function_id=sleep_uuid
                )
            )
        ]
    except Exception as e:
        time.sleep(1)
        print(e)


end_submit = time.time()

while len(futures) > 0:
    for index, f in enumerate(futures):
        if f.done():
            f.result()
            futures.pop(index)

returned = time.time()
print('finished in {:.0f}s'.format(returned - start_submit))

db = sqlite3.connect('data.db')
db.execute("""insert into analyses(
    tag,
    start_submit,
    end_submit,
    returned,
    tasks,
    connected_managers,
    cores_per_manager,
    sleep_seconds
    )
    values (?, ?, ?, ?, ?, ?, ?, ?)""", (
        args.tag,
        start_submit,
        end_submit,
        returned,
        tasks,
        connected_managers,
        args.cores_per_manager,
        args.sleep
    )
)
db.commit()
db.close()
