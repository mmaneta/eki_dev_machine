from setuptools import setup, find_packages

long_description = '''
Utilities to launch, provision, and delete aws host servers. 

'''

config = {
    'name': 'dev_machine',
    'version': '0.0.1.dev0',
    'author': 'Marco Maneta',
    'author_email': 'mmaneta@ekiconsult.com',
    'description': 'EDI development machine ',
    'long_description': long_description,
    'long_description_content_type': 'text/markdown',
    'url': '',
    'download_url': '',
    'include_package_data': True,
    'install_requires': [ # 
        'pyyaml', 'boto3', 'docker'
    ],
    'extras_require': {
        'test': ['pytest', 'moto', 'black']
    },  
    'packages': find_packages(where='src'),
    'package_dir': {"aws_cluster": "src/aws_cluster",
                    "eki_dev": "src/eki_dev"},
    
    'package_data': {'eki_dev': ['*.yaml']},
    #'entry_point': {'console_scripts': ['bin.dev_machine']},
    'scripts': [  
        'bin/dev_machine.py',
    ],
}

setup(**config)
