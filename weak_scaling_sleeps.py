import argparse
import os
import time
import sqlite3
from tqdm.auto import tqdm

import funcx
from coffea.processor.funcx.detail import MappedFuncXFuture
funcx.set_file_logger('funcx.log')

client = funcx.sdk.client.FuncXClient(funcx_service_address='https://dev.funcx.org/api/v1')

parser = argparse.ArgumentParser()
parser.add_argument("--tasks_per_core", default=10, help="number of cores per task")
parser.add_argument("--sleep", default=60, help="number of cores per task")
parser.add_argument("--tag", default='after yadu updates', help="any extra info to save to DB")
parser.add_argument("--cores_per_manager", default=28)
parser.add_argument("--endpoint", default='07ad6996-3505-4b86-b95a-aa33acf842d8')
parser.add_argument("--batch_size", default=5000)

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

def sleep(fake_args):
    import time
    import random
    import string

    time.sleep(60)

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
task_args = [fake_args for _ in range(tasks)]
batched_args = [task_args[i:i + args.batch_size] for i in range(0, len(task_args), args.batch_size)]

start_submit = time.time()
futures = []
for batch in batched_args:
    futures += [MappedFuncXFuture(client.map_run(batch, endpoint_id=args.endpoint, function_id=sleep_uuid))]
    print('submitted batch of {} tasks'.format(len(batch)))

end_submit = time.time()

print([f.result() for f in futures])

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
