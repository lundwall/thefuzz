# Use an official Ubuntu as a parent image
FROM ubuntu:latest

# Install openssh-server
RUN apt-get update && \
    apt-get install -y openssh-server && \
    mkdir /var/run/sshd

RUN apt-get install -y python3

# Create user for ssh access
RUN useradd -rm -d /home/ubuntu -s /bin/bash -g root -G sudo -u 1001 ubuntu
RUN echo 'ubuntu:ubuntu' | chpasswd

# Allow root login and password authentication
RUN echo "PermitRootLogin yes" >> /etc/ssh/sshd_config
RUN echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config

# Expose the ssh port
EXPOSE 22

# Run sshd in the foreground
CMD ["/usr/sbin/sshd", "-D"]
