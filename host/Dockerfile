FROM python:3.10

RUN apt-get update

# Necessary to use different locales
RUN apt-get -y install locales locales-all

RUN python3 -m pip install https://github.com/ansible/ansible/archive/v2.14.5.tar.gz
RUN ansible-galaxy collection install community.general

# Download repos to get the test suites
RUN git clone --depth 1 --branch v2.14.5 https://github.com/ansible/ansible /ansible
RUN git clone --depth 1 --branch 6.6.0 https://github.com/ansible-collections/community.general.git /community

RUN apt install -y sshpass

# RUN mkdir /etc/ansible
# RUN touch /etc/ansible/hosts
# RUN bash -c "echo [test_target] > /etc/ansible/hosts"

# RUN mkdir /home/.ssh
# RUN touch /home/.ssh/config
# RUN bash -c "echo 'Host * \n StrictHostKeyChecking no '> /home/.ssh/config"
COPY ansible /etc/ansible
COPY .ssh /home/.ssh

## To stop container immedietly exiting
ENTRYPOINT ["tail"]
CMD ["-f","/dev/null"]