import copy
import os.path
import json
from pathlib import Path
import random
import string

from fixtures import (ec2_config,
                        aws_credentials,
                        aws_s3,
                        create_test_bucket,
                      bucket_with_project_tags)
from moto import mock_aws

from eki_dev.utils import (
    ssh_tunnel,
    ssh_splitter,
    register_instance,
    deregister_instance,
    add_instance_tags,
    get_project_tags,
    Config,
    generate_makefile,
    update_dict
)


def test_update_dict(mocker):
    user_conf = {}
    m = mocker.patch('importlib_resources.files')
    m.return_value = Path('.')
    config = Config()

    conf = copy.deepcopy(config.conf)

    random_string = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
    user_conf["Ec2Instance"] = {"Properties": {"KeyName": random_string}}

    assert conf["Ec2Instance"]["Properties"]["KeyName"] != random_string

    update_dict(conf, user_conf)

    assert conf["Ec2Instance"]["Properties"]["KeyName"] == random_string


def test_generate_makefile():
    tmpl = generate_makefile("test_image", "test_repo", makefile_name='test_makefile')
    with open('test_makefile') as f:
        assert len(tmpl) > 0
        assert tmpl is not None
        assert f.read() == tmpl
    os.remove('test_makefile')


class TestConfig:
    def setUp(self):
        pass

    def test_constructor(self, mocker):
        m = mocker.patch('importlib_resources.files')
        m.return_value = Path('.')
        config = Config()

        assert isinstance(config.conf, dict)
        assert isinstance(config.user_conf, dict)

    def test_retrieve_config(self, mocker):
        m = mocker.patch('importlib_resources.files')
        m.return_value = Path('.')
        config = Config('.')
        dct_conf = config.retrieve_configuration()

        assert dct_conf is not config.conf
        assert dct_conf["Ec2Instance"]["Properties"]["KeyName"] != config.conf["Ec2Instance"]["Properties"][
            "KeyName"]
        assert dct_conf["Ec2Instance"]["Properties"]["KeyName"] == config.user_conf["Ec2Instance"]["Properties"]["KeyName"]

    def test_write_config(self, mocker):
        m = mocker.patch('importlib_resources.files')
        m.return_value = Path('.')
        config = Config(path_config_dir='.')
        random_string = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
        config.conf["Ec2Instance"]["Properties"]["KeyName"] = random_string
        config.write_configuration()

        config2 = Config(path_config_dir='.')
        assert config2.conf["Ec2Instance"]["Properties"]['KeyName'] == random_string
        try:
            os.remove('config')
        except FileNotFoundError:
            pass

    def test_write_user_config(self, mocker):
        m = mocker.patch('importlib_resources.files')
        m.return_value = Path('.')
        config = Config(path_config_dir='.')
        random_string = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))
        config.update_ssh_key_name(random_string)
        config.write_user_configuration()

        config2 = Config(path_config_dir='.')
        assert config2.user_conf["Ec2Instance"]["Properties"]['KeyName'] == random_string
        try:
            os.remove('config')
        except FileNotFoundError:
            pass

    @mock_aws
    def test_create_ssh_keys(self, mocker):
        m = mocker.patch('importlib_resources.files')
        m.return_value = Path('.')
        path_config_dir = '.'
        Config(path_config_dir=path_config_dir).create_ssh_keys("test_key")

        assert os.path.exists(os.path.expanduser('~/.ssh/test_key.pem'))

        assert Config(path_config_dir=path_config_dir).user_conf["Ec2Instance"]["Properties"]['KeyName'] == "test_key"
        os.remove(os.path.expanduser('~/.ssh/test_key.pem'))
        os.remove('config')

@mock_aws
def test_get_project_tags(bucket_with_project_tags):
    assert get_project_tags(bucket='eki-dev-machine-config') == ['dev', 'eki_training', 'test_project']


def test_add_instance_tags(ec2_config):
    instance_attrs = json.loads(ec2_config)["Ec2Instance"]["Properties"]
    instance_attrs = add_instance_tags('test_project', **instance_attrs)

    assert instance_attrs['TagSpecifications'][0] ['ResourceType'] == 'instance'
    assert instance_attrs['TagSpecifications'][0]['Tags'][0]['Key'] == 'user'
    assert instance_attrs['TagSpecifications'][0]['Tags'][1]['Key'] == 'project'


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




# def test_ssh_tunnel_connection_error():
#
#     with pytest.raises(ConnectionError) as e:
#         ssh_tunnel(user='test_user',
#                host='10.10.10.10',
#                jupyter_port=8888,
#                dask_port=8889)
#
#     assert "Connection refused" in str(e.value.args[0])


def test_ssh_splitter_with_ssh():
    assert list(ssh_splitter('ssh://test_user@1.0.1.1:22')) == ['test_user', '1.0.1.1', '22']


def test_ssh_splitter_without_ssh():
    assert list(ssh_splitter('test_user@1.0.1.1:22')) == ['test_user', '1.0.1.1', '22']


def test_ssh_splitter_without_user():
    assert list(ssh_splitter('ssh://1.0.1.1:22')) == ['', '1.0.1.1', '22']


def test_ssh_splitter_without_port():
    assert list(ssh_splitter('ssh://1.0.1.1')) == ['', '1.0.1.1', '']