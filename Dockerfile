FROM python:3.10

RUN apt-get update
RUN apt-get -y install locales locales-all
RUN python3 -m pip install https://github.com/ansible/ansible/archive/v2.14.5.tar.gz
RUN git clone --depth 1 --branch v2.14.5 https://github.com/ansible/ansible /ansible