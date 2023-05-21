# thefuzz

### Setup:

Check `config.yaml` and modify if necessary.

Add modules to test, for example by running:
```
git clone --depth 1 --branch v2.14.5 https://github.com/ansible/ansible ansible
```
```
git clone --depth 1 --branch 6.6.0 https://github.com/ansible-collections/community.general.git community
```

Then build the 2 docker images we need, the 'host' and the 'target':
```
docker build --tag 'ansible:host' host
docker build --tag 'ansible:target' target
```

To start testing, run: `python3 test_ansible_roles.py`
