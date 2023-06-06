# thefuzz

### What is this?

thefuzz is a tool to test configuration management libraries, such as Ansible or Puppet. As the tool monitors (polices) the output of the integration tests under targeted transformations, we call it _thefuzz_, [british slang for police](https://www.urbandictionary.com/define.php?term=the+fuzz).

### Setup:

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
python thefuzz.py --modules lineinfile read_csv puppet-archive --new
```
The `--new` flag will create a new config file for the specified modules, and the transformations can be tweaked if needed.

To reproduce a bug, run: 
```
REPRODUCE=lineinfile python thefuzz.py --config config_lineinfile.yaml
```
or
```
REPRODUCE=rhsm python thefuzz.py --config config_rhsm.yaml
```