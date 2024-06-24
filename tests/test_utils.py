import os.path

import pytest

from eki_dev.utils import (
    ssh_tunnel,
    ssh_splitter,
    register_instance,
    deregister_instance
)


def test_register_deregister_instance():
    user_folder = '.test_user'
    name = "test"
    host_ip = "10.01.01.01"
    home = os.path.expanduser("~")

    register_instance(name, host_ip, CONFIG_DIR=user_folder)

    assert os.path.exists(os.path.join(home, user_folder, name+"@"+host_ip))

    deregister_instance(name, host_ip, CONFIG_DIR=user_folder)
    assert not os.path.exists(os.path.join(home, user_folder, name + "@" + host_ip))

    os.rmdir(os.path.join(home, user_folder))




def test_ssh_tunnel_connection_error():

    with pytest.raises(ConnectionError) as e:
        ssh_tunnel(user='test_user',
               host='10.10.10.10',
               jupyter_port=8888,
               dask_port=8889)

    assert "Connection refused" in str(e.value.args[0])


def test_ssh_splitter_with_ssh():
    assert list(ssh_splitter('ssh://test_user@1.0.1.1:22')) == ['test_user', '1.0.1.1', '22']


def test_ssh_splitter_without_ssh():
    assert list(ssh_splitter('test_user@1.0.1.1:22')) == ['test_user', '1.0.1.1', '22']


def test_ssh_splitter_without_user():
    assert list(ssh_splitter('ssh://1.0.1.1:22')) == ['', '1.0.1.1', '22']


def test_ssh_splitter_without_port():
    assert list(ssh_splitter('ssh://1.0.1.1')) == ['', '1.0.1.1', '']