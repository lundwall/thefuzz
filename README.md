# thefuzz

### Setup:

Check `config.yaml` and run:

Then Build the 2 docker images we need, the 'host' and the 'target'

```
docker build --tag 'ansible:host' - < ./host/Dockerfile
docker build --tag 'ansible:target' - < ./target/Dockerfile
```

`python3 test_ansible_roles.py`
