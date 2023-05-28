FROM python:3.10

RUN apt-get update

# Necessary to use different locales
RUN apt-get -y install locales locales-all

# Copy the modules to the image
COPY modules /modules

# Faster than installing from the copied module repos
RUN python3 -m pip install https://github.com/ansible/ansible/archive/v2.14.5.tar.gz
RUN ansible-galaxy collection install community.general

RUN apt install -y sshpass

COPY host/ansible /etc/ansible
COPY host/.ssh /home/.ssh

# Puppet stuff
RUN apt install -y ruby
RUN wget https://apt.puppet.com/puppet-tools-release-bullseye.deb
RUN dpkg -i puppet-tools-release-bullseye.deb
RUN apt-get update
RUN apt-get install -y pdk
RUN ln -s /bin/mkdir /usr/bin/mkdir
RUN gem install beaker-hostgenerator

# Docker-in-Docker-stuff
RUN install -m 0755 -d /etc/apt/keyrings
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
RUN chmod a+r /etc/apt/keyrings/docker.gpg
RUN echo \
  "deb [arch="$(dpkg --print-architecture)" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  "$(. /etc/os-release && echo "$VERSION_CODENAME")" stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null
RUN apt-get update
RUN apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

## To stop container immedietly exiting
ENTRYPOINT ["tail"]
CMD ["-f","/dev/null"]