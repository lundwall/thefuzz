# thefuzz

### Setup:

Check `config.yaml` and modify if necessary.

Add modules to test in a `modules` folder, for example by running:
```
mkdir modules
git clone --depth 1 --branch v2.14.5 https://github.com/ansible/ansible modules/ansible
git clone --depth 1 --branch 6.6.0 https://github.com/ansible-collections/community.general.git modules/community
git clone --depth 1 --branch v6.1.2 https://github.com/voxpupuli/puppet-archive.git modules/puppet-archive
```

Then build the two docker images we need, the 'host' and the 'target':
```
docker build --tag 'testing:host' -f host/Dockerfile .
docker build --tag 'testing:target' -f target/Dockerfile .
```

To start testing, run: 
```
pip install -r requirements.txt
python test_ansible_roles.py
```

To reproduce a bug, run: 
```
REPRODUCE=lineinfile python test_ansible_roles.py --config config_lineinfile.yaml
```
or
```
REPRODUCE=rhms python test_ansible_roles.py --config config_rhsm.yaml
```