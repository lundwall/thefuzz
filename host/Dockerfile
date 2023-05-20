FROM python:3.10

RUN apt-get update

# Necessary to use different locales
RUN apt-get -y install locales locales-all

RUN python3 -m pip install https://github.com/ansible/ansible/archive/v2.14.5.tar.gz
RUN ansible-galaxy collection install community.general

# Download repos to get the test suites
RUN git clone --depth 1 --branch v2.14.5 https://github.com/ansible/ansible /ansible
RUN git clone --depth 1 --branch 6.6.0 https://github.com/ansible-collections/community.general.git /community


## To stop container immedietly exiting
ENTRYPOINT ["tail"]
CMD ["-f","/dev/null"]