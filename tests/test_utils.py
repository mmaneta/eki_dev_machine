import pytest

from eki_dev.utils import (
    ssh_tunnel,
    ssh_splitter
)


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