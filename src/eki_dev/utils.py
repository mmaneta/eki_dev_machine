import os
import subprocess
from rich.pretty import pprint
from pathlib import Path


# Show task progress (red for download, green for extract)
def show_progress(line, progress, tasks):

    if line['status'] == 'Downloading':
        #id_ = f'[red][Download {line["id"]}]'
        pprint(f'Downloading: {line["id"]}')
        return
    elif line['status'] == 'Extracting':
        id_ = f'[green][Extract  {line["id"]}]'
    else:
        # skip other statuses
        return

    if id_ not in tasks.keys():
        tasks[id_] = progress.add_task(f"{id_}", total=line['progressDetail']['total'])
    #else:
    progress.update(tasks[id_], completed=line['progressDetail']['current'])


def register_instance(
        name : str,
        host_ip : str,
        CONFIG_DIR='.dev_machine',
              ) -> str:
    HOME = os.path.expanduser("~")
    dev_machine_dir = os.path.join(HOME, CONFIG_DIR)
    Path(dev_machine_dir).mkdir(parents=False, exist_ok=True)
    p = os.path.join(dev_machine_dir, name + "@" + host_ip)
    Path(p).touch()
    return p


def deregister_instance(name : str,
                        host_ip : str,
                        CONFIG_DIR='.dev_machine')->str:
    HOME = os.path.expanduser("~")
    p = os.path.join(HOME, CONFIG_DIR, name + "@" + host_ip)
    try:
        os.remove(p)
    except FileNotFoundError:
        pass
    return p


def ssh_splitter(ssh_connect_string):
    ssh_connect_string = ssh_connect_string.replace('ssh://', '')
    user_host, _, path = ssh_connect_string.partition(':')
    user, _, host = user_host.rpartition('@')
    return user, host, path


def ssh_tunnel(user: str,
               host: str,
               jupyter_port: int,
               dask_port: int,
               ):
    tunnel_cmd = f"ssh -f -N -L {jupyter_port}:localhost:{jupyter_port} -L {dask_port}:localhost:{dask_port} {user}@{host}"
    proc = subprocess.Popen(tunnel_cmd, shell=True, stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE, executable="/bin/bash")
    stdout, stderr = proc.communicate()
    if proc.returncode != 0:
        raise ConnectionError(stderr)
    return tunnel_cmd
